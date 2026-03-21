use safeclaw_core::effect_ledger::{
    crash_outcome_for, AttemptResultStatus, EffectAction, EffectActor, EffectAttempt,
    EffectRecord, EffectReversibility, EffectStatus, EffectStore, EffectStoreError,
    EffectTier, ProbeMode, RecoveryLease, COMMIT_PROTOCOL_STEPS,
    CORE_EFFECT_PHASES,
};
use safeclaw_core::protocol_version;
use safeclaw_core::spec_map::{CORE_SPEC_BINDINGS, ImplementationStage};
use safeclaw_core::{
    probe_definition_for, ConfirmationAction, ExecutionDisposition,
    ExecutionInterruption, HibernationAction, InMemoryEffectStore,
    InMemoryProbeAdapter, InMemoryStateEngine, InMemoryTaskOrchestrator,
    InMemoryTaskRuntime, InMemoryTaskScheduler, MockEffectStore,
    MockRuntimeStore, MockStateEngine, OrchestratorError, OrchestratorTask,
    PreflightDecision, ProbeReceipt, ProbeReceiptStatus, ReconcileDecision,
    RepairUserAction, RuntimeRestoreError, RuntimeStore, RuntimeStoreError,
    ScheduleIntent, SchedulerError, StateApplyResult, StateEngine,
    StateEvent, StateEngineError, TaskOrchestrator, TaskScheduler,
    DEFAULT_LEASE_TTL_MS,
};
use safeclaw_core::task_concurrency::{
    auto_retry_allowed, auto_retry_decision, runtime_state_from_effect,
    schedule_decision, scope_quarantine_trigger, user_retry_allowed,
    user_retry_decision, write_scope_decision, EffectGuardSnapshot,
    EffectRuntimeState, GuardBlockReason, GuardDecision, ScopeClaim,
    TaskScheduleRequest, MAX_CONCURRENT_WORKERS, USER_RETRY_BLOCKED_STATES,
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
fn probe_catalog_exposes_phase1_supported_contracts() {
    let file_write = probe_definition_for(EffectAction::FileWrite).unwrap();
    assert_eq!(file_write.inputs, &["target_path", "expected_blake3"]);

    let file_delete = probe_definition_for(EffectAction::FileDelete).unwrap();
    assert_eq!(file_delete.inputs, &["target_path"]);

    let network = probe_definition_for(EffectAction::NetworkRequest).unwrap();
    assert_eq!(network.timeout_ms, 10_000);

    assert!(CORE_SPEC_BINDINGS.iter().any(|binding| {
        binding.spec_path == "specs/probes/network_request.json"
            && binding.module_path == "safeclaw_core::recovery::probes"
            && binding.stage == ImplementationStage::TestSkeleton
    }));
    assert!(CORE_SPEC_BINDINGS.iter().any(|binding| {
        binding.spec_path == "specs/schemas/task_concurrency.json"
            && binding.module_path == "safeclaw_core::scheduler"
            && binding.stage == ImplementationStage::TestSkeleton
    }));
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
fn task_schedule_decision_enforces_slots_and_doctor_bypass() {
    let quarantined = [String::from("scope:/tmp/quarantined")];

    assert_eq!(
        schedule_decision(
            &TaskScheduleRequest::write(
                MAX_CONCURRENT_WORKERS,
                false,
                "scope:/tmp/clean.txt",
            ),
            &[],
            &[],
        ),
        GuardDecision::Blocked(GuardBlockReason::MaxWorkersReached)
    );
    assert_eq!(
        schedule_decision(
            &TaskScheduleRequest::write(1, false, "scope:/tmp/quarantined"),
            &[],
            &quarantined,
        ),
        GuardDecision::Blocked(GuardBlockReason::ScopeQuarantined)
    );
    assert_eq!(
        schedule_decision(
            &TaskScheduleRequest::write(1, false, "scope:/tmp/quarantined")
                .with_doctor_bypass(),
            &[],
            &quarantined,
        ),
        GuardDecision::Allowed
    );
}

#[test]
fn scheduler_trait_mock_enforces_queue_rules_and_doctor_bypass() {
    let mut scheduler = InMemoryTaskScheduler::new();
    let ticket = scheduler
        .admit(ScheduleIntent::write("scope:/tmp/demo.txt"))
        .unwrap();
    assert_eq!(scheduler.snapshot().active_workers, 1);

    assert_eq!(
        scheduler.admit(ScheduleIntent::read("scope:/tmp/other.txt")),
        Err(SchedulerError::GuardBlocked(GuardBlockReason::ToolBusy))
    );

    scheduler.release(&ticket).unwrap();
    scheduler.quarantine_scope("scope:/tmp/demo.txt");
    assert_eq!(
        scheduler.admit(ScheduleIntent::write("scope:/tmp/demo.txt")),
        Err(SchedulerError::GuardBlocked(
            GuardBlockReason::ScopeQuarantined,
        ))
    );

    let bypass = scheduler
        .admit(ScheduleIntent::write("scope:/tmp/demo.txt").with_doctor_bypass())
        .unwrap();
    assert_eq!(bypass.target_scope, "scope:/tmp/demo.txt");
}

#[test]
fn orchestrator_trait_mock_claims_renews_and_reaps_expired_leases() {
    let mut orchestrator = InMemoryTaskOrchestrator::new().with_lease_ttl_ms(25);
    orchestrator
        .enqueue(OrchestratorTask::new(
            "task-orch-1",
            ScheduleIntent::write("scope:/tmp/orchestrator.txt"),
            0,
        ))
        .unwrap();

    let claim = orchestrator.claim_next("orch-a", 10).unwrap().unwrap();
    assert_eq!(claim.task.task_id, "task-orch-1");
    assert_eq!(claim.lease.fencing_token, 1);

    let renewed = orchestrator
        .renew_lease(&claim.task.task_id, &claim.lease.lease_id, "orch-a", 20)
        .unwrap();
    assert_eq!(renewed.expires_at_ms, 45);

    let expired = orchestrator.reap_expired_leases(46).unwrap();
    assert_eq!(expired.len(), 1);
    assert_eq!(expired[0].task_id, "task-orch-1");

    let reclaimed = orchestrator.claim_next("orch-b", 47).unwrap().unwrap();
    assert_eq!(reclaimed.task.task_id, "task-orch-1");
    assert_eq!(reclaimed.lease.fencing_token, 2);

    assert_eq!(
        orchestrator.complete(&reclaimed.task.task_id, &reclaimed.lease.lease_id, "orch-a"),
        Err(OrchestratorError::LeaseNotOwned {
            task_id: String::from("task-orch-1"),
            lease_id: reclaimed.lease.lease_id.clone(),
            owner_id: String::from("orch-a"),
        })
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
fn in_memory_runtime_confirmation_checkpoint_can_commit_after_user_confirm() {
    let effect = EffectRecord::new(
        "effect-5",
        "task-3",
        "trace-3",
        "intent-5",
        EffectActor::Worker,
        EffectAction::FileWrite,
        "scope:/tmp/confirm.txt",
        EffectTier::Tier1,
        EffectReversibility::Rollbackable,
        ProbeMode::Auto,
    );

    let mut runtime = InMemoryTaskRuntime::new(effect);
    let waiting = runtime.run_confirmation_checkpoint().unwrap();
    assert_eq!(waiting.worker_state, WorkerState::AwaitingConfirmation);

    let executing = runtime
        .resolve_confirmation(ConfirmationAction::Confirm)
        .unwrap();
    assert_eq!(executing.worker_state, WorkerState::Executing);

    let summary = runtime.continue_execution(ExecutionDisposition::Commit).unwrap();
    assert_eq!(summary.worker_state, WorkerState::Succeeded);
    assert_eq!(summary.effect_status, EffectStatus::Executed);
}

#[test]
fn in_memory_runtime_hibernation_can_resume_or_expire() {
    let effect = EffectRecord::new(
        "effect-5b",
        "task-3b",
        "trace-3b",
        "intent-5b",
        EffectActor::Worker,
        EffectAction::FileWrite,
        "scope:/tmp/hibernate.txt",
        EffectTier::Tier1,
        EffectReversibility::Rollbackable,
        ProbeMode::Auto,
    );

    let mut resume_runtime = InMemoryTaskRuntime::new(effect.clone());
    resume_runtime.run_confirmation_checkpoint().unwrap();
    resume_runtime
        .resolve_confirmation(ConfirmationAction::Timeout)
        .unwrap();
    let resumed = resume_runtime
        .resolve_hibernation(HibernationAction::Resume(PreflightDecision::Permit))
        .unwrap();
    assert_eq!(resumed.worker_state, WorkerState::Executing);

    let mut expire_runtime = InMemoryTaskRuntime::new(effect);
    expire_runtime.run_confirmation_checkpoint().unwrap();
    expire_runtime
        .resolve_confirmation(ConfirmationAction::Timeout)
        .unwrap();
    let expired = expire_runtime
        .resolve_hibernation(HibernationAction::Expire)
        .unwrap();
    assert_eq!(expired.worker_state, WorkerState::FailedTerminal);
}

#[test]
fn in_memory_runtime_uncertain_probe_success_reaches_succeeded() {
    let effect = EffectRecord::new(
        "effect-5c",
        "task-3c",
        "trace-3c",
        "intent-5c",
        EffectActor::Worker,
        EffectAction::NetworkRequest,
        "scope:/tmp/probe.txt",
        EffectTier::Tier2,
        EffectReversibility::Irreversible,
        ProbeMode::Auto,
    );

    let mut runtime = InMemoryTaskRuntime::new(effect);
    runtime
        .run_minimal_flow(PreflightDecision::Permit, ExecutionDisposition::Crash)
        .unwrap();
    runtime.begin_probe().unwrap();
    let summary = runtime.resolve_probe_success().unwrap();

    assert_eq!(summary.worker_state, WorkerState::Succeeded);
    assert_eq!(summary.effect_status, EffectStatus::Executed);
}

#[test]
fn in_memory_runtime_uncertain_probe_failure_cancels_effect_and_reopens_retry() {
    let effect = EffectRecord::new(
        "effect-5c-fail",
        "task-3c-fail",
        "trace-3c-fail",
        "intent-5c-fail",
        EffectActor::Worker,
        EffectAction::NetworkRequest,
        "scope:/tmp/probe-fail.txt",
        EffectTier::Tier2,
        EffectReversibility::Irreversible,
        ProbeMode::Auto,
    );

    let mut runtime = InMemoryTaskRuntime::new(effect);
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
fn in_memory_runtime_probe_adapter_can_drive_success_and_indeterminate_paths() {
    let success_effect = EffectRecord::new(
        "effect-probe-adapter-success",
        "task-probe-adapter-success",
        "trace-probe-adapter-success",
        "intent-probe-adapter-success",
        EffectActor::Worker,
        EffectAction::FileWrite,
        "scope:/tmp/probe-adapter-success.txt",
        EffectTier::Tier1,
        EffectReversibility::Rollbackable,
        ProbeMode::Auto,
    );
    let mut success_runtime = InMemoryTaskRuntime::new(success_effect.clone());
    success_runtime
        .run_minimal_flow(PreflightDecision::Permit, ExecutionDisposition::Crash)
        .unwrap();

    let mut adapter = InMemoryProbeAdapter::new();
    adapter.register(
        success_effect.effect_id.clone(),
        ProbeReceipt::new(
            ProbeReceiptStatus::VerifiedExecuted,
            "file_hash=verified",
            "2026-03-21T00:00:00Z",
        ),
    );
    let success = success_runtime.run_probe_with(&adapter).unwrap();
    assert_eq!(success.worker_state, WorkerState::Succeeded);
    assert_eq!(success.effect_status, EffectStatus::Executed);

    let indeterminate_effect = EffectRecord::new(
        "effect-probe-adapter-indeterminate",
        "task-probe-adapter-indeterminate",
        "trace-probe-adapter-indeterminate",
        "intent-probe-adapter-indeterminate",
        EffectActor::Worker,
        EffectAction::NetworkRequest,
        "scope:https://example.invalid/api",
        EffectTier::Tier2,
        EffectReversibility::Irreversible,
        ProbeMode::Auto,
    );
    let mut indeterminate_runtime = InMemoryTaskRuntime::new(indeterminate_effect.clone());
    indeterminate_runtime
        .run_minimal_flow(PreflightDecision::Permit, ExecutionDisposition::Crash)
        .unwrap();
    adapter.register(
        indeterminate_effect.effect_id.clone(),
        ProbeReceipt::new(
            ProbeReceiptStatus::Indeterminate,
            "timeout",
            "2026-03-21T00:00:01Z",
        ),
    );
    let stalled = indeterminate_runtime.run_probe_with(&adapter).unwrap();
    assert_eq!(stalled.worker_state, WorkerState::Uncertain);
    assert_eq!(stalled.effect_status, EffectStatus::Uncertain);
    assert_eq!(
        indeterminate_runtime.effect.probe_state,
        Some(safeclaw_core::effect_ledger::ProbeState::ProbeFailed)
    );
}

#[test]
fn in_memory_runtime_plan_and_execution_failures_follow_worker_contract() {
    let effect = EffectRecord::new(
        "effect-5d",
        "task-3d",
        "trace-3d",
        "intent-5d",
        EffectActor::Worker,
        EffectAction::FileWrite,
        "scope:/tmp/runtime-failures.txt",
        EffectTier::Tier1,
        EffectReversibility::Rollbackable,
        ProbeMode::Auto,
    );

    let mut planning_runtime = InMemoryTaskRuntime::new(effect.clone());
    let planning_failed = planning_runtime.run_plan_failure().unwrap();
    assert_eq!(planning_failed.worker_state, WorkerState::Failed);

    let mut blacklist_runtime = InMemoryTaskRuntime::new(effect.clone());
    blacklist_runtime.run_confirmation_checkpoint().unwrap();
    blacklist_runtime
        .resolve_confirmation(ConfirmationAction::Confirm)
        .unwrap();
    let waiting = blacklist_runtime
        .interrupt_execution(ExecutionInterruption::NewBlacklistOp)
        .unwrap();
    assert_eq!(waiting.worker_state, WorkerState::AwaitingConfirmation);

    let mut budget_runtime = InMemoryTaskRuntime::new(effect);
    budget_runtime.run_confirmation_checkpoint().unwrap();
    budget_runtime
        .resolve_confirmation(ConfirmationAction::Confirm)
        .unwrap();
    let budget_failed = budget_runtime
        .interrupt_execution(ExecutionInterruption::BudgetExceeded)
        .unwrap();
    assert_eq!(budget_failed.worker_state, WorkerState::Failed);
}

#[test]
fn in_memory_runtime_failed_retry_respects_user_retry_guard() {
    let retryable_effect = EffectRecord::new(
        "effect-5e",
        "task-3e",
        "trace-3e",
        "intent-5e",
        EffectActor::Worker,
        EffectAction::FileWrite,
        "scope:/tmp/retry.txt",
        EffectTier::Tier1,
        EffectReversibility::Rollbackable,
        ProbeMode::Auto,
    );

    let mut retryable_runtime = InMemoryTaskRuntime::new(retryable_effect);
    retryable_runtime.run_confirmation_checkpoint().unwrap();
    retryable_runtime
        .resolve_confirmation(ConfirmationAction::Deny)
        .unwrap();
    let executing = retryable_runtime.retry_failed(PreflightDecision::Permit).unwrap();
    assert_eq!(executing.worker_state, WorkerState::Executing);

    let blocked_effect = EffectRecord::new(
        "effect-5d",
        "task-3d",
        "trace-3d",
        "intent-5d",
        EffectActor::Worker,
        EffectAction::SystemExec,
        "scope:/tmp/retry-blocked",
        EffectTier::Tier2,
        EffectReversibility::Irreversible,
        ProbeMode::None,
    );

    let mut blocked_runtime = InMemoryTaskRuntime::new(blocked_effect);
    blocked_runtime
        .run_minimal_flow(PreflightDecision::Permit, ExecutionDisposition::Crash)
        .unwrap();
    let retry_err = blocked_runtime.retry_failed(PreflightDecision::Permit).unwrap_err();
    assert_eq!(retry_err, safeclaw_core::RuntimeError::GuardBlocked(GuardBlockReason::UserRetryBlocked));
}

#[test]
fn in_memory_runtime_failed_abandon_reaches_terminal() {
    let effect = EffectRecord::new(
        "effect-5e",
        "task-3e",
        "trace-3e",
        "intent-5e",
        EffectActor::Worker,
        EffectAction::FileWrite,
        "scope:/tmp/abandon.txt",
        EffectTier::Tier1,
        EffectReversibility::Rollbackable,
        ProbeMode::Auto,
    );

    let mut runtime = InMemoryTaskRuntime::new(effect);
    runtime.run_confirmation_checkpoint().unwrap();
    runtime
        .resolve_confirmation(ConfirmationAction::SystemBudgetExceeded)
        .unwrap();
    let terminal = runtime.abandon_failed().unwrap();

    assert_eq!(terminal.worker_state, WorkerState::FailedTerminal);
}

#[test]
fn in_memory_runtime_stops_at_uncertain_after_probeable_crash() {
    let effect = EffectRecord::new(
        "effect-5f",
        "task-3f",
        "trace-3f",
        "intent-5f",
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
fn state_engine_contract_is_idempotent_and_fencing_aware() {
    let effect = EffectRecord::new(
        "effect-state",
        "task-state",
        "trace-state",
        "intent-state",
        EffectActor::Worker,
        EffectAction::FileWrite,
        "scope:/tmp/state.txt",
        EffectTier::Tier1,
        EffectReversibility::Rollbackable,
        ProbeMode::Auto,
    );

    let mut runtime = InMemoryTaskRuntime::new(effect);
    runtime
        .run_minimal_flow(PreflightDecision::Permit, ExecutionDisposition::Commit)
        .unwrap();

    let mut engine = InMemoryStateEngine::new();
    let event = runtime.state_event("evt-state-1", "worker");
    assert_eq!(engine.apply_event(event.clone()).unwrap(), StateApplyResult::Applied);
    assert_eq!(engine.apply_event(event).unwrap(), StateApplyResult::DuplicateIgnored);
    assert_eq!(engine.event_count(), 1);

    let stale = StateEvent {
        state_event_id: String::from("evt-state-stale"),
        task_id: String::from("task-state"),
        worker_state: WorkerState::Failed,
        effect_status: EffectStatus::Cancelled,
        probe_state: None,
        fencing_token: 0,
        triggered_by: String::from("doctor"),
        at: String::from("2026-03-21T00:00:01Z"),
    };
    assert_eq!(
        engine.apply_event(stale),
        Err(StateEngineError::StaleFencingToken {
            current: 1,
            provided: 0,
        })
    );
}

#[test]
fn state_engine_snapshot_can_restore_uncertain_and_executed_assumed_runtime() {
    let uncertain_effect = EffectRecord::new(
        "effect-restore-1",
        "task-restore-1",
        "trace-restore-1",
        "intent-restore-1",
        EffectActor::Worker,
        EffectAction::NetworkRequest,
        "scope:/tmp/restore-uncertain.txt",
        EffectTier::Tier2,
        EffectReversibility::Irreversible,
        ProbeMode::Auto,
    );
    let mut uncertain_runtime = InMemoryTaskRuntime::new(uncertain_effect.clone());
    uncertain_runtime
        .run_minimal_flow(PreflightDecision::Permit, ExecutionDisposition::Crash)
        .unwrap();

    let mut engine = InMemoryStateEngine::new();
    engine
        .apply_event(uncertain_runtime.state_event("evt-restore-uncertain", "worker"))
        .unwrap();
    let restored_uncertain = InMemoryTaskRuntime::restore_from_snapshot(
        uncertain_effect,
        engine.snapshot("task-restore-1").unwrap(),
        None,
    );
    assert_eq!(restored_uncertain.worker_state, WorkerState::Uncertain);
    assert_eq!(restored_uncertain.effect.status, EffectStatus::Uncertain);

    let assumed_effect = EffectRecord::new(
        "effect-restore-2",
        "task-restore-2",
        "trace-restore-2",
        "intent-restore-2",
        EffectActor::Worker,
        EffectAction::SystemExec,
        "scope:/tmp/restore-assumed.txt",
        EffectTier::Tier2,
        EffectReversibility::Irreversible,
        ProbeMode::None,
    );
    let mut assumed_runtime = InMemoryTaskRuntime::new(assumed_effect.clone());
    assumed_runtime
        .run_minimal_flow(PreflightDecision::Permit, ExecutionDisposition::Crash)
        .unwrap();
    engine
        .apply_event(assumed_runtime.state_event("evt-restore-assumed", "worker"))
        .unwrap();
    let restored_assumed = InMemoryTaskRuntime::restore_from_snapshot(
        assumed_effect,
        engine.snapshot("task-restore-2").unwrap(),
        None,
    );
    assert_eq!(restored_assumed.worker_state, WorkerState::Failed);
    assert_eq!(restored_assumed.effect.status, EffectStatus::ExecutedAssumed);
}

#[test]
fn state_engine_trait_contract_roundtrips_through_mock_adapter() {
    let effect = EffectRecord::new(
        "effect-state-trait",
        "task-state-trait",
        "trace-state-trait",
        "intent-state-trait",
        EffectActor::Worker,
        EffectAction::FileWrite,
        "scope:/tmp/state-trait.txt",
        EffectTier::Tier1,
        EffectReversibility::Rollbackable,
        ProbeMode::Auto,
    );
    let mut runtime = InMemoryTaskRuntime::new(effect.clone());
    runtime
        .run_minimal_flow(PreflightDecision::Permit, ExecutionDisposition::Crash)
        .unwrap();

    let mut engine = MockStateEngine::new();
    assert_eq!(
        runtime.persist_state(&mut engine, "evt-trait-1", "worker").unwrap(),
        StateApplyResult::Applied
    );

    let snapshot = StateEngine::load_snapshot(&engine, "task-state-trait")
        .unwrap()
        .expect("snapshot must exist");
    assert_eq!(snapshot.worker_state, runtime.worker_state);
    assert_eq!(snapshot.effect_status, runtime.effect.status);

    let restored = InMemoryTaskRuntime::restore_from_engine(
        effect,
        &engine,
        "task-state-trait",
        None,
    )
    .unwrap()
    .expect("runtime must restore from trait-backed engine");

    assert_eq!(restored.worker_state, runtime.worker_state);
    assert_eq!(restored.effect.status, runtime.effect.status);
}

#[test]
fn state_engine_trait_surfaces_backend_unavailable_errors() {
    struct FailingStateEngine;

    impl StateEngine for FailingStateEngine {
        fn apply_event(
            &mut self,
            _event: StateEvent,
        ) -> Result<StateApplyResult, StateEngineError> {
            Err(StateEngineError::BackendUnavailable {
                operation: "apply_event",
            })
        }

        fn load_snapshot(
            &self,
            _task_id: &str,
        ) -> Result<Option<safeclaw_core::TaskSnapshot>, StateEngineError> {
            Err(StateEngineError::BackendUnavailable {
                operation: "load_snapshot",
            })
        }
    }

    let effect = EffectRecord::new(
        "effect-state-fail",
        "task-state-fail",
        "trace-state-fail",
        "intent-state-fail",
        EffectActor::Worker,
        EffectAction::FileWrite,
        "scope:/tmp/state-fail.txt",
        EffectTier::Tier1,
        EffectReversibility::Rollbackable,
        ProbeMode::Auto,
    );
    let runtime = InMemoryTaskRuntime::new(effect.clone());
    let mut engine = FailingStateEngine;

    assert_eq!(
        runtime.persist_state(&mut engine, "evt-state-fail", "worker"),
        Err(StateEngineError::BackendUnavailable {
            operation: "apply_event",
        })
    );
    assert_eq!(
        InMemoryTaskRuntime::restore_from_engine(effect, &engine, "task-state-fail", None),
        Err(StateEngineError::BackendUnavailable {
            operation: "load_snapshot",
        })
    );
}

#[test]
fn effect_store_trait_contract_roundtrips_through_mock_adapter() {
    let effect = EffectRecord::new(
        "effect-store-trait",
        "task-store-trait",
        "trace-store-trait",
        "intent-store-trait",
        EffectActor::Worker,
        EffectAction::FileWrite,
        "scope:/tmp/store-trait.txt",
        EffectTier::Tier1,
        EffectReversibility::Rollbackable,
        ProbeMode::None,
    );
    let lease = RecoveryLease::new("lease-store-trait", "doctor-a", 7, 0, DEFAULT_LEASE_TTL_MS);
    let mut attempt = EffectAttempt::next_for_effect(
        &[],
        "attempt-store-trait",
        effect.effect_id.clone(),
        "2026-03-21T00:00:00Z",
        &lease,
        0,
    )
    .unwrap();
    attempt
        .record_result(AttemptResultStatus::Crash, &lease, 0)
        .unwrap();

    let mut store = MockEffectStore::new();
    store.save_effect(&effect).unwrap();
    store.save_lease(&effect.task_id, &lease).unwrap();
    store.save_attempt(&attempt).unwrap();

    assert_eq!(EffectStore::load_effect(&store, &effect.effect_id).unwrap(), Some(effect));
    assert_eq!(
        EffectStore::load_latest_lease(&store, "task-store-trait")
            .unwrap()
            .unwrap(),
        lease
    );
    assert_eq!(EffectStore::list_attempts(&store, "effect-store-trait").unwrap(), vec![attempt]);
}

#[test]
fn runtime_store_trait_contract_roundtrips_through_mock_adapter() {
    let effect = EffectRecord::new(
        "effect-runtime-trait",
        "task-runtime-trait",
        "trace-runtime-trait",
        "intent-runtime-trait",
        EffectActor::Worker,
        EffectAction::FileWrite,
        "scope:/tmp/runtime-trait.txt",
        EffectTier::Tier1,
        EffectReversibility::Rollbackable,
        ProbeMode::None,
    );
    let mut runtime = InMemoryTaskRuntime::new(effect);
    runtime
        .run_minimal_flow(PreflightDecision::Permit, ExecutionDisposition::Commit)
        .unwrap();

    let mut store = MockRuntimeStore::new();
    assert_eq!(
        store.persist_runtime(&runtime, "evt-runtime-trait", "runtime-store").unwrap(),
        StateApplyResult::Applied
    );
    let restored = store
        .load_runtime("task-runtime-trait", "effect-runtime-trait")
        .unwrap()
        .unwrap();

    assert_eq!(restored.worker_state, runtime.worker_state);
    assert_eq!(restored.effect.status, runtime.effect.status);
}

#[test]
fn runtime_store_trait_surfaces_backend_unavailable_errors() {
    struct FailingRuntimeStore;

    impl RuntimeStore for FailingRuntimeStore {
        fn persist_runtime(
            &mut self,
            _runtime: &InMemoryTaskRuntime,
            _state_event_id: &str,
            _triggered_by: &str,
        ) -> Result<StateApplyResult, RuntimeStoreError> {
            Err(RuntimeStoreError::BackendUnavailable {
                operation: "persist_runtime",
            })
        }

        fn load_runtime(
            &self,
            _task_id: &str,
            _effect_id: &str,
        ) -> Result<Option<InMemoryTaskRuntime>, RuntimeStoreError> {
            Err(RuntimeStoreError::BackendUnavailable {
                operation: "load_runtime",
            })
        }
    }

    let store = FailingRuntimeStore;
    assert_eq!(
        store.load_runtime("task-runtime-fail", "effect-runtime-fail"),
        Err(RuntimeStoreError::BackendUnavailable {
            operation: "load_runtime",
        })
    );
}
#[test]
fn runtime_restore_from_effect_store_and_state_engine_roundtrips() {
    let effect = EffectRecord::new(
        "effect-store-restore",
        "task-store-restore",
        "trace-store-restore",
        "intent-store-restore",
        EffectActor::Worker,
        EffectAction::FileWrite,
        "scope:/tmp/store-restore.txt",
        EffectTier::Tier1,
        EffectReversibility::Rollbackable,
        ProbeMode::None,
    );
    let mut runtime = InMemoryTaskRuntime::new(effect.clone());
    runtime
        .run_minimal_flow(PreflightDecision::Permit, ExecutionDisposition::Crash)
        .unwrap();

    let mut engine = InMemoryStateEngine::new();
    let mut store = InMemoryEffectStore::new();
    runtime.persist_state(&mut engine, "evt-store-restore", "worker").unwrap();
    store.save_effect(&runtime.effect).unwrap();
    if let Some(lease) = runtime.current_recovery_lease().cloned() {
        store.save_lease(&runtime.effect.task_id, &lease).unwrap();
    }
    for attempt in &runtime.attempts {
        store.save_attempt(attempt).unwrap();
    }

    let restored = InMemoryTaskRuntime::restore_from_stores(
        &store,
        &engine,
        "task-store-restore",
        "effect-store-restore",
    )
    .unwrap()
    .expect("runtime must restore from stores");

    assert_eq!(restored.worker_state, runtime.worker_state);
    assert_eq!(restored.effect.status, runtime.effect.status);
    assert_eq!(restored.attempts, runtime.attempts);
}

#[test]
fn effect_store_trait_surfaces_backend_unavailable_errors() {
    struct FailingEffectStore;

    impl EffectStore for FailingEffectStore {
        fn save_effect(&mut self, _effect: &EffectRecord) -> Result<(), EffectStoreError> {
            Err(EffectStoreError::BackendUnavailable { operation: "save_effect" })
        }

        fn load_effect(&self, _effect_id: &str) -> Result<Option<EffectRecord>, EffectStoreError> {
            Err(EffectStoreError::BackendUnavailable { operation: "load_effect" })
        }

        fn save_lease(&mut self, _task_id: &str, _lease: &RecoveryLease) -> Result<(), EffectStoreError> {
            Err(EffectStoreError::BackendUnavailable { operation: "save_lease" })
        }

        fn load_latest_lease(&self, _task_id: &str) -> Result<Option<RecoveryLease>, EffectStoreError> {
            Err(EffectStoreError::BackendUnavailable { operation: "load_latest_lease" })
        }

        fn list_leases(&self, _task_id: &str) -> Result<Vec<RecoveryLease>, EffectStoreError> {
            Err(EffectStoreError::BackendUnavailable { operation: "list_leases" })
        }

        fn save_attempt(&mut self, _attempt: &EffectAttempt) -> Result<(), EffectStoreError> {
            Err(EffectStoreError::BackendUnavailable { operation: "save_attempt" })
        }

        fn list_attempts(&self, _effect_id: &str) -> Result<Vec<EffectAttempt>, EffectStoreError> {
            Err(EffectStoreError::BackendUnavailable { operation: "list_attempts" })
        }
    }

    let effect = EffectRecord::new(
        "effect-store-fail",
        "task-store-fail",
        "trace-store-fail",
        "intent-store-fail",
        EffectActor::Worker,
        EffectAction::FileWrite,
        "scope:/tmp/store-fail.txt",
        EffectTier::Tier1,
        EffectReversibility::Rollbackable,
        ProbeMode::None,
    );
    let runtime = InMemoryTaskRuntime::new(effect);
    let mut engine = InMemoryStateEngine::new();
    runtime
        .persist_state(&mut engine, "evt-store-fail", "worker")
        .unwrap();
    let store = FailingEffectStore;
    assert_eq!(
        InMemoryTaskRuntime::restore_from_stores(
            &store,
            &engine,
            "task-store-fail",
            "effect-store-fail",
        ),
        Err(RuntimeRestoreError::EffectStore(EffectStoreError::BackendUnavailable {
            operation: "load_effect",
        }))
    );
}

#[test]
fn persisted_runtime_can_restart_and_finish_recovery_paths() {
    let uncertain_effect = EffectRecord::new(
        "effect-restart-1",
        "task-restart-1",
        "trace-restart-1",
        "intent-restart-1",
        EffectActor::Worker,
        EffectAction::NetworkRequest,
        "scope:/tmp/restart-uncertain.txt",
        EffectTier::Tier2,
        EffectReversibility::Irreversible,
        ProbeMode::Auto,
    );
    let mut uncertain_runtime = InMemoryTaskRuntime::new(uncertain_effect.clone());
    uncertain_runtime
        .run_minimal_flow(PreflightDecision::Permit, ExecutionDisposition::Crash)
        .unwrap();
    let mut engine = InMemoryStateEngine::new();
    uncertain_runtime
        .persist_state(&mut engine, "evt-restart-1", "worker")
        .unwrap();
    let mut restarted_uncertain = InMemoryTaskRuntime::restore_from_snapshot(
        uncertain_effect,
        engine.snapshot("task-restart-1").unwrap(),
        None,
    );
    restarted_uncertain.begin_probe().unwrap();
    let success = restarted_uncertain.resolve_probe_success().unwrap();
    assert_eq!(success.worker_state, WorkerState::Succeeded);

    let assumed_effect = EffectRecord::new(
        "effect-restart-2",
        "task-restart-2",
        "trace-restart-2",
        "intent-restart-2",
        EffectActor::Worker,
        EffectAction::SystemExec,
        "scope:/tmp/restart-assumed.txt",
        EffectTier::Tier2,
        EffectReversibility::Irreversible,
        ProbeMode::None,
    );
    let mut assumed_runtime = InMemoryTaskRuntime::new(assumed_effect.clone());
    assumed_runtime
        .run_minimal_flow(PreflightDecision::Permit, ExecutionDisposition::Crash)
        .unwrap();
    assumed_runtime
        .persist_state(&mut engine, "evt-restart-2", "worker")
        .unwrap();
    let mut restarted_assumed = InMemoryTaskRuntime::restore_from_snapshot(
        assumed_effect,
        engine.snapshot("task-restart-2").unwrap(),
        None,
    );
    let reconcile = restarted_assumed.reconcile_assumed(ReconcileDecision::Success).unwrap();
    assert_eq!(reconcile.worker_state, WorkerState::Succeeded);
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

#[test]
fn in_memory_runtime_doctor_repair_can_close_cleanly() {
    let effect = EffectRecord::new(
        "effect-10",
        "task-8",
        "trace-8",
        "intent-10",
        EffectActor::Worker,
        EffectAction::FileWrite,
        "scope:/tmp/repair-close.txt",
        EffectTier::Tier1,
        EffectReversibility::Rollbackable,
        ProbeMode::Auto,
    );

    let mut runtime = InMemoryTaskRuntime::new(effect);
    let summary = runtime
        .run_doctor_repair_flow(PreflightDecision::Permit, true)
        .unwrap();
    assert_eq!(summary.worker_state, WorkerState::Repaired);
    assert_eq!(summary.effect_status, EffectStatus::Executed);

    let closed = runtime.resolve_repair_state(RepairUserAction::Close).unwrap();
    assert_eq!(closed.worker_state, WorkerState::Closed);
    assert_eq!(closed.effect_status, EffectStatus::Executed);
}

#[test]
fn in_memory_runtime_repair_failed_can_retry_repair() {
    let effect = EffectRecord::new(
        "effect-11",
        "task-9",
        "trace-9",
        "intent-11",
        EffectActor::Worker,
        EffectAction::FileWrite,
        "scope:/tmp/repair-retry.txt",
        EffectTier::Tier1,
        EffectReversibility::Rollbackable,
        ProbeMode::Auto,
    );

    let mut runtime = InMemoryTaskRuntime::new(effect);
    let summary = runtime
        .run_doctor_repair_flow(PreflightDecision::Permit, false)
        .unwrap();
    assert_eq!(summary.worker_state, WorkerState::RepairFailed);
    assert_eq!(summary.effect_status, EffectStatus::Executed);

    let awaiting_doctor = runtime
        .resolve_repair_state(RepairUserAction::RetryRepair)
        .unwrap();
    assert_eq!(awaiting_doctor.worker_state, WorkerState::AwaitingDoctor);
    assert_eq!(awaiting_doctor.effect_status, EffectStatus::Executed);
}

#[test]
fn in_memory_runtime_repair_failed_can_abandon() {
    let effect = EffectRecord::new(
        "effect-12",
        "task-10",
        "trace-10",
        "intent-12",
        EffectActor::Worker,
        EffectAction::FileWrite,
        "scope:/tmp/repair-abandon.txt",
        EffectTier::Tier1,
        EffectReversibility::Rollbackable,
        ProbeMode::Auto,
    );

    let mut runtime = InMemoryTaskRuntime::new(effect);
    let summary = runtime
        .run_doctor_repair_flow(PreflightDecision::Permit, false)
        .unwrap();
    assert_eq!(summary.worker_state, WorkerState::RepairFailed);
    assert_eq!(summary.effect_status, EffectStatus::Executed);

    let failed_terminal = runtime.resolve_repair_state(RepairUserAction::Abandon).unwrap();
    assert_eq!(failed_terminal.worker_state, WorkerState::FailedTerminal);
    assert_eq!(failed_terminal.effect_status, EffectStatus::Executed);
}










