use std::{
    env, fs,
    path::{Path, PathBuf},
    process,
    time::{SystemTime, UNIX_EPOCH},
};

use rusqlite::{Connection, OptionalExtension};
use safeclaw_core::{
    ConfirmationAction, HibernationAction,
    effect_ledger::{
        EffectAction, EffectActor, EffectRecord, EffectReversibility, EffectTier,
        ProbeMode,
    },
    scheduler::{OrchestratorClaim, OrchestratorSnapshot, OrchestratorTask, TaskOrchestrator},
    worker_lifecycle::WorkerState, InMemoryTaskRuntime, PreflightDecision,
    ReconcileDecision, ScheduleIntent,
};
use safeclaw_sqlite::{
    open_database, LocalSandboxExecutor, SandboxCommand, SqliteOpenOptions, SqliteRuntimeStore,
    SqliteSingleWorkerLoop, SqliteTaskOrchestrator, SqliteWorkerService,
};

const DEFAULT_CONTENT: &str = "safeclaw mvp entry\n";
const DEFAULT_OWNER_ID: &str = "safeclaw-mvp";
const RECOVERY_LEASE_TTL_MS: u64 = 25;
const RECOVERY_BLOCKED_NOW_MS: u64 = 10;
const RECOVERY_RECLAIM_NOW_MS: u64 = 26;

fn main() -> Result<(), String> {
    let raw_args = env::args().skip(1).collect::<Vec<_>>();
    if raw_args.iter().any(|arg| arg == "--help" || arg == "-h") {
        print_usage();
        return Ok(());
    }

    let args = CliArgs::parse(raw_args)?;
    match args.action {
        CliAction::Run => run_action(&args),
        CliAction::Report => report_action(&args),
        CliAction::Status => status_action(&args),
        CliAction::SeedCrash => seed_crash_action(&args),
        CliAction::SeedHibernated => seed_hibernated_action(&args),
        CliAction::Recover => recover_action(&args),
        CliAction::SeedFailed => seed_failed_action(&args),
        CliAction::Retry => retry_action(&args),
        CliAction::Resume => resume_action(&args),
        CliAction::Reconcile => reconcile_action(&args),
    }
}

fn run_action(args: &CliArgs) -> Result<(), String> {
    ensure_parent_dir(&args.db_path)?;
    ensure_parent_dir(&args.output_path)?;
    if args.reset {
        reset_session_artifacts(&args.db_path, &args.output_path);
    }

    let effect_id = args.effect_id();
    let mut service = SqliteWorkerService::open(
        &args.db_path,
        SqliteOpenOptions::default(),
        args.owner_id.clone(),
    )
    .map_err(|error| format!("{error:?}"))?
    .with_lease_ttl_ms(60_000)
    .with_poll_interval_ms(5);

    if args.probe_mode == ProbeModeCli::Auto {
        service.filesystem_probe_mut().register_expected_blake3(
            effect_id.clone(),
            blake3::hash(args.content.as_bytes()).to_hex().to_string(),
        );
    }
    service
        .enqueue_task(OrchestratorTask::new(
            &args.task_id,
            ScheduleIntent::write(format!("scope:{}", args.output_path.display())),
            0,
        ))
        .map_err(|error| format!("{error:?}"))?;

    println!("[mvp] accepted task => task={} effect={}", args.task_id, effect_id);
    print_snapshot("after-enqueue", service.queue_snapshot());

    let output_path = args.output_path.clone();
    let content = args.content.clone();
    let effect_id_for_service = effect_id.clone();
    let report = service
        .run_dispatch_until_idle(
            0,
            2,
            PreflightDecision::Permit,
            {
                let effect_id = effect_id_for_service.clone();
                move |_| Ok(effect_id.clone())
            },
            {
                let effect_id = effect_id_for_service.clone();
                let output_path = output_path.clone();
                let content = content.clone();
                move |claim| {
                    Ok((
                        build_runtime(claim, &effect_id, args.probe_mode.to_probe_mode()),
                        sandbox_write_command(&output_path, content.as_bytes()),
                    ))
                }
            },
            {
                let output_path = output_path.clone();
                let content = content.clone();
                move |_, _| Ok(sandbox_write_command(&output_path, content.as_bytes()))
            },
        )
        .map_err(|error| format!("{error:?}"))?;

    println!(
        "[mvp] run report => polls={} idle={} executed={} probed={} parked={}",
        report.poll_count,
        report.consecutive_idle_polls,
        report.executed_count(),
        report.probed_count(),
        report.parked_count()
    );

    let governance = service
        .governance_report_for_report(&report)
        .map_err(|error| format!("{error:?}"))?;
    for line in governance.render_lines() {
        println!("[mvp] governance {line}");
    }

    print_snapshot("after-run", service.queue_snapshot());
    print_output_state(&args.output_path)?;
    println!("[mvp] db: {}", args.db_path.display());
    println!("[mvp] output: {}", args.output_path.display());
    println!("[mvp] owner: {}", args.owner_id);
    println!(
        "[mvp] next report => cargo run -p safeclaw-sqlite --example safeclaw_mvp_entry -- report --db \"{}\" --output \"{}\" --task-id {} --effect-id {}",
        args.db_path.display(),
        args.output_path.display(),
        args.task_id,
        effect_id
    );
    Ok(())
}

fn report_action(args: &CliArgs) -> Result<(), String> {
    let effect_id = args.effect_id();
    let service = SqliteWorkerService::open(
        &args.db_path,
        SqliteOpenOptions::default(),
        args.owner_id.clone(),
    )
    .map_err(|error| format!("{error:?}"))?;

    print_runtime_status(&service, args, "report", &args.task_id, &effect_id)
}

fn status_action(args: &CliArgs) -> Result<(), String> {
    let (task_id, effect_id) = resolve_status_target(args)?;
    let service = SqliteWorkerService::open(
        &args.db_path,
        SqliteOpenOptions::default(),
        args.owner_id.clone(),
    )
    .map_err(|error| format!("{error:?}"))?;

    print_runtime_status(&service, args, "status", &task_id, &effect_id)
}

fn seed_crash_action(args: &CliArgs) -> Result<(), String> {
    ensure_parent_dir(&args.db_path)?;
    ensure_parent_dir(&args.output_path)?;
    if args.reset {
        reset_session_artifacts(&args.db_path, &args.output_path);
    }

    let effect_id = args.effect_id();
    let mut orchestrator = SqliteTaskOrchestrator::new(
        open_database(&args.db_path, SqliteOpenOptions::default())
            .map_err(|error| format!("{error:?}"))?,
    )
    .with_lease_ttl_ms(RECOVERY_LEASE_TTL_MS);
    orchestrator
        .enqueue(OrchestratorTask::new(
            &args.task_id,
            ScheduleIntent::write(format!("scope:{}", args.output_path.display())),
            0,
        ))
        .map_err(|error| format!("{error:?}"))?;

    println!("[mvp] accepted task => task={} effect={}", args.task_id, effect_id);
    print_snapshot("after-enqueue", orchestrator.queue_snapshot());

    let claim = orchestrator
        .claim_next(&args.owner_id, 0)
        .map_err(|error| format!("{error:?}"))?
        .ok_or_else(|| format!("no claimable task for {}", args.task_id))?;
    println!(
        "[mvp] crash claim => task={} lease={} fence={}",
        claim.task.task_id,
        claim.lease.lease_id,
        claim.lease.fencing_token
    );

    let mut runtime = build_runtime(&claim, &effect_id, args.probe_mode.to_probe_mode());
    runtime
        .begin_execution(PreflightDecision::Permit)
        .map_err(|error| format!("{error:?}"))?;
    let executor = LocalSandboxExecutor::new();
    let (report, execution_summary) = executor
        .run_and_apply(
            &mut runtime,
            &sandbox_write_then_timeout_command(&args.output_path, args.content.as_bytes()),
        )
        .map_err(|error| format!("{error:?}"))?;
    println!(
        "[mvp] crash phase => worker={:?}, effect={:?}, timed_out={}",
        execution_summary.worker_state,
        execution_summary.effect_status,
        report.timed_out
    );

    let mut store = SqliteRuntimeStore::new(
        open_database(&args.db_path, SqliteOpenOptions::default())
            .map_err(|error| format!("{error:?}"))?,
    );
    store
        .persist_runtime(
            &runtime,
            format!("safeclaw-mvp:{}:post-exec", claim.lease.lease_id),
            "safeclaw-mvp-entry",
        )
        .map_err(|error| format!("{error:?}"))?;

    print_snapshot("after-seed", orchestrator.queue_snapshot());
    print_output_state(&args.output_path)?;
    println!("[mvp] db: {}", args.db_path.display());
    println!("[mvp] output: {}", args.output_path.display());
    println!("[mvp] owner: {}", args.owner_id);
    if args.probe_mode == ProbeModeCli::None {
        println!(
            "[mvp] next reconcile => cargo run -p safeclaw-sqlite --example safeclaw_mvp_entry -- reconcile --db \"{}\" --output \"{}\" --task-id {} --effect-id {} --decision executed",
            args.db_path.display(),
            args.output_path.display(),
            args.task_id,
            effect_id
        );
    } else {
        println!(
            "[mvp] next recover => cargo run -p safeclaw-sqlite --example safeclaw_mvp_entry -- recover --db \"{}\" --output \"{}\" --task-id {} --effect-id {}",
            args.db_path.display(),
            args.output_path.display(),
            args.task_id,
            effect_id
        );
        if args.content != DEFAULT_CONTENT {
            println!("[mvp] note => recover requires the same --content used during seed-crash");
        }
    }
    Ok(())
}

fn seed_hibernated_action(args: &CliArgs) -> Result<(), String> {
    ensure_parent_dir(&args.db_path)?;
    ensure_parent_dir(&args.output_path)?;
    if args.reset {
        reset_session_artifacts(&args.db_path, &args.output_path);
    }

    let effect_id = args.effect_id();
    let mut orchestrator = SqliteTaskOrchestrator::new(
        open_database(&args.db_path, SqliteOpenOptions::default())
            .map_err(|error| format!("{error:?}"))?,
    )
    .with_lease_ttl_ms(RECOVERY_LEASE_TTL_MS);
    orchestrator
        .enqueue(OrchestratorTask::new(
            &args.task_id,
            ScheduleIntent::write(format!("scope:{}", args.output_path.display())),
            0,
        ))
        .map_err(|error| format!("{error:?}"))?;

    println!("[mvp] accepted task => task={} effect={}", args.task_id, effect_id);
    print_snapshot("after-enqueue", orchestrator.queue_snapshot());

    let claim = orchestrator
        .claim_next(&args.owner_id, 0)
        .map_err(|error| format!("{error:?}"))?
        .ok_or_else(|| format!("no claimable task for {}", args.task_id))?;
    println!(
        "[mvp] hibernated claim => task={} lease={} fence={}",
        claim.task.task_id,
        claim.lease.lease_id,
        claim.lease.fencing_token
    );

    let mut runtime = build_runtime(&claim, &effect_id, args.probe_mode.to_probe_mode());
    let waiting = runtime
        .run_confirmation_checkpoint()
        .map_err(|error| format!("{error:?}"))?;
    println!(
        "[mvp] confirmation checkpoint => worker={:?} effect={:?}",
        waiting.worker_state,
        waiting.effect_status
    );
    let hibernated = runtime
        .resolve_confirmation(ConfirmationAction::Timeout)
        .map_err(|error| format!("{error:?}"))?;
    println!(
        "[mvp] hibernated result => worker={:?} effect={:?}",
        hibernated.worker_state,
        hibernated.effect_status
    );

    let mut store = SqliteRuntimeStore::new(
        open_database(&args.db_path, SqliteOpenOptions::default())
            .map_err(|error| format!("{error:?}"))?,
    );
    store
        .persist_runtime(
            &runtime,
            format!("safeclaw-mvp:{}:hibernated", claim.lease.lease_id),
            "safeclaw-mvp-entry",
        )
        .map_err(|error| format!("{error:?}"))?;

    print_snapshot("after-seed-hibernated", orchestrator.queue_snapshot());
    print_output_state(&args.output_path)?;
    println!("[mvp] db: {}", args.db_path.display());
    println!("[mvp] output: {}", args.output_path.display());
    println!("[mvp] owner: {}", args.owner_id);
    println!(
        "[mvp] next resume => cargo run -p safeclaw-sqlite --example safeclaw_mvp_entry -- resume --db \"{}\" --output \"{}\" --task-id {} --effect-id {}",
        args.db_path.display(),
        args.output_path.display(),
        args.task_id,
        effect_id
    );
    if args.content != DEFAULT_CONTENT {
        println!("[mvp] note => resume requires the same --content intended for the successful write");
    }
    Ok(())
}

fn recover_action(args: &CliArgs) -> Result<(), String> {
    let effect_id = args.effect_id();
    let mut loop_driver = SqliteSingleWorkerLoop::open(&args.db_path, SqliteOpenOptions::default())
        .map_err(|error| format!("{error:?}"))?
        .with_lease_ttl_ms(RECOVERY_LEASE_TTL_MS);
    loop_driver.filesystem_probe_mut().register_expected_blake3(
        effect_id.clone(),
        blake3::hash(args.content.as_bytes()).to_hex().to_string(),
    );

    let blocked = loop_driver
        .claim_and_probe_persisted_once(&args.owner_id, RECOVERY_BLOCKED_NOW_MS, &effect_id)
        .map_err(|error| format!("{error:?}"))?;
    println!("[mvp] recover blocked before expiry => {}", blocked.is_none());

    let recovered = loop_driver
        .claim_and_probe_persisted_once(&args.owner_id, RECOVERY_RECLAIM_NOW_MS, &effect_id)
        .map_err(|error| format!("{error:?}"))?
        .ok_or_else(|| format!("no recoverable runtime for task={} effect={effect_id}", args.task_id))?;
    println!("[mvp] recover result => {}", recovered.render_recovery_status_line());

    print_snapshot("after-recover", loop_driver.queue_snapshot());
    print_output_state(&args.output_path)?;
    println!("[mvp] db: {}", args.db_path.display());
    println!("[mvp] output: {}", args.output_path.display());
    println!("[mvp] owner: {}", args.owner_id);
    println!(
        "[mvp] next report => cargo run -p safeclaw-sqlite --example safeclaw_mvp_entry -- report --db \"{}\" --output \"{}\" --task-id {} --effect-id {}",
        args.db_path.display(),
        args.output_path.display(),
        args.task_id,
        effect_id
    );
    if args.content != DEFAULT_CONTENT {
        println!("[mvp] note => recover requires the same --content used during seed-crash");
    }
    Ok(())
}

fn reconcile_action(args: &CliArgs) -> Result<(), String> {
    let effect_id = args.effect_id();
    let decision = args
        .reconcile_decision
        .ok_or_else(|| format!("reconcile requires --decision <executed|not-executed>\n\n{}", usage_text()))?;
    let mut store = SqliteRuntimeStore::new(
        open_database(&args.db_path, SqliteOpenOptions::default())
            .map_err(|error| format!("{error:?}"))?,
    );
    let mut runtime = store
        .load_runtime(&args.task_id, &effect_id)
        .map_err(|error| format!("{error:?}"))?
        .ok_or_else(|| format!("no reconcileable runtime for task={} effect={effect_id}", args.task_id))?;
    let summary = runtime
        .reconcile_assumed(decision.to_runtime_decision())
        .map_err(|error| format!("{error:?}"))?;
    let event_id = format!("safeclaw-mvp:reconcile:{}:{}", args.task_id, unique_suffix()?);
    store
        .persist_runtime(&runtime, event_id, "safeclaw-mvp-entry")
        .map_err(|error| format!("{error:?}"))?;

    let mut orchestrator = SqliteTaskOrchestrator::new(
        open_database(&args.db_path, SqliteOpenOptions::default())
            .map_err(|error| format!("{error:?}"))?,
    );
    if let Some(active_lease) = orchestrator
        .queue_snapshot()
        .active_leases
        .into_iter()
        .find(|lease| lease.task_id == args.task_id)
    {
        orchestrator
            .complete(&args.task_id, &active_lease.lease_id, &active_lease.owner_id)
            .map_err(|error| format!("{error:?}"))?;
    }

    println!(
        "[mvp] reconcile result => decision={} worker={:?} effect={:?} attempts={} quarantined={}",
        decision.as_str(),
        summary.worker_state,
        summary.effect_status,
        summary.attempt_count,
        summary.quarantined_scopes.len()
    );

    let service = SqliteWorkerService::open(
        &args.db_path,
        SqliteOpenOptions::default(),
        args.owner_id.clone(),
    )
    .map_err(|error| format!("{error:?}"))?;
    print_runtime_status(&service, args, "reconcile", &args.task_id, &effect_id)?;
    println!(
        "[mvp] next report => cargo run -p safeclaw-sqlite --example safeclaw_mvp_entry -- report --db \"{}\" --output \"{}\" --task-id {} --effect-id {}",
        args.db_path.display(),
        args.output_path.display(),
        args.task_id,
        effect_id
    );
    Ok(())
}

fn seed_failed_action(args: &CliArgs) -> Result<(), String> {
    ensure_parent_dir(&args.db_path)?;
    ensure_parent_dir(&args.output_path)?;
    if args.reset {
        reset_session_artifacts(&args.db_path, &args.output_path);
    }

    let effect_id = args.effect_id();
    let mut loop_driver = SqliteSingleWorkerLoop::open(&args.db_path, SqliteOpenOptions::default())
        .map_err(|error| format!("{error:?}"))?
        .with_lease_ttl_ms(RECOVERY_LEASE_TTL_MS);
    loop_driver
        .enqueue_task(OrchestratorTask::new(
            &args.task_id,
            ScheduleIntent::write(format!("scope:{}", args.output_path.display())),
            0,
        ))
        .map_err(|error| format!("{error:?}"))?;

    println!("[mvp] accepted task => task={} effect={}", args.task_id, effect_id);
    print_snapshot("after-enqueue", loop_driver.queue_snapshot());

    let failed = loop_driver
        .claim_and_drive_once(&args.owner_id, 0, PreflightDecision::Permit, {
            let effect_id = effect_id.clone();
            move |claim| Ok((build_runtime(claim, &effect_id, args.probe_mode.to_probe_mode()), sandbox_fail_command()))
        })
        .map_err(|error| format!("{error:?}"))?
        .ok_or_else(|| format!("no claimable task for {}", args.task_id))?;
    println!("[mvp] first failure => {}", failed.render_final_status_line());

    print_snapshot("after-failed-attempt", loop_driver.queue_snapshot());
    print_output_state(&args.output_path)?;
    println!("[mvp] db: {}", args.db_path.display());
    println!("[mvp] output: {}", args.output_path.display());
    println!("[mvp] owner: {}", args.owner_id);
    println!(
        "[mvp] next retry => cargo run -p safeclaw-sqlite --example safeclaw_mvp_entry -- retry --db \"{}\" --output \"{}\" --task-id {} --effect-id {}",
        args.db_path.display(),
        args.output_path.display(),
        args.task_id,
        effect_id
    );
    if args.content != DEFAULT_CONTENT {
        println!("[mvp] note => retry requires the same --content intended for the successful write");
    }
    Ok(())
}

fn retry_action(args: &CliArgs) -> Result<(), String> {
    let effect_id = args.effect_id();

    let mut blocked_worker = SqliteSingleWorkerLoop::open(&args.db_path, SqliteOpenOptions::default())
        .map_err(|error| format!("{error:?}"))?
        .with_lease_ttl_ms(RECOVERY_LEASE_TTL_MS);
    let blocked = blocked_worker
        .claim_and_resume_once(&args.owner_id, RECOVERY_BLOCKED_NOW_MS, |_| unreachable!())
        .map_err(|error| format!("{error:?}"))?;
    println!("[mvp] retry blocked before expiry => {}", blocked.is_none());

    let mut retry_worker = SqliteSingleWorkerLoop::open(&args.db_path, SqliteOpenOptions::default())
        .map_err(|error| format!("{error:?}"))?
        .with_lease_ttl_ms(RECOVERY_LEASE_TTL_MS);
    let output_path = args.output_path.clone();
    let content = args.content.clone();
    let retried = retry_worker
        .claim_and_retry_failed_once(
            &args.owner_id,
            RECOVERY_RECLAIM_NOW_MS,
            &effect_id,
            PreflightDecision::Permit,
            move |_, _| Ok(sandbox_write_command(&output_path, content.as_bytes())),
        )
        .map_err(|error| format!("{error:?}"))?
        .ok_or_else(|| format!("no failed runtime ready for retry task={} effect={effect_id}", args.task_id))?;
    println!("[mvp] retry result => {}", retried.render_final_status_line());

    print_snapshot("after-retry", retry_worker.queue_snapshot());
    print_output_state(&args.output_path)?;
    println!("[mvp] db: {}", args.db_path.display());
    println!("[mvp] output: {}", args.output_path.display());
    println!("[mvp] owner: {}", args.owner_id);
    println!(
        "[mvp] next report => cargo run -p safeclaw-sqlite --example safeclaw_mvp_entry -- report --db \"{}\" --output \"{}\" --task-id {} --effect-id {}",
        args.db_path.display(),
        args.output_path.display(),
        args.task_id,
        effect_id
    );
    Ok(())
}

fn resume_action(args: &CliArgs) -> Result<(), String> {
    let effect_id = args.effect_id();

    let mut blocked_orchestrator = SqliteTaskOrchestrator::new(
        open_database(&args.db_path, SqliteOpenOptions::default())
            .map_err(|error| format!("{error:?}"))?,
    )
    .with_lease_ttl_ms(RECOVERY_LEASE_TTL_MS);
    let blocked = blocked_orchestrator
        .claim_next(&args.owner_id, RECOVERY_BLOCKED_NOW_MS)
        .map_err(|error| format!("{error:?}"))?;
    println!("[mvp] resume blocked before expiry => {}", blocked.is_none());

    let mut orchestrator = SqliteTaskOrchestrator::new(
        open_database(&args.db_path, SqliteOpenOptions::default())
            .map_err(|error| format!("{error:?}"))?,
    )
    .with_lease_ttl_ms(RECOVERY_LEASE_TTL_MS);
    let claim = orchestrator
        .claim_next(&args.owner_id, RECOVERY_RECLAIM_NOW_MS)
        .map_err(|error| format!("{error:?}"))?
        .ok_or_else(|| format!("no hibernated runtime ready for resume task={} effect={effect_id}", args.task_id))?;
    println!(
        "[mvp] resume claim => task={} lease={} fence={}",
        claim.task.task_id,
        claim.lease.lease_id,
        claim.lease.fencing_token
    );

    let mut store = SqliteRuntimeStore::new(
        open_database(&args.db_path, SqliteOpenOptions::default())
            .map_err(|error| format!("{error:?}"))?,
    );
    let mut runtime = store
        .load_runtime(&claim.task.task_id, &effect_id)
        .map_err(|error| format!("{error:?}"))?
        .ok_or_else(|| format!("no hibernated runtime ready for resume task={} effect={effect_id}", args.task_id))?;

    let resumed = runtime
        .resolve_hibernation(HibernationAction::Resume(PreflightDecision::Permit))
        .map_err(|error| format!("{error:?}"))?;
    println!(
        "[mvp] resume phase => worker={:?} effect={:?}",
        resumed.worker_state,
        resumed.effect_status
    );
    store
        .persist_runtime(
            &runtime,
            format!("safeclaw-mvp:{}:pre-resume", claim.lease.lease_id),
            "safeclaw-mvp-entry",
        )
        .map_err(|error| format!("{error:?}"))?;

    let executor = LocalSandboxExecutor::new();
    let (report, final_summary) = executor
        .run_and_apply(
            &mut runtime,
            &sandbox_write_command(&args.output_path, args.content.as_bytes()),
        )
        .map_err(|error| format!("{error:?}"))?;
    println!(
        "[mvp] resume result => worker={:?} effect={:?} exit={:?} timed_out={}",
        final_summary.worker_state,
        final_summary.effect_status,
        report.exit_code,
        report.timed_out
    );
    store
        .persist_runtime(
            &runtime,
            format!("safeclaw-mvp:{}:post-resume", claim.lease.lease_id),
            "safeclaw-mvp-entry",
        )
        .map_err(|error| format!("{error:?}"))?;

    if final_summary.worker_state == WorkerState::Succeeded {
        orchestrator
            .complete(&claim.task.task_id, &claim.lease.lease_id, &claim.lease.owner_id)
            .map_err(|error| format!("{error:?}"))?;
    }

    print_snapshot("after-resume", orchestrator.queue_snapshot());
    print_output_state(&args.output_path)?;
    println!("[mvp] db: {}", args.db_path.display());
    println!("[mvp] output: {}", args.output_path.display());
    println!("[mvp] owner: {}", args.owner_id);
    println!(
        "[mvp] next report => cargo run -p safeclaw-sqlite --example safeclaw_mvp_entry -- report --db \"{}\" --output \"{}\" --task-id {} --effect-id {}",
        args.db_path.display(),
        args.output_path.display(),
        args.task_id,
        effect_id
    );
    Ok(())
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum CliAction {
    Run,
    Report,
    Status,
    SeedCrash,
    SeedHibernated,
    Recover,
    SeedFailed,
    Retry,
    Resume,
    Reconcile,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum ProbeModeCli {
    Auto,
    None,
}

impl ProbeModeCli {
    fn to_probe_mode(self) -> ProbeMode {
        match self {
            Self::Auto => ProbeMode::Auto,
            Self::None => ProbeMode::None,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum ReconcileCliDecision {
    Executed,
    NotExecuted,
}

impl ReconcileCliDecision {
    fn as_str(self) -> &'static str {
        match self {
            Self::Executed => "executed",
            Self::NotExecuted => "not-executed",
        }
    }

    fn to_runtime_decision(self) -> ReconcileDecision {
        match self {
            Self::Executed => ReconcileDecision::Success,
            Self::NotExecuted => ReconcileDecision::Failure,
        }
    }
}

#[derive(Clone, Debug)]
struct CliArgs {
    action: CliAction,
    db_path: PathBuf,
    output_path: PathBuf,
    content: String,
    task_id: String,
    owner_id: String,
    effect_id: Option<String>,
    reset: bool,
    probe_mode: ProbeModeCli,
    reconcile_decision: Option<ReconcileCliDecision>,
}

impl CliArgs {
    fn parse(raw_args: Vec<String>) -> Result<Self, String> {
        let workspace = env::current_dir().map_err(|error| error.to_string())?;
        let unique = unique_suffix()?;
        let default_root = workspace.join("target").join(format!("safeclaw-mvp-entry-{unique}"));
        let default_output = default_root.join("output.txt");
        let default_db = default_root.join("session.db");

        let mut action = CliAction::Run;
        let mut action_set = false;
        let mut db_path = None;
        let mut output_path = None;
        let mut content = String::from(DEFAULT_CONTENT);
        let mut task_id = None;
        let mut owner_id = String::from(DEFAULT_OWNER_ID);
        let mut effect_id = None;
        let mut reset = false;
        let mut probe_mode = ProbeModeCli::Auto;
        let mut reconcile_decision = None;

        let mut args = raw_args.into_iter();
        while let Some(arg) = args.next() {
            match arg.as_str() {
                "run" if !action_set => {
                    action = CliAction::Run;
                    action_set = true;
                }
                "report" if !action_set => {
                    action = CliAction::Report;
                    action_set = true;
                }
                "status" if !action_set => {
                    action = CliAction::Status;
                    action_set = true;
                }
                "seed-crash" if !action_set => {
                    action = CliAction::SeedCrash;
                    action_set = true;
                }
                "seed-hibernated" if !action_set => {
                    action = CliAction::SeedHibernated;
                    action_set = true;
                }
                "recover" if !action_set => {
                    action = CliAction::Recover;
                    action_set = true;
                }
                "seed-failed" if !action_set => {
                    action = CliAction::SeedFailed;
                    action_set = true;
                }
                "retry" if !action_set => {
                    action = CliAction::Retry;
                    action_set = true;
                }
                "resume" if !action_set => {
                    action = CliAction::Resume;
                    action_set = true;
                }
                "reconcile" if !action_set => {
                    action = CliAction::Reconcile;
                    action_set = true;
                }
                "--db" => db_path = Some(PathBuf::from(next_value(&mut args, "--db")?)),
                "--output" => {
                    output_path = Some(PathBuf::from(next_value(&mut args, "--output")?))
                }
                "--content" => content = next_value(&mut args, "--content")?,
                "--task-id" => task_id = Some(next_value(&mut args, "--task-id")?),
                "--owner-id" => owner_id = next_value(&mut args, "--owner-id")?,
                "--effect-id" => effect_id = Some(next_value(&mut args, "--effect-id")?),
                "--probe-mode" => probe_mode = parse_probe_mode(&next_value(&mut args, "--probe-mode")?)?,
                "--decision" => reconcile_decision = Some(parse_reconcile_decision(&next_value(&mut args, "--decision")?)?),
                "--reset" => reset = true,
                _ => return Err(format!("unknown argument: {arg}\n\n{}", usage_text())),
            }
        }

        let (db_path, output_path, task_id) = match action {
            CliAction::Run | CliAction::SeedCrash | CliAction::SeedHibernated | CliAction::SeedFailed => {
                let output_path = output_path.unwrap_or(default_output);
                let db_path = db_path.unwrap_or(default_db);
                let task_id = task_id.unwrap_or(format!("task-safeclaw-mvp-{unique}"));
                (db_path, output_path, task_id)
            }
            CliAction::Report | CliAction::Recover | CliAction::Retry | CliAction::Resume | CliAction::Reconcile => {
                let db_path = db_path.ok_or_else(|| {
                    format!("{} requires --db\n\n{}", action_name(action), usage_text())
                })?;
                let task_id = task_id.ok_or_else(|| {
                    format!("{} requires --task-id\n\n{}", action_name(action), usage_text())
                })?;
                let output_path = output_path.unwrap_or_else(|| {
                    db_path
                        .parent()
                        .unwrap_or_else(|| Path::new("."))
                        .join("output.txt")
                });
                (db_path, output_path, task_id)
            }
            CliAction::Status => {
                let db_path = db_path.ok_or_else(|| {
                    format!("{} requires --db\n\n{}", action_name(action), usage_text())
                })?;
                let output_path = output_path.unwrap_or_else(|| {
                    db_path
                        .parent()
                        .unwrap_or_else(|| Path::new("."))
                        .join("output.txt")
                });
                (db_path, output_path, task_id.unwrap_or_default())
            }
        };

        if action == CliAction::Reconcile && reconcile_decision.is_none() {
            return Err(format!("reconcile requires --decision <executed|not-executed>\n\n{}", usage_text()));
        }

        Ok(Self {
            action,
            db_path,
            output_path,
            content,
            task_id,
            owner_id,
            effect_id,
            reset,
            probe_mode,
            reconcile_decision,
        })
    }

    fn effect_id(&self) -> String {
        self.effect_id
            .clone()
            .unwrap_or_else(|| format!("effect-{}", self.task_id))
    }
}

fn action_name(action: CliAction) -> &'static str {
    match action {
        CliAction::Run => "run",
        CliAction::Report => "report",
        CliAction::Status => "status",
        CliAction::SeedCrash => "seed-crash",
        CliAction::SeedHibernated => "seed-hibernated",
        CliAction::Recover => "recover",
        CliAction::SeedFailed => "seed-failed",
        CliAction::Retry => "retry",
        CliAction::Resume => "resume",
        CliAction::Reconcile => "reconcile",
    }
}

fn next_value(
    args: &mut impl Iterator<Item = String>,
    flag: &str,
) -> Result<String, String> {
    args.next()
        .ok_or_else(|| format!("missing value for {flag}\n\n{}", usage_text()))
}

fn parse_probe_mode(value: &str) -> Result<ProbeModeCli, String> {
    match value {
        "auto" => Ok(ProbeModeCli::Auto),
        "none" => Ok(ProbeModeCli::None),
        _ => Err(format!("unsupported --probe-mode value: {value}\n\n{}", usage_text())),
    }
}

fn parse_reconcile_decision(value: &str) -> Result<ReconcileCliDecision, String> {
    match value {
        "executed" => Ok(ReconcileCliDecision::Executed),
        "not-executed" => Ok(ReconcileCliDecision::NotExecuted),
        _ => Err(format!("unsupported --decision value: {value}\n\n{}", usage_text())),
    }
}
fn usage_text() -> &'static str {
    "usage: cargo run -p safeclaw-sqlite --example safeclaw_mvp_entry -- [run [--reset] [--db <path>] [--output <path>] [--content <text>] [--task-id <id>] [--owner-id <id>] [--effect-id <id>] | report --db <path> --task-id <id> [--output <path>] [--owner-id <id>] [--effect-id <id>] | status --db <path> [--task-id <id>] [--output <path>] [--owner-id <id>] [--effect-id <id>] | seed-crash [--reset] [--probe-mode <auto|none>] [--db <path>] [--output <path>] [--content <text>] [--task-id <id>] [--owner-id <id>] [--effect-id <id>] | seed-hibernated [--reset] [--probe-mode <auto|none>] [--db <path>] [--output <path>] [--content <text>] [--task-id <id>] [--owner-id <id>] [--effect-id <id>] | recover --db <path> --task-id <id> [--output <path>] [--content <text>] [--owner-id <id>] [--effect-id <id>] | seed-failed [--reset] [--db <path>] [--output <path>] [--content <text>] [--task-id <id>] [--owner-id <id>] [--effect-id <id>] | retry --db <path> --task-id <id> [--output <path>] [--content <text>] [--owner-id <id>] [--effect-id <id>] | resume --db <path> --task-id <id> [--output <path>] [--content <text>] [--owner-id <id>] [--effect-id <id>] | reconcile --db <path> --task-id <id> --decision <executed|not-executed> [--output <path>] [--owner-id <id>] [--effect-id <id>]]"
}

fn print_usage() {
    println!("{}", usage_text());
}

fn print_runtime_status(
    service: &SqliteWorkerService,
    args: &CliArgs,
    label: &str,
    task_id: &str,
    effect_id: &str,
) -> Result<(), String> {
    println!("[mvp] {label} target => task={task_id} effect={effect_id}");

    let governance = service
        .governance_view(task_id, effect_id)
        .map_err(|error| format!("{error:?}"))?
        .ok_or_else(|| format!("missing governance view for task={task_id} effect={effect_id}"))?;
    println!(
        "[mvp] governance view => disposition={:?} worker={:?} effect={:?} attempts={}",
        governance.disposition,
        governance.worker_state,
        governance.effect_status,
        governance.attempt_count
    );

    let runtime_store = SqliteRuntimeStore::new(
        open_database(&args.db_path, SqliteOpenOptions::default())
            .map_err(|error| format!("{error:?}"))?,
    );
    let runtime = runtime_store
        .load_runtime(task_id, effect_id)
        .map_err(|error| format!("{error:?}"))?
        .ok_or_else(|| format!("missing runtime for task={task_id} effect={effect_id}"))?;
    print_readable_operation_bill(&runtime);

    let snapshot = service
        .diagnostic_snapshot(task_id, effect_id)
        .map_err(|error| format!("{error:?}"))?
        .ok_or_else(|| format!("missing diagnostic snapshot for task={task_id} effect={effect_id}"))?;
    println!("[mvp] diagnostic => {}", snapshot.render_line());
    print_snapshot(label, service.queue_snapshot());
    print_output_state(&args.output_path)?;
    println!("[mvp] db: {}", args.db_path.display());
    println!("[mvp] output: {}", args.output_path.display());
    println!("[mvp] owner: {}", args.owner_id);
    Ok(())
}

fn print_readable_operation_bill(runtime: &InMemoryTaskRuntime) {
    let tracked_operation_count = 1 + runtime.compensation_effects.len();
    println!("[mvp] 操作账单 => 已记录 {tracked_operation_count} 个操作");
    println!(
        "[mvp] 账单条目 => {} {}（{}）",
        render_effect_action_label(runtime.effect.action),
        render_effect_target(&runtime.effect.target),
        render_effect_reversibility_label(runtime.effect.reversibility)
    );
    println!(
        "[mvp] 账单撤销能力 => {}",
        render_effect_undo_hint(runtime.effect.reversibility)
    );
}

fn render_effect_action_label(action: EffectAction) -> &'static str {
    match action {
        EffectAction::FileRead => "读取文件",
        EffectAction::FileWrite => "写入文件",
        EffectAction::FileDelete => "删除文件",
        EffectAction::FileMove => "移动文件",
        EffectAction::DirCreate => "创建目录",
        EffectAction::DirDelete => "删除目录",
        EffectAction::NetworkRequest => "发起网络请求",
        EffectAction::SystemExec => "执行系统命令",
        EffectAction::ClipboardWrite => "写入剪贴板",
        EffectAction::ConfigChange => "修改配置",
        EffectAction::PluginInstall => "安装插件",
        EffectAction::PluginUninstall => "卸载插件",
    }
}

fn render_effect_target(target: &str) -> &str {
    target.strip_prefix("scope:").unwrap_or(target)
}

fn render_effect_reversibility_label(reversibility: EffectReversibility) -> &'static str {
    match reversibility {
        EffectReversibility::Rollbackable => "可撤销",
        EffectReversibility::Compensatable => "可补偿",
        EffectReversibility::Irreversible => "不可撤销",
    }
}

fn render_effect_undo_hint(reversibility: EffectReversibility) -> &'static str {
    match reversibility {
        EffectReversibility::Rollbackable => "可撤销，但用户级 undo 入口待接入",
        EffectReversibility::Compensatable => "可补偿，但用户级 undo 入口待接入",
        EffectReversibility::Irreversible => "当前操作不可撤销",
    }
}

fn resolve_status_target(args: &CliArgs) -> Result<(String, String), String> {
    let connection = open_database(&args.db_path, SqliteOpenOptions::default())
        .map_err(|error| format!("{error:?}"))?;
    let task_id = if args.task_id.is_empty() {
        load_latest_task_id(&connection)?
            .ok_or_else(|| format!("no persisted task snapshots in {}", args.db_path.display()))?
    } else {
        args.task_id.clone()
    };
    let effect_id = if let Some(effect_id) = args.effect_id.clone() {
        effect_id
    } else {
        load_latest_effect_id(&connection, &task_id)?
            .unwrap_or_else(|| format!("effect-{task_id}"))
    };
    Ok((task_id, effect_id))
}

fn load_latest_task_id(connection: &Connection) -> Result<Option<String>, String> {
    connection
        .query_row(
            "SELECT task_id FROM task_snapshots ORDER BY updated_at DESC, task_id DESC LIMIT 1",
            [],
            |row| row.get(0),
        )
        .optional()
        .map_err(|error| error.to_string())
}

fn load_latest_effect_id(connection: &Connection, task_id: &str) -> Result<Option<String>, String> {
    connection
        .query_row(
            "SELECT effect_id FROM effects WHERE task_id = ?1 ORDER BY rowid DESC LIMIT 1",
            [task_id],
            |row| row.get(0),
        )
        .optional()
        .map_err(|error| error.to_string())
}

fn unique_suffix() -> Result<String, String> {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|error| error.to_string())?
        .as_nanos();
    Ok(format!("{}-{nanos}", process::id()))
}

fn ensure_parent_dir(path: &Path) -> Result<(), String> {
    if let Some(parent) = path.parent().filter(|parent| !parent.as_os_str().is_empty()) {
        fs::create_dir_all(parent).map_err(|error| error.to_string())?;
    }
    Ok(())
}

fn reset_session_artifacts(db_path: &Path, output_path: &Path) {
    let _ = fs::remove_file(output_path);
    for suffix in ["", "-wal", "-shm"] {
        let candidate = if suffix.is_empty() {
            db_path.to_path_buf()
        } else {
            PathBuf::from(format!("{}{}", db_path.display(), suffix))
        };
        let _ = fs::remove_file(candidate);
    }
}

fn build_runtime(claim: &OrchestratorClaim, effect_id: &str, probe_mode: ProbeMode) -> InMemoryTaskRuntime {
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
        probe_mode,
    );
    InMemoryTaskRuntime::new(effect)
}

fn print_snapshot(label: &str, snapshot: OrchestratorSnapshot) {
    println!(
        "[mvp] snapshot {label} => queued={}, active={}, completed={}",
        snapshot.queued_tasks.len(),
        snapshot.active_leases.len(),
        snapshot.completed_task_ids.len(),
    );
}

fn print_output_state(output_path: &Path) -> Result<(), String> {
    let output_exists = output_path.exists();
    println!("[mvp] output exists => {output_exists}");
    if output_exists {
        let rendered = fs::read_to_string(output_path).map_err(|error| error.to_string())?;
        println!(
            "[mvp] output content => {}",
            rendered.replace('\r', "\\r").replace('\n', "\\n")
        );
    }
    Ok(())
}

fn sandbox_fail_command() -> SandboxCommand {
    if cfg!(windows) {
        SandboxCommand::new("powershell", ["-Command", "Write-Error 'boom'; exit 7"], 5_000)
    } else {
        SandboxCommand::new("sh", ["-c", "echo boom 1>&2; exit 7"], 5_000)
    }
}

fn sandbox_write_command(output_path: &Path, output_bytes: &[u8]) -> SandboxCommand {
    let bytes_literal = output_bytes
        .iter()
        .map(u8::to_string)
        .collect::<Vec<_>>()
        .join(", ");
    if cfg!(windows) {
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
            "python3",
            [
                "-c",
                &format!(
                    "from pathlib import Path; Path(r'''{}''').write_bytes(bytes([{}]))",
                    output_path.display(),
                    bytes_literal
                ),
            ],
            5_000,
        )
    }
}

fn sandbox_write_then_timeout_command(output_path: &Path, output_bytes: &[u8]) -> SandboxCommand {
    let bytes_literal = output_bytes
        .iter()
        .map(u8::to_string)
        .collect::<Vec<_>>()
        .join(", ");
    if cfg!(windows) {
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
        SandboxCommand::new(
            "python3",
            [
                "-c",
                &format!(
                    "from pathlib import Path; import time; Path(r'''{}''').write_bytes(bytes([{}])); time.sleep(1)",
                    output_path.display(),
                    bytes_literal
                ),
            ],
            500,
        )
    }
}
