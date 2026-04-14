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
    let shared_output = temp.root.join("worker-loop-batch-shared.txt");
    let other_one_output = temp.root.join("worker-loop-batch-other-1.txt");
    let other_two_output = temp.root.join("worker-loop-batch-other-2.txt");
    let shared_scope = format!("scope:{}", shared_output.display());
    let other_one_scope = format!("scope:{}", other_one_output.display());
    let other_two_scope = format!("scope:{}", other_two_output.display());

    let mut blocking_orchestrator =
        into_demo(open_database(temp.db_path(), SqliteOpenOptions::default()))
            .map(SqliteTaskOrchestrator::new)?
            .with_lease_ttl_ms(60_000);
    into_demo(blocking_orchestrator.enqueue(OrchestratorTask::new(
        "task-worker-batch-shared-1",
        ScheduleIntent::write(shared_scope.clone()),
        0,
    )))?;
    into_demo(blocking_orchestrator.enqueue(OrchestratorTask::new(
        "task-worker-batch-shared-2",
        ScheduleIntent::write(shared_scope.clone()),
        1,
    )))?;
    into_demo(blocking_orchestrator.enqueue(OrchestratorTask::new(
        "task-worker-batch-other-1",
        ScheduleIntent::write(other_one_scope.clone()),
        2,
    )))?;
    into_demo(blocking_orchestrator.enqueue(OrchestratorTask::new(
        "task-worker-batch-other-2",
        ScheduleIntent::write(other_two_scope.clone()),
        3,
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

    let mut batch_worker = into_demo(SqliteSingleWorkerLoop::open(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?
    .with_lease_ttl_ms(60_000);
    let outcomes = into_demo(batch_worker.claim_and_drive_until_empty(
        "worker-b",
        1,
        PreflightDecision::Permit,
        |claim| {
            let (effect_id, trace_id, intent_key, output_path, output_bytes) =
                match claim.task.task_id.as_str() {
                    "task-worker-batch-other-1" => (
                        "effect-worker-batch-other-1",
                        "trace-worker-batch-other-1",
                        "intent-worker-batch-other-1",
                        &other_one_output,
                        b"safeclaw batch other one\n".as_slice(),
                    ),
                    "task-worker-batch-other-2" => (
                        "effect-worker-batch-other-2",
                        "trace-worker-batch-other-2",
                        "intent-worker-batch-other-2",
                        &other_two_output,
                        b"safeclaw batch other two\n".as_slice(),
                    ),
                    other => panic!("unexpected task id: {other}"),
                };
            Ok((
                InMemoryTaskRuntime::new(build_demo_effect(claim, effect_id, trace_id, intent_key)),
                sandbox_write_command(output_path, output_bytes),
            ))
        },
    ))?;

    println!("[demo] drained outcomes => {}", outcomes.len());
    for outcome in &outcomes {
        println!(
            "[demo] drained task={} owner={} completed={} worker={:?} effect={:?}",
            outcome.claim.task.task_id,
            outcome.claim.lease.owner_id,
            outcome.completed,
            outcome.final_summary.worker_state,
            outcome.final_summary.effect_status
        );
    }
    print_snapshot("after-batch-drain", batch_worker.queue_snapshot());

    let verify_store = SqliteRuntimeStore::new(into_demo(open_database(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?);
    let restored_one = into_demo(
        verify_store.load_runtime("task-worker-batch-other-1", "effect-worker-batch-other-1"),
    )?
    .expect("first drained runtime must reload");
    let restored_two = into_demo(
        verify_store.load_runtime("task-worker-batch-other-2", "effect-worker-batch-other-2"),
    )?
    .expect("second drained runtime must reload");
    println!(
        "[demo] restored first-pass runtimes => one={:?}/{:?}, two={:?}/{:?}",
        restored_one.worker_state,
        restored_one.effect.status,
        restored_two.worker_state,
        restored_two.effect.status
    );
    println!(
        "[demo] remaining queued task => {}",
        batch_worker.queue_snapshot().queued_tasks[0].task_id
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

    let mut release_worker = into_demo(SqliteSingleWorkerLoop::open(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?
    .with_lease_ttl_ms(60_000);
    let release_outcomes = into_demo(release_worker.claim_and_drive_until_empty(
        "worker-c",
        2,
        PreflightDecision::Permit,
        |claim| {
            assert_eq!(claim.task.task_id, "task-worker-batch-shared-2");
            Ok((
                InMemoryTaskRuntime::new(build_demo_effect(
                    claim,
                    "effect-worker-batch-shared-2",
                    "trace-worker-batch-shared-2",
                    "intent-worker-batch-shared-2",
                )),
                sandbox_write_command(&shared_output, b"safeclaw shared after release\n"),
            ))
        },
    ))?;

    println!("[demo] release outcomes => {}", release_outcomes.len());
    for outcome in &release_outcomes {
        println!(
            "[demo] released task={} owner={} completed={} worker={:?} effect={:?}",
            outcome.claim.task.task_id,
            outcome.claim.lease.owner_id,
            outcome.completed,
            outcome.final_summary.worker_state,
            outcome.final_summary.effect_status
        );
    }
    print_snapshot("after-release-drain", release_worker.queue_snapshot());

    let verify_store = SqliteRuntimeStore::new(into_demo(open_database(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?);
    let restored_shared = into_demo(
        verify_store.load_runtime("task-worker-batch-shared-2", "effect-worker-batch-shared-2"),
    )?
    .expect("released shared runtime must reload");
    println!(
        "[demo] restored released runtime => shared={:?}/{:?}",
        restored_shared.worker_state, restored_shared.effect.status
    );
    println!("[demo] shared output exists => {}", shared_output.exists());
    println!("[demo] db: {}", temp.db_path().display());
    println!("[demo] shared output: {}", shared_output.display());
    println!("[demo] other-1 output: {}", other_one_output.display());
    println!("[demo] other-2 output: {}", other_two_output.display());
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
            .expect("worker batch release demo bytes must remain utf-8");
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
            "worker-loop-batch-release-demo-{}-{unique}",
            process::id()
        ));
        fs::create_dir_all(&root).map_err(|error| error.to_string())?;
        Ok(Self {
            db_path: root.join("worker-loop-batch-release.db"),
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
