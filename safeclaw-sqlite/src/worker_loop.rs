use crate::{
    FileSystemProbeAdapter, LocalSandboxExecutor, NetworkProbeAdapter, SandboxCommand,
    SandboxExecutionReport, SandboxRuntimeError, SqliteAdapterError, SqliteRuntimeStore,
    SqliteTaskOrchestrator,
};
use safeclaw_core::{
    effect_ledger::EffectAction,
    recovery::probes::ProbeAdapterError,
    scheduler::{OrchestratorClaim, OrchestratorError, OrchestratorSnapshot, TaskOrchestrator},
    worker_lifecycle::WorkerState,
    InMemoryTaskRuntime, PreflightDecision, RunSummary, RuntimeError,
};

#[derive(Debug)]
pub enum WorkerLoopError {
    Orchestrator(OrchestratorError),
    Runtime(RuntimeError),
    Sandbox(SandboxRuntimeError),
    Store(SqliteAdapterError),
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
        let Some(claim) = self
            .orchestrator
            .claim_next(owner_id, now_ms)
            .map_err(WorkerLoopError::Orchestrator)?
        else {
            return Ok(None);
        };

        let (mut runtime, command) = build(&claim)?;
        runtime
            .begin_execution(preflight)
            .map_err(WorkerLoopError::Runtime)?;

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

        Ok(Some(WorkerLoopOutcome {
            claim,
            report,
            execution_summary,
            final_summary,
            completed,
        }))
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
    use super::SqliteSingleWorkerLoop;
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
