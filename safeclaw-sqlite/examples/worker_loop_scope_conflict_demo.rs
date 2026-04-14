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
    let shared_output = temp.root.join("worker-loop-shared-output.txt");
    let other_output = temp.root.join("worker-loop-other-output.txt");
    let shared_scope = format!("scope:{}", shared_output.display());
    let other_scope = format!("scope:{}", other_output.display());

    let mut blocking_orchestrator =
        into_demo(open_database(temp.db_path(), SqliteOpenOptions::default()))
            .map(SqliteTaskOrchestrator::new)?
            .with_lease_ttl_ms(60_000);
    into_demo(blocking_orchestrator.enqueue(OrchestratorTask::new(
        "task-worker-scope-shared-1",
        ScheduleIntent::write(shared_scope.clone()),
        0,
    )))?;
    into_demo(blocking_orchestrator.enqueue(OrchestratorTask::new(
        "task-worker-scope-shared-2",
        ScheduleIntent::write(shared_scope.clone()),
        1,
    )))?;
    into_demo(blocking_orchestrator.enqueue(OrchestratorTask::new(
        "task-worker-scope-other",
        ScheduleIntent::write(other_scope.clone()),
        2,
    )))?;
    print_snapshot("after-enqueue", blocking_orchestrator.queue_snapshot());

    let blocking_claim = into_demo(blocking_orchestrator.claim_next("worker-a", 0))?
        .expect("first shared task must be claimable");
    println!(
        "[demo] blocking claim => task={} lease={} fence={} owner={}",
        blocking_claim.task.task_id,
        blocking_claim.lease.lease_id,
        blocking_claim.lease.fencing_token,
        blocking_claim.lease.owner_id
    );
    print_snapshot(
        "after-blocking-claim",
        blocking_orchestrator.queue_snapshot(),
    );

    let mut other_worker = into_demo(SqliteSingleWorkerLoop::open(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?
    .with_lease_ttl_ms(60_000);
    let other_outcome = into_demo(other_worker.claim_and_drive_once(
        "worker-b",
        1,
        PreflightDecision::Permit,
        |claim| {
            Ok((
                InMemoryTaskRuntime::new(build_demo_effect(
                    claim,
                    "effect-worker-scope-other",
                    "trace-worker-scope-other",
                    "intent-worker-scope-other",
                )),
                sandbox_write_command(&other_output, b"safeclaw non-conflicting task\n"),
            ))
        },
    ))?
    .expect("non-conflicting task must remain claimable");
    println!(
        "[demo] skipped conflicting scope => claimed task={} owner={} completed={}",
        other_outcome.claim.task.task_id,
        other_outcome.claim.lease.owner_id,
        other_outcome.completed
    );
    print_snapshot("after-other-task-complete", other_worker.queue_snapshot());

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
        "[demo] only conflicting task remains => {}",
        blocked.is_none()
    );

    into_demo(blocking_orchestrator.complete(
        &blocking_claim.task.task_id,
        &blocking_claim.lease.lease_id,
        &blocking_claim.lease.owner_id,
    ))?;
    print_snapshot(
        "after-release-blocking-claim",
        blocking_orchestrator.queue_snapshot(),
    );

    let mut unblocked_worker = into_demo(SqliteSingleWorkerLoop::open(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?
    .with_lease_ttl_ms(60_000);
    let unblocked_outcome = into_demo(unblocked_worker.claim_and_drive_once(
        "worker-c",
        3,
        PreflightDecision::Permit,
        |claim| {
            Ok((
                InMemoryTaskRuntime::new(build_demo_effect(
                    claim,
                    "effect-worker-scope-shared-2",
                    "trace-worker-scope-shared-2",
                    "intent-worker-scope-shared-2",
                )),
                sandbox_write_command(&shared_output, b"safeclaw shared task after release\n"),
            ))
        },
    ))?
    .expect("shared task must unblock after lease release");
    println!(
        "[demo] unblocked claim => task={} owner={} completed={}",
        unblocked_outcome.claim.task.task_id,
        unblocked_outcome.claim.lease.owner_id,
        unblocked_outcome.completed
    );
    print_snapshot(
        "after-shared-task-complete",
        unblocked_worker.queue_snapshot(),
    );

    let verify_store = SqliteRuntimeStore::new(into_demo(open_database(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?);
    let restored_other = into_demo(
        verify_store.load_runtime("task-worker-scope-other", "effect-worker-scope-other"),
    )?
    .expect("other runtime must reload");
    let restored_shared = into_demo(
        verify_store.load_runtime("task-worker-scope-shared-2", "effect-worker-scope-shared-2"),
    )?
    .expect("shared runtime must reload");
    println!(
        "[demo] restored runtimes => other={:?}/{:?}, shared={:?}/{:?}",
        restored_other.worker_state,
        restored_other.effect.status,
        restored_shared.worker_state,
        restored_shared.effect.status
    );
    println!("[demo] db: {}", temp.db_path().display());
    println!("[demo] shared output: {}", shared_output.display());
    println!("[demo] other output: {}", other_output.display());
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
            .expect("worker scope conflict demo bytes must remain utf-8");
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
            "worker-loop-scope-conflict-demo-{}-{unique}",
            process::id()
        ));
        fs::create_dir_all(&root).map_err(|error| error.to_string())?;
        Ok(Self {
            db_path: root.join("worker-loop-scope-conflict.db"),
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
