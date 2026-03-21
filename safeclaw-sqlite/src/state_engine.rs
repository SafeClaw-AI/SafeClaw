use std::convert::TryFrom;

use rusqlite::{params, Connection, Error as RusqliteError, TransactionBehavior};
use safeclaw_core::{
    effect_ledger::{EffectStatus, ProbeState},
    state_engine::{StateApplyResult, StateEngine, StateEngineError, StateEvent, TaskSnapshot},
    worker_lifecycle::WorkerState,
};

pub struct SqliteStateEngine {
    connection: Connection,
}

impl SqliteStateEngine {
    pub fn new(connection: Connection) -> Self {
        Self { connection }
    }

    pub fn connection(&self) -> &Connection {
        &self.connection
    }

    pub fn into_connection(self) -> Connection {
        self.connection
    }
}

impl StateEngine for SqliteStateEngine {
    fn apply_event(&mut self, event: StateEvent) -> Result<StateApplyResult, StateEngineError> {
        let transaction = self
            .connection
            .transaction_with_behavior(TransactionBehavior::Immediate)
            .map_err(|_| backend_unavailable("begin_immediate"))?;

        let duplicate_count: i64 = transaction
            .query_row(
                "SELECT COUNT(1) FROM state_events WHERE state_event_id = ?1",
                [&event.state_event_id],
                |row| row.get(0),
            )
            .map_err(|_| backend_unavailable("lookup_duplicate_event"))?;
        if duplicate_count > 0 {
            return Ok(StateApplyResult::DuplicateIgnored);
        }

        let (current_fencing_token, current_version) =
            load_snapshot_meta(&transaction, &event.task_id)?;
        if event.fencing_token < current_fencing_token {
            return Err(StateEngineError::StaleFencingToken {
                current: current_fencing_token,
                provided: event.fencing_token,
            });
        }

        let StateEvent {
            state_event_id,
            task_id,
            worker_state,
            effect_status,
            probe_state,
            fencing_token,
            triggered_by,
            at,
        } = event;
        let next_version = current_version + 1;
        let worker_state_sql = encode_worker_state(worker_state);
        let effect_status_sql = encode_effect_status(effect_status);
        let probe_state_sql = probe_state.map(encode_probe_state);
        let fencing_token_sql = to_sql_i64(fencing_token, "encode_fencing_token")?;
        let version_sql = to_sql_i64(next_version, "encode_snapshot_version")?;

        transaction
            .execute(
                "INSERT INTO state_events (
                    state_event_id,
                    task_id,
                    worker_state,
                    effect_status,
                    probe_state,
                    fencing_token,
                    triggered_by,
                    occurred_at
                ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)",
                params![
                    &state_event_id,
                    &task_id,
                    worker_state_sql,
                    effect_status_sql,
                    probe_state_sql,
                    fencing_token_sql,
                    &triggered_by,
                    &at,
                ],
            )
            .map_err(|_| backend_unavailable("insert_state_event"))?;

        transaction
            .execute(
                "INSERT INTO task_snapshots (
                    task_id,
                    worker_state,
                    effect_status,
                    probe_state,
                    last_state_event_id,
                    fencing_token,
                    version,
                    updated_at
                ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)
                ON CONFLICT(task_id) DO UPDATE SET
                    worker_state = excluded.worker_state,
                    effect_status = excluded.effect_status,
                    probe_state = excluded.probe_state,
                    last_state_event_id = excluded.last_state_event_id,
                    fencing_token = excluded.fencing_token,
                    version = excluded.version,
                    updated_at = excluded.updated_at",
                params![
                    &task_id,
                    worker_state_sql,
                    effect_status_sql,
                    probe_state_sql,
                    &state_event_id,
                    fencing_token_sql,
                    version_sql,
                    &at,
                ],
            )
            .map_err(|_| backend_unavailable("upsert_task_snapshot"))?;

        transaction
            .commit()
            .map_err(|_| backend_unavailable("commit_state_event"))?;
        Ok(StateApplyResult::Applied)
    }

    fn load_snapshot(&self, task_id: &str) -> Result<Option<TaskSnapshot>, StateEngineError> {
        let raw_snapshot = match self.connection.query_row(
            "SELECT
                task_id,
                worker_state,
                effect_status,
                probe_state,
                last_state_event_id,
                fencing_token,
                version,
                updated_at
             FROM task_snapshots
             WHERE task_id = ?1",
            [task_id],
            |row| {
                Ok((
                    row.get::<_, String>(0)?,
                    row.get::<_, String>(1)?,
                    row.get::<_, String>(2)?,
                    row.get::<_, Option<String>>(3)?,
                    row.get::<_, String>(4)?,
                    row.get::<_, i64>(5)?,
                    row.get::<_, i64>(6)?,
                    row.get::<_, String>(7)?,
                ))
            },
        ) {
            Ok(snapshot) => snapshot,
            Err(RusqliteError::QueryReturnedNoRows) => return Ok(None),
            Err(_) => return Err(backend_unavailable("load_snapshot")),
        };

        let worker_state = decode_worker_state(&raw_snapshot.1)?;
        let effect_status = decode_effect_status(&raw_snapshot.2)?;
        let probe_state = decode_probe_state_opt(raw_snapshot.3)?;
        let fencing_token = from_sql_i64(raw_snapshot.5, "decode_fencing_token")?;
        let version = from_sql_i64(raw_snapshot.6, "decode_snapshot_version")?;

        Ok(Some(TaskSnapshot {
            task_id: raw_snapshot.0,
            worker_state,
            effect_status,
            probe_state,
            last_state_event_id: raw_snapshot.4,
            fencing_token,
            version,
            updated_at: raw_snapshot.7,
        }))
    }

    fn event_count(&self) -> usize {
        self.connection
            .query_row("SELECT COUNT(1) FROM state_events", [], |row| {
                row.get::<_, i64>(0)
            })
            .ok()
            .and_then(|count| usize::try_from(count).ok())
            .unwrap_or(0)
    }
}

fn load_snapshot_meta(
    transaction: &rusqlite::Transaction<'_>,
    task_id: &str,
) -> Result<(u64, u64), StateEngineError> {
    match transaction.query_row(
        "SELECT fencing_token, version FROM task_snapshots WHERE task_id = ?1",
        [task_id],
        |row| Ok((row.get::<_, i64>(0)?, row.get::<_, i64>(1)?)),
    ) {
        Ok((fencing_token, version)) => Ok((
            from_sql_i64(fencing_token, "decode_current_fencing_token")?,
            from_sql_i64(version, "decode_current_snapshot_version")?,
        )),
        Err(RusqliteError::QueryReturnedNoRows) => Ok((0, 0)),
        Err(_) => Err(backend_unavailable("load_snapshot_meta")),
    }
}

fn encode_worker_state(state: WorkerState) -> &'static str {
    match state {
        WorkerState::Created => "created",
        WorkerState::Planning => "planning",
        WorkerState::AwaitingConfirmation => "awaiting_confirmation",
        WorkerState::Hibernated => "hibernated",
        WorkerState::Executing => "executing",
        WorkerState::Uncertain => "uncertain",
        WorkerState::Committing => "committing",
        WorkerState::Succeeded => "succeeded",
        WorkerState::Failed => "failed",
        WorkerState::RollingBack => "rolling_back",
        WorkerState::RolledBack => "rolled_back",
        WorkerState::AwaitingDoctor => "awaiting_doctor",
        WorkerState::Repairing => "repairing",
        WorkerState::Repaired => "repaired",
        WorkerState::RepairFailed => "repair_failed",
        WorkerState::FailedTerminal => "failed_terminal",
        WorkerState::Closed => "closed",
    }
}

fn decode_worker_state(value: &str) -> Result<WorkerState, StateEngineError> {
    match value {
        "created" => Ok(WorkerState::Created),
        "planning" => Ok(WorkerState::Planning),
        "awaiting_confirmation" => Ok(WorkerState::AwaitingConfirmation),
        "hibernated" => Ok(WorkerState::Hibernated),
        "executing" => Ok(WorkerState::Executing),
        "uncertain" => Ok(WorkerState::Uncertain),
        "committing" => Ok(WorkerState::Committing),
        "succeeded" => Ok(WorkerState::Succeeded),
        "failed" => Ok(WorkerState::Failed),
        "rolling_back" => Ok(WorkerState::RollingBack),
        "rolled_back" => Ok(WorkerState::RolledBack),
        "awaiting_doctor" => Ok(WorkerState::AwaitingDoctor),
        "repairing" => Ok(WorkerState::Repairing),
        "repaired" => Ok(WorkerState::Repaired),
        "repair_failed" => Ok(WorkerState::RepairFailed),
        "failed_terminal" => Ok(WorkerState::FailedTerminal),
        "closed" => Ok(WorkerState::Closed),
        _ => Err(backend_unavailable("decode_worker_state")),
    }
}

fn encode_effect_status(status: EffectStatus) -> &'static str {
    match status {
        EffectStatus::Prepared => "prepared",
        EffectStatus::Dispatched => "dispatched",
        EffectStatus::Executed => "executed",
        EffectStatus::Uncertain => "uncertain",
        EffectStatus::ExecutedAssumed => "executed_assumed",
        EffectStatus::Previewed => "previewed",
        EffectStatus::Confirmed => "confirmed",
        EffectStatus::RolledBack => "rolled_back",
        EffectStatus::Compensated => "compensated",
        EffectStatus::Cancelled => "cancelled",
        EffectStatus::Expired => "expired",
    }
}

fn decode_effect_status(value: &str) -> Result<EffectStatus, StateEngineError> {
    match value {
        "prepared" => Ok(EffectStatus::Prepared),
        "dispatched" => Ok(EffectStatus::Dispatched),
        "executed" => Ok(EffectStatus::Executed),
        "uncertain" => Ok(EffectStatus::Uncertain),
        "executed_assumed" => Ok(EffectStatus::ExecutedAssumed),
        "previewed" => Ok(EffectStatus::Previewed),
        "confirmed" => Ok(EffectStatus::Confirmed),
        "rolled_back" => Ok(EffectStatus::RolledBack),
        "compensated" => Ok(EffectStatus::Compensated),
        "cancelled" => Ok(EffectStatus::Cancelled),
        "expired" => Ok(EffectStatus::Expired),
        _ => Err(backend_unavailable("decode_effect_status")),
    }
}

fn encode_probe_state(state: ProbeState) -> &'static str {
    match state {
        ProbeState::ProbePending => "probe_pending",
        ProbeState::Probing => "probing",
        ProbeState::ProbeFailed => "probe_failed",
        ProbeState::HumanFrozen => "human_frozen",
    }
}

fn decode_probe_state_opt(value: Option<String>) -> Result<Option<ProbeState>, StateEngineError> {
    match value.as_deref() {
        Some("probe_pending") => Ok(Some(ProbeState::ProbePending)),
        Some("probing") => Ok(Some(ProbeState::Probing)),
        Some("probe_failed") => Ok(Some(ProbeState::ProbeFailed)),
        Some("human_frozen") => Ok(Some(ProbeState::HumanFrozen)),
        Some(_) => Err(backend_unavailable("decode_probe_state")),
        None => Ok(None),
    }
}

fn to_sql_i64(value: u64, operation: &'static str) -> Result<i64, StateEngineError> {
    i64::try_from(value).map_err(|_| backend_unavailable(operation))
}

fn from_sql_i64(value: i64, operation: &'static str) -> Result<u64, StateEngineError> {
    u64::try_from(value).map_err(|_| backend_unavailable(operation))
}

fn backend_unavailable(operation: &'static str) -> StateEngineError {
    StateEngineError::BackendUnavailable { operation }
}

#[cfg(test)]
mod tests {
    use super::SqliteStateEngine;
    use crate::{open_database, SqliteOpenOptions};
    use safeclaw_core::{
        effect_ledger::{EffectStatus, ProbeState},
        state_engine::{StateApplyResult, StateEngine, StateEngineError, StateEvent},
        worker_lifecycle::WorkerState,
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
                "safeclaw-state-engine-{label}-{}-{unique}.db",
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
    fn apply_event_persists_snapshot_and_event_count() {
        let temp_db = TempDatabase::new("persist");
        let connection = open_database(temp_db.path(), SqliteOpenOptions::default())
            .expect("sqlite adapter must open test database");
        let mut engine = SqliteStateEngine::new(connection);

        let applied = engine.apply_event(sample_event("event-1", 3, WorkerState::Executing));
        assert_eq!(applied.unwrap(), StateApplyResult::Applied);
        assert_eq!(engine.event_count(), 1);

        let snapshot = engine
            .load_snapshot("task-1")
            .expect("snapshot load must succeed")
            .expect("snapshot must exist");
        assert_eq!(snapshot.worker_state, WorkerState::Executing);
        assert_eq!(snapshot.effect_status, EffectStatus::Dispatched);
        assert_eq!(snapshot.probe_state, Some(ProbeState::ProbePending));
        assert_eq!(snapshot.fencing_token, 3);
        assert_eq!(snapshot.version, 1);
        assert_eq!(snapshot.last_state_event_id, "event-1");
    }

    #[test]
    fn duplicate_state_event_is_ignored() {
        let temp_db = TempDatabase::new("duplicate");
        let connection = open_database(temp_db.path(), SqliteOpenOptions::default())
            .expect("sqlite adapter must open test database");
        let mut engine = SqliteStateEngine::new(connection);
        let event = sample_event("event-dup", 7, WorkerState::Planning);

        assert_eq!(
            engine.apply_event(event.clone()).unwrap(),
            StateApplyResult::Applied
        );
        assert_eq!(
            engine.apply_event(event).unwrap(),
            StateApplyResult::DuplicateIgnored
        );
        assert_eq!(engine.event_count(), 1);
        assert_eq!(
            engine
                .load_snapshot("task-1")
                .unwrap()
                .expect("snapshot must exist")
                .version,
            1
        );
    }

    #[test]
    fn stale_fencing_token_is_rejected() {
        let temp_db = TempDatabase::new("stale");
        let connection = open_database(temp_db.path(), SqliteOpenOptions::default())
            .expect("sqlite adapter must open test database");
        let mut engine = SqliteStateEngine::new(connection);

        assert_eq!(
            engine
                .apply_event(sample_event("event-fresh", 9, WorkerState::Executing))
                .unwrap(),
            StateApplyResult::Applied
        );

        let stale = engine.apply_event(sample_event("event-stale", 4, WorkerState::Failed));
        assert_eq!(
            stale,
            Err(StateEngineError::StaleFencingToken {
                current: 9,
                provided: 4,
            })
        );
        assert_eq!(engine.event_count(), 1);
        assert_eq!(
            engine
                .load_snapshot("task-1")
                .unwrap()
                .expect("snapshot must exist")
                .worker_state,
            WorkerState::Executing
        );
    }

    #[test]
    fn snapshot_roundtrips_across_reopen() {
        let temp_db = TempDatabase::new("reopen");
        {
            let connection = open_database(temp_db.path(), SqliteOpenOptions::default())
                .expect("sqlite adapter must open test database");
            let mut engine = SqliteStateEngine::new(connection);
            engine
                .apply_event(sample_event("event-reopen", 11, WorkerState::Uncertain))
                .expect("event apply must succeed");
        }

        let reopened = open_database(temp_db.path(), SqliteOpenOptions::default())
            .expect("sqlite adapter must reopen test database");
        let engine = SqliteStateEngine::new(reopened);
        let snapshot = engine
            .load_snapshot("task-1")
            .expect("snapshot load must succeed")
            .expect("snapshot must exist after reopen");

        assert_eq!(snapshot.worker_state, WorkerState::Uncertain);
        assert_eq!(snapshot.fencing_token, 11);
        assert_eq!(snapshot.version, 1);
        assert_eq!(engine.event_count(), 1);
    }

    fn sample_event(
        state_event_id: &str,
        fencing_token: u64,
        worker_state: WorkerState,
    ) -> StateEvent {
        StateEvent {
            state_event_id: state_event_id.to_string(),
            task_id: "task-1".to_string(),
            worker_state,
            effect_status: EffectStatus::Dispatched,
            probe_state: Some(ProbeState::ProbePending),
            fencing_token,
            triggered_by: "sqlite-test".to_string(),
            at: "2026-03-21T00:00:00Z".to_string(),
        }
    }
}
