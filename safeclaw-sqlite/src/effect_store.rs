use std::convert::TryFrom;

use rusqlite::{params, Connection, Error as RusqliteError, TransactionBehavior};
use safeclaw_core::effect_ledger::{
    AttemptResultStatus, EffectAction, EffectActor, EffectAttempt, EffectRecord,
    EffectReversibility, EffectStatus, EffectStore, EffectStoreError, EffectTier,
    EffectTransitionRecord, ProbeMode, ProbeState, RecoveryLease, EFFECT_LEDGER_SCHEMA_VERSION,
};

use crate::SqliteAdapterError;

pub struct SqliteEffectStore {
    connection: Connection,
}

impl SqliteEffectStore {
    pub fn new(connection: Connection) -> Self {
        Self { connection }
    }

    pub fn connection(&self) -> &Connection {
        &self.connection
    }

    pub fn into_connection(self) -> Connection {
        self.connection
    }

    pub fn save_effect(&mut self, effect: &EffectRecord) -> Result<(), SqliteAdapterError> {
        let transaction = self
            .connection
            .transaction_with_behavior(TransactionBehavior::Immediate)?;
        save_effect_in_transaction(&transaction, effect)?;
        transaction.commit()?;
        Ok(())
    }

    pub fn load_effect(&self, effect_id: &str) -> Result<Option<EffectRecord>, SqliteAdapterError> {
        load_effect_from_connection(&self.connection, effect_id)
    }

    pub fn save_lease(
        &mut self,
        task_id: &str,
        lease: &RecoveryLease,
    ) -> Result<(), SqliteAdapterError> {
        let transaction = self
            .connection
            .transaction_with_behavior(TransactionBehavior::Immediate)?;
        save_lease_in_transaction(&transaction, task_id, lease)?;
        transaction.commit()?;
        Ok(())
    }

    pub fn load_latest_lease(
        &self,
        task_id: &str,
    ) -> Result<Option<RecoveryLease>, SqliteAdapterError> {
        load_latest_lease_from_connection(&self.connection, task_id)
    }

    pub fn list_leases(&self, task_id: &str) -> Result<Vec<RecoveryLease>, SqliteAdapterError> {
        list_leases_from_connection(&self.connection, task_id)
    }

    pub fn save_attempt(&mut self, attempt: &EffectAttempt) -> Result<(), SqliteAdapterError> {
        let transaction = self
            .connection
            .transaction_with_behavior(TransactionBehavior::Immediate)?;
        save_attempt_in_transaction(&transaction, attempt)?;
        transaction.commit()?;
        Ok(())
    }

    pub fn list_attempts(&self, effect_id: &str) -> Result<Vec<EffectAttempt>, SqliteAdapterError> {
        list_attempts_from_connection(&self.connection, effect_id)
    }
}

impl EffectStore for SqliteEffectStore {
    fn save_effect(&mut self, effect: &EffectRecord) -> Result<(), EffectStoreError> {
        SqliteEffectStore::save_effect(self, effect).map_err(|_| {
            EffectStoreError::BackendUnavailable {
                operation: "save_effect",
            }
        })
    }

    fn load_effect(&self, effect_id: &str) -> Result<Option<EffectRecord>, EffectStoreError> {
        SqliteEffectStore::load_effect(self, effect_id).map_err(|_| {
            EffectStoreError::BackendUnavailable {
                operation: "load_effect",
            }
        })
    }

    fn save_lease(&mut self, task_id: &str, lease: &RecoveryLease) -> Result<(), EffectStoreError> {
        SqliteEffectStore::save_lease(self, task_id, lease).map_err(|_| {
            EffectStoreError::BackendUnavailable {
                operation: "save_lease",
            }
        })
    }

    fn load_latest_lease(&self, task_id: &str) -> Result<Option<RecoveryLease>, EffectStoreError> {
        SqliteEffectStore::load_latest_lease(self, task_id).map_err(|_| {
            EffectStoreError::BackendUnavailable {
                operation: "load_latest_lease",
            }
        })
    }

    fn list_leases(&self, task_id: &str) -> Result<Vec<RecoveryLease>, EffectStoreError> {
        SqliteEffectStore::list_leases(self, task_id).map_err(|_| {
            EffectStoreError::BackendUnavailable {
                operation: "list_leases",
            }
        })
    }

    fn save_attempt(&mut self, attempt: &EffectAttempt) -> Result<(), EffectStoreError> {
        SqliteEffectStore::save_attempt(self, attempt).map_err(|_| {
            EffectStoreError::BackendUnavailable {
                operation: "save_attempt",
            }
        })
    }

    fn list_attempts(&self, effect_id: &str) -> Result<Vec<EffectAttempt>, EffectStoreError> {
        SqliteEffectStore::list_attempts(self, effect_id).map_err(|_| {
            EffectStoreError::BackendUnavailable {
                operation: "list_attempts",
            }
        })
    }
}

pub(crate) fn save_effect_in_transaction(
    transaction: &rusqlite::Transaction<'_>,
    effect: &EffectRecord,
) -> Result<(), SqliteAdapterError> {
    let (actor_kind, actor_plugin) = encode_actor(&effect.actor);
    transaction.execute(
        "INSERT INTO effects (
            effect_id,
            task_id,
            trace_id,
            intent_key,
            schema_version,
            actor_kind,
            actor_plugin,
            action,
            target,
            probe_mode,
            tier,
            reversibility,
            compensates_effect_id,
            status,
            probe_state
        ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14, ?15)
        ON CONFLICT(effect_id) DO UPDATE SET
            task_id = excluded.task_id,
            trace_id = excluded.trace_id,
            intent_key = excluded.intent_key,
            schema_version = excluded.schema_version,
            actor_kind = excluded.actor_kind,
            actor_plugin = excluded.actor_plugin,
            action = excluded.action,
            target = excluded.target,
            probe_mode = excluded.probe_mode,
            tier = excluded.tier,
            reversibility = excluded.reversibility,
            compensates_effect_id = excluded.compensates_effect_id,
            status = excluded.status,
            probe_state = excluded.probe_state",
        params![
            &effect.effect_id,
            &effect.task_id,
            &effect.trace_id,
            &effect.intent_key,
            effect.schema_version,
            actor_kind,
            actor_plugin,
            encode_action(effect.action),
            &effect.target,
            encode_probe_mode(effect.probe_mode),
            encode_tier(effect.tier),
            encode_reversibility(effect.reversibility),
            effect.compensates_effect_id.as_deref(),
            encode_effect_status(effect.status),
            effect.probe_state.map(encode_probe_state),
        ],
    )?;

    for (index, transition) in effect.transitions.iter().enumerate() {
        transaction.execute(
            "INSERT OR IGNORE INTO effect_transitions (
                effect_id,
                transition_seq,
                from_status,
                to_status,
                occurred_at,
                triggered_by,
                reason
            ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)",
            params![
                &effect.effect_id,
                to_sql_i64((index + 1) as u64, "effect_transition_seq")?,
                encode_effect_status(transition.from_status),
                encode_effect_status(transition.to_status),
                &transition.at,
                &transition.triggered_by,
                &transition.reason,
            ],
        )?;
    }

    Ok(())
}

pub(crate) fn load_effect_from_connection(
    connection: &Connection,
    effect_id: &str,
) -> Result<Option<EffectRecord>, SqliteAdapterError> {
    let raw_effect = match connection.query_row(
        "SELECT
            effect_id,
            task_id,
            trace_id,
            intent_key,
            schema_version,
            actor_kind,
            actor_plugin,
            action,
            target,
            probe_mode,
            tier,
            reversibility,
            compensates_effect_id,
            status,
            probe_state
         FROM effects
         WHERE effect_id = ?1",
        [effect_id],
        |row| {
            Ok((
                row.get::<_, String>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, String>(2)?,
                row.get::<_, String>(3)?,
                row.get::<_, String>(4)?,
                row.get::<_, String>(5)?,
                row.get::<_, Option<String>>(6)?,
                row.get::<_, String>(7)?,
                row.get::<_, String>(8)?,
                row.get::<_, String>(9)?,
                row.get::<_, String>(10)?,
                row.get::<_, String>(11)?,
                row.get::<_, Option<String>>(12)?,
                row.get::<_, String>(13)?,
                row.get::<_, Option<String>>(14)?,
            ))
        },
    ) {
        Ok(effect) => effect,
        Err(RusqliteError::QueryReturnedNoRows) => return Ok(None),
        Err(error) => return Err(error.into()),
    };

    let schema_version = decode_schema_version(&raw_effect.4)?;
    let actor = decode_actor(&raw_effect.5, raw_effect.6)?;
    let action = decode_action(&raw_effect.7)?;
    let probe_mode = decode_probe_mode(&raw_effect.9)?;
    let tier = decode_tier(&raw_effect.10)?;
    let reversibility = decode_reversibility(&raw_effect.11)?;
    let status = decode_effect_status(&raw_effect.13)?;
    let probe_state = decode_probe_state_opt(raw_effect.14)?;
    let transitions = load_transitions_from_connection(connection, effect_id)?;

    Ok(Some(EffectRecord {
        effect_id: raw_effect.0,
        task_id: raw_effect.1,
        trace_id: raw_effect.2,
        intent_key: raw_effect.3,
        schema_version,
        actor,
        action,
        target: raw_effect.8,
        probe_mode,
        tier,
        reversibility,
        compensates_effect_id: raw_effect.12,
        status,
        probe_state,
        transitions,
    }))
}

pub(crate) fn save_lease_in_transaction(
    transaction: &rusqlite::Transaction<'_>,
    task_id: &str,
    lease: &RecoveryLease,
) -> Result<(), SqliteAdapterError> {
    transaction.execute(
        "INSERT INTO task_recovery_leases (
            lease_id,
            task_id,
            owner_id,
            fencing_token,
            ttl_ms,
            expires_at_ms
        ) VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        ON CONFLICT(lease_id) DO UPDATE SET
            task_id = excluded.task_id,
            owner_id = excluded.owner_id,
            fencing_token = excluded.fencing_token,
            ttl_ms = excluded.ttl_ms,
            expires_at_ms = excluded.expires_at_ms",
        params![
            &lease.lease_id,
            task_id,
            &lease.owner_id,
            to_sql_i64(lease.fencing_token, "lease_fencing_token")?,
            to_sql_i64(lease.ttl_ms, "lease_ttl_ms")?,
            to_sql_i64(lease.expires_at_ms, "lease_expires_at_ms")?,
        ],
    )?;
    Ok(())
}

pub(crate) fn load_latest_lease_from_connection(
    connection: &Connection,
    task_id: &str,
) -> Result<Option<RecoveryLease>, SqliteAdapterError> {
    let leases = list_leases_from_connection(connection, task_id)?;
    Ok(leases.into_iter().next())
}

pub(crate) fn list_leases_from_connection(
    connection: &Connection,
    task_id: &str,
) -> Result<Vec<RecoveryLease>, SqliteAdapterError> {
    let mut statement = connection.prepare(
        "SELECT lease_id, owner_id, fencing_token, ttl_ms, expires_at_ms
         FROM task_recovery_leases
         WHERE task_id = ?1
         ORDER BY fencing_token DESC, expires_at_ms DESC, lease_id DESC",
    )?;

    let leases = statement
        .query_map([task_id], |row| {
            Ok((
                row.get::<_, String>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, i64>(2)?,
                row.get::<_, i64>(3)?,
                row.get::<_, i64>(4)?,
            ))
        })?
        .map(|row| {
            let (lease_id, owner_id, fencing_token, ttl_ms, expires_at_ms) = row?;
            Ok(RecoveryLease {
                lease_id,
                owner_id,
                fencing_token: from_sql_i64(fencing_token, "lease_fencing_token")?,
                ttl_ms: from_sql_i64(ttl_ms, "lease_ttl_ms")?,
                expires_at_ms: from_sql_i64(expires_at_ms, "lease_expires_at_ms")?,
            })
        })
        .collect();
    leases
}

pub(crate) fn save_attempt_in_transaction(
    transaction: &rusqlite::Transaction<'_>,
    attempt: &EffectAttempt,
) -> Result<(), SqliteAdapterError> {
    transaction.execute(
        "INSERT INTO effect_attempts (
            attempt_id,
            effect_id,
            attempt_seq,
            dispatched_at,
            lease_id,
            fencing_token,
            result_status
        ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
        ON CONFLICT(attempt_id) DO UPDATE SET
            effect_id = excluded.effect_id,
            attempt_seq = excluded.attempt_seq,
            dispatched_at = excluded.dispatched_at,
            lease_id = excluded.lease_id,
            fencing_token = excluded.fencing_token,
            result_status = excluded.result_status",
        params![
            &attempt.attempt_id,
            &attempt.effect_id,
            to_sql_i64(attempt.attempt_seq, "attempt_seq")?,
            &attempt.dispatched_at,
            &attempt.lease_id,
            to_sql_i64(attempt.fencing_token, "attempt_fencing_token")?,
            attempt.result_status.map(encode_attempt_result_status),
        ],
    )?;
    Ok(())
}

pub(crate) fn list_attempts_from_connection(
    connection: &Connection,
    effect_id: &str,
) -> Result<Vec<EffectAttempt>, SqliteAdapterError> {
    let mut statement = connection.prepare(
        "SELECT attempt_id, effect_id, attempt_seq, dispatched_at, lease_id, fencing_token, result_status
         FROM effect_attempts
         WHERE effect_id = ?1
         ORDER BY attempt_seq ASC",
    )?;

    let attempts = statement
        .query_map([effect_id], |row| {
            Ok((
                row.get::<_, String>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, i64>(2)?,
                row.get::<_, String>(3)?,
                row.get::<_, String>(4)?,
                row.get::<_, i64>(5)?,
                row.get::<_, Option<String>>(6)?,
            ))
        })?
        .map(|row| {
            let (
                attempt_id,
                effect_id,
                attempt_seq,
                dispatched_at,
                lease_id,
                fencing_token,
                result_status,
            ) = row?;
            Ok(EffectAttempt {
                attempt_id,
                effect_id,
                attempt_seq: from_sql_i64(attempt_seq, "attempt_seq")?,
                dispatched_at,
                lease_id,
                fencing_token: from_sql_i64(fencing_token, "attempt_fencing_token")?,
                result_status: decode_attempt_result_status_opt(result_status)?,
            })
        })
        .collect();
    attempts
}

pub(crate) fn load_transitions_from_connection(
    connection: &Connection,
    effect_id: &str,
) -> Result<Vec<EffectTransitionRecord>, SqliteAdapterError> {
    let mut statement = connection.prepare(
        "SELECT from_status, to_status, occurred_at, triggered_by, reason
         FROM effect_transitions
         WHERE effect_id = ?1
         ORDER BY transition_seq ASC",
    )?;

    let transitions = statement
        .query_map([effect_id], |row| {
            Ok((
                row.get::<_, String>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, String>(2)?,
                row.get::<_, String>(3)?,
                row.get::<_, String>(4)?,
            ))
        })?
        .map(|row| {
            let (from_status, to_status, at, triggered_by, reason) = row?;
            Ok(EffectTransitionRecord {
                from_status: decode_effect_status(&from_status)?,
                to_status: decode_effect_status(&to_status)?,
                at,
                triggered_by,
                reason,
            })
        })
        .collect();
    transitions
}

fn encode_actor(actor: &EffectActor) -> (&'static str, Option<&str>) {
    match actor {
        EffectActor::Worker => ("worker", None),
        EffectActor::Doctor => ("doctor", None),
        EffectActor::Plugin(name) => ("plugin", Some(name.as_str())),
    }
}

fn decode_actor(
    actor_kind: &str,
    actor_plugin: Option<String>,
) -> Result<EffectActor, SqliteAdapterError> {
    match actor_kind {
        "worker" => Ok(EffectActor::Worker),
        "doctor" => Ok(EffectActor::Doctor),
        "plugin" => actor_plugin.map(EffectActor::Plugin).ok_or_else(|| {
            SqliteAdapterError::InvalidStoredValue {
                field: "actor_plugin",
                value: String::from("<missing-for-plugin>"),
            }
        }),
        _ => Err(SqliteAdapterError::InvalidStoredValue {
            field: "actor_kind",
            value: actor_kind.to_string(),
        }),
    }
}

fn encode_action(action: EffectAction) -> &'static str {
    match action {
        EffectAction::FileRead => "file_read",
        EffectAction::FileWrite => "file_write",
        EffectAction::FileDelete => "file_delete",
        EffectAction::FileMove => "file_move",
        EffectAction::DirCreate => "dir_create",
        EffectAction::DirDelete => "dir_delete",
        EffectAction::NetworkRequest => "network_request",
        EffectAction::SystemExec => "system_exec",
        EffectAction::ClipboardWrite => "clipboard_write",
        EffectAction::ConfigChange => "config_change",
        EffectAction::PluginInstall => "plugin_install",
        EffectAction::PluginUninstall => "plugin_uninstall",
    }
}

fn decode_action(value: &str) -> Result<EffectAction, SqliteAdapterError> {
    match value {
        "file_read" => Ok(EffectAction::FileRead),
        "file_write" => Ok(EffectAction::FileWrite),
        "file_delete" => Ok(EffectAction::FileDelete),
        "file_move" => Ok(EffectAction::FileMove),
        "dir_create" => Ok(EffectAction::DirCreate),
        "dir_delete" => Ok(EffectAction::DirDelete),
        "network_request" => Ok(EffectAction::NetworkRequest),
        "system_exec" => Ok(EffectAction::SystemExec),
        "clipboard_write" => Ok(EffectAction::ClipboardWrite),
        "config_change" => Ok(EffectAction::ConfigChange),
        "plugin_install" => Ok(EffectAction::PluginInstall),
        "plugin_uninstall" => Ok(EffectAction::PluginUninstall),
        _ => Err(SqliteAdapterError::InvalidStoredValue {
            field: "action",
            value: value.to_string(),
        }),
    }
}

fn encode_tier(tier: EffectTier) -> &'static str {
    match tier {
        EffectTier::Tier0 => "tier0",
        EffectTier::Tier1 => "tier1",
        EffectTier::Tier2 => "tier2",
    }
}

fn decode_tier(value: &str) -> Result<EffectTier, SqliteAdapterError> {
    match value {
        "tier0" => Ok(EffectTier::Tier0),
        "tier1" => Ok(EffectTier::Tier1),
        "tier2" => Ok(EffectTier::Tier2),
        _ => Err(SqliteAdapterError::InvalidStoredValue {
            field: "tier",
            value: value.to_string(),
        }),
    }
}

fn encode_reversibility(value: EffectReversibility) -> &'static str {
    match value {
        EffectReversibility::Rollbackable => "rollbackable",
        EffectReversibility::Compensatable => "compensatable",
        EffectReversibility::Irreversible => "irreversible",
    }
}

fn decode_reversibility(value: &str) -> Result<EffectReversibility, SqliteAdapterError> {
    match value {
        "rollbackable" => Ok(EffectReversibility::Rollbackable),
        "compensatable" => Ok(EffectReversibility::Compensatable),
        "irreversible" => Ok(EffectReversibility::Irreversible),
        _ => Err(SqliteAdapterError::InvalidStoredValue {
            field: "reversibility",
            value: value.to_string(),
        }),
    }
}

fn encode_probe_mode(mode: ProbeMode) -> &'static str {
    match mode {
        ProbeMode::Auto => "auto",
        ProbeMode::None => "none",
    }
}

fn decode_probe_mode(value: &str) -> Result<ProbeMode, SqliteAdapterError> {
    match value {
        "auto" => Ok(ProbeMode::Auto),
        "none" => Ok(ProbeMode::None),
        _ => Err(SqliteAdapterError::InvalidStoredValue {
            field: "probe_mode",
            value: value.to_string(),
        }),
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

fn decode_probe_state_opt(value: Option<String>) -> Result<Option<ProbeState>, SqliteAdapterError> {
    match value.as_deref() {
        Some("probe_pending") => Ok(Some(ProbeState::ProbePending)),
        Some("probing") => Ok(Some(ProbeState::Probing)),
        Some("probe_failed") => Ok(Some(ProbeState::ProbeFailed)),
        Some("human_frozen") => Ok(Some(ProbeState::HumanFrozen)),
        Some(other) => Err(SqliteAdapterError::InvalidStoredValue {
            field: "probe_state",
            value: other.to_string(),
        }),
        None => Ok(None),
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

fn decode_effect_status(value: &str) -> Result<EffectStatus, SqliteAdapterError> {
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
        _ => Err(SqliteAdapterError::InvalidStoredValue {
            field: "status",
            value: value.to_string(),
        }),
    }
}

fn encode_attempt_result_status(status: AttemptResultStatus) -> &'static str {
    match status {
        AttemptResultStatus::Success => "success",
        AttemptResultStatus::Failure => "failure",
        AttemptResultStatus::Timeout => "timeout",
        AttemptResultStatus::Crash => "crash",
    }
}

fn decode_attempt_result_status_opt(
    value: Option<String>,
) -> Result<Option<AttemptResultStatus>, SqliteAdapterError> {
    match value.as_deref() {
        Some("success") => Ok(Some(AttemptResultStatus::Success)),
        Some("failure") => Ok(Some(AttemptResultStatus::Failure)),
        Some("timeout") => Ok(Some(AttemptResultStatus::Timeout)),
        Some("crash") => Ok(Some(AttemptResultStatus::Crash)),
        Some(other) => Err(SqliteAdapterError::InvalidStoredValue {
            field: "result_status",
            value: other.to_string(),
        }),
        None => Ok(None),
    }
}

fn decode_schema_version(value: &str) -> Result<&'static str, SqliteAdapterError> {
    if value == EFFECT_LEDGER_SCHEMA_VERSION {
        Ok(EFFECT_LEDGER_SCHEMA_VERSION)
    } else {
        Err(SqliteAdapterError::InvalidStoredValue {
            field: "schema_version",
            value: value.to_string(),
        })
    }
}

fn to_sql_i64(value: u64, field: &'static str) -> Result<i64, SqliteAdapterError> {
    i64::try_from(value).map_err(|_| SqliteAdapterError::IntegerOutOfRange {
        field,
        value: i64::MAX,
    })
}

fn from_sql_i64(value: i64, field: &'static str) -> Result<u64, SqliteAdapterError> {
    u64::try_from(value).map_err(|_| SqliteAdapterError::IntegerOutOfRange { field, value })
}

#[cfg(test)]
mod tests {
    use super::SqliteEffectStore;
    use crate::{open_database, SqliteOpenOptions};
    use safeclaw_core::effect_ledger::{
        AttemptResultStatus, EffectAction, EffectActor, EffectAttempt, EffectRecord,
        EffectReversibility, EffectTier, ProbeMode, ProbeState, RecoveryLease,
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
                "safeclaw-effect-store-{label}-{}-{unique}.db",
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
    fn effect_roundtrips_with_history_and_plugin_actor() {
        let temp_db = TempDatabase::new("effect-roundtrip");
        let connection = open_database(temp_db.path(), SqliteOpenOptions::default())
            .expect("sqlite adapter must open test database");
        let mut store = SqliteEffectStore::new(connection);

        let mut effect = demo_effect();
        effect
            .transition_to(
                safeclaw_core::effect_ledger::EffectStatus::Dispatched,
                "2026-03-21T01:00:00Z",
                "worker",
                "dispatch",
            )
            .unwrap();
        effect
            .transition_to(
                safeclaw_core::effect_ledger::EffectStatus::Uncertain,
                "2026-03-21T01:00:01Z",
                "worker",
                "crash",
            )
            .unwrap();

        store.save_effect(&effect).unwrap();
        let loaded = store.load_effect(&effect.effect_id).unwrap().unwrap();

        assert_eq!(loaded.effect_id, effect.effect_id);
        assert_eq!(loaded.task_id, effect.task_id);
        assert_eq!(loaded.intent_key, effect.intent_key);
        assert_eq!(loaded.actor, effect.actor);
        assert_eq!(loaded.status, effect.status);
        assert_eq!(loaded.probe_state, Some(ProbeState::ProbePending));
        assert_eq!(loaded.transitions, effect.transitions);
    }

    #[test]
    fn save_effect_remains_append_only_across_multiple_saves() {
        let temp_db = TempDatabase::new("effect-append-only");
        let connection = open_database(temp_db.path(), SqliteOpenOptions::default())
            .expect("sqlite adapter must open test database");
        let mut store = SqliteEffectStore::new(connection);

        let mut effect = demo_effect();
        effect
            .transition_to(
                safeclaw_core::effect_ledger::EffectStatus::Dispatched,
                "2026-03-21T02:00:00Z",
                "worker",
                "dispatch",
            )
            .unwrap();
        store.save_effect(&effect).unwrap();

        effect
            .transition_to(
                safeclaw_core::effect_ledger::EffectStatus::ExecutedAssumed,
                "2026-03-21T02:00:01Z",
                "worker",
                "assume",
            )
            .unwrap();
        store.save_effect(&effect).unwrap();
        store.save_effect(&effect).unwrap();

        let loaded = store.load_effect(&effect.effect_id).unwrap().unwrap();
        assert_eq!(loaded.transitions.len(), 2);
        assert_eq!(loaded.transitions, effect.transitions);
    }

    #[test]
    fn lease_history_keeps_multiple_entries_and_latest_lookup() {
        let temp_db = TempDatabase::new("lease-history");
        let connection = open_database(temp_db.path(), SqliteOpenOptions::default())
            .expect("sqlite adapter must open test database");
        let mut store = SqliteEffectStore::new(connection);

        let lease_a = RecoveryLease::new("lease-a", "doctor-a", 3, 0, 30_000);
        let lease_b = RecoveryLease::new("lease-b", "doctor-b", 4, 1_000, 30_000);
        store.save_lease("task-lease", &lease_a).unwrap();
        store.save_lease("task-lease", &lease_b).unwrap();

        let latest = store.load_latest_lease("task-lease").unwrap().unwrap();
        let leases = store.list_leases("task-lease").unwrap();

        assert_eq!(latest.lease_id, "lease-b");
        assert_eq!(leases.len(), 2);
        assert_eq!(leases[0].lease_id, "lease-b");
        assert_eq!(leases[1].lease_id, "lease-a");
    }

    #[test]
    fn attempts_roundtrip_and_update_result_status() {
        let temp_db = TempDatabase::new("attempts");
        let connection = open_database(temp_db.path(), SqliteOpenOptions::default())
            .expect("sqlite adapter must open test database");
        let mut store = SqliteEffectStore::new(connection);

        let effect = demo_effect();
        let lease = RecoveryLease::new("lease-attempt", "doctor-a", 7, 0, 30_000);
        store.save_effect(&effect).unwrap();
        store.save_lease(&effect.task_id, &lease).unwrap();

        let mut attempt = EffectAttempt::next_for_effect(
            &[],
            "attempt-1",
            effect.effect_id.clone(),
            "2026-03-21T03:00:00Z",
            &lease,
            0,
        )
        .unwrap();
        store.save_attempt(&attempt).unwrap();

        attempt
            .record_result(AttemptResultStatus::Success, &lease, 0)
            .unwrap();
        store.save_attempt(&attempt).unwrap();

        let attempts = store.list_attempts(&effect.effect_id).unwrap();
        assert_eq!(attempts.len(), 1);
        assert_eq!(attempts[0].attempt_seq, 1);
        assert_eq!(
            attempts[0].result_status,
            Some(AttemptResultStatus::Success)
        );
    }

    fn demo_effect() -> EffectRecord {
        EffectRecord::new(
            "effect-1",
            "task-1",
            "trace-1",
            "intent-1",
            EffectActor::Plugin(String::from("git")),
            EffectAction::FileWrite,
            "scope:/tmp/demo",
            EffectTier::Tier2,
            EffectReversibility::Compensatable,
            ProbeMode::Auto,
        )
    }
}
