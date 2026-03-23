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
    PreflightDecision, ScheduleIntent,
};
use safeclaw_sqlite::{
    open_database, SandboxCommand, SqliteOpenOptions, SqliteRuntimeStore,
    SqliteSingleWorkerLoop,
};

fn main() -> Result<(), String> {
    let workspace = into_demo(env::current_dir())?;
    let temp = DemoArtifacts::new(&workspace)?;
    let output_bytes = b"safeclaw worker loop demo\n";

    let mut loop_driver = into_demo(SqliteSingleWorkerLoop::open(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?
    .with_lease_ttl_ms(60_000);
    into_demo(loop_driver.enqueue_task(OrchestratorTask::new(
        "task-worker-loop-demo",
        ScheduleIntent::write(format!("scope:{}", temp.output_path.display())),
        0,
    )))?;
    loop_driver.filesystem_probe_mut().register_expected_blake3(
        "effect-worker-loop-demo",
        blake3::hash(output_bytes).to_hex().to_string(),
    );

    print_snapshot("after-enqueue", loop_driver.queue_snapshot());

    let outcome = into_demo(loop_driver.claim_and_drive_once(
        "worker-demo",
        1,
        PreflightDecision::Permit,
        |claim| {
            Ok((
                InMemoryTaskRuntime::new(demo_effect(claim)),
                sandbox_write_then_timeout_command(&temp.output_path, output_bytes),
            ))
        },
    ))?
    .expect("queued task must be claimable");

    println!(
        "[demo] claim => task={} lease={} fence={}",
        outcome.claim.task.task_id,
        outcome.claim.lease.lease_id,
        outcome.claim.lease.fencing_token
    );
    println!(
        "[demo] sandbox => timed_out={} exit_code={:?} duration_ms={}",
        outcome.report.timed_out,
        outcome.report.exit_code,
        outcome.report.duration_ms
    );
    println!("[demo] execution summary => {}", outcome.render_execution_status_line());
    println!("[demo] final summary => {}", outcome.render_final_status_line());

    print_snapshot("after-complete", loop_driver.queue_snapshot());

    let verify_store = SqliteRuntimeStore::new(into_demo(open_database(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?);
    let restored = into_demo(verify_store.load_runtime(
        "task-worker-loop-demo",
        "effect-worker-loop-demo",
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
        "effect-worker-loop-demo",
        claim.task.task_id.clone(),
        "trace-worker-loop-demo",
        "intent-worker-loop-demo",
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

fn sandbox_write_then_timeout_command(
    output_path: &Path,
    output_bytes: &[u8],
) -> SandboxCommand {
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
            .expect("worker loop demo bytes must remain utf-8");
        SandboxCommand::new(
            "sh",
            [
                "-c",
                &format!("printf '%s' '{}' > '{}'; sleep 1", text, output_path.display()),
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
        let root = workspace
            .join("target")
            .join(format!("worker-loop-demo-{}-{unique}", process::id()));
        fs::create_dir_all(&root).map_err(|error| error.to_string())?;
        Ok(Self {
            output_path: root.join("worker-loop-output.txt"),
            db_path: root.join("worker-loop.db"),
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
