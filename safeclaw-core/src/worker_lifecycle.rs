#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum WorkerState {
    Created,
    Planning,
    AwaitingConfirmation,
    Hibernated,
    Executing,
    Uncertain,
    Committing,
    Succeeded,
    Failed,
    RollingBack,
    RolledBack,
    AwaitingDoctor,
    Repairing,
    Repaired,
    RepairFailed,
    FailedTerminal,
    Closed,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum WorkerEvent {
    /// spec: EV_TASK_ACCEPTED
    TaskAccepted,
    /// spec: EV_PLAN_READY_PERMITTED
    PlanReadyPermitted,
    /// spec: EV_PLAN_READY_NEEDS_CONFIRM
    PlanReadyNeedsConfirm,
    /// spec: EV_PLAN_ERROR
    PlanError,
    /// spec: EV_USER_CONFIRMED
    UserConfirmed,
    /// spec: EV_USER_DENIED
    UserDenied,
    /// spec: EV_CONFIRM_TIMEOUT
    ConfirmTimeout,
    /// spec: EV_SYSTEM_BUDGET_EXCEEDED
    SystemBudgetExceeded,
    /// spec: EV_USER_RESUME
    UserResume,
    /// spec: EV_HIBERNATE_EXPIRED
    HibernateExpired,
    /// spec: EV_NEW_BLACKLIST_OP
    NewBlacklistOp,
    /// spec: EV_EFFECT_UNCERTAIN
    EffectUncertain,
    /// spec: EV_ALL_EFFECTS_DONE
    AllEffectsDone,
    /// spec: EV_EXEC_ERROR
    ExecError,
    /// spec: EV_BUDGET_EXCEEDED
    BudgetExceeded,
    /// spec: EV_PROBE_SUCCESS
    ProbeSuccess,
    /// spec: EV_PROBE_FAILURE
    ProbeFailure,
    /// spec: EV_PROBE_ASSUMED
    ProbeAssumed,
    /// spec: EV_RESULTS_PERSISTED
    ResultsPersisted,
    /// spec: EV_PERSIST_ERROR
    PersistError,
    /// spec: EV_AUTO_ROLLBACK
    AutoRollback,
    /// spec: EV_USER_ROLLBACK_FAILED / EV_USER_ROLLBACK_SUCCEEDED
    UserRollback,
    /// spec: EV_USER_RETRY
    UserRetry,
    /// spec: EV_USER_ABANDON
    UserAbandon,
    /// spec: EV_USER_RECONCILE_SUCCESS
    UserReconcileSuccess,
    /// spec: EV_USER_RECONCILE_FAILURE
    UserReconcileFailure,
    /// spec: EV_ROLLBACK_OK
    RollbackOk,
    /// spec: EV_ROLLBACK_FAILED
    RollbackFailed,
    /// spec: EV_DOCTOR_KILL_DONE
    DoctorKillDone,
    /// spec: EV_REPAIR_OK
    RepairOk,
    /// spec: EV_REPAIR_FAILED
    RepairFailed,
    /// spec: EV_USER_RETRY_FROM_REPAIRED
    UserRetryFromRepaired,
    /// spec: EV_USER_CLOSE
    UserClose,
    /// spec: EV_USER_RETRY_REPAIR
    UserRetryRepair,
    /// spec: EV_USER_ABANDON_REPAIR
    UserAbandonRepair,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Transition {
    pub event: WorkerEvent,
    pub from: WorkerState,
    pub to: WorkerState,
    pub guards: &'static [&'static str],
}

pub const USER_RETRY_GUARDS: [&str; 4] = [
    "no_uncertain_effects",
    "no_dispatched_effects",
    "no_probing_effects",
    "no_executed_assumed_effects",
];

pub const RECONCILE_GUARD: [&str; 1] = ["has_executed_assumed_effect"];

pub const TERMINAL_STATES: [WorkerState; 4] = [
    WorkerState::Succeeded,
    WorkerState::RolledBack,
    WorkerState::FailedTerminal,
    WorkerState::Closed,
];

pub const TRANSITIONS: [Transition; 36] = [
    Transition {
        event: WorkerEvent::TaskAccepted,
        from: WorkerState::Created,
        to: WorkerState::Planning,
        guards: &[],
    },
    Transition {
        event: WorkerEvent::PlanReadyPermitted,
        from: WorkerState::Planning,
        to: WorkerState::Executing,
        guards: &[],
    },
    Transition {
        event: WorkerEvent::PlanReadyNeedsConfirm,
        from: WorkerState::Planning,
        to: WorkerState::AwaitingConfirmation,
        guards: &[],
    },
    Transition {
        event: WorkerEvent::PlanError,
        from: WorkerState::Planning,
        to: WorkerState::Failed,
        guards: &[],
    },
    Transition {
        event: WorkerEvent::UserConfirmed,
        from: WorkerState::AwaitingConfirmation,
        to: WorkerState::Executing,
        guards: &[],
    },
    Transition {
        event: WorkerEvent::UserDenied,
        from: WorkerState::AwaitingConfirmation,
        to: WorkerState::Failed,
        guards: &[],
    },
    Transition {
        event: WorkerEvent::ConfirmTimeout,
        from: WorkerState::AwaitingConfirmation,
        to: WorkerState::Hibernated,
        guards: &[],
    },
    Transition {
        event: WorkerEvent::SystemBudgetExceeded,
        from: WorkerState::AwaitingConfirmation,
        to: WorkerState::Failed,
        guards: &[],
    },
    Transition {
        event: WorkerEvent::UserResume,
        from: WorkerState::Hibernated,
        to: WorkerState::Planning,
        guards: &[],
    },
    Transition {
        event: WorkerEvent::HibernateExpired,
        from: WorkerState::Hibernated,
        to: WorkerState::FailedTerminal,
        guards: &[],
    },
    Transition {
        event: WorkerEvent::NewBlacklistOp,
        from: WorkerState::Executing,
        to: WorkerState::AwaitingConfirmation,
        guards: &[],
    },
    Transition {
        event: WorkerEvent::EffectUncertain,
        from: WorkerState::Executing,
        to: WorkerState::Uncertain,
        guards: &[],
    },
    Transition {
        event: WorkerEvent::AllEffectsDone,
        from: WorkerState::Executing,
        to: WorkerState::Committing,
        guards: &[],
    },
    Transition {
        event: WorkerEvent::ExecError,
        from: WorkerState::Executing,
        to: WorkerState::Failed,
        guards: &[],
    },
    Transition {
        event: WorkerEvent::BudgetExceeded,
        from: WorkerState::Executing,
        to: WorkerState::Failed,
        guards: &[],
    },
    Transition {
        event: WorkerEvent::ProbeSuccess,
        from: WorkerState::Uncertain,
        to: WorkerState::Committing,
        guards: &[],
    },
    Transition {
        event: WorkerEvent::ProbeFailure,
        from: WorkerState::Uncertain,
        to: WorkerState::Failed,
        guards: &[],
    },
    Transition {
        event: WorkerEvent::ProbeAssumed,
        from: WorkerState::Uncertain,
        to: WorkerState::Failed,
        guards: &[],
    },
    Transition {
        event: WorkerEvent::ResultsPersisted,
        from: WorkerState::Committing,
        to: WorkerState::Succeeded,
        guards: &[],
    },
    Transition {
        event: WorkerEvent::PersistError,
        from: WorkerState::Committing,
        to: WorkerState::Failed,
        guards: &[],
    },
    Transition {
        event: WorkerEvent::AutoRollback,
        from: WorkerState::Failed,
        to: WorkerState::RollingBack,
        guards: &[],
    },
    Transition {
        event: WorkerEvent::UserRollback,
        from: WorkerState::Failed,
        to: WorkerState::RollingBack,
        guards: &[],
    },
    Transition {
        event: WorkerEvent::UserRollback,
        from: WorkerState::Succeeded,
        to: WorkerState::RollingBack,
        guards: &[],
    },
    Transition {
        event: WorkerEvent::UserRetry,
        from: WorkerState::Failed,
        to: WorkerState::Planning,
        guards: &USER_RETRY_GUARDS,
    },
    Transition {
        event: WorkerEvent::UserAbandon,
        from: WorkerState::Failed,
        to: WorkerState::FailedTerminal,
        guards: &[],
    },
    Transition {
        event: WorkerEvent::UserReconcileSuccess,
        from: WorkerState::Failed,
        to: WorkerState::Committing,
        guards: &RECONCILE_GUARD,
    },
    Transition {
        event: WorkerEvent::UserReconcileFailure,
        from: WorkerState::Failed,
        to: WorkerState::FailedTerminal,
        guards: &RECONCILE_GUARD,
    },
    Transition {
        event: WorkerEvent::RollbackOk,
        from: WorkerState::RollingBack,
        to: WorkerState::RolledBack,
        guards: &[],
    },
    Transition {
        event: WorkerEvent::RollbackFailed,
        from: WorkerState::RollingBack,
        to: WorkerState::AwaitingDoctor,
        guards: &[],
    },
    Transition {
        event: WorkerEvent::DoctorKillDone,
        from: WorkerState::AwaitingDoctor,
        to: WorkerState::Repairing,
        guards: &[],
    },
    Transition {
        event: WorkerEvent::RepairOk,
        from: WorkerState::Repairing,
        to: WorkerState::Repaired,
        guards: &[],
    },
    Transition {
        event: WorkerEvent::RepairFailed,
        from: WorkerState::Repairing,
        to: WorkerState::RepairFailed,
        guards: &[],
    },
    Transition {
        event: WorkerEvent::UserRetryFromRepaired,
        from: WorkerState::Repaired,
        to: WorkerState::Planning,
        guards: &[],
    },
    Transition {
        event: WorkerEvent::UserClose,
        from: WorkerState::Repaired,
        to: WorkerState::Closed,
        guards: &[],
    },
    Transition {
        event: WorkerEvent::UserRetryRepair,
        from: WorkerState::RepairFailed,
        to: WorkerState::AwaitingDoctor,
        guards: &[],
    },
    Transition {
        event: WorkerEvent::UserAbandonRepair,
        from: WorkerState::RepairFailed,
        to: WorkerState::FailedTerminal,
        guards: &[],
    },
];

pub fn transition_for(event: WorkerEvent, from: WorkerState) -> Option<Transition> {
    TRANSITIONS
        .iter()
        .copied()
        .find(|item| item.event == event && item.from == from)
}

#[cfg(test)]
mod tests {
    use super::{
        transition_for, WorkerEvent, WorkerState, RECONCILE_GUARD, TRANSITIONS,
        USER_RETRY_GUARDS,
    };

    fn walk_path(start: WorkerState, events: &[WorkerEvent]) -> Vec<WorkerState> {
        let mut states = vec![start];
        let mut current = start;

        for event in events {
            let transition = transition_for(*event, current).expect("expected valid transition");
            current = transition.to;
            states.push(current);
        }

        states
    }

    #[test]
    fn full_transition_table_matches_spec_count() {
        assert_eq!(TRANSITIONS.len(), 36);
    }

    #[test]
    fn happy_path_reaches_succeeded_without_confirmation() {
        let states = walk_path(
            WorkerState::Created,
            &[
                WorkerEvent::TaskAccepted,
                WorkerEvent::PlanReadyPermitted,
                WorkerEvent::AllEffectsDone,
                WorkerEvent::ResultsPersisted,
            ],
        );

        assert_eq!(
            states,
            vec![
                WorkerState::Created,
                WorkerState::Planning,
                WorkerState::Executing,
                WorkerState::Committing,
                WorkerState::Succeeded,
            ]
        );
    }

    #[test]
    fn uncertain_path_reaches_commit_after_probe_success() {
        let states = walk_path(
            WorkerState::Created,
            &[
                WorkerEvent::TaskAccepted,
                WorkerEvent::PlanReadyPermitted,
                WorkerEvent::EffectUncertain,
                WorkerEvent::ProbeSuccess,
                WorkerEvent::ResultsPersisted,
            ],
        );

        assert_eq!(
            states,
            vec![
                WorkerState::Created,
                WorkerState::Planning,
                WorkerState::Executing,
                WorkerState::Uncertain,
                WorkerState::Committing,
                WorkerState::Succeeded,
            ]
        );
    }

    #[test]
    fn exceptional_paths_are_explicitly_modeled() {
        assert_eq!(
            transition_for(WorkerEvent::ConfirmTimeout, WorkerState::AwaitingConfirmation)
                .unwrap()
                .to,
            WorkerState::Hibernated
        );
        assert_eq!(
            transition_for(WorkerEvent::RollbackFailed, WorkerState::RollingBack)
                .unwrap()
                .to,
            WorkerState::AwaitingDoctor
        );
        assert_eq!(
            transition_for(WorkerEvent::RepairFailed, WorkerState::Repairing)
                .unwrap()
                .to,
            WorkerState::RepairFailed
        );
    }

    #[test]
    fn guarded_failed_state_transitions_keep_spec_guards() {
        assert_eq!(
            transition_for(WorkerEvent::UserRetry, WorkerState::Failed)
                .unwrap()
                .guards,
            &USER_RETRY_GUARDS
        );
        assert_eq!(
            transition_for(WorkerEvent::UserReconcileSuccess, WorkerState::Failed)
                .unwrap()
                .guards,
            &RECONCILE_GUARD
        );
        assert_eq!(
            transition_for(WorkerEvent::UserReconcileFailure, WorkerState::Failed)
                .unwrap()
                .guards,
            &RECONCILE_GUARD
        );
        assert!(
            transition_for(WorkerEvent::UserRollback, WorkerState::Succeeded)
                .unwrap()
                .guards
                .is_empty()
        );
    }

    #[test]
    fn invalid_transitions_return_none() {
        assert!(transition_for(WorkerEvent::UserConfirmed, WorkerState::Created).is_none());
        assert!(transition_for(WorkerEvent::UserRetry, WorkerState::Succeeded).is_none());
        assert!(transition_for(WorkerEvent::ProbeSuccess, WorkerState::Executing).is_none());
    }
}
