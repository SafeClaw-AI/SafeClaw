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
    ExecutionDisposition, InMemoryTaskRuntime, OrchestratorClaim, OrchestratorSnapshot,
    OrchestratorTask, PreflightDecision, ScheduleIntent, TaskOrchestrator,
};
use safeclaw_sqlite::{
    open_database, FileSystemProbeAdapter, LocalSandboxExecutor, RuntimeDiagnosticSnapshot,
    SandboxCommand, SqliteOpenOptions, SqliteRuntimeStore, SqliteTaskOrchestrator,
};

fn main() -> Result<(), String> {
    let workspace = into_demo(env::current_dir())?;
    let temp = DemoArtifacts::new(&workspace)?;
    let output_bytes = b"safeclaw full lifecycle demo\n";

    let orchestrator_connection =
        into_demo(open_database(temp.db_path(), SqliteOpenOptions::default()))?;
    let mut orchestrator =
        SqliteTaskOrchestrator::new(orchestrator_connection).with_lease_ttl_ms(60_000);
    into_demo(orchestrator.enqueue(OrchestratorTask::new(
        "task-demo-1",
        ScheduleIntent::write(format!("scope:{}", temp.output_path.display())),
        0,
    )))?;
    println!("[demo] enqueued task: task-demo-1");

    let claim = into_demo(orchestrator.claim_next("worker-demo", 1))?
        .expect("queued task must be claimable");
    println!(
        "[demo] claimed task={} lease={} fence={}",
        claim.task.task_id, claim.lease.lease_id, claim.lease.fencing_token
    );
    print_snapshot("after-claim", orchestrator.queue_snapshot());

    let mut runtime = InMemoryTaskRuntime::new(demo_effect(&claim));
    into_demo(runtime.begin_execution(PreflightDecision::Permit))?;
    println!(
        "[demo] runtime entered => worker={:?}, effect={:?}",
        runtime.worker_state, runtime.effect.status
    );

    let executor = LocalSandboxExecutor::new();
    let command = sandbox_write_command(&temp.output_path, output_bytes)?;
    let execution = into_demo(executor.run(&command))?;
    println!("[demo] sandbox stdout: {}", execution.stdout.trim());
    println!("[demo] sandbox stderr: {}", execution.stderr.trim());
    println!("[demo] sandbox result: {:?}", execution.runtime_directive());

    into_demo(runtime.continue_execution(ExecutionDisposition::Crash))?;
    println!(
        "[demo] runtime after crash => worker={:?}, effect={:?}",
        runtime.worker_state, runtime.effect.status
    );

    let connection = into_demo(open_database(temp.db_path(), SqliteOpenOptions::default()))?;
    let mut store = SqliteRuntimeStore::new(connection);
    into_demo(store.persist_runtime(&runtime, "demo-state-1", "full-lifecycle-demo"))?;
    let uncertain_snapshot = store
        .diagnostic_snapshot(&claim.task.task_id, "effect-demo-1")
        .map_err(|error| format!("{error:?}"))?
        .expect("uncertain runtime diagnostic snapshot must exist");
    print_diagnostic("uncertain", &uncertain_snapshot);
    drop(store);
    println!("[demo] persisted uncertain runtime");

    drop(orchestrator);

    let reopened = into_demo(open_database(temp.db_path(), SqliteOpenOptions::default()))?;
    let store = SqliteRuntimeStore::new(reopened);
    let mut restored = into_demo(store.load_runtime(&claim.task.task_id, "effect-demo-1"))?
        .expect("persisted runtime must reload");
    println!(
        "[demo] restored runtime => worker={:?}, effect={:?}",
        restored.worker_state, restored.effect.status
    );

    let mut probe = FileSystemProbeAdapter::new();
    probe.register_expected_blake3(
        restored.effect.effect_id.clone(),
        blake3::hash(output_bytes).to_hex().to_string(),
    );
    let summary = into_demo(restored.run_probe_with(&probe))?;
    println!(
        "[demo] probe summary => worker={:?}, effect={:?}, attempts={}",
        summary.worker_state, summary.effect_status, summary.attempt_count
    );

    let final_connection = into_demo(open_database(temp.db_path(), SqliteOpenOptions::default()))?;
    let mut final_store = SqliteRuntimeStore::new(final_connection);
    into_demo(final_store.persist_runtime(&restored, "demo-state-2", "full-lifecycle-demo"))?;
    let reconciled_snapshot = final_store
        .diagnostic_snapshot(&claim.task.task_id, "effect-demo-1")
        .map_err(|error| format!("{error:?}"))?
        .expect("reconciled runtime diagnostic snapshot must exist");
    print_diagnostic("reconciled", &reconciled_snapshot);
    println!("[demo] persisted reconciled runtime");

    let completion_connection =
        into_demo(open_database(temp.db_path(), SqliteOpenOptions::default()))?;
    let mut completion_orchestrator = SqliteTaskOrchestrator::new(completion_connection);
    into_demo(completion_orchestrator.complete(
        &claim.task.task_id,
        &claim.lease.lease_id,
        &claim.lease.owner_id,
    ))?;
    print_snapshot("after-complete", completion_orchestrator.queue_snapshot());

    println!("[demo] db: {}", temp.db_path().display());
    println!("[demo] output: {}", temp.output_path.display());
    Ok(())
}

fn demo_effect(claim: &OrchestratorClaim) -> EffectRecord {
    EffectRecord::new(
        "effect-demo-1",
        claim.task.task_id.clone(),
        "trace-demo-1",
        "intent-demo-1",
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

fn print_diagnostic(label: &str, snapshot: &RuntimeDiagnosticSnapshot) {
    println!(
        "[demo] diagnostic {label} => worker={:?} effect={:?} attempts={} events={} transitions={} disposition={:?}",
        snapshot.governance.worker_state,
        snapshot.governance.effect_status,
        snapshot.attempts.len(),
        snapshot.state_events.len(),
        snapshot.effect_transitions.len(),
        snapshot.governance.disposition,
    );
}

fn sandbox_write_command(output_path: &Path, output_bytes: &[u8]) -> Result<SandboxCommand, String> {
    let text = String::from_utf8(output_bytes.to_vec()).map_err(|error| error.to_string())?;
    let command = if cfg!(windows) {
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
        SandboxCommand::new(
            "sh",
            ["-c", &format!("printf '%s' '{}' > '{}'", text, output_path.display())],
            5_000,
        )
    };
    Ok(command)
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
        let root = workspace
            .join("target")
            .join(format!("full-lifecycle-demo-{}-{unique}", process::id()));
        fs::create_dir_all(&root).map_err(|error| error.to_string())?;
        Ok(Self {
            output_path: root.join("demo-output.txt"),
            db_path: root.join("demo.db"),
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
