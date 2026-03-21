use crate::effect_ledger::{EffectStatus, ProbeState};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum EffectRuntimeState {
    Prepared,
    Dispatched,
    Uncertain,
    Probing,
    ExecutedAssumed,
    Executed,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct EffectGuardSnapshot {
    pub status: EffectStatus,
    pub probe_state: Option<ProbeState>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ScopeClaim {
    pub scope: String,
    pub is_write: bool,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct TaskScheduleRequest {
    pub active_workers: usize,
    pub tool_busy: bool,
    pub target_scope: String,
    pub requires_write: bool,
    pub doctor_bypass: bool,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum GuardBlockReason {
    MaxWorkersReached,
    ToolBusy,
    AutoRetryBlocked,
    UserRetryBlocked,
    ScopeConflict,
    ScopeQuarantined,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum GuardDecision {
    Allowed,
    Blocked(GuardBlockReason),
}

pub const MAX_CONCURRENT_WORKERS: usize = 5;
pub const AUTO_RETRY_MAX_ATTEMPTS: usize = 1;
pub const USER_RETRY_BLOCKED_STATES: [EffectRuntimeState; 4] = [
    EffectRuntimeState::Uncertain,
    EffectRuntimeState::Dispatched,
    EffectRuntimeState::Probing,
    EffectRuntimeState::ExecutedAssumed,
];

impl ScopeClaim {
    pub fn write(scope: impl Into<String>) -> Self {
        Self {
            scope: scope.into(),
            is_write: true,
        }
    }

    pub fn read(scope: impl Into<String>) -> Self {
        Self {
            scope: scope.into(),
            is_write: false,
        }
    }
}

impl TaskScheduleRequest {
    pub fn write(
        active_workers: usize,
        tool_busy: bool,
        target_scope: impl Into<String>,
    ) -> Self {
        Self {
            active_workers,
            tool_busy,
            target_scope: target_scope.into(),
            requires_write: true,
            doctor_bypass: false,
        }
    }

    pub fn read(
        active_workers: usize,
        tool_busy: bool,
        target_scope: impl Into<String>,
    ) -> Self {
        Self {
            active_workers,
            tool_busy,
            target_scope: target_scope.into(),
            requires_write: false,
            doctor_bypass: false,
        }
    }

    pub fn with_doctor_bypass(mut self) -> Self {
        self.doctor_bypass = true;
        self
    }
}

pub fn runtime_state_from_status(status: EffectStatus) -> EffectRuntimeState {
    runtime_state_from_effect(status, None)
}

pub fn runtime_state_from_effect(
    status: EffectStatus,
    probe_state: Option<ProbeState>,
) -> EffectRuntimeState {
    match (status, probe_state) {
        (EffectStatus::Prepared, _) => EffectRuntimeState::Prepared,
        (EffectStatus::Dispatched, _) => EffectRuntimeState::Dispatched,
        (EffectStatus::Uncertain, Some(ProbeState::Probing)) => EffectRuntimeState::Probing,
        (EffectStatus::Uncertain, _) => EffectRuntimeState::Uncertain,
        (EffectStatus::ExecutedAssumed, _) => EffectRuntimeState::ExecutedAssumed,
        _ => EffectRuntimeState::Executed,
    }
}

pub fn auto_retry_allowed(state: EffectRuntimeState) -> bool {
    matches!(state, EffectRuntimeState::Prepared)
}

pub fn auto_retry_decision(snapshot: &EffectGuardSnapshot) -> GuardDecision {
    if auto_retry_allowed(runtime_state_from_effect(snapshot.status, snapshot.probe_state)) {
        GuardDecision::Allowed
    } else {
        GuardDecision::Blocked(GuardBlockReason::AutoRetryBlocked)
    }
}

pub fn user_retry_allowed(effect_states: &[EffectRuntimeState]) -> bool {
    effect_states
        .iter()
        .all(|state| !USER_RETRY_BLOCKED_STATES.contains(state))
}

pub fn user_retry_decision(effect_snapshots: &[EffectGuardSnapshot]) -> GuardDecision {
    let states: Vec<EffectRuntimeState> = effect_snapshots
        .iter()
        .map(|snapshot| runtime_state_from_effect(snapshot.status, snapshot.probe_state))
        .collect();

    if user_retry_allowed(&states) {
        GuardDecision::Allowed
    } else {
        GuardDecision::Blocked(GuardBlockReason::UserRetryBlocked)
    }
}

pub fn scope_quarantine_trigger(state: EffectRuntimeState) -> bool {
    matches!(state, EffectRuntimeState::ExecutedAssumed)
}

pub fn scope_conflict_decision(scope: &str, active_claims: &[ScopeClaim]) -> GuardDecision {
    if active_claims
        .iter()
        .any(|claim| claim.scope == scope && claim.is_write)
    {
        return GuardDecision::Blocked(GuardBlockReason::ScopeConflict);
    }

    GuardDecision::Allowed
}

pub fn write_scope_decision(
    scope: &str,
    active_claims: &[ScopeClaim],
    quarantined_scopes: &[String],
) -> GuardDecision {
    if quarantined_scopes.iter().any(|item| item == scope) {
        return GuardDecision::Blocked(GuardBlockReason::ScopeQuarantined);
    }

    scope_conflict_decision(scope, active_claims)
}

pub fn schedule_decision(
    request: &TaskScheduleRequest,
    active_claims: &[ScopeClaim],
    quarantined_scopes: &[String],
) -> GuardDecision {
    match worker_slot_decision(request.active_workers) {
        GuardDecision::Allowed => {}
        blocked => return blocked,
    }

    match tool_slot_decision(request.tool_busy) {
        GuardDecision::Allowed => {}
        blocked => return blocked,
    }

    if request.requires_write {
        if !request.doctor_bypass
            && quarantined_scopes
                .iter()
                .any(|item| item == &request.target_scope)
        {
            return GuardDecision::Blocked(GuardBlockReason::ScopeQuarantined);
        }

        return scope_conflict_decision(&request.target_scope, active_claims);
    }

    GuardDecision::Allowed
}

pub fn worker_slot_decision(active_workers: usize) -> GuardDecision {
    if active_workers < MAX_CONCURRENT_WORKERS {
        GuardDecision::Allowed
    } else {
        GuardDecision::Blocked(GuardBlockReason::MaxWorkersReached)
    }
}

pub fn tool_slot_decision(tool_busy: bool) -> GuardDecision {
    if tool_busy {
        GuardDecision::Blocked(GuardBlockReason::ToolBusy)
    } else {
        GuardDecision::Allowed
    }
}

#[cfg(test)]
mod tests {
    use super::{
        auto_retry_decision, runtime_state_from_effect, schedule_decision,
        user_retry_decision, write_scope_decision, EffectGuardSnapshot,
        EffectRuntimeState, GuardBlockReason, GuardDecision, ScopeClaim,
        TaskScheduleRequest, MAX_CONCURRENT_WORKERS,
    };
    use crate::effect_ledger::{EffectStatus, ProbeState};

    #[test]
    fn probing_substate_is_treated_as_blocked_runtime_state() {
        assert_eq!(
            runtime_state_from_effect(EffectStatus::Uncertain, Some(ProbeState::Probing)),
            EffectRuntimeState::Probing
        );
    }

    #[test]
    fn auto_retry_and_user_retry_follow_blocked_states() {
        let prepared = EffectGuardSnapshot {
            status: EffectStatus::Prepared,
            probe_state: None,
        };
        let probing = EffectGuardSnapshot {
            status: EffectStatus::Uncertain,
            probe_state: Some(ProbeState::Probing),
        };

        assert_eq!(auto_retry_decision(&prepared), GuardDecision::Allowed);
        assert_eq!(
            user_retry_decision(&[probing]),
            GuardDecision::Blocked(GuardBlockReason::UserRetryBlocked)
        );
    }

    #[test]
    fn scope_write_rules_block_quarantine_and_conflicts() {
        assert_eq!(
            write_scope_decision(
                "scope:/tmp/demo.txt",
                &[ScopeClaim::write("scope:/tmp/demo.txt")],
                &[],
            ),
            GuardDecision::Blocked(GuardBlockReason::ScopeConflict)
        );
        assert_eq!(
            write_scope_decision(
                "scope:/tmp/demo.txt",
                &[],
                &[String::from("scope:/tmp/demo.txt")],
            ),
            GuardDecision::Blocked(GuardBlockReason::ScopeQuarantined)
        );
        assert_eq!(
            write_scope_decision(
                "scope:/tmp/clean.txt",
                &[ScopeClaim::write("scope:/tmp/demo.txt")],
                &[],
            ),
            GuardDecision::Allowed
        );
    }

    #[test]
    fn schedule_decision_blocks_full_worker_pool_and_busy_tool() {
        assert_eq!(
            schedule_decision(
                &TaskScheduleRequest::write(
                    MAX_CONCURRENT_WORKERS,
                    false,
                    "scope:/tmp/demo.txt",
                ),
                &[],
                &[],
            ),
            GuardDecision::Blocked(GuardBlockReason::MaxWorkersReached)
        );
        assert_eq!(
            schedule_decision(
                &TaskScheduleRequest::write(1, true, "scope:/tmp/demo.txt"),
                &[],
                &[],
            ),
            GuardDecision::Blocked(GuardBlockReason::ToolBusy)
        );
    }

    #[test]
    fn schedule_decision_respects_quarantine_but_allows_doctor_bypass() {
        let quarantined = [String::from("scope:/tmp/demo.txt")];

        assert_eq!(
            schedule_decision(
                &TaskScheduleRequest::write(1, false, "scope:/tmp/demo.txt"),
                &[],
                &quarantined,
            ),
            GuardDecision::Blocked(GuardBlockReason::ScopeQuarantined)
        );
        assert_eq!(
            schedule_decision(
                &TaskScheduleRequest::write(1, false, "scope:/tmp/demo.txt")
                    .with_doctor_bypass(),
                &[],
                &quarantined,
            ),
            GuardDecision::Allowed
        );
        assert_eq!(
            schedule_decision(
                &TaskScheduleRequest::read(1, false, "scope:/tmp/demo.txt"),
                &[],
                &quarantined,
            ),
            GuardDecision::Allowed
        );
    }
}
