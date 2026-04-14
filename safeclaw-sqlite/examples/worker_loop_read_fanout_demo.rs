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
    let shared_scope = format!("scope:{}", temp.root.join("shared-read.txt").display());

    let mut blocking_orchestrator =
        into_demo(open_database(temp.db_path(), SqliteOpenOptions::default()))
            .map(SqliteTaskOrchestrator::new)?
            .with_lease_ttl_ms(60_000);

    into_demo(blocking_orchestrator.enqueue(OrchestratorTask::new(
        "task-worker-shared-read-1",
        ScheduleIntent::read(shared_scope.clone()),
        0,
    )))?;
    into_demo(blocking_orchestrator.enqueue(OrchestratorTask::new(
        "task-worker-shared-read-2",
        ScheduleIntent::read(shared_scope.clone()),
        1,
    )))?;
    print_snapshot("after-enqueue", blocking_orchestrator.queue_snapshot());

    let blocking_claim = into_demo(blocking_orchestrator.claim_next("worker-a", 0))?
        .expect("first shared read must be claimable");
    println!(
        "[demo] first read claim => task={} lease={} fence={} owner={}",
        blocking_claim.task.task_id,
        blocking_claim.lease.lease_id,
        blocking_claim.lease.fencing_token,
        blocking_claim.lease.owner_id
    );

    let read_orchestrator = into_demo(open_database(temp.db_path(), SqliteOpenOptions::default()))
        .map(SqliteTaskOrchestrator::new)?
        .with_lease_ttl_ms(60_000);
    let read_store = SqliteRuntimeStore::new(into_demo(open_database(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?);
    let mut read_worker = SqliteSingleWorkerLoop::new(read_orchestrator, read_store);

    let read_outcome = into_demo(read_worker.claim_and_drive_once(
        "worker-b",
        1,
        PreflightDecision::Permit,
        |claim| {
            println!("[demo] second read claim => {}", claim.task.task_id);
            Ok((
                InMemoryTaskRuntime::new(build_demo_effect(
                    claim,
                    "effect-worker-shared-read-2",
                    "trace-worker-shared-read-2",
                    "intent-worker-shared-read-2",
                )),
                sandbox_success_command(),
            ))
        },
    ))?
    .expect("second shared read must remain claimable");

    println!(
        "[demo] second read outcome => worker={:?}, effect={:?}, completed={}",
        read_outcome.final_summary.worker_state,
        read_outcome.final_summary.effect_status,
        read_outcome.completed
    );
    print_snapshot("after-second-read-complete", read_worker.queue_snapshot());
    assert_eq!(read_worker.queue_snapshot().active_leases.len(), 1);
    assert_eq!(
        read_worker.queue_snapshot().active_leases[0].task_id,
        "task-worker-shared-read-1"
    );

    let verify_store = SqliteRuntimeStore::new(into_demo(open_database(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?);
    let restored = into_demo(
        verify_store.load_runtime("task-worker-shared-read-2", "effect-worker-shared-read-2"),
    )?
    .expect("second shared read runtime must reload");
    println!(
        "[demo] restored runtime => worker={:?}, effect={:?}, attempts={}",
        restored.worker_state,
        restored.effect.status,
        restored.attempts.len()
    );
    println!("[demo] db: {}", temp.db_path().display());
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
        EffectAction::NetworkRequest,
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
            "worker-loop-read-fanout-demo-{}-{unique}",
            process::id()
        ));
        fs::create_dir_all(&root).map_err(|error| error.to_string())?;
        Ok(Self {
            db_path: root.join("worker-loop-read-fanout.db"),
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
