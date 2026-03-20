use safeclaw_core::effect_ledger::{crash_outcome_for, EffectStatus, ProbeMode, COMMIT_PROTOCOL_STEPS, CORE_EFFECT_PHASES};
use safeclaw_core::protocol_version;
use safeclaw_core::spec_map::{CORE_SPEC_BINDINGS, ImplementationStage};
use safeclaw_core::task_concurrency::{
    auto_retry_allowed, scope_quarantine_trigger, user_retry_allowed, EffectRuntimeState,
    USER_RETRY_BLOCKED_STATES,
};
use safeclaw_core::worker_lifecycle::{
    transition_for, WorkerEvent, WorkerState, TERMINAL_STATES, USER_RETRY_GUARDS,
};

#[test]
fn protocol_version_matches_repo_anchor() {
    assert_eq!(protocol_version(), "3.2.0");
}

#[test]
fn effect_ledger_preserves_core_four_phase_statuses_and_six_steps() {
    assert_eq!(CORE_EFFECT_PHASES.len(), 5);
    assert!(CORE_EFFECT_PHASES.contains(&EffectStatus::Uncertain));
    assert!(CORE_EFFECT_PHASES.contains(&EffectStatus::ExecutedAssumed));
    assert_eq!(COMMIT_PROTOCOL_STEPS.len(), 6);
}

#[test]
fn probe_mode_none_escalates_to_executed_assumed() {
    assert_eq!(crash_outcome_for(ProbeMode::None), EffectStatus::ExecutedAssumed);
}

#[test]
fn user_retry_guard_blocks_uncertain_and_probing_effects() {
    assert!(!user_retry_allowed(&USER_RETRY_BLOCKED_STATES));
    assert!(!auto_retry_allowed(EffectRuntimeState::ExecutedAssumed));
    assert!(auto_retry_allowed(EffectRuntimeState::Prepared));
}

#[test]
fn scope_quarantine_and_reconcile_transitions_exist() {
    assert!(scope_quarantine_trigger(EffectRuntimeState::ExecutedAssumed));
    let success = transition_for(WorkerEvent::UserReconcileSuccess, WorkerState::Failed).unwrap();
    assert_eq!(success.to, WorkerState::Committing);
    let failure = transition_for(WorkerEvent::UserReconcileFailure, WorkerState::Failed).unwrap();
    assert_eq!(failure.to, WorkerState::FailedTerminal);
}

#[test]
fn worker_retry_guards_and_spec_bindings_are_explicit() {
    assert_eq!(USER_RETRY_GUARDS.len(), 4);
    assert!(TERMINAL_STATES.contains(&WorkerState::Closed));
    assert!(CORE_SPEC_BINDINGS.iter().any(|binding| {
        binding.spec_path == "specs/schemas/effect_ledger.json"
            && binding.stage == ImplementationStage::RuntimeSlice
    }));
}
