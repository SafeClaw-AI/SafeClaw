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
    scheduler::TaskOrchestrator,
    worker_lifecycle::WorkerState,
    InMemoryTaskRuntime, OrchestratorClaim, OrchestratorSnapshot, OrchestratorTask,
    PreflightDecision, ScheduleIntent,
};
use safeclaw_sqlite::{
    open_database, LocalSandboxExecutor, SandboxCommand, SqliteOpenOptions, SqliteRuntimeStore,
    SqliteSingleWorkerLoop, SqliteTaskOrchestrator,
};

fn main() -> Result<(), String> {
    let workspace = into_demo(env::current_dir())?;
    let temp = DemoArtifacts::new(&workspace)?;
    let output_bytes = b"safeclaw persisted probe demo\n";

    let mut setup_orchestrator = SqliteTaskOrchestrator::new(into_demo(open_database(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?)
    .with_lease_ttl_ms(25);
    into_demo(setup_orchestrator.enqueue(OrchestratorTask::new(
        "task-worker-loop-persisted-probe-demo",
        ScheduleIntent::write(format!("scope:{}", temp.output_path.display())),
        0,
    )))?;
    print_snapshot("after-enqueue", setup_orchestrator.queue_snapshot());

    let claim = into_demo(setup_orchestrator.claim_next("worker-a", 0))?
        .expect("queued task must be claimable");
    println!(
        "[demo] initial claim => task={} lease={} fence={}",
        claim.task.task_id, claim.lease.lease_id, claim.lease.fencing_token
    );

    let mut runtime = InMemoryTaskRuntime::new(demo_effect(&claim));
    into_demo(runtime.begin_execution(PreflightDecision::Permit))?;
    let executor = LocalSandboxExecutor::new();
    let (report, execution_summary) = into_demo(executor.run_and_apply(
        &mut runtime,
        &sandbox_write_then_timeout_command(&temp.output_path, output_bytes),
    ))?;
    assert!(report.timed_out);
    assert_eq!(execution_summary.worker_state, WorkerState::Uncertain);
    println!(
        "[demo] crash phase => worker={:?}, effect={:?}, timed_out={}",
        execution_summary.worker_state, execution_summary.effect_status, report.timed_out
    );

    let mut setup_store = SqliteRuntimeStore::new(into_demo(open_database(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?);
    into_demo(setup_store.persist_runtime(
        &runtime,
        format!("worker-loop:{}:post-exec", claim.lease.lease_id),
        "demo",
    ))?;

    let mut probe_worker = into_demo(SqliteSingleWorkerLoop::open(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?
    .with_lease_ttl_ms(25);
    probe_worker
        .filesystem_probe_mut()
        .register_expected_blake3(
            "effect-worker-loop-persisted-probe-demo",
            blake3::hash(output_bytes).to_hex().to_string(),
        );

    let blocked = into_demo(probe_worker.claim_and_probe_persisted_once(
        "worker-b",
        10,
        "effect-worker-loop-persisted-probe-demo",
    ))?;
    println!("[demo] reclaim before expiry => {}", blocked.is_none());

    let recovered = into_demo(probe_worker.claim_and_probe_persisted_once(
        "worker-b",
        26,
        "effect-worker-loop-persisted-probe-demo",
    ))?
    .expect("expired uncertain runtime must be claimable for probe");
    println!(
        "[demo] probe recovery => {}",
        recovered.render_recovery_status_line()
    );
    print_snapshot("after-probe-complete", probe_worker.queue_snapshot());

    let verify_store = SqliteRuntimeStore::new(into_demo(open_database(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?);
    let restored = into_demo(verify_store.load_runtime(
        "task-worker-loop-persisted-probe-demo",
        "effect-worker-loop-persisted-probe-demo",
    ))?
    .expect("persisted runtime must reload");
    println!(
        "[demo] restored runtime => worker={:?}, effect={:?}, attempts={}",
        restored.worker_state,
        restored.effect.status,
        restored.attempts.len()
    );
    println!("[demo] db: {}", temp.db_path().display());
    println!("[demo] output: {}", temp.output_path.display());
    Ok(())
}

fn demo_effect(claim: &OrchestratorClaim) -> EffectRecord {
    EffectRecord::new(
        "effect-worker-loop-persisted-probe-demo",
        claim.task.task_id.clone(),
        "trace-worker-loop-persisted-probe-demo",
        "intent-worker-loop-persisted-probe-demo",
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

fn sandbox_write_then_timeout_command(output_path: &Path, output_bytes: &[u8]) -> SandboxCommand {
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
                    "$bytes = [byte[]]({bytes_literal}); [System.IO.File]::WriteAllBytes('{}', $bytes); Start-Sleep -Milliseconds 1000",
                    output_path.display()
                ),
            ],
            500,
        )
    } else {
        let text = String::from_utf8(output_bytes.to_vec())
            .expect("persisted probe demo bytes must remain utf-8");
        SandboxCommand::new(
            "sh",
            [
                "-c",
                &format!(
                    "printf '%s' '{}' > '{}'; sleep 1",
                    text,
                    output_path.display()
                ),
            ],
            500,
        )
    }
}

fn into_demo<T, E: std::fmt::Debug>(result: Result<T, E>) -> Result<T, String> {
    result.map_err(|error| format!("{error:?}"))
}

struct DemoArtifacts {
    root: PathBuf,
    output_path: PathBuf,
    db_path: PathBuf,
}

impl DemoArtifacts {
    fn new(workspace: &Path) -> Result<Self, String> {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_err(|error| error.to_string())?
            .as_nanos();
        let root = workspace.join("target").join(format!(
            "worker-loop-persisted-probe-demo-{}-{unique}",
            process::id()
        ));
        fs::create_dir_all(&root).map_err(|error| error.to_string())?;
        Ok(Self {
            output_path: root.join("worker-loop-persisted-probe-output.txt"),
            db_path: root.join("worker-loop-persisted-probe.db"),
            root,
        })
    }

    fn db_path(&self) -> &Path {
        &self.db_path
    }
}

impl Drop for DemoArtifacts {
    fn drop(&mut self) {
        let _ = fs::remove_file(&self.output_path);
        let _ = fs::remove_file(&self.db_path);
        let _ = fs::remove_file(PathBuf::from(format!("{}-wal", self.db_path.display())));
        let _ = fs::remove_file(PathBuf::from(format!("{}-shm", self.db_path.display())));
        let _ = fs::remove_dir(&self.root);
    }
}
