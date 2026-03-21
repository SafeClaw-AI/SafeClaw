#![forbid(unsafe_code)]

mod connection;
mod error;
mod migrations;
mod state_engine;

use std::path::Path;

pub use connection::{open_file_database, SqliteOpenOptions, DEFAULT_BUSY_TIMEOUT_MS};
pub use error::SqliteAdapterError;
pub use migrations::{apply_migrations, CURRENT_SCHEMA_VERSION, EXPECTED_TABLES};
use rusqlite::Connection;
pub use state_engine::SqliteStateEngine;

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
        adapter_name, open_database, SqliteOpenOptions, ADAPTER_NAME, CURRENT_SCHEMA_VERSION,
        DEFAULT_BUSY_TIMEOUT_MS, EXPECTED_TABLES,
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
    fn open_database_applies_six_table_schema() {
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
