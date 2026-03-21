#![forbid(unsafe_code)]

pub mod effect_ledger;
pub mod protocol;
pub mod spec_map;
pub mod task_concurrency;
pub mod worker_lifecycle;

use std::collections::{HashMap, HashSet};

use effect_ledger::{
    AttemptResultStatus, AttemptWriteError, EffectAttempt, EffectRecord, EffectStatus,
    EffectTransitionError, LeaseError, ProbeState, RecoveryLease,
};
use task_concurrency::{
    runtime_state_from_effect, scope_quarantine_trigger, user_retry_decision,
    write_scope_decision, EffectGuardSnapshot, GuardBlockReason, GuardDecision,
    ScopeClaim,
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

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RepairUserAction {
    Close,
    RetryPlanning,
    RetryRepair,
    Abandon,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ConfirmationAction {
    Confirm,
    Deny,
    Timeout,
    SystemBudgetExceeded,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum HibernationAction {
    Resume(PreflightDecision),
    Expire,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ExecutionInterruption {
    NewBlacklistOp,
    ExecError,
    BudgetExceeded,
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
pub struct StateEvent {
    pub state_event_id: String,
    pub task_id: String,
    pub worker_state: WorkerState,
    pub effect_status: EffectStatus,
    pub probe_state: Option<ProbeState>,
    pub fencing_token: u64,
    pub triggered_by: String,
    pub at: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct TaskSnapshot {
    pub task_id: String,
    pub worker_state: WorkerState,
    pub effect_status: EffectStatus,
    pub probe_state: Option<ProbeState>,
    pub last_state_event_id: String,
    pub fencing_token: u64,
    pub version: u64,
    pub updated_at: String,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum StateApplyResult {
    Applied,
    DuplicateIgnored,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum StateEngineError {
    StaleFencingToken { current: u64, provided: u64 },
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

#[derive(Clone, Debug, Default)]
pub struct InMemoryStateEngine {
    snapshots: HashMap<String, TaskSnapshot>,
    applied_event_ids: HashSet<String>,
    current_fencing_tokens: HashMap<String, u64>,
    events: Vec<StateEvent>,
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

    pub fn state_event(
        &self,
        state_event_id: impl Into<String>,
        triggered_by: impl Into<String>,
    ) -> StateEvent {
        StateEvent {
            state_event_id: state_event_id.into(),
            task_id: self.effect.task_id.clone(),
            worker_state: self.worker_state,
            effect_status: self.effect.status,
            probe_state: self.effect.probe_state,
            fencing_token: self
                .recovery_lease
                .as_ref()
                .map(|lease| lease.fencing_token)
                .unwrap_or(0),
            triggered_by: triggered_by.into(),
            at: self.timestamp(),
        }
    }

    pub fn persist_state(
        &self,
        engine: &mut InMemoryStateEngine,
        state_event_id: impl Into<String>,
        triggered_by: impl Into<String>,
    ) -> Result<StateApplyResult, StateEngineError> {
        engine.apply_event(self.state_event(state_event_id, triggered_by))
    }

    pub fn restore_from_snapshot(
        mut effect: EffectRecord,
        snapshot: &TaskSnapshot,
        recovery_lease: Option<RecoveryLease>,
    ) -> Self {
        effect.status = snapshot.effect_status;
        effect.probe_state = snapshot.probe_state;

        Self {
            worker_state: snapshot.worker_state,
            effect,
            attempts: Vec::new(),
            compensation_effects: Vec::new(),
            active_claims: Vec::new(),
            quarantined_scopes: Vec::new(),
            recovery_lease,
            next_fencing_token: snapshot.fencing_token,
            clock_ms: 0,
        }
    }

    pub fn run_minimal_flow(
        &mut self,
        preflight: PreflightDecision,
        execution: ExecutionDisposition,
    ) -> Result<RunSummary, RuntimeError> {
        self.start_task(preflight)?;

        if self.worker_state == WorkerState::Executing {
            self.execute_effect(execution)?;
        }

        Ok(self.summary())
    }

    pub fn run_confirmation_checkpoint(&mut self) -> Result<RunSummary, RuntimeError> {
        self.start_task(PreflightDecision::NeedsConfirmation)?;
        Ok(self.summary())
    }

    pub fn run_plan_failure(&mut self) -> Result<RunSummary, RuntimeError> {
        self.apply_worker_event(WorkerEvent::TaskAccepted)?;
        self.apply_worker_event(WorkerEvent::PlanError)?;
        Ok(self.summary())
    }

    pub fn resolve_confirmation(
        &mut self,
        action: ConfirmationAction,
    ) -> Result<RunSummary, RuntimeError> {
        let event = match action {
            ConfirmationAction::Confirm => WorkerEvent::UserConfirmed,
            ConfirmationAction::Deny => WorkerEvent::UserDenied,
            ConfirmationAction::Timeout => WorkerEvent::ConfirmTimeout,
            ConfirmationAction::SystemBudgetExceeded => WorkerEvent::SystemBudgetExceeded,
        };

        if self.worker_state != WorkerState::AwaitingConfirmation {
            return Err(RuntimeError::ReconcileUnavailable {
                state: self.worker_state,
                effect_status: self.effect.status,
            });
        }

        self.apply_worker_event(event)?;
        Ok(self.summary())
    }

    pub fn resolve_hibernation(
        &mut self,
        action: HibernationAction,
    ) -> Result<RunSummary, RuntimeError> {
        if self.worker_state != WorkerState::Hibernated {
            return Err(RuntimeError::ReconcileUnavailable {
                state: self.worker_state,
                effect_status: self.effect.status,
            });
        }

        match action {
            HibernationAction::Resume(preflight) => {
                self.apply_worker_event(WorkerEvent::UserResume)?;
                self.apply_preflight(preflight)?;
            }
            HibernationAction::Expire => {
                self.apply_worker_event(WorkerEvent::HibernateExpired)?;
            }
        }

        Ok(self.summary())
    }

    pub fn continue_execution(
        &mut self,
        execution: ExecutionDisposition,
    ) -> Result<RunSummary, RuntimeError> {
        if self.worker_state != WorkerState::Executing {
            return Err(RuntimeError::ReconcileUnavailable {
                state: self.worker_state,
                effect_status: self.effect.status,
            });
        }

        self.execute_effect(execution)?;
        Ok(self.summary())
    }

    pub fn interrupt_execution(
        &mut self,
        interruption: ExecutionInterruption,
    ) -> Result<RunSummary, RuntimeError> {
        if self.worker_state != WorkerState::Executing {
            return Err(RuntimeError::ReconcileUnavailable {
                state: self.worker_state,
                effect_status: self.effect.status,
            });
        }

        let event = match interruption {
            ExecutionInterruption::NewBlacklistOp => WorkerEvent::NewBlacklistOp,
            ExecutionInterruption::ExecError => WorkerEvent::ExecError,
            ExecutionInterruption::BudgetExceeded => WorkerEvent::BudgetExceeded,
        };

        self.apply_worker_event(event)?;
        Ok(self.summary())
    }

    pub fn begin_probe(&mut self) -> Result<RunSummary, RuntimeError> {
        if self.worker_state != WorkerState::Uncertain
            || self.effect.status != EffectStatus::Uncertain
        {
            return Err(RuntimeError::ReconcileUnavailable {
                state: self.worker_state,
                effect_status: self.effect.status,
            });
        }

        self.effect.probe_state = Some(ProbeState::Probing);
        Ok(self.summary())
    }

    pub fn resolve_probe_success(&mut self) -> Result<RunSummary, RuntimeError> {
        if self.worker_state != WorkerState::Uncertain
            || self.effect.status != EffectStatus::Uncertain
        {
            return Err(RuntimeError::ReconcileUnavailable {
                state: self.worker_state,
                effect_status: self.effect.status,
            });
        }

        self.effect.transition_to(
            EffectStatus::Executed,
            self.timestamp(),
            "doctor",
            "probe_confirmed_executed",
        )?;
        self.apply_worker_event(WorkerEvent::ProbeSuccess)?;
        self.apply_worker_event(WorkerEvent::ResultsPersisted)?;
        Ok(self.summary())
    }

    pub fn resolve_probe_failure(&mut self) -> Result<RunSummary, RuntimeError> {
        if self.worker_state != WorkerState::Uncertain
            || self.effect.status != EffectStatus::Uncertain
        {
            return Err(RuntimeError::ReconcileUnavailable {
                state: self.worker_state,
                effect_status: self.effect.status,
            });
        }

        self.effect.transition_to(
            EffectStatus::Cancelled,
            self.timestamp(),
            "doctor",
            "probe_confirmed_not_executed",
        )?;
        self.apply_worker_event(WorkerEvent::ProbeFailure)?;
        Ok(self.summary())
    }

    pub fn retry_failed(
        &mut self,
        preflight: PreflightDecision,
    ) -> Result<RunSummary, RuntimeError> {
        if self.worker_state != WorkerState::Failed {
            return Err(RuntimeError::ReconcileUnavailable {
                state: self.worker_state,
                effect_status: self.effect.status,
            });
        }

        match user_retry_decision(&[self.effect_guard_snapshot()]) {
            GuardDecision::Allowed => {
                self.apply_worker_event(WorkerEvent::UserRetry)?;
                self.apply_preflight(preflight)?;
                Ok(self.summary())
            }
            GuardDecision::Blocked(reason) => Err(RuntimeError::GuardBlocked(reason)),
        }
    }

    pub fn abandon_failed(&mut self) -> Result<RunSummary, RuntimeError> {
        if self.worker_state != WorkerState::Failed {
            return Err(RuntimeError::ReconcileUnavailable {
                state: self.worker_state,
                effect_status: self.effect.status,
            });
        }

        self.apply_worker_event(WorkerEvent::UserAbandon)?;
        Ok(self.summary())
    }

    pub fn run_persist_error_recovery(
        &mut self,
        preflight: PreflightDecision,
    ) -> Result<RunSummary, RuntimeError> {
        self.start_task(preflight)?;

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

    pub fn run_doctor_repair_flow(
        &mut self,
        preflight: PreflightDecision,
        repair_succeeds: bool,
    ) -> Result<RunSummary, RuntimeError> {
        self.start_task(preflight)?;

        if self.worker_state == WorkerState::Executing {
            self.ensure_scope_write_allowed()?;
            self.active_claims
                .push(ScopeClaim::write(self.effect.target.clone()));
            self.ensure_recovery_lease("worker")?;
            self.execute_effect_to_commit_ready()?;
            self.apply_worker_event(WorkerEvent::PersistError)?;
            self.apply_worker_event(WorkerEvent::AutoRollback)?;
            self.apply_worker_event(WorkerEvent::RollbackFailed)?;
            self.acquire_recovery_lease("doctor", DEFAULT_LEASE_TTL_MS);
            self.apply_worker_event(WorkerEvent::DoctorKillDone)?;
            if repair_succeeds {
                self.apply_worker_event(WorkerEvent::RepairOk)?;
            } else {
                self.apply_worker_event(WorkerEvent::RepairFailed)?;
            }
            self.active_claims.clear();
        }

        Ok(self.summary())
    }

    pub fn resolve_repair_state(
        &mut self,
        action: RepairUserAction,
    ) -> Result<RunSummary, RuntimeError> {
        match (self.worker_state, action) {
            (WorkerState::Repaired, RepairUserAction::Close) => {
                self.apply_worker_event(WorkerEvent::UserClose)?;
            }
            (WorkerState::Repaired, RepairUserAction::RetryPlanning) => {
                self.apply_worker_event(WorkerEvent::UserRetryFromRepaired)?;
            }
            (WorkerState::RepairFailed, RepairUserAction::RetryRepair) => {
                self.apply_worker_event(WorkerEvent::UserRetryRepair)?;
            }
            (WorkerState::RepairFailed, RepairUserAction::Abandon) => {
                self.apply_worker_event(WorkerEvent::UserAbandonRepair)?;
            }
            _ => {
                return Err(RuntimeError::ReconcileUnavailable {
                    state: self.worker_state,
                    effect_status: self.effect.status,
                });
            }
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

    fn start_task(&mut self, preflight: PreflightDecision) -> Result<(), RuntimeError> {
        self.apply_worker_event(WorkerEvent::TaskAccepted)?;
        self.apply_preflight(preflight)
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

    fn effect_guard_snapshot(&self) -> EffectGuardSnapshot {
        EffectGuardSnapshot {
            status: self.effect.status,
            probe_state: self.effect.probe_state,
        }
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

impl InMemoryStateEngine {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn apply_event(
        &mut self,
        event: StateEvent,
    ) -> Result<StateApplyResult, StateEngineError> {
        if self.applied_event_ids.contains(&event.state_event_id) {
            return Ok(StateApplyResult::DuplicateIgnored);
        }

        let current_fencing_token = self
            .current_fencing_tokens
            .get(&event.task_id)
            .copied()
            .unwrap_or(0);
        if event.fencing_token < current_fencing_token {
            return Err(StateEngineError::StaleFencingToken {
                current: current_fencing_token,
                provided: event.fencing_token,
            });
        }

        let next_version = self
            .snapshots
            .get(&event.task_id)
            .map(|snapshot| snapshot.version + 1)
            .unwrap_or(1);
        let snapshot = TaskSnapshot {
            task_id: event.task_id.clone(),
            worker_state: event.worker_state,
            effect_status: event.effect_status,
            probe_state: event.probe_state,
            last_state_event_id: event.state_event_id.clone(),
            fencing_token: event.fencing_token,
            version: next_version,
            updated_at: event.at.clone(),
        };

        self.current_fencing_tokens
            .insert(event.task_id.clone(), event.fencing_token);
        self.applied_event_ids.insert(event.state_event_id.clone());
        self.events.push(event.clone());
        self.snapshots.insert(event.task_id, snapshot);
        Ok(StateApplyResult::Applied)
    }

    pub fn snapshot(&self, task_id: &str) -> Option<&TaskSnapshot> {
        self.snapshots.get(task_id)
    }

    pub fn event_count(&self) -> usize {
        self.events.len()
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
        ConfirmationAction, DEFAULT_LEASE_TTL_MS, ExecutionDisposition,
        ExecutionInterruption, HibernationAction, InMemoryStateEngine,
        InMemoryTaskRuntime, PreflightDecision, ReconcileDecision, RepairUserAction,
        RuntimeError, StateApplyResult, StateEngineError, StateEvent,
    };
    use crate::effect_ledger::{
        EffectAction, EffectActor, EffectRecord, EffectReversibility, EffectStatus, EffectTier,
        LeaseError, ProbeMode, ProbeState,
    };
    use crate::task_concurrency::GuardBlockReason;
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
    fn state_engine_deduplicates_by_state_event_id() {
        let mut runtime = demo_runtime(ProbeMode::Auto);
        runtime
            .run_minimal_flow(PreflightDecision::Permit, ExecutionDisposition::Commit)
            .unwrap();

        let mut engine = InMemoryStateEngine::new();
        let event = runtime.state_event("evt-1", "worker");

        assert_eq!(
            engine.apply_event(event.clone()).unwrap(),
            StateApplyResult::Applied
        );
        assert_eq!(
            engine.apply_event(event).unwrap(),
            StateApplyResult::DuplicateIgnored
        );
        assert_eq!(engine.event_count(), 1);

        let snapshot = engine.snapshot("task-1").unwrap();
        assert_eq!(snapshot.worker_state, WorkerState::Succeeded);
        assert_eq!(snapshot.effect_status, EffectStatus::Executed);
        assert_eq!(snapshot.version, 1);
    }

    #[test]
    fn state_engine_rejects_stale_fencing_token() {
        let mut engine = InMemoryStateEngine::new();
        let fresh = StateEvent {
            state_event_id: String::from("evt-fresh"),
            task_id: String::from("task-fence"),
            worker_state: WorkerState::Failed,
            effect_status: EffectStatus::Cancelled,
            probe_state: None,
            fencing_token: 7,
            triggered_by: String::from("doctor"),
            at: String::from("2026-03-21T00:00:00Z"),
        };
        let stale = StateEvent {
            state_event_id: String::from("evt-stale"),
            task_id: String::from("task-fence"),
            worker_state: WorkerState::Planning,
            effect_status: EffectStatus::Prepared,
            probe_state: None,
            fencing_token: 6,
            triggered_by: String::from("worker"),
            at: String::from("2026-03-21T00:00:01Z"),
        };

        assert_eq!(engine.apply_event(fresh).unwrap(), StateApplyResult::Applied);
        assert_eq!(
            engine.apply_event(stale),
            Err(StateEngineError::StaleFencingToken {
                current: 7,
                provided: 6,
            })
        );
    }

    #[test]
    fn runtime_can_restore_from_uncertain_snapshot() {
        let mut runtime = demo_runtime(ProbeMode::Auto);
        runtime
            .run_minimal_flow(PreflightDecision::Permit, ExecutionDisposition::Crash)
            .unwrap();

        let snapshot = runtime.state_event("evt-restore-uncertain", "worker");
        let mut engine = InMemoryStateEngine::new();
        engine.apply_event(snapshot).unwrap();

        let restored = InMemoryTaskRuntime::restore_from_snapshot(
            demo_runtime(ProbeMode::Auto).effect,
            engine.snapshot("task-1").unwrap(),
            None,
        );

        assert_eq!(restored.worker_state, WorkerState::Uncertain);
        assert_eq!(restored.effect.status, EffectStatus::Uncertain);
        assert_eq!(restored.effect.probe_state, Some(ProbeState::ProbePending));
    }

    #[test]
    fn runtime_can_restore_from_executed_assumed_snapshot() {
        let mut runtime = demo_runtime(ProbeMode::None);
        runtime
            .run_minimal_flow(PreflightDecision::Permit, ExecutionDisposition::Crash)
            .unwrap();

        let snapshot = runtime.state_event("evt-restore-assumed", "worker");
        let mut engine = InMemoryStateEngine::new();
        engine.apply_event(snapshot).unwrap();

        let restored = InMemoryTaskRuntime::restore_from_snapshot(
            demo_runtime(ProbeMode::None).effect,
            engine.snapshot("task-1").unwrap(),
            None,
        );

        assert_eq!(restored.worker_state, WorkerState::Failed);
        assert_eq!(restored.effect.status, EffectStatus::ExecutedAssumed);
        assert_eq!(restored.effect.probe_state, Some(ProbeState::HumanFrozen));
    }

    #[test]
    fn persisted_uncertain_runtime_can_restart_and_commit_after_probe_success() {
        let mut runtime = demo_runtime(ProbeMode::Auto);
        runtime
            .run_minimal_flow(PreflightDecision::Permit, ExecutionDisposition::Crash)
            .unwrap();

        let mut engine = InMemoryStateEngine::new();
        runtime
            .persist_state(&mut engine, "evt-restart-uncertain", "worker")
            .unwrap();

        let mut restarted = InMemoryTaskRuntime::restore_from_snapshot(
            demo_runtime(ProbeMode::Auto).effect,
            engine.snapshot("task-1").unwrap(),
            None,
        );
        restarted.begin_probe().unwrap();
        let summary = restarted.resolve_probe_success().unwrap();

        assert_eq!(summary.worker_state, WorkerState::Succeeded);
        assert_eq!(summary.effect_status, EffectStatus::Executed);
    }

    #[test]
    fn persisted_executed_assumed_runtime_can_restart_and_reconcile() {
        let mut runtime = demo_runtime(ProbeMode::None);
        runtime
            .run_minimal_flow(PreflightDecision::Permit, ExecutionDisposition::Crash)
            .unwrap();

        let mut engine = InMemoryStateEngine::new();
        runtime
            .persist_state(&mut engine, "evt-restart-assumed", "worker")
            .unwrap();

        let mut restarted = InMemoryTaskRuntime::restore_from_snapshot(
            demo_runtime(ProbeMode::None).effect,
            engine.snapshot("task-1").unwrap(),
            None,
        );
        let summary = restarted.reconcile_assumed(ReconcileDecision::Success).unwrap();

        assert_eq!(summary.worker_state, WorkerState::Succeeded);
        assert_eq!(summary.effect_status, EffectStatus::Executed);
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
    fn uncertain_probe_success_can_commit_cleanly() {
        let mut runtime = demo_runtime(ProbeMode::Auto);
        runtime
            .run_minimal_flow(PreflightDecision::Permit, ExecutionDisposition::Crash)
            .unwrap();

        let probing = runtime.begin_probe().unwrap();
        assert_eq!(probing.worker_state, WorkerState::Uncertain);
        assert_eq!(runtime.effect.probe_state, Some(ProbeState::Probing));

        let succeeded = runtime.resolve_probe_success().unwrap();
        assert_eq!(succeeded.worker_state, WorkerState::Succeeded);
        assert_eq!(succeeded.effect_status, EffectStatus::Executed);
    }

    #[test]
    fn uncertain_probe_failure_cancels_effect_and_allows_retry() {
        let mut runtime = demo_runtime(ProbeMode::Auto);
        runtime
            .run_minimal_flow(PreflightDecision::Permit, ExecutionDisposition::Crash)
            .unwrap();
        runtime.begin_probe().unwrap();

        let failed = runtime.resolve_probe_failure().unwrap();
        assert_eq!(failed.worker_state, WorkerState::Failed);
        assert_eq!(failed.effect_status, EffectStatus::Cancelled);

        let executing = runtime.retry_failed(PreflightDecision::Permit).unwrap();
        assert_eq!(executing.worker_state, WorkerState::Executing);
    }

    #[test]
    fn confirmation_flow_can_confirm_and_commit() {
        let mut runtime = demo_runtime(ProbeMode::Auto);

        let waiting = runtime.run_confirmation_checkpoint().unwrap();
        assert_eq!(waiting.worker_state, WorkerState::AwaitingConfirmation);

        let executing = runtime
            .resolve_confirmation(ConfirmationAction::Confirm)
            .unwrap();
        assert_eq!(executing.worker_state, WorkerState::Executing);

        let succeeded = runtime.continue_execution(ExecutionDisposition::Commit).unwrap();
        assert_eq!(succeeded.worker_state, WorkerState::Succeeded);
        assert_eq!(succeeded.effect_status, EffectStatus::Executed);
    }

    #[test]
    fn confirmation_timeout_can_hibernate_and_resume() {
        let mut runtime = demo_runtime(ProbeMode::Auto);

        runtime.run_confirmation_checkpoint().unwrap();
        let hibernated = runtime
            .resolve_confirmation(ConfirmationAction::Timeout)
            .unwrap();
        assert_eq!(hibernated.worker_state, WorkerState::Hibernated);

        let resumed = runtime
            .resolve_hibernation(HibernationAction::Resume(PreflightDecision::Permit))
            .unwrap();
        assert_eq!(resumed.worker_state, WorkerState::Executing);

        let succeeded = runtime.continue_execution(ExecutionDisposition::Commit).unwrap();
        assert_eq!(succeeded.worker_state, WorkerState::Succeeded);
    }

    #[test]
    fn confirmation_denial_and_hibernation_expiry_fail_safely() {
        let mut denied_runtime = demo_runtime(ProbeMode::Auto);
        denied_runtime.run_confirmation_checkpoint().unwrap();
        let denied = denied_runtime
            .resolve_confirmation(ConfirmationAction::Deny)
            .unwrap();
        assert_eq!(denied.worker_state, WorkerState::Failed);

        let mut budget_runtime = demo_runtime(ProbeMode::Auto);
        budget_runtime.run_confirmation_checkpoint().unwrap();
        let budget_failed = budget_runtime
            .resolve_confirmation(ConfirmationAction::SystemBudgetExceeded)
            .unwrap();
        assert_eq!(budget_failed.worker_state, WorkerState::Failed);

        let mut expired_runtime = demo_runtime(ProbeMode::Auto);
        expired_runtime.run_confirmation_checkpoint().unwrap();
        expired_runtime
            .resolve_confirmation(ConfirmationAction::Timeout)
            .unwrap();
        let expired = expired_runtime
            .resolve_hibernation(HibernationAction::Expire)
            .unwrap();
        assert_eq!(expired.worker_state, WorkerState::FailedTerminal);
    }

    #[test]
    fn planning_failure_can_retry_into_execution() {
        let mut runtime = demo_runtime(ProbeMode::Auto);
        let failed = runtime.run_plan_failure().unwrap();
        assert_eq!(failed.worker_state, WorkerState::Failed);

        let executing = runtime.retry_failed(PreflightDecision::Permit).unwrap();
        assert_eq!(executing.worker_state, WorkerState::Executing);
    }

    #[test]
    fn execution_blacklist_pause_can_reconfirm_and_continue() {
        let mut runtime = demo_runtime(ProbeMode::Auto);
        runtime.start_task(PreflightDecision::Permit).unwrap();
        let waiting = runtime
            .interrupt_execution(ExecutionInterruption::NewBlacklistOp)
            .unwrap();
        assert_eq!(waiting.worker_state, WorkerState::AwaitingConfirmation);

        let executing = runtime
            .resolve_confirmation(ConfirmationAction::Confirm)
            .unwrap();
        assert_eq!(executing.worker_state, WorkerState::Executing);

        let succeeded = runtime.continue_execution(ExecutionDisposition::Commit).unwrap();
        assert_eq!(succeeded.worker_state, WorkerState::Succeeded);
    }

    #[test]
    fn execution_failures_can_abandon_or_retry_when_effect_is_safe() {
        let mut runtime = demo_runtime(ProbeMode::Auto);
        runtime.start_task(PreflightDecision::Permit).unwrap();
        let failed = runtime
            .interrupt_execution(ExecutionInterruption::BudgetExceeded)
            .unwrap();
        assert_eq!(failed.worker_state, WorkerState::Failed);

        let executing = runtime.retry_failed(PreflightDecision::Permit).unwrap();
        assert_eq!(executing.worker_state, WorkerState::Executing);

        let mut abandon_runtime = demo_runtime(ProbeMode::Auto);
        abandon_runtime.start_task(PreflightDecision::Permit).unwrap();
        abandon_runtime
            .interrupt_execution(ExecutionInterruption::ExecError)
            .unwrap();
        let terminal = abandon_runtime.abandon_failed().unwrap();
        assert_eq!(terminal.worker_state, WorkerState::FailedTerminal);
    }

    #[test]
    fn failed_retry_reenters_planning_when_effect_is_safe() {
        let mut runtime = demo_runtime(ProbeMode::Auto);
        runtime.run_confirmation_checkpoint().unwrap();
        runtime
            .resolve_confirmation(ConfirmationAction::Deny)
            .unwrap();

        let executing = runtime.retry_failed(PreflightDecision::Permit).unwrap();
        assert_eq!(executing.worker_state, WorkerState::Executing);

        let succeeded = runtime.continue_execution(ExecutionDisposition::Commit).unwrap();
        assert_eq!(succeeded.worker_state, WorkerState::Succeeded);
    }

    #[test]
    fn failed_retry_is_blocked_when_effect_remains_executed_assumed() {
        let mut runtime = demo_runtime(ProbeMode::None);
        runtime
            .run_minimal_flow(PreflightDecision::Permit, ExecutionDisposition::Crash)
            .unwrap();

        let err = runtime.retry_failed(PreflightDecision::Permit).unwrap_err();
        assert_eq!(
            err,
            RuntimeError::GuardBlocked(GuardBlockReason::UserRetryBlocked)
        );
    }

    #[test]
    fn failed_abandon_reaches_failed_terminal() {
        let mut runtime = demo_runtime(ProbeMode::Auto);
        runtime.run_confirmation_checkpoint().unwrap();
        runtime
            .resolve_confirmation(ConfirmationAction::SystemBudgetExceeded)
            .unwrap();

        let terminal = runtime.abandon_failed().unwrap();
        assert_eq!(terminal.worker_state, WorkerState::FailedTerminal);
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
    fn doctor_repair_flow_can_close_after_successful_repair() {
        let mut runtime = demo_runtime(ProbeMode::Auto);

        let summary = runtime
            .run_doctor_repair_flow(PreflightDecision::Permit, true)
            .unwrap();
        assert_eq!(summary.worker_state, WorkerState::Repaired);
        assert_eq!(summary.effect_status, EffectStatus::Executed);

        let closed = runtime.resolve_repair_state(RepairUserAction::Close).unwrap();
        assert_eq!(closed.worker_state, WorkerState::Closed);
    }

    #[test]
    fn doctor_repair_flow_can_abandon_after_repair_failed() {
        let mut runtime = demo_runtime(ProbeMode::Auto);

        let summary = runtime
            .run_doctor_repair_flow(PreflightDecision::Permit, false)
            .unwrap();
        assert_eq!(summary.worker_state, WorkerState::RepairFailed);
        assert_eq!(summary.effect_status, EffectStatus::Executed);

        let failed_terminal = runtime.resolve_repair_state(RepairUserAction::Abandon).unwrap();
        assert_eq!(failed_terminal.worker_state, WorkerState::FailedTerminal);
    }

    #[test]
    fn repaired_worker_can_reenter_planning() {
        let mut runtime = demo_runtime(ProbeMode::Auto);
        runtime
            .run_doctor_repair_flow(PreflightDecision::Permit, true)
            .unwrap();

        let planning = runtime
            .resolve_repair_state(RepairUserAction::RetryPlanning)
            .unwrap();

        assert_eq!(planning.worker_state, WorkerState::Planning);
        assert_eq!(planning.effect_status, EffectStatus::Executed);
    }

    #[test]
    fn repair_failed_worker_can_retry_repair() {
        let mut runtime = demo_runtime(ProbeMode::Auto);
        runtime
            .run_doctor_repair_flow(PreflightDecision::Permit, false)
            .unwrap();

        let awaiting_doctor = runtime
            .resolve_repair_state(RepairUserAction::RetryRepair)
            .unwrap();

        assert_eq!(awaiting_doctor.worker_state, WorkerState::AwaitingDoctor);
        assert_eq!(awaiting_doctor.effect_status, EffectStatus::Executed);
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
