use std::convert::TryFrom;

use rusqlite::{params, Connection, Error as RusqliteError, TransactionBehavior};
use safeclaw_core::{
    OrchestratorClaim, OrchestratorError, OrchestratorLease, OrchestratorSnapshot,
    OrchestratorTask, ScheduleIntent, TaskOrchestrator,
};

pub struct SqliteTaskOrchestrator {
    connection: Connection,
    lease_ttl_ms: u64,
}

impl SqliteTaskOrchestrator {
    pub fn new(connection: Connection) -> Self {
        Self {
            connection,
            lease_ttl_ms: 30_000,
        }
    }

    pub fn with_lease_ttl_ms(mut self, lease_ttl_ms: u64) -> Self {
        self.lease_ttl_ms = lease_ttl_ms;
        self
    }

    pub fn connection(&self) -> &Connection {
        &self.connection
    }

    pub fn into_connection(self) -> Connection {
        self.connection
    }
}

impl TaskOrchestrator for SqliteTaskOrchestrator {
    fn enqueue(&mut self, task: OrchestratorTask) -> Result<(), OrchestratorError> {
        match self.connection.execute(
            "INSERT INTO orchestrator_tasks (
                task_id,
                target_scope,
                requires_write,
                doctor_bypass,
                enqueued_at_ms,
                is_completed
            ) VALUES (?1, ?2, ?3, ?4, ?5, 0)",
            params![
                &task.task_id,
                &task.intent.target_scope,
                encode_bool(task.intent.requires_write),
                encode_bool(task.intent.doctor_bypass),
                to_sql_i64(task.enqueued_at_ms, "enqueue_task_at_ms")?,
            ],
        ) {
            Ok(_) => Ok(()),
            Err(RusqliteError::SqliteFailure(_, _)) => match load_task_completion_state(&self.connection, &task.task_id) {
                Ok(Some(true)) => Err(OrchestratorError::TaskAlreadyCompleted {
                    task_id: task.task_id,
                }),
                Ok(Some(false)) => Err(OrchestratorError::TaskAlreadyQueued {
                    task_id: task.task_id,
                }),
                Ok(None) => Err(backend_unavailable("enqueue_task")),
                Err(error) => Err(error),
            },
            Err(_) => Err(backend_unavailable("enqueue_task")),
        }
    }

    fn claim_next(
        &mut self,
        owner_id: impl Into<String>,
        now_ms: u64,
    ) -> Result<Option<OrchestratorClaim>, OrchestratorError> {
        let transaction = self
            .connection
            .transaction_with_behavior(TransactionBehavior::Immediate)
            .map_err(|_| backend_unavailable("begin_claim_next_task"))?;
        let _ = reap_expired_leases_in_transaction(&transaction, now_ms)?;

        let Some(task) = load_next_claimable_task(&transaction, now_ms)? else {
            transaction
                .commit()
                .map_err(|_| backend_unavailable("commit_empty_claim_next_task"))?;
            return Ok(None);
        };

        let last_fencing_token = load_max_fencing_token(&transaction, &task.task_id)?;
        let fencing_token = last_fencing_token + 1;
        let lease = OrchestratorLease {
            lease_id: format!("{}-lease-{}", task.task_id, fencing_token),
            task_id: task.task_id.clone(),
            owner_id: owner_id.into(),
            fencing_token,
            ttl_ms: self.lease_ttl_ms,
            expires_at_ms: now_ms.saturating_add(self.lease_ttl_ms),
        };

        transaction
            .execute(
                "INSERT INTO orchestrator_leases (
                    lease_id,
                    task_id,
                    owner_id,
                    fencing_token,
                    ttl_ms,
                    issued_at_ms,
                    expires_at_ms,
                    released_at_ms
                ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, NULL)",
                params![
                    &lease.lease_id,
                    &lease.task_id,
                    &lease.owner_id,
                    to_sql_i64(lease.fencing_token, "claim_task_fencing_token")?,
                    to_sql_i64(lease.ttl_ms, "claim_task_ttl_ms")?,
                    to_sql_i64(now_ms, "claim_task_issued_at_ms")?,
                    to_sql_i64(lease.expires_at_ms, "claim_task_expires_at_ms")?,
                ],
            )
            .map_err(|_| backend_unavailable("insert_orchestrator_lease"))?;
        transaction
            .commit()
            .map_err(|_| backend_unavailable("commit_claim_next_task"))?;

        Ok(Some(OrchestratorClaim { task, lease }))
    }

    fn renew_lease(
        &mut self,
        task_id: &str,
        lease_id: &str,
        owner_id: &str,
        now_ms: u64,
    ) -> Result<OrchestratorLease, OrchestratorError> {
        let transaction = self
            .connection
            .transaction_with_behavior(TransactionBehavior::Immediate)
            .map_err(|_| backend_unavailable("begin_renew_orchestrator_lease"))?;
        let lease = load_active_lease(&transaction, task_id)?
            .ok_or_else(|| OrchestratorError::LeaseNotFound {
                task_id: task_id.to_string(),
                lease_id: lease_id.to_string(),
            })?;

        if lease.lease_id != lease_id {
            return Err(OrchestratorError::LeaseNotFound {
                task_id: task_id.to_string(),
                lease_id: lease_id.to_string(),
            });
        }
        if lease.owner_id != owner_id {
            return Err(OrchestratorError::LeaseNotOwned {
                task_id: task_id.to_string(),
                lease_id: lease_id.to_string(),
                owner_id: owner_id.to_string(),
            });
        }
        if now_ms > lease.expires_at_ms {
            return Err(OrchestratorError::LeaseExpired {
                task_id: task_id.to_string(),
                lease_id: lease_id.to_string(),
                now_ms,
                expires_at_ms: lease.expires_at_ms,
            });
        }

        let renewed = OrchestratorLease {
            expires_at_ms: now_ms.saturating_add(lease.ttl_ms),
            ..lease
        };
        transaction
            .execute(
                "UPDATE orchestrator_leases
                 SET expires_at_ms = ?1
                 WHERE lease_id = ?2",
                params![
                    to_sql_i64(renewed.expires_at_ms, "renew_orchestrator_lease_expires_at_ms")?,
                    &renewed.lease_id,
                ],
            )
            .map_err(|_| backend_unavailable("renew_orchestrator_lease"))?;
        transaction
            .commit()
            .map_err(|_| backend_unavailable("commit_renew_orchestrator_lease"))?;
        Ok(renewed)
    }

    fn reap_expired_leases(
        &mut self,
        now_ms: u64,
    ) -> Result<Vec<OrchestratorLease>, OrchestratorError> {
        let transaction = self
            .connection
            .transaction_with_behavior(TransactionBehavior::Immediate)
            .map_err(|_| backend_unavailable("begin_reap_expired_orchestrator_leases"))?;
        let expired = reap_expired_leases_in_transaction(&transaction, now_ms)?;
        transaction
            .commit()
            .map_err(|_| backend_unavailable("commit_reap_expired_orchestrator_leases"))?;
        Ok(expired)
    }

    fn complete(
        &mut self,
        task_id: &str,
        lease_id: &str,
        owner_id: &str,
    ) -> Result<(), OrchestratorError> {
        let transaction = self
            .connection
            .transaction_with_behavior(TransactionBehavior::Immediate)
            .map_err(|_| backend_unavailable("begin_complete_task"))?;
        let lease = load_active_lease(&transaction, task_id)?
            .ok_or_else(|| OrchestratorError::LeaseNotFound {
                task_id: task_id.to_string(),
                lease_id: lease_id.to_string(),
            })?;

        if lease.lease_id != lease_id {
            return Err(OrchestratorError::LeaseNotFound {
                task_id: task_id.to_string(),
                lease_id: lease_id.to_string(),
            });
        }
        if lease.owner_id != owner_id {
            return Err(OrchestratorError::LeaseNotOwned {
                task_id: task_id.to_string(),
                lease_id: lease_id.to_string(),
                owner_id: owner_id.to_string(),
            });
        }

        transaction
            .execute(
                "UPDATE orchestrator_tasks
                 SET is_completed = 1
                 WHERE task_id = ?1",
                [task_id],
            )
            .map_err(|_| backend_unavailable("mark_task_completed"))?;
        transaction
            .execute(
                "UPDATE orchestrator_leases
                 SET released_at_ms = expires_at_ms
                 WHERE lease_id = ?1",
                [lease_id],
            )
            .map_err(|_| backend_unavailable("release_completed_task_lease"))?;
        transaction
            .commit()
            .map_err(|_| backend_unavailable("commit_complete_task"))?;
        Ok(())
    }

    fn queue_snapshot(&self) -> OrchestratorSnapshot {
        OrchestratorSnapshot {
            queued_tasks: list_queued_tasks(&self.connection).unwrap_or_default(),
            active_leases: list_active_leases(&self.connection).unwrap_or_default(),
            completed_task_ids: list_completed_task_ids(&self.connection).unwrap_or_default(),
        }
    }
}

fn load_task_completion_state(
    connection: &Connection,
    task_id: &str,
) -> Result<Option<bool>, OrchestratorError> {
    match connection.query_row(
        "SELECT is_completed FROM orchestrator_tasks WHERE task_id = ?1",
        [task_id],
        |row| row.get::<_, i64>(0),
    ) {
        Ok(value) => decode_bool(value, "task_is_completed").map(Some),
        Err(RusqliteError::QueryReturnedNoRows) => Ok(None),
        Err(_) => Err(backend_unavailable("load_task_completion_state")),
    }
}

fn load_next_claimable_task(
    transaction: &rusqlite::Transaction<'_>,
    now_ms: u64,
) -> Result<Option<OrchestratorTask>, OrchestratorError> {
    match transaction.query_row(
        "SELECT task_id, target_scope, requires_write, doctor_bypass, enqueued_at_ms
         FROM orchestrator_tasks
         WHERE is_completed = 0
           AND NOT EXISTS (
                SELECT 1
                FROM orchestrator_leases active
                WHERE active.task_id = orchestrator_tasks.task_id
                  AND active.released_at_ms IS NULL
                  AND active.expires_at_ms >= ?1
           )
         ORDER BY enqueued_at_ms ASC, task_id ASC
         LIMIT 1",
        [to_sql_i64(now_ms, "claim_task_now_ms")?],
        |row| {
            Ok((
                row.get::<_, String>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, i64>(2)?,
                row.get::<_, i64>(3)?,
                row.get::<_, i64>(4)?,
            ))
        },
    ) {
        Ok((task_id, target_scope, requires_write, doctor_bypass, enqueued_at_ms)) => Ok(Some(
            OrchestratorTask::new(
                task_id,
                ScheduleIntent {
                    target_scope,
                    requires_write: decode_bool(requires_write, "task_requires_write")?,
                    doctor_bypass: decode_bool(doctor_bypass, "task_doctor_bypass")?,
                },
                from_sql_i64(enqueued_at_ms, "task_enqueued_at_ms")?,
            ),
        )),
        Err(RusqliteError::QueryReturnedNoRows) => Ok(None),
        Err(_) => Err(backend_unavailable("claim_next_task")),
    }
}

fn load_max_fencing_token(
    transaction: &rusqlite::Transaction<'_>,
    task_id: &str,
) -> Result<u64, OrchestratorError> {
    let value: i64 = transaction
        .query_row(
            "SELECT COALESCE(MAX(fencing_token), 0) FROM orchestrator_leases WHERE task_id = ?1",
            [task_id],
            |row| row.get(0),
        )
        .map_err(|_| backend_unavailable("load_max_orchestrator_fencing_token"))?;
    from_sql_i64(value, "orchestrator_fencing_token")
}

fn load_active_lease(
    transaction: &rusqlite::Transaction<'_>,
    task_id: &str,
) -> Result<Option<OrchestratorLease>, OrchestratorError> {
    match transaction.query_row(
        "SELECT lease_id, task_id, owner_id, fencing_token, ttl_ms, expires_at_ms
         FROM orchestrator_leases
         WHERE task_id = ?1 AND released_at_ms IS NULL
         ORDER BY fencing_token DESC
         LIMIT 1",
        [task_id],
        |row| {
            Ok((
                row.get::<_, String>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, String>(2)?,
                row.get::<_, i64>(3)?,
                row.get::<_, i64>(4)?,
                row.get::<_, i64>(5)?,
            ))
        },
    ) {
        Ok((lease_id, task_id, owner_id, fencing_token, ttl_ms, expires_at_ms)) => {
            Ok(Some(OrchestratorLease {
                lease_id,
                task_id,
                owner_id,
                fencing_token: from_sql_i64(fencing_token, "active_lease_fencing_token")?,
                ttl_ms: from_sql_i64(ttl_ms, "active_lease_ttl_ms")?,
                expires_at_ms: from_sql_i64(expires_at_ms, "active_lease_expires_at_ms")?,
            }))
        }
        Err(RusqliteError::QueryReturnedNoRows) => Ok(None),
        Err(_) => Err(backend_unavailable("load_active_orchestrator_lease")),
    }
}

fn reap_expired_leases_in_transaction(
    transaction: &rusqlite::Transaction<'_>,
    now_ms: u64,
) -> Result<Vec<OrchestratorLease>, OrchestratorError> {
    let cutoff = to_sql_i64(now_ms, "reap_expired_leases_now_ms")?;
    let mut statement = transaction
        .prepare(
            "SELECT lease_id, task_id, owner_id, fencing_token, ttl_ms, expires_at_ms
             FROM orchestrator_leases
             WHERE released_at_ms IS NULL AND expires_at_ms < ?1
             ORDER BY expires_at_ms ASC, task_id ASC",
        )
        .map_err(|_| backend_unavailable("prepare_reap_expired_orchestrator_leases"))?;

    let expired = statement
        .query_map([cutoff], |row| {
            Ok((
                row.get::<_, String>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, String>(2)?,
                row.get::<_, i64>(3)?,
                row.get::<_, i64>(4)?,
                row.get::<_, i64>(5)?,
            ))
        })
        .map_err(|_| backend_unavailable("query_reap_expired_orchestrator_leases"))?
        .map(|row| {
            let (lease_id, task_id, owner_id, fencing_token, ttl_ms, expires_at_ms) =
                row.map_err(|_| backend_unavailable("decode_reap_expired_orchestrator_lease"))?;
            Ok(OrchestratorLease {
                lease_id,
                task_id,
                owner_id,
                fencing_token: from_sql_i64(fencing_token, "expired_lease_fencing_token")?,
                ttl_ms: from_sql_i64(ttl_ms, "expired_lease_ttl_ms")?,
                expires_at_ms: from_sql_i64(expires_at_ms, "expired_lease_expires_at_ms")?,
            })
        })
        .collect::<Result<Vec<_>, OrchestratorError>>()?;

    if !expired.is_empty() {
        transaction
            .execute(
                "UPDATE orchestrator_leases
                 SET released_at_ms = ?1
                 WHERE released_at_ms IS NULL AND expires_at_ms < ?1",
                [cutoff],
            )
            .map_err(|_| backend_unavailable("update_reap_expired_orchestrator_leases"))?;
    }

    Ok(expired)
}

fn list_queued_tasks(connection: &Connection) -> Result<Vec<OrchestratorTask>, OrchestratorError> {
    let mut statement = connection
        .prepare(
            "SELECT task_id, target_scope, requires_write, doctor_bypass, enqueued_at_ms
             FROM orchestrator_tasks
             WHERE is_completed = 0
               AND NOT EXISTS (
                    SELECT 1
                    FROM orchestrator_leases active
                    WHERE active.task_id = orchestrator_tasks.task_id
                      AND active.released_at_ms IS NULL
               )
             ORDER BY enqueued_at_ms ASC, task_id ASC",
        )
        .map_err(|_| backend_unavailable("prepare_orchestrator_queue_snapshot"))?;

    let rows = statement
        .query_map([], |row| {
            Ok((
                row.get::<_, String>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, i64>(2)?,
                row.get::<_, i64>(3)?,
                row.get::<_, i64>(4)?,
            ))
        })
        .map_err(|_| backend_unavailable("query_orchestrator_queue_snapshot"))?;

    rows.map(|row| {
        let (task_id, target_scope, requires_write, doctor_bypass, enqueued_at_ms) =
            row.map_err(|_| backend_unavailable("decode_orchestrator_queue_snapshot"))?;
        Ok(OrchestratorTask::new(
            task_id,
            ScheduleIntent {
                target_scope,
                requires_write: decode_bool(requires_write, "snapshot_requires_write")?,
                doctor_bypass: decode_bool(doctor_bypass, "snapshot_doctor_bypass")?,
            },
            from_sql_i64(enqueued_at_ms, "snapshot_enqueued_at_ms")?,
        ))
    })
    .collect()
}

fn list_active_leases(connection: &Connection) -> Result<Vec<OrchestratorLease>, OrchestratorError> {
    let mut statement = connection
        .prepare(
            "SELECT lease_id, task_id, owner_id, fencing_token, ttl_ms, expires_at_ms
             FROM orchestrator_leases
             WHERE released_at_ms IS NULL
             ORDER BY task_id ASC, fencing_token ASC",
        )
        .map_err(|_| backend_unavailable("prepare_active_orchestrator_leases_snapshot"))?;

    let rows = statement
        .query_map([], |row| {
            Ok((
                row.get::<_, String>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, String>(2)?,
                row.get::<_, i64>(3)?,
                row.get::<_, i64>(4)?,
                row.get::<_, i64>(5)?,
            ))
        })
        .map_err(|_| backend_unavailable("query_active_orchestrator_leases_snapshot"))?;

    rows.map(|row| {
        let (lease_id, task_id, owner_id, fencing_token, ttl_ms, expires_at_ms) =
            row.map_err(|_| backend_unavailable("decode_active_orchestrator_lease_snapshot"))?;
        Ok(OrchestratorLease {
            lease_id,
            task_id,
            owner_id,
            fencing_token: from_sql_i64(fencing_token, "snapshot_active_lease_fencing_token")?,
            ttl_ms: from_sql_i64(ttl_ms, "snapshot_active_lease_ttl_ms")?,
            expires_at_ms: from_sql_i64(expires_at_ms, "snapshot_active_lease_expires_at_ms")?,
        })
    })
    .collect()
}

fn list_completed_task_ids(connection: &Connection) -> Result<Vec<String>, OrchestratorError> {
    let mut statement = connection
        .prepare(
            "SELECT task_id
             FROM orchestrator_tasks
             WHERE is_completed = 1
             ORDER BY task_id ASC",
        )
        .map_err(|_| backend_unavailable("prepare_completed_orchestrator_tasks_snapshot"))?;

    let rows = statement
        .query_map([], |row| row.get::<_, String>(0))
        .map_err(|_| backend_unavailable("query_completed_orchestrator_tasks_snapshot"))?;

    rows.map(|row| row.map_err(|_| backend_unavailable("decode_completed_orchestrator_task_snapshot")))
        .collect()
}

fn encode_bool(value: bool) -> i64 {
    if value { 1 } else { 0 }
}

fn decode_bool(value: i64, operation: &'static str) -> Result<bool, OrchestratorError> {
    match value {
        0 => Ok(false),
        1 => Ok(true),
        _ => Err(backend_unavailable(operation)),
    }
}

fn to_sql_i64(value: u64, operation: &'static str) -> Result<i64, OrchestratorError> {
    i64::try_from(value).map_err(|_| backend_unavailable(operation))
}

fn from_sql_i64(value: i64, operation: &'static str) -> Result<u64, OrchestratorError> {
    u64::try_from(value).map_err(|_| backend_unavailable(operation))
}

fn backend_unavailable(operation: &'static str) -> OrchestratorError {
    OrchestratorError::BackendUnavailable { operation }
}

#[cfg(test)]
mod tests {
    use super::SqliteTaskOrchestrator;
    use crate::{open_database, SqliteOpenOptions};
    use safeclaw_core::{
        OrchestratorError, OrchestratorTask, ScheduleIntent, TaskOrchestrator,
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
                "safeclaw-sqlite-orchestrator-{label}-{}-{unique}.db",
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
    fn claim_next_renews_and_snapshots_queue_state() {
        let temp_db = TempDatabase::new("claim-renew");
        let connection = open_database(temp_db.path(), SqliteOpenOptions::default())
            .expect("sqlite adapter must open orchestrator database");
        let mut orchestrator = SqliteTaskOrchestrator::new(connection).with_lease_ttl_ms(25);

        orchestrator
            .enqueue(OrchestratorTask::new(
                "task-a",
                ScheduleIntent::write("scope:/tmp/task-a"),
                0,
            ))
            .unwrap();
        orchestrator
            .enqueue(OrchestratorTask::new(
                "task-b",
                ScheduleIntent::read("scope:/tmp/task-b"),
                1,
            ))
            .unwrap();

        let claim = orchestrator.claim_next("orch-a", 10).unwrap().unwrap();
        assert_eq!(claim.task.task_id, "task-a");
        assert_eq!(claim.lease.fencing_token, 1);

        let renewed = orchestrator
            .renew_lease(&claim.task.task_id, &claim.lease.lease_id, "orch-a", 20)
            .unwrap();
        assert_eq!(renewed.expires_at_ms, 45);

        let snapshot = orchestrator.queue_snapshot();
        assert_eq!(snapshot.queued_tasks.len(), 1);
        assert_eq!(snapshot.queued_tasks[0].task_id, "task-b");
        assert_eq!(snapshot.active_leases.len(), 1);
        assert_eq!(snapshot.active_leases[0].task_id, "task-a");
    }

    #[test]
    fn expired_leases_can_be_reaped_and_reclaimed() {
        let temp_db = TempDatabase::new("reap");
        let connection = open_database(temp_db.path(), SqliteOpenOptions::default())
            .expect("sqlite adapter must open orchestrator database");
        let mut orchestrator = SqliteTaskOrchestrator::new(connection).with_lease_ttl_ms(10);

        orchestrator
            .enqueue(OrchestratorTask::new(
                "task-reap",
                ScheduleIntent::write("scope:/tmp/task-reap"),
                0,
            ))
            .unwrap();

        let claim = orchestrator.claim_next("orch-a", 0).unwrap().unwrap();
        let expired = orchestrator.reap_expired_leases(11).unwrap();
        assert_eq!(expired, vec![claim.lease.clone()]);

        let reclaimed = orchestrator.claim_next("orch-b", 12).unwrap().unwrap();
        assert_eq!(reclaimed.task.task_id, "task-reap");
        assert_eq!(reclaimed.lease.fencing_token, 2);
        assert_eq!(reclaimed.lease.owner_id, "orch-b");
    }

    #[test]
    fn complete_marks_task_done_and_duplicate_enqueue_is_blocked() {
        let temp_db = TempDatabase::new("complete");
        let connection = open_database(temp_db.path(), SqliteOpenOptions::default())
            .expect("sqlite adapter must open orchestrator database");
        let mut orchestrator = SqliteTaskOrchestrator::new(connection);

        orchestrator
            .enqueue(OrchestratorTask::new(
                "task-done",
                ScheduleIntent::write("scope:/tmp/task-done"),
                0,
            ))
            .unwrap();
        let claim = orchestrator.claim_next("orch-a", 0).unwrap().unwrap();

        assert_eq!(
            orchestrator.complete(&claim.task.task_id, &claim.lease.lease_id, "orch-b"),
            Err(OrchestratorError::LeaseNotOwned {
                task_id: String::from("task-done"),
                lease_id: claim.lease.lease_id.clone(),
                owner_id: String::from("orch-b"),
            })
        );

        orchestrator
            .complete(&claim.task.task_id, &claim.lease.lease_id, "orch-a")
            .unwrap();
        assert!(orchestrator.claim_next("orch-c", 1).unwrap().is_none());
        assert_eq!(
            orchestrator
                .enqueue(OrchestratorTask::new(
                    "task-done",
                    ScheduleIntent::write("scope:/tmp/task-done"),
                    2,
                )),
            Err(OrchestratorError::TaskAlreadyCompleted {
                task_id: String::from("task-done"),
            })
        );
        assert_eq!(
            orchestrator.queue_snapshot().completed_task_ids,
            vec![String::from("task-done")]
        );
    }
}

