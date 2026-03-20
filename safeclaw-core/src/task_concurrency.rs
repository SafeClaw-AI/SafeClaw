use crate::effect_ledger::EffectStatus;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum EffectRuntimeState {
    Prepared,
    Dispatched,
    Uncertain,
    Probing,
    ExecutedAssumed,
    Executed,
}

pub const MAX_CONCURRENT_WORKERS: usize = 5;
pub const AUTO_RETRY_MAX_ATTEMPTS: usize = 1;
pub const USER_RETRY_BLOCKED_STATES: [EffectRuntimeState; 4] = [
    EffectRuntimeState::Uncertain,
    EffectRuntimeState::Dispatched,
    EffectRuntimeState::Probing,
    EffectRuntimeState::ExecutedAssumed,
];

pub fn runtime_state_from_status(status: EffectStatus) -> EffectRuntimeState {
    match status {
        EffectStatus::Prepared => EffectRuntimeState::Prepared,
        EffectStatus::Dispatched => EffectRuntimeState::Dispatched,
        EffectStatus::Uncertain => EffectRuntimeState::Uncertain,
        EffectStatus::ExecutedAssumed => EffectRuntimeState::ExecutedAssumed,
        _ => EffectRuntimeState::Executed,
    }
}

pub fn auto_retry_allowed(state: EffectRuntimeState) -> bool {
    matches!(state, EffectRuntimeState::Prepared)
}

pub fn user_retry_allowed(effect_states: &[EffectRuntimeState]) -> bool {
    effect_states.iter().all(|state| !USER_RETRY_BLOCKED_STATES.contains(state))
}

pub fn scope_quarantine_trigger(state: EffectRuntimeState) -> bool {
    matches!(state, EffectRuntimeState::ExecutedAssumed)
}
