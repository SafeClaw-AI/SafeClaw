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

    run_executed_batch(&temp)?;
    run_probe_batch(&temp)?;

    println!("[demo] db: {}", temp.db_path().display());
    println!("[demo] fresh output: {}", temp.fresh_output.display());
    println!("[demo] retry output: {}", temp.retry_output.display());
    println!("[demo] resume output: {}", temp.resume_output.display());
    println!("[demo] probe output: {}", temp.probe_output.display());
    Ok(())
}

fn run_executed_batch(temp: &DemoArtifacts) -> Result<(), String> {
    let mut retry_seed_worker = into_demo(SqliteSingleWorkerLoop::open(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?
    .with_lease_ttl_ms(25);
    into_demo(retry_seed_worker.enqueue_task(OrchestratorTask::new(
        "task-worker-dispatch-batch-demo-retry",
        ScheduleIntent::write(format!("scope:{}", temp.retry_output.display())),
        0,
    )))?;
    let failed = into_demo(retry_seed_worker.claim_and_drive_once(
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
    .expect("retry seed must claim task");
    println!(
        "[demo] retry seed => worker={:?} effect={:?} completed={}",
        failed.final_summary.worker_state, failed.final_summary.effect_status, failed.completed
    );

    let mut resume_seed_worker = into_demo(SqliteSingleWorkerLoop::open(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?
    .with_lease_ttl_ms(25);
    into_demo(resume_seed_worker.enqueue_task(OrchestratorTask::new(
        "task-worker-dispatch-batch-demo-resume",
        ScheduleIntent::write(format!("scope:{}", temp.resume_output.display())),
        1,
    )))?;
    let resume_error = resume_seed_worker
        .claim_and_drive_once("worker-resume-a", 0, PreflightDecision::Permit, |claim| {
            Ok((
                InMemoryTaskRuntime::new(resume_effect(claim)),
                sandbox_missing_program_command(),
            ))
        })
        .expect_err("resume seed must persist pre-exec runtime");
    println!("[demo] resume seed => {resume_error:?}");

    let mut fresh_worker = into_demo(SqliteSingleWorkerLoop::open(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?
    .with_lease_ttl_ms(25);
    into_demo(fresh_worker.enqueue_task(OrchestratorTask::new(
        "task-worker-dispatch-batch-demo-fresh",
        ScheduleIntent::write(format!("scope:{}", temp.fresh_output.display())),
        2,
    )))?;

    let expected_fresh = b"safeclaw batch fresh demo\n";
    let expected_retry = b"safeclaw batch retry demo\n";
    let expected_resume = b"safeclaw batch resume demo\n";

    let mut batch_worker = into_demo(SqliteSingleWorkerLoop::open(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?
    .with_lease_ttl_ms(25);
    let outcomes = into_demo(batch_worker.claim_and_dispatch_until_empty(
        "worker-batch",
        26,
        PreflightDecision::Permit,
        |claim| {
            Ok(match claim.task.task_id.as_str() {
                "task-worker-dispatch-batch-demo-fresh" => {
                    String::from("effect-worker-dispatch-batch-demo-fresh")
                }
                "task-worker-dispatch-batch-demo-retry" => {
                    String::from("effect-worker-dispatch-batch-demo-retry")
                }
                "task-worker-dispatch-batch-demo-resume" => {
                    String::from("effect-worker-dispatch-batch-demo-resume")
                }
                other => panic!("unexpected task id: {other}"),
            })
        },
        |claim| match claim.task.task_id.as_str() {
            "task-worker-dispatch-batch-demo-fresh" => Ok((
                InMemoryTaskRuntime::new(fresh_effect(claim)),
                sandbox_write_command(&temp.fresh_output, expected_fresh),
            )),
            other => panic!("unexpected fresh task id: {other}"),
        },
        |claim, runtime| match claim.task.task_id.as_str() {
            "task-worker-dispatch-batch-demo-retry" => {
                println!(
                    "[demo] retry batch => task={} state={:?}",
                    claim.task.task_id, runtime.worker_state
                );
                Ok(sandbox_write_command(&temp.retry_output, expected_retry))
            }
            "task-worker-dispatch-batch-demo-resume" => {
                println!(
                    "[demo] resume batch => task={} state={:?}",
                    claim.task.task_id, runtime.worker_state
                );
                Ok(sandbox_write_command(&temp.resume_output, expected_resume))
            }
            other => panic!("unexpected persisted task id: {other}"),
        },
    ))?;

    println!("[demo] executed batch => count={}", outcomes.len());
    for outcome in &outcomes {
        match outcome {
            WorkerLoopDispatchOutcome::Executed(executed) => println!(
                "[demo] executed => task={} worker={:?} effect={:?} completed={}",
                executed.claim.task.task_id,
                executed.final_summary.worker_state,
                executed.final_summary.effect_status,
                executed.completed
            ),
            WorkerLoopDispatchOutcome::Probed(_) => {
                return Err("executed batch unexpectedly probed".into())
            }
            _ => panic!("unexpected parked dispatch outcome"),
        }
    }
    let _diagnostics = into_demo(batch_worker.diagnostic_snapshots_for_outcomes(&outcomes))?;
    let summary = into_demo(batch_worker.governance_summary_for_outcomes(&outcomes))?;
    println!(
        "[demo] executed batch governance => {}",
        summary.render_counts()
    );
    print_snapshot(
        "executed-batch-after-complete",
        batch_worker.queue_snapshot(),
    );

    let verify_store = SqliteRuntimeStore::new(into_demo(open_database(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?);
    let restored_fresh = into_demo(verify_store.load_runtime(
        "task-worker-dispatch-batch-demo-fresh",
        "effect-worker-dispatch-batch-demo-fresh",
    ))?
    .expect("fresh batch runtime must reload");
    let restored_retry = into_demo(verify_store.load_runtime(
        "task-worker-dispatch-batch-demo-retry",
        "effect-worker-dispatch-batch-demo-retry",
    ))?
    .expect("retry batch runtime must reload");
    let restored_resume = into_demo(verify_store.load_runtime(
        "task-worker-dispatch-batch-demo-resume",
        "effect-worker-dispatch-batch-demo-resume",
    ))?
    .expect("resume batch runtime must reload");
    println!(
        "[demo] restored executed batch => fresh={:?}/{:?}, retry={:?}/{:?}, resume={:?}/{:?}",
        restored_fresh.worker_state,
        restored_fresh.effect.status,
        restored_retry.worker_state,
        restored_retry.effect.status,
        restored_resume.worker_state,
        restored_resume.effect.status,
    );
    Ok(())
}

fn run_probe_batch(temp: &DemoArtifacts) -> Result<(), String> {
    let expected_probe = b"safeclaw batch probe demo\n";
    let mut orchestrator = SqliteTaskOrchestrator::new(into_demo(open_database(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?)
    .with_lease_ttl_ms(25);
    into_demo(orchestrator.enqueue(OrchestratorTask::new(
        "task-worker-dispatch-batch-demo-probe",
        ScheduleIntent::write(format!("scope:{}", temp.probe_output.display())),
        3,
    )))?;
    let claim = into_demo(orchestrator.claim_next("worker-probe-a", 100))?
        .expect("probe batch seed must claim task");
    let mut runtime = InMemoryTaskRuntime::new(probe_effect(&claim));
    runtime
        .begin_execution(PreflightDecision::Permit)
        .map_err(|error| format!("{error:?}"))?;
    let executor = LocalSandboxExecutor::new();
    let (_, execution_summary) = into_demo(executor.run_and_apply(
        &mut runtime,
        &sandbox_write_then_timeout_command(&temp.probe_output, expected_probe),
    ))?;
    println!(
        "[demo] probe seed => worker={:?} effect={:?}",
        execution_summary.worker_state, execution_summary.effect_status
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

    let mut batch_worker = into_demo(SqliteSingleWorkerLoop::open(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?
    .with_lease_ttl_ms(25);
    batch_worker
        .filesystem_probe_mut()
        .register_expected_blake3(
            "effect-worker-dispatch-batch-demo-probe",
            blake3::hash(expected_probe).to_hex().to_string(),
        );
    let outcomes = into_demo(batch_worker.claim_and_dispatch_until_empty(
        "worker-probe-b",
        126,
        PreflightDecision::Permit,
        |_| Ok(String::from("effect-worker-dispatch-batch-demo-probe")),
        |_| unreachable!(),
        |_, _| unreachable!(),
    ))?;

    println!("[demo] probe batch => count={}", outcomes.len());
    for outcome in &outcomes {
        match outcome {
            WorkerLoopDispatchOutcome::Probed(probed) => println!(
                "[demo] probed => task={} from={:?} worker={:?} effect={:?} completed={}",
                probed.claim.task.task_id,
                probed.recovered_from,
                probed.final_summary.worker_state,
                probed.final_summary.effect_status,
                probed.completed
            ),
            WorkerLoopDispatchOutcome::Executed(_) => {
                return Err("probe batch unexpectedly executed".into())
            }
            _ => panic!("unexpected parked dispatch outcome"),
        }
    }
    let _diagnostics = into_demo(batch_worker.diagnostic_snapshots_for_outcomes(&outcomes))?;
    let summary = into_demo(batch_worker.governance_summary_for_outcomes(&outcomes))?;
    println!(
        "[demo] probe batch governance => {}",
        summary.render_counts()
    );
    print_snapshot("probe-batch-after-complete", batch_worker.queue_snapshot());
    Ok(())
}

fn fresh_effect(claim: &OrchestratorClaim) -> EffectRecord {
    build_effect(
        claim,
        "effect-worker-dispatch-batch-demo-fresh",
        "trace-worker-dispatch-batch-demo-fresh",
        "intent-worker-dispatch-batch-demo-fresh",
    )
}

fn retry_effect(claim: &OrchestratorClaim) -> EffectRecord {
    build_effect(
        claim,
        "effect-worker-dispatch-batch-demo-retry",
        "trace-worker-dispatch-batch-demo-retry",
        "intent-worker-dispatch-batch-demo-retry",
    )
}

fn resume_effect(claim: &OrchestratorClaim) -> EffectRecord {
    build_effect(
        claim,
        "effect-worker-dispatch-batch-demo-resume",
        "trace-worker-dispatch-batch-demo-resume",
        "intent-worker-dispatch-batch-demo-resume",
    )
}

fn probe_effect(claim: &OrchestratorClaim) -> EffectRecord {
    build_effect(
        claim,
        "effect-worker-dispatch-batch-demo-probe",
        "trace-worker-dispatch-batch-demo-probe",
        "intent-worker-dispatch-batch-demo-probe",
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
            .expect("dispatch batch demo bytes must remain utf-8");
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
            .expect("dispatch batch probe bytes must remain utf-8");
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
            "worker-loop-dispatch-batch-demo-{}-{unique}",
            process::id()
        ));
        fs::create_dir_all(&root).map_err(|error| error.to_string())?;
        Ok(Self {
            fresh_output: root.join("worker-loop-dispatch-batch-fresh.txt"),
            retry_output: root.join("worker-loop-dispatch-batch-retry.txt"),
            resume_output: root.join("worker-loop-dispatch-batch-resume.txt"),
            probe_output: root.join("worker-loop-dispatch-batch-probe.txt"),
            db_path: root.join("worker-loop-dispatch-batch.db"),
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
