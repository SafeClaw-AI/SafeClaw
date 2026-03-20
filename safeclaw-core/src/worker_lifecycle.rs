#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum WorkerState {
    Created, Planning, AwaitingConfirmation, Hibernated, Executing, Uncertain,
    Committing, Succeeded, Failed, RollingBack, RolledBack, AwaitingDoctor,
    Repairing, Repaired, RepairFailed, FailedTerminal, Closed,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum WorkerEvent {
    EffectUncertain, ProbeSuccess, ProbeFailure, ProbeAssumed,
    UserRetry, UserReconcileSuccess, UserReconcileFailure,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Transition {
    pub event: WorkerEvent,
    pub from: WorkerState,
    pub to: WorkerState,
    pub guards: &'static [&'static str],
}

pub const USER_RETRY_GUARDS: [&str; 4] = [
    "no_uncertain_effects", "no_dispatched_effects", "no_probing_effects", "no_executed_assumed_effects",
];
pub const RECONCILE_GUARD: [&str; 1] = ["has_executed_assumed_effect"];
pub const TERMINAL_STATES: [WorkerState; 4] = [
    WorkerState::Succeeded, WorkerState::RolledBack, WorkerState::FailedTerminal, WorkerState::Closed,
];
pub const CRITICAL_TRANSITIONS: [Transition; 6] = [
    Transition { event: WorkerEvent::ProbeSuccess, from: WorkerState::Uncertain, to: WorkerState::Committing, guards: &[] },
    Transition { event: WorkerEvent::ProbeFailure, from: WorkerState::Uncertain, to: WorkerState::Failed, guards: &[] },
    Transition { event: WorkerEvent::ProbeAssumed, from: WorkerState::Uncertain, to: WorkerState::Failed, guards: &[] },
    Transition { event: WorkerEvent::UserRetry, from: WorkerState::Failed, to: WorkerState::Planning, guards: &USER_RETRY_GUARDS },
    Transition { event: WorkerEvent::UserReconcileSuccess, from: WorkerState::Failed, to: WorkerState::Committing, guards: &RECONCILE_GUARD },
    Transition { event: WorkerEvent::UserReconcileFailure, from: WorkerState::Failed, to: WorkerState::FailedTerminal, guards: &RECONCILE_GUARD },
];

pub fn transition_for(event: WorkerEvent, from: WorkerState) -> Option<Transition> {
    CRITICAL_TRANSITIONS.into_iter().find(|item| item.event == event && item.from == from)
}
