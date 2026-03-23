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
    scheduler::OrchestratorTask,
    InMemoryTaskRuntime, PreflightDecision, ScheduleIntent,
};
use safeclaw_sqlite::{
    RuntimeGovernanceDisposition, SandboxCommand, SqliteOpenOptions,
    SqliteWorkerService,
};

fn main() -> Result<(), String> {
    let temp = TempDatabase::new("worker-service-governance")?;
    let mut service = SqliteWorkerService::open(
        temp.path(),
        SqliteOpenOptions::default(),
        "worker-service-demo-a",
    )
    .map_err(|error| format!("{error:?}"))?
    .with_lease_ttl_ms(25)
    .with_poll_interval_ms(5);

    enqueue_demo_task(&mut service, "task-worker-service-governance-a")?;
    enqueue_demo_task(&mut service, "task-worker-service-governance-b")?;

    let resolved_report = run_demo_report(&mut service, 0, PreflightDecision::Permit)?;
    println!(
        "[demo] service run resolved => executed={} probed={} parked={}",
        resolved_report.executed_count(),
        resolved_report.probed_count(),
        resolved_report.parked_count(),
    );
    let resolved_governance = service
        .governance_report_for_report(&resolved_report)
        .map_err(|error| format!("{error:?}"))?;
    println!(
        "[demo] service governance resolved => total={} resolved={} confirmation={} manual_review={}",
        resolved_governance.summary.total,
        resolved_governance.summary.resolved,
        resolved_governance.summary.queue_for_confirmation,
        resolved_governance.summary.queue_for_manual_review,
    );
    println!(
        "[demo] service governance resolved tasks => {}",
        resolved_governance
            .task_ids_for_disposition(RuntimeGovernanceDisposition::Resolved)
            .join(",")
    );
    print_snapshot("after-resolved", service.queue_snapshot());

    enqueue_demo_task(&mut service, "task-worker-service-governance-confirmation")?;

    let confirmation_report =
        run_demo_report(&mut service, 100, PreflightDecision::NeedsConfirmation)?;
    println!(
        "[demo] service run confirmation => executed={} probed={} parked={}",
        confirmation_report.executed_count(),
        confirmation_report.probed_count(),
        confirmation_report.parked_count(),
    );
    let confirmation_governance = service
        .governance_report_for_report(&confirmation_report)
        .map_err(|error| format!("{error:?}"))?;
    println!(
        "[demo] service governance confirmation => total={} resolved={} confirmation={} manual_review={}",
        confirmation_governance.summary.total,
        confirmation_governance.summary.resolved,
        confirmation_governance.summary.queue_for_confirmation,
        confirmation_governance.summary.queue_for_manual_review,
    );
    println!(
        "[demo] service governance confirmation tasks => {}",
        confirmation_governance
            .task_ids_for_disposition(RuntimeGovernanceDisposition::QueueForConfirmation)
            .join(",")
    );
    print_snapshot("after-confirmation", service.queue_snapshot());
    println!("[demo] db: {}", temp.path().display());
    Ok(())
}

fn enqueue_demo_task(
    service: &mut SqliteWorkerService,
    task_id: &str,
) -> Result<(), String> {
    service
        .enqueue_task(OrchestratorTask::new(
            task_id,
            ScheduleIntent::write(format!("scope:{task_id}")),
            0,
        ))
        .map_err(|error| format!("{error:?}"))
}

fn run_demo_report(
    service: &mut SqliteWorkerService,
    start_now_ms: u64,
    preflight: PreflightDecision,
) -> Result<safeclaw_sqlite::WorkerServiceRunReport, String> {
    service
        .run_dispatch_until_idle(
            start_now_ms,
            2,
            preflight,
            |claim| Ok(format!("effect-{}", claim.task.task_id)),
            |claim| {
                let effect_id = format!("effect-{}", claim.task.task_id);
                let effect = EffectRecord::new(
                    effect_id,
                    claim.task.task_id.clone(),
                    format!("trace-{}", claim.task.task_id),
                    format!("intent-{}", claim.task.task_id),
                    EffectActor::Worker,
                    EffectAction::FileWrite,
                    claim.task.intent.target_scope.clone(),
                    EffectTier::Tier1,
                    EffectReversibility::Rollbackable,
                    ProbeMode::Auto,
                );
                Ok((InMemoryTaskRuntime::new(effect), sandbox_success_command()))
            },
            |_, _| unreachable!(),
        )
        .map_err(|error| format!("{error:?}"))
}

fn print_snapshot(label: &str, snapshot: safeclaw_core::OrchestratorSnapshot) {
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

struct TempDatabase {
    path: PathBuf,
}

impl TempDatabase {
    fn new(label: &str) -> Result<Self, String> {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_err(|error| error.to_string())?
            .as_nanos();
        let path = env::temp_dir().join(format!(
            "safeclaw-{label}-{}-{unique}.db",
            process::id()
        ));
        Ok(Self { path })
    }

    fn path(&self) -> &Path {
        &self.path
    }
}

impl Drop for TempDatabase {
    fn drop(&mut self) {
        for suffix in ["", "-wal", "-shm"] {
            let candidate = if suffix.is_empty() {
                self.path.clone()
            } else {
                PathBuf::from(format!("{}{}", self.path.display(), suffix))
            };
            let _ = fs::remove_file(candidate);
        }
    }
}
