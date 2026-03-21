use std::{path::Path, time::Duration};

use rusqlite::Connection;

use crate::SqliteAdapterError;

pub const DEFAULT_BUSY_TIMEOUT_MS: u64 = 5_000;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct SqliteOpenOptions {
    pub busy_timeout_ms: u64,
}

impl Default for SqliteOpenOptions {
    fn default() -> Self {
        Self {
            busy_timeout_ms: DEFAULT_BUSY_TIMEOUT_MS,
        }
    }
}

pub fn open_file_database(
    path: impl AsRef<Path>,
    options: SqliteOpenOptions,
) -> Result<Connection, SqliteAdapterError> {
    let connection = Connection::open(path)?;
    configure_connection(&connection, options)?;
    Ok(connection)
}

fn configure_connection(
    connection: &Connection,
    options: SqliteOpenOptions,
) -> Result<(), SqliteAdapterError> {
    let journal_mode: String =
        connection.query_row("PRAGMA journal_mode=WAL;", [], |row| row.get(0))?;
    if !journal_mode.eq_ignore_ascii_case("wal") {
        return Err(SqliteAdapterError::InvalidPragmaValue {
            pragma: "journal_mode",
            value: journal_mode,
        });
    }

    connection.execute_batch("PRAGMA synchronous=NORMAL; PRAGMA foreign_keys=ON;")?;
    connection.busy_timeout(Duration::from_millis(options.busy_timeout_ms))?;
    Ok(())
}
