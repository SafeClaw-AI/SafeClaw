use std::{
    env, fs,
    path::{Path, PathBuf},
    process,
    time::{SystemTime, UNIX_EPOCH},
};

use safeclaw_core::{
    effect_ledger::{
        EffectAction, EffectActor, EffectRecord, EffectReversibility, EffectStatus, EffectTier,
        ProbeMode,
    },
    worker_lifecycle::WorkerState,
    InMemoryTaskRuntime, OrchestratorClaim, OrchestratorSnapshot, OrchestratorTask,
    PreflightDecision, ScheduleIntent,
};
use safeclaw_sqlite::{
    open_database, SandboxCommand, SqliteOpenOptions, SqliteRuntimeStore,
    SqliteSingleWorkerLoop,
};

fn main() -> Result<(), String> {
    let workspace = into_demo(env::current_dir())?;
    let temp = DemoArtifacts::new(&workspace)?;
    let output_bytes = b"safeclaw worker retry pre-exec demo\n";

    let mut first_worker = into_demo(SqliteSingleWorkerLoop::open(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?
    .with_lease_ttl_ms(25);
    into_demo(first_worker.enqueue_task(OrchestratorTask::new(
        "task-worker-loop-retry-pre-exec-demo",
        ScheduleIntent::write(format!("scope:{}", temp.output_path.display())),
        0,
    )))?;
    print_snapshot("after-enqueue", first_worker.queue_snapshot());

    let failed = into_demo(first_worker.claim_and_drive_once(
        "worker-a",
        0,
        PreflightDecision::Permit,
        |claim| Ok((InMemoryTaskRuntime::new(demo_effect(claim)), sandbox_fail_command())),
    ))?
    .expect("queued task must be claimable");
    println!(
        "[demo] first attempt => worker={:?}, effect={:?}, completed={}",
        failed.final_summary.worker_state,
        failed.final_summary.effect_status,
        failed.completed
    );
    print_snapshot("after-failed-attempt", first_worker.queue_snapshot());

    let mut retry_spawn_worker = into_demo(SqliteSingleWorkerLoop::open(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?
    .with_lease_ttl_ms(25);
    let retry_error = retry_spawn_worker
        .claim_and_retry_failed_once(
            "worker-b",
            26,
            "effect-worker-loop-retry-pre-exec-demo",
            PreflightDecision::Permit,
            |claim, runtime| {
                println!(
                    "[demo] retry pre-exec claim => task={} lease={} fence={} state={:?}",
                    claim.task.task_id,
                    claim.lease.lease_id,
                    claim.lease.fencing_token,
                    runtime.worker_state
                );
                Ok(sandbox_missing_program_command())
            },
        )
        .expect_err("missing program must surface sandbox error");
    println!("[demo] retry spawn error => {retry_error:?}");
    print_snapshot("after-retry-spawn-failure", retry_spawn_worker.queue_snapshot());

    let verify_store = SqliteRuntimeStore::new(into_demo(open_database(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?);
    let restored_after_spawn_fail = into_demo(verify_store.load_runtime(
        "task-worker-loop-retry-pre-exec-demo",
        "effect-worker-loop-retry-pre-exec-demo",
    ))?
    .expect("retry pre-exec runtime must persist before sandbox spawn");
    assert_eq!(restored_after_spawn_fail.worker_state, WorkerState::Executing);
    assert_eq!(restored_after_spawn_fail.effect.status, EffectStatus::Prepared);
    println!(
        "[demo] restored after spawn failure => worker={:?}, effect={:?}, attempts={}",
        restored_after_spawn_fail.worker_state,
        restored_after_spawn_fail.effect.status,
        restored_after_spawn_fail.attempts.len()
    );

    let mut resume_worker = into_demo(SqliteSingleWorkerLoop::open(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?
    .with_lease_ttl_ms(25);
    let resumed = into_demo(resume_worker.claim_and_resume_persisted_once(
        "worker-c",
        52,
        "effect-worker-loop-retry-pre-exec-demo",
        |claim, runtime| {
            println!(
                "[demo] resume after spawn failure => task={} lease={} fence={} state={:?}",
                claim.task.task_id,
                claim.lease.lease_id,
                claim.lease.fencing_token,
                runtime.worker_state
            );
            Ok(sandbox_write_command(&temp.output_path, output_bytes))
        },
    ))?
    .expect("spawn-failed runtime must be resumable after expiry");

    assert!(resumed.completed);
    assert_eq!(fs::read(&temp.output_path).map_err(|error| error.to_string())?, output_bytes);
    println!(
        "[demo] resume completion => worker={:?}, effect={:?}, completed={}",
        resumed.final_summary.worker_state,
        resumed.final_summary.effect_status,
        resumed.completed
    );
    print_snapshot("after-resume-complete", resume_worker.queue_snapshot());

    let verify_store = SqliteRuntimeStore::new(into_demo(open_database(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?);
    let restored = into_demo(verify_store.load_runtime(
        "task-worker-loop-retry-pre-exec-demo",
        "effect-worker-loop-retry-pre-exec-demo",
    ))?
    .expect("persisted retry runtime must reload");
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
        "effect-worker-loop-retry-pre-exec-demo",
        claim.task.task_id.clone(),
        "trace-worker-loop-retry-pre-exec-demo",
        "intent-worker-loop-retry-pre-exec-demo",
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

fn sandbox_fail_command() -> SandboxCommand {
    if cfg!(windows) {
        SandboxCommand::new("powershell", ["-Command", "Write-Error 'boom'; exit 7"], 5_000)
    } else {
        SandboxCommand::new("sh", ["-c", "echo boom 1>&2; exit 7"], 5_000)
    }
}

fn sandbox_missing_program_command() -> SandboxCommand {
    SandboxCommand::new(
        "safeclaw-missing-program-for-spawn-test",
        std::iter::empty::<&str>(),
        5_000,
    )
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
            .expect("worker retry pre-exec demo bytes must remain utf-8");
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
            "worker-loop-retry-pre-exec-demo-{}-{unique}",
            process::id()
        ));
        fs::create_dir_all(&root).map_err(|error| error.to_string())?;
        Ok(Self {
            output_path: root.join("worker-loop-retry-pre-exec-output.txt"),
            db_path: root.join("worker-loop-retry-pre-exec.db"),
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
