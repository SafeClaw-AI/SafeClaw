#![forbid(unsafe_code)]

pub mod effect_ledger;
pub mod protocol;
pub mod spec_map;
pub mod task_concurrency;
pub mod worker_lifecycle;

use effect_ledger::{
    AttemptResultStatus, AttemptWriteError, EffectAttempt, EffectRecord, EffectStatus,
    EffectTransitionError, LeaseError, RecoveryLease,
};
use task_concurrency::{
    runtime_state_from_effect, scope_quarantine_trigger, write_scope_decision,
    GuardBlockReason, GuardDecision, ScopeClaim,
};
use worker_lifecycle::{transition_for, WorkerEvent, WorkerState};

pub use protocol::protocol_version;

pub const DEFAULT_LEASE_TTL_MS: u64 = 30_000;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum PreflightDecision {
    Permit,
    NeedsConfirmation,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ExecutionDisposition {
    Commit,
    Crash,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ReconcileDecision {
    Success,
    Failure,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RunSummary {
    pub worker_state: WorkerState,
    pub effect_status: EffectStatus,
    pub attempt_count: usize,
    pub compensation_count: usize,
    pub quarantined_scopes: Vec<String>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum RuntimeError {
    InvalidWorkerTransition {
        state: WorkerState,
        event: WorkerEvent,
    },
    EffectTransition(EffectTransitionError),
    AttemptWrite(AttemptWriteError),
    Lease(LeaseError),
    GuardBlocked(GuardBlockReason),
    MissingRecoveryLease,
    MissingAttempt,
    ReconcileUnavailable {
        state: WorkerState,
        effect_status: EffectStatus,
    },
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct InMemoryTaskRuntime {
    pub worker_state: WorkerState,
    pub effect: EffectRecord,
    pub attempts: Vec<EffectAttempt>,
    pub compensation_effects: Vec<EffectRecord>,
    pub active_claims: Vec<ScopeClaim>,
    pub quarantined_scopes: Vec<String>,
    pub recovery_lease: Option<RecoveryLease>,
    next_fencing_token: u64,
    clock_ms: u64,
}

impl InMemoryTaskRuntime {
    pub fn new(effect: EffectRecord) -> Self {
        Self {
            worker_state: WorkerState::Created,
            effect,
            attempts: Vec::new(),
            compensation_effects: Vec::new(),
            active_claims: Vec::new(),
            quarantined_scopes: Vec::new(),
            recovery_lease: None,
            next_fencing_token: 0,
            clock_ms: 0,
        }
    }

    pub fn run_minimal_flow(
        &mut self,
        preflight: PreflightDecision,
        execution: ExecutionDisposition,
    ) -> Result<RunSummary, RuntimeError> {
        self.apply_worker_event(WorkerEvent::TaskAccepted)?;
        self.apply_preflight(preflight)?;

        if self.worker_state == WorkerState::Executing {
            self.execute_effect(execution)?;
        }

        Ok(self.summary())
    }

    pub fn run_persist_error_recovery(
        &mut self,
        preflight: PreflightDecision,
    ) -> Result<RunSummary, RuntimeError> {
        self.apply_worker_event(WorkerEvent::TaskAccepted)?;
        self.apply_preflight(preflight)?;

        if self.worker_state == WorkerState::Executing {
            self.ensure_scope_write_allowed()?;
            self.active_claims
                .push(ScopeClaim::write(self.effect.target.clone()));
            self.ensure_recovery_lease("worker")?;
            self.execute_effect_to_commit_ready()?;
            self.apply_worker_event(WorkerEvent::PersistError)?;
            self.recover_failed_commit()?;
            self.active_claims.clear();
        }

        Ok(self.summary())
    }

    pub fn advance_clock(&mut self, delta_ms: u64) {
        self.clock_ms += delta_ms;
    }

    pub fn current_recovery_lease(&self) -> Option<&RecoveryLease> {
        self.recovery_lease.as_ref()
    }

    pub fn acquire_recovery_lease(&mut self, owner_id: &str, ttl_ms: u64) -> RecoveryLease {
        self.next_fencing_token += 1;
        let lease = RecoveryLease::new(
            format!("lease-{}", self.next_fencing_token),
            owner_id,
            self.next_fencing_token,
            self.clock_ms,
            ttl_ms,
        );
        self.recovery_lease = Some(lease.clone());
        lease
    }

    pub fn reconcile_assumed(
        &mut self,
        decision: ReconcileDecision,
    ) -> Result<RunSummary, RuntimeError> {
        if self.worker_state != WorkerState::Failed
            || self.effect.status != EffectStatus::ExecutedAssumed
        {
            return Err(RuntimeError::ReconcileUnavailable {
                state: self.worker_state,
                effect_status: self.effect.status,
            });
        }

        self.acquire_recovery_lease("doctor", DEFAULT_LEASE_TTL_MS);
        match decision {
            ReconcileDecision::Success => {
                self.effect.transition_to(
                    EffectStatus::Executed,
                    self.timestamp(),
                    "doctor",
                    "user_reconcile_success",
                )?;
                self.release_scope_quarantine();
                self.apply_worker_event(WorkerEvent::UserReconcileSuccess)?;
                self.apply_worker_event(WorkerEvent::ResultsPersisted)?;
            }
            ReconcileDecision::Failure => {
                self.effect.transition_to(
                    EffectStatus::Cancelled,
                    self.timestamp(),
                    "doctor",
                    "user_reconcile_failure",
                )?;
                self.release_scope_quarantine();
                self.apply_worker_event(WorkerEvent::UserReconcileFailure)?;
            }
        }

        Ok(self.summary())
    }

    fn apply_preflight(&mut self, decision: PreflightDecision) -> Result<(), RuntimeError> {
        let event = match decision {
            PreflightDecision::Permit => WorkerEvent::PlanReadyPermitted,
            PreflightDecision::NeedsConfirmation => WorkerEvent::PlanReadyNeedsConfirm,
        };

        self.apply_worker_event(event)
    }

    fn execute_effect(&mut self, execution: ExecutionDisposition) -> Result<(), RuntimeError> {
        self.ensure_scope_write_allowed()?;
        self.active_claims
            .push(ScopeClaim::write(self.effect.target.clone()));
        self.ensure_recovery_lease("worker")?;

        match execution {
            ExecutionDisposition::Commit => {
                self.execute_effect_to_commit_ready()?;
                self.apply_worker_event(WorkerEvent::ResultsPersisted)?;
            }
            ExecutionDisposition::Crash => {
                self.effect.transition_to(
                    EffectStatus::Dispatched,
                    self.timestamp(),
                    "worker",
                    "dispatch",
                )?;
                self.append_attempt()?;
                self.record_latest_attempt_result(AttemptResultStatus::Crash)?;
                let crash_status = self.effect.record_crash_outcome(
                    self.timestamp(),
                    "worker",
                    "process_crash",
                )?;
                self.apply_worker_event(WorkerEvent::EffectUncertain)?;

                if crash_status == EffectStatus::ExecutedAssumed {
                    let runtime_state =
                        runtime_state_from_effect(crash_status, self.effect.probe_state);
                    if scope_quarantine_trigger(runtime_state) {
                        self.quarantined_scopes.push(self.effect.target.clone());
                    }
                    self.apply_worker_event(WorkerEvent::ProbeAssumed)?;
                }
            }
        }

        self.active_claims.clear();
        Ok(())
    }

    fn execute_effect_to_commit_ready(&mut self) -> Result<(), RuntimeError> {
        self.effect.transition_to(
            EffectStatus::Dispatched,
            self.timestamp(),
            "worker",
            "dispatch",
        )?;
        self.append_attempt()?;
        self.effect.transition_to(
            EffectStatus::Executed,
            self.timestamp(),
            "worker",
            "external_confirmed",
        )?;
        self.record_latest_attempt_result(AttemptResultStatus::Success)?;
        self.apply_worker_event(WorkerEvent::AllEffectsDone)?;
        Ok(())
    }

    fn recover_failed_commit(&mut self) -> Result<(), RuntimeError> {
        match self.effect.reversibility {
            effect_ledger::EffectReversibility::Rollbackable => {
                self.apply_worker_event(WorkerEvent::AutoRollback)?;
                self.effect.transition_to(
                    EffectStatus::RolledBack,
                    self.timestamp(),
                    "worker",
                    "auto_rollback_after_persist_error",
                )?;
                self.apply_worker_event(WorkerEvent::RollbackOk)?;
            }
            effect_ledger::EffectReversibility::Compensatable => {
                self.apply_worker_event(WorkerEvent::AutoRollback)?;
                let compensation = self.effect.spawn_compensation(
                    format!("{}-comp", self.effect.effect_id),
                    format!("{}-comp", self.effect.intent_key),
                    effect_ledger::EffectActor::Doctor,
                    self.effect.action,
                    self.effect.target.clone(),
                    effect_ledger::EffectReversibility::Rollbackable,
                    self.effect.probe_mode,
                );
                let mut compensation = compensation;
                compensation.transition_to(
                    EffectStatus::Dispatched,
                    self.timestamp(),
                    "doctor",
                    "compensation_dispatch",
                )?;
                compensation.transition_to(
                    EffectStatus::Executed,
                    self.timestamp(),
                    "doctor",
                    "compensation_executed",
                )?;
                self.compensation_effects.push(compensation);
                self.effect.transition_to(
                    EffectStatus::Compensated,
                    self.timestamp(),
                    "doctor",
                    "compensation_applied",
                )?;
                self.apply_worker_event(WorkerEvent::RollbackOk)?;
            }
            effect_ledger::EffectReversibility::Irreversible => {
                self.apply_worker_event(WorkerEvent::UserAbandon)?;
            }
        }
        Ok(())
    }

    fn ensure_scope_write_allowed(&self) -> Result<(), RuntimeError> {
        match write_scope_decision(
            &self.effect.target,
            &self.active_claims,
            &self.quarantined_scopes,
        ) {
            GuardDecision::Allowed => Ok(()),
            GuardDecision::Blocked(reason) => Err(RuntimeError::GuardBlocked(reason)),
        }
    }

    fn ensure_recovery_lease(&mut self, owner_id: &str) -> Result<(), RuntimeError> {
        if let Some(lease) = self.recovery_lease.as_mut() {
            if lease.owner_id == owner_id && lease.is_active(self.clock_ms) {
                lease.renew(self.clock_ms)?;
                return Ok(());
            }
        }

        self.acquire_recovery_lease(owner_id, DEFAULT_LEASE_TTL_MS);
        Ok(())
    }

    fn append_attempt(&mut self) -> Result<(), RuntimeError> {
        let lease = self
            .recovery_lease
            .as_ref()
            .ok_or(RuntimeError::MissingRecoveryLease)?;
        let attempt = EffectAttempt::next_for_effect(
            &self.attempts,
            format!("attempt-{}", self.attempts.len() + 1),
            self.effect.effect_id.clone(),
            self.timestamp(),
            lease,
            self.clock_ms,
        )?;
        self.attempts.push(attempt);
        Ok(())
    }

    fn record_latest_attempt_result(
        &mut self,
        result_status: AttemptResultStatus,
    ) -> Result<(), RuntimeError> {
        let lease = self
            .recovery_lease
            .as_ref()
            .ok_or(RuntimeError::MissingRecoveryLease)?;
        let latest_attempt = self
            .attempts
            .last_mut()
            .ok_or(RuntimeError::MissingAttempt)?;
        latest_attempt.record_result(result_status, lease, self.clock_ms)?;
        Ok(())
    }

    fn release_scope_quarantine(&mut self) {
        self.quarantined_scopes.retain(|scope| scope != &self.effect.target);
    }

    fn apply_worker_event(&mut self, event: WorkerEvent) -> Result<(), RuntimeError> {
        let transition = transition_for(event, self.worker_state).ok_or(
            RuntimeError::InvalidWorkerTransition {
                state: self.worker_state,
                event,
            },
        )?;
        self.worker_state = transition.to;
        Ok(())
    }

    fn timestamp(&self) -> String {
        format!("2026-03-21T00:00:{:02}Z", (self.clock_ms / 1000) % 60)
    }

    fn summary(&self) -> RunSummary {
        RunSummary {
            worker_state: self.worker_state,
            effect_status: self.effect.status,
            attempt_count: self.attempts.len(),
            compensation_count: self.compensation_effects.len(),
            quarantined_scopes: self.quarantined_scopes.clone(),
        }
    }
}

impl From<EffectTransitionError> for RuntimeError {
    fn from(value: EffectTransitionError) -> Self {
        RuntimeError::EffectTransition(value)
    }
}

impl From<AttemptWriteError> for RuntimeError {
    fn from(value: AttemptWriteError) -> Self {
        RuntimeError::AttemptWrite(value)
    }
}

impl From<LeaseError> for RuntimeError {
    fn from(value: LeaseError) -> Self {
        RuntimeError::Lease(value)
    }
}

#[cfg(test)]
mod tests {
    use super::{
        DEFAULT_LEASE_TTL_MS, ExecutionDisposition, InMemoryTaskRuntime, PreflightDecision,
        ReconcileDecision,
    };
    use crate::effect_ledger::{
        EffectAction, EffectActor, EffectRecord, EffectReversibility, EffectStatus, EffectTier,
        LeaseError, ProbeMode,
    };
    use crate::worker_lifecycle::WorkerState;

    fn demo_runtime(probe_mode: ProbeMode) -> InMemoryTaskRuntime {
        InMemoryTaskRuntime::new(EffectRecord::new(
            "effect-1",
            "task-1",
            "trace-1",
            "intent-1",
            EffectActor::Worker,
            EffectAction::FileWrite,
            "scope:/tmp/demo.txt",
            EffectTier::Tier1,
            EffectReversibility::Rollbackable,
            probe_mode,
        ))
    }

    #[test]
    fn minimal_flow_reaches_succeeded_on_commit() {
        let mut runtime = demo_runtime(ProbeMode::Auto);

        let summary = runtime
            .run_minimal_flow(PreflightDecision::Permit, ExecutionDisposition::Commit)
            .unwrap();

        assert_eq!(summary.worker_state, WorkerState::Succeeded);
        assert_eq!(summary.effect_status, EffectStatus::Executed);
        assert_eq!(summary.attempt_count, 1);
    }

    #[test]
    fn minimal_flow_stops_at_uncertain_after_probeable_crash() {
        let mut runtime = demo_runtime(ProbeMode::Auto);

        let summary = runtime
            .run_minimal_flow(PreflightDecision::Permit, ExecutionDisposition::Crash)
            .unwrap();

        assert_eq!(summary.worker_state, WorkerState::Uncertain);
        assert_eq!(summary.effect_status, EffectStatus::Uncertain);
        assert_eq!(runtime.attempts.len(), 1);
    }

    #[test]
    fn no_probe_crash_quarantines_scope_and_ends_failed() {
        let mut runtime = demo_runtime(ProbeMode::None);

        let summary = runtime
            .run_minimal_flow(PreflightDecision::Permit, ExecutionDisposition::Crash)
            .unwrap();

        assert_eq!(summary.worker_state, WorkerState::Failed);
        assert_eq!(summary.effect_status, EffectStatus::ExecutedAssumed);
        assert_eq!(summary.quarantined_scopes, vec![String::from("scope:/tmp/demo.txt")]);
    }

    #[test]
    fn rollbackable_persist_error_recovers_to_rolled_back() {
        let mut runtime = demo_runtime(ProbeMode::Auto);

        let summary = runtime
            .run_persist_error_recovery(PreflightDecision::Permit)
            .unwrap();

        assert_eq!(summary.worker_state, WorkerState::RolledBack);
        assert_eq!(summary.effect_status, EffectStatus::RolledBack);
        assert_eq!(summary.compensation_count, 0);
    }

    #[test]
    fn compensatable_persist_error_spawns_independent_compensation_effect() {
        let effect = EffectRecord::new(
            "effect-compensatable",
            "task-2",
            "trace-2",
            "intent-2",
            EffectActor::Worker,
            EffectAction::FileWrite,
            "scope:/tmp/comp.txt",
            EffectTier::Tier1,
            EffectReversibility::Compensatable,
            ProbeMode::Auto,
        );
        let mut runtime = InMemoryTaskRuntime::new(effect);

        let summary = runtime
            .run_persist_error_recovery(PreflightDecision::Permit)
            .unwrap();

        assert_eq!(summary.worker_state, WorkerState::RolledBack);
        assert_eq!(summary.effect_status, EffectStatus::Compensated);
        assert_eq!(summary.compensation_count, 1);
        assert_eq!(
            runtime.compensation_effects[0].compensates_effect_id,
            Some(String::from("effect-compensatable"))
        );
    }

    #[test]
    fn expired_lease_rejects_stale_holder_and_new_lease_can_reconcile() {
        let mut runtime = demo_runtime(ProbeMode::None);
        runtime
            .run_minimal_flow(PreflightDecision::Permit, ExecutionDisposition::Crash)
            .unwrap();

        let stale_lease = runtime.current_recovery_lease().unwrap().clone();
        runtime.advance_clock(DEFAULT_LEASE_TTL_MS + 1);

        assert_eq!(
            stale_lease.assert_can_write(
                &stale_lease.lease_id,
                stale_lease.fencing_token,
                runtime.clock_ms,
            ),
            Err(LeaseError::Expired {
                now_ms: runtime.clock_ms,
                expires_at_ms: stale_lease.expires_at_ms,
            })
        );

        let summary = runtime.reconcile_assumed(ReconcileDecision::Success).unwrap();
        let new_lease = runtime.current_recovery_lease().unwrap();

        assert_eq!(summary.worker_state, WorkerState::Succeeded);
        assert_eq!(summary.effect_status, EffectStatus::Executed);
        assert!(summary.quarantined_scopes.is_empty());
        assert!(new_lease.fencing_token > stale_lease.fencing_token);
    }

    #[test]
    fn reconcile_failure_clears_quarantine_and_closes_failed_terminal() {
        let mut runtime = demo_runtime(ProbeMode::None);
        runtime
            .run_minimal_flow(PreflightDecision::Permit, ExecutionDisposition::Crash)
            .unwrap();
        runtime.advance_clock(DEFAULT_LEASE_TTL_MS + 1);

        let summary = runtime.reconcile_assumed(ReconcileDecision::Failure).unwrap();

        assert_eq!(summary.worker_state, WorkerState::FailedTerminal);
        assert_eq!(summary.effect_status, EffectStatus::Cancelled);
        assert!(summary.quarantined_scopes.is_empty());
    }
}
