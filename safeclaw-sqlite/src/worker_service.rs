use std::path::Path;

use crate::{
    FileSystemProbeAdapter, NetworkProbeAdapter, RuntimeGovernanceView, SandboxCommand,
    SqliteAdapterError, SqliteOpenOptions, SqliteSingleWorkerLoop,
    WorkerLoopDispatchOutcome, WorkerLoopError,
};
use safeclaw_core::{
    effect_ledger::EffectAttempt,
    scheduler::{OrchestratorClaim, OrchestratorSnapshot, OrchestratorTask},
    state_engine::StateEvent,
    InMemoryTaskRuntime, PreflightDecision,
};

#[derive(Clone, Debug, Default)]
pub struct WorkerServiceRunReport {
    pub poll_count: usize,
    pub consecutive_idle_polls: usize,
    pub outcomes: Vec<WorkerLoopDispatchOutcome>,
}

impl WorkerServiceRunReport {
    pub fn executed_count(&self) -> usize {
        self.outcomes
            .iter()
            .filter(|outcome| matches!(outcome, WorkerLoopDispatchOutcome::Executed(_)))
            .count()
    }

    pub fn probed_count(&self) -> usize {
        self.outcomes
            .iter()
            .filter(|outcome| matches!(outcome, WorkerLoopDispatchOutcome::Probed(_)))
            .count()
    }

    pub fn parked_count(&self) -> usize {
        self.outcomes
            .iter()
            .filter(|outcome| matches!(outcome, WorkerLoopDispatchOutcome::Parked(_)))
            .count()
    }
}

pub struct SqliteWorkerService {
    worker_loop: SqliteSingleWorkerLoop,
    owner_id: String,
    poll_interval_ms: u64,
}

impl SqliteWorkerService {
    pub fn open(
        path: impl AsRef<Path>,
        options: SqliteOpenOptions,
        owner_id: impl Into<String>,
    ) -> Result<Self, SqliteAdapterError> {
        Ok(Self::new(SqliteSingleWorkerLoop::open(path, options)?, owner_id))
    }

    pub fn new(worker_loop: SqliteSingleWorkerLoop, owner_id: impl Into<String>) -> Self {
        Self {
            worker_loop,
            owner_id: owner_id.into(),
            poll_interval_ms: 10,
        }
    }

    pub fn with_lease_ttl_ms(mut self, lease_ttl_ms: u64) -> Self {
        self.worker_loop = self.worker_loop.with_lease_ttl_ms(lease_ttl_ms);
        self
    }

    pub fn with_poll_interval_ms(mut self, poll_interval_ms: u64) -> Self {
        self.poll_interval_ms = poll_interval_ms;
        self
    }

    pub fn enqueue_task(&mut self, task: OrchestratorTask) -> Result<(), WorkerLoopError> {
        self.worker_loop.enqueue_task(task)
    }

    pub fn queue_snapshot(&self) -> OrchestratorSnapshot {
        self.worker_loop.queue_snapshot()
    }

    pub fn governance_view(
        &self,
        task_id: &str,
        effect_id: &str,
    ) -> Result<Option<RuntimeGovernanceView>, WorkerLoopError> {
        self.worker_loop.governance_view(task_id, effect_id)
    }

    pub fn list_attempts(&self, effect_id: &str) -> Result<Vec<EffectAttempt>, WorkerLoopError> {
        self.worker_loop.list_attempts(effect_id)
    }

    pub fn list_state_events(&self, task_id: &str) -> Result<Vec<StateEvent>, WorkerLoopError> {
        self.worker_loop.list_state_events(task_id)
    }

    pub fn filesystem_probe_mut(&mut self) -> &mut FileSystemProbeAdapter {
        self.worker_loop.filesystem_probe_mut()
    }

    pub fn network_probe_mut(&mut self) -> &mut NetworkProbeAdapter {
        self.worker_loop.network_probe_mut()
    }

    pub fn run_dispatch_until_idle<I, F, P>(
        &mut self,
        start_now_ms: u64,
        max_idle_polls: usize,
        preflight: PreflightDecision,
        mut resolve_effect_id: I,
        mut build_fresh: F,
        mut build_persisted_command: P,
    ) -> Result<WorkerServiceRunReport, WorkerLoopError>
    where
        I: FnMut(&OrchestratorClaim) -> Result<String, WorkerLoopError>,
        F: FnMut(&OrchestratorClaim) -> Result<(InMemoryTaskRuntime, SandboxCommand), WorkerLoopError>,
        P: FnMut(&OrchestratorClaim, &InMemoryTaskRuntime) -> Result<SandboxCommand, WorkerLoopError>,
    {
        let mut report = WorkerServiceRunReport::default();
        if max_idle_polls == 0 {
            return Ok(report);
        }

        let mut now_ms = start_now_ms;
        loop {
            report.poll_count += 1;
            let mut poll_outcomes = self.worker_loop.claim_and_dispatch_until_empty(
                &self.owner_id,
                now_ms,
                preflight,
                |claim| resolve_effect_id(claim),
                |claim| build_fresh(claim),
                |claim, runtime| build_persisted_command(claim, runtime),
            )?;

            if poll_outcomes.is_empty() {
                report.consecutive_idle_polls += 1;
                if report.consecutive_idle_polls >= max_idle_polls {
                    return Ok(report);
                }
            } else {
                report.consecutive_idle_polls = 0;
                report.outcomes.append(&mut poll_outcomes);
            }

            now_ms = now_ms.saturating_add(self.poll_interval_ms);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::SqliteWorkerService;
    use crate::{
        RuntimeGovernanceDisposition, SandboxCommand, SqliteOpenOptions,
    };
    use safeclaw_core::{
        effect_ledger::{
            AttemptResultStatus, EffectAction, EffectActor, EffectRecord,
            EffectReversibility, EffectStatus, EffectTier, ProbeMode,
        },
        scheduler::OrchestratorTask,
        worker_lifecycle::WorkerState,
        InMemoryTaskRuntime, PreflightDecision, ScheduleIntent,
    };
    use std::{
        env, fs,
        path::{Path, PathBuf},
        process,
        time::{SystemTime, UNIX_EPOCH},
    };

    struct TempDatabase {
        path: PathBuf,
    }

    impl TempDatabase {
        fn new(label: &str) -> Self {
            let unique = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .expect("system clock must be after epoch")
                .as_nanos();
            let path = env::temp_dir().join(format!(
                "safeclaw-worker-service-{label}-{}-{unique}.db",
                process::id()
            ));
            Self { path }
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

    #[test]
    fn worker_service_returns_idle_report_when_queue_is_empty() {
        let temp = TempDatabase::new("idle");
        let mut service = SqliteWorkerService::open(
            temp.path(),
            SqliteOpenOptions::default(),
            "worker-service-a",
        )
        .unwrap()
        .with_poll_interval_ms(5);

        let report = service
            .run_dispatch_until_idle(
                100,
                2,
                PreflightDecision::Permit,
                |_| unreachable!(),
                |_| unreachable!(),
                |_, _| unreachable!(),
            )
            .unwrap();

        assert_eq!(report.poll_count, 2);
        assert_eq!(report.consecutive_idle_polls, 2);
        assert!(report.outcomes.is_empty());
        assert!(service.queue_snapshot().active_leases.is_empty());
        assert!(service.queue_snapshot().completed_task_ids.is_empty());
    }

    #[test]
    fn worker_service_parks_confirmation_task_and_exposes_governance_view() {
        let temp = TempDatabase::new("confirmation");
        let mut service = SqliteWorkerService::open(
            temp.path(),
            SqliteOpenOptions::default(),
            "worker-service-a",
        )
        .unwrap()
        .with_lease_ttl_ms(25)
        .with_poll_interval_ms(5);
        service
            .enqueue_task(OrchestratorTask::new(
                "task-worker-service-confirmation",
                ScheduleIntent::write("scope:worker-service-confirmation"),
                0,
            ))
            .unwrap();

        let report = service
            .run_dispatch_until_idle(
                0,
                2,
                PreflightDecision::NeedsConfirmation,
                |claim| Ok(format!("effect-{}", claim.task.task_id)),
                |claim| {
                    let effect_id = format!("effect-{}", claim.task.task_id);
                    let effect = EffectRecord::new(
                        effect_id,
                        claim.task.task_id.clone(),
                        "trace-worker-service-confirmation",
                        "intent-worker-service-confirmation",
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
            .unwrap();

        assert_eq!(report.poll_count, 3);
        assert_eq!(report.consecutive_idle_polls, 2);
        assert_eq!(report.outcomes.len(), 1);
        assert_eq!(report.executed_count(), 0);
        assert_eq!(report.probed_count(), 0);
        assert_eq!(report.parked_count(), 1);

        let view = service
            .governance_view(
                "task-worker-service-confirmation",
                "effect-task-worker-service-confirmation",
            )
            .unwrap()
            .expect("governance view must exist after parked confirmation");
        assert_eq!(view.worker_state, WorkerState::AwaitingConfirmation);
        assert_eq!(view.effect_status, EffectStatus::Prepared);
        assert_eq!(view.disposition, RuntimeGovernanceDisposition::QueueForConfirmation);

        let snapshot = service.queue_snapshot();
        assert_eq!(snapshot.active_leases.len(), 1);
        assert!(snapshot.completed_task_ids.is_empty());
    }

    #[test]
    fn worker_service_exposes_attempt_history_for_executed_task() {
        let temp = TempDatabase::new("attempt-history");
        let mut service = SqliteWorkerService::open(
            temp.path(),
            SqliteOpenOptions::default(),
            "worker-service-a",
        )
        .unwrap()
        .with_lease_ttl_ms(25)
        .with_poll_interval_ms(5);
        service
            .enqueue_task(OrchestratorTask::new(
                "task-worker-service-attempt-history",
                ScheduleIntent::write("scope:worker-service-attempt-history"),
                0,
            ))
            .unwrap();

        let report = service
            .run_dispatch_until_idle(
                0,
                1,
                PreflightDecision::Permit,
                |claim| Ok(format!("effect-{}", claim.task.task_id)),
                |claim| {
                    let effect_id = format!("effect-{}", claim.task.task_id);
                    let effect = EffectRecord::new(
                        effect_id,
                        claim.task.task_id.clone(),
                        "trace-worker-service-attempt-history",
                        "intent-worker-service-attempt-history",
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
            .unwrap();

        assert_eq!(report.executed_count(), 1);
        assert_eq!(report.probed_count(), 0);
        assert_eq!(report.parked_count(), 0);

        let attempts = service
            .list_attempts("effect-task-worker-service-attempt-history")
            .unwrap();
        assert_eq!(attempts.len(), 1);
        assert_eq!(attempts[0].attempt_seq, 1);
        assert_eq!(attempts[0].result_status, Some(AttemptResultStatus::Success));
    }

    #[test]
    fn worker_service_exposes_state_timeline_for_executed_task() {
        let temp = TempDatabase::new("state-timeline");
        let mut service = SqliteWorkerService::open(
            temp.path(),
            SqliteOpenOptions::default(),
            "worker-service-a",
        )
        .unwrap()
        .with_lease_ttl_ms(25)
        .with_poll_interval_ms(5);
        service
            .enqueue_task(OrchestratorTask::new(
                "task-worker-service-state-timeline",
                ScheduleIntent::write("scope:worker-service-state-timeline"),
                0,
            ))
            .unwrap();

        let report = service
            .run_dispatch_until_idle(
                0,
                1,
                PreflightDecision::Permit,
                |claim| Ok(format!("effect-{}", claim.task.task_id)),
                |claim| {
                    let effect_id = format!("effect-{}", claim.task.task_id);
                    let effect = EffectRecord::new(
                        effect_id,
                        claim.task.task_id.clone(),
                        "trace-worker-service-state-timeline",
                        "intent-worker-service-state-timeline",
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
            .unwrap();

        assert_eq!(report.executed_count(), 1);

        let events = service
            .list_state_events("task-worker-service-state-timeline")
            .unwrap();
        assert_eq!(events.len(), 2);
        assert_eq!(events[0].task_id, "task-worker-service-state-timeline");
        assert_eq!(events[0].worker_state, WorkerState::Executing);
        assert_eq!(events[1].worker_state, WorkerState::Succeeded);
        assert_eq!(events[1].effect_status, EffectStatus::Executed);
        assert_eq!(events[0].triggered_by, "worker-loop");
        assert_eq!(events[1].triggered_by, "worker-loop");
    }

    fn sandbox_success_command() -> SandboxCommand {
        if cfg!(windows) {
            SandboxCommand::new("powershell", ["-Command", "Write-Output 'ok'"], 5_000)
        } else {
            SandboxCommand::new("sh", ["-c", "printf '%s' ok"], 5_000)
        }
    }
}
