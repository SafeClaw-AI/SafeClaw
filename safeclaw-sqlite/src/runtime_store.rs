use rusqlite::{Connection, TransactionBehavior};
use safeclaw_core::{
    effect_ledger::{
        AttemptResultStatus, EffectAttempt, EffectStatus, EffectTransitionRecord, ProbeState,
    },
    state_engine::{StateApplyResult, StateEvent, TaskSnapshot},
    worker_lifecycle::WorkerState,
    InMemoryTaskRuntime, RuntimeStore, RuntimeStoreError,
};

use crate::{
    effect_store::{
        list_attempts_from_connection, load_effect_from_connection,
        load_latest_lease_from_connection, load_transitions_from_connection,
        save_attempt_in_transaction, save_effect_in_transaction, save_lease_in_transaction,
    },
    state_engine::{
        apply_event_in_transaction, list_state_events_from_connection,
        load_snapshot_from_connection,
    },
    SqliteAdapterError,
};

pub struct SqliteRuntimeStore {
    connection: Connection,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RuntimeGovernanceDisposition {
    InFlight,
    QueueForConfirmation,
    RetryEligible,
    QueueForManualReview,
    Resolved,
    ParkedUnsupported,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RuntimeGovernanceView {
    pub task_id: String,
    pub effect_id: String,
    pub worker_state: WorkerState,
    pub effect_status: EffectStatus,
    pub probe_state: Option<ProbeState>,
    pub last_state_event_id: String,
    pub updated_at: String,
    pub attempt_count: usize,
    pub last_attempt_result: Option<AttemptResultStatus>,
    pub compensation_count: usize,
    pub quarantined_scopes: Vec<String>,
    pub has_recovery_lease: bool,
    pub disposition: RuntimeGovernanceDisposition,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RuntimeDiagnosticSnapshot {
    pub governance: RuntimeGovernanceView,
    pub attempts: Vec<EffectAttempt>,
    pub state_events: Vec<StateEvent>,
    pub effect_transitions: Vec<EffectTransitionRecord>,
}

impl SqliteRuntimeStore {
    pub fn new(connection: Connection) -> Self {
        Self { connection }
    }

    pub fn connection(&self) -> &Connection {
        &self.connection
    }

    pub fn into_connection(self) -> Connection {
        self.connection
    }

    pub fn persist_runtime(
        &mut self,
        runtime: &InMemoryTaskRuntime,
        state_event_id: impl Into<String>,
        triggered_by: impl Into<String>,
    ) -> Result<StateApplyResult, SqliteAdapterError> {
        let state_event = runtime.state_event(state_event_id, triggered_by);
        self.persist_runtime_with_event(runtime, state_event)
    }

    pub fn persist_runtime_with_event(
        &mut self,
        runtime: &InMemoryTaskRuntime,
        state_event: StateEvent,
    ) -> Result<StateApplyResult, SqliteAdapterError> {
        let transaction = self
            .connection
            .transaction_with_behavior(TransactionBehavior::Immediate)?;

        let apply_result = apply_event_in_transaction(&transaction, state_event)
            .map_err(map_state_engine_error)?;
        if apply_result == StateApplyResult::DuplicateIgnored {
            transaction.commit()?;
            return Ok(apply_result);
        }

        save_effect_in_transaction(&transaction, &runtime.effect)?;
        for compensation in &runtime.compensation_effects {
            save_effect_in_transaction(&transaction, compensation)?;
        }
        if let Some(lease) = runtime.current_recovery_lease() {
            save_lease_in_transaction(&transaction, &runtime.effect.task_id, lease)?;
        }
        for attempt in &runtime.attempts {
            save_attempt_in_transaction(&transaction, attempt)?;
        }

        transaction.commit()?;
        Ok(apply_result)
    }

    pub fn load_runtime(
        &self,
        task_id: &str,
        effect_id: &str,
    ) -> Result<Option<InMemoryTaskRuntime>, SqliteAdapterError> {
        let snapshot = match load_snapshot_from_connection(&self.connection, task_id) {
            Ok(Some(snapshot)) => snapshot,
            Ok(None) => return Ok(None),
            Err(error) => return Err(map_state_engine_error(error)),
        };

        let effect =
            load_effect_from_connection(&self.connection, effect_id)?.ok_or_else(|| {
                SqliteAdapterError::InvalidStoredValue {
                    field: "runtime_effect",
                    value: effect_id.to_string(),
                }
            })?;
        let lease = load_latest_lease_from_connection(&self.connection, task_id)?;
        let attempts = list_attempts_from_connection(&self.connection, effect_id)?;
        let compensation_effects = self.list_compensation_effects(effect_id)?;

        let mut runtime = InMemoryTaskRuntime::restore_from_snapshot(effect, &snapshot, lease);
        runtime.attempts = attempts;
        runtime.compensation_effects = compensation_effects;
        Ok(Some(runtime))
    }

    pub fn governance_view(
        &self,
        task_id: &str,
        effect_id: &str,
    ) -> Result<Option<RuntimeGovernanceView>, SqliteAdapterError> {
        let snapshot = match load_snapshot_from_connection(&self.connection, task_id) {
            Ok(Some(snapshot)) => snapshot,
            Ok(None) => return Ok(None),
            Err(error) => return Err(map_state_engine_error(error)),
        };
        let Some(runtime) = self.load_runtime(task_id, effect_id)? else {
            return Ok(None);
        };
        Ok(Some(build_governance_view(snapshot, runtime)))
    }

    pub fn diagnostic_snapshot(
        &self,
        task_id: &str,
        effect_id: &str,
    ) -> Result<Option<RuntimeDiagnosticSnapshot>, SqliteAdapterError> {
        let snapshot = match load_snapshot_from_connection(&self.connection, task_id) {
            Ok(Some(snapshot)) => snapshot,
            Ok(None) => return Ok(None),
            Err(error) => return Err(map_state_engine_error(error)),
        };
        let Some(runtime) = self.load_runtime(task_id, effect_id)? else {
            return Ok(None);
        };
        let attempts = runtime.attempts.clone();
        let governance = build_governance_view(snapshot, runtime);
        let state_events =
            list_state_events_from_connection(&self.connection, task_id).map_err(map_state_engine_error)?;
        let effect_transitions = load_transitions_from_connection(&self.connection, effect_id)?;
        Ok(Some(RuntimeDiagnosticSnapshot {
            governance,
            attempts,
            state_events,
            effect_transitions,
        }))
    }

    pub fn list_attempts(&self, effect_id: &str) -> Result<Vec<EffectAttempt>, SqliteAdapterError> {
        list_attempts_from_connection(&self.connection, effect_id)
    }

    pub fn list_state_events(&self, task_id: &str) -> Result<Vec<StateEvent>, SqliteAdapterError> {
        list_state_events_from_connection(&self.connection, task_id).map_err(map_state_engine_error)
    }

    pub fn list_effect_transitions(
        &self,
        effect_id: &str,
    ) -> Result<Vec<EffectTransitionRecord>, SqliteAdapterError> {
        load_transitions_from_connection(&self.connection, effect_id)
    }

    fn list_compensation_effects(
        &self,
        effect_id: &str,
    ) -> Result<Vec<safeclaw_core::effect_ledger::EffectRecord>, SqliteAdapterError> {
        let mut statement = self.connection.prepare(
            "SELECT effect_id FROM effects WHERE compensates_effect_id = ?1 ORDER BY effect_id ASC",
        )?;
        let rows = statement
            .query_map([effect_id], |row| row.get::<_, String>(0))?
            .collect::<Result<Vec<_>, _>>()?;

        let mut effects = Vec::with_capacity(rows.len());
        for compensation_id in rows {
            let effect = load_effect_from_connection(&self.connection, &compensation_id)?
                .ok_or_else(|| SqliteAdapterError::InvalidStoredValue {
                    field: "compensation_effect",
                    value: compensation_id.clone(),
                })?;
            effects.push(effect);
        }
        Ok(effects)
    }
}


fn build_governance_view(
    snapshot: TaskSnapshot,
    runtime: InMemoryTaskRuntime,
) -> RuntimeGovernanceView {
    let has_recovery_lease = runtime.current_recovery_lease().is_some();
    RuntimeGovernanceView {
        task_id: snapshot.task_id,
        effect_id: runtime.effect.effect_id.clone(),
        worker_state: runtime.worker_state,
        effect_status: runtime.effect.status,
        probe_state: runtime.effect.probe_state,
        last_state_event_id: snapshot.last_state_event_id,
        updated_at: snapshot.updated_at,
        attempt_count: runtime.attempts.len(),
        last_attempt_result: runtime.attempts.last().and_then(|attempt| attempt.result_status),
        compensation_count: runtime.compensation_effects.len(),
        quarantined_scopes: runtime.quarantined_scopes,
        has_recovery_lease,
        disposition: governance_disposition_for_state(runtime.worker_state),
    }
}

fn governance_disposition_for_state(state: WorkerState) -> RuntimeGovernanceDisposition {
    match state {
        WorkerState::Created
        | WorkerState::Planning
        | WorkerState::Executing
        | WorkerState::Committing
        | WorkerState::RollingBack => RuntimeGovernanceDisposition::InFlight,
        WorkerState::AwaitingConfirmation => RuntimeGovernanceDisposition::QueueForConfirmation,
        WorkerState::Failed => RuntimeGovernanceDisposition::RetryEligible,
        WorkerState::Uncertain => RuntimeGovernanceDisposition::QueueForManualReview,
        WorkerState::Succeeded
        | WorkerState::RolledBack
        | WorkerState::FailedTerminal
        | WorkerState::Closed => RuntimeGovernanceDisposition::Resolved,
        WorkerState::Hibernated
        | WorkerState::AwaitingDoctor
        | WorkerState::Repairing
        | WorkerState::Repaired
        | WorkerState::RepairFailed => RuntimeGovernanceDisposition::ParkedUnsupported,
    }
}

impl RuntimeStore for SqliteRuntimeStore {
    fn persist_runtime(
        &mut self,
        runtime: &InMemoryTaskRuntime,
        state_event_id: &str,
        triggered_by: &str,
    ) -> Result<StateApplyResult, RuntimeStoreError> {
        SqliteRuntimeStore::persist_runtime(self, runtime, state_event_id, triggered_by)
            .map_err(|error| map_runtime_store_error(error, "persist_runtime"))
    }

    fn load_runtime(
        &self,
        task_id: &str,
        effect_id: &str,
    ) -> Result<Option<InMemoryTaskRuntime>, RuntimeStoreError> {
        SqliteRuntimeStore::load_runtime(self, task_id, effect_id)
            .map_err(|error| map_runtime_store_error(error, "load_runtime"))
    }
}
fn map_state_engine_error(
    error: safeclaw_core::state_engine::StateEngineError,
) -> SqliteAdapterError {
    SqliteAdapterError::InvalidStoredValue {
        field: "state_engine",
        value: format!("{error:?}"),
    }
}

#[cfg(test)]
mod tests {
    use super::{
        RuntimeGovernanceDisposition, SqliteRuntimeStore,
    };
    use crate::{open_database, SqliteEffectStore, SqliteOpenOptions, SqliteStateEngine};
    use safeclaw_core::{
        effect_ledger::{
            EffectAction, EffectActor, EffectRecord, EffectReversibility, EffectStatus, EffectTier,
            ProbeMode,
        },
        state_engine::{StateApplyResult, StateEngine},
        ExecutionDisposition, InMemoryTaskRuntime, PreflightDecision,
    };
    use std::{
        env, fs,
        path::{Path, PathBuf},
        process,
        time::{SystemTime, UNIX_EPOCH},
    };

    struct TempDatabase {
        path: PathBuf,
    }

    impl TempDatabase {
        fn new(label: &str) -> Self {
            let unique = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .expect("system clock must be after epoch")
                .as_nanos();
            let path = env::temp_dir().join(format!(
                "safeclaw-runtime-store-{label}-{}-{unique}.db",
                process::id()
            ));
            Self { path }
        }

        fn path(&self) -> &Path {
            &self.path
        }
    }

    impl Drop for TempDatabase {
        fn drop(&mut self) {
            for suffix in ["", "-wal", "-shm"] {
                let candidate = PathBuf::from(format!("{}{}", self.path.display(), suffix));
                let _ = fs::remove_file(candidate);
            }
        }
    }

    #[test]
    fn persist_runtime_roundtrips_attempts_lease_and_state() {
        let temp_db = TempDatabase::new("roundtrip");
        let mut runtime = InMemoryTaskRuntime::new(demo_effect(ProbeMode::None));
        runtime
            .run_minimal_flow(PreflightDecision::Permit, ExecutionDisposition::Crash)
            .expect("runtime flow must succeed");

        let connection = open_database(temp_db.path(), SqliteOpenOptions::default())
            .expect("sqlite adapter must open runtime database");
        let mut store = SqliteRuntimeStore::new(connection);
        assert_eq!(
            store
                .persist_runtime(&runtime, "runtime-state-1", "runtime-store")
                .unwrap(),
            StateApplyResult::Applied
        );
        drop(store);

        let reopened = open_database(temp_db.path(), SqliteOpenOptions::default())
            .expect("sqlite adapter must reopen runtime database");
        let store = SqliteRuntimeStore::new(reopened);
        let restored = store
            .load_runtime("task-none-runtime", "effect-none-runtime")
            .unwrap()
            .expect("runtime must exist");

        assert_eq!(
            restored.worker_state,
            safeclaw_core::worker_lifecycle::WorkerState::Failed
        );
        assert_eq!(restored.effect.status, EffectStatus::ExecutedAssumed);
        assert_eq!(restored.attempts.len(), 1);
        assert_eq!(restored.attempts[0].attempt_seq, 1);
        assert!(restored.current_recovery_lease().is_some());
    }

    #[test]
    fn duplicate_runtime_event_does_not_overwrite_effect_state() {
        let temp_db = TempDatabase::new("duplicate");
        let mut runtime = InMemoryTaskRuntime::new(demo_effect(ProbeMode::Auto));
        runtime
            .run_minimal_flow(PreflightDecision::Permit, ExecutionDisposition::Crash)
            .expect("runtime flow must succeed");

        let connection = open_database(temp_db.path(), SqliteOpenOptions::default())
            .expect("sqlite adapter must open runtime database");
        let mut store = SqliteRuntimeStore::new(connection);
        assert_eq!(
            store
                .persist_runtime(&runtime, "dup-runtime-event", "runtime-store")
                .unwrap(),
            StateApplyResult::Applied
        );

        runtime
            .begin_probe()
            .expect("probe begin must succeed on uncertain runtime");
        assert_eq!(
            store
                .persist_runtime(&runtime, "dup-runtime-event", "runtime-store")
                .unwrap(),
            StateApplyResult::DuplicateIgnored
        );
        drop(store);

        let effect_store = SqliteEffectStore::new(
            open_database(temp_db.path(), SqliteOpenOptions::default())
                .expect("sqlite adapter must reopen effect store"),
        );
        let state_engine = SqliteStateEngine::new(
            open_database(temp_db.path(), SqliteOpenOptions::default())
                .expect("sqlite adapter must reopen state engine"),
        );
        let effect = effect_store
            .load_effect("effect-auto-runtime")
            .unwrap()
            .expect("effect must exist");
        let snapshot = state_engine
            .load_snapshot("task-auto-runtime")
            .unwrap()
            .expect("snapshot must exist");

        assert_eq!(effect.status, EffectStatus::Uncertain);
        assert_eq!(snapshot.effect_status, EffectStatus::Uncertain);
        assert_eq!(snapshot.version, 1);
    }

    #[test]
    fn persist_runtime_restores_compensation_effects() {
        let temp_db = TempDatabase::new("compensation");
        let effect = EffectRecord::new(
            "effect-compensatable-runtime",
            "task-compensatable-runtime",
            "trace-compensatable-runtime",
            "intent-compensatable-runtime",
            EffectActor::Worker,
            EffectAction::FileWrite,
            "scope:/task-compensatable-runtime",
            EffectTier::Tier1,
            EffectReversibility::Compensatable,
            ProbeMode::Auto,
        );
        let mut runtime = InMemoryTaskRuntime::new(effect);
        runtime
            .run_persist_error_recovery(PreflightDecision::Permit)
            .expect("persist error recovery must succeed");
        assert_eq!(runtime.compensation_effects.len(), 1);

        let connection = open_database(temp_db.path(), SqliteOpenOptions::default())
            .expect("sqlite adapter must open runtime database");
        let mut store = SqliteRuntimeStore::new(connection);
        assert_eq!(
            store
                .persist_runtime(&runtime, "comp-runtime-event", "runtime-store")
                .unwrap(),
            StateApplyResult::Applied
        );
        drop(store);

        let reopened = open_database(temp_db.path(), SqliteOpenOptions::default())
            .expect("sqlite adapter must reopen runtime database");
        let store = SqliteRuntimeStore::new(reopened);
        let restored = store
            .load_runtime("task-compensatable-runtime", "effect-compensatable-runtime")
            .unwrap()
            .expect("runtime must exist");

        assert_eq!(
            restored.worker_state,
            safeclaw_core::worker_lifecycle::WorkerState::RolledBack
        );
        assert_eq!(restored.effect.status, EffectStatus::Compensated);
        assert_eq!(restored.compensation_effects.len(), 1);
        assert_eq!(
            restored.compensation_effects[0].compensates_effect_id,
            Some(String::from("effect-compensatable-runtime"))
        );
    }

    #[test]
    fn governance_view_reports_confirmation_state_and_snapshot_meta() {
        let temp_db = TempDatabase::new("governance-confirmation");
        let mut runtime = InMemoryTaskRuntime::new(demo_effect_with_ids(
            "effect-governance-confirmation",
            "task-governance-confirmation",
            ProbeMode::Auto,
        ));
        let waiting = runtime.run_confirmation_checkpoint().unwrap();
        assert_eq!(waiting.worker_state, safeclaw_core::worker_lifecycle::WorkerState::AwaitingConfirmation);

        let connection = open_database(temp_db.path(), SqliteOpenOptions::default())
            .expect("sqlite adapter must open runtime database");
        let mut store = SqliteRuntimeStore::new(connection);
        store
            .persist_runtime(&runtime, "runtime-governance-confirmation", "runtime-store")
            .unwrap();

        let view = store
            .governance_view(
                "task-governance-confirmation",
                "effect-governance-confirmation",
            )
            .unwrap()
            .expect("governance view must exist");

        assert_eq!(view.worker_state, safeclaw_core::worker_lifecycle::WorkerState::AwaitingConfirmation);
        assert_eq!(view.effect_status, EffectStatus::Prepared);
        assert_eq!(view.last_state_event_id, "runtime-governance-confirmation");
        assert_eq!(view.attempt_count, 0);
        assert_eq!(view.last_attempt_result, None);
        assert_eq!(view.compensation_count, 0);
        assert!(!view.has_recovery_lease);
        assert_eq!(view.disposition, RuntimeGovernanceDisposition::QueueForConfirmation);
    }

    #[test]
    fn governance_view_classifies_failed_uncertain_and_resolved_runtimes() {
        let temp_db = TempDatabase::new("governance-dispositions");
        let connection = open_database(temp_db.path(), SqliteOpenOptions::default())
            .expect("sqlite adapter must open runtime database");
        let mut store = SqliteRuntimeStore::new(connection);

        let mut failed_runtime = InMemoryTaskRuntime::new(demo_effect_with_ids(
            "effect-governance-failed",
            "task-governance-failed",
            ProbeMode::Auto,
        ));
        failed_runtime.run_plan_failure().unwrap();
        store
            .persist_runtime(&failed_runtime, "runtime-governance-failed", "runtime-store")
            .unwrap();
        let failed_view = store
            .governance_view("task-governance-failed", "effect-governance-failed")
            .unwrap()
            .expect("failed governance view must exist");
        assert_eq!(failed_view.disposition, RuntimeGovernanceDisposition::RetryEligible);
        assert_eq!(failed_view.attempt_count, 0);
        assert_eq!(failed_view.last_attempt_result, None);

        let mut uncertain_runtime = InMemoryTaskRuntime::new(demo_effect_with_ids(
            "effect-governance-uncertain",
            "task-governance-uncertain",
            ProbeMode::Auto,
        ));
        uncertain_runtime
            .run_minimal_flow(PreflightDecision::Permit, ExecutionDisposition::Crash)
            .unwrap();
        store
            .persist_runtime(
                &uncertain_runtime,
                "runtime-governance-uncertain",
                "runtime-store",
            )
            .unwrap();
        let uncertain_view = store
            .governance_view("task-governance-uncertain", "effect-governance-uncertain")
            .unwrap()
            .expect("uncertain governance view must exist");
        assert_eq!(
            uncertain_view.disposition,
            RuntimeGovernanceDisposition::QueueForManualReview
        );
        assert_eq!(uncertain_view.attempt_count, 1);
        assert_eq!(
            uncertain_view.last_attempt_result,
            Some(safeclaw_core::effect_ledger::AttemptResultStatus::Crash)
        );
        assert!(uncertain_view.has_recovery_lease);

        let mut resolved_runtime = InMemoryTaskRuntime::new(demo_effect_with_ids(
            "effect-governance-resolved",
            "task-governance-resolved",
            ProbeMode::Auto,
        ));
        resolved_runtime
            .run_minimal_flow(PreflightDecision::Permit, ExecutionDisposition::Commit)
            .unwrap();
        store
            .persist_runtime(
                &resolved_runtime,
                "runtime-governance-resolved",
                "runtime-store",
            )
            .unwrap();
        let resolved_view = store
            .governance_view("task-governance-resolved", "effect-governance-resolved")
            .unwrap()
            .expect("resolved governance view must exist");
        assert_eq!(resolved_view.disposition, RuntimeGovernanceDisposition::Resolved);
        assert_eq!(
            resolved_view.last_attempt_result,
            Some(safeclaw_core::effect_ledger::AttemptResultStatus::Success)
        );
        assert_eq!(resolved_view.attempt_count, 1);
    }

    fn demo_effect(probe_mode: ProbeMode) -> EffectRecord {
        let (effect_id, task_id) = match probe_mode {
            ProbeMode::Auto => ("effect-auto-runtime", "task-auto-runtime"),
            ProbeMode::None => ("effect-none-runtime", "task-none-runtime"),
        };
        demo_effect_with_ids(effect_id, task_id, probe_mode)
    }

    fn demo_effect_with_ids(
        effect_id: &str,
        task_id: &str,
        probe_mode: ProbeMode,
    ) -> EffectRecord {
        EffectRecord::new(
            effect_id,
            task_id,
            format!("trace-{task_id}"),
            format!("intent-{task_id}"),
            EffectActor::Worker,
            EffectAction::FileWrite,
            format!("scope:/{task_id}"),
            EffectTier::Tier1,
            EffectReversibility::Rollbackable,
            probe_mode,
        )
    }
}

fn map_runtime_store_error(
    error: SqliteAdapterError,
    operation: &'static str,
) -> RuntimeStoreError {
    match error {
        SqliteAdapterError::InvalidStoredValue { field, value } => {
            RuntimeStoreError::InvalidStoredValue { field, value }
        }
        SqliteAdapterError::IntegerOutOfRange { field, value } => {
            RuntimeStoreError::InvalidStoredValue {
                field,
                value: value.to_string(),
            }
        }
        SqliteAdapterError::UnsupportedSchemaVersion { current, expected } => {
            RuntimeStoreError::InvalidStoredValue {
                field: "schema_version",
                value: format!("current={current}, expected={expected}"),
            }
        }
        SqliteAdapterError::InvalidPragmaValue { pragma, value } => {
            RuntimeStoreError::InvalidStoredValue {
                field: pragma,
                value,
            }
        }
        SqliteAdapterError::Sqlite(_) => RuntimeStoreError::BackendUnavailable { operation },
    }
}

