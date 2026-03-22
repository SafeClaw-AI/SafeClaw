#![forbid(unsafe_code)]

mod connection;
mod effect_store;
mod error;
mod migrations;
mod orchestrator;
mod probe_executor;
mod runtime_store;
mod sandbox_executor;
mod state_engine;
mod worker_loop;
mod worker_service;

#[cfg(test)]
mod integration;

use std::path::Path;

pub use connection::{open_file_database, SqliteOpenOptions, DEFAULT_BUSY_TIMEOUT_MS};
pub use effect_store::SqliteEffectStore;
pub use error::SqliteAdapterError;
pub use migrations::{apply_migrations, CURRENT_SCHEMA_VERSION, EXPECTED_TABLES};
pub use orchestrator::SqliteTaskOrchestrator;
pub use probe_executor::{FileSystemProbeAdapter, NetworkProbeAdapter};
pub use runtime_store::{
    RuntimeDiagnosticSnapshot, RuntimeGovernanceDisposition, RuntimeGovernanceSummary,
    RuntimeGovernanceView, SqliteRuntimeStore,
};
pub use sandbox_executor::{
    LocalSandboxExecutor, RuntimeExecutionDirective, SandboxCommand,
    SandboxExecutionReport, SandboxExecutorError, SandboxRuntimeError,
};
use rusqlite::Connection;
pub use state_engine::SqliteStateEngine;
pub use worker_loop::{
    SqliteSingleWorkerLoop, WorkerLoopDispatchOutcome, WorkerLoopError, WorkerLoopOutcome,
    WorkerLoopProbeOutcome,
};
pub use worker_service::{SqliteWorkerService, WorkerServiceRunReport};

pub const ADAPTER_NAME: &str = "safeclaw-sqlite";

pub fn adapter_name() -> &'static str {
    ADAPTER_NAME
}

pub fn open_database(
    path: impl AsRef<Path>,
    options: SqliteOpenOptions,
) -> Result<Connection, SqliteAdapterError> {
    let connection = open_file_database(path, options)?;
    apply_migrations(&connection)?;
    Ok(connection)
}

#[cfg(test)]
mod tests {
    use super::{
        adapter_name, open_database, open_file_database, SqliteOpenOptions, ADAPTER_NAME,
        CURRENT_SCHEMA_VERSION, DEFAULT_BUSY_TIMEOUT_MS, EXPECTED_TABLES,
    };
    use std::{
        collections::BTreeSet,
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
                "safeclaw-sqlite-{label}-{}-{unique}.db",
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
    fn open_database_configures_expected_pragmas() {
        let temp_db = TempDatabase::new("pragmas");
        let connection = open_database(temp_db.path(), SqliteOpenOptions::default())
            .expect("sqlite adapter must open file database");

        let journal_mode: String = connection
            .query_row("PRAGMA journal_mode;", [], |row| row.get(0))
            .expect("journal mode must be queryable");
        let foreign_keys: i64 = connection
            .query_row("PRAGMA foreign_keys;", [], |row| row.get(0))
            .expect("foreign_keys pragma must be queryable");
        let busy_timeout: i64 = connection
            .query_row("PRAGMA busy_timeout;", [], |row| row.get(0))
            .expect("busy_timeout pragma must be queryable");

        assert_eq!(adapter_name(), ADAPTER_NAME);
        assert_eq!(journal_mode.to_ascii_lowercase(), "wal");
        assert_eq!(foreign_keys, 1);
        assert_eq!(busy_timeout, DEFAULT_BUSY_TIMEOUT_MS as i64);
    }

    #[test]
    fn open_database_applies_orchestrator_ready_schema() {
        let temp_db = TempDatabase::new("schema");
        let connection = open_database(temp_db.path(), SqliteOpenOptions::default())
            .expect("sqlite adapter must apply schema migrations");

        let table_names = read_table_names(&connection);
        for expected in EXPECTED_TABLES {
            assert!(table_names.contains(expected), "missing table {expected}");
        }

        let user_version: i64 = connection
            .query_row("PRAGMA user_version;", [], |row| row.get(0))
            .expect("user_version must be queryable");
        assert_eq!(user_version, CURRENT_SCHEMA_VERSION);
    }

    #[test]
    fn open_database_migrates_v1_lease_index_to_history_friendly_schema() {
        let temp_db = TempDatabase::new("migrate-v1");
        let connection = open_file_database(temp_db.path(), SqliteOpenOptions::default())
            .expect("sqlite adapter must open v1 database");
        connection
            .execute_batch(
                r#"
CREATE TABLE IF NOT EXISTS task_recovery_leases (
    lease_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    fencing_token INTEGER NOT NULL,
    ttl_ms INTEGER NOT NULL,
    expires_at_ms INTEGER NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_task_recovery_leases_task_id
    ON task_recovery_leases(task_id);
CREATE INDEX IF NOT EXISTS idx_task_recovery_leases_task_fencing_token
    ON task_recovery_leases(task_id, fencing_token);
PRAGMA user_version=1;
"#,
            )
            .expect("v1 schema must be created");
        drop(connection);

        let migrated = open_database(temp_db.path(), SqliteOpenOptions::default())
            .expect("sqlite adapter must migrate v1 schema");

        let user_version: i64 = migrated
            .query_row("PRAGMA user_version;", [], |row| row.get(0))
            .expect("user_version must be queryable");
        assert_eq!(user_version, CURRENT_SCHEMA_VERSION);

        let mut statement = migrated
            .prepare("PRAGMA index_list('task_recovery_leases')")
            .expect("index list pragma must prepare");
        let indexes: Vec<(String, i64)> = statement
            .query_map([], |row| {
                Ok((row.get::<_, String>(1)?, row.get::<_, i64>(2)?))
            })
            .expect("index list pragma must execute")
            .map(|row| row.expect("index row must be readable"))
            .collect();

        assert!(!indexes
            .iter()
            .any(|(name, _)| name == "idx_task_recovery_leases_task_id"));
        assert!(indexes.iter().any(|(name, unique)| name
            == "idx_task_recovery_leases_task_fencing_token"
            && *unique == 0));
    }

    fn read_table_names(connection: &rusqlite::Connection) -> BTreeSet<String> {
        let mut statement = connection
            .prepare("SELECT name FROM sqlite_master WHERE type='table'")
            .expect("sqlite_master query must prepare");
        statement
            .query_map([], |row| row.get::<_, String>(0))
            .expect("sqlite_master query must execute")
            .map(|name| name.expect("table name row must be readable"))
            .collect()
    }
}



