#[derive(Clone, Debug, PartialEq, Eq)]
pub enum EffectActor {
    Worker,
    Doctor,
    Plugin(String),
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum EffectAction {
    FileRead,
    FileWrite,
    FileDelete,
    FileMove,
    DirCreate,
    DirDelete,
    NetworkRequest,
    SystemExec,
    ClipboardWrite,
    ConfigChange,
    PluginInstall,
    PluginUninstall,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum EffectTier {
    Tier0,
    Tier1,
    Tier2,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum EffectReversibility {
    Rollbackable,
    Compensatable,
    Irreversible,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ProbeMode {
    Auto,
    None,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ProbeState {
    ProbePending,
    Probing,
    ProbeFailed,
    HumanFrozen,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum EffectStatus {
    Prepared,
    Dispatched,
    Executed,
    Uncertain,
    ExecutedAssumed,
    Previewed,
    Confirmed,
    RolledBack,
    Compensated,
    Cancelled,
    Expired,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct EffectTransitionRecord {
    pub from_status: EffectStatus,
    pub to_status: EffectStatus,
    pub at: String,
    pub triggered_by: String,
    pub reason: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct EffectRecord {
    pub effect_id: String,
    pub task_id: String,
    pub trace_id: String,
    pub intent_key: String,
    pub schema_version: &'static str,
    pub actor: EffectActor,
    pub action: EffectAction,
    pub target: String,
    pub probe_mode: ProbeMode,
    pub tier: EffectTier,
    pub reversibility: EffectReversibility,
    pub compensates_effect_id: Option<String>,
    pub status: EffectStatus,
    pub probe_state: Option<ProbeState>,
    pub transitions: Vec<EffectTransitionRecord>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum EffectTransitionError {
    InvalidTransition {
        from: EffectStatus,
        to: EffectStatus,
    },
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum AttemptResultStatus {
    Success,
    Failure,
    Timeout,
    Crash,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum LeaseError {
    Expired {
        now_ms: u64,
        expires_at_ms: u64,
    },
    LeaseIdMismatch,
    StaleFencingToken {
        current: u64,
        provided: u64,
    },
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum AttemptWriteError {
    Lease(LeaseError),
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RecoveryLease {
    pub lease_id: String,
    pub owner_id: String,
    pub fencing_token: u64,
    pub ttl_ms: u64,
    pub expires_at_ms: u64,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct EffectAttempt {
    pub attempt_id: String,
    pub effect_id: String,
    pub attempt_seq: u64,
    pub dispatched_at: String,
    pub lease_id: String,
    pub fencing_token: u64,
    pub result_status: Option<AttemptResultStatus>,
}

pub const EFFECT_LEDGER_SCHEMA_VERSION: &str = "3.2.0";

pub const COMMIT_PROTOCOL_STEPS: [&str; 6] = [
    "prepared",
    "dispatched",
    "external_action",
    "executed",
    "apply_event",
    "finalize",
];

pub const CORE_EFFECT_PHASES: [EffectStatus; 5] = [
    EffectStatus::Prepared,
    EffectStatus::Dispatched,
    EffectStatus::Executed,
    EffectStatus::Uncertain,
    EffectStatus::ExecutedAssumed,
];

pub const ALLOWED_STATUS_TRANSITIONS: [(EffectStatus, EffectStatus); 17] = [
    (EffectStatus::Prepared, EffectStatus::Previewed),
    (EffectStatus::Prepared, EffectStatus::Dispatched),
    (EffectStatus::Prepared, EffectStatus::Cancelled),
    (EffectStatus::Prepared, EffectStatus::Expired),
    (EffectStatus::Previewed, EffectStatus::Confirmed),
    (EffectStatus::Previewed, EffectStatus::Cancelled),
    (EffectStatus::Previewed, EffectStatus::Expired),
    (EffectStatus::Confirmed, EffectStatus::Dispatched),
    (EffectStatus::Dispatched, EffectStatus::Executed),
    (EffectStatus::Dispatched, EffectStatus::Uncertain),
    (EffectStatus::Dispatched, EffectStatus::ExecutedAssumed),
    (EffectStatus::Uncertain, EffectStatus::Executed),
    (EffectStatus::Uncertain, EffectStatus::ExecutedAssumed),
    (EffectStatus::Executed, EffectStatus::RolledBack),
    (EffectStatus::Executed, EffectStatus::Compensated),
    (EffectStatus::ExecutedAssumed, EffectStatus::Executed),
    (EffectStatus::ExecutedAssumed, EffectStatus::Cancelled),
];

pub fn crash_outcome_for(mode: ProbeMode) -> EffectStatus {
    match mode {
        ProbeMode::Auto => EffectStatus::Uncertain,
        ProbeMode::None => EffectStatus::ExecutedAssumed,
    }
}

pub fn transition_allowed(from: EffectStatus, to: EffectStatus) -> bool {
    ALLOWED_STATUS_TRANSITIONS.contains(&(from, to))
}

impl RecoveryLease {
    pub fn new(
        lease_id: impl Into<String>,
        owner_id: impl Into<String>,
        fencing_token: u64,
        now_ms: u64,
        ttl_ms: u64,
    ) -> Self {
        Self {
            lease_id: lease_id.into(),
            owner_id: owner_id.into(),
            fencing_token,
            ttl_ms,
            expires_at_ms: now_ms + ttl_ms,
        }
    }

    pub fn is_active(&self, now_ms: u64) -> bool {
        now_ms <= self.expires_at_ms
    }

    pub fn renew(&mut self, now_ms: u64) -> Result<(), LeaseError> {
        if !self.is_active(now_ms) {
            return Err(LeaseError::Expired {
                now_ms,
                expires_at_ms: self.expires_at_ms,
            });
        }
        self.expires_at_ms = now_ms + self.ttl_ms;
        Ok(())
    }

    pub fn assert_can_write(
        &self,
        provided_lease_id: &str,
        provided_fencing_token: u64,
        now_ms: u64,
    ) -> Result<(), LeaseError> {
        if !self.is_active(now_ms) {
            return Err(LeaseError::Expired {
                now_ms,
                expires_at_ms: self.expires_at_ms,
            });
        }
        if self.lease_id != provided_lease_id {
            return Err(LeaseError::LeaseIdMismatch);
        }
        if self.fencing_token != provided_fencing_token {
            return Err(LeaseError::StaleFencingToken {
                current: self.fencing_token,
                provided: provided_fencing_token,
            });
        }
        Ok(())
    }
}

impl EffectAttempt {
    pub fn next_for_effect(
        attempts: &[EffectAttempt],
        attempt_id: impl Into<String>,
        effect_id: impl Into<String>,
        dispatched_at: impl Into<String>,
        lease: &RecoveryLease,
        now_ms: u64,
    ) -> Result<Self, AttemptWriteError> {
        lease
            .assert_can_write(&lease.lease_id, lease.fencing_token, now_ms)
            .map_err(AttemptWriteError::Lease)?;

        let effect_id = effect_id.into();
        let next_attempt_seq = attempts
            .iter()
            .filter(|attempt| attempt.effect_id == effect_id)
            .map(|attempt| attempt.attempt_seq)
            .max()
            .unwrap_or(0)
            + 1;

        Ok(Self {
            attempt_id: attempt_id.into(),
            effect_id,
            attempt_seq: next_attempt_seq,
            dispatched_at: dispatched_at.into(),
            lease_id: lease.lease_id.clone(),
            fencing_token: lease.fencing_token,
            result_status: None,
        })
    }

    pub fn record_result(
        &mut self,
        result_status: AttemptResultStatus,
        lease: &RecoveryLease,
        now_ms: u64,
    ) -> Result<(), AttemptWriteError> {
        lease
            .assert_can_write(&self.lease_id, self.fencing_token, now_ms)
            .map_err(AttemptWriteError::Lease)?;
        self.result_status = Some(result_status);
        Ok(())
    }
}

impl EffectRecord {
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        effect_id: impl Into<String>,
        task_id: impl Into<String>,
        trace_id: impl Into<String>,
        intent_key: impl Into<String>,
        actor: EffectActor,
        action: EffectAction,
        target: impl Into<String>,
        tier: EffectTier,
        reversibility: EffectReversibility,
        probe_mode: ProbeMode,
    ) -> Self {
        Self {
            effect_id: effect_id.into(),
            task_id: task_id.into(),
            trace_id: trace_id.into(),
            intent_key: intent_key.into(),
            schema_version: EFFECT_LEDGER_SCHEMA_VERSION,
            actor,
            action,
            target: target.into(),
            probe_mode,
            tier,
            reversibility,
            compensates_effect_id: None,
            status: EffectStatus::Prepared,
            probe_state: None,
            transitions: Vec::new(),
        }
    }

    pub fn transition_to(
        &mut self,
        to_status: EffectStatus,
        at: impl Into<String>,
        triggered_by: impl Into<String>,
        reason: impl Into<String>,
    ) -> Result<(), EffectTransitionError> {
        let from_status = self.status;
        if !transition_allowed(from_status, to_status) {
            return Err(EffectTransitionError::InvalidTransition {
                from: from_status,
                to: to_status,
            });
        }

        self.transitions.push(EffectTransitionRecord {
            from_status,
            to_status,
            at: at.into(),
            triggered_by: triggered_by.into(),
            reason: reason.into(),
        });
        self.status = to_status;
        self.probe_state = match to_status {
            EffectStatus::Uncertain => Some(ProbeState::ProbePending),
            EffectStatus::ExecutedAssumed => Some(ProbeState::HumanFrozen),
            _ => None,
        };

        Ok(())
    }

    pub fn record_crash_outcome(
        &mut self,
        at: impl Into<String>,
        triggered_by: impl Into<String>,
        reason: impl Into<String>,
    ) -> Result<EffectStatus, EffectTransitionError> {
        let outcome = crash_outcome_for(self.probe_mode);
        self.transition_to(outcome, at, triggered_by, reason)?;
        Ok(outcome)
    }

    #[allow(clippy::too_many_arguments)]
    pub fn spawn_compensation(
        &self,
        compensation_effect_id: impl Into<String>,
        compensation_intent_key: impl Into<String>,
        actor: EffectActor,
        action: EffectAction,
        target: impl Into<String>,
        reversibility: EffectReversibility,
        probe_mode: ProbeMode,
    ) -> Self {
        let mut compensation = Self::new(
            compensation_effect_id,
            self.task_id.clone(),
            self.trace_id.clone(),
            compensation_intent_key,
            actor,
            action,
            target,
            self.tier,
            reversibility,
            probe_mode,
        );
        compensation.compensates_effect_id = Some(self.effect_id.clone());
        compensation
    }
}

#[cfg(test)]
mod tests {
    use super::{
        crash_outcome_for, AttemptResultStatus, AttemptWriteError, EffectAction,
        EffectActor, EffectAttempt, EffectRecord, EffectReversibility, EffectStatus,
        EffectTier, EffectTransitionError, LeaseError, ProbeMode, ProbeState,
        RecoveryLease,
    };

    fn demo_record(probe_mode: ProbeMode) -> EffectRecord {
        EffectRecord::new(
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
        )
    }

    #[test]
    fn new_record_starts_prepared_with_empty_history() {
        let record = demo_record(ProbeMode::Auto);

        assert_eq!(record.status, EffectStatus::Prepared);
        assert!(record.transitions.is_empty());
        assert!(record.probe_state.is_none());
    }

    #[test]
    fn transitions_append_history_without_overwriting_previous_entries() {
        let mut record = demo_record(ProbeMode::Auto);
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

        assert_eq!(record.transitions.len(), 2);
        assert_eq!(record.transitions[0].from_status, EffectStatus::Prepared);
        assert_eq!(record.transitions[0].to_status, EffectStatus::Dispatched);
        assert_eq!(record.transitions[1].from_status, EffectStatus::Dispatched);
        assert_eq!(record.transitions[1].to_status, EffectStatus::Executed);
    }

    #[test]
    fn invalid_transition_is_rejected() {
        let mut record = demo_record(ProbeMode::Auto);

        assert_eq!(
            record.transition_to(
                EffectStatus::Executed,
                "2026-03-21T00:00:00Z",
                "worker",
                "skip_dispatch",
            ),
            Err(EffectTransitionError::InvalidTransition {
                from: EffectStatus::Prepared,
                to: EffectStatus::Executed,
            })
        );
    }

    #[test]
    fn crash_outcome_tracks_probe_state() {
        let mut auto_probe = demo_record(ProbeMode::Auto);
        auto_probe
            .transition_to(
                EffectStatus::Dispatched,
                "2026-03-21T00:00:00Z",
                "worker",
                "dispatch",
            )
            .unwrap();

        assert_eq!(crash_outcome_for(ProbeMode::Auto), EffectStatus::Uncertain);
        assert_eq!(
            auto_probe
                .record_crash_outcome("2026-03-21T00:00:01Z", "worker", "sidecar_crash")
                .unwrap(),
            EffectStatus::Uncertain
        );
        assert_eq!(auto_probe.probe_state, Some(ProbeState::ProbePending));

        let mut no_probe = demo_record(ProbeMode::None);
        no_probe
            .transition_to(
                EffectStatus::Dispatched,
                "2026-03-21T00:00:00Z",
                "worker",
                "dispatch",
            )
            .unwrap();

        assert_eq!(
            no_probe
                .record_crash_outcome("2026-03-21T00:00:01Z", "worker", "process_crash")
                .unwrap(),
            EffectStatus::ExecutedAssumed
        );
        assert_eq!(no_probe.probe_state, Some(ProbeState::HumanFrozen));
    }

    #[test]
    fn recovery_lease_gates_attempt_writes_and_rejects_stale_holders() {
        let mut lease = RecoveryLease::new("lease-1", "doctor-a", 7, 0, 30_000);
        let attempt = EffectAttempt::next_for_effect(
            &[],
            "attempt-1",
            "effect-1",
            "2026-03-21T00:00:00Z",
            &lease,
            1,
        )
        .unwrap();
        assert_eq!(attempt.attempt_seq, 1);

        let mut recorded_attempt = attempt.clone();
        recorded_attempt
            .record_result(AttemptResultStatus::Crash, &lease, 10)
            .unwrap();
        assert_eq!(recorded_attempt.result_status, Some(AttemptResultStatus::Crash));

        lease.expires_at_ms = 5;
        assert_eq!(
            recorded_attempt.record_result(AttemptResultStatus::Success, &lease, 10),
            Err(AttemptWriteError::Lease(LeaseError::Expired {
                now_ms: 10,
                expires_at_ms: 5,
            }))
        );
    }

    #[test]
    fn compensation_effect_is_independent_and_linked_to_source_effect() {
        let source = demo_record(ProbeMode::Auto);
        let compensation = source.spawn_compensation(
            "effect-comp-1",
            "intent-comp-1",
            EffectActor::Doctor,
            EffectAction::FileWrite,
            "scope:/tmp/undo.txt",
            EffectReversibility::Rollbackable,
            ProbeMode::Auto,
        );

        assert_eq!(compensation.status, EffectStatus::Prepared);
        assert_eq!(compensation.compensates_effect_id, Some(String::from("effect-1")));
        assert_eq!(compensation.task_id, source.task_id);
        assert_ne!(compensation.effect_id, source.effect_id);
    }
}
