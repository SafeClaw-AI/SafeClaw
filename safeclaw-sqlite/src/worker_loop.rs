use std::path::Path;

use crate::{
    open_database, FileSystemProbeAdapter, LocalSandboxExecutor, NetworkProbeAdapter,
    RuntimeDiagnosticSnapshot, RuntimeGovernanceSummary, RuntimeGovernanceView,
    SandboxCommand, SandboxExecutionReport, SandboxRuntimeError, SqliteAdapterError,
    SqliteOpenOptions, SqliteRuntimeStore, SqliteTaskOrchestrator,
};
use safeclaw_core::{
    effect_ledger::{EffectAction, EffectAttempt, EffectTransitionRecord},
    recovery::probes::ProbeAdapterError,
    scheduler::{
        OrchestratorClaim, OrchestratorError, OrchestratorSnapshot, OrchestratorTask,
        TaskOrchestrator,
    },
    state_engine::StateEvent,
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
    pub effect_id: String,
    pub report: SandboxExecutionReport,
    pub execution_summary: RunSummary,
    pub final_summary: RunSummary,
    pub completed: bool,
    pub disposition: Option<WorkerLoopDisposition>,
}

#[derive(Clone, Debug)]
pub struct WorkerLoopProbeOutcome {
    pub claim: OrchestratorClaim,
    pub effect_id: String,
    pub recovered_from: WorkerState,
    pub final_summary: RunSummary,
    pub completed: bool,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum WorkerLoopDisposition {
    QueueForConfirmation,
    ParkedUnsupported,
}

#[derive(Clone, Debug)]
pub struct WorkerLoopParkedOutcome {
    pub claim: OrchestratorClaim,
    pub effect_id: String,
    pub summary: RunSummary,
    pub disposition: WorkerLoopDisposition,
    pub completed: bool,
}

#[derive(Clone, Debug)]
pub enum WorkerLoopDispatchOutcome {
    Executed(WorkerLoopOutcome),
    Probed(WorkerLoopProbeOutcome),
    Parked(WorkerLoopParkedOutcome),
}

impl WorkerLoopDispatchOutcome {
    pub fn task_id(&self) -> &str {
        match self {
            WorkerLoopDispatchOutcome::Executed(outcome) => &outcome.claim.task.task_id,
            WorkerLoopDispatchOutcome::Probed(outcome) => &outcome.claim.task.task_id,
            WorkerLoopDispatchOutcome::Parked(outcome) => &outcome.claim.task.task_id,
        }
    }

    pub fn effect_id(&self) -> &str {
        match self {
            WorkerLoopDispatchOutcome::Executed(outcome) => &outcome.effect_id,
            WorkerLoopDispatchOutcome::Probed(outcome) => &outcome.effect_id,
            WorkerLoopDispatchOutcome::Parked(outcome) => &outcome.effect_id,
        }
    }
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

    pub fn governance_view(
        &self,
        task_id: &str,
        effect_id: &str,
    ) -> Result<Option<RuntimeGovernanceView>, WorkerLoopError> {
        self.runtime_store
            .governance_view(task_id, effect_id)
            .map_err(WorkerLoopError::Store)
    }

    pub fn diagnostic_snapshot(
        &self,
        task_id: &str,
        effect_id: &str,
    ) -> Result<Option<RuntimeDiagnosticSnapshot>, WorkerLoopError> {
        self.runtime_store
            .diagnostic_snapshot(task_id, effect_id)
            .map_err(WorkerLoopError::Store)
    }

    pub fn diagnostic_snapshots_for_outcomes(
        &self,
        outcomes: &[WorkerLoopDispatchOutcome],
    ) -> Result<Vec<RuntimeDiagnosticSnapshot>, WorkerLoopError> {
        outcomes
            .iter()
            .map(|outcome| {
                let task_id = outcome.task_id();
                let effect_id = outcome.effect_id();
                self.diagnostic_snapshot(task_id, effect_id)?.ok_or_else(|| {
                    WorkerLoopError::PersistedRuntimeMissing {
                        task_id: task_id.to_string(),
                        effect_id: effect_id.to_string(),
                    }
                })
            })
            .collect()
    }

    pub fn governance_summary_for_outcomes(
        &self,
        outcomes: &[WorkerLoopDispatchOutcome],
    ) -> Result<RuntimeGovernanceSummary, WorkerLoopError> {
        let snapshots = self.diagnostic_snapshots_for_outcomes(outcomes)?;
        Ok(RuntimeGovernanceSummary::from_snapshots(&snapshots))
    }

    pub fn list_attempts(&self, effect_id: &str) -> Result<Vec<EffectAttempt>, WorkerLoopError> {
        self.runtime_store
            .list_attempts(effect_id)
            .map_err(WorkerLoopError::Store)
    }

    pub fn list_state_events(&self, task_id: &str) -> Result<Vec<StateEvent>, WorkerLoopError> {
        self.runtime_store
            .list_state_events(task_id)
            .map_err(WorkerLoopError::Store)
    }

    pub fn list_effect_transitions(
        &self,
        effect_id: &str,
    ) -> Result<Vec<EffectTransitionRecord>, WorkerLoopError> {
        self.runtime_store
            .list_effect_transitions(effect_id)
            .map_err(WorkerLoopError::Store)
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
        let summary = runtime
            .begin_execution(preflight)
            .map_err(WorkerLoopError::Runtime)?;
        self.persist_runtime(&runtime, &claim, "pre-exec")?;
        if let Some(disposition) = parked_disposition_for_summary(&summary) {
            return Ok(Some(Self::parked_drive_outcome(
                claim,
                runtime.effect.effect_id.clone(),
                summary,
                disposition,
            )));
        }

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
            let summary = runtime
                .begin_execution(preflight)
                .map_err(WorkerLoopError::Runtime)?;
            self.persist_runtime(&runtime, &claim, "pre-exec")?;
            if let Some(disposition) = parked_disposition_for_summary(&summary) {
                outcomes.push(Self::parked_drive_outcome(
                    claim,
                    runtime.effect.effect_id.clone(),
                    summary,
                    disposition,
                ));
                continue;
            }
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
        let summary = runtime_summary(&runtime);
        if let Some(disposition) = parked_disposition_for_summary(&summary) {
            self.persist_runtime(&runtime, &claim, "pre-resume")?;
            return Ok(Some(Self::parked_drive_outcome(
                claim,
                runtime.effect.effect_id.clone(),
                summary,
                disposition,
            )));
        }
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
        let summary = runtime_summary(&runtime);
        if let Some(disposition) = parked_disposition_for_summary(&summary) {
            self.persist_runtime(&runtime, &claim, "pre-resume")?;
            return Ok(Some(Self::parked_drive_outcome(
                claim,
                runtime.effect.effect_id.clone(),
                summary,
                disposition,
            )));
        }
        let command = build_command(&claim, &runtime)?;
        self.drive_claimed_runtime(claim, runtime, command).map(Some)
    }

    pub fn claim_and_probe_persisted_once(
        &mut self,
        owner_id: &str,
        now_ms: u64,
        effect_id: &str,
    ) -> Result<Option<WorkerLoopProbeOutcome>, WorkerLoopError> {
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
        let recovered_from = runtime.worker_state;
        let final_summary = self.recover_uncertain(&mut runtime, &claim)?;

        let mut completed = false;
        if final_summary.worker_state == WorkerState::Succeeded {
            self.orchestrator
                .complete(&claim.task.task_id, &claim.lease.lease_id, &claim.lease.owner_id)
                .map_err(WorkerLoopError::Orchestrator)?;
            completed = true;
        }

        Ok(Some(WorkerLoopProbeOutcome {
            claim,
            effect_id: runtime.effect.effect_id.clone(),
            recovered_from,
            final_summary,
            completed,
        }))
    }

    pub fn claim_and_dispatch_once<F, P>(
        &mut self,
        owner_id: &str,
        now_ms: u64,
        effect_id: &str,
        preflight: PreflightDecision,
        build_fresh: F,
        build_persisted_command: P,
    ) -> Result<Option<WorkerLoopDispatchOutcome>, WorkerLoopError>
    where
        F: FnOnce(&OrchestratorClaim) -> Result<(InMemoryTaskRuntime, SandboxCommand), WorkerLoopError>,
        P: FnOnce(&OrchestratorClaim, &InMemoryTaskRuntime) -> Result<SandboxCommand, WorkerLoopError>,
    {
        let Some(claim) = self.claim_once(owner_id, now_ms)? else {
            return Ok(None);
        };

        self.dispatch_claimed(
            claim,
            effect_id,
            preflight,
            build_fresh,
            build_persisted_command,
        )
        .map(Some)
    }

    pub fn claim_and_dispatch_until_empty<I, F, P>(
        &mut self,
        owner_id: &str,
        now_ms: u64,
        preflight: PreflightDecision,
        mut resolve_effect_id: I,
        mut build_fresh: F,
        mut build_persisted_command: P,
    ) -> Result<Vec<WorkerLoopDispatchOutcome>, WorkerLoopError>
    where
        I: FnMut(&OrchestratorClaim) -> Result<String, WorkerLoopError>,
        F: FnMut(&OrchestratorClaim) -> Result<(InMemoryTaskRuntime, SandboxCommand), WorkerLoopError>,
        P: FnMut(&OrchestratorClaim, &InMemoryTaskRuntime) -> Result<SandboxCommand, WorkerLoopError>,
    {
        let mut outcomes = Vec::new();
        loop {
            let Some(claim) = self.claim_once(owner_id, now_ms)? else {
                break;
            };
            let effect_id = resolve_effect_id(&claim)?;
            let outcome = self.dispatch_claimed(
                claim,
                &effect_id,
                preflight,
                |claim| build_fresh(claim),
                |claim, runtime| build_persisted_command(claim, runtime),
            )?;
            outcomes.push(outcome);
        }
        Ok(outcomes)
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
        let summary = runtime
            .retry_failed(preflight)
            .map_err(WorkerLoopError::Runtime)?;
        self.persist_runtime(&runtime, &claim, "pre-exec")?;
        if let Some(disposition) = parked_disposition_for_summary(&summary) {
            return Ok(Some(Self::parked_drive_outcome(
                claim,
                runtime.effect.effect_id.clone(),
                summary,
                disposition,
            )));
        }
        let command = build_command(&claim, &runtime)?;
        self.drive_claimed_runtime(claim, runtime, command).map(Some)
    }

    fn dispatch_claimed<F, P>(
        &mut self,
        claim: OrchestratorClaim,
        effect_id: &str,
        preflight: PreflightDecision,
        build_fresh: F,
        build_persisted_command: P,
    ) -> Result<WorkerLoopDispatchOutcome, WorkerLoopError>
    where
        F: FnOnce(&OrchestratorClaim) -> Result<(InMemoryTaskRuntime, SandboxCommand), WorkerLoopError>,
        P: FnOnce(&OrchestratorClaim, &InMemoryTaskRuntime) -> Result<SandboxCommand, WorkerLoopError>,
    {
        let runtime = self
            .runtime_store
            .load_runtime(&claim.task.task_id, effect_id)
            .map_err(WorkerLoopError::Store)?;

        match runtime {
            None => {
                let (mut runtime, command) = build_fresh(&claim)?;
                let summary = runtime
                    .begin_execution(preflight)
                    .map_err(WorkerLoopError::Runtime)?;
                self.persist_runtime(&runtime, &claim, "pre-exec")?;
                if let Some(disposition) = parked_disposition_for_summary(&summary) {
                    return Ok(Self::parked_outcome(
                        claim,
                        runtime.effect.effect_id.clone(),
                        summary,
                        disposition,
                    ));
                }
                self.drive_claimed_runtime(claim, runtime, command)
                    .map(WorkerLoopDispatchOutcome::Executed)
            }
            Some(mut runtime) => match runtime.worker_state {
                WorkerState::Failed => {
                    let summary = runtime
                        .retry_failed(preflight)
                        .map_err(WorkerLoopError::Runtime)?;
                    self.persist_runtime(&runtime, &claim, "pre-exec")?;
                    if let Some(disposition) = parked_disposition_for_summary(&summary) {
                        return Ok(Self::parked_outcome(
                            claim,
                            runtime.effect.effect_id.clone(),
                            summary,
                            disposition,
                        ));
                    }
                    let command = build_persisted_command(&claim, &runtime)?;
                    self.drive_claimed_runtime(claim, runtime, command)
                        .map(WorkerLoopDispatchOutcome::Executed)
                }
                WorkerState::Executing => {
                    let command = build_persisted_command(&claim, &runtime)?;
                    self.drive_claimed_runtime(claim, runtime, command)
                        .map(WorkerLoopDispatchOutcome::Executed)
                }
                WorkerState::Uncertain => {
                    let recovered_from = runtime.worker_state;
                    let final_summary = self.recover_uncertain(&mut runtime, &claim)?;
                    let mut completed = false;
                    if final_summary.worker_state == WorkerState::Succeeded {
                        self.orchestrator
                            .complete(
                                &claim.task.task_id,
                                &claim.lease.lease_id,
                                &claim.lease.owner_id,
                            )
                            .map_err(WorkerLoopError::Orchestrator)?;
                        completed = true;
                    }
                    Ok(WorkerLoopDispatchOutcome::Probed(WorkerLoopProbeOutcome {
                        claim,
                        effect_id: runtime.effect.effect_id.clone(),
                        recovered_from,
                        final_summary,
                        completed,
                    }))
                }
                _ => Ok(Self::parked_outcome(
                    claim,
                    runtime.effect.effect_id.clone(),
                    runtime_summary(&runtime),
                    WorkerLoopDisposition::ParkedUnsupported,
                )),
            },
        }
    }

    fn parked_outcome(
        claim: OrchestratorClaim,
        effect_id: String,
        summary: RunSummary,
        disposition: WorkerLoopDisposition,
    ) -> WorkerLoopDispatchOutcome {
        WorkerLoopDispatchOutcome::Parked(WorkerLoopParkedOutcome {
            claim,
            effect_id,
            summary,
            disposition,
            completed: false,
        })
    }

    fn parked_drive_outcome(
        claim: OrchestratorClaim,
        effect_id: String,
        summary: RunSummary,
        disposition: WorkerLoopDisposition,
    ) -> WorkerLoopOutcome {
        WorkerLoopOutcome {
            claim,
            effect_id,
            report: empty_sandbox_report(),
            execution_summary: summary.clone(),
            final_summary: summary,
            completed: false,
            disposition: Some(disposition),
        }
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
        let effect_id = runtime.effect.effect_id.clone();
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
            effect_id,
            report,
            execution_summary,
            final_summary,
            completed,
            disposition: None,
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

fn empty_sandbox_report() -> SandboxExecutionReport {
    SandboxExecutionReport {
        exit_code: None,
        stdout: String::new(),
        stderr: String::new(),
        timed_out: false,
        duration_ms: 0,
    }
}

fn parked_disposition_for_summary(summary: &RunSummary) -> Option<WorkerLoopDisposition> {
    match summary.worker_state {
        WorkerState::AwaitingConfirmation => Some(WorkerLoopDisposition::QueueForConfirmation),
        WorkerState::Created
        | WorkerState::Planning
        | WorkerState::Hibernated
        | WorkerState::Committing
        | WorkerState::RollingBack
        | WorkerState::RolledBack
        | WorkerState::AwaitingDoctor
        | WorkerState::Repairing
        | WorkerState::Repaired
        | WorkerState::RepairFailed
        | WorkerState::FailedTerminal
        | WorkerState::Closed => Some(WorkerLoopDisposition::ParkedUnsupported),
        WorkerState::Executing | WorkerState::Uncertain | WorkerState::Succeeded | WorkerState::Failed => {
            None
        }
    }
}

fn runtime_summary(runtime: &InMemoryTaskRuntime) -> RunSummary {
    RunSummary {
        worker_state: runtime.worker_state,
        effect_status: runtime.effect.status,
        attempt_count: runtime.attempts.len(),
        compensation_count: runtime.compensation_effects.len(),
        quarantined_scopes: runtime.quarantined_scopes.clone(),
    }
}

#[cfg(test)]
mod tests {
    use super::{
        SqliteSingleWorkerLoop, WorkerLoopDispatchOutcome, WorkerLoopDisposition,
        WorkerLoopError,
    };
    use crate::{
        open_database, LocalSandboxExecutor, RuntimeGovernanceDisposition, SandboxCommand,
        SqliteOpenOptions, SqliteRuntimeStore, SqliteTaskOrchestrator,
    };
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
    fn worker_loop_governance_view_returns_none_when_runtime_is_missing() {
        let temp = TempWorkspace::new("governance-view-missing");
        let loop_driver = SqliteSingleWorkerLoop::open(&temp.db_path, SqliteOpenOptions::default())
            .unwrap();

        let view = loop_driver
            .governance_view("task-worker-governance-missing", "effect-worker-governance-missing")
            .unwrap();

        assert!(view.is_none());
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
    fn worker_loop_drive_parks_confirmation_before_sandbox() {
        let temp = TempWorkspace::new("drive-confirmation");
        let mut loop_driver = SqliteSingleWorkerLoop::open(
            &temp.db_path,
            SqliteOpenOptions::default(),
        )
        .unwrap()
        .with_lease_ttl_ms(25);
        loop_driver
            .enqueue_task(OrchestratorTask::new(
                "task-worker-drive-confirmation",
                ScheduleIntent::write(format!("scope:{}", temp.output_path.display())),
                0,
            ))
            .unwrap();

        let outcome = loop_driver
            .claim_and_drive_once("worker-a", 0, PreflightDecision::NeedsConfirmation, |claim| {
                let effect = EffectRecord::new(
                    "effect-worker-drive-confirmation",
                    claim.task.task_id.clone(),
                    "trace-worker-drive-confirmation",
                    "intent-worker-drive-confirmation",
                    EffectActor::Worker,
                    EffectAction::FileWrite,
                    claim.task.intent.target_scope.clone(),
                    EffectTier::Tier1,
                    EffectReversibility::Rollbackable,
                    ProbeMode::Auto,
                );
                Ok((InMemoryTaskRuntime::new(effect), sandbox_success_command()))
            })
            .unwrap()
            .expect("confirmation drive must claim task");

        assert_eq!(outcome.execution_summary.worker_state, WorkerState::AwaitingConfirmation);
        assert_eq!(outcome.execution_summary.effect_status, EffectStatus::Prepared);
        assert_eq!(outcome.final_summary.worker_state, WorkerState::AwaitingConfirmation);
        assert_eq!(outcome.final_summary.effect_status, EffectStatus::Prepared);
        assert_eq!(outcome.disposition, Some(WorkerLoopDisposition::QueueForConfirmation));
        assert!(!outcome.completed);
        assert_eq!(outcome.report.exit_code, None);
        assert!(!outcome.report.timed_out);
        assert_eq!(outcome.report.duration_ms, 0);
        assert!(!temp.output_path.exists());
        assert_eq!(loop_driver.queue_snapshot().active_leases.len(), 1);

        let verify_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let restored = verify_store
            .load_runtime("task-worker-drive-confirmation", "effect-worker-drive-confirmation")
            .unwrap()
            .expect("confirmation drive runtime must persist");
        assert_eq!(restored.worker_state, WorkerState::AwaitingConfirmation);
        assert_eq!(restored.effect.status, EffectStatus::Prepared);
        assert!(restored.attempts.is_empty());
    }

    #[test]
    fn worker_loop_governance_view_surfaces_confirmation_runtime() {
        let temp = TempWorkspace::new("governance-view-confirmation");
        let mut loop_driver = SqliteSingleWorkerLoop::open(
            &temp.db_path,
            SqliteOpenOptions::default(),
        )
        .unwrap()
        .with_lease_ttl_ms(25);
        loop_driver
            .enqueue_task(OrchestratorTask::new(
                "task-worker-governance-confirmation",
                ScheduleIntent::write(format!("scope:{}", temp.output_path.display())),
                0,
            ))
            .unwrap();

        let outcome = loop_driver
            .claim_and_drive_once("worker-a", 0, PreflightDecision::NeedsConfirmation, |claim| {
                let effect = EffectRecord::new(
                    "effect-worker-governance-confirmation",
                    claim.task.task_id.clone(),
                    "trace-worker-governance-confirmation",
                    "intent-worker-governance-confirmation",
                    EffectActor::Worker,
                    EffectAction::FileWrite,
                    claim.task.intent.target_scope.clone(),
                    EffectTier::Tier1,
                    EffectReversibility::Rollbackable,
                    ProbeMode::Auto,
                );
                Ok((InMemoryTaskRuntime::new(effect), sandbox_success_command()))
            })
            .unwrap()
            .expect("governance confirmation run must claim task");

        assert_eq!(
            outcome.disposition,
            Some(WorkerLoopDisposition::QueueForConfirmation)
        );
        assert!(!outcome.completed);

        let view = loop_driver
            .governance_view(
                "task-worker-governance-confirmation",
                "effect-worker-governance-confirmation",
            )
            .unwrap()
            .expect("governance view must exist after parked confirmation");

        assert_eq!(view.worker_state, WorkerState::AwaitingConfirmation);
        assert_eq!(view.effect_status, EffectStatus::Prepared);
        assert_eq!(view.attempt_count, 0);
        assert_eq!(view.disposition, RuntimeGovernanceDisposition::QueueForConfirmation);
        assert!(!view.has_recovery_lease);
    }

    #[test]
    fn worker_loop_drive_until_empty_returns_parked_confirmation_batch() {
        let temp = TempWorkspace::new("drive-confirmation-batch");
        let mut loop_driver = SqliteSingleWorkerLoop::open(
            &temp.db_path,
            SqliteOpenOptions::default(),
        )
        .unwrap()
        .with_lease_ttl_ms(25);
        loop_driver
            .enqueue_task(OrchestratorTask::new(
                "task-worker-drive-confirmation-batch",
                ScheduleIntent::write(format!("scope:{}", temp.output_path.display())),
                0,
            ))
            .unwrap();

        let outcomes = loop_driver
            .claim_and_drive_until_empty("worker-a", 0, PreflightDecision::NeedsConfirmation, |claim| {
                let effect = EffectRecord::new(
                    "effect-worker-drive-confirmation-batch",
                    claim.task.task_id.clone(),
                    "trace-worker-drive-confirmation-batch",
                    "intent-worker-drive-confirmation-batch",
                    EffectActor::Worker,
                    EffectAction::FileWrite,
                    claim.task.intent.target_scope.clone(),
                    EffectTier::Tier1,
                    EffectReversibility::Rollbackable,
                    ProbeMode::Auto,
                );
                Ok((InMemoryTaskRuntime::new(effect), sandbox_success_command()))
            })
            .unwrap();

        assert_eq!(outcomes.len(), 1);
        let outcome = &outcomes[0];
        assert_eq!(outcome.execution_summary.worker_state, WorkerState::AwaitingConfirmation);
        assert_eq!(outcome.final_summary.worker_state, WorkerState::AwaitingConfirmation);
        assert_eq!(outcome.disposition, Some(WorkerLoopDisposition::QueueForConfirmation));
        assert!(!outcome.completed);
        assert!(!temp.output_path.exists());
        assert_eq!(loop_driver.queue_snapshot().active_leases.len(), 1);
    }

    #[test]
    fn worker_loop_dispatch_runs_fresh_task_when_no_persisted_runtime_exists() {
        let temp = TempWorkspace::new("dispatch-fresh");
        let expected_bytes = b"safeclaw dispatch fresh\n";
        let mut loop_driver = SqliteSingleWorkerLoop::open(
            &temp.db_path,
            SqliteOpenOptions::default(),
        )
        .unwrap()
        .with_lease_ttl_ms(25);
        loop_driver
            .enqueue_task(OrchestratorTask::new(
                "task-worker-dispatch-fresh",
                ScheduleIntent::write(format!("scope:{}", temp.output_path.display())),
                0,
            ))
            .unwrap();

        let outcome = loop_driver
            .claim_and_dispatch_once(
                "worker-a",
                0,
                "effect-worker-dispatch-fresh",
                PreflightDecision::Permit,
                |claim| {
                    let effect = EffectRecord::new(
                        "effect-worker-dispatch-fresh",
                        claim.task.task_id.clone(),
                        "trace-worker-dispatch-fresh",
                        "intent-worker-dispatch-fresh",
                        EffectActor::Worker,
                        EffectAction::FileWrite,
                        claim.task.intent.target_scope.clone(),
                        EffectTier::Tier1,
                        EffectReversibility::Rollbackable,
                        ProbeMode::Auto,
                    );
                    Ok((
                        InMemoryTaskRuntime::new(effect),
                        sandbox_write_command(&temp.output_path, expected_bytes),
                    ))
                },
                |_, _| unreachable!(),
            )
            .unwrap()
            .expect("fresh task must be dispatchable");
        match outcome {
            WorkerLoopDispatchOutcome::Executed(executed) => {
                assert_eq!(executed.claim.task.task_id, "task-worker-dispatch-fresh");
                assert_eq!(executed.final_summary.worker_state, WorkerState::Succeeded);
                assert_eq!(executed.final_summary.effect_status, EffectStatus::Executed);
                assert!(executed.completed);
            }
            WorkerLoopDispatchOutcome::Probed(_) => panic!("fresh dispatch must execute directly"),
            _ => panic!("unexpected parked dispatch outcome"),
        }
        assert_eq!(fs::read(&temp.output_path).unwrap(), expected_bytes);
    }

    #[test]
    fn worker_loop_dispatch_parks_confirmation_before_sandbox() {
        let temp = TempWorkspace::new("dispatch-confirmation");
        let mut loop_driver = SqliteSingleWorkerLoop::open(
            &temp.db_path,
            SqliteOpenOptions::default(),
        )
        .unwrap()
        .with_lease_ttl_ms(25);
        loop_driver
            .enqueue_task(OrchestratorTask::new(
                "task-worker-dispatch-confirmation",
                ScheduleIntent::write(format!("scope:{}", temp.output_path.display())),
                0,
            ))
            .unwrap();

        let outcome = loop_driver
            .claim_and_dispatch_once(
                "worker-a",
                0,
                "effect-worker-dispatch-confirmation",
                PreflightDecision::NeedsConfirmation,
                |claim| {
                    let effect = EffectRecord::new(
                        "effect-worker-dispatch-confirmation",
                        claim.task.task_id.clone(),
                        "trace-worker-dispatch-confirmation",
                        "intent-worker-dispatch-confirmation",
                        EffectActor::Worker,
                        EffectAction::FileWrite,
                        claim.task.intent.target_scope.clone(),
                        EffectTier::Tier1,
                        EffectReversibility::Rollbackable,
                        ProbeMode::Auto,
                    );
                    Ok((InMemoryTaskRuntime::new(effect), sandbox_success_command()))
                },
                |_, _| unreachable!(),
            )
            .unwrap()
            .expect("confirmation dispatch must claim task");

        match outcome {
            WorkerLoopDispatchOutcome::Parked(parked) => {
                assert_eq!(parked.claim.task.task_id, "task-worker-dispatch-confirmation");
                assert_eq!(parked.summary.worker_state, WorkerState::AwaitingConfirmation);
                assert_eq!(parked.summary.effect_status, EffectStatus::Prepared);
                assert_eq!(parked.disposition, WorkerLoopDisposition::QueueForConfirmation);
                assert!(!parked.completed);
            }
            WorkerLoopDispatchOutcome::Executed(_) => {
                panic!("confirmation dispatch must not execute sandbox")
            }
            WorkerLoopDispatchOutcome::Probed(_) => {
                panic!("confirmation dispatch must not probe runtime")
            }
        }
        assert!(!temp.output_path.exists());
        assert_eq!(loop_driver.queue_snapshot().active_leases.len(), 1);

        let verify_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let restored = verify_store
            .load_runtime(
                "task-worker-dispatch-confirmation",
                "effect-worker-dispatch-confirmation",
            )
            .unwrap()
            .expect("confirmation runtime must persist before parking");
        assert_eq!(restored.worker_state, WorkerState::AwaitingConfirmation);
        assert_eq!(restored.effect.status, EffectStatus::Prepared);
        assert!(restored.attempts.is_empty());
    }

    #[test]
    fn worker_loop_dispatch_retries_failed_runtime_before_execution() {
        let temp = TempWorkspace::new("dispatch-failed");
        let mut first_worker = SqliteSingleWorkerLoop::open(
            &temp.db_path,
            SqliteOpenOptions::default(),
        )
        .unwrap()
        .with_lease_ttl_ms(25);
        first_worker
            .enqueue_task(OrchestratorTask::new(
                "task-worker-dispatch-failed",
                ScheduleIntent::write(format!("scope:{}", temp.output_path.display())),
                0,
            ))
            .unwrap();
        let failed = first_worker
            .claim_and_drive_once("worker-a", 0, PreflightDecision::Permit, |claim| {
                let effect = EffectRecord::new(
                    "effect-worker-dispatch-failed",
                    claim.task.task_id.clone(),
                    "trace-worker-dispatch-failed",
                    "intent-worker-dispatch-failed",
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

        let expected_bytes = b"safeclaw dispatch retried\n";
        let mut retry_worker = SqliteSingleWorkerLoop::open(
            &temp.db_path,
            SqliteOpenOptions::default(),
        )
        .unwrap()
        .with_lease_ttl_ms(25);
        let outcome = retry_worker
            .claim_and_dispatch_once(
                "worker-b",
                26,
                "effect-worker-dispatch-failed",
                PreflightDecision::Permit,
                |_| unreachable!(),
                |claim, runtime| {
                    assert_eq!(claim.task.task_id, "task-worker-dispatch-failed");
                    assert_eq!(runtime.worker_state, WorkerState::Executing);
                    Ok(sandbox_write_command(&temp.output_path, expected_bytes))
                },
            )
            .unwrap()
            .expect("failed runtime must be retried by dispatch");
        match outcome {
            WorkerLoopDispatchOutcome::Executed(executed) => {
                assert_eq!(executed.final_summary.worker_state, WorkerState::Succeeded);
                assert_eq!(executed.final_summary.effect_status, EffectStatus::Executed);
                assert!(executed.completed);
            }
            WorkerLoopDispatchOutcome::Probed(_) => panic!("failed dispatch must retry via execution"),
            _ => panic!("unexpected parked dispatch outcome"),
        }
        assert_eq!(fs::read(&temp.output_path).unwrap(), expected_bytes);
    }

    #[test]
    fn worker_loop_dispatch_probes_persisted_uncertain_runtime() {
        let temp = TempWorkspace::new("dispatch-uncertain");
        let expected_bytes = b"safeclaw dispatch probe\n";
        let mut orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-dispatch-uncertain",
                ScheduleIntent::write(format!("scope:{}", temp.output_path.display())),
                0,
            ))
            .unwrap();
        let claim = orchestrator.claim_next("worker-a", 0).unwrap().unwrap();
        let effect = EffectRecord::new(
            "effect-worker-dispatch-uncertain",
            claim.task.task_id.clone(),
            "trace-worker-dispatch-uncertain",
            "intent-worker-dispatch-uncertain",
            EffectActor::Worker,
            EffectAction::FileWrite,
            claim.task.intent.target_scope.clone(),
            EffectTier::Tier1,
            EffectReversibility::Rollbackable,
            ProbeMode::Auto,
        );
        let mut runtime = InMemoryTaskRuntime::new(effect);
        runtime.begin_execution(PreflightDecision::Permit).unwrap();
        let executor = LocalSandboxExecutor::new();
        let (_, execution_summary) = executor
            .run_and_apply(
                &mut runtime,
                &sandbox_write_then_timeout_command(&temp.output_path, expected_bytes),
            )
            .unwrap();
        assert_eq!(execution_summary.worker_state, WorkerState::Uncertain);

        let mut store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        store
            .persist_runtime(
                &runtime,
                format!("worker-loop:{}:post-exec", claim.lease.lease_id),
                "test",
            )
            .unwrap();

        let mut probe_worker = SqliteSingleWorkerLoop::open(
            &temp.db_path,
            SqliteOpenOptions::default(),
        )
        .unwrap()
        .with_lease_ttl_ms(25);
        probe_worker.filesystem_probe_mut().register_expected_blake3(
            "effect-worker-dispatch-uncertain",
            blake3::hash(expected_bytes).to_hex().to_string(),
        );
        let outcome = probe_worker
            .claim_and_dispatch_once(
                "worker-b",
                26,
                "effect-worker-dispatch-uncertain",
                PreflightDecision::Permit,
                |_| unreachable!(),
                |_, _| unreachable!(),
            )
            .unwrap()
            .expect("uncertain runtime must be probed by dispatch");
        match outcome {
            WorkerLoopDispatchOutcome::Probed(probed) => {
                assert_eq!(probed.recovered_from, WorkerState::Uncertain);
                assert_eq!(probed.final_summary.worker_state, WorkerState::Succeeded);
                assert_eq!(probed.final_summary.effect_status, EffectStatus::Executed);
                assert!(probed.completed);
            }
            WorkerLoopDispatchOutcome::Executed(_) => panic!("uncertain dispatch must probe"),
            _ => panic!("unexpected parked dispatch outcome"),
        }
        assert_eq!(fs::read(&temp.output_path).unwrap(), expected_bytes);
    }

    #[test]
    fn worker_loop_dispatch_resumes_persisted_runtime_before_execution() {
        let temp = TempWorkspace::new("dispatch-resume");
        let mut first_worker = SqliteSingleWorkerLoop::open(
            &temp.db_path,
            SqliteOpenOptions::default(),
        )
        .unwrap()
        .with_lease_ttl_ms(25);
        first_worker
            .enqueue_task(OrchestratorTask::new(
                "task-worker-dispatch-resume",
                ScheduleIntent::write(format!("scope:{}", temp.output_path.display())),
                0,
            ))
            .unwrap();
        let error = first_worker
            .claim_and_drive_once("worker-a", 0, PreflightDecision::Permit, |claim| {
                let effect = EffectRecord::new(
                    "effect-worker-dispatch-resume",
                    claim.task.task_id.clone(),
                    "trace-worker-dispatch-resume",
                    "intent-worker-dispatch-resume",
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

        let mut resume_worker = SqliteSingleWorkerLoop::open(
            &temp.db_path,
            SqliteOpenOptions::default(),
        )
        .unwrap()
        .with_lease_ttl_ms(25);
        let blocked = resume_worker
            .claim_and_dispatch_once(
                "worker-b",
                10,
                "effect-worker-dispatch-resume",
                PreflightDecision::Permit,
                |_| unreachable!(),
                |_, _| unreachable!(),
            )
            .unwrap();
        assert!(blocked.is_none());

        let expected_bytes = b"safeclaw dispatch resume\n";
        let outcome = resume_worker
            .claim_and_dispatch_once(
                "worker-b",
                26,
                "effect-worker-dispatch-resume",
                PreflightDecision::Permit,
                |_| unreachable!(),
                |claim, runtime| {
                    assert_eq!(claim.task.task_id, "task-worker-dispatch-resume");
                    assert_eq!(runtime.worker_state, WorkerState::Executing);
                    assert_eq!(runtime.effect.status, EffectStatus::Prepared);
                    Ok(sandbox_write_command(&temp.output_path, expected_bytes))
                },
            )
            .unwrap()
            .expect("expired pre-exec runtime must be resumed by dispatch");
        match outcome {
            WorkerLoopDispatchOutcome::Executed(executed) => {
                assert_eq!(executed.final_summary.worker_state, WorkerState::Succeeded);
                assert_eq!(executed.final_summary.effect_status, EffectStatus::Executed);
                assert!(executed.completed);
            }
            WorkerLoopDispatchOutcome::Probed(_) => panic!("executing dispatch must resume via execution"),
            _ => panic!("unexpected parked dispatch outcome"),
        }
        assert_eq!(fs::read(&temp.output_path).unwrap(), expected_bytes);

        let verify_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let restored = verify_store
            .load_runtime("task-worker-dispatch-resume", "effect-worker-dispatch-resume")
            .unwrap()
            .expect("resumed dispatch runtime must reload");
        assert_eq!(restored.worker_state, WorkerState::Succeeded);
        assert_eq!(restored.effect.status, EffectStatus::Executed);
        assert!(!restored.attempts.is_empty());
    }

    #[test]
    fn worker_loop_dispatch_parks_unavailable_persisted_runtime_state() {
        let temp = TempWorkspace::new("dispatch-unavailable");
        let mut orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-dispatch-unavailable",
                ScheduleIntent::write(format!("scope:{}", temp.output_path.display())),
                0,
            ))
            .unwrap();
        let effect = EffectRecord::new(
            "effect-worker-dispatch-unavailable",
            String::from("task-worker-dispatch-unavailable"),
            "trace-worker-dispatch-unavailable",
            "intent-worker-dispatch-unavailable",
            EffectActor::Worker,
            EffectAction::FileWrite,
            format!("scope:{}", temp.output_path.display()),
            EffectTier::Tier1,
            EffectReversibility::Rollbackable,
            ProbeMode::Auto,
        );
        let runtime = InMemoryTaskRuntime::new(effect);
        let mut store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        store
            .persist_runtime(&runtime, String::from("worker-loop:seed:planning"), "test")
            .unwrap();

        let mut dispatch_worker = SqliteSingleWorkerLoop::new(orchestrator, store);
        let outcome = dispatch_worker
            .claim_and_dispatch_once(
                "worker-b",
                0,
                "effect-worker-dispatch-unavailable",
                PreflightDecision::Permit,
                |_| unreachable!(),
                |_, _| unreachable!(),
            )
            .unwrap()
            .expect("unavailable runtime must still return a parked outcome");
        match outcome {
            WorkerLoopDispatchOutcome::Parked(parked) => {
                assert_eq!(parked.summary.worker_state, WorkerState::Created);
                assert_eq!(parked.summary.effect_status, EffectStatus::Prepared);
                assert_eq!(parked.disposition, WorkerLoopDisposition::ParkedUnsupported);
                assert!(!parked.completed);
            }
            WorkerLoopDispatchOutcome::Executed(_) => {
                panic!("unavailable runtime must not execute")
            }
            WorkerLoopDispatchOutcome::Probed(_) => {
                panic!("unavailable runtime must not probe")
            }
        }
        assert!(!temp.output_path.exists());
        assert_eq!(dispatch_worker.queue_snapshot().active_leases.len(), 1);
    }

    #[test]
    fn worker_loop_dispatch_until_empty_returns_empty_batch_when_queue_is_empty() {
        let temp = TempWorkspace::new("dispatch-empty");
        let mut loop_driver = SqliteSingleWorkerLoop::open(
            &temp.db_path,
            SqliteOpenOptions::default(),
        )
        .unwrap()
        .with_lease_ttl_ms(25);

        let outcomes = loop_driver
            .claim_and_dispatch_until_empty(
                "worker-a",
                0,
                PreflightDecision::Permit,
                |_| unreachable!(),
                |_| unreachable!(),
                |_, _| unreachable!(),
            )
            .unwrap();
        assert!(outcomes.is_empty());
    }

    #[test]
    fn worker_loop_dispatch_until_empty_drains_executed_branches() {
        let temp = TempWorkspace::new("dispatch-batch");
        let fresh_output = temp.root.join("dispatch-fresh.txt");
        let retry_output = temp.root.join("dispatch-retry.txt");
        let resume_output = temp.root.join("dispatch-resume.txt");

        let mut retry_seed_worker = SqliteSingleWorkerLoop::open(
            &temp.db_path,
            SqliteOpenOptions::default(),
        )
        .unwrap()
        .with_lease_ttl_ms(25);
        retry_seed_worker
            .enqueue_task(OrchestratorTask::new(
                "task-worker-dispatch-batch-retry",
                ScheduleIntent::write(format!("scope:{}", retry_output.display())),
                0,
            ))
            .unwrap();
        let failed = retry_seed_worker
            .claim_and_drive_once("worker-retry-a", 0, PreflightDecision::Permit, |claim| {
                let effect = EffectRecord::new(
                    "effect-worker-dispatch-batch-retry",
                    claim.task.task_id.clone(),
                    "trace-worker-dispatch-batch-retry",
                    "intent-worker-dispatch-batch-retry",
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
            .expect("retry seed must claim task");
        assert_eq!(failed.final_summary.worker_state, WorkerState::Failed);

        let mut resume_seed_worker = SqliteSingleWorkerLoop::open(
            &temp.db_path,
            SqliteOpenOptions::default(),
        )
        .unwrap()
        .with_lease_ttl_ms(25);
        resume_seed_worker
            .enqueue_task(OrchestratorTask::new(
                "task-worker-dispatch-batch-resume",
                ScheduleIntent::write(format!("scope:{}", resume_output.display())),
                1,
            ))
            .unwrap();
        let resume_error = resume_seed_worker
            .claim_and_drive_once("worker-resume-a", 0, PreflightDecision::Permit, |claim| {
                let effect = EffectRecord::new(
                    "effect-worker-dispatch-batch-resume",
                    claim.task.task_id.clone(),
                    "trace-worker-dispatch-batch-resume",
                    "intent-worker-dispatch-batch-resume",
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
        assert!(matches!(resume_error, WorkerLoopError::Sandbox(_)));

        let mut fresh_worker = SqliteSingleWorkerLoop::open(
            &temp.db_path,
            SqliteOpenOptions::default(),
        )
        .unwrap()
        .with_lease_ttl_ms(25);
        fresh_worker
            .enqueue_task(OrchestratorTask::new(
                "task-worker-dispatch-batch-fresh",
                ScheduleIntent::write(format!("scope:{}", fresh_output.display())),
                2,
            ))
            .unwrap();

        let expected_fresh = b"safeclaw batch fresh\n";
        let expected_retry = b"safeclaw batch retry\n";
        let expected_resume = b"safeclaw batch resume\n";

        let mut batch_worker = SqliteSingleWorkerLoop::open(
            &temp.db_path,
            SqliteOpenOptions::default(),
        )
        .unwrap()
        .with_lease_ttl_ms(25);
        let outcomes = batch_worker
            .claim_and_dispatch_until_empty(
                "worker-batch",
                26,
                PreflightDecision::Permit,
                |claim| {
                    Ok(match claim.task.task_id.as_str() {
                        "task-worker-dispatch-batch-fresh" => {
                            String::from("effect-worker-dispatch-batch-fresh")
                        }
                        "task-worker-dispatch-batch-retry" => {
                            String::from("effect-worker-dispatch-batch-retry")
                        }
                        "task-worker-dispatch-batch-resume" => {
                            String::from("effect-worker-dispatch-batch-resume")
                        }
                        other => panic!("unexpected task id: {other}"),
                    })
                },
                |claim| match claim.task.task_id.as_str() {
                    "task-worker-dispatch-batch-fresh" => {
                        let effect = EffectRecord::new(
                            "effect-worker-dispatch-batch-fresh",
                            claim.task.task_id.clone(),
                            "trace-worker-dispatch-batch-fresh",
                            "intent-worker-dispatch-batch-fresh",
                            EffectActor::Worker,
                            EffectAction::FileWrite,
                            claim.task.intent.target_scope.clone(),
                            EffectTier::Tier1,
                            EffectReversibility::Rollbackable,
                            ProbeMode::Auto,
                        );
                        Ok((
                            InMemoryTaskRuntime::new(effect),
                            sandbox_write_command(&fresh_output, expected_fresh),
                        ))
                    }
                    other => panic!("unexpected fresh task id: {other}"),
                },
                |claim, runtime| match claim.task.task_id.as_str() {
                    "task-worker-dispatch-batch-retry" => {
                        assert_eq!(runtime.worker_state, WorkerState::Executing);
                        Ok(sandbox_write_command(&retry_output, expected_retry))
                    }
                    "task-worker-dispatch-batch-resume" => {
                        assert_eq!(runtime.worker_state, WorkerState::Executing);
                        Ok(sandbox_write_command(&resume_output, expected_resume))
                    }
                    other => panic!("unexpected persisted task id: {other}"),
                },
            )
            .unwrap();

        assert_eq!(outcomes.len(), 3);
        let mut executed_ids = Vec::new();
        for outcome in outcomes {
            match outcome {
                WorkerLoopDispatchOutcome::Executed(executed) => {
                    assert_eq!(executed.final_summary.worker_state, WorkerState::Succeeded);
                    assert_eq!(executed.final_summary.effect_status, EffectStatus::Executed);
                    assert!(executed.completed);
                    executed_ids.push(executed.claim.task.task_id);
                }
                WorkerLoopDispatchOutcome::Probed(_) => {
                    panic!("executed-branch batch must not probe")
                }
                _ => panic!("unexpected parked dispatch outcome"),
            }
        }
        executed_ids.sort();
        assert_eq!(
            executed_ids,
            vec![
                String::from("task-worker-dispatch-batch-fresh"),
                String::from("task-worker-dispatch-batch-resume"),
                String::from("task-worker-dispatch-batch-retry"),
            ]
        );
        assert_eq!(fs::read(&fresh_output).unwrap(), expected_fresh);
        assert_eq!(fs::read(&retry_output).unwrap(), expected_retry);
        assert_eq!(fs::read(&resume_output).unwrap(), expected_resume);
        assert!(batch_worker.queue_snapshot().queued_tasks.is_empty());
        assert!(batch_worker.queue_snapshot().active_leases.is_empty());
        assert_eq!(batch_worker.queue_snapshot().completed_task_ids.len(), 3);
    }

    #[test]
    fn worker_loop_dispatch_until_empty_drains_probe_branch() {
        let temp = TempWorkspace::new("dispatch-batch-probe");
        let expected_probe = b"safeclaw batch probe\n";
        let mut orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-dispatch-batch-probe",
                ScheduleIntent::write(format!("scope:{}", temp.output_path.display())),
                0,
            ))
            .unwrap();
        let claim = orchestrator.claim_next("worker-probe-a", 0).unwrap().unwrap();
        let effect = EffectRecord::new(
            "effect-worker-dispatch-batch-probe",
            claim.task.task_id.clone(),
            "trace-worker-dispatch-batch-probe",
            "intent-worker-dispatch-batch-probe",
            EffectActor::Worker,
            EffectAction::FileWrite,
            claim.task.intent.target_scope.clone(),
            EffectTier::Tier1,
            EffectReversibility::Rollbackable,
            ProbeMode::Auto,
        );
        let mut runtime = InMemoryTaskRuntime::new(effect);
        runtime.begin_execution(PreflightDecision::Permit).unwrap();
        let executor = LocalSandboxExecutor::new();
        let (_, execution_summary) = executor
            .run_and_apply(
                &mut runtime,
                &sandbox_write_then_timeout_command(&temp.output_path, expected_probe),
            )
            .unwrap();
        assert_eq!(execution_summary.worker_state, WorkerState::Uncertain);
        let mut store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        store
            .persist_runtime(
                &runtime,
                format!("worker-loop:{}:post-exec", claim.lease.lease_id),
                "test",
            )
            .unwrap();

        let mut batch_worker = SqliteSingleWorkerLoop::open(
            &temp.db_path,
            SqliteOpenOptions::default(),
        )
        .unwrap()
        .with_lease_ttl_ms(25);
        batch_worker.filesystem_probe_mut().register_expected_blake3(
            "effect-worker-dispatch-batch-probe",
            blake3::hash(expected_probe).to_hex().to_string(),
        );
        let outcomes = batch_worker
            .claim_and_dispatch_until_empty(
                "worker-probe-b",
                26,
                PreflightDecision::Permit,
                |_| Ok(String::from("effect-worker-dispatch-batch-probe")),
                |_| unreachable!(),
                |_, _| unreachable!(),
            )
            .unwrap();
        assert_eq!(outcomes.len(), 1);
        match &outcomes[0] {
            WorkerLoopDispatchOutcome::Probed(probed) => {
                assert_eq!(probed.recovered_from, WorkerState::Uncertain);
                assert_eq!(probed.final_summary.worker_state, WorkerState::Succeeded);
                assert_eq!(probed.final_summary.effect_status, EffectStatus::Executed);
                assert!(probed.completed);
            }
            WorkerLoopDispatchOutcome::Executed(_) => panic!("probe batch must recover uncertain runtime"),
            _ => panic!("unexpected parked dispatch outcome"),
        }
        assert_eq!(fs::read(&temp.output_path).unwrap(), expected_probe);
        assert!(batch_worker.queue_snapshot().queued_tasks.is_empty());
        assert!(batch_worker.queue_snapshot().active_leases.is_empty());
        assert_eq!(batch_worker.queue_snapshot().completed_task_ids.len(), 1);
    }

    #[test]
    fn worker_loop_dispatch_until_empty_returns_parked_later_unavailable_runtime() {
        let temp = TempWorkspace::new("dispatch-batch-stop");
        let first_output = temp.root.join("dispatch-first.txt");
        let second_output = temp.root.join("dispatch-second.txt");

        let mut seed_worker = SqliteSingleWorkerLoop::open(
            &temp.db_path,
            SqliteOpenOptions::default(),
        )
        .unwrap()
        .with_lease_ttl_ms(25);
        seed_worker
            .enqueue_task(OrchestratorTask::new(
                "task-worker-dispatch-stop-fresh",
                ScheduleIntent::write(format!("scope:{}", first_output.display())),
                0,
            ))
            .unwrap();
        seed_worker
            .enqueue_task(OrchestratorTask::new(
                "task-worker-dispatch-stop-created",
                ScheduleIntent::write(format!("scope:{}", second_output.display())),
                1,
            ))
            .unwrap();

        let created_effect = EffectRecord::new(
            "effect-worker-dispatch-stop-created",
            String::from("task-worker-dispatch-stop-created"),
            "trace-worker-dispatch-stop-created",
            "intent-worker-dispatch-stop-created",
            EffectActor::Worker,
            EffectAction::FileWrite,
            format!("scope:{}", second_output.display()),
            EffectTier::Tier1,
            EffectReversibility::Rollbackable,
            ProbeMode::Auto,
        );
        let created_runtime = InMemoryTaskRuntime::new(created_effect);
        let mut seed_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        seed_store
            .persist_runtime(
                &created_runtime,
                String::from("worker-loop:seed:created"),
                "test",
            )
            .unwrap();

        let expected_first = b"safeclaw dispatch stop first\n";
        let mut batch_worker = SqliteSingleWorkerLoop::open(
            &temp.db_path,
            SqliteOpenOptions::default(),
        )
        .unwrap()
        .with_lease_ttl_ms(25);
        let outcomes = batch_worker
            .claim_and_dispatch_until_empty(
                "worker-batch",
                0,
                PreflightDecision::Permit,
                |claim| {
                    Ok(match claim.task.task_id.as_str() {
                        "task-worker-dispatch-stop-fresh" => {
                            String::from("effect-worker-dispatch-stop-fresh")
                        }
                        "task-worker-dispatch-stop-created" => {
                            String::from("effect-worker-dispatch-stop-created")
                        }
                        other => panic!("unexpected task id: {other}"),
                    })
                },
                |claim| match claim.task.task_id.as_str() {
                    "task-worker-dispatch-stop-fresh" => {
                        let effect = EffectRecord::new(
                            "effect-worker-dispatch-stop-fresh",
                            claim.task.task_id.clone(),
                            "trace-worker-dispatch-stop-fresh",
                            "intent-worker-dispatch-stop-fresh",
                            EffectActor::Worker,
                            EffectAction::FileWrite,
                            claim.task.intent.target_scope.clone(),
                            EffectTier::Tier1,
                            EffectReversibility::Rollbackable,
                            ProbeMode::Auto,
                        );
                        Ok((
                            InMemoryTaskRuntime::new(effect),
                            sandbox_write_command(&first_output, expected_first),
                        ))
                    }
                    other => panic!("unexpected fresh task id: {other}"),
                },
                |_, _| unreachable!(),
            )
            .unwrap();

        assert_eq!(outcomes.len(), 2);
        match &outcomes[0] {
            WorkerLoopDispatchOutcome::Executed(executed) => {
                assert_eq!(executed.claim.task.task_id, "task-worker-dispatch-stop-fresh");
                assert_eq!(executed.final_summary.worker_state, WorkerState::Succeeded);
                assert!(executed.completed);
            }
            _ => panic!("first batch outcome must execute"),
        }
        match &outcomes[1] {
            WorkerLoopDispatchOutcome::Parked(parked) => {
                assert_eq!(parked.claim.task.task_id, "task-worker-dispatch-stop-created");
                assert_eq!(parked.summary.worker_state, WorkerState::Created);
                assert_eq!(parked.summary.effect_status, EffectStatus::Prepared);
                assert_eq!(parked.disposition, WorkerLoopDisposition::ParkedUnsupported);
                assert!(!parked.completed);
            }
            _ => panic!("second batch outcome must park unsupported runtime"),
        }
        assert_eq!(fs::read(&first_output).unwrap(), expected_first);
        assert!(!second_output.exists());
        assert!(batch_worker.queue_snapshot().queued_tasks.is_empty());
        assert_eq!(batch_worker.queue_snapshot().completed_task_ids, vec![String::from("task-worker-dispatch-stop-fresh")]);
        assert_eq!(batch_worker.queue_snapshot().active_leases.len(), 1);
        assert_eq!(batch_worker.queue_snapshot().active_leases[0].task_id, "task-worker-dispatch-stop-created");
    }

    #[test]
    fn worker_loop_dispatch_until_empty_stops_on_later_fresh_spawn_failure() {
        let temp = TempWorkspace::new("dispatch-batch-fresh-spawn-failure");
        let first_output = temp.root.join("dispatch-fresh-first.txt");
        let second_output = temp.root.join("dispatch-fresh-second.txt");
        let mut loop_driver = SqliteSingleWorkerLoop::open(
            &temp.db_path,
            SqliteOpenOptions::default(),
        )
        .unwrap()
        .with_lease_ttl_ms(25);
        loop_driver
            .enqueue_task(OrchestratorTask::new(
                "task-worker-dispatch-fresh-failure-1",
                ScheduleIntent::write(format!("scope:{}", first_output.display())),
                0,
            ))
            .unwrap();
        loop_driver
            .enqueue_task(OrchestratorTask::new(
                "task-worker-dispatch-fresh-failure-2",
                ScheduleIntent::write(format!("scope:{}", second_output.display())),
                1,
            ))
            .unwrap();

        let error = loop_driver
            .claim_and_dispatch_until_empty(
                "worker-a",
                0,
                PreflightDecision::Permit,
                |claim| {
                    Ok(match claim.task.task_id.as_str() {
                        "task-worker-dispatch-fresh-failure-1" => {
                            String::from("effect-worker-dispatch-fresh-failure-1")
                        }
                        "task-worker-dispatch-fresh-failure-2" => {
                            String::from("effect-worker-dispatch-fresh-failure-2")
                        }
                        other => panic!("unexpected task id: {other}"),
                    })
                },
                |claim| {
                    let (effect_id, trace_id, intent_key, command) = match claim.task.task_id.as_str() {
                        "task-worker-dispatch-fresh-failure-1" => (
                            "effect-worker-dispatch-fresh-failure-1",
                            "trace-worker-dispatch-fresh-failure-1",
                            "intent-worker-dispatch-fresh-failure-1",
                            sandbox_write_command(&first_output, b"safeclaw dispatch fresh failure one\n"),
                        ),
                        "task-worker-dispatch-fresh-failure-2" => (
                            "effect-worker-dispatch-fresh-failure-2",
                            "trace-worker-dispatch-fresh-failure-2",
                            "intent-worker-dispatch-fresh-failure-2",
                            sandbox_missing_program_command(),
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
                    Ok((InMemoryTaskRuntime::new(effect), command))
                },
                |_, _| unreachable!(),
            )
            .unwrap_err();

        assert!(matches!(error, WorkerLoopError::Sandbox(_)));
        assert_eq!(fs::read(&first_output).unwrap(), b"safeclaw dispatch fresh failure one\n");
        assert!(!second_output.exists());
        assert!(loop_driver.queue_snapshot().queued_tasks.is_empty());
        assert_eq!(
            loop_driver.queue_snapshot().completed_task_ids,
            vec![String::from("task-worker-dispatch-fresh-failure-1")]
        );
        assert_eq!(loop_driver.queue_snapshot().active_leases.len(), 1);
        assert_eq!(
            loop_driver.queue_snapshot().active_leases[0].task_id,
            "task-worker-dispatch-fresh-failure-2"
        );

        let verify_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let restored_one = verify_store
            .load_runtime(
                "task-worker-dispatch-fresh-failure-1",
                "effect-worker-dispatch-fresh-failure-1",
            )
            .unwrap()
            .expect("first fresh failure runtime must reload");
        let restored_two = verify_store
            .load_runtime(
                "task-worker-dispatch-fresh-failure-2",
                "effect-worker-dispatch-fresh-failure-2",
            )
            .unwrap()
            .expect("second fresh failure runtime must reload");
        assert_eq!(restored_one.worker_state, WorkerState::Succeeded);
        assert_eq!(restored_one.effect.status, EffectStatus::Executed);
        assert_eq!(restored_two.worker_state, WorkerState::Executing);
        assert_eq!(restored_two.effect.status, EffectStatus::Prepared);
    }

    #[test]
    fn worker_loop_dispatch_until_empty_stops_on_later_persisted_spawn_failure() {
        let temp = TempWorkspace::new("dispatch-batch-persisted-spawn-failure");
        let first_output = temp.root.join("dispatch-persisted-first.txt");
        let second_output = temp.root.join("dispatch-persisted-second.txt");
        let mut orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-dispatch-persisted-failure-1",
                ScheduleIntent::write(format!("scope:{}", first_output.display())),
                0,
            ))
            .unwrap();
        orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-dispatch-persisted-failure-2",
                ScheduleIntent::write(format!("scope:{}", second_output.display())),
                1,
            ))
            .unwrap();
        let mut runtime_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let effect = EffectRecord::new(
            "effect-worker-dispatch-persisted-failure-2",
            String::from("task-worker-dispatch-persisted-failure-2"),
            "trace-worker-dispatch-persisted-failure-2",
            "intent-worker-dispatch-persisted-failure-2",
            EffectActor::Worker,
            EffectAction::FileWrite,
            format!("scope:{}", second_output.display()),
            EffectTier::Tier1,
            EffectReversibility::Rollbackable,
            ProbeMode::Auto,
        );
        let mut runtime = InMemoryTaskRuntime::new(effect);
        runtime.begin_execution(PreflightDecision::Permit).unwrap();
        runtime_store
            .persist_runtime(
                &runtime,
                String::from("worker-loop:seed:persisted-pre-exec"),
                "test",
            )
            .unwrap();
        let mut loop_driver = SqliteSingleWorkerLoop::new(orchestrator, runtime_store)
            .with_lease_ttl_ms(25);

        let error = loop_driver
            .claim_and_dispatch_until_empty(
                "worker-a",
                0,
                PreflightDecision::Permit,
                |claim| {
                    Ok(match claim.task.task_id.as_str() {
                        "task-worker-dispatch-persisted-failure-1" => {
                            String::from("effect-worker-dispatch-persisted-failure-1")
                        }
                        "task-worker-dispatch-persisted-failure-2" => {
                            String::from("effect-worker-dispatch-persisted-failure-2")
                        }
                        other => panic!("unexpected task id: {other}"),
                    })
                },
                |claim| match claim.task.task_id.as_str() {
                    "task-worker-dispatch-persisted-failure-1" => {
                        let effect = EffectRecord::new(
                            "effect-worker-dispatch-persisted-failure-1",
                            claim.task.task_id.clone(),
                            "trace-worker-dispatch-persisted-failure-1",
                            "intent-worker-dispatch-persisted-failure-1",
                            EffectActor::Worker,
                            EffectAction::FileWrite,
                            claim.task.intent.target_scope.clone(),
                            EffectTier::Tier1,
                            EffectReversibility::Rollbackable,
                            ProbeMode::Auto,
                        );
                        Ok((
                            InMemoryTaskRuntime::new(effect),
                            sandbox_write_command(&first_output, b"safeclaw dispatch persisted failure one\n"),
                        ))
                    }
                    other => panic!("unexpected fresh task id: {other}"),
                },
                |claim, runtime| match claim.task.task_id.as_str() {
                    "task-worker-dispatch-persisted-failure-2" => {
                        assert_eq!(runtime.worker_state, WorkerState::Executing);
                        Ok(sandbox_missing_program_command())
                    }
                    other => panic!("unexpected persisted task id: {other}"),
                },
            )
            .unwrap_err();

        assert!(matches!(error, WorkerLoopError::Sandbox(_)));
        assert_eq!(
            fs::read(&first_output).unwrap(),
            b"safeclaw dispatch persisted failure one\n"
        );
        assert!(!second_output.exists());
        assert!(loop_driver.queue_snapshot().queued_tasks.is_empty());
        assert_eq!(
            loop_driver.queue_snapshot().completed_task_ids,
            vec![String::from("task-worker-dispatch-persisted-failure-1")]
        );
        assert_eq!(loop_driver.queue_snapshot().active_leases.len(), 1);
        assert_eq!(
            loop_driver.queue_snapshot().active_leases[0].task_id,
            "task-worker-dispatch-persisted-failure-2"
        );

        let verify_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let restored_one = verify_store
            .load_runtime(
                "task-worker-dispatch-persisted-failure-1",
                "effect-worker-dispatch-persisted-failure-1",
            )
            .unwrap()
            .expect("first persisted failure runtime must reload");
        let restored_two = verify_store
            .load_runtime(
                "task-worker-dispatch-persisted-failure-2",
                "effect-worker-dispatch-persisted-failure-2",
            )
            .unwrap()
            .expect("second persisted failure runtime must reload");
        assert_eq!(restored_one.worker_state, WorkerState::Succeeded);
        assert_eq!(restored_one.effect.status, EffectStatus::Executed);
        assert_eq!(restored_two.worker_state, WorkerState::Executing);
        assert_eq!(restored_two.effect.status, EffectStatus::Prepared);
    }

    #[test]
    fn worker_loop_dispatch_until_empty_skips_conflicts_held_by_other_owner() {
        let temp = TempWorkspace::new("dispatch-drain-scope-skip");
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
                "task-worker-dispatch-shared-1",
                ScheduleIntent::write(shared_scope.clone()),
                0,
            ))
            .unwrap();
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-dispatch-shared-2",
                ScheduleIntent::write(shared_scope.clone()),
                1,
            ))
            .unwrap();
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-dispatch-other-1",
                ScheduleIntent::write(other_one_scope.clone()),
                2,
            ))
            .unwrap();
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-dispatch-other-2",
                ScheduleIntent::write(other_two_scope.clone()),
                3,
            ))
            .unwrap();

        let blocking_claim = blocking_orchestrator.claim_next("worker-a", 0).unwrap().unwrap();
        assert_eq!(blocking_claim.task.task_id, "task-worker-dispatch-shared-1");

        let drain_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        let drain_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut drain_worker = SqliteSingleWorkerLoop::new(drain_orchestrator, drain_store);

        let outcomes = drain_worker
            .claim_and_dispatch_until_empty(
                "worker-b",
                1,
                PreflightDecision::Permit,
                |claim| {
                    Ok(match claim.task.task_id.as_str() {
                        "task-worker-dispatch-other-1" => {
                            String::from("effect-worker-dispatch-other-1")
                        }
                        "task-worker-dispatch-other-2" => {
                            String::from("effect-worker-dispatch-other-2")
                        }
                        other => panic!("unexpected task id: {other}"),
                    })
                },
                |claim| {
                    let (effect_id, trace_id, intent_key, output_path, output_bytes) =
                        match claim.task.task_id.as_str() {
                            "task-worker-dispatch-other-1" => (
                                "effect-worker-dispatch-other-1",
                                "trace-worker-dispatch-other-1",
                                "intent-worker-dispatch-other-1",
                                &other_one_output,
                                b"safeclaw dispatch other one\n".as_slice(),
                            ),
                            "task-worker-dispatch-other-2" => (
                                "effect-worker-dispatch-other-2",
                                "trace-worker-dispatch-other-2",
                                "intent-worker-dispatch-other-2",
                                &other_two_output,
                                b"safeclaw dispatch other two\n".as_slice(),
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
                },
                |_, _| unreachable!(),
            )
            .unwrap();

        assert_eq!(outcomes.len(), 2);
        match &outcomes[0] {
            WorkerLoopDispatchOutcome::Executed(executed) => {
                assert_eq!(executed.claim.task.task_id, "task-worker-dispatch-other-1")
            }
            WorkerLoopDispatchOutcome::Probed(_) => panic!("conflict skip branch must execute"),
            _ => panic!("unexpected parked dispatch outcome"),
        }
        match &outcomes[1] {
            WorkerLoopDispatchOutcome::Executed(executed) => {
                assert_eq!(executed.claim.task.task_id, "task-worker-dispatch-other-2")
            }
            WorkerLoopDispatchOutcome::Probed(_) => panic!("conflict skip branch must execute"),
            _ => panic!("unexpected parked dispatch outcome"),
        }
        assert_eq!(
            fs::read(&other_one_output).unwrap(),
            b"safeclaw dispatch other one\n"
        );
        assert_eq!(
            fs::read(&other_two_output).unwrap(),
            b"safeclaw dispatch other two\n"
        );
        assert_eq!(
            drain_worker.queue_snapshot().queued_tasks[0].task_id,
            "task-worker-dispatch-shared-2"
        );
        assert_eq!(drain_worker.queue_snapshot().active_leases.len(), 1);
        assert_eq!(
            drain_worker.queue_snapshot().active_leases[0].task_id,
            "task-worker-dispatch-shared-1"
        );
    }

    #[test]
    fn worker_loop_dispatch_until_empty_claims_remaining_conflict_after_release() {
        let temp = TempWorkspace::new("dispatch-drain-release");
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
                "task-worker-dispatch-shared-1",
                ScheduleIntent::write(shared_scope.clone()),
                0,
            ))
            .unwrap();
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-dispatch-shared-2",
                ScheduleIntent::write(shared_scope.clone()),
                1,
            ))
            .unwrap();
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-dispatch-other-1",
                ScheduleIntent::write(other_one_scope.clone()),
                2,
            ))
            .unwrap();
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-dispatch-other-2",
                ScheduleIntent::write(other_two_scope.clone()),
                3,
            ))
            .unwrap();

        let blocking_claim = blocking_orchestrator.claim_next("worker-a", 0).unwrap().unwrap();
        assert_eq!(blocking_claim.task.task_id, "task-worker-dispatch-shared-1");

        let first_drain_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        let first_drain_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut first_drain_worker = SqliteSingleWorkerLoop::new(first_drain_orchestrator, first_drain_store);

        let first_outcomes = first_drain_worker
            .claim_and_dispatch_until_empty(
                "worker-b",
                1,
                PreflightDecision::Permit,
                |claim| {
                    Ok(match claim.task.task_id.as_str() {
                        "task-worker-dispatch-other-1" => {
                            String::from("effect-worker-dispatch-other-1")
                        }
                        "task-worker-dispatch-other-2" => {
                            String::from("effect-worker-dispatch-other-2")
                        }
                        other => panic!("unexpected task id: {other}"),
                    })
                },
                |claim| {
                    let (effect_id, trace_id, intent_key, output_path, output_bytes) =
                        match claim.task.task_id.as_str() {
                            "task-worker-dispatch-other-1" => (
                                "effect-worker-dispatch-other-1",
                                "trace-worker-dispatch-other-1",
                                "intent-worker-dispatch-other-1",
                                &other_one_output,
                                b"safeclaw dispatch other one\n".as_slice(),
                            ),
                            "task-worker-dispatch-other-2" => (
                                "effect-worker-dispatch-other-2",
                                "trace-worker-dispatch-other-2",
                                "intent-worker-dispatch-other-2",
                                &other_two_output,
                                b"safeclaw dispatch other two\n".as_slice(),
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
                },
                |_, _| unreachable!(),
            )
            .unwrap();
        assert_eq!(first_outcomes.len(), 2);
        assert_eq!(
            first_drain_worker.queue_snapshot().queued_tasks[0].task_id,
            "task-worker-dispatch-shared-2"
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
        let mut second_drain_worker = SqliteSingleWorkerLoop::new(second_drain_orchestrator, second_drain_store);

        let second_outcomes = second_drain_worker
            .claim_and_dispatch_until_empty(
                "worker-c",
                2,
                PreflightDecision::Permit,
                |claim| {
                    assert_eq!(claim.task.task_id, "task-worker-dispatch-shared-2");
                    Ok(String::from("effect-worker-dispatch-shared-2"))
                },
                |claim| {
                    assert_eq!(claim.task.task_id, "task-worker-dispatch-shared-2");
                    let effect = EffectRecord::new(
                        "effect-worker-dispatch-shared-2",
                        claim.task.task_id.clone(),
                        "trace-worker-dispatch-shared-2",
                        "intent-worker-dispatch-shared-2",
                        EffectActor::Worker,
                        EffectAction::FileWrite,
                        claim.task.intent.target_scope.clone(),
                        EffectTier::Tier1,
                        EffectReversibility::Rollbackable,
                        ProbeMode::Auto,
                    );
                    Ok((
                        InMemoryTaskRuntime::new(effect),
                        sandbox_write_command(&shared_output, b"safeclaw dispatch shared after release\n"),
                    ))
                },
                |_, _| unreachable!(),
            )
            .unwrap();

        assert_eq!(second_outcomes.len(), 1);
        match &second_outcomes[0] {
            WorkerLoopDispatchOutcome::Executed(executed) => {
                assert_eq!(executed.claim.task.task_id, "task-worker-dispatch-shared-2");
                assert!(executed.completed);
            }
            WorkerLoopDispatchOutcome::Probed(_) => panic!("released conflict must execute"),
            _ => panic!("unexpected parked dispatch outcome"),
        }
        assert_eq!(
            fs::read(&shared_output).unwrap(),
            b"safeclaw dispatch shared after release\n"
        );
        assert!(second_drain_worker.queue_snapshot().queued_tasks.is_empty());
        assert!(second_drain_worker.queue_snapshot().active_leases.is_empty());
        assert_eq!(
            second_drain_worker.queue_snapshot().completed_task_ids,
            vec![
                String::from("task-worker-dispatch-other-1"),
                String::from("task-worker-dispatch-other-2"),
                String::from("task-worker-dispatch-shared-1"),
                String::from("task-worker-dispatch-shared-2"),
            ]
        );
    }

    #[test]
    fn worker_loop_dispatch_until_empty_allows_same_scope_reads_to_coexist() {
        let temp = TempWorkspace::new("dispatch-scope-read-fanout");
        let shared_scope = format!("scope:{}", temp.root.join("shared-read.txt").display());

        let mut blocking_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-dispatch-shared-read-1",
                ScheduleIntent::read(shared_scope.clone()),
                0,
            ))
            .unwrap();
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-dispatch-shared-read-2",
                ScheduleIntent::read(shared_scope.clone()),
                1,
            ))
            .unwrap();

        let blocking_claim = blocking_orchestrator.claim_next("worker-a", 0).unwrap().unwrap();
        assert_eq!(blocking_claim.task.task_id, "task-worker-dispatch-shared-read-1");
        assert!(!blocking_claim.task.intent.requires_write);

        let read_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        let read_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut read_worker = SqliteSingleWorkerLoop::new(read_orchestrator, read_store);

        let outcomes = read_worker
            .claim_and_dispatch_until_empty(
                "worker-b",
                1,
                PreflightDecision::Permit,
                |claim| {
                    assert_eq!(claim.task.task_id, "task-worker-dispatch-shared-read-2");
                    Ok(String::from("effect-worker-dispatch-shared-read-2"))
                },
                |claim| {
                    assert_eq!(claim.task.task_id, "task-worker-dispatch-shared-read-2");
                    let effect = EffectRecord::new(
                        "effect-worker-dispatch-shared-read-2",
                        claim.task.task_id.clone(),
                        "trace-worker-dispatch-shared-read-2",
                        "intent-worker-dispatch-shared-read-2",
                        EffectActor::Worker,
                        EffectAction::NetworkRequest,
                        claim.task.intent.target_scope.clone(),
                        EffectTier::Tier1,
                        EffectReversibility::Rollbackable,
                        ProbeMode::Auto,
                    );
                    Ok((InMemoryTaskRuntime::new(effect), sandbox_success_command()))
                },
                |_, _| unreachable!(),
            )
            .unwrap();

        assert_eq!(outcomes.len(), 1);
        match &outcomes[0] {
            WorkerLoopDispatchOutcome::Executed(executed) => {
                assert_eq!(executed.claim.task.task_id, "task-worker-dispatch-shared-read-2");
                assert!(executed.completed);
                assert_eq!(executed.final_summary.worker_state, WorkerState::Succeeded);
                assert_eq!(executed.final_summary.effect_status, EffectStatus::Executed);
            }
            WorkerLoopDispatchOutcome::Probed(_) => panic!("same-scope second read must execute"),
            _ => panic!("unexpected parked dispatch outcome"),
        }
        assert_eq!(read_worker.queue_snapshot().queued_tasks.len(), 0);
        assert_eq!(read_worker.queue_snapshot().active_leases.len(), 1);
        assert_eq!(
            read_worker.queue_snapshot().active_leases[0].task_id,
            "task-worker-dispatch-shared-read-1"
        );
        assert_eq!(
            read_worker.queue_snapshot().completed_task_ids,
            vec![String::from("task-worker-dispatch-shared-read-2")]
        );

        let verify_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let restored = verify_store
            .load_runtime(
                "task-worker-dispatch-shared-read-2",
                "effect-worker-dispatch-shared-read-2",
            )
            .unwrap()
            .expect("same-scope second read runtime must reload");
        assert_eq!(restored.worker_state, WorkerState::Succeeded);
        assert_eq!(restored.effect.status, EffectStatus::Executed);
    }

    #[test]
    fn worker_loop_dispatch_until_empty_allows_same_scope_write_while_other_owners_hold_read_leases() {
        let temp = TempWorkspace::new("dispatch-scope-write-under-reads");
        let shared_scope = format!("scope:{}", temp.root.join("shared.txt").display());
        let write_output = temp.root.join("write-under-reads.txt");

        let mut blocking_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-dispatch-shared-read-active-1",
                ScheduleIntent::read(shared_scope.clone()),
                0,
            ))
            .unwrap();
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-dispatch-shared-read-active-2",
                ScheduleIntent::read(shared_scope.clone()),
                1,
            ))
            .unwrap();
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-dispatch-shared-write-after-reads",
                ScheduleIntent::write(shared_scope.clone()),
                2,
            ))
            .unwrap();

        let first_read = blocking_orchestrator.claim_next("worker-a", 0).unwrap().unwrap();
        assert_eq!(first_read.task.task_id, "task-worker-dispatch-shared-read-active-1");
        let second_read = blocking_orchestrator.claim_next("worker-b", 1).unwrap().unwrap();
        assert_eq!(second_read.task.task_id, "task-worker-dispatch-shared-read-active-2");

        let write_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        let write_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut write_worker = SqliteSingleWorkerLoop::new(write_orchestrator, write_store);

        let outcomes = write_worker
            .claim_and_dispatch_until_empty(
                "worker-c",
                2,
                PreflightDecision::Permit,
                |claim| {
                    assert_eq!(claim.task.task_id, "task-worker-dispatch-shared-write-after-reads");
                    Ok(String::from("effect-worker-dispatch-shared-write-after-reads"))
                },
                |claim| {
                    assert_eq!(claim.task.task_id, "task-worker-dispatch-shared-write-after-reads");
                    let effect = EffectRecord::new(
                        "effect-worker-dispatch-shared-write-after-reads",
                        claim.task.task_id.clone(),
                        "trace-worker-dispatch-shared-write-after-reads",
                        "intent-worker-dispatch-shared-write-after-reads",
                        EffectActor::Worker,
                        EffectAction::FileWrite,
                        claim.task.intent.target_scope.clone(),
                        EffectTier::Tier1,
                        EffectReversibility::Rollbackable,
                        ProbeMode::Auto,
                    );
                    Ok((
                        InMemoryTaskRuntime::new(effect),
                        sandbox_write_command(&write_output, b"safeclaw dispatch write under reads\n"),
                    ))
                },
                |_, _| unreachable!(),
            )
            .unwrap();

        assert_eq!(outcomes.len(), 1);
        match &outcomes[0] {
            WorkerLoopDispatchOutcome::Executed(executed) => {
                assert_eq!(executed.claim.task.task_id, "task-worker-dispatch-shared-write-after-reads");
                assert!(executed.completed);
                assert_eq!(executed.final_summary.worker_state, WorkerState::Succeeded);
                assert_eq!(executed.final_summary.effect_status, EffectStatus::Executed);
            }
            WorkerLoopDispatchOutcome::Probed(_) => panic!("same-scope write under reads must execute"),
            _ => panic!("unexpected parked dispatch outcome"),
        }
        assert_eq!(
            fs::read(&write_output).unwrap(),
            b"safeclaw dispatch write under reads\n"
        );
        assert_eq!(write_worker.queue_snapshot().queued_tasks.len(), 0);
        assert_eq!(write_worker.queue_snapshot().active_leases.len(), 2);

        let verify_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let restored = verify_store
            .load_runtime(
                "task-worker-dispatch-shared-write-after-reads",
                "effect-worker-dispatch-shared-write-after-reads",
            )
            .unwrap()
            .expect("same-scope write runtime must reload");
        assert_eq!(restored.worker_state, WorkerState::Succeeded);
        assert_eq!(restored.effect.status, EffectStatus::Executed);
    }

    #[test]
    fn worker_loop_dispatch_until_empty_claims_second_write_only_after_prior_write_under_reads_releases() {
        let temp = TempWorkspace::new("dispatch-scope-write-under-reads-release");
        let shared_scope = format!("scope:{}", temp.root.join("shared.txt").display());
        let second_write_output = temp.root.join("second-write-under-reads.txt");

        let mut orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-dispatch-shared-read-active-1",
                ScheduleIntent::read(shared_scope.clone()),
                0,
            ))
            .unwrap();
        orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-dispatch-shared-read-active-2",
                ScheduleIntent::read(shared_scope.clone()),
                1,
            ))
            .unwrap();
        orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-dispatch-shared-write-1",
                ScheduleIntent::write(shared_scope.clone()),
                2,
            ))
            .unwrap();
        orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-dispatch-shared-write-2",
                ScheduleIntent::write(shared_scope.clone()),
                3,
            ))
            .unwrap();

        let first_read = orchestrator.claim_next("worker-a", 0).unwrap().unwrap();
        assert_eq!(first_read.task.task_id, "task-worker-dispatch-shared-read-active-1");
        let second_read = orchestrator.claim_next("worker-b", 1).unwrap().unwrap();
        assert_eq!(second_read.task.task_id, "task-worker-dispatch-shared-read-active-2");
        let first_write = orchestrator.claim_next("worker-c", 2).unwrap().unwrap();
        assert_eq!(first_write.task.task_id, "task-worker-dispatch-shared-write-1");
        assert!(first_write.task.intent.requires_write);

        let blocked_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        let blocked_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut blocked_worker = SqliteSingleWorkerLoop::new(blocked_orchestrator, blocked_store);
        let blocked = blocked_worker
            .claim_and_dispatch_until_empty(
                "worker-d",
                3,
                PreflightDecision::Permit,
                |_| unreachable!(),
                |_| unreachable!(),
                |_, _| unreachable!(),
            )
            .unwrap();
        assert!(blocked.is_empty());

        orchestrator
            .complete(
                &first_write.task.task_id,
                &first_write.lease.lease_id,
                &first_write.lease.owner_id,
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

        let released = release_worker
            .claim_and_dispatch_until_empty(
                "worker-d",
                4,
                PreflightDecision::Permit,
                |claim| {
                    assert_eq!(claim.task.task_id, "task-worker-dispatch-shared-write-2");
                    Ok(String::from("effect-worker-dispatch-shared-write-2"))
                },
                |claim| {
                    assert_eq!(claim.task.task_id, "task-worker-dispatch-shared-write-2");
                    let effect = EffectRecord::new(
                        "effect-worker-dispatch-shared-write-2",
                        claim.task.task_id.clone(),
                        "trace-worker-dispatch-shared-write-2",
                        "intent-worker-dispatch-shared-write-2",
                        EffectActor::Worker,
                        EffectAction::FileWrite,
                        claim.task.intent.target_scope.clone(),
                        EffectTier::Tier1,
                        EffectReversibility::Rollbackable,
                        ProbeMode::Auto,
                    );
                    Ok((
                        InMemoryTaskRuntime::new(effect),
                        sandbox_write_command(&second_write_output, b"safeclaw dispatch second write under reads\n"),
                    ))
                },
                |_, _| unreachable!(),
            )
            .unwrap();

        assert_eq!(released.len(), 1);
        match &released[0] {
            WorkerLoopDispatchOutcome::Executed(executed) => {
                assert_eq!(executed.claim.task.task_id, "task-worker-dispatch-shared-write-2");
                assert!(executed.completed);
                assert_eq!(executed.final_summary.worker_state, WorkerState::Succeeded);
                assert_eq!(executed.final_summary.effect_status, EffectStatus::Executed);
            }
            WorkerLoopDispatchOutcome::Probed(_) => panic!("released second write must execute"),
            _ => panic!("unexpected parked dispatch outcome"),
        }
        assert_eq!(
            fs::read(&second_write_output).unwrap(),
            b"safeclaw dispatch second write under reads\n"
        );
        assert_eq!(release_worker.queue_snapshot().queued_tasks.len(), 0);
        assert_eq!(release_worker.queue_snapshot().active_leases.len(), 2);

        let verify_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let restored = verify_store
            .load_runtime(
                "task-worker-dispatch-shared-write-2",
                "effect-worker-dispatch-shared-write-2",
            )
            .unwrap()
            .expect("second write runtime must reload");
        assert_eq!(restored.worker_state, WorkerState::Succeeded);
        assert_eq!(restored.effect.status, EffectStatus::Executed);
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
    fn worker_loop_allows_same_scope_write_while_other_owners_hold_read_leases() {
        let temp = TempWorkspace::new("scope-write-under-reads");
        let shared_scope = format!("scope:{}", temp.root.join("shared.txt").display());
        let write_output = temp.root.join("write-under-reads.txt");

        let mut blocking_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-shared-read-active-1",
                ScheduleIntent::read(shared_scope.clone()),
                0,
            ))
            .unwrap();
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-shared-read-active-2",
                ScheduleIntent::read(shared_scope.clone()),
                1,
            ))
            .unwrap();
        blocking_orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-shared-write-after-reads",
                ScheduleIntent::write(shared_scope.clone()),
                2,
            ))
            .unwrap();

        let first_read = blocking_orchestrator.claim_next("worker-a", 0).unwrap().unwrap();
        assert_eq!(first_read.task.task_id, "task-worker-shared-read-active-1");
        assert!(!first_read.task.intent.requires_write);

        let second_read = blocking_orchestrator.claim_next("worker-b", 1).unwrap().unwrap();
        assert_eq!(second_read.task.task_id, "task-worker-shared-read-active-2");
        assert!(!second_read.task.intent.requires_write);

        let write_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        let write_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut write_worker = SqliteSingleWorkerLoop::new(write_orchestrator, write_store);

        let write_outcome = write_worker
            .claim_and_drive_once("worker-c", 2, PreflightDecision::Permit, |claim| {
                assert_eq!(claim.task.task_id, "task-worker-shared-write-after-reads");
                let effect = EffectRecord::new(
                    "effect-worker-shared-write-after-reads",
                    claim.task.task_id.clone(),
                    "trace-worker-shared-write-after-reads",
                    "intent-worker-shared-write-after-reads",
                    EffectActor::Worker,
                    EffectAction::FileWrite,
                    claim.task.intent.target_scope.clone(),
                    EffectTier::Tier1,
                    EffectReversibility::Rollbackable,
                    ProbeMode::Auto,
                );
                Ok((
                    InMemoryTaskRuntime::new(effect),
                    sandbox_write_command(&write_output, b"safeclaw write under reads\n"),
                ))
            })
            .unwrap()
            .expect("same-scope write must remain claimable under active reads");

        assert_eq!(write_outcome.claim.task.task_id, "task-worker-shared-write-after-reads");
        assert!(write_outcome.completed);
        assert_eq!(write_outcome.final_summary.worker_state, WorkerState::Succeeded);
        assert_eq!(write_outcome.final_summary.effect_status, EffectStatus::Executed);
        assert_eq!(fs::read(&write_output).unwrap(), b"safeclaw write under reads\n");
        assert_eq!(write_worker.queue_snapshot().queued_tasks.len(), 0);
        assert_eq!(write_worker.queue_snapshot().active_leases.len(), 2);

        let verify_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let restored = verify_store
            .load_runtime(
                "task-worker-shared-write-after-reads",
                "effect-worker-shared-write-after-reads",
            )
            .unwrap()
            .expect("same-scope write runtime must reload");
        assert_eq!(restored.worker_state, WorkerState::Succeeded);
        assert_eq!(restored.effect.status, EffectStatus::Executed);
    }

    #[test]
    fn worker_loop_claims_second_write_only_after_prior_write_under_reads_releases() {
        let temp = TempWorkspace::new("scope-write-under-reads-release");
        let shared_scope = format!("scope:{}", temp.root.join("shared.txt").display());
        let second_write_output = temp.root.join("second-write-under-reads.txt");

        let mut orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-shared-read-active-1",
                ScheduleIntent::read(shared_scope.clone()),
                0,
            ))
            .unwrap();
        orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-shared-read-active-2",
                ScheduleIntent::read(shared_scope.clone()),
                1,
            ))
            .unwrap();
        orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-shared-write-1",
                ScheduleIntent::write(shared_scope.clone()),
                2,
            ))
            .unwrap();
        orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-shared-write-2",
                ScheduleIntent::write(shared_scope.clone()),
                3,
            ))
            .unwrap();

        let first_read = orchestrator.claim_next("worker-a", 0).unwrap().unwrap();
        assert_eq!(first_read.task.task_id, "task-worker-shared-read-active-1");
        let second_read = orchestrator.claim_next("worker-b", 1).unwrap().unwrap();
        assert_eq!(second_read.task.task_id, "task-worker-shared-read-active-2");
        let first_write = orchestrator.claim_next("worker-c", 2).unwrap().unwrap();
        assert_eq!(first_write.task.task_id, "task-worker-shared-write-1");
        assert!(first_write.task.intent.requires_write);

        let blocked_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        let blocked_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut blocked_worker = SqliteSingleWorkerLoop::new(blocked_orchestrator, blocked_store);
        let blocked = blocked_worker
            .claim_and_drive_once("worker-d", 3, PreflightDecision::Permit, |_| unreachable!())
            .unwrap();
        assert!(blocked.is_none());

        orchestrator
            .complete(&first_write.task.task_id, &first_write.lease.lease_id, &first_write.lease.owner_id)
            .unwrap();

        let release_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        let release_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut release_worker = SqliteSingleWorkerLoop::new(release_orchestrator, release_store);

        let released = release_worker
            .claim_and_drive_once("worker-d", 4, PreflightDecision::Permit, |claim| {
                assert_eq!(claim.task.task_id, "task-worker-shared-write-2");
                let effect = EffectRecord::new(
                    "effect-worker-shared-write-2",
                    claim.task.task_id.clone(),
                    "trace-worker-shared-write-2",
                    "intent-worker-shared-write-2",
                    EffectActor::Worker,
                    EffectAction::FileWrite,
                    claim.task.intent.target_scope.clone(),
                    EffectTier::Tier1,
                    EffectReversibility::Rollbackable,
                    ProbeMode::Auto,
                );
                Ok((
                    InMemoryTaskRuntime::new(effect),
                    sandbox_write_command(&second_write_output, b"safeclaw second write under reads\n"),
                ))
            })
            .unwrap()
            .expect("second write must unblock after first write release");

        assert_eq!(released.claim.task.task_id, "task-worker-shared-write-2");
        assert!(released.completed);
        assert_eq!(released.final_summary.worker_state, WorkerState::Succeeded);
        assert_eq!(released.final_summary.effect_status, EffectStatus::Executed);
        assert_eq!(fs::read(&second_write_output).unwrap(), b"safeclaw second write under reads\n");
        assert_eq!(release_worker.queue_snapshot().queued_tasks.len(), 0);
        assert_eq!(release_worker.queue_snapshot().active_leases.len(), 2);

        let verify_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let restored = verify_store
            .load_runtime("task-worker-shared-write-2", "effect-worker-shared-write-2")
            .unwrap()
            .expect("second write runtime must reload");
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
    fn worker_loop_claims_persisted_uncertain_runtime_probes_and_completes() {
        let temp = TempWorkspace::new("persisted-probe");
        let expected_bytes = b"safeclaw persisted probe\n";
        let mut orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-persisted-probe",
                ScheduleIntent::write(format!("scope:{}", temp.output_path.display())),
                0,
            ))
            .unwrap();
        let claim = orchestrator.claim_next("worker-a", 0).unwrap().unwrap();

        let effect = EffectRecord::new(
            "effect-worker-persisted-probe",
            claim.task.task_id.clone(),
            "trace-worker-persisted-probe",
            "intent-worker-persisted-probe",
            EffectActor::Worker,
            EffectAction::FileWrite,
            claim.task.intent.target_scope.clone(),
            EffectTier::Tier1,
            EffectReversibility::Rollbackable,
            ProbeMode::Auto,
        );
        let mut runtime = InMemoryTaskRuntime::new(effect);
        runtime.begin_execution(PreflightDecision::Permit).unwrap();
        let executor = LocalSandboxExecutor::new();
        let (_, execution_summary) = executor
            .run_and_apply(
                &mut runtime,
                &sandbox_write_then_timeout_command(&temp.output_path, expected_bytes),
            )
            .unwrap();
        assert_eq!(execution_summary.worker_state, WorkerState::Uncertain);
        assert_eq!(execution_summary.effect_status, EffectStatus::Uncertain);

        let mut setup_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        setup_store
            .persist_runtime(
                &runtime,
                format!("worker-loop:{}:post-exec", claim.lease.lease_id),
                "test",
            )
            .unwrap();
        drop(setup_store);

        let probe_orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        let probe_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut probe_worker = SqliteSingleWorkerLoop::new(probe_orchestrator, probe_store);
        probe_worker.filesystem_probe_mut().register_expected_blake3(
            "effect-worker-persisted-probe",
            blake3::hash(expected_bytes).to_hex().to_string(),
        );

        let blocked = probe_worker
            .claim_and_probe_persisted_once("worker-b", 10, "effect-worker-persisted-probe")
            .unwrap();
        assert!(blocked.is_none());

        let recovered = probe_worker
            .claim_and_probe_persisted_once("worker-b", 26, "effect-worker-persisted-probe")
            .unwrap()
            .expect("expired uncertain runtime must be claimable for probe");
        assert_eq!(recovered.claim.task.task_id, "task-worker-persisted-probe");
        assert_eq!(recovered.recovered_from, WorkerState::Uncertain);
        assert_eq!(recovered.final_summary.worker_state, WorkerState::Succeeded);
        assert_eq!(recovered.final_summary.effect_status, EffectStatus::Executed);
        assert!(recovered.completed);
        assert!(probe_worker.queue_snapshot().queued_tasks.is_empty());
        assert!(probe_worker.queue_snapshot().active_leases.is_empty());
        assert_eq!(
            probe_worker.queue_snapshot().completed_task_ids,
            vec![String::from("task-worker-persisted-probe")]
        );

        let verify_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let restored = verify_store
            .load_runtime(
                "task-worker-persisted-probe",
                "effect-worker-persisted-probe",
            )
            .unwrap()
            .expect("persisted probe runtime must reload");
        assert_eq!(restored.worker_state, WorkerState::Succeeded);
        assert_eq!(restored.effect.status, EffectStatus::Executed);
    }

    #[test]
    fn worker_loop_probe_reports_missing_persisted_runtime() {
        let temp = TempWorkspace::new("missing-probe-runtime");
        let mut orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-missing-probe",
                ScheduleIntent::write(format!("scope:{}", temp.output_path.display())),
                0,
            ))
            .unwrap();
        let runtime_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let mut loop_driver = SqliteSingleWorkerLoop::new(orchestrator, runtime_store);

        let error = loop_driver
            .claim_and_probe_persisted_once("worker-a", 0, "effect-worker-missing-probe")
            .unwrap_err();
        match error {
            WorkerLoopError::PersistedRuntimeMissing { task_id, effect_id } => {
                assert_eq!(task_id, "task-worker-missing-probe");
                assert_eq!(effect_id, "effect-worker-missing-probe");
            }
            other => panic!("unexpected error: {other:?}"),
        }
        assert!(loop_driver.queue_snapshot().completed_task_ids.is_empty());
        assert_eq!(loop_driver.queue_snapshot().active_leases.len(), 1);
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
    fn worker_loop_resume_parks_confirmation_before_sandbox() {
        let temp = TempWorkspace::new("resume-confirmation");
        let mut loop_driver = SqliteSingleWorkerLoop::open(
            &temp.db_path,
            SqliteOpenOptions::default(),
        )
        .unwrap()
        .with_lease_ttl_ms(25);
        loop_driver
            .enqueue_task(OrchestratorTask::new(
                "task-worker-resume-confirmation",
                ScheduleIntent::write(format!("scope:{}", temp.output_path.display())),
                0,
            ))
            .unwrap();

        let outcome = loop_driver
            .claim_and_resume_once("worker-a", 0, |claim| {
                let effect = EffectRecord::new(
                    "effect-worker-resume-confirmation",
                    claim.task.task_id.clone(),
                    "trace-worker-resume-confirmation",
                    "intent-worker-resume-confirmation",
                    EffectActor::Worker,
                    EffectAction::FileWrite,
                    claim.task.intent.target_scope.clone(),
                    EffectTier::Tier1,
                    EffectReversibility::Rollbackable,
                    ProbeMode::Auto,
                );
                let mut runtime = InMemoryTaskRuntime::new(effect);
                let waiting = runtime.run_confirmation_checkpoint().unwrap();
                assert_eq!(waiting.worker_state, WorkerState::AwaitingConfirmation);
                Ok((runtime, sandbox_success_command()))
            })
            .unwrap()
            .expect("confirmation runtime must be parked on resume");

        assert_eq!(outcome.claim.task.task_id, "task-worker-resume-confirmation");
        assert_eq!(outcome.execution_summary.worker_state, WorkerState::AwaitingConfirmation);
        assert_eq!(outcome.execution_summary.effect_status, EffectStatus::Prepared);
        assert_eq!(outcome.final_summary.worker_state, WorkerState::AwaitingConfirmation);
        assert_eq!(outcome.final_summary.effect_status, EffectStatus::Prepared);
        assert_eq!(outcome.disposition, Some(WorkerLoopDisposition::QueueForConfirmation));
        assert!(!outcome.completed);
        assert_eq!(outcome.report.exit_code, None);
        assert_eq!(outcome.report.duration_ms, 0);
        assert!(!temp.output_path.exists());
        assert_eq!(loop_driver.queue_snapshot().active_leases.len(), 1);

        let verify_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let restored = verify_store
            .load_runtime("task-worker-resume-confirmation", "effect-worker-resume-confirmation")
            .unwrap()
            .expect("resume confirmation runtime must persist");
        assert_eq!(restored.worker_state, WorkerState::AwaitingConfirmation);
        assert_eq!(restored.effect.status, EffectStatus::Prepared);
        assert!(restored.attempts.is_empty());
    }

    #[test]
    fn worker_loop_resume_persisted_parks_confirmation_before_sandbox() {
        let temp = TempWorkspace::new("resume-persisted-confirmation");
        let mut orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-resume-persisted-confirmation",
                ScheduleIntent::write(format!("scope:{}", temp.output_path.display())),
                0,
            ))
            .unwrap();
        let effect = EffectRecord::new(
            "effect-worker-resume-persisted-confirmation",
            String::from("task-worker-resume-persisted-confirmation"),
            "trace-worker-resume-persisted-confirmation",
            "intent-worker-resume-persisted-confirmation",
            EffectActor::Worker,
            EffectAction::FileWrite,
            format!("scope:{}", temp.output_path.display()),
            EffectTier::Tier1,
            EffectReversibility::Rollbackable,
            ProbeMode::Auto,
        );
        let mut runtime = InMemoryTaskRuntime::new(effect);
        let waiting = runtime.run_confirmation_checkpoint().unwrap();
        assert_eq!(waiting.worker_state, WorkerState::AwaitingConfirmation);

        let mut store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        store
            .persist_runtime(
                &runtime,
                String::from("worker-loop:seed:resume-confirmation"),
                "test",
            )
            .unwrap();

        let mut resume_worker = SqliteSingleWorkerLoop::new(orchestrator, store).with_lease_ttl_ms(25);
        let outcome = resume_worker
            .claim_and_resume_persisted_once(
                "worker-a",
                0,
                "effect-worker-resume-persisted-confirmation",
                |_, _| unreachable!(),
            )
            .unwrap()
            .expect("persisted confirmation runtime must park on resume");

        assert_eq!(outcome.claim.task.task_id, "task-worker-resume-persisted-confirmation");
        assert_eq!(outcome.execution_summary.worker_state, WorkerState::AwaitingConfirmation);
        assert_eq!(outcome.final_summary.worker_state, WorkerState::AwaitingConfirmation);
        assert_eq!(outcome.disposition, Some(WorkerLoopDisposition::QueueForConfirmation));
        assert!(!outcome.completed);
        assert_eq!(outcome.report.exit_code, None);
        assert_eq!(outcome.report.duration_ms, 0);
        assert!(!temp.output_path.exists());
        assert_eq!(resume_worker.queue_snapshot().active_leases.len(), 1);
    }

    #[test]
    fn worker_loop_retry_parks_confirmation_before_sandbox() {
        let temp = TempWorkspace::new("retry-confirmation");
        let mut orchestrator = SqliteTaskOrchestrator::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        )
        .with_lease_ttl_ms(25);
        orchestrator
            .enqueue(OrchestratorTask::new(
                "task-worker-retry-confirmation",
                ScheduleIntent::write(format!("scope:{}", temp.output_path.display())),
                0,
            ))
            .unwrap();
        let effect = EffectRecord::new(
            "effect-worker-retry-confirmation",
            String::from("task-worker-retry-confirmation"),
            "trace-worker-retry-confirmation",
            "intent-worker-retry-confirmation",
            EffectActor::Worker,
            EffectAction::FileWrite,
            format!("scope:{}", temp.output_path.display()),
            EffectTier::Tier1,
            EffectReversibility::Rollbackable,
            ProbeMode::Auto,
        );
        let mut runtime = InMemoryTaskRuntime::new(effect);
        let failed = runtime.run_plan_failure().unwrap();
        assert_eq!(failed.worker_state, WorkerState::Failed);
        assert_eq!(failed.effect_status, EffectStatus::Prepared);

        let mut store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        store
            .persist_runtime(&runtime, String::from("worker-loop:seed:retry-failed"), "test")
            .unwrap();

        let mut retry_worker = SqliteSingleWorkerLoop::new(orchestrator, store).with_lease_ttl_ms(25);
        let outcome = retry_worker
            .claim_and_retry_failed_once(
                "worker-a",
                0,
                "effect-worker-retry-confirmation",
                PreflightDecision::NeedsConfirmation,
                |_, _| unreachable!(),
            )
            .unwrap()
            .expect("failed runtime must claim for confirmation retry");

        assert_eq!(outcome.claim.task.task_id, "task-worker-retry-confirmation");
        assert_eq!(outcome.execution_summary.worker_state, WorkerState::AwaitingConfirmation);
        assert_eq!(outcome.execution_summary.effect_status, EffectStatus::Prepared);
        assert_eq!(outcome.final_summary.worker_state, WorkerState::AwaitingConfirmation);
        assert_eq!(outcome.final_summary.effect_status, EffectStatus::Prepared);
        assert_eq!(outcome.disposition, Some(WorkerLoopDisposition::QueueForConfirmation));
        assert!(!outcome.completed);
        assert_eq!(outcome.report.exit_code, None);
        assert_eq!(outcome.report.duration_ms, 0);
        assert!(!outcome.report.timed_out);
        assert!(!temp.output_path.exists());
        assert_eq!(retry_worker.queue_snapshot().active_leases.len(), 1);
        assert!(retry_worker.queue_snapshot().completed_task_ids.is_empty());

        let verify_store = SqliteRuntimeStore::new(
            open_database(&temp.db_path, SqliteOpenOptions::default()).unwrap(),
        );
        let restored = verify_store
            .load_runtime(
                "task-worker-retry-confirmation",
                "effect-worker-retry-confirmation",
            )
            .unwrap()
            .expect("retry confirmation runtime must persist");
        assert_eq!(restored.worker_state, WorkerState::AwaitingConfirmation);
        assert_eq!(restored.effect.status, EffectStatus::Prepared);
        assert!(restored.attempts.is_empty());
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
