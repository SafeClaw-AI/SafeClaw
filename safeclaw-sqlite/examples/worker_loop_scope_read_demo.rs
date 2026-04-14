use std::{
    env, fs,
    path::{Path, PathBuf},
    process,
    time::{SystemTime, UNIX_EPOCH},
};

use safeclaw_core::{
    effect_ledger::{
        EffectAction, EffectActor, EffectRecord, EffectReversibility, EffectTier, ProbeMode,
    },
    InMemoryTaskRuntime, OrchestratorClaim, OrchestratorSnapshot, OrchestratorTask,
    PreflightDecision, ScheduleIntent, TaskOrchestrator,
};
use safeclaw_sqlite::{
    open_database, SandboxCommand, SqliteOpenOptions, SqliteRuntimeStore, SqliteSingleWorkerLoop,
    SqliteTaskOrchestrator,
};

fn main() -> Result<(), String> {
    let workspace = into_demo(env::current_dir())?;
    let temp = DemoArtifacts::new(&workspace)?;
    let shared_scope = format!("scope:{}", temp.root.join("shared.txt").display());
    let write_after_output = temp.root.join("worker-loop-shared-write-after.txt");

    let mut blocking_orchestrator =
        into_demo(open_database(temp.db_path(), SqliteOpenOptions::default()))
            .map(SqliteTaskOrchestrator::new)?
            .with_lease_ttl_ms(60_000);
    into_demo(blocking_orchestrator.enqueue(OrchestratorTask::new(
        "task-worker-read-write-active",
        ScheduleIntent::write(shared_scope.clone()),
        0,
    )))?;
    into_demo(blocking_orchestrator.enqueue(OrchestratorTask::new(
        "task-worker-read-shared",
        ScheduleIntent::read(shared_scope.clone()),
        1,
    )))?;
    into_demo(blocking_orchestrator.enqueue(OrchestratorTask::new(
        "task-worker-read-write-after",
        ScheduleIntent::write(shared_scope.clone()),
        2,
    )))?;
    print_snapshot("after-enqueue", blocking_orchestrator.queue_snapshot());

    let blocking_claim = into_demo(blocking_orchestrator.claim_next("worker-a", 0))?
        .expect("initial shared write must be claimable");
    println!(
        "[demo] blocking write claim => task={} lease={} fence={} owner={}",
        blocking_claim.task.task_id,
        blocking_claim.lease.lease_id,
        blocking_claim.lease.fencing_token,
        blocking_claim.lease.owner_id
    );
    print_snapshot(
        "after-blocking-write-claim",
        blocking_orchestrator.queue_snapshot(),
    );

    let mut read_worker = into_demo(SqliteSingleWorkerLoop::open(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?
    .with_lease_ttl_ms(60_000);
    let read_outcome = into_demo(read_worker.claim_and_drive_once(
        "worker-b",
        1,
        PreflightDecision::Permit,
        |claim| {
            Ok((
                InMemoryTaskRuntime::new(build_demo_effect(
                    claim,
                    "effect-worker-read-shared",
                    "trace-worker-read-shared",
                    "intent-worker-read-shared",
                    EffectAction::NetworkRequest,
                )),
                sandbox_success_command(),
            ))
        },
    ))?
    .expect("same-scope read must remain claimable");
    println!(
        "[demo] same-scope read claimed => task={} owner={} completed={}",
        read_outcome.claim.task.task_id, read_outcome.claim.lease.owner_id, read_outcome.completed
    );
    print_snapshot("after-read-complete", read_worker.queue_snapshot());

    let mut blocked_worker = into_demo(SqliteSingleWorkerLoop::open(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?
    .with_lease_ttl_ms(60_000);
    let blocked = into_demo(blocked_worker.claim_and_drive_once(
        "worker-c",
        2,
        PreflightDecision::Permit,
        |_| unreachable!(),
    ))?;
    println!(
        "[demo] remaining write still blocked => {}",
        blocked.is_none()
    );

    into_demo(blocking_orchestrator.complete(
        &blocking_claim.task.task_id,
        &blocking_claim.lease.lease_id,
        &blocking_claim.lease.owner_id,
    ))?;
    print_snapshot(
        "after-release-blocking-write",
        blocking_orchestrator.queue_snapshot(),
    );

    let mut write_worker = into_demo(SqliteSingleWorkerLoop::open(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?
    .with_lease_ttl_ms(60_000);
    let write_outcome = into_demo(write_worker.claim_and_drive_once(
        "worker-c",
        3,
        PreflightDecision::Permit,
        |claim| {
            Ok((
                InMemoryTaskRuntime::new(build_demo_effect(
                    claim,
                    "effect-worker-read-write-after",
                    "trace-worker-read-write-after",
                    "intent-worker-read-write-after",
                    EffectAction::FileWrite,
                )),
                sandbox_write_command(&write_after_output, b"safeclaw write after shared read\n"),
            ))
        },
    ))?
    .expect("same-scope write must unblock after active lease release");
    println!(
        "[demo] unblocked write claim => task={} owner={} completed={}",
        write_outcome.claim.task.task_id,
        write_outcome.claim.lease.owner_id,
        write_outcome.completed
    );
    print_snapshot("after-write-complete", write_worker.queue_snapshot());

    let verify_store = SqliteRuntimeStore::new(into_demo(open_database(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?);
    let restored_read = into_demo(
        verify_store.load_runtime("task-worker-read-shared", "effect-worker-read-shared"),
    )?
    .expect("same-scope read runtime must reload");
    let restored_write = into_demo(verify_store.load_runtime(
        "task-worker-read-write-after",
        "effect-worker-read-write-after",
    ))?
    .expect("same-scope write runtime must reload");
    println!(
        "[demo] restored runtimes => read={:?}/{:?}, write={:?}/{:?}",
        restored_read.worker_state,
        restored_read.effect.status,
        restored_write.worker_state,
        restored_write.effect.status
    );
    println!("[demo] db: {}", temp.db_path().display());
    println!(
        "[demo] write-after output: {}",
        write_after_output.display()
    );
    Ok(())
}

fn build_demo_effect(
    claim: &OrchestratorClaim,
    effect_id: &str,
    trace_id: &str,
    intent_key: &str,
    action: EffectAction,
) -> EffectRecord {
    EffectRecord::new(
        effect_id,
        claim.task.task_id.clone(),
        trace_id,
        intent_key,
        EffectActor::Worker,
        action,
        claim.task.intent.target_scope.clone(),
        EffectTier::Tier1,
        EffectReversibility::Rollbackable,
        ProbeMode::Auto,
    )
}

fn print_snapshot(label: &str, snapshot: OrchestratorSnapshot) {
    println!(
        "[demo] snapshot {label} => queued={}, active={}, completed={}",
        snapshot.queued_tasks.len(),
        snapshot.active_leases.len(),
        snapshot.completed_task_ids.len(),
    );
}

fn sandbox_success_command() -> SandboxCommand {
    if cfg!(windows) {
        SandboxCommand::new("powershell", ["-Command", "Write-Output 'ok'"], 5_000)
    } else {
        SandboxCommand::new("sh", ["-c", "printf '%s' ok"], 5_000)
    }
}

fn sandbox_write_command(output_path: &Path, output_bytes: &[u8]) -> SandboxCommand {
    if cfg!(windows) {
        let bytes_literal = output_bytes
            .iter()
            .map(u8::to_string)
            .collect::<Vec<_>>()
            .join(", ");
        SandboxCommand::new(
            "powershell",
            [
                "-Command",
                &format!(
                    "$bytes = [byte[]]({bytes_literal}); [System.IO.File]::WriteAllBytes('{}', $bytes)",
                    output_path.display()
                ),
            ],
            5_000,
        )
    } else {
        let text = String::from_utf8(output_bytes.to_vec())
            .expect("worker scope read demo bytes must remain utf-8");
        SandboxCommand::new(
            "sh",
            [
                "-c",
                &format!("printf '%s' '{}' > '{}'", text, output_path.display()),
            ],
            5_000,
        )
    }
}

fn into_demo<T, E: std::fmt::Debug>(result: Result<T, E>) -> Result<T, String> {
    result.map_err(|error| format!("{error:?}"))
}

struct DemoArtifacts {
    root: PathBuf,
    db_path: PathBuf,
}

impl DemoArtifacts {
    fn new(workspace: &Path) -> Result<Self, String> {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_err(|error| error.to_string())?
            .as_nanos();
        let root = workspace.join("target").join(format!(
            "worker-loop-scope-read-demo-{}-{unique}",
            process::id()
        ));
        fs::create_dir_all(&root).map_err(|error| error.to_string())?;
        Ok(Self {
            db_path: root.join("worker-loop-scope-read.db"),
            root,
        })
    }

    fn db_path(&self) -> &Path {
        &self.db_path
    }
}

impl Drop for DemoArtifacts {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.root);
    }
}
