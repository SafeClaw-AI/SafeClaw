#[cfg(test)]
mod tests {
    use crate::{
        open_database, FileSystemProbeAdapter, LocalSandboxExecutor, RuntimeExecutionDirective,
        SandboxCommand, SqliteEffectStore, SqliteOpenOptions, SqliteRuntimeStore,
        SqliteStateEngine, SqliteTaskOrchestrator,
    };
    use safeclaw_core::{
        effect_ledger::{
            EffectAction, EffectActor, EffectRecord, EffectReversibility, EffectStatus, EffectTier,
            ProbeMode,
        },
        scheduler::{OrchestratorTask, ScheduleIntent, TaskOrchestrator},
        worker_lifecycle::WorkerState,
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

    struct TempWorkspace {
        root: PathBuf,
        output_path: PathBuf,
        db_path: PathBuf,
    }

    impl TempWorkspace {
        fn new(label: &str) -> Self {
            let unique = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .expect("system clock must be after epoch")
                .as_nanos();
            let root = env::temp_dir().join(format!(
                "safeclaw-sqlite-demo-{label}-{}-{unique}",
                process::id()
            ));
            fs::create_dir_all(&root).expect("workspace root must be creatable");
            Self {
                output_path: root.join("demo-output.txt"),
                db_path: root.join("demo.db"),
                root,
            }
        }

        fn output_path(&self) -> &Path {
            &self.output_path
        }

        fn db_path(&self) -> &Path {
            &self.db_path
        }
    }

    impl Drop for TempWorkspace {
        fn drop(&mut self) {
            let _ = fs::remove_file(&self.output_path);
            for suffix in ["", "-wal", "-shm"] {
                let candidate = if suffix.is_empty() {
                    self.db_path.clone()
                } else {
                    PathBuf::from(format!("{}{}", self.db_path.display(), suffix))
                };
                let _ = fs::remove_file(candidate);
            }
            let _ = fs::remove_dir(&self.root);
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
        assert_eq!(summary.worker_state, WorkerState::Failed);

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

        assert_eq!(reconciled.worker_state, WorkerState::Succeeded);
        assert_eq!(reconciled.effect_status, EffectStatus::Executed);
        assert!(restored.current_recovery_lease().is_some());
    }

    #[test]
    fn sqlite_runtime_store_recovers_full_lifecycle_after_real_external_write() {
        let temp = TempWorkspace::new("full-lifecycle");
        let output_bytes = b"safeclaw integration recovery demo\n";
        let effect = EffectRecord::new(
            "effect-full-lifecycle",
            "task-full-lifecycle",
            "trace-full-lifecycle",
            "intent-full-lifecycle",
            EffectActor::Worker,
            EffectAction::FileWrite,
            format!("scope:{}", temp.output_path().display()),
            EffectTier::Tier1,
            EffectReversibility::Rollbackable,
            ProbeMode::Auto,
        );
        let mut runtime = InMemoryTaskRuntime::new(effect);

        runtime
            .begin_execution(PreflightDecision::Permit)
            .expect("runtime must enter executing before external side effects");
        assert_eq!(runtime.worker_state, WorkerState::Executing);
        assert_eq!(runtime.effect.status, EffectStatus::Prepared);

        let executor = LocalSandboxExecutor::new();
        let report = executor
            .run(&sandbox_write_command(temp.output_path(), output_bytes))
            .expect("sandbox write must complete");
        assert_eq!(report.runtime_directive(), RuntimeExecutionDirective::Commit);
        assert_eq!(fs::read(temp.output_path()).unwrap(), output_bytes);

        runtime
            .continue_execution(ExecutionDisposition::Crash)
            .expect("worker crash after external write must be representable");
        assert_eq!(runtime.worker_state, WorkerState::Uncertain);
        assert_eq!(runtime.effect.status, EffectStatus::Uncertain);

        let mut store = SqliteRuntimeStore::new(
            open_database(temp.db_path(), SqliteOpenOptions::default())
                .expect("sqlite adapter must open runtime database"),
        );
        store
            .persist_runtime(&runtime, "runtime-full-lifecycle-1", "integration-test")
            .expect("uncertain runtime must persist");
        drop(store);

        let store = SqliteRuntimeStore::new(
            open_database(temp.db_path(), SqliteOpenOptions::default())
                .expect("sqlite adapter must reopen runtime database"),
        );
        let mut restored = store
            .load_runtime("task-full-lifecycle", "effect-full-lifecycle")
            .expect("runtime load must succeed")
            .expect("persisted runtime must reload");
        assert_eq!(restored.worker_state, WorkerState::Uncertain);
        assert_eq!(restored.effect.status, EffectStatus::Uncertain);

        let mut probe = FileSystemProbeAdapter::new();
        probe.register_expected_blake3(
            restored.effect.effect_id.clone(),
            blake3::hash(output_bytes).to_hex().to_string(),
        );
        let summary = restored
            .run_probe_with(&probe)
            .expect("restored runtime must probe and settle");
        assert_eq!(summary.worker_state, WorkerState::Succeeded);
        assert_eq!(summary.effect_status, EffectStatus::Executed);

        let mut final_store = SqliteRuntimeStore::new(
            open_database(temp.db_path(), SqliteOpenOptions::default())
                .expect("sqlite adapter must reopen for final persist"),
        );
        final_store
            .persist_runtime(&restored, "runtime-full-lifecycle-2", "integration-test")
            .expect("final runtime snapshot must persist");
        let final_runtime = final_store
            .load_runtime("task-full-lifecycle", "effect-full-lifecycle")
            .expect("final runtime load must succeed")
            .expect("final runtime must exist");
        assert_eq!(final_runtime.worker_state, WorkerState::Succeeded);
        assert_eq!(final_runtime.effect.status, EffectStatus::Executed);
        assert_eq!(final_runtime.attempts.len(), 1);
    }

    #[test]
    fn sqlite_orchestrator_claims_then_completes_recovered_runtime() {
        let temp = TempWorkspace::new("orchestrated-runtime");
        let output_bytes = b"safeclaw orchestrator runtime demo\n";
        let mut orchestrator = SqliteTaskOrchestrator::new(
            open_database(temp.db_path(), SqliteOpenOptions::default())
                .expect("sqlite adapter must open orchestrator database"),
        );
        orchestrator
            .enqueue(OrchestratorTask::new(
                "task-orchestrated-runtime",
                ScheduleIntent::write(format!("scope:{}", temp.output_path().display())),
                0,
            ))
            .expect("task must enqueue");

        let claim = orchestrator
            .claim_next("orch-main", 1)
            .expect("claim must succeed")
            .expect("task must be claimable");
        assert_eq!(claim.task.task_id, "task-orchestrated-runtime");

        let effect = EffectRecord::new(
            "effect-orchestrated-runtime",
            claim.task.task_id.clone(),
            "trace-orchestrated-runtime",
            "intent-orchestrated-runtime",
            EffectActor::Worker,
            EffectAction::FileWrite,
            claim.task.intent.target_scope.clone(),
            EffectTier::Tier1,
            EffectReversibility::Rollbackable,
            ProbeMode::Auto,
        );
        let mut runtime = InMemoryTaskRuntime::new(effect);
        runtime
            .begin_execution(PreflightDecision::Permit)
            .expect("claimed task must enter execution");

        let executor = LocalSandboxExecutor::new();
        let report = executor
            .run(&sandbox_write_command(temp.output_path(), output_bytes))
            .expect("sandbox write must complete");
        assert_eq!(report.runtime_directive(), RuntimeExecutionDirective::Commit);
        runtime
            .continue_execution(ExecutionDisposition::Crash)
            .expect("post-write crash must enter uncertain state");

        let mut store = SqliteRuntimeStore::new(
            open_database(temp.db_path(), SqliteOpenOptions::default())
                .expect("sqlite adapter must open runtime database"),
        );
        store
            .persist_runtime(&runtime, "runtime-orchestrated-1", "integration-test")
            .expect("orchestrated runtime must persist");
        drop(store);

        let store = SqliteRuntimeStore::new(
            open_database(temp.db_path(), SqliteOpenOptions::default())
                .expect("sqlite adapter must reopen runtime database"),
        );
        let mut restored = store
            .load_runtime("task-orchestrated-runtime", "effect-orchestrated-runtime")
            .expect("runtime load must succeed")
            .expect("persisted runtime must reload");
        let mut probe = FileSystemProbeAdapter::new();
        probe.register_expected_blake3(
            restored.effect.effect_id.clone(),
            blake3::hash(output_bytes).to_hex().to_string(),
        );
        let settled = restored
            .run_probe_with(&probe)
            .expect("restored runtime must settle via probe");
        assert_eq!(settled.worker_state, WorkerState::Succeeded);

        orchestrator
            .complete(&claim.task.task_id, &claim.lease.lease_id, &claim.lease.owner_id)
            .expect("successful runtime must complete orchestrator lease");
        let snapshot = orchestrator.queue_snapshot();
        assert!(snapshot.queued_tasks.is_empty());
        assert!(snapshot.active_leases.is_empty());
        assert_eq!(snapshot.completed_task_ids, vec![String::from("task-orchestrated-runtime")]);
        assert!(orchestrator.claim_next("orch-other", 2).unwrap().is_none());
    }

    fn sandbox_write_command(output_path: &Path, output_bytes: &[u8]) -> SandboxCommand {
        if cfg!(windows) {
            let bytes_literal = output_bytes
                .iter()
                .map(u8::to_string)
                .collect::<Vec<_>>()
                .join(", ");
            SandboxCommand::new(
                "powershell",
                [
                    "-Command",
                    &format!(
                        "$bytes = [byte[]]({bytes_literal}); [System.IO.File]::WriteAllBytes('{}', $bytes)",
                        output_path.display()
                    ),
                ],
                5_000,
            )
        } else {
            let text = String::from_utf8(output_bytes.to_vec())
                .expect("integration demo bytes must remain utf-8");
            SandboxCommand::new(
                "sh",
                [
                    "-c",
                    &format!("printf '%s' '{}' > '{}'", text, output_path.display()),
                ],
                5_000,
            )
        }
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
