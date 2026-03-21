use crate::{
    FileSystemProbeAdapter, LocalSandboxExecutor, NetworkProbeAdapter, SandboxCommand,
    SandboxExecutionReport, SandboxRuntimeError, SqliteAdapterError, SqliteRuntimeStore,
    SqliteTaskOrchestrator,
};
use safeclaw_core::{
    effect_ledger::EffectAction,
    recovery::probes::ProbeAdapterError,
    scheduler::{
        OrchestratorClaim, OrchestratorError, OrchestratorSnapshot, TaskOrchestrator,
    },
    worker_lifecycle::WorkerState,
    InMemoryTaskRuntime, PreflightDecision, RunSummary, RuntimeError,
};

#[derive(Debug)]
pub enum WorkerLoopError {
    Orchestrator(OrchestratorError),
    Runtime(RuntimeError),
    Sandbox(SandboxRuntimeError),
    Store(SqliteAdapterError),
    PersistedRuntimeMissing { task_id: String, effect_id: String },
}

#[derive(Clone, Debug)]
pub struct WorkerLoopOutcome {
    pub claim: OrchestratorClaim,
    pub report: SandboxExecutionReport,
    pub execution_summary: RunSummary,
    pub final_summary: RunSummary,
    pub completed: bool,
}

pub struct SqliteSingleWorkerLoop {
    orchestrator: SqliteTaskOrchestrator,
    runtime_store: SqliteRuntimeStore,
    sandbox: LocalSandboxExecutor,
    filesystem_probe: FileSystemProbeAdapter,
    network_probe: NetworkProbeAdapter,
}

impl SqliteSingleWorkerLoop {
    pub fn new(orchestrator: SqliteTaskOrchestrator, runtime_store: SqliteRuntimeStore) -> Self {
        Self {
            orchestrator,
            runtime_store,
            sandbox: LocalSandboxExecutor::new(),
            filesystem_probe: FileSystemProbeAdapter::new(),
            network_probe: NetworkProbeAdapter::new(),
        }
    }

    pub fn filesystem_probe_mut(&mut self) -> &mut FileSystemProbeAdapter {
        &mut self.filesystem_probe
    }

    pub fn network_probe_mut(&mut self) -> &mut NetworkProbeAdapter {
        &mut self.network_probe
    }

    pub fn queue_snapshot(&self) -> OrchestratorSnapshot {
        self.orchestrator.queue_snapshot()
    }

    pub fn renew_claim_lease(
        &mut self,
        claim: &OrchestratorClaim,
        now_ms: u64,
    ) -> Result<OrchestratorClaim, WorkerLoopError> {
        let lease = self
            .orchestrator
            .renew_lease(
                &claim.task.task_id,
                &claim.lease.lease_id,
                &claim.lease.owner_id,
                now_ms,
            )
            .map_err(WorkerLoopError::Orchestrator)?;
        Ok(OrchestratorClaim {
            task: claim.task.clone(),
            lease,
        })
    }

    pub fn claim_and_drive_once<F>(
        &mut self,
        owner_id: &str,
        now_ms: u64,
        preflight: PreflightDecision,
        build: F,
    ) -> Result<Option<WorkerLoopOutcome>, WorkerLoopError>
    where
        F: FnOnce(&OrchestratorClaim) -> Result<(InMemoryTaskRuntime, SandboxCommand), WorkerLoopError>,
    {
        let Some(claim) = self.claim_once(owner_id, now_ms)? else {
            return Ok(None);
        };

        let (mut runtime, command) = build(&claim)?;
        runtime
            .begin_execution(preflight)
            .map_err(WorkerLoopError::Runtime)?;
        self.persist_runtime(&runtime, &claim, "pre-exec")?;

        self.drive_claimed_runtime(claim, runtime, command).map(Some)
    }

    pub fn claim_and_resume_once<F>(
        &mut self,
        owner_id: &str,
        now_ms: u64,
        build: F,
    ) -> Result<Option<WorkerLoopOutcome>, WorkerLoopError>
    where
        F: FnOnce(&OrchestratorClaim) -> Result<(InMemoryTaskRuntime, SandboxCommand), WorkerLoopError>,
    {
        let Some(claim) = self.claim_once(owner_id, now_ms)? else {
            return Ok(None);
        };

        let (runtime, command) = build(&claim)?;
        self.drive_claimed_runtime(claim, runtime, command).map(Some)
    }

    pub fn claim_and_retry_failed_once<F>(
        &mut self,
        owner_id: &str,
        now_ms: u64,
        effect_id: &str,
        preflight: PreflightDecision,
        build_command: F,
    ) -> Result<Option<WorkerLoopOutcome>, WorkerLoopError>
    where
        F: FnOnce(&OrchestratorClaim, &InMemoryTaskRuntime) -> Result<SandboxCommand, WorkerLoopError>,
    {
        let Some(claim) = self.claim_once(owner_id, now_ms)? else {
            return Ok(None);
        };

        let mut runtime = self
            .runtime_store
            .load_runtime(&claim.task.task_id, effect_id)
            .map_err(WorkerLoopError::Store)?
            .ok_or_else(|| WorkerLoopError::PersistedRuntimeMissing {
                task_id: claim.task.task_id.clone(),
                effect_id: effect_id.to_string(),
            })?;
        runtime
            .retry_failed(preflight)
            .map_err(WorkerLoopError::Runtime)?;
        self.persist_runtime(&runtime, &claim, "pre-exec")?;
        let command = build_command(&claim, &runtime)?;
        self.drive_claimed_runtime(claim, runtime, command).map(Some)
    }

    fn claim_once(
        &mut self,
        owner_id: &str,
        now_ms: u64,
    ) -> Result<Option<OrchestratorClaim>, WorkerLoopError> {
        self.orchestrator
            .claim_next(owner_id, now_ms)
            .map_err(WorkerLoopError::Orchestrator)
    }

    fn drive_claimed_runtime(
        &mut self,
        claim: OrchestratorClaim,
        mut runtime: InMemoryTaskRuntime,
        command: SandboxCommand,
    ) -> Result<WorkerLoopOutcome, WorkerLoopError> {
        let (report, execution_summary) = self
            .sandbox
            .run_and_apply(&mut runtime, &command)
            .map_err(WorkerLoopError::Sandbox)?;
        self.persist_runtime(&runtime, &claim, "post-exec")?;

        let mut final_summary = execution_summary.clone();
        if runtime.worker_state == WorkerState::Uncertain {
            final_summary = self.recover_uncertain(&mut runtime, &claim)?;
        }

        let mut completed = false;
        if final_summary.worker_state == WorkerState::Succeeded {
            self.orchestrator
                .complete(&claim.task.task_id, &claim.lease.lease_id, &claim.lease.owner_id)
                .map_err(WorkerLoopError::Orchestrator)?;
            completed = true;
        }

        Ok(WorkerLoopOutcome {
            claim,
            report,
            execution_summary,
            final_summary,
            completed,
        })
    }

    fn recover_uncertain(
        &mut self,
        runtime: &mut InMemoryTaskRuntime,
        claim: &OrchestratorClaim,
    ) -> Result<RunSummary, WorkerLoopError> {
        let summary = match runtime.effect.action {
            EffectAction::FileWrite | EffectAction::FileDelete => runtime
                .run_probe_with(&self.filesystem_probe)
                .map_err(WorkerLoopError::Runtime)?,
            EffectAction::NetworkRequest => runtime
                .run_probe_with(&self.network_probe)
                .map_err(WorkerLoopError::Runtime)?,
            action => {
                return Err(WorkerLoopError::Runtime(RuntimeError::ProbeAdapter(
                    ProbeAdapterError::AdapterUnavailable { action },
                )))
            }
        };
        self.persist_runtime(runtime, claim, "post-probe")?;
        Ok(summary)
    }

    fn persist_runtime(
        &mut self,
        runtime: &InMemoryTaskRuntime,
        claim: &OrchestratorClaim,
        phase: &str,
    ) -> Result<(), WorkerLoopError> {
        let state_event_id = format!("worker-loop:{}:{phase}", claim.lease.lease_id);
        self.runtime_store
            .persist_runtime(runtime, state_event_id, "worker-loop")
            .map_err(WorkerLoopError::Store)?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::{SqliteSingleWorkerLoop, WorkerLoopError};
    use crate::{open_database, SandboxCommand, SqliteOpenOptions, SqliteRuntimeStore, SqliteTaskOrchestrator};
    use safeclaw_core::{
        effect_ledger::{
            EffectAction, EffectActor, EffectRecord, EffectReversibility, EffectStatus, EffectTier,
            ProbeMode,
        },
        scheduler::{OrchestratorTask, ScheduleIntent, TaskOrchestrator},
        worker_lifecycle::WorkerState,
        InMemoryTaskRuntime, PreflightDecision,
    };
    use std::{
        env, fs,
        path::{Path, PathBuf},
        process,
        time::{SystemTime, UNIX_EPOCH},
    };

    struct TempWorkspace {
        root: PathBuf,
        db_path: PathBuf,
        output_path: PathBuf,
    }

    impl TempWorkspace {
        fn new(label: &str) -> Self {
            let unique = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .expect("system clock must be after epoch")
                .as_nanos();
            let root = env::temp_dir().join(format!(
                "safeclaw-worker-loop-{label}-{}-{unique}",
                process::id()
            ));
            fs::create_dir_all(&root).expect("temp workspace must be created");
            Self {
                db_path: root.join("worker-loop.db"),
                output_path: root.join("output.txt"),
                root,
            }
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
    fn worker_loop_returns_none_when_queue_is_empty() {
        let temp = TempWorkspace::new("empty");
        let orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let runtime_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut loop_driver = SqliteSingleWorkerLoop::new(orchestrator, runtime_store);

        let outcome = loop_driver
            .claim_and_drive_once("worker-a", 0, PreflightDecision::Permit, |_| unreachable!())
            .unwrap();
        assert!(outcome.is_none());
    }

    #[test]
    fn worker_loop_persists_pre_exec_runtime_when_sandbox_spawn_fails() {
        let temp = TempWorkspace::new("pre-exec-spawn");
        let mut orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-pre-exec",
                ScheduleIntent::write(format!("scope:{}", temp.output_path.display())),
                0,
            ))
            .unwrap();
        let runtime_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut loop_driver = SqliteSingleWorkerLoop::new(orchestrator, runtime_store);

        let error = loop_driver
            .claim_and_drive_once("worker-a", 0, PreflightDecision::Permit, |claim| {
                let effect = EffectRecord::new(
                    "effect-worker-pre-exec",
                    claim.task.task_id.clone(),
                    "trace-worker-pre-exec",
                    "intent-worker-pre-exec",
                    EffectActor::Worker,
                    EffectAction::FileWrite,
                    claim.task.intent.target_scope.clone(),
                    EffectTier::Tier1,
                    EffectReversibility::Rollbackable,
                    ProbeMode::Auto,
                );
                Ok((InMemoryTaskRuntime::new(effect), sandbox_missing_program_command()))
            })
            .unwrap_err();
        assert!(matches!(error, WorkerLoopError::Sandbox(_)));
        assert_eq!(loop_driver.queue_snapshot().completed_task_ids.len(), 0);
        assert_eq!(loop_driver.queue_snapshot().active_leases.len(), 1);
        assert!(!temp.output_path.exists());

        let verify_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let restored = verify_store
            .load_runtime("task-worker-pre-exec", "effect-worker-pre-exec")
            .unwrap()
            .expect("pre-exec runtime must persist before sandbox spawn");
        assert_eq!(restored.worker_state, WorkerState::Executing);
        assert_eq!(restored.effect.status, EffectStatus::Prepared);
    }

    #[test]
    fn worker_loop_claims_probes_persists_and_completes_uncertain_file_write_task() {
        let temp = TempWorkspace::new("success");
        let mut orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-loop",
                ScheduleIntent::write(format!("scope:{}", temp.output_path.display())),
                0,
            ))
            .unwrap();
        let runtime_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut loop_driver = SqliteSingleWorkerLoop::new(orchestrator, runtime_store);
        let expected_bytes = b"safeclaw worker loop\n";
        loop_driver
            .filesystem_probe_mut()
            .register_expected_blake3(
                "effect-worker-loop",
                blake3::hash(expected_bytes).to_hex().to_string(),
            );

        let outcome = loop_driver
            .claim_and_drive_once("worker-a", 10, PreflightDecision::Permit, |claim| {
                let effect = EffectRecord::new(
                    "effect-worker-loop",
                    claim.task.task_id.clone(),
                    "trace-worker-loop",
                    "intent-worker-loop",
                    EffectActor::Worker,
                    EffectAction::FileWrite,
                    claim.task.intent.target_scope.clone(),
                    EffectTier::Tier1,
                    EffectReversibility::Rollbackable,
                    ProbeMode::Auto,
                );
                Ok((
                    InMemoryTaskRuntime::new(effect),
                    sandbox_write_then_timeout_command(&temp.output_path, expected_bytes),
                ))
            })
            .unwrap()
            .expect("worker loop must claim queued task");

        assert_eq!(outcome.claim.task.task_id, "task-worker-loop");
        assert!(outcome.report.timed_out);
        assert_eq!(outcome.execution_summary.worker_state, WorkerState::Uncertain);
        assert_eq!(outcome.execution_summary.effect_status, EffectStatus::Uncertain);
        assert_eq!(outcome.final_summary.worker_state, WorkerState::Succeeded);
        assert_eq!(outcome.final_summary.effect_status, EffectStatus::Executed);
        assert!(outcome.completed);
        assert_eq!(fs::read(&temp.output_path).unwrap(), expected_bytes);
        assert!(loop_driver.queue_snapshot().queued_tasks.is_empty());
        assert!(loop_driver.queue_snapshot().active_leases.is_empty());
        assert_eq!(
            loop_driver.queue_snapshot().completed_task_ids,
            vec![String::from("task-worker-loop")]
        );

        let verify_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let restored = verify_store
            .load_runtime("task-worker-loop", "effect-worker-loop")
            .unwrap()
            .expect("persisted runtime must reload");
        assert_eq!(restored.worker_state, WorkerState::Succeeded);
        assert_eq!(restored.effect.status, EffectStatus::Executed);
    }

    #[test]
    fn worker_loop_can_renew_failed_task_lease_and_block_reclaim() {
        let temp = TempWorkspace::new("renew-lease");
        let mut orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-renew",
                ScheduleIntent::write(format!("scope:{}", temp.output_path.display())),
                0,
            ))
            .unwrap();
        let runtime_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut loop_driver = SqliteSingleWorkerLoop::new(orchestrator, runtime_store);

        let failed = loop_driver
            .claim_and_drive_once("worker-a", 0, PreflightDecision::Permit, |claim| {
                let effect = EffectRecord::new(
                    "effect-worker-renew",
                    claim.task.task_id.clone(),
                    "trace-worker-renew",
                    "intent-worker-renew",
                    EffectActor::Worker,
                    EffectAction::FileWrite,
                    claim.task.intent.target_scope.clone(),
                    EffectTier::Tier1,
                    EffectReversibility::Rollbackable,
                    ProbeMode::Auto,
                );
                Ok((InMemoryTaskRuntime::new(effect), sandbox_fail_command()))
            })
            .unwrap()
            .expect("first worker must claim queued task");
        assert_eq!(failed.final_summary.worker_state, WorkerState::Failed);
        assert!(!failed.completed);

        let renewed = loop_driver.renew_claim_lease(&failed.claim, 20).unwrap();
        assert_eq!(renewed.lease.owner_id, "worker-a");
        assert_eq!(renewed.lease.fencing_token, 1);
        assert_eq!(renewed.lease.expires_at_ms, 45);
        assert_eq!(loop_driver.queue_snapshot().active_leases.len(), 1);
        assert_eq!(loop_driver.queue_snapshot().active_leases[0].expires_at_ms, 45);

        let other_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        let other_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut other_worker = SqliteSingleWorkerLoop::new(other_orchestrator, other_store);
        let blocked = other_worker
            .claim_and_resume_once("worker-b", 26, |_| unreachable!())
            .unwrap();
        assert!(blocked.is_none());
    }

    #[test]
    fn worker_loop_retry_reports_missing_persisted_runtime() {
        let temp = TempWorkspace::new("missing-runtime");
        let mut orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-missing",
                ScheduleIntent::write(format!("scope:{}", temp.output_path.display())),
                0,
            ))
            .unwrap();
        let runtime_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut loop_driver = SqliteSingleWorkerLoop::new(orchestrator, runtime_store);

        let error = loop_driver
            .claim_and_retry_failed_once(
                "worker-a",
                0,
                "effect-worker-missing",
                PreflightDecision::Permit,
                |_, _| unreachable!(),
            )
            .unwrap_err();
        match error {
            WorkerLoopError::PersistedRuntimeMissing { task_id, effect_id } => {
                assert_eq!(task_id, "task-worker-missing");
                assert_eq!(effect_id, "effect-worker-missing");
            }
            other => panic!("unexpected error: {other:?}"),
        }
        assert!(loop_driver.queue_snapshot().completed_task_ids.is_empty());
        assert_eq!(loop_driver.queue_snapshot().active_leases.len(), 1);
    }

    #[test]
    fn worker_loop_persists_pre_exec_retry_state_when_sandbox_spawn_fails() {
        let temp = TempWorkspace::new("retry-pre-exec-spawn");
        let mut orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-retry-pre-exec",
                ScheduleIntent::write(format!("scope:{}", temp.output_path.display())),
                0,
            ))
            .unwrap();
        let runtime_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut first_worker = SqliteSingleWorkerLoop::new(orchestrator, runtime_store);
        first_worker
            .claim_and_drive_once("worker-a", 0, PreflightDecision::Permit, |claim| {
                let effect = EffectRecord::new(
                    "effect-worker-retry-pre-exec",
                    claim.task.task_id.clone(),
                    "trace-worker-retry-pre-exec",
                    "intent-worker-retry-pre-exec",
                    EffectActor::Worker,
                    EffectAction::FileWrite,
                    claim.task.intent.target_scope.clone(),
                    EffectTier::Tier1,
                    EffectReversibility::Rollbackable,
                    ProbeMode::Auto,
                );
                Ok((InMemoryTaskRuntime::new(effect), sandbox_fail_command()))
            })
            .unwrap()
            .expect("first worker must claim queued task");

        let retry_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        let retry_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut retry_worker = SqliteSingleWorkerLoop::new(retry_orchestrator, retry_store);

        let error = retry_worker
            .claim_and_retry_failed_once(
                "worker-b",
                26,
                "effect-worker-retry-pre-exec",
                PreflightDecision::Permit,
                |claim, runtime| {
                    assert_eq!(claim.task.task_id, "task-worker-retry-pre-exec");
                    assert_eq!(runtime.worker_state, WorkerState::Executing);
                    Ok(sandbox_missing_program_command())
                },
            )
            .unwrap_err();
        assert!(matches!(error, WorkerLoopError::Sandbox(_)));
        assert_eq!(retry_worker.queue_snapshot().completed_task_ids.len(), 0);
        assert_eq!(retry_worker.queue_snapshot().active_leases.len(), 1);

        let verify_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let restored = verify_store
            .load_runtime(
                "task-worker-retry-pre-exec",
                "effect-worker-retry-pre-exec",
            )
            .unwrap()
            .expect("retry pre-exec runtime must persist before sandbox spawn");
        assert_eq!(restored.worker_state, WorkerState::Executing);
        assert_eq!(restored.effect.status, EffectStatus::Prepared);
    }

    #[test]
    fn worker_loop_reclaims_expired_failed_task_and_retries_persisted_runtime() {
        let temp = TempWorkspace::new("reclaim");
        let mut orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-retry",
                ScheduleIntent::write(format!("scope:{}", temp.output_path.display())),
                0,
            ))
            .unwrap();
        let runtime_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut first_worker = SqliteSingleWorkerLoop::new(orchestrator, runtime_store);

        let first_outcome = first_worker
            .claim_and_drive_once("worker-a", 0, PreflightDecision::Permit, |claim| {
                let effect = EffectRecord::new(
                    "effect-worker-retry",
                    claim.task.task_id.clone(),
                    "trace-worker-retry",
                    "intent-worker-retry",
                    EffectActor::Worker,
                    EffectAction::FileWrite,
                    claim.task.intent.target_scope.clone(),
                    EffectTier::Tier1,
                    EffectReversibility::Rollbackable,
                    ProbeMode::Auto,
                );
                Ok((InMemoryTaskRuntime::new(effect), sandbox_fail_command()))
            })
            .unwrap()
            .expect("first worker must claim queued task");

        assert_eq!(first_outcome.final_summary.worker_state, WorkerState::Failed);
        assert_eq!(first_outcome.final_summary.effect_status, EffectStatus::Prepared);
        assert!(!first_outcome.completed);
        assert_eq!(first_worker.queue_snapshot().completed_task_ids.len(), 0);
        assert_eq!(first_worker.queue_snapshot().active_leases.len(), 1);

        let second_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        let second_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut second_worker = SqliteSingleWorkerLoop::new(second_orchestrator, second_store);

        let blocked = second_worker
            .claim_and_resume_once("worker-b", 10, |_| unreachable!())
            .unwrap();
        assert!(blocked.is_none());

        let expected_bytes = b"safeclaw reclaimed retry\n";
        let retry_outcome = second_worker
            .claim_and_retry_failed_once(
                "worker-b",
                26,
                "effect-worker-retry",
                PreflightDecision::Permit,
                |claim, runtime| {
                    assert_eq!(claim.task.task_id, "task-worker-retry");
                    assert_eq!(runtime.worker_state, WorkerState::Executing);
                    Ok(sandbox_write_command(&temp.output_path, expected_bytes))
                },
            )
            .unwrap()
            .expect("expired task must be reclaimable");

        assert_eq!(retry_outcome.claim.lease.owner_id, "worker-b");
        assert_eq!(retry_outcome.claim.lease.fencing_token, 2);
        assert_eq!(retry_outcome.final_summary.worker_state, WorkerState::Succeeded);
        assert_eq!(retry_outcome.final_summary.effect_status, EffectStatus::Executed);
        assert!(retry_outcome.completed);
        assert_eq!(fs::read(&temp.output_path).unwrap(), expected_bytes);
        assert!(second_worker.queue_snapshot().active_leases.is_empty());
        assert_eq!(
            second_worker.queue_snapshot().completed_task_ids,
            vec![String::from("task-worker-retry")]
        );

        let verify_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let restored = verify_store
            .load_runtime("task-worker-retry", "effect-worker-retry")
            .unwrap()
            .expect("retried runtime must reload");
        assert_eq!(restored.worker_state, WorkerState::Succeeded);
        assert_eq!(restored.effect.status, EffectStatus::Executed);
        assert!(!restored.attempts.is_empty());
    }

    fn sandbox_fail_command() -> SandboxCommand {
        if cfg!(windows) {
            SandboxCommand::new("powershell", ["-Command", "Write-Error 'boom'; exit 7"], 5_000)
        } else {
            SandboxCommand::new("sh", ["-c", "echo boom 1>&2; exit 7"], 5_000)
        }
    }

    fn sandbox_missing_program_command() -> SandboxCommand {
        SandboxCommand::new(
            "safeclaw-missing-program-for-spawn-test",
            std::iter::empty::<&str>(),
            5_000,
        )
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
                .expect("worker loop demo bytes must remain utf-8");
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

    fn sandbox_write_then_timeout_command(
        output_path: &Path,
        output_bytes: &[u8],
    ) -> SandboxCommand {
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
                        "$bytes = [byte[]]({bytes_literal}); [System.IO.File]::WriteAllBytes('{}', $bytes); Start-Sleep -Milliseconds 1000",
                        output_path.display()
                    ),
                ],
                500,
            )
        } else {
            let text = String::from_utf8(output_bytes.to_vec())
                .expect("worker loop demo bytes must remain utf-8");
            SandboxCommand::new(
                "sh",
                [
                    "-c",
                    &format!("printf '%s' '{}' > '{}'; sleep 1", text, output_path.display()),
                ],
                500,
            )
        }
    }
}
