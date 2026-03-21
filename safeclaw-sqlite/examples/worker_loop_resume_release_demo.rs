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
    PreflightDecision, ScheduleIntent, TaskOrchestrator,
};
use safeclaw_sqlite::{
    open_database, SandboxCommand, SqliteOpenOptions, SqliteRuntimeStore,
    SqliteSingleWorkerLoop, SqliteTaskOrchestrator,
};

fn main() -> Result<(), String> {
    let workspace = into_demo(env::current_dir())?;
    let temp = DemoArtifacts::new(&workspace)?;
    let shared_output = temp.root.join("worker-loop-resume-shared.txt");
    let other_output = temp.root.join("worker-loop-resume-other.txt");
    let shared_scope = format!("scope:{}", shared_output.display());
    let other_scope = format!("scope:{}", other_output.display());
    let output_bytes = b"safeclaw resumed other scope\n";

    let mut blocking_orchestrator = into_demo(open_database(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))
    .map(SqliteTaskOrchestrator::new)?
    .with_lease_ttl_ms(25);
    into_demo(blocking_orchestrator.enqueue(OrchestratorTask::new(
        "task-worker-resume-shared-blocking",
        ScheduleIntent::write(shared_scope.clone()),
        0,
    )))?;
    into_demo(blocking_orchestrator.enqueue(OrchestratorTask::new(
        "task-worker-resume-shared-queued",
        ScheduleIntent::write(shared_scope.clone()),
        1,
    )))?;
    into_demo(blocking_orchestrator.enqueue(OrchestratorTask::new(
        "task-worker-resume-other",
        ScheduleIntent::write(other_scope.clone()),
        2,
    )))?;
    print_snapshot("after-enqueue", blocking_orchestrator.queue_snapshot());

    let blocking_claim = into_demo(blocking_orchestrator.claim_next("worker-a", 0))?
        .expect("blocking task must be claimable");
    println!(
        "[demo] blocking claim => task={} lease={} fence={} owner={}",
        blocking_claim.task.task_id,
        blocking_claim.lease.lease_id,
        blocking_claim.lease.fencing_token,
        blocking_claim.lease.owner_id
    );
    print_snapshot("after-blocking-claim", blocking_orchestrator.queue_snapshot());

    let mut first_worker = into_demo(SqliteSingleWorkerLoop::open(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?
    .with_lease_ttl_ms(25);
    let first_error = first_worker
        .claim_and_drive_once("worker-b", 1, PreflightDecision::Permit, |claim| {
            println!("[demo] first claim => {}", claim.task.task_id);
            Ok((
                InMemoryTaskRuntime::new(demo_effect(
                    claim,
                    "effect-worker-loop-resume-release-demo",
                    "trace-worker-loop-resume-release-demo",
                    "intent-worker-loop-resume-release-demo",
                )),
                sandbox_missing_program_command(),
            ))
        })
        .unwrap_err();
    println!("[demo] first attempt spawn failure => {first_error:?}");
    print_snapshot("after-pre-exec-persist", first_worker.queue_snapshot());

    let persisted_store = SqliteRuntimeStore::new(into_demo(open_database(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?);
    let persisted = into_demo(persisted_store.load_runtime(
        "task-worker-resume-other",
        "effect-worker-loop-resume-release-demo",
    ))?
    .expect("persisted failed runtime must reload");
    println!(
        "[demo] persisted runtime => worker={:?}, effect={:?}, attempts={}",
        persisted.worker_state,
        persisted.effect.status,
        persisted.attempts.len()
    );

    let renewed = into_demo(blocking_orchestrator.renew_lease(
        &blocking_claim.task.task_id,
        &blocking_claim.lease.lease_id,
        &blocking_claim.lease.owner_id,
        20,
    ))?;
    println!(
        "[demo] renewed blocking lease => task={} expires={} owner={}",
        blocking_claim.task.task_id,
        renewed.expires_at_ms,
        renewed.owner_id
    );

    let mut blocked_worker = into_demo(SqliteSingleWorkerLoop::open(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?
    .with_lease_ttl_ms(25);
    let blocked = into_demo(blocked_worker.claim_and_resume_once("worker-c", 10, |_| unreachable!()))?;
    println!("[demo] reclaim before expiry => {}", blocked.is_none());

    let mut resume_worker = into_demo(SqliteSingleWorkerLoop::open(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?
    .with_lease_ttl_ms(25);
    let resumed = into_demo(resume_worker.claim_and_resume_persisted_once(
        "worker-c",
        27,
        "effect-worker-loop-resume-release-demo",
        |claim, runtime| {
            println!(
                "[demo] resume claim => task={} lease={} fence={} state={:?}",
                claim.task.task_id,
                claim.lease.lease_id,
                claim.lease.fencing_token,
                runtime.worker_state
            );
            Ok(sandbox_write_command(&other_output, output_bytes))
        },
    ))?
    .expect("expired other-scope task must be resumable");

    println!(
        "[demo] resume attempt => worker={:?}, effect={:?}, completed={}",
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
        "task-worker-resume-other",
        "effect-worker-loop-resume-release-demo",
    ))?
    .expect("persisted resumed runtime must reload");
    println!(
        "[demo] restored runtime => worker={:?}, effect={:?}, attempts={}",
        restored.worker_state,
        restored.effect.status,
        restored.attempts.len()
    );
    println!(
        "[demo] remaining queued task => {}",
        resume_worker.queue_snapshot().queued_tasks[0].task_id
    );
    println!(
        "[demo] remaining active lease => {}",
        resume_worker.queue_snapshot().active_leases[0].task_id
    );

    into_demo(blocking_orchestrator.complete(
        &blocking_claim.task.task_id,
        &blocking_claim.lease.lease_id,
        &blocking_claim.lease.owner_id,
    ))?;
    print_snapshot("after-release-blocking-claim", blocking_orchestrator.queue_snapshot());

    let mut release_worker = into_demo(SqliteSingleWorkerLoop::open(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?
    .with_lease_ttl_ms(25);
    let released = into_demo(release_worker.claim_and_drive_once(
        "worker-d",
        28,
        PreflightDecision::Permit,
        |claim| {
            println!("[demo] release claim => {}", claim.task.task_id);
            Ok((
                InMemoryTaskRuntime::new(demo_effect(
                    claim,
                    "effect-worker-loop-resume-release-shared",
                    "trace-worker-loop-resume-release-shared",
                    "intent-worker-loop-resume-release-shared",
                )),
                sandbox_write_command(&shared_output, b"safeclaw shared after resume release\n"),
            ))
        },
    ))?
    .expect("shared queued task must unblock after release");

    println!(
        "[demo] release attempt => worker={:?}, effect={:?}, completed={}",
        released.final_summary.worker_state,
        released.final_summary.effect_status,
        released.completed
    );
    print_snapshot("after-release-drive", release_worker.queue_snapshot());

    let verify_store = SqliteRuntimeStore::new(into_demo(open_database(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?);
    let restored_shared = into_demo(verify_store.load_runtime(
        "task-worker-resume-shared-queued",
        "effect-worker-loop-resume-release-shared",
    ))?
    .expect("released shared runtime must reload");
    println!(
        "[demo] restored shared runtime => worker={:?}, effect={:?}, attempts={}",
        restored_shared.worker_state,
        restored_shared.effect.status,
        restored_shared.attempts.len()
    );
    println!("[demo] shared output exists => {}", shared_output.exists());
    println!("[demo] db: {}", temp.db_path().display());
    println!("[demo] shared output: {}", shared_output.display());
    println!("[demo] other output: {}", other_output.display());
    Ok(())
}

fn demo_effect(
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
            .expect("worker resume release demo bytes must remain utf-8");
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
            .join(format!("worker-loop-resume-release-demo-{}-{unique}", process::id()));
        fs::create_dir_all(&root).map_err(|error| error.to_string())?;
        Ok(Self {
            db_path: root.join("worker-loop-resume-release.db"),
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
