use std::{
    env, fs,
    path::{Path, PathBuf},
    process,
    time::{SystemTime, UNIX_EPOCH},
};

use safeclaw_core::{
    effect_ledger::{
        EffectAction, EffectActor, EffectRecord, EffectReversibility, EffectTier,
        ProbeMode,
    },
    InMemoryTaskRuntime, OrchestratorClaim, OrchestratorSnapshot, OrchestratorTask,
    PreflightDecision, ScheduleIntent, TaskOrchestrator,
};
use safeclaw_sqlite::{
    open_database, SandboxCommand, SqliteOpenOptions, SqliteRuntimeStore,
    SqliteSingleWorkerLoop, SqliteTaskOrchestrator,
};

fn main() -> Result<(), String> {
    let workspace = into_demo(env::current_dir())?;
    let temp = DemoArtifacts::new(&workspace)?;
    let shared_scope = format!("scope:{}", temp.root.join("shared-write-serial-under-reads.txt").display());
    let second_write_output = temp.root.join("worker-loop-second-write-under-reads.txt");

    let mut blocking_orchestrator = into_demo(open_database(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))
    .map(SqliteTaskOrchestrator::new)?
    .with_lease_ttl_ms(60_000);

    into_demo(blocking_orchestrator.enqueue(OrchestratorTask::new(
        "task-worker-shared-read-active-1",
        ScheduleIntent::read(shared_scope.clone()),
        0,
    )))?;
    into_demo(blocking_orchestrator.enqueue(OrchestratorTask::new(
        "task-worker-shared-read-active-2",
        ScheduleIntent::read(shared_scope.clone()),
        1,
    )))?;
    into_demo(blocking_orchestrator.enqueue(OrchestratorTask::new(
        "task-worker-shared-write-1",
        ScheduleIntent::write(shared_scope.clone()),
        2,
    )))?;
    into_demo(blocking_orchestrator.enqueue(OrchestratorTask::new(
        "task-worker-shared-write-2",
        ScheduleIntent::write(shared_scope.clone()),
        3,
    )))?;
    print_snapshot("after-enqueue", blocking_orchestrator.queue_snapshot());

    let first_read = into_demo(blocking_orchestrator.claim_next("worker-a", 0))?
        .expect("first shared read must be claimable");
    println!(
        "[demo] first read claim => task={} lease={} fence={} owner={}",
        first_read.task.task_id,
        first_read.lease.lease_id,
        first_read.lease.fencing_token,
        first_read.lease.owner_id
    );
    assert!(!first_read.task.intent.requires_write);

    let second_read = into_demo(blocking_orchestrator.claim_next("worker-b", 1))?
        .expect("second shared read must remain claimable");
    println!(
        "[demo] second read claim => task={} lease={} fence={} owner={}",
        second_read.task.task_id,
        second_read.lease.lease_id,
        second_read.lease.fencing_token,
        second_read.lease.owner_id
    );
    assert!(!second_read.task.intent.requires_write);

    let first_write = into_demo(blocking_orchestrator.claim_next("worker-c", 2))?
        .expect("first same-scope write must remain claimable under active reads");
    println!(
        "[demo] first write claim => task={} lease={} fence={} owner={}",
        first_write.task.task_id,
        first_write.lease.lease_id,
        first_write.lease.fencing_token,
        first_write.lease.owner_id
    );
    assert!(first_write.task.intent.requires_write);

    let blocked_orchestrator = into_demo(open_database(temp.db_path(), SqliteOpenOptions::default()))
        .map(SqliteTaskOrchestrator::new)?
        .with_lease_ttl_ms(60_000);
    let blocked_store = SqliteRuntimeStore::new(into_demo(open_database(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?);
    let mut blocked_worker = SqliteSingleWorkerLoop::new(blocked_orchestrator, blocked_store);

    let blocked = into_demo(blocked_worker.claim_and_drive_once(
        "worker-d",
        3,
        PreflightDecision::Permit,
        |_| unreachable!(),
    ))?;
    println!("[demo] second write blocked while first write active => {}", blocked.is_none());
    assert!(blocked.is_none());

    into_demo(blocking_orchestrator.complete(
        &first_write.task.task_id,
        &first_write.lease.lease_id,
        &first_write.lease.owner_id,
    ))?;
    print_snapshot("after-first-write-release", blocking_orchestrator.queue_snapshot());

    let release_orchestrator = into_demo(open_database(temp.db_path(), SqliteOpenOptions::default()))
        .map(SqliteTaskOrchestrator::new)?
        .with_lease_ttl_ms(60_000);
    let release_store = SqliteRuntimeStore::new(into_demo(open_database(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?);
    let mut release_worker = SqliteSingleWorkerLoop::new(release_orchestrator, release_store);

    let released = into_demo(release_worker.claim_and_drive_once(
        "worker-d",
        4,
        PreflightDecision::Permit,
        |claim| {
            println!("[demo] second write claim => {}", claim.task.task_id);
            Ok((
                InMemoryTaskRuntime::new(build_demo_effect(
                    claim,
                    "effect-worker-shared-write-2",
                    "trace-worker-shared-write-2",
                    "intent-worker-shared-write-2",
                )),
                sandbox_write_command(&second_write_output, b"safeclaw second write under reads\n"),
            ))
        },
    ))?
    .expect("second same-scope write must unblock after first write release");

    println!(
        "[demo] second write outcome => worker={:?}, effect={:?}, completed={}",
        released.final_summary.worker_state,
        released.final_summary.effect_status,
        released.completed
    );
    print_snapshot("after-second-write-complete", release_worker.queue_snapshot());
    assert_eq!(fs::read(&second_write_output).unwrap(), b"safeclaw second write under reads\n");
    assert_eq!(release_worker.queue_snapshot().active_leases.len(), 2);

    let verify_store = SqliteRuntimeStore::new(into_demo(open_database(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?);
    let restored = into_demo(verify_store.load_runtime(
        "task-worker-shared-write-2",
        "effect-worker-shared-write-2",
    ))?
    .expect("second write runtime must reload");
    println!(
        "[demo] restored runtime => worker={:?}, effect={:?}, attempts={}",
        restored.worker_state,
        restored.effect.status,
        restored.attempts.len()
    );
    println!("[demo] db: {}", temp.db_path().display());
    println!("[demo] second write output: {}", second_write_output.display());
    Ok(())
}

fn build_demo_effect(
    claim: &OrchestratorClaim,
    effect_id: &str,
    trace_id: &str,
    intent_key: &str,
) -> EffectRecord {
    EffectRecord::new(
        effect_id,
        claim.task.task_id.clone(),
        trace_id,
        intent_key,
        EffectActor::Worker,
        EffectAction::FileWrite,
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
            .expect("worker loop write under reads demo bytes must remain utf-8");
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
        let root = workspace
            .join("target")
            .join(format!("worker-loop-write-serial-under-reads-demo-{}-{unique}", process::id()));
        fs::create_dir_all(&root).map_err(|error| error.to_string())?;
        Ok(Self {
            db_path: root.join("worker-loop-write-serial-under-reads.db"),
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
