use rusqlite::Connection;

use crate::SqliteAdapterError;

pub const CURRENT_SCHEMA_VERSION: i64 = 1;
pub const EXPECTED_TABLES: [&str; 6] = [
    "state_events",
    "task_snapshots",
    "effects",
    "effect_transitions",
    "effect_attempts",
    "task_recovery_leases",
];

const INITIAL_SCHEMA_SQL: &str = r#"
CREATE TABLE IF NOT EXISTS state_events (
    state_event_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    worker_state TEXT NOT NULL,
    effect_status TEXT NOT NULL,
    probe_state TEXT,
    fencing_token INTEGER NOT NULL,
    triggered_by TEXT NOT NULL,
    occurred_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_state_events_task_id
    ON state_events(task_id);
CREATE INDEX IF NOT EXISTS idx_state_events_task_fencing_token
    ON state_events(task_id, fencing_token);

CREATE TABLE IF NOT EXISTS task_snapshots (
    task_id TEXT PRIMARY KEY,
    worker_state TEXT NOT NULL,
    effect_status TEXT NOT NULL,
    probe_state TEXT,
    last_state_event_id TEXT NOT NULL UNIQUE,
    fencing_token INTEGER NOT NULL,
    version INTEGER NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (last_state_event_id) REFERENCES state_events(state_event_id)
);

CREATE TABLE IF NOT EXISTS effects (
    effect_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    trace_id TEXT NOT NULL,
    intent_key TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    actor_kind TEXT NOT NULL,
    actor_plugin TEXT,
    action TEXT NOT NULL,
    target TEXT NOT NULL,
    probe_mode TEXT NOT NULL,
    tier TEXT NOT NULL,
    reversibility TEXT NOT NULL,
    compensates_effect_id TEXT,
    status TEXT NOT NULL,
    probe_state TEXT,
    UNIQUE(task_id, intent_key),
    FOREIGN KEY (compensates_effect_id) REFERENCES effects(effect_id)
);
CREATE INDEX IF NOT EXISTS idx_effects_task_id
    ON effects(task_id);
CREATE INDEX IF NOT EXISTS idx_effects_trace_id
    ON effects(trace_id);

CREATE TABLE IF NOT EXISTS effect_transitions (
    effect_id TEXT NOT NULL,
    transition_seq INTEGER NOT NULL,
    from_status TEXT NOT NULL,
    to_status TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    triggered_by TEXT NOT NULL,
    reason TEXT NOT NULL,
    PRIMARY KEY (effect_id, transition_seq),
    FOREIGN KEY (effect_id) REFERENCES effects(effect_id) ON DELETE CASCADE
);

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

CREATE TABLE IF NOT EXISTS effect_attempts (
    attempt_id TEXT PRIMARY KEY,
    effect_id TEXT NOT NULL,
    attempt_seq INTEGER NOT NULL,
    dispatched_at TEXT NOT NULL,
    lease_id TEXT NOT NULL,
    fencing_token INTEGER NOT NULL,
    result_status TEXT,
    UNIQUE(effect_id, attempt_seq),
    FOREIGN KEY (effect_id) REFERENCES effects(effect_id) ON DELETE CASCADE,
    FOREIGN KEY (lease_id) REFERENCES task_recovery_leases(lease_id)
);
CREATE INDEX IF NOT EXISTS idx_effect_attempts_effect_id
    ON effect_attempts(effect_id);
"#;

pub fn apply_migrations(connection: &Connection) -> Result<(), SqliteAdapterError> {
    let current_version: i64 =
        connection.query_row("PRAGMA user_version;", [], |row| row.get(0))?;
    if current_version == CURRENT_SCHEMA_VERSION {
        return Ok(());
    }
    if current_version != 0 {
        return Err(SqliteAdapterError::UnsupportedSchemaVersion {
            current: current_version,
            expected: CURRENT_SCHEMA_VERSION,
        });
    }

    connection.execute_batch(INITIAL_SCHEMA_SQL)?;
    connection.execute_batch(&format!("PRAGMA user_version={CURRENT_SCHEMA_VERSION};"))?;
    Ok(())
}
