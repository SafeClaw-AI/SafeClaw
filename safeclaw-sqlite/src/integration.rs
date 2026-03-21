#[cfg(test)]
mod tests {
    use crate::{open_database, SqliteEffectStore, SqliteOpenOptions, SqliteStateEngine};
    use safeclaw_core::{
        effect_ledger::{
            EffectAction, EffectActor, EffectRecord, EffectReversibility, EffectTier, ProbeMode,
        },
        ExecutionDisposition, InMemoryTaskRuntime, PreflightDecision, ReconcileDecision,
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
                "safeclaw-sqlite-integration-{label}-{}-{unique}.db",
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
    fn sqlite_persistence_restores_uncertain_runtime_after_restart() {
        let temp_db = TempDatabase::new("restore-uncertain");
        let mut state_engine = SqliteStateEngine::new(
            open_database(temp_db.path(), SqliteOpenOptions::default())
                .expect("sqlite adapter must open state database"),
        );
        let mut effect_store = SqliteEffectStore::new(
            open_database(temp_db.path(), SqliteOpenOptions::default())
                .expect("sqlite adapter must open effect database"),
        );

        let mut runtime = InMemoryTaskRuntime::new(demo_effect(ProbeMode::Auto));
        let summary = runtime
            .run_minimal_flow(PreflightDecision::Permit, ExecutionDisposition::Crash)
            .expect("probeable crash flow must succeed");
        assert_eq!(
            summary.worker_state,
            safeclaw_core::worker_lifecycle::WorkerState::Uncertain
        );

        effect_store.save_effect(&runtime.effect).unwrap();
        if let Some(lease) = runtime.current_recovery_lease().cloned() {
            effect_store
                .save_lease(&runtime.effect.task_id, &lease)
                .unwrap();
        }
        runtime
            .persist_state(&mut state_engine, "state-uncertain-1", "sqlite-adapter")
            .expect("state snapshot must persist");

        drop(effect_store);
        drop(state_engine);

        let state_engine = SqliteStateEngine::new(
            open_database(temp_db.path(), SqliteOpenOptions::default())
                .expect("sqlite adapter must reopen state database"),
        );
        let effect_store = SqliteEffectStore::new(
            open_database(temp_db.path(), SqliteOpenOptions::default())
                .expect("sqlite adapter must reopen effect database"),
        );
        let effect = effect_store
            .load_effect("effect-auto")
            .expect("effect load must succeed")
            .expect("effect must exist");
        let lease = effect_store
            .load_latest_lease("task-auto")
            .expect("lease load must succeed");

        let restored =
            InMemoryTaskRuntime::restore_from_engine(effect, &state_engine, "task-auto", lease)
                .expect("runtime restore must succeed")
                .expect("snapshot must exist");

        assert_eq!(
            restored.worker_state,
            safeclaw_core::worker_lifecycle::WorkerState::Uncertain
        );
        assert_eq!(
            restored.effect.status,
            safeclaw_core::effect_ledger::EffectStatus::Uncertain
        );
        assert_eq!(
            restored.effect.probe_state,
            Some(safeclaw_core::effect_ledger::ProbeState::ProbePending)
        );
    }

    #[test]
    fn sqlite_persistence_restores_executed_assumed_runtime_and_reconciles() {
        let temp_db = TempDatabase::new("restore-assumed");
        let mut state_engine = SqliteStateEngine::new(
            open_database(temp_db.path(), SqliteOpenOptions::default())
                .expect("sqlite adapter must open state database"),
        );
        let mut effect_store = SqliteEffectStore::new(
            open_database(temp_db.path(), SqliteOpenOptions::default())
                .expect("sqlite adapter must open effect database"),
        );

        let mut runtime = InMemoryTaskRuntime::new(demo_effect(ProbeMode::None));
        let summary = runtime
            .run_minimal_flow(PreflightDecision::Permit, ExecutionDisposition::Crash)
            .expect("assumed crash flow must succeed");
        assert_eq!(
            summary.worker_state,
            safeclaw_core::worker_lifecycle::WorkerState::Failed
        );

        effect_store.save_effect(&runtime.effect).unwrap();
        if let Some(lease) = runtime.current_recovery_lease().cloned() {
            effect_store
                .save_lease(&runtime.effect.task_id, &lease)
                .unwrap();
        }
        runtime
            .persist_state(&mut state_engine, "state-assumed-1", "sqlite-adapter")
            .expect("state snapshot must persist");

        drop(effect_store);
        drop(state_engine);

        let state_engine = SqliteStateEngine::new(
            open_database(temp_db.path(), SqliteOpenOptions::default())
                .expect("sqlite adapter must reopen state database"),
        );
        let effect_store = SqliteEffectStore::new(
            open_database(temp_db.path(), SqliteOpenOptions::default())
                .expect("sqlite adapter must reopen effect database"),
        );
        let effect = effect_store
            .load_effect("effect-none")
            .expect("effect load must succeed")
            .expect("effect must exist");
        let lease = effect_store
            .load_latest_lease("task-none")
            .expect("lease load must succeed");

        let mut restored =
            InMemoryTaskRuntime::restore_from_engine(effect, &state_engine, "task-none", lease)
                .expect("runtime restore must succeed")
                .expect("snapshot must exist");
        let reconciled = restored
            .reconcile_assumed(ReconcileDecision::Success)
            .expect("restored runtime must reconcile cleanly");

        assert_eq!(
            reconciled.worker_state,
            safeclaw_core::worker_lifecycle::WorkerState::Succeeded
        );
        assert_eq!(
            reconciled.effect_status,
            safeclaw_core::effect_ledger::EffectStatus::Executed
        );
        assert!(restored.current_recovery_lease().is_some());
    }

    fn demo_effect(probe_mode: ProbeMode) -> EffectRecord {
        let (effect_id, task_id) = match probe_mode {
            ProbeMode::Auto => ("effect-auto", "task-auto"),
            ProbeMode::None => ("effect-none", "task-none"),
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
