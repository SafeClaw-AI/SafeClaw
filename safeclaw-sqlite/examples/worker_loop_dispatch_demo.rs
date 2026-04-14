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
    InMemoryTaskRuntime, OrchestratorClaim, OrchestratorSnapshot, OrchestratorTask,
    PreflightDecision, ScheduleIntent,
};
use safeclaw_sqlite::{
    open_database, LocalSandboxExecutor, SandboxCommand, SqliteOpenOptions, SqliteRuntimeStore,
    SqliteSingleWorkerLoop, SqliteTaskOrchestrator, WorkerLoopDispatchOutcome,
};

fn main() -> Result<(), String> {
    let workspace = into_demo(env::current_dir())?;
    let temp = DemoArtifacts::new(&workspace)?;

    run_fresh_branch(&temp)?;
    run_retry_branch(&temp)?;
    run_resume_branch(&temp)?;
    run_probe_branch(&temp)?;

    println!("[demo] db: {}", temp.db_path().display());
    println!("[demo] fresh output: {}", temp.fresh_output.display());
    println!("[demo] retry output: {}", temp.retry_output.display());
    println!("[demo] resume output: {}", temp.resume_output.display());
    println!("[demo] probe output: {}", temp.probe_output.display());
    Ok(())
}

fn run_fresh_branch(temp: &DemoArtifacts) -> Result<(), String> {
    let output_bytes = b"safeclaw dispatch fresh demo\n";
    let mut worker = into_demo(SqliteSingleWorkerLoop::open(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?
    .with_lease_ttl_ms(25);
    into_demo(worker.enqueue_task(OrchestratorTask::new(
        "task-worker-dispatch-demo-fresh",
        ScheduleIntent::write(format!("scope:{}", temp.fresh_output.display())),
        0,
    )))?;
    print_snapshot("fresh-after-enqueue", worker.queue_snapshot());

    let outcome = into_demo(worker.claim_and_dispatch_once(
        "worker-fresh",
        0,
        "effect-worker-dispatch-demo-fresh",
        PreflightDecision::Permit,
        |claim| {
            Ok((
                InMemoryTaskRuntime::new(fresh_effect(claim)),
                sandbox_write_command(&temp.fresh_output, output_bytes),
            ))
        },
        |_, _| unreachable!(),
    ))?
    .expect("fresh task must dispatch");

    match outcome {
        WorkerLoopDispatchOutcome::Executed(executed) => println!(
            "[demo] fresh => task={} worker={:?} effect={:?} completed={}",
            executed.claim.task.task_id,
            executed.final_summary.worker_state,
            executed.final_summary.effect_status,
            executed.completed
        ),
        WorkerLoopDispatchOutcome::Probed(_) => {
            return Err("fresh branch unexpectedly probed".into())
        }
        _ => panic!("unexpected parked dispatch outcome"),
    }
    print_snapshot("fresh-after-complete", worker.queue_snapshot());
    Ok(())
}

fn run_retry_branch(temp: &DemoArtifacts) -> Result<(), String> {
    let mut failing_worker = into_demo(SqliteSingleWorkerLoop::open(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?
    .with_lease_ttl_ms(25);
    into_demo(failing_worker.enqueue_task(OrchestratorTask::new(
        "task-worker-dispatch-demo-retry",
        ScheduleIntent::write(format!("scope:{}", temp.retry_output.display())),
        0,
    )))?;

    let failed = into_demo(failing_worker.claim_and_drive_once(
        "worker-retry-a",
        0,
        PreflightDecision::Permit,
        |claim| {
            Ok((
                InMemoryTaskRuntime::new(retry_effect(claim)),
                sandbox_fail_command(),
            ))
        },
    ))?
    .expect("retry seed task must claim");
    println!(
        "[demo] failed seed => worker={:?} effect={:?} completed={}",
        failed.final_summary.worker_state, failed.final_summary.effect_status, failed.completed
    );

    let output_bytes = b"safeclaw dispatch retry demo\n";
    let mut retry_worker = into_demo(SqliteSingleWorkerLoop::open(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?
    .with_lease_ttl_ms(25);
    let outcome = into_demo(retry_worker.claim_and_dispatch_once(
        "worker-retry-b",
        26,
        "effect-worker-dispatch-demo-retry",
        PreflightDecision::Permit,
        |_| unreachable!(),
        |claim, runtime| {
            println!(
                "[demo] retry dispatch => task={} state={:?}",
                claim.task.task_id, runtime.worker_state
            );
            Ok(sandbox_write_command(&temp.retry_output, output_bytes))
        },
    ))?
    .expect("failed runtime must dispatch through retry branch");

    match outcome {
        WorkerLoopDispatchOutcome::Executed(executed) => println!(
            "[demo] retry => task={} worker={:?} effect={:?} completed={}",
            executed.claim.task.task_id,
            executed.final_summary.worker_state,
            executed.final_summary.effect_status,
            executed.completed
        ),
        WorkerLoopDispatchOutcome::Probed(_) => {
            return Err("retry branch unexpectedly probed".into())
        }
        _ => panic!("unexpected parked dispatch outcome"),
    }
    print_snapshot("retry-after-complete", retry_worker.queue_snapshot());
    Ok(())
}

fn run_resume_branch(temp: &DemoArtifacts) -> Result<(), String> {
    let mut first_worker = into_demo(SqliteSingleWorkerLoop::open(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?
    .with_lease_ttl_ms(25);
    into_demo(first_worker.enqueue_task(OrchestratorTask::new(
        "task-worker-dispatch-demo-resume",
        ScheduleIntent::write(format!("scope:{}", temp.resume_output.display())),
        0,
    )))?;
    print_snapshot("resume-after-enqueue", first_worker.queue_snapshot());

    let first_error = first_worker
        .claim_and_drive_once("worker-resume-a", 0, PreflightDecision::Permit, |claim| {
            Ok((
                InMemoryTaskRuntime::new(resume_effect(claim)),
                sandbox_missing_program_command(),
            ))
        })
        .expect_err("resume seed task must persist pre-exec runtime");
    println!("[demo] resume seed => {first_error:?}");

    let mut blocked_worker = into_demo(SqliteSingleWorkerLoop::open(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?
    .with_lease_ttl_ms(25);
    let blocked = into_demo(blocked_worker.claim_and_dispatch_once(
        "worker-resume-b",
        10,
        "effect-worker-dispatch-demo-resume",
        PreflightDecision::Permit,
        |_| unreachable!(),
        |_, _| unreachable!(),
    ))?;
    println!(
        "[demo] resume reclaim before expiry => {}",
        blocked.is_none()
    );

    let output_bytes = b"safeclaw dispatch resume demo\n";
    let mut resume_worker = into_demo(SqliteSingleWorkerLoop::open(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?
    .with_lease_ttl_ms(25);
    let outcome = into_demo(resume_worker.claim_and_dispatch_once(
        "worker-resume-b",
        26,
        "effect-worker-dispatch-demo-resume",
        PreflightDecision::Permit,
        |_| unreachable!(),
        |claim, runtime| {
            println!(
                "[demo] resume dispatch => task={} state={:?}",
                claim.task.task_id, runtime.worker_state
            );
            Ok(sandbox_write_command(&temp.resume_output, output_bytes))
        },
    ))?
    .expect("expired pre-exec runtime must dispatch through resume branch");

    match outcome {
        WorkerLoopDispatchOutcome::Executed(executed) => println!(
            "[demo] resume => task={} worker={:?} effect={:?} completed={}",
            executed.claim.task.task_id,
            executed.final_summary.worker_state,
            executed.final_summary.effect_status,
            executed.completed
        ),
        WorkerLoopDispatchOutcome::Probed(_) => {
            return Err("resume branch unexpectedly probed".into())
        }
        _ => panic!("unexpected parked dispatch outcome"),
    }
    print_snapshot("resume-after-complete", resume_worker.queue_snapshot());
    Ok(())
}

fn run_probe_branch(temp: &DemoArtifacts) -> Result<(), String> {
    let output_bytes = b"safeclaw dispatch probe demo\n";
    let mut orchestrator = SqliteTaskOrchestrator::new(into_demo(open_database(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?)
    .with_lease_ttl_ms(25);
    into_demo(orchestrator.enqueue(OrchestratorTask::new(
        "task-worker-dispatch-demo-probe",
        ScheduleIntent::write(format!("scope:{}", temp.probe_output.display())),
        0,
    )))?;
    let claim = into_demo(orchestrator.claim_next("worker-probe-a", 100))?
        .expect("probe seed task must claim");

    let mut runtime = InMemoryTaskRuntime::new(probe_effect(&claim));
    into_demo(runtime.begin_execution(PreflightDecision::Permit))?;
    let executor = LocalSandboxExecutor::new();
    let (_, summary) = into_demo(executor.run_and_apply(
        &mut runtime,
        &sandbox_write_then_timeout_command(&temp.probe_output, output_bytes),
    ))?;
    println!(
        "[demo] probe seed => worker={:?} effect={:?}",
        summary.worker_state, summary.effect_status
    );
    let mut store = SqliteRuntimeStore::new(into_demo(open_database(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?);
    into_demo(store.persist_runtime(
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
            "effect-worker-dispatch-demo-probe",
            blake3::hash(output_bytes).to_hex().to_string(),
        );
    let outcome = into_demo(probe_worker.claim_and_dispatch_once(
        "worker-probe-b",
        126,
        "effect-worker-dispatch-demo-probe",
        PreflightDecision::Permit,
        |_| unreachable!(),
        |_, _| unreachable!(),
    ))?
    .expect("uncertain runtime must dispatch through probe branch");

    match outcome {
        WorkerLoopDispatchOutcome::Probed(probed) => println!(
            "[demo] probe => task={} from={:?} worker={:?} effect={:?} completed={}",
            probed.claim.task.task_id,
            probed.recovered_from,
            probed.final_summary.worker_state,
            probed.final_summary.effect_status,
            probed.completed
        ),
        WorkerLoopDispatchOutcome::Executed(_) => {
            return Err("probe branch unexpectedly executed".into())
        }
        _ => panic!("unexpected parked dispatch outcome"),
    }
    print_snapshot("probe-after-complete", probe_worker.queue_snapshot());
    Ok(())
}

fn fresh_effect(claim: &OrchestratorClaim) -> EffectRecord {
    build_effect(
        claim,
        "effect-worker-dispatch-demo-fresh",
        "trace-worker-dispatch-demo-fresh",
        "intent-worker-dispatch-demo-fresh",
    )
}

fn retry_effect(claim: &OrchestratorClaim) -> EffectRecord {
    build_effect(
        claim,
        "effect-worker-dispatch-demo-retry",
        "trace-worker-dispatch-demo-retry",
        "intent-worker-dispatch-demo-retry",
    )
}

fn resume_effect(claim: &OrchestratorClaim) -> EffectRecord {
    build_effect(
        claim,
        "effect-worker-dispatch-demo-resume",
        "trace-worker-dispatch-demo-resume",
        "intent-worker-dispatch-demo-resume",
    )
}

fn probe_effect(claim: &OrchestratorClaim) -> EffectRecord {
    build_effect(
        claim,
        "effect-worker-dispatch-demo-probe",
        "trace-worker-dispatch-demo-probe",
        "intent-worker-dispatch-demo-probe",
    )
}

fn build_effect(
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

fn sandbox_fail_command() -> SandboxCommand {
    if cfg!(windows) {
        SandboxCommand::new(
            "powershell",
            ["-Command", "Write-Error 'boom'; exit 7"],
            5_000,
        )
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
            .expect("dispatch demo bytes must remain utf-8");
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
            .expect("dispatch probe demo bytes must remain utf-8");
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
    fresh_output: PathBuf,
    retry_output: PathBuf,
    resume_output: PathBuf,
    probe_output: PathBuf,
    db_path: PathBuf,
}

impl DemoArtifacts {
    fn new(workspace: &Path) -> Result<Self, String> {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_err(|error| error.to_string())?
            .as_nanos();
        let root = workspace.join("target").join(format!(
            "worker-loop-dispatch-demo-{}-{unique}",
            process::id()
        ));
        fs::create_dir_all(&root).map_err(|error| error.to_string())?;
        Ok(Self {
            fresh_output: root.join("worker-loop-dispatch-fresh.txt"),
            retry_output: root.join("worker-loop-dispatch-retry.txt"),
            resume_output: root.join("worker-loop-dispatch-resume.txt"),
            probe_output: root.join("worker-loop-dispatch-probe.txt"),
            db_path: root.join("worker-loop-dispatch.db"),
            root,
        })
    }

    fn db_path(&self) -> &Path {
        &self.db_path
    }
}

impl Drop for DemoArtifacts {
    fn drop(&mut self) {
        let _ = fs::remove_file(&self.fresh_output);
        let _ = fs::remove_file(&self.retry_output);
        let _ = fs::remove_file(&self.resume_output);
        let _ = fs::remove_file(&self.probe_output);
        let _ = fs::remove_file(&self.db_path);
        let _ = fs::remove_file(PathBuf::from(format!("{}-wal", self.db_path.display())));
        let _ = fs::remove_file(PathBuf::from(format!("{}-shm", self.db_path.display())));
        let _ = fs::remove_dir(&self.root);
    }
}
