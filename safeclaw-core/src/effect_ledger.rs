#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ProbeMode { Auto, None }

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ProbeState { ProbePending, Probing, ProbeFailed, HumanFrozen }

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum EffectStatus {
    Prepared, Dispatched, Executed, Uncertain, ExecutedAssumed,
    Previewed, Confirmed, RolledBack, Compensated, Cancelled, Expired,
}

pub const COMMIT_PROTOCOL_STEPS: [&str; 6] = [
    "prepared", "dispatched", "external_action", "executed", "apply_event", "finalize",
];

pub const CORE_EFFECT_PHASES: [EffectStatus; 5] = [
    EffectStatus::Prepared,
    EffectStatus::Dispatched,
    EffectStatus::Executed,
    EffectStatus::Uncertain,
    EffectStatus::ExecutedAssumed,
];

pub fn crash_outcome_for(mode: ProbeMode) -> EffectStatus {
    match mode {
        ProbeMode::Auto => EffectStatus::Uncertain,
        ProbeMode::None => EffectStatus::ExecutedAssumed,
    }
}
