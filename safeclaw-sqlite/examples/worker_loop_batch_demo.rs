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
    PreflightDecision, ScheduleIntent,
};
use safeclaw_sqlite::{
    open_database, SandboxCommand, SqliteOpenOptions, SqliteRuntimeStore, SqliteSingleWorkerLoop,
};

fn main() -> Result<(), String> {
    let workspace = into_demo(env::current_dir())?;
    let temp = DemoArtifacts::new(&workspace)?;
    let first_output = temp.root.join("worker-loop-batch-output-1.txt");
    let second_output = temp.root.join("worker-loop-batch-output-2.txt");

    let mut loop_driver = into_demo(SqliteSingleWorkerLoop::open(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?
    .with_lease_ttl_ms(60_000);
    into_demo(loop_driver.enqueue_task(OrchestratorTask::new(
        "task-worker-loop-batch-1",
        ScheduleIntent::write(format!("scope:{}", first_output.display())),
        0,
    )))?;
    into_demo(loop_driver.enqueue_task(OrchestratorTask::new(
        "task-worker-loop-batch-2",
        ScheduleIntent::write(format!("scope:{}", second_output.display())),
        0,
    )))?;
    print_snapshot("after-enqueue", loop_driver.queue_snapshot());

    let outcomes = into_demo(loop_driver.claim_and_drive_until_empty(
        "worker-demo",
        1,
        PreflightDecision::Permit,
        |claim| match claim.task.task_id.as_str() {
            "task-worker-loop-batch-1" => Ok((
                InMemoryTaskRuntime::new(build_demo_effect(
                    claim,
                    "effect-worker-loop-batch-1",
                    "trace-worker-loop-batch-1",
                    "intent-worker-loop-batch-1",
                )),
                sandbox_write_command(&first_output, b"safeclaw batch demo one\n"),
            )),
            "task-worker-loop-batch-2" => Ok((
                InMemoryTaskRuntime::new(build_demo_effect(
                    claim,
                    "effect-worker-loop-batch-2",
                    "trace-worker-loop-batch-2",
                    "intent-worker-loop-batch-2",
                )),
                sandbox_write_command(&second_output, b"safeclaw batch demo two\n"),
            )),
            other => panic!("unexpected task id: {other}"),
        },
    ))?;

    println!("[demo] drained batch => count={}", outcomes.len());
    for outcome in &outcomes {
        println!(
            "[demo] outcome => task={} lease={} fence={} worker={:?} effect={:?} completed={}",
            outcome.claim.task.task_id,
            outcome.claim.lease.lease_id,
            outcome.claim.lease.fencing_token,
            outcome.final_summary.worker_state,
            outcome.final_summary.effect_status,
            outcome.completed
        );
    }
    print_snapshot("after-batch-complete", loop_driver.queue_snapshot());

    let verify_store = SqliteRuntimeStore::new(into_demo(open_database(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?);
    let restored_one = into_demo(
        verify_store.load_runtime("task-worker-loop-batch-1", "effect-worker-loop-batch-1"),
    )?
    .expect("first batch runtime must reload");
    let restored_two = into_demo(
        verify_store.load_runtime("task-worker-loop-batch-2", "effect-worker-loop-batch-2"),
    )?
    .expect("second batch runtime must reload");
    println!(
        "[demo] restored runtimes => one={:?}/{:?}, two={:?}/{:?}",
        restored_one.worker_state,
        restored_one.effect.status,
        restored_two.worker_state,
        restored_two.effect.status
    );
    println!("[demo] db: {}", temp.db_path().display());
    println!("[demo] output-1: {}", first_output.display());
    println!("[demo] output-2: {}", second_output.display());
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
            .expect("worker batch demo bytes must remain utf-8");
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
            .join(format!("worker-loop-batch-demo-{}-{unique}", process::id()));
        fs::create_dir_all(&root).map_err(|error| error.to_string())?;
        Ok(Self {
            db_path: root.join("worker-loop-batch.db"),
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
