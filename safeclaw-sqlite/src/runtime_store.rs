use rusqlite::{Connection, TransactionBehavior};
use safeclaw_core::{
    state_engine::{StateApplyResult, StateEvent},
    InMemoryTaskRuntime, RuntimeStore, RuntimeStoreError,
};

use crate::{
    effect_store::{
        list_attempts_from_connection, load_effect_from_connection,
        load_latest_lease_from_connection, save_attempt_in_transaction, save_effect_in_transaction,
        save_lease_in_transaction,
    },
    state_engine::{apply_event_in_transaction, load_snapshot_from_connection},
    SqliteAdapterError,
};

pub struct SqliteRuntimeStore {
    connection: Connection,
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
    use super::SqliteRuntimeStore;
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

    fn demo_effect(probe_mode: ProbeMode) -> EffectRecord {
        let (effect_id, task_id) = match probe_mode {
            ProbeMode::Auto => ("effect-auto-runtime", "task-auto-runtime"),
            ProbeMode::None => ("effect-none-runtime", "task-none-runtime"),
        };

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

