use safeclaw_core::effect_ledger::{
    crash_outcome_for, AttemptResultStatus, EffectAction, EffectActor, EffectAttempt,
    EffectRecord, EffectReversibility, EffectStatus, EffectTier, ProbeMode,
    RecoveryLease, COMMIT_PROTOCOL_STEPS, CORE_EFFECT_PHASES,
};
use safeclaw_core::protocol_version;
use safeclaw_core::spec_map::{CORE_SPEC_BINDINGS, ImplementationStage};
use safeclaw_core::{
    ExecutionDisposition, InMemoryTaskRuntime, PreflightDecision, ReconcileDecision,
    DEFAULT_LEASE_TTL_MS,
};
use safeclaw_core::task_concurrency::{
    auto_retry_allowed, auto_retry_decision, runtime_state_from_effect,
    scope_quarantine_trigger, user_retry_allowed, user_retry_decision,
    write_scope_decision, EffectGuardSnapshot, EffectRuntimeState, GuardBlockReason,
    GuardDecision, ScopeClaim, USER_RETRY_BLOCKED_STATES,
};
use safeclaw_core::worker_lifecycle::{
    transition_for, WorkerEvent, WorkerState, TERMINAL_STATES, TRANSITIONS,
    USER_RETRY_GUARDS,
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

#[test]
fn worker_transition_table_covers_full_spec_paths() {
    assert_eq!(TRANSITIONS.len(), 35);

    let accepted = transition_for(WorkerEvent::TaskAccepted, WorkerState::Created).unwrap();
    assert_eq!(accepted.to, WorkerState::Planning);

    let persisted = transition_for(WorkerEvent::ResultsPersisted, WorkerState::Committing).unwrap();
    assert_eq!(persisted.to, WorkerState::Succeeded);
}

#[test]
fn worker_transition_table_rejects_invalid_moves() {
    assert!(transition_for(WorkerEvent::UserConfirmed, WorkerState::Created).is_none());
    assert!(transition_for(WorkerEvent::UserRetry, WorkerState::Succeeded).is_none());
}

#[test]
fn effect_ledger_record_tracks_append_only_status_history() {
    let mut record = EffectRecord::new(
        "effect-1",
        "task-1",
        "trace-1",
        "intent-1",
        EffectActor::Worker,
        EffectAction::FileWrite,
        "scope:/tmp/demo.txt",
        EffectTier::Tier1,
        EffectReversibility::Rollbackable,
        ProbeMode::Auto,
    );

    record
        .transition_to(
            EffectStatus::Dispatched,
            "2026-03-21T00:00:00Z",
            "worker",
            "dispatch",
        )
        .unwrap();
    record
        .transition_to(
            EffectStatus::Executed,
            "2026-03-21T00:00:01Z",
            "worker",
            "external_confirmed",
        )
        .unwrap();

    assert_eq!(record.status, EffectStatus::Executed);
    assert_eq!(record.transitions.len(), 2);
    assert_eq!(record.transitions[0].from_status, EffectStatus::Prepared);
    assert_eq!(record.transitions[0].to_status, EffectStatus::Dispatched);
    assert_eq!(record.transitions[1].from_status, EffectStatus::Dispatched);
    assert_eq!(record.transitions[1].to_status, EffectStatus::Executed);
}

#[test]
fn effect_ledger_record_uses_probe_mode_for_crash_outcomes() {
    let mut auto_probe = EffectRecord::new(
        "effect-2",
        "task-1",
        "trace-1",
        "intent-2",
        EffectActor::Worker,
        EffectAction::NetworkRequest,
        "https://safeclaw.local/api",
        EffectTier::Tier2,
        EffectReversibility::Irreversible,
        ProbeMode::Auto,
    );
    auto_probe
        .transition_to(
            EffectStatus::Dispatched,
            "2026-03-21T00:00:00Z",
            "worker",
            "dispatch",
        )
        .unwrap();

    let mut no_probe = EffectRecord::new(
        "effect-3",
        "task-1",
        "trace-1",
        "intent-3",
        EffectActor::Worker,
        EffectAction::SystemExec,
        "cmd:demo",
        EffectTier::Tier2,
        EffectReversibility::Irreversible,
        ProbeMode::None,
    );
    no_probe
        .transition_to(
            EffectStatus::Dispatched,
            "2026-03-21T00:00:00Z",
            "worker",
            "dispatch",
        )
        .unwrap();

    assert_eq!(
        auto_probe
            .record_crash_outcome("2026-03-21T00:00:01Z", "worker", "sidecar_crash")
            .unwrap(),
        EffectStatus::Uncertain
    );
    assert_eq!(
        no_probe
            .record_crash_outcome("2026-03-21T00:00:01Z", "worker", "process_crash")
            .unwrap(),
        EffectStatus::ExecutedAssumed
    );
}

#[test]
fn task_concurrency_guard_evaluator_blocks_probing_retry_and_quarantined_writes() {
    let probing_effect = EffectGuardSnapshot {
        status: EffectStatus::Uncertain,
        probe_state: Some(safeclaw_core::effect_ledger::ProbeState::Probing),
    };

    assert_eq!(
        runtime_state_from_effect(probing_effect.status, probing_effect.probe_state),
        EffectRuntimeState::Probing
    );
    assert_eq!(
        user_retry_decision(&[probing_effect.clone()]),
        GuardDecision::Blocked(GuardBlockReason::UserRetryBlocked)
    );
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
}

#[test]
fn task_concurrency_guard_evaluator_allows_prepared_auto_retry_and_clean_scope() {
    let prepared_effect = EffectGuardSnapshot {
        status: EffectStatus::Prepared,
        probe_state: None,
    };

    assert_eq!(auto_retry_decision(&prepared_effect), GuardDecision::Allowed);
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
fn in_memory_runtime_commits_after_permitted_preflight() {
    let effect = EffectRecord::new(
        "effect-4",
        "task-2",
        "trace-2",
        "intent-4",
        EffectActor::Worker,
        EffectAction::FileWrite,
        "scope:/tmp/commit.txt",
        EffectTier::Tier1,
        EffectReversibility::Rollbackable,
        ProbeMode::Auto,
    );

    let mut runtime = InMemoryTaskRuntime::new(effect);
    let summary = runtime
        .run_minimal_flow(PreflightDecision::Permit, ExecutionDisposition::Commit)
        .unwrap();

    assert_eq!(summary.worker_state, WorkerState::Succeeded);
    assert_eq!(summary.effect_status, EffectStatus::Executed);
}

#[test]
fn in_memory_runtime_stops_at_uncertain_after_probeable_crash() {
    let effect = EffectRecord::new(
        "effect-5",
        "task-3",
        "trace-3",
        "intent-5",
        EffectActor::Worker,
        EffectAction::NetworkRequest,
        "scope:/tmp/uncertain",
        EffectTier::Tier2,
        EffectReversibility::Irreversible,
        ProbeMode::Auto,
    );

    let mut runtime = InMemoryTaskRuntime::new(effect);
    let summary = runtime
        .run_minimal_flow(PreflightDecision::Permit, ExecutionDisposition::Crash)
        .unwrap();

    assert_eq!(summary.worker_state, WorkerState::Uncertain);
    assert_eq!(summary.effect_status, EffectStatus::Uncertain);
}

#[test]
fn effect_attempt_requires_active_matching_lease() {
    let lease = RecoveryLease::new("lease-1", "doctor-a", 3, 0, DEFAULT_LEASE_TTL_MS);
    let mut attempt = EffectAttempt::next_for_effect(
        &[],
        "attempt-1",
        "effect-lease-1",
        "2026-03-21T00:00:00Z",
        &lease,
        1,
    )
    .unwrap();

    attempt
        .record_result(AttemptResultStatus::Crash, &lease, 10)
        .unwrap();
    assert_eq!(attempt.result_status, Some(AttemptResultStatus::Crash));
}

#[test]
fn compensation_effect_keeps_independent_identity() {
    let source = EffectRecord::new(
        "effect-6",
        "task-4",
        "trace-4",
        "intent-6",
        EffectActor::Worker,
        EffectAction::FileWrite,
        "scope:/tmp/source.txt",
        EffectTier::Tier1,
        EffectReversibility::Compensatable,
        ProbeMode::Auto,
    );
    let compensation = source.spawn_compensation(
        "effect-6-comp",
        "intent-6-comp",
        EffectActor::Doctor,
        EffectAction::FileWrite,
        "scope:/tmp/source.txt",
        EffectReversibility::Rollbackable,
        ProbeMode::Auto,
    );

    assert_eq!(compensation.status, EffectStatus::Prepared);
    assert_eq!(compensation.compensates_effect_id, Some(String::from("effect-6")));
    assert_ne!(compensation.effect_id, source.effect_id);
}

#[test]
fn in_memory_runtime_reconcile_success_releases_quarantine() {
    let effect = EffectRecord::new(
        "effect-7",
        "task-5",
        "trace-5",
        "intent-7",
        EffectActor::Worker,
        EffectAction::SystemExec,
        "scope:/tmp/reconcile",
        EffectTier::Tier2,
        EffectReversibility::Irreversible,
        ProbeMode::None,
    );

    let mut runtime = InMemoryTaskRuntime::new(effect);
    runtime
        .run_minimal_flow(PreflightDecision::Permit, ExecutionDisposition::Crash)
        .unwrap();
    runtime.advance_clock(DEFAULT_LEASE_TTL_MS + 1);

    let summary = runtime.reconcile_assumed(ReconcileDecision::Success).unwrap();

    assert_eq!(summary.worker_state, WorkerState::Succeeded);
    assert_eq!(summary.effect_status, EffectStatus::Executed);
    assert!(summary.quarantined_scopes.is_empty());
}

#[test]
fn in_memory_runtime_rolls_back_after_persist_error() {
    let effect = EffectRecord::new(
        "effect-8",
        "task-6",
        "trace-6",
        "intent-8",
        EffectActor::Worker,
        EffectAction::FileWrite,
        "scope:/tmp/rollback.txt",
        EffectTier::Tier1,
        EffectReversibility::Rollbackable,
        ProbeMode::Auto,
    );

    let mut runtime = InMemoryTaskRuntime::new(effect);
    let summary = runtime
        .run_persist_error_recovery(PreflightDecision::Permit)
        .unwrap();

    assert_eq!(summary.worker_state, WorkerState::RolledBack);
    assert_eq!(summary.effect_status, EffectStatus::RolledBack);
    assert_eq!(summary.compensation_count, 0);
}

#[test]
fn in_memory_runtime_spawns_compensation_after_persist_error() {
    let effect = EffectRecord::new(
        "effect-9",
        "task-7",
        "trace-7",
        "intent-9",
        EffectActor::Worker,
        EffectAction::FileWrite,
        "scope:/tmp/compensate.txt",
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
}
