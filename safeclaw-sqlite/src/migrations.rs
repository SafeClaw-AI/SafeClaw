use rusqlite::Connection;

use crate::SqliteAdapterError;

pub const CURRENT_SCHEMA_VERSION: i64 = 3;
pub const EXPECTED_TABLES: [&str; 8] = [
    "state_events",
    "task_snapshots",
    "effects",
    "effect_transitions",
    "effect_attempts",
    "task_recovery_leases",
    "orchestrator_tasks",
    "orchestrator_leases",
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
CREATE INDEX IF NOT EXISTS idx_task_recovery_leases_task_fencing_token
    ON task_recovery_leases(task_id, fencing_token DESC, expires_at_ms DESC);
CREATE INDEX IF NOT EXISTS idx_task_recovery_leases_task_expiry
    ON task_recovery_leases(task_id, expires_at_ms DESC);

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
CREATE TABLE IF NOT EXISTS orchestrator_tasks (
    task_id TEXT PRIMARY KEY,
    target_scope TEXT NOT NULL,
    requires_write INTEGER NOT NULL,
    doctor_bypass INTEGER NOT NULL,
    enqueued_at_ms INTEGER NOT NULL,
    is_completed INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_orchestrator_tasks_pending
    ON orchestrator_tasks(is_completed, enqueued_at_ms, task_id);

CREATE TABLE IF NOT EXISTS orchestrator_leases (
    lease_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    fencing_token INTEGER NOT NULL,
    ttl_ms INTEGER NOT NULL,
    issued_at_ms INTEGER NOT NULL,
    expires_at_ms INTEGER NOT NULL,
    released_at_ms INTEGER,
    UNIQUE(task_id, fencing_token),
    FOREIGN KEY (task_id) REFERENCES orchestrator_tasks(task_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_orchestrator_leases_active
    ON orchestrator_leases(task_id, released_at_ms, expires_at_ms DESC, fencing_token DESC);
CREATE INDEX IF NOT EXISTS idx_orchestrator_leases_expiry
    ON orchestrator_leases(released_at_ms, expires_at_ms, task_id);
"#;

pub fn apply_migrations(connection: &Connection) -> Result<(), SqliteAdapterError> {
    let current_version: i64 =
        connection.query_row("PRAGMA user_version;", [], |row| row.get(0))?;
    match current_version {
        CURRENT_SCHEMA_VERSION => Ok(()),
        0 => {
            connection.execute_batch(INITIAL_SCHEMA_SQL)?;
            connection.execute_batch(&format!("PRAGMA user_version={CURRENT_SCHEMA_VERSION};"))?;
            Ok(())
        }
        1 => {
            migrate_v1_to_v2(connection)?;
            migrate_v2_to_v3(connection)
        }
        2 => migrate_v2_to_v3(connection),
        _ => Err(SqliteAdapterError::UnsupportedSchemaVersion {
            current: current_version,
            expected: CURRENT_SCHEMA_VERSION,
        }),
    }
}

fn migrate_v1_to_v2(connection: &Connection) -> Result<(), SqliteAdapterError> {
    connection.execute_batch(
        r#"
DROP INDEX IF EXISTS idx_task_recovery_leases_task_id;
DROP INDEX IF EXISTS idx_task_recovery_leases_task_fencing_token;
CREATE INDEX IF NOT EXISTS idx_task_recovery_leases_task_fencing_token
    ON task_recovery_leases(task_id, fencing_token DESC, expires_at_ms DESC);
CREATE INDEX IF NOT EXISTS idx_task_recovery_leases_task_expiry
    ON task_recovery_leases(task_id, expires_at_ms DESC);
PRAGMA user_version=2;
"#,
    )?;
    Ok(())
}

fn migrate_v2_to_v3(connection: &Connection) -> Result<(), SqliteAdapterError> {
    connection.execute_batch(
        r#"
CREATE TABLE IF NOT EXISTS orchestrator_tasks (
    task_id TEXT PRIMARY KEY,
    target_scope TEXT NOT NULL,
    requires_write INTEGER NOT NULL,
    doctor_bypass INTEGER NOT NULL,
    enqueued_at_ms INTEGER NOT NULL,
    is_completed INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_orchestrator_tasks_pending
    ON orchestrator_tasks(is_completed, enqueued_at_ms, task_id);

CREATE TABLE IF NOT EXISTS orchestrator_leases (
    lease_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    fencing_token INTEGER NOT NULL,
    ttl_ms INTEGER NOT NULL,
    issued_at_ms INTEGER NOT NULL,
    expires_at_ms INTEGER NOT NULL,
    released_at_ms INTEGER,
    UNIQUE(task_id, fencing_token),
    FOREIGN KEY (task_id) REFERENCES orchestrator_tasks(task_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_orchestrator_leases_active
    ON orchestrator_leases(task_id, released_at_ms, expires_at_ms DESC, fencing_token DESC);
CREATE INDEX IF NOT EXISTS idx_orchestrator_leases_expiry
    ON orchestrator_leases(released_at_ms, expires_at_ms, task_id);
PRAGMA user_version=3;
"#,
    )?;
    Ok(())
}
