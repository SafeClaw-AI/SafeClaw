use std::path::Path;

use crate::{
    open_database, FileSystemProbeAdapter, LocalSandboxExecutor, NetworkProbeAdapter,
    SandboxCommand, SandboxExecutionReport, SandboxRuntimeError, SqliteAdapterError,
    SqliteOpenOptions, SqliteRuntimeStore, SqliteTaskOrchestrator,
};
use safeclaw_core::{
    effect_ledger::EffectAction,
    recovery::probes::ProbeAdapterError,
    scheduler::{
        OrchestratorClaim, OrchestratorError, OrchestratorSnapshot, OrchestratorTask,
        TaskOrchestrator,
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
    pub fn open(
        path: impl AsRef<Path>,
        options: SqliteOpenOptions,
    ) -> Result<Self, SqliteAdapterError> {
        let orchestrator = SqliteTaskOrchestrator::new(open_database(path.as_ref(), options)?);
        let runtime_store = SqliteRuntimeStore::new(open_database(path.as_ref(), options)?);
        Ok(Self::new(orchestrator, runtime_store))
    }

    pub fn new(orchestrator: SqliteTaskOrchestrator, runtime_store: SqliteRuntimeStore) -> Self {
        Self {
            orchestrator,
            runtime_store,
            sandbox: LocalSandboxExecutor::new(),
            filesystem_probe: FileSystemProbeAdapter::new(),
            network_probe: NetworkProbeAdapter::new(),
        }
    }

    pub fn with_lease_ttl_ms(mut self, lease_ttl_ms: u64) -> Self {
        self.orchestrator = self.orchestrator.with_lease_ttl_ms(lease_ttl_ms);
        self
    }

    pub fn enqueue_task(&mut self, task: OrchestratorTask) -> Result<(), WorkerLoopError> {
        self.orchestrator
            .enqueue(task)
            .map_err(WorkerLoopError::Orchestrator)
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

    pub fn claim_and_drive_until_empty<F>(
        &mut self,
        owner_id: &str,
        now_ms: u64,
        preflight: PreflightDecision,
        mut build: F,
    ) -> Result<Vec<WorkerLoopOutcome>, WorkerLoopError>
    where
        F: FnMut(&OrchestratorClaim) -> Result<(InMemoryTaskRuntime, SandboxCommand), WorkerLoopError>,
    {
        let mut outcomes = Vec::new();
        loop {
            let Some(claim) = self.claim_once(owner_id, now_ms)? else {
                break;
            };

            let (mut runtime, command) = build(&claim)?;
            runtime
                .begin_execution(preflight)
                .map_err(WorkerLoopError::Runtime)?;
            self.persist_runtime(&runtime, &claim, "pre-exec")?;
            outcomes.push(self.drive_claimed_runtime(claim, runtime, command)?);
        }
        Ok(outcomes)
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

    pub fn claim_and_resume_persisted_once<F>(
        &mut self,
        owner_id: &str,
        now_ms: u64,
        effect_id: &str,
        build_command: F,
    ) -> Result<Option<WorkerLoopOutcome>, WorkerLoopError>
    where
        F: FnOnce(&OrchestratorClaim, &InMemoryTaskRuntime) -> Result<SandboxCommand, WorkerLoopError>,
    {
        let Some(claim) = self.claim_once(owner_id, now_ms)? else {
            return Ok(None);
        };

        let runtime = self
            .runtime_store
            .load_runtime(&claim.task.task_id, effect_id)
            .map_err(WorkerLoopError::Store)?
            .ok_or_else(|| WorkerLoopError::PersistedRuntimeMissing {
                task_id: claim.task.task_id.clone(),
                effect_id: effect_id.to_string(),
            })?;
        let command = build_command(&claim, &runtime)?;
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
        io::{Read, Write},
        net::TcpListener,
        path::{Path, PathBuf},
        process, thread,
        time::{Duration, SystemTime, UNIX_EPOCH},
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
    fn worker_loop_open_and_enqueue_task_tracks_queue_snapshot() {
        let temp = TempWorkspace::new("open-enqueue");
        let mut loop_driver = SqliteSingleWorkerLoop::open(
            &temp.db_path,
            SqliteOpenOptions::default(),
        )
        .unwrap()
        .with_lease_ttl_ms(25);
        loop_driver
            .enqueue_task(OrchestratorTask::new(
                "task-worker-open-enqueue",
                ScheduleIntent::write(format!("scope:{}", temp.output_path.display())),
                0,
            ))
            .unwrap();

        let snapshot = loop_driver.queue_snapshot();
        assert_eq!(snapshot.queued_tasks.len(), 1);
        assert_eq!(snapshot.queued_tasks[0].task_id, "task-worker-open-enqueue");
        assert!(snapshot.active_leases.is_empty());
        assert!(snapshot.completed_task_ids.is_empty());
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
    fn worker_loop_drive_until_empty_returns_empty_batch_when_queue_is_empty() {
        let temp = TempWorkspace::new("empty-batch");
        let orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let runtime_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut loop_driver = SqliteSingleWorkerLoop::new(orchestrator, runtime_store);

        let outcomes = loop_driver
            .claim_and_drive_until_empty("worker-a", 0, PreflightDecision::Permit, |_| unreachable!())
            .unwrap();
        assert!(outcomes.is_empty());
    }

    #[test]
    fn worker_loop_drives_multiple_queued_tasks_until_empty() {
        let temp = TempWorkspace::new("drain-batch");
        let first_output = temp.root.join("output-1.txt");
        let second_output = temp.root.join("output-2.txt");
        let mut orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-batch-1",
                ScheduleIntent::write(format!("scope:{}", first_output.display())),
                0,
            ))
            .unwrap();
        orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-batch-2",
                ScheduleIntent::write(format!("scope:{}", second_output.display())),
                0,
            ))
            .unwrap();
        let runtime_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut loop_driver = SqliteSingleWorkerLoop::new(orchestrator, runtime_store);

        let outcomes = loop_driver
            .claim_and_drive_until_empty("worker-a", 0, PreflightDecision::Permit, |claim| {
                let (effect_id, trace_id, intent_key, output_path, output_bytes) =
                    match claim.task.task_id.as_str() {
                        "task-worker-batch-1" => (
                            "effect-worker-batch-1",
                            "trace-worker-batch-1",
                            "intent-worker-batch-1",
                            &first_output,
                            b"safeclaw batch one\n".as_slice(),
                        ),
                        "task-worker-batch-2" => (
                            "effect-worker-batch-2",
                            "trace-worker-batch-2",
                            "intent-worker-batch-2",
                            &second_output,
                            b"safeclaw batch two\n".as_slice(),
                        ),
                        other => panic!("unexpected task id: {other}"),
                    };
                let effect = EffectRecord::new(
                    effect_id,
                    claim.task.task_id.clone(),
                    trace_id,
                    intent_key,
                    EffectActor::Worker,
                    EffectAction::FileWrite,
                    claim.task.intent.target_scope.clone(),
                    EffectTier::Tier1,
                    EffectReversibility::Rollbackable,
                    ProbeMode::Auto,
                );
                Ok((
                    InMemoryTaskRuntime::new(effect),
                    sandbox_write_command(output_path, output_bytes),
                ))
            })
            .unwrap();

        assert_eq!(outcomes.len(), 2);
        assert_eq!(outcomes[0].claim.task.task_id, "task-worker-batch-1");
        assert_eq!(outcomes[1].claim.task.task_id, "task-worker-batch-2");
        assert!(outcomes.iter().all(|outcome| outcome.completed));
        assert!(outcomes
            .iter()
            .all(|outcome| outcome.final_summary.worker_state == WorkerState::Succeeded));
        assert_eq!(fs::read(&first_output).unwrap(), b"safeclaw batch one\n");
        assert_eq!(fs::read(&second_output).unwrap(), b"safeclaw batch two\n");
        assert!(loop_driver.queue_snapshot().queued_tasks.is_empty());
        assert!(loop_driver.queue_snapshot().active_leases.is_empty());
        assert_eq!(
            loop_driver.queue_snapshot().completed_task_ids,
            vec![
                String::from("task-worker-batch-1"),
                String::from("task-worker-batch-2"),
            ]
        );

        let verify_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let restored_one = verify_store
            .load_runtime("task-worker-batch-1", "effect-worker-batch-1")
            .unwrap()
            .expect("first batch runtime must reload");
        let restored_two = verify_store
            .load_runtime("task-worker-batch-2", "effect-worker-batch-2")
            .unwrap()
            .expect("second batch runtime must reload");
        assert_eq!(restored_one.worker_state, WorkerState::Succeeded);
        assert_eq!(restored_two.worker_state, WorkerState::Succeeded);
        assert_eq!(restored_one.effect.status, EffectStatus::Executed);
        assert_eq!(restored_two.effect.status, EffectStatus::Executed);
    }

    #[test]
    fn worker_loop_drive_until_empty_stops_on_later_spawn_failure() {
        let temp = TempWorkspace::new("drain-batch-failure");
        let first_output = temp.root.join("output-1.txt");
        let second_output = temp.root.join("output-2.txt");
        let mut orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-batch-failure-1",
                ScheduleIntent::write(format!("scope:{}", first_output.display())),
                0,
            ))
            .unwrap();
        orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-batch-failure-2",
                ScheduleIntent::write(format!("scope:{}", second_output.display())),
                0,
            ))
            .unwrap();
        let runtime_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut loop_driver = SqliteSingleWorkerLoop::new(orchestrator, runtime_store);

        let error = loop_driver
            .claim_and_drive_until_empty("worker-a", 0, PreflightDecision::Permit, |claim| {
                let (effect_id, trace_id, intent_key) = match claim.task.task_id.as_str() {
                    "task-worker-batch-failure-1" => (
                        "effect-worker-batch-failure-1",
                        "trace-worker-batch-failure-1",
                        "intent-worker-batch-failure-1",
                    ),
                    "task-worker-batch-failure-2" => (
                        "effect-worker-batch-failure-2",
                        "trace-worker-batch-failure-2",
                        "intent-worker-batch-failure-2",
                    ),
                    other => panic!("unexpected task id: {other}"),
                };
                let effect = EffectRecord::new(
                    effect_id,
                    claim.task.task_id.clone(),
                    trace_id,
                    intent_key,
                    EffectActor::Worker,
                    EffectAction::FileWrite,
                    claim.task.intent.target_scope.clone(),
                    EffectTier::Tier1,
                    EffectReversibility::Rollbackable,
                    ProbeMode::Auto,
                );
                let command = match claim.task.task_id.as_str() {
                    "task-worker-batch-failure-1" => {
                        sandbox_write_command(&first_output, b"safeclaw batch failure one\n")
                    }
                    "task-worker-batch-failure-2" => sandbox_missing_program_command(),
                    other => panic!("unexpected task id: {other}"),
                };
                Ok((InMemoryTaskRuntime::new(effect), command))
            })
            .unwrap_err();

        assert!(matches!(error, WorkerLoopError::Sandbox(_)));
        assert_eq!(fs::read(&first_output).unwrap(), b"safeclaw batch failure one\n");
        assert!(!second_output.exists());
        assert!(loop_driver.queue_snapshot().queued_tasks.is_empty());
        assert_eq!(
            loop_driver.queue_snapshot().completed_task_ids,
            vec![String::from("task-worker-batch-failure-1")]
        );
        assert_eq!(loop_driver.queue_snapshot().active_leases.len(), 1);
        assert_eq!(
            loop_driver.queue_snapshot().active_leases[0].task_id,
            "task-worker-batch-failure-2"
        );

        let verify_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let restored_one = verify_store
            .load_runtime("task-worker-batch-failure-1", "effect-worker-batch-failure-1")
            .unwrap()
            .expect("first batch failure runtime must reload");
        let restored_two = verify_store
            .load_runtime("task-worker-batch-failure-2", "effect-worker-batch-failure-2")
            .unwrap()
            .expect("second batch failure runtime must reload");
        assert_eq!(restored_one.worker_state, WorkerState::Succeeded);
        assert_eq!(restored_one.effect.status, EffectStatus::Executed);
        assert_eq!(restored_two.worker_state, WorkerState::Executing);
        assert_eq!(restored_two.effect.status, EffectStatus::Prepared);
    }

    #[test]
    fn worker_loop_drive_until_empty_skips_conflicts_held_by_other_owner() {
        let temp = TempWorkspace::new("drain-scope-skip");
        let shared_output = temp.root.join("shared-output.txt");
        let other_one_output = temp.root.join("other-one-output.txt");
        let other_two_output = temp.root.join("other-two-output.txt");
        let shared_scope = format!("scope:{}", shared_output.display());
        let other_one_scope = format!("scope:{}", other_one_output.display());
        let other_two_scope = format!("scope:{}", other_two_output.display());

        let mut blocking_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-batch-shared-1",
                ScheduleIntent::write(shared_scope.clone()),
                0,
            ))
            .unwrap();
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-batch-shared-2",
                ScheduleIntent::write(shared_scope.clone()),
                1,
            ))
            .unwrap();
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-batch-other-1",
                ScheduleIntent::write(other_one_scope.clone()),
                2,
            ))
            .unwrap();
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-batch-other-2",
                ScheduleIntent::write(other_two_scope.clone()),
                3,
            ))
            .unwrap();

        let blocking_claim = blocking_orchestrator.claim_next("worker-a", 0).unwrap().unwrap();
        assert_eq!(blocking_claim.task.task_id, "task-worker-batch-shared-1");

        let drain_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        let drain_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut drain_worker = SqliteSingleWorkerLoop::new(drain_orchestrator, drain_store);

        let outcomes = drain_worker
            .claim_and_drive_until_empty("worker-b", 1, PreflightDecision::Permit, |claim| {
                let (effect_id, trace_id, intent_key, output_path, output_bytes) =
                    match claim.task.task_id.as_str() {
                        "task-worker-batch-other-1" => (
                            "effect-worker-batch-other-1",
                            "trace-worker-batch-other-1",
                            "intent-worker-batch-other-1",
                            &other_one_output,
                            b"safeclaw batch other one\n".as_slice(),
                        ),
                        "task-worker-batch-other-2" => (
                            "effect-worker-batch-other-2",
                            "trace-worker-batch-other-2",
                            "intent-worker-batch-other-2",
                            &other_two_output,
                            b"safeclaw batch other two\n".as_slice(),
                        ),
                        other => panic!("unexpected task id: {other}"),
                    };
                let effect = EffectRecord::new(
                    effect_id,
                    claim.task.task_id.clone(),
                    trace_id,
                    intent_key,
                    EffectActor::Worker,
                    EffectAction::FileWrite,
                    claim.task.intent.target_scope.clone(),
                    EffectTier::Tier1,
                    EffectReversibility::Rollbackable,
                    ProbeMode::Auto,
                );
                Ok((
                    InMemoryTaskRuntime::new(effect),
                    sandbox_write_command(output_path, output_bytes),
                ))
            })
            .unwrap();

        assert_eq!(outcomes.len(), 2);
        assert_eq!(outcomes[0].claim.task.task_id, "task-worker-batch-other-1");
        assert_eq!(outcomes[1].claim.task.task_id, "task-worker-batch-other-2");
        assert!(outcomes.iter().all(|outcome| outcome.completed));
        assert_eq!(fs::read(&other_one_output).unwrap(), b"safeclaw batch other one\n");
        assert_eq!(fs::read(&other_two_output).unwrap(), b"safeclaw batch other two\n");
        assert!(!shared_output.exists());
        assert_eq!(drain_worker.queue_snapshot().queued_tasks.len(), 1);
        assert_eq!(
            drain_worker.queue_snapshot().queued_tasks[0].task_id,
            "task-worker-batch-shared-2"
        );
        assert_eq!(drain_worker.queue_snapshot().active_leases.len(), 1);
        assert_eq!(
            drain_worker.queue_snapshot().active_leases[0].task_id,
            "task-worker-batch-shared-1"
        );
        assert_eq!(
            drain_worker.queue_snapshot().completed_task_ids,
            vec![
                String::from("task-worker-batch-other-1"),
                String::from("task-worker-batch-other-2"),
            ]
        );

        let verify_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let restored_one = verify_store
            .load_runtime("task-worker-batch-other-1", "effect-worker-batch-other-1")
            .unwrap()
            .expect("first other runtime must reload");
        let restored_two = verify_store
            .load_runtime("task-worker-batch-other-2", "effect-worker-batch-other-2")
            .unwrap()
            .expect("second other runtime must reload");
        assert_eq!(restored_one.worker_state, WorkerState::Succeeded);
        assert_eq!(restored_one.effect.status, EffectStatus::Executed);
        assert_eq!(restored_two.worker_state, WorkerState::Succeeded);
        assert_eq!(restored_two.effect.status, EffectStatus::Executed);
        assert!(verify_store
            .load_runtime("task-worker-batch-shared-2", "effect-worker-batch-shared-2")
            .unwrap()
            .is_none());
    }

    #[test]
    fn worker_loop_drive_until_empty_claims_remaining_conflict_after_release() {
        let temp = TempWorkspace::new("drain-scope-release");
        let shared_output = temp.root.join("shared-output.txt");
        let other_one_output = temp.root.join("other-one-output.txt");
        let other_two_output = temp.root.join("other-two-output.txt");
        let shared_scope = format!("scope:{}", shared_output.display());
        let other_one_scope = format!("scope:{}", other_one_output.display());
        let other_two_scope = format!("scope:{}", other_two_output.display());

        let mut blocking_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-batch-shared-1",
                ScheduleIntent::write(shared_scope.clone()),
                0,
            ))
            .unwrap();
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-batch-shared-2",
                ScheduleIntent::write(shared_scope.clone()),
                1,
            ))
            .unwrap();
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-batch-other-1",
                ScheduleIntent::write(other_one_scope.clone()),
                2,
            ))
            .unwrap();
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-batch-other-2",
                ScheduleIntent::write(other_two_scope.clone()),
                3,
            ))
            .unwrap();

        let blocking_claim = blocking_orchestrator.claim_next("worker-a", 0).unwrap().unwrap();
        assert_eq!(blocking_claim.task.task_id, "task-worker-batch-shared-1");

        let first_drain_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        let first_drain_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut first_drain_worker =
            SqliteSingleWorkerLoop::new(first_drain_orchestrator, first_drain_store);

        let first_outcomes = first_drain_worker
            .claim_and_drive_until_empty("worker-b", 1, PreflightDecision::Permit, |claim| {
                let (effect_id, trace_id, intent_key, output_path, output_bytes) =
                    match claim.task.task_id.as_str() {
                        "task-worker-batch-other-1" => (
                            "effect-worker-batch-other-1",
                            "trace-worker-batch-other-1",
                            "intent-worker-batch-other-1",
                            &other_one_output,
                            b"safeclaw batch other one\n".as_slice(),
                        ),
                        "task-worker-batch-other-2" => (
                            "effect-worker-batch-other-2",
                            "trace-worker-batch-other-2",
                            "intent-worker-batch-other-2",
                            &other_two_output,
                            b"safeclaw batch other two\n".as_slice(),
                        ),
                        other => panic!("unexpected task id: {other}"),
                    };
                let effect = EffectRecord::new(
                    effect_id,
                    claim.task.task_id.clone(),
                    trace_id,
                    intent_key,
                    EffectActor::Worker,
                    EffectAction::FileWrite,
                    claim.task.intent.target_scope.clone(),
                    EffectTier::Tier1,
                    EffectReversibility::Rollbackable,
                    ProbeMode::Auto,
                );
                Ok((
                    InMemoryTaskRuntime::new(effect),
                    sandbox_write_command(output_path, output_bytes),
                ))
            })
            .unwrap();
        assert_eq!(first_outcomes.len(), 2);
        assert_eq!(
            first_drain_worker.queue_snapshot().queued_tasks[0].task_id,
            "task-worker-batch-shared-2"
        );

        blocking_orchestrator
            .complete(
                &blocking_claim.task.task_id,
                &blocking_claim.lease.lease_id,
                &blocking_claim.lease.owner_id,
            )
            .unwrap();

        let second_drain_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        let second_drain_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut second_drain_worker =
            SqliteSingleWorkerLoop::new(second_drain_orchestrator, second_drain_store);

        let second_outcomes = second_drain_worker
            .claim_and_drive_until_empty("worker-c", 2, PreflightDecision::Permit, |claim| {
                assert_eq!(claim.task.task_id, "task-worker-batch-shared-2");
                let effect = EffectRecord::new(
                    "effect-worker-batch-shared-2",
                    claim.task.task_id.clone(),
                    "trace-worker-batch-shared-2",
                    "intent-worker-batch-shared-2",
                    EffectActor::Worker,
                    EffectAction::FileWrite,
                    claim.task.intent.target_scope.clone(),
                    EffectTier::Tier1,
                    EffectReversibility::Rollbackable,
                    ProbeMode::Auto,
                );
                Ok((
                    InMemoryTaskRuntime::new(effect),
                    sandbox_write_command(&shared_output, b"safeclaw shared after release\n"),
                ))
            })
            .unwrap();

        assert_eq!(second_outcomes.len(), 1);
        assert_eq!(
            second_outcomes[0].claim.task.task_id,
            "task-worker-batch-shared-2"
        );
        assert!(second_outcomes[0].completed);
        assert_eq!(fs::read(&shared_output).unwrap(), b"safeclaw shared after release\n");
        assert!(second_drain_worker.queue_snapshot().queued_tasks.is_empty());
        assert!(second_drain_worker.queue_snapshot().active_leases.is_empty());
        assert_eq!(
            second_drain_worker.queue_snapshot().completed_task_ids,
            vec![
                String::from("task-worker-batch-other-1"),
                String::from("task-worker-batch-other-2"),
                String::from("task-worker-batch-shared-1"),
                String::from("task-worker-batch-shared-2"),
            ]
        );

        let verify_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let restored_shared = verify_store
            .load_runtime("task-worker-batch-shared-2", "effect-worker-batch-shared-2")
            .unwrap()
            .expect("released shared runtime must reload");
        assert_eq!(restored_shared.worker_state, WorkerState::Succeeded);
        assert_eq!(restored_shared.effect.status, EffectStatus::Executed);
    }

    #[test]
    fn worker_loop_skips_conflicting_write_scope_held_by_other_owner() {
        let temp = TempWorkspace::new("scope-skip");
        let shared_output = temp.root.join("shared-output.txt");
        let other_output = temp.root.join("other-output.txt");
        let shared_scope = format!("scope:{}", shared_output.display());
        let other_scope = format!("scope:{}", other_output.display());

        let mut blocking_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-shared-1",
                ScheduleIntent::write(shared_scope.clone()),
                0,
            ))
            .unwrap();
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-shared-2",
                ScheduleIntent::write(shared_scope.clone()),
                1,
            ))
            .unwrap();
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-other",
                ScheduleIntent::write(other_scope.clone()),
                2,
            ))
            .unwrap();

        let blocking_claim = blocking_orchestrator.claim_next("worker-a", 0).unwrap().unwrap();
        assert_eq!(blocking_claim.task.task_id, "task-worker-shared-1");

        let other_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        let other_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut other_worker = SqliteSingleWorkerLoop::new(other_orchestrator, other_store);

        let other_outcome = other_worker
            .claim_and_drive_once("worker-b", 1, PreflightDecision::Permit, |claim| {
                assert_eq!(claim.task.task_id, "task-worker-other");
                let effect = EffectRecord::new(
                    "effect-worker-other",
                    claim.task.task_id.clone(),
                    "trace-worker-other",
                    "intent-worker-other",
                    EffectActor::Worker,
                    EffectAction::FileWrite,
                    claim.task.intent.target_scope.clone(),
                    EffectTier::Tier1,
                    EffectReversibility::Rollbackable,
                    ProbeMode::Auto,
                );
                Ok((
                    InMemoryTaskRuntime::new(effect),
                    sandbox_write_command(&other_output, b"safeclaw other task\n"),
                ))
            })
            .unwrap()
            .expect("other-scope task must remain claimable");
        assert_eq!(other_outcome.claim.task.task_id, "task-worker-other");
        assert!(other_outcome.completed);

        let blocked_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        let blocked_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut blocked_worker = SqliteSingleWorkerLoop::new(blocked_orchestrator, blocked_store);
        let blocked = blocked_worker
            .claim_and_drive_once("worker-c", 2, PreflightDecision::Permit, |_| unreachable!())
            .unwrap();
        assert!(blocked.is_none());

        blocking_orchestrator
            .complete(
                &blocking_claim.task.task_id,
                &blocking_claim.lease.lease_id,
                &blocking_claim.lease.owner_id,
            )
            .unwrap();

        let unblocked_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        let unblocked_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut unblocked_worker = SqliteSingleWorkerLoop::new(unblocked_orchestrator, unblocked_store);

        let unblocked = unblocked_worker
            .claim_and_drive_once("worker-c", 3, PreflightDecision::Permit, |claim| {
                assert_eq!(claim.task.task_id, "task-worker-shared-2");
                let effect = EffectRecord::new(
                    "effect-worker-shared-2",
                    claim.task.task_id.clone(),
                    "trace-worker-shared-2",
                    "intent-worker-shared-2",
                    EffectActor::Worker,
                    EffectAction::FileWrite,
                    claim.task.intent.target_scope.clone(),
                    EffectTier::Tier1,
                    EffectReversibility::Rollbackable,
                    ProbeMode::Auto,
                );
                Ok((
                    InMemoryTaskRuntime::new(effect),
                    sandbox_write_command(&shared_output, b"safeclaw shared task\n"),
                ))
            })
            .unwrap()
            .expect("shared-scope task must unblock after active lease finishes");
        assert_eq!(unblocked.claim.task.task_id, "task-worker-shared-2");
        assert!(unblocked.completed);
        assert_eq!(fs::read(&other_output).unwrap(), b"safeclaw other task\n");
        assert_eq!(fs::read(&shared_output).unwrap(), b"safeclaw shared task\n");
    }

    #[test]
    fn worker_loop_allows_same_scope_read_while_other_owner_holds_write_lease() {
        let temp = TempWorkspace::new("scope-read-pass");
        let shared_scope = format!("scope:{}", temp.root.join("shared.txt").display());
        let write_after_output = temp.root.join("shared-write-after-read.txt");

        let mut blocking_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-shared-write-active",
                ScheduleIntent::write(shared_scope.clone()),
                0,
            ))
            .unwrap();
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-shared-read",
                ScheduleIntent::read(shared_scope.clone()),
                1,
            ))
            .unwrap();
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-shared-write-after",
                ScheduleIntent::write(shared_scope.clone()),
                2,
            ))
            .unwrap();

        let blocking_claim = blocking_orchestrator.claim_next("worker-a", 0).unwrap().unwrap();
        assert_eq!(blocking_claim.task.task_id, "task-worker-shared-write-active");

        let read_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        let read_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut read_worker = SqliteSingleWorkerLoop::new(read_orchestrator, read_store);

        let read_outcome = read_worker
            .claim_and_drive_once("worker-b", 1, PreflightDecision::Permit, |claim| {
                assert_eq!(claim.task.task_id, "task-worker-shared-read");
                let effect = EffectRecord::new(
                    "effect-worker-shared-read",
                    claim.task.task_id.clone(),
                    "trace-worker-shared-read",
                    "intent-worker-shared-read",
                    EffectActor::Worker,
                    EffectAction::NetworkRequest,
                    claim.task.intent.target_scope.clone(),
                    EffectTier::Tier1,
                    EffectReversibility::Rollbackable,
                    ProbeMode::Auto,
                );
                Ok((InMemoryTaskRuntime::new(effect), sandbox_success_command()))
            })
            .unwrap()
            .expect("same-scope read must remain claimable");
        assert_eq!(read_outcome.claim.task.task_id, "task-worker-shared-read");
        assert!(read_outcome.completed);

        let blocked_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        let blocked_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut blocked_worker = SqliteSingleWorkerLoop::new(blocked_orchestrator, blocked_store);
        let blocked = blocked_worker
            .claim_and_drive_once("worker-c", 2, PreflightDecision::Permit, |_| unreachable!())
            .unwrap();
        assert!(blocked.is_none());

        blocking_orchestrator
            .complete(
                &blocking_claim.task.task_id,
                &blocking_claim.lease.lease_id,
                &blocking_claim.lease.owner_id,
            )
            .unwrap();

        let write_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        let write_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut write_worker = SqliteSingleWorkerLoop::new(write_orchestrator, write_store);

        let write_outcome = write_worker
            .claim_and_drive_once("worker-c", 3, PreflightDecision::Permit, |claim| {
                assert_eq!(claim.task.task_id, "task-worker-shared-write-after");
                let effect = EffectRecord::new(
                    "effect-worker-shared-write-after",
                    claim.task.task_id.clone(),
                    "trace-worker-shared-write-after",
                    "intent-worker-shared-write-after",
                    EffectActor::Worker,
                    EffectAction::FileWrite,
                    claim.task.intent.target_scope.clone(),
                    EffectTier::Tier1,
                    EffectReversibility::Rollbackable,
                    ProbeMode::Auto,
                );
                Ok((
                    InMemoryTaskRuntime::new(effect),
                    sandbox_write_command(&write_after_output, b"safeclaw write after read\n"),
                ))
            })
            .unwrap()
            .expect("same-scope write must unblock after active lease finishes");
        assert_eq!(write_outcome.claim.task.task_id, "task-worker-shared-write-after");
        assert!(write_outcome.completed);
        assert_eq!(fs::read(&write_after_output).unwrap(), b"safeclaw write after read\n");

        let verify_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let restored_read = verify_store
            .load_runtime("task-worker-shared-read", "effect-worker-shared-read")
            .unwrap()
            .expect("same-scope read runtime must reload");
        let restored_write = verify_store
            .load_runtime(
                "task-worker-shared-write-after",
                "effect-worker-shared-write-after",
            )
            .unwrap()
            .expect("same-scope write runtime must reload");
        assert_eq!(restored_read.worker_state, WorkerState::Succeeded);
        assert_eq!(restored_read.effect.status, EffectStatus::Executed);
        assert_eq!(restored_write.worker_state, WorkerState::Succeeded);
        assert_eq!(restored_write.effect.status, EffectStatus::Executed);
    }

    #[test]
    fn worker_loop_allows_same_scope_reads_to_coexist() {
        let temp = TempWorkspace::new("scope-read-fanout");
        let shared_scope = format!("scope:{}", temp.root.join("shared-read.txt").display());

        let mut blocking_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-shared-read-1",
                ScheduleIntent::read(shared_scope.clone()),
                0,
            ))
            .unwrap();
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-shared-read-2",
                ScheduleIntent::read(shared_scope.clone()),
                1,
            ))
            .unwrap();

        let blocking_claim = blocking_orchestrator.claim_next("worker-a", 0).unwrap().unwrap();
        assert_eq!(blocking_claim.task.task_id, "task-worker-shared-read-1");
        assert!(!blocking_claim.task.intent.requires_write);

        let read_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        let read_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut read_worker = SqliteSingleWorkerLoop::new(read_orchestrator, read_store);

        let read_outcome = read_worker
            .claim_and_drive_once("worker-b", 1, PreflightDecision::Permit, |claim| {
                assert_eq!(claim.task.task_id, "task-worker-shared-read-2");
                let effect = EffectRecord::new(
                    "effect-worker-shared-read-2",
                    claim.task.task_id.clone(),
                    "trace-worker-shared-read-2",
                    "intent-worker-shared-read-2",
                    EffectActor::Worker,
                    EffectAction::NetworkRequest,
                    claim.task.intent.target_scope.clone(),
                    EffectTier::Tier1,
                    EffectReversibility::Rollbackable,
                    ProbeMode::Auto,
                );
                Ok((InMemoryTaskRuntime::new(effect), sandbox_success_command()))
            })
            .unwrap()
            .expect("same-scope second read must remain claimable");
        assert_eq!(read_outcome.claim.task.task_id, "task-worker-shared-read-2");
        assert!(read_outcome.completed);
        assert_eq!(read_outcome.final_summary.worker_state, WorkerState::Succeeded);
        assert_eq!(read_outcome.final_summary.effect_status, EffectStatus::Executed);
        assert_eq!(read_worker.queue_snapshot().queued_tasks.len(), 0);
        assert_eq!(read_worker.queue_snapshot().active_leases.len(), 1);
        assert_eq!(
            read_worker.queue_snapshot().active_leases[0].task_id,
            "task-worker-shared-read-1"
        );
        assert_eq!(
            read_worker.queue_snapshot().completed_task_ids,
            vec![String::from("task-worker-shared-read-2")]
        );

        let verify_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let restored = verify_store
            .load_runtime("task-worker-shared-read-2", "effect-worker-shared-read-2")
            .unwrap()
            .expect("same-scope second read runtime must reload");
        assert_eq!(restored.worker_state, WorkerState::Succeeded);
        assert_eq!(restored.effect.status, EffectStatus::Executed);
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
    fn worker_loop_resume_reports_missing_persisted_runtime() {
        let temp = TempWorkspace::new("missing-resume-runtime");
        let mut orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-missing-resume",
                ScheduleIntent::write(format!("scope:{}", temp.output_path.display())),
                0,
            ))
            .unwrap();
        let runtime_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut loop_driver = SqliteSingleWorkerLoop::new(orchestrator, runtime_store);

        let error = loop_driver
            .claim_and_resume_persisted_once(
                "worker-a",
                0,
                "effect-worker-missing-resume",
                |_, _| unreachable!(),
            )
            .unwrap_err();
        match error {
            WorkerLoopError::PersistedRuntimeMissing { task_id, effect_id } => {
                assert_eq!(task_id, "task-worker-missing-resume");
                assert_eq!(effect_id, "effect-worker-missing-resume");
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

    #[test]
    fn worker_loop_reclaims_expired_pre_exec_runtime_and_resumes_persisted_runtime() {
        let temp = TempWorkspace::new("resume-persisted");
        let mut orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-resume",
                ScheduleIntent::write(format!("scope:{}", temp.output_path.display())),
                0,
            ))
            .unwrap();
        let runtime_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut first_worker = SqliteSingleWorkerLoop::new(orchestrator, runtime_store);

        let error = first_worker
            .claim_and_drive_once("worker-a", 0, PreflightDecision::Permit, |claim| {
                let effect = EffectRecord::new(
                    "effect-worker-resume",
                    claim.task.task_id.clone(),
                    "trace-worker-resume",
                    "intent-worker-resume",
                    EffectActor::Worker,
                    EffectAction::FileWrite,
                    claim.task.intent.target_scope.clone(),
                    EffectTier::Tier1,
                    EffectReversibility::Rollbackable,
                    ProbeMode::Auto,
                );
                Ok((
                    InMemoryTaskRuntime::new(effect),
                    sandbox_missing_program_command(),
                ))
            })
            .unwrap_err();
        assert!(matches!(error, WorkerLoopError::Sandbox(_)));
        assert_eq!(first_worker.queue_snapshot().completed_task_ids.len(), 0);
        assert_eq!(first_worker.queue_snapshot().active_leases.len(), 1);

        let resume_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        let resume_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut resume_worker = SqliteSingleWorkerLoop::new(resume_orchestrator, resume_store);

        let blocked = resume_worker
            .claim_and_resume_once("worker-b", 10, |_| unreachable!())
            .unwrap();
        assert!(blocked.is_none());

        let expected_bytes = b"safeclaw resumed runtime\n";
        let resumed = resume_worker
            .claim_and_resume_persisted_once(
                "worker-b",
                26,
                "effect-worker-resume",
                |claim, runtime| {
                    assert_eq!(claim.task.task_id, "task-worker-resume");
                    assert_eq!(runtime.worker_state, WorkerState::Executing);
                    assert_eq!(runtime.effect.status, EffectStatus::Prepared);
                    Ok(sandbox_write_command(&temp.output_path, expected_bytes))
                },
            )
            .unwrap()
            .expect("expired pre-exec runtime must be reclaimable");

        assert_eq!(resumed.claim.lease.owner_id, "worker-b");
        assert_eq!(resumed.claim.lease.fencing_token, 2);
        assert_eq!(resumed.final_summary.worker_state, WorkerState::Succeeded);
        assert_eq!(resumed.final_summary.effect_status, EffectStatus::Executed);
        assert!(resumed.completed);
        assert_eq!(fs::read(&temp.output_path).unwrap(), expected_bytes);
        assert!(resume_worker.queue_snapshot().active_leases.is_empty());
        assert_eq!(
            resume_worker.queue_snapshot().completed_task_ids,
            vec![String::from("task-worker-resume")]
        );

        let verify_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let restored = verify_store
            .load_runtime("task-worker-resume", "effect-worker-resume")
            .unwrap()
            .expect("resumed runtime must reload");
        assert_eq!(restored.worker_state, WorkerState::Succeeded);
        assert_eq!(restored.effect.status, EffectStatus::Executed);
        assert!(!restored.attempts.is_empty());
    }

    #[test]
    fn worker_loop_retry_skips_conflicting_scope_held_by_other_owner() {
        let temp = TempWorkspace::new("retry-scope-skip");
        let shared_output = temp.root.join("shared-output.txt");
        let other_output = temp.root.join("retry-output.txt");
        let shared_scope = format!("scope:{}", shared_output.display());
        let other_scope = format!("scope:{}", other_output.display());

        let mut blocking_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-retry-shared-blocking",
                ScheduleIntent::write(shared_scope.clone()),
                0,
            ))
            .unwrap();
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-retry-shared-queued",
                ScheduleIntent::write(shared_scope.clone()),
                1,
            ))
            .unwrap();
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-retry-other",
                ScheduleIntent::write(other_scope.clone()),
                2,
            ))
            .unwrap();

        let blocking_claim = blocking_orchestrator.claim_next("worker-a", 0).unwrap().unwrap();
        assert_eq!(blocking_claim.task.task_id, "task-worker-retry-shared-blocking");

        let first_retry_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        let first_retry_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut first_retry_worker =
            SqliteSingleWorkerLoop::new(first_retry_orchestrator, first_retry_store);

        let first_outcome = first_retry_worker
            .claim_and_drive_once("worker-b", 1, PreflightDecision::Permit, |claim| {
                assert_eq!(claim.task.task_id, "task-worker-retry-other");
                let effect = EffectRecord::new(
                    "effect-worker-retry-other",
                    claim.task.task_id.clone(),
                    "trace-worker-retry-other",
                    "intent-worker-retry-other",
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
            .expect("first retry worker must claim other-scope task");

        assert_eq!(first_outcome.final_summary.worker_state, WorkerState::Failed);
        assert_eq!(first_outcome.final_summary.effect_status, EffectStatus::Prepared);
        assert!(!first_outcome.completed);
        assert_eq!(first_retry_worker.queue_snapshot().queued_tasks.len(), 1);
        assert_eq!(
            first_retry_worker.queue_snapshot().queued_tasks[0].task_id,
            "task-worker-retry-shared-queued"
        );
        assert_eq!(first_retry_worker.queue_snapshot().active_leases.len(), 2);

        let renewed_blocking_lease = blocking_orchestrator
            .renew_lease(
                &blocking_claim.task.task_id,
                &blocking_claim.lease.lease_id,
                &blocking_claim.lease.owner_id,
                20,
            )
            .unwrap();
        assert_eq!(renewed_blocking_lease.owner_id, "worker-a");

        let retry_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        let retry_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut retry_worker = SqliteSingleWorkerLoop::new(retry_orchestrator, retry_store);

        let blocked = retry_worker
            .claim_and_resume_once("worker-c", 10, |_| unreachable!())
            .unwrap();
        assert!(blocked.is_none());

        let expected_bytes = b"safeclaw retried other scope\n";
        let retried = retry_worker
            .claim_and_retry_failed_once(
                "worker-c",
                27,
                "effect-worker-retry-other",
                PreflightDecision::Permit,
                |claim, runtime| {
                    assert_eq!(claim.task.task_id, "task-worker-retry-other");
                    assert_eq!(runtime.worker_state, WorkerState::Executing);
                    assert_eq!(runtime.effect.status, EffectStatus::Prepared);
                    Ok(sandbox_write_command(&other_output, expected_bytes))
                },
            )
            .unwrap()
            .expect("expired other-scope failed runtime must be reclaimable");

        assert_eq!(retried.claim.lease.owner_id, "worker-c");
        assert_eq!(retried.claim.lease.fencing_token, 2);
        assert_eq!(retried.final_summary.worker_state, WorkerState::Succeeded);
        assert_eq!(retried.final_summary.effect_status, EffectStatus::Executed);
        assert!(retried.completed);
        assert_eq!(fs::read(&other_output).unwrap(), expected_bytes);
        assert!(!shared_output.exists());
        assert_eq!(retry_worker.queue_snapshot().queued_tasks.len(), 1);
        assert_eq!(
            retry_worker.queue_snapshot().queued_tasks[0].task_id,
            "task-worker-retry-shared-queued"
        );
        assert_eq!(retry_worker.queue_snapshot().active_leases.len(), 1);
        assert_eq!(
            retry_worker.queue_snapshot().active_leases[0].task_id,
            "task-worker-retry-shared-blocking"
        );
        assert_eq!(
            retry_worker.queue_snapshot().completed_task_ids,
            vec![String::from("task-worker-retry-other")]
        );

        let verify_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let restored = verify_store
            .load_runtime("task-worker-retry-other", "effect-worker-retry-other")
            .unwrap()
            .expect("retried other-scope runtime must reload");
        assert_eq!(restored.worker_state, WorkerState::Succeeded);
        assert_eq!(restored.effect.status, EffectStatus::Executed);
        assert!(!restored.attempts.is_empty());
    }

    #[test]
    fn worker_loop_retry_claims_remaining_conflict_after_release() {
        let temp = TempWorkspace::new("retry-scope-release");
        let shared_output = temp.root.join("shared-output.txt");
        let other_output = temp.root.join("retry-output.txt");
        let shared_scope = format!("scope:{}", shared_output.display());
        let other_scope = format!("scope:{}", other_output.display());

        let mut blocking_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-retry-shared-blocking",
                ScheduleIntent::write(shared_scope.clone()),
                0,
            ))
            .unwrap();
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-retry-shared-queued",
                ScheduleIntent::write(shared_scope.clone()),
                1,
            ))
            .unwrap();
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-retry-other",
                ScheduleIntent::write(other_scope.clone()),
                2,
            ))
            .unwrap();

        let blocking_claim = blocking_orchestrator.claim_next("worker-a", 0).unwrap().unwrap();
        assert_eq!(blocking_claim.task.task_id, "task-worker-retry-shared-blocking");

        let first_retry_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        let first_retry_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut first_retry_worker =
            SqliteSingleWorkerLoop::new(first_retry_orchestrator, first_retry_store);

        let first_outcome = first_retry_worker
            .claim_and_drive_once("worker-b", 1, PreflightDecision::Permit, |claim| {
                assert_eq!(claim.task.task_id, "task-worker-retry-other");
                let effect = EffectRecord::new(
                    "effect-worker-retry-other",
                    claim.task.task_id.clone(),
                    "trace-worker-retry-other",
                    "intent-worker-retry-other",
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
            .expect("first retry worker must claim other-scope task");
        assert_eq!(first_outcome.final_summary.worker_state, WorkerState::Failed);

        let renewed_blocking_lease = blocking_orchestrator
            .renew_lease(
                &blocking_claim.task.task_id,
                &blocking_claim.lease.lease_id,
                &blocking_claim.lease.owner_id,
                20,
            )
            .unwrap();
        assert_eq!(renewed_blocking_lease.owner_id, "worker-a");

        let retry_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        let retry_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut retry_worker = SqliteSingleWorkerLoop::new(retry_orchestrator, retry_store);

        let expected_other_bytes = b"safeclaw retried other scope\n";
        let retried = retry_worker
            .claim_and_retry_failed_once(
                "worker-c",
                27,
                "effect-worker-retry-other",
                PreflightDecision::Permit,
                |claim, runtime| {
                    assert_eq!(claim.task.task_id, "task-worker-retry-other");
                    assert_eq!(runtime.worker_state, WorkerState::Executing);
                    Ok(sandbox_write_command(&other_output, expected_other_bytes))
                },
            )
            .unwrap()
            .expect("expired other-scope failed runtime must be reclaimable");
        assert!(retried.completed);
        assert_eq!(fs::read(&other_output).unwrap(), expected_other_bytes);
        assert_eq!(retry_worker.queue_snapshot().queued_tasks.len(), 1);
        assert_eq!(
            retry_worker.queue_snapshot().queued_tasks[0].task_id,
            "task-worker-retry-shared-queued"
        );

        blocking_orchestrator
            .complete(
                &blocking_claim.task.task_id,
                &blocking_claim.lease.lease_id,
                &blocking_claim.lease.owner_id,
            )
            .unwrap();

        let release_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        let release_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut release_worker = SqliteSingleWorkerLoop::new(release_orchestrator, release_store);

        let expected_shared_bytes = b"safeclaw shared after retry release\n";
        let released = release_worker
            .claim_and_drive_once("worker-d", 28, PreflightDecision::Permit, |claim| {
                assert_eq!(claim.task.task_id, "task-worker-retry-shared-queued");
                let effect = EffectRecord::new(
                    "effect-worker-retry-shared-queued",
                    claim.task.task_id.clone(),
                    "trace-worker-retry-shared-queued",
                    "intent-worker-retry-shared-queued",
                    EffectActor::Worker,
                    EffectAction::FileWrite,
                    claim.task.intent.target_scope.clone(),
                    EffectTier::Tier1,
                    EffectReversibility::Rollbackable,
                    ProbeMode::Auto,
                );
                Ok((
                    InMemoryTaskRuntime::new(effect),
                    sandbox_write_command(&shared_output, expected_shared_bytes),
                ))
            })
            .unwrap()
            .expect("shared queued task must unblock after lease release");

        assert_eq!(released.claim.lease.owner_id, "worker-d");
        assert!(released.completed);
        assert_eq!(released.final_summary.worker_state, WorkerState::Succeeded);
        assert_eq!(released.final_summary.effect_status, EffectStatus::Executed);
        assert_eq!(fs::read(&shared_output).unwrap(), expected_shared_bytes);
        assert!(release_worker.queue_snapshot().queued_tasks.is_empty());
        assert!(release_worker.queue_snapshot().active_leases.is_empty());
        assert_eq!(
            release_worker.queue_snapshot().completed_task_ids,
            vec![
                String::from("task-worker-retry-other"),
                String::from("task-worker-retry-shared-blocking"),
                String::from("task-worker-retry-shared-queued"),
            ]
        );

        let verify_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let restored = verify_store
            .load_runtime(
                "task-worker-retry-shared-queued",
                "effect-worker-retry-shared-queued",
            )
            .unwrap()
            .expect("released shared runtime must reload");
        assert_eq!(restored.worker_state, WorkerState::Succeeded);
        assert_eq!(restored.effect.status, EffectStatus::Executed);
    }

    #[test]
    fn worker_loop_resume_skips_conflicting_scope_held_by_other_owner() {
        let temp = TempWorkspace::new("resume-scope-skip");
        let shared_output = temp.root.join("shared-output.txt");
        let other_output = temp.root.join("resume-output.txt");
        let shared_scope = format!("scope:{}", shared_output.display());
        let other_scope = format!("scope:{}", other_output.display());

        let mut blocking_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-shared-blocking",
                ScheduleIntent::write(shared_scope.clone()),
                0,
            ))
            .unwrap();
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-shared-queued",
                ScheduleIntent::write(shared_scope.clone()),
                1,
            ))
            .unwrap();
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-resume-other",
                ScheduleIntent::write(other_scope.clone()),
                2,
            ))
            .unwrap();

        let blocking_claim = blocking_orchestrator.claim_next("worker-a", 0).unwrap().unwrap();
        assert_eq!(blocking_claim.task.task_id, "task-worker-shared-blocking");

        let first_resume_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        let first_resume_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut first_resume_worker =
            SqliteSingleWorkerLoop::new(first_resume_orchestrator, first_resume_store);

        let error = first_resume_worker
            .claim_and_drive_once("worker-b", 1, PreflightDecision::Permit, |claim| {
                assert_eq!(claim.task.task_id, "task-worker-resume-other");
                let effect = EffectRecord::new(
                    "effect-worker-resume-other",
                    claim.task.task_id.clone(),
                    "trace-worker-resume-other",
                    "intent-worker-resume-other",
                    EffectActor::Worker,
                    EffectAction::FileWrite,
                    claim.task.intent.target_scope.clone(),
                    EffectTier::Tier1,
                    EffectReversibility::Rollbackable,
                    ProbeMode::Auto,
                );
                Ok((
                    InMemoryTaskRuntime::new(effect),
                    sandbox_missing_program_command(),
                ))
            })
            .unwrap_err();
        assert!(matches!(error, WorkerLoopError::Sandbox(_)));
        assert_eq!(first_resume_worker.queue_snapshot().queued_tasks.len(), 1);
        assert_eq!(
            first_resume_worker.queue_snapshot().queued_tasks[0].task_id,
            "task-worker-shared-queued"
        );
        assert_eq!(first_resume_worker.queue_snapshot().active_leases.len(), 2);

        let renewed_blocking_lease = blocking_orchestrator
            .renew_lease(
                &blocking_claim.task.task_id,
                &blocking_claim.lease.lease_id,
                &blocking_claim.lease.owner_id,
                20,
            )
            .unwrap();
        assert_eq!(renewed_blocking_lease.owner_id, "worker-a");

        let resume_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        let resume_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut resume_worker = SqliteSingleWorkerLoop::new(resume_orchestrator, resume_store);

        let blocked = resume_worker
            .claim_and_resume_once("worker-c", 10, |_| unreachable!())
            .unwrap();
        assert!(blocked.is_none());

        let expected_bytes = b"safeclaw resumed other scope\n";
        let resumed = resume_worker
            .claim_and_resume_persisted_once(
                "worker-c",
                27,
                "effect-worker-resume-other",
                |claim, runtime| {
                    assert_eq!(claim.task.task_id, "task-worker-resume-other");
                    assert_eq!(runtime.worker_state, WorkerState::Executing);
                    assert_eq!(runtime.effect.status, EffectStatus::Prepared);
                    Ok(sandbox_write_command(&other_output, expected_bytes))
                },
            )
            .unwrap()
            .expect("expired other-scope persisted runtime must be reclaimable");

        assert_eq!(resumed.claim.lease.owner_id, "worker-c");
        assert_eq!(resumed.claim.lease.fencing_token, 2);
        assert_eq!(resumed.final_summary.worker_state, WorkerState::Succeeded);
        assert_eq!(resumed.final_summary.effect_status, EffectStatus::Executed);
        assert!(resumed.completed);
        assert_eq!(fs::read(&other_output).unwrap(), expected_bytes);
        assert!(!shared_output.exists());
        assert_eq!(resume_worker.queue_snapshot().queued_tasks.len(), 1);
        assert_eq!(
            resume_worker.queue_snapshot().queued_tasks[0].task_id,
            "task-worker-shared-queued"
        );
        assert_eq!(resume_worker.queue_snapshot().active_leases.len(), 1);
        assert_eq!(
            resume_worker.queue_snapshot().active_leases[0].task_id,
            "task-worker-shared-blocking"
        );
        assert_eq!(
            resume_worker.queue_snapshot().completed_task_ids,
            vec![String::from("task-worker-resume-other")]
        );

        let verify_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let restored = verify_store
            .load_runtime("task-worker-resume-other", "effect-worker-resume-other")
            .unwrap()
            .expect("resumed other-scope runtime must reload");
        assert_eq!(restored.worker_state, WorkerState::Succeeded);
        assert_eq!(restored.effect.status, EffectStatus::Executed);
        assert!(!restored.attempts.is_empty());
    }

    #[test]
    fn worker_loop_resume_claims_remaining_conflict_after_release() {
        let temp = TempWorkspace::new("resume-release");
        let shared_output = temp.root.join("shared-output.txt");
        let other_output = temp.root.join("resume-output.txt");
        let shared_scope = format!("scope:{}", shared_output.display());
        let other_scope = format!("scope:{}", other_output.display());

        let mut blocking_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-resume-shared-blocking",
                ScheduleIntent::write(shared_scope.clone()),
                0,
            ))
            .unwrap();
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-resume-shared-queued",
                ScheduleIntent::write(shared_scope.clone()),
                1,
            ))
            .unwrap();
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-resume-other",
                ScheduleIntent::write(other_scope.clone()),
                2,
            ))
            .unwrap();

        let blocking_claim = blocking_orchestrator.claim_next("worker-a", 0).unwrap().unwrap();
        assert_eq!(blocking_claim.task.task_id, "task-worker-resume-shared-blocking");

        let first_resume_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        let first_resume_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut first_resume_worker =
            SqliteSingleWorkerLoop::new(first_resume_orchestrator, first_resume_store);

        let error = first_resume_worker
            .claim_and_drive_once("worker-b", 1, PreflightDecision::Permit, |claim| {
                assert_eq!(claim.task.task_id, "task-worker-resume-other");
                let effect = EffectRecord::new(
                    "effect-worker-resume-other",
                    claim.task.task_id.clone(),
                    "trace-worker-resume-other",
                    "intent-worker-resume-other",
                    EffectActor::Worker,
                    EffectAction::FileWrite,
                    claim.task.intent.target_scope.clone(),
                    EffectTier::Tier1,
                    EffectReversibility::Rollbackable,
                    ProbeMode::Auto,
                );
                Ok((
                    InMemoryTaskRuntime::new(effect),
                    sandbox_missing_program_command(),
                ))
            })
            .unwrap_err();
        assert!(matches!(error, WorkerLoopError::Sandbox(_)));
        assert_eq!(first_resume_worker.queue_snapshot().queued_tasks.len(), 1);
        assert_eq!(
            first_resume_worker.queue_snapshot().queued_tasks[0].task_id,
            "task-worker-resume-shared-queued"
        );

        let renewed_blocking_lease = blocking_orchestrator
            .renew_lease(
                &blocking_claim.task.task_id,
                &blocking_claim.lease.lease_id,
                &blocking_claim.lease.owner_id,
                20,
            )
            .unwrap();
        assert_eq!(renewed_blocking_lease.owner_id, "worker-a");

        let resume_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        let resume_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut resume_worker = SqliteSingleWorkerLoop::new(resume_orchestrator, resume_store);

        let expected_other_bytes = b"safeclaw resumed other scope\n";
        let resumed = resume_worker
            .claim_and_resume_persisted_once(
                "worker-c",
                27,
                "effect-worker-resume-other",
                |claim, runtime| {
                    assert_eq!(claim.task.task_id, "task-worker-resume-other");
                    assert_eq!(runtime.worker_state, WorkerState::Executing);
                    assert_eq!(runtime.effect.status, EffectStatus::Prepared);
                    Ok(sandbox_write_command(&other_output, expected_other_bytes))
                },
            )
            .unwrap()
            .expect("expired other-scope persisted runtime must be reclaimable");

        assert_eq!(resumed.claim.lease.owner_id, "worker-c");
        assert_eq!(resumed.claim.lease.fencing_token, 2);
        assert_eq!(resumed.final_summary.worker_state, WorkerState::Succeeded);
        assert_eq!(resumed.final_summary.effect_status, EffectStatus::Executed);
        assert!(resumed.completed);
        assert_eq!(fs::read(&other_output).unwrap(), expected_other_bytes);
        assert!(!shared_output.exists());
        assert_eq!(resume_worker.queue_snapshot().queued_tasks.len(), 1);
        assert_eq!(
            resume_worker.queue_snapshot().queued_tasks[0].task_id,
            "task-worker-resume-shared-queued"
        );

        blocking_orchestrator
            .complete(
                &blocking_claim.task.task_id,
                &blocking_claim.lease.lease_id,
                &blocking_claim.lease.owner_id,
            )
            .unwrap();

        let release_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        let release_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut release_worker = SqliteSingleWorkerLoop::new(release_orchestrator, release_store);

        let expected_shared_bytes = b"safeclaw shared after resume release\n";
        let released = release_worker
            .claim_and_drive_once("worker-d", 28, PreflightDecision::Permit, |claim| {
                assert_eq!(claim.task.task_id, "task-worker-resume-shared-queued");
                let effect = EffectRecord::new(
                    "effect-worker-resume-shared-queued",
                    claim.task.task_id.clone(),
                    "trace-worker-resume-shared-queued",
                    "intent-worker-resume-shared-queued",
                    EffectActor::Worker,
                    EffectAction::FileWrite,
                    claim.task.intent.target_scope.clone(),
                    EffectTier::Tier1,
                    EffectReversibility::Rollbackable,
                    ProbeMode::Auto,
                );
                Ok((
                    InMemoryTaskRuntime::new(effect),
                    sandbox_write_command(&shared_output, expected_shared_bytes),
                ))
            })
            .unwrap()
            .expect("shared queued task must unblock after resume lease release");

        assert_eq!(released.claim.lease.owner_id, "worker-d");
        assert!(released.completed);
        assert_eq!(released.final_summary.worker_state, WorkerState::Succeeded);
        assert_eq!(released.final_summary.effect_status, EffectStatus::Executed);
        assert_eq!(fs::read(&shared_output).unwrap(), expected_shared_bytes);
        assert!(release_worker.queue_snapshot().queued_tasks.is_empty());
        assert!(release_worker.queue_snapshot().active_leases.is_empty());
        assert_eq!(
            release_worker.queue_snapshot().completed_task_ids,
            vec![
                String::from("task-worker-resume-other"),
                String::from("task-worker-resume-shared-blocking"),
                String::from("task-worker-resume-shared-queued"),
            ]
        );

        let verify_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let restored = verify_store
            .load_runtime(
                "task-worker-resume-shared-queued",
                "effect-worker-resume-shared-queued",
            )
            .unwrap()
            .expect("released shared runtime must reload");
        assert_eq!(restored.worker_state, WorkerState::Succeeded);
        assert_eq!(restored.effect.status, EffectStatus::Executed);
    }

    #[test]
    fn worker_loop_claims_probes_and_completes_uncertain_network_request_task() {
        let server = TestHttpServer::spawn(
            "HTTP/1.1 200 OK\r\nContent-Length: 14\r\nConnection: close\r\n\r\nstatus=applied",
            0,
        );
        let temp = TempWorkspace::new("network-loop");
        let mut orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-network",
                ScheduleIntent::read(server.target()),
                0,
            ))
            .unwrap();
        let runtime_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut loop_driver = SqliteSingleWorkerLoop::new(orchestrator, runtime_store);
        loop_driver.network_probe_mut().register_expected_response(
            String::from("effect-worker-network"),
            "status=applied",
        );

        let timeout_bytes = b"safeclaw network timeout\n";
        let outcome = loop_driver
            .claim_and_drive_once("worker-a", 0, PreflightDecision::Permit, |claim| {
                let effect = EffectRecord::new(
                    "effect-worker-network",
                    claim.task.task_id.clone(),
                    "trace-worker-network",
                    "intent-worker-network",
                    EffectActor::Worker,
                    EffectAction::NetworkRequest,
                    claim.task.intent.target_scope.clone(),
                    EffectTier::Tier1,
                    EffectReversibility::Rollbackable,
                    ProbeMode::Auto,
                );
                Ok((
                    InMemoryTaskRuntime::new(effect),
                    sandbox_write_then_timeout_command(&temp.output_path, timeout_bytes),
                ))
            })
            .unwrap()
            .expect("network task must be claimable");

        assert_eq!(outcome.claim.lease.owner_id, "worker-a");
        assert_eq!(outcome.execution_summary.worker_state, WorkerState::Uncertain);
        assert_eq!(outcome.execution_summary.effect_status, EffectStatus::Uncertain);
        assert_eq!(outcome.final_summary.worker_state, WorkerState::Succeeded);
        assert_eq!(outcome.final_summary.effect_status, EffectStatus::Executed);
        assert!(outcome.completed);
        assert_eq!(fs::read(&temp.output_path).unwrap(), timeout_bytes);
        assert!(loop_driver.queue_snapshot().active_leases.is_empty());
        assert_eq!(
            loop_driver.queue_snapshot().completed_task_ids,
            vec![String::from("task-worker-network")]
        );

        let verify_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let restored = verify_store
            .load_runtime("task-worker-network", "effect-worker-network")
            .unwrap()
            .expect("network runtime must reload");
        assert_eq!(restored.worker_state, WorkerState::Succeeded);
        assert_eq!(restored.effect.status, EffectStatus::Executed);
        assert_eq!(restored.attempts.len(), 1);
    }

    struct TestHttpServer {
        target: String,
        handle: Option<thread::JoinHandle<()>>,
    }

    impl TestHttpServer {
        fn spawn(response: &str, delay_ms: u64) -> Self {
            let listener = TcpListener::bind("127.0.0.1:0").unwrap();
            let addr = listener.local_addr().unwrap();
            let response = response.to_string();
            let handle = thread::spawn(move || {
                let (mut stream, _) = listener.accept().unwrap();
                let mut buffer = [0_u8; 1024];
                let _ = stream.read(&mut buffer);
                if delay_ms > 0 {
                    thread::sleep(Duration::from_millis(delay_ms));
                }
                let _ = stream.write_all(response.as_bytes());
            });
            Self {
                target: format!("scope:http://{addr}/status"),
                handle: Some(handle),
            }
        }

        fn target(&self) -> String {
            self.target.clone()
        }
    }

    impl Drop for TestHttpServer {
        fn drop(&mut self) {
            if let Some(handle) = self.handle.take() {
                let _ = handle.join();
            }
        }
    }

    fn sandbox_success_command() -> SandboxCommand {
        if cfg!(windows) {
            SandboxCommand::new("powershell", ["-Command", "Write-Output 'ok'"], 5_000)
        } else {
            SandboxCommand::new("sh", ["-c", "printf '%s' ok"], 5_000)
        }
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
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    &format!(
                        "$bytes = [byte[]]({bytes_literal}); [System.IO.File]::WriteAllBytes('{}', $bytes); Start-Sleep -Milliseconds 3000",
                        output_path.display()
                    ),
                ],
                1_500,
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
