use std::collections::{HashMap, VecDeque};

use crate::task_concurrency::{
    schedule_decision, GuardBlockReason, GuardDecision, ScopeClaim, TaskScheduleRequest,
};

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ScheduleIntent {
    pub target_scope: String,
    pub requires_write: bool,
    pub doctor_bypass: bool,
}

impl ScheduleIntent {
    pub fn write(target_scope: impl Into<String>) -> Self {
        Self {
            target_scope: target_scope.into(),
            requires_write: true,
            doctor_bypass: false,
        }
    }

    pub fn read(target_scope: impl Into<String>) -> Self {
        Self {
            target_scope: target_scope.into(),
            requires_write: false,
            doctor_bypass: false,
        }
    }

    pub fn with_doctor_bypass(mut self) -> Self {
        self.doctor_bypass = true;
        self
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ScheduleTicket {
    pub worker_slot: usize,
    pub target_scope: String,
    pub requires_write: bool,
    pub doctor_bypass: bool,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SchedulerSnapshot {
    pub active_workers: usize,
    pub tool_busy: bool,
    pub active_claims: Vec<ScopeClaim>,
    pub quarantined_scopes: Vec<String>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SchedulerError {
    GuardBlocked(GuardBlockReason),
    WorkerUnderflow,
}

pub trait TaskScheduler {
    fn admit(&mut self, intent: ScheduleIntent) -> Result<ScheduleTicket, SchedulerError>;
    fn release(&mut self, ticket: &ScheduleTicket) -> Result<(), SchedulerError>;
    fn quarantine_scope(&mut self, scope: impl Into<String>);
    fn release_quarantine(&mut self, scope: &str);
    fn snapshot(&self) -> SchedulerSnapshot;
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct OrchestratorTask {
    pub task_id: String,
    pub intent: ScheduleIntent,
    pub enqueued_at_ms: u64,
}

impl OrchestratorTask {
    pub fn new(task_id: impl Into<String>, intent: ScheduleIntent, enqueued_at_ms: u64) -> Self {
        Self {
            task_id: task_id.into(),
            intent,
            enqueued_at_ms,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct OrchestratorLease {
    pub lease_id: String,
    pub task_id: String,
    pub owner_id: String,
    pub fencing_token: u64,
    pub ttl_ms: u64,
    pub expires_at_ms: u64,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct OrchestratorClaim {
    pub task: OrchestratorTask,
    pub lease: OrchestratorLease,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct OrchestratorSnapshot {
    pub queued_tasks: Vec<OrchestratorTask>,
    pub active_leases: Vec<OrchestratorLease>,
    pub completed_task_ids: Vec<String>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum OrchestratorError {
    BackendUnavailable {
        operation: &'static str,
    },
    TaskAlreadyQueued {
        task_id: String,
    },
    TaskAlreadyCompleted {
        task_id: String,
    },
    LeaseNotFound {
        task_id: String,
        lease_id: String,
    },
    LeaseNotOwned {
        task_id: String,
        lease_id: String,
        owner_id: String,
    },
    LeaseExpired {
        task_id: String,
        lease_id: String,
        now_ms: u64,
        expires_at_ms: u64,
    },
}

pub trait TaskOrchestrator {
    fn enqueue(&mut self, task: OrchestratorTask) -> Result<(), OrchestratorError>;
    fn claim_next(
        &mut self,
        owner_id: impl Into<String>,
        now_ms: u64,
    ) -> Result<Option<OrchestratorClaim>, OrchestratorError>;
    fn renew_lease(
        &mut self,
        task_id: &str,
        lease_id: &str,
        owner_id: &str,
        now_ms: u64,
    ) -> Result<OrchestratorLease, OrchestratorError>;
    fn reap_expired_leases(
        &mut self,
        now_ms: u64,
    ) -> Result<Vec<OrchestratorLease>, OrchestratorError>;
    fn complete(
        &mut self,
        task_id: &str,
        lease_id: &str,
        owner_id: &str,
    ) -> Result<(), OrchestratorError>;
    fn queue_snapshot(&self) -> OrchestratorSnapshot;
}

#[derive(Clone, Debug)]
pub struct InMemoryTaskScheduler {
    max_workers: usize,
    active_workers: usize,
    tool_busy: bool,
    active_claims: Vec<ScopeClaim>,
    quarantined_scopes: Vec<String>,
}

impl Default for InMemoryTaskScheduler {
    fn default() -> Self {
        Self {
            max_workers: 100,
            active_workers: 0,
            tool_busy: false,
            active_claims: Vec::new(),
            quarantined_scopes: Vec::new(),
        }
    }
}

pub type MockTaskScheduler = InMemoryTaskScheduler;

impl InMemoryTaskScheduler {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn with_active_workers(mut self, active_workers: usize) -> Self {
        self.active_workers = active_workers;
        self
    }

    pub fn with_max_workers(mut self, max_workers: usize) -> Self {
        self.max_workers = max_workers;
        self
    }
}

impl TaskScheduler for InMemoryTaskScheduler {
    fn admit(&mut self, intent: ScheduleIntent) -> Result<ScheduleTicket, SchedulerError> {
        // Apply an optional scheduler-local pool cap before protocol-level guards run.
        if self.active_workers >= self.max_workers {
            return Err(SchedulerError::GuardBlocked(
                GuardBlockReason::WorkerPoolFull,
            ));
        }

        let request = TaskScheduleRequest {
            active_workers: self.active_workers,
            tool_busy: self.tool_busy,
            target_scope: intent.target_scope.clone(),
            requires_write: intent.requires_write,
            doctor_bypass: intent.doctor_bypass,
        };

        match schedule_decision(&request, &self.active_claims, &self.quarantined_scopes) {
            GuardDecision::Allowed => {
                self.active_workers += 1;
                self.tool_busy = true;
                if intent.requires_write {
                    self.active_claims
                        .push(ScopeClaim::write(intent.target_scope.clone()));
                }
                Ok(ScheduleTicket {
                    worker_slot: self.active_workers,
                    target_scope: intent.target_scope,
                    requires_write: intent.requires_write,
                    doctor_bypass: intent.doctor_bypass,
                })
            }
            GuardDecision::Blocked(reason) => Err(SchedulerError::GuardBlocked(reason)),
        }
    }

    fn release(&mut self, ticket: &ScheduleTicket) -> Result<(), SchedulerError> {
        if self.active_workers == 0 {
            return Err(SchedulerError::WorkerUnderflow);
        }

        self.active_workers -= 1;
        self.tool_busy = false;
        if ticket.requires_write {
            if let Some(index) = self
                .active_claims
                .iter()
                .position(|claim| claim.scope == ticket.target_scope && claim.is_write)
            {
                self.active_claims.remove(index);
            }
        }
        Ok(())
    }

    fn quarantine_scope(&mut self, scope: impl Into<String>) {
        let scope = scope.into();
        if !self.quarantined_scopes.iter().any(|item| item == &scope) {
            self.quarantined_scopes.push(scope);
        }
    }

    fn release_quarantine(&mut self, scope: &str) {
        self.quarantined_scopes.retain(|item| item != scope);
    }

    fn snapshot(&self) -> SchedulerSnapshot {
        SchedulerSnapshot {
            active_workers: self.active_workers,
            tool_busy: self.tool_busy,
            active_claims: self.active_claims.clone(),
            quarantined_scopes: self.quarantined_scopes.clone(),
        }
    }
}

#[derive(Clone, Debug)]
pub struct InMemoryTaskOrchestrator {
    lease_ttl_ms: u64,
    next_lease_seq: u64,
    queued_tasks: VecDeque<OrchestratorTask>,
    active_claims: HashMap<String, OrchestratorClaim>,
    completed_task_ids: Vec<String>,
    next_fencing_token_by_task: HashMap<String, u64>,
}

pub type MockTaskOrchestrator = InMemoryTaskOrchestrator;

impl Default for InMemoryTaskOrchestrator {
    fn default() -> Self {
        Self {
            lease_ttl_ms: 30_000,
            next_lease_seq: 0,
            queued_tasks: VecDeque::new(),
            active_claims: HashMap::new(),
            completed_task_ids: Vec::new(),
            next_fencing_token_by_task: HashMap::new(),
        }
    }
}

impl InMemoryTaskOrchestrator {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn with_lease_ttl_ms(mut self, lease_ttl_ms: u64) -> Self {
        self.lease_ttl_ms = lease_ttl_ms;
        self
    }
}

impl TaskOrchestrator for InMemoryTaskOrchestrator {
    fn enqueue(&mut self, task: OrchestratorTask) -> Result<(), OrchestratorError> {
        let task_id = task.task_id.clone();
        if self
            .completed_task_ids
            .iter()
            .any(|completed| completed == &task_id)
        {
            return Err(OrchestratorError::TaskAlreadyCompleted { task_id });
        }
        if self
            .queued_tasks
            .iter()
            .any(|queued| queued.task_id == task_id)
            || self.active_claims.contains_key(&task_id)
        {
            return Err(OrchestratorError::TaskAlreadyQueued { task_id });
        }
        self.queued_tasks.push_back(task);
        Ok(())
    }

    fn claim_next(
        &mut self,
        owner_id: impl Into<String>,
        now_ms: u64,
    ) -> Result<Option<OrchestratorClaim>, OrchestratorError> {
        self.reap_expired_leases(now_ms)?;

        let Some(task) = self.queued_tasks.pop_front() else {
            return Ok(None);
        };

        let owner_id = owner_id.into();
        let fencing_token = {
            let next = self
                .next_fencing_token_by_task
                .entry(task.task_id.clone())
                .or_insert(0);
            *next += 1;
            *next
        };
        self.next_lease_seq += 1;

        let claim = OrchestratorClaim {
            lease: OrchestratorLease {
                lease_id: format!("{}-lease-{}", task.task_id, self.next_lease_seq),
                task_id: task.task_id.clone(),
                owner_id,
                fencing_token,
                ttl_ms: self.lease_ttl_ms,
                expires_at_ms: now_ms.saturating_add(self.lease_ttl_ms),
            },
            task,
        };
        self.active_claims
            .insert(claim.task.task_id.clone(), claim.clone());
        Ok(Some(claim))
    }

    fn renew_lease(
        &mut self,
        task_id: &str,
        lease_id: &str,
        owner_id: &str,
        now_ms: u64,
    ) -> Result<OrchestratorLease, OrchestratorError> {
        let claim = self.active_claims.get_mut(task_id).ok_or_else(|| {
            OrchestratorError::LeaseNotFound {
                task_id: task_id.to_string(),
                lease_id: lease_id.to_string(),
            }
        })?;

        if claim.lease.lease_id != lease_id {
            return Err(OrchestratorError::LeaseNotFound {
                task_id: task_id.to_string(),
                lease_id: lease_id.to_string(),
            });
        }
        if claim.lease.owner_id != owner_id {
            return Err(OrchestratorError::LeaseNotOwned {
                task_id: task_id.to_string(),
                lease_id: lease_id.to_string(),
                owner_id: owner_id.to_string(),
            });
        }
        if now_ms > claim.lease.expires_at_ms {
            return Err(OrchestratorError::LeaseExpired {
                task_id: task_id.to_string(),
                lease_id: lease_id.to_string(),
                now_ms,
                expires_at_ms: claim.lease.expires_at_ms,
            });
        }

        claim.lease.expires_at_ms = now_ms.saturating_add(claim.lease.ttl_ms);
        Ok(claim.lease.clone())
    }

    fn reap_expired_leases(
        &mut self,
        now_ms: u64,
    ) -> Result<Vec<OrchestratorLease>, OrchestratorError> {
        let expired_task_ids = self
            .active_claims
            .iter()
            .filter_map(|(task_id, claim)| {
                (now_ms > claim.lease.expires_at_ms).then(|| task_id.clone())
            })
            .collect::<Vec<_>>();

        let mut expired = Vec::new();
        for task_id in expired_task_ids {
            if let Some(claim) = self.active_claims.remove(&task_id) {
                expired.push(claim.lease.clone());
                self.queued_tasks.push_back(claim.task);
            }
        }
        Ok(expired)
    }

    fn complete(
        &mut self,
        task_id: &str,
        lease_id: &str,
        owner_id: &str,
    ) -> Result<(), OrchestratorError> {
        let claim =
            self.active_claims
                .get(task_id)
                .ok_or_else(|| OrchestratorError::LeaseNotFound {
                    task_id: task_id.to_string(),
                    lease_id: lease_id.to_string(),
                })?;

        if claim.lease.lease_id != lease_id {
            return Err(OrchestratorError::LeaseNotFound {
                task_id: task_id.to_string(),
                lease_id: lease_id.to_string(),
            });
        }
        if claim.lease.owner_id != owner_id {
            return Err(OrchestratorError::LeaseNotOwned {
                task_id: task_id.to_string(),
                lease_id: lease_id.to_string(),
                owner_id: owner_id.to_string(),
            });
        }

        self.active_claims.remove(task_id);
        if !self
            .completed_task_ids
            .iter()
            .any(|completed| completed == task_id)
        {
            self.completed_task_ids.push(task_id.to_string());
        }
        Ok(())
    }

    fn queue_snapshot(&self) -> OrchestratorSnapshot {
        let mut active_leases = self
            .active_claims
            .values()
            .map(|claim| claim.lease.clone())
            .collect::<Vec<_>>();
        active_leases.sort_by(|left, right| {
            left.task_id
                .cmp(&right.task_id)
                .then(left.fencing_token.cmp(&right.fencing_token))
        });

        let mut completed_task_ids = self.completed_task_ids.clone();
        completed_task_ids.sort();

        OrchestratorSnapshot {
            queued_tasks: self.queued_tasks.iter().cloned().collect(),
            active_leases,
            completed_task_ids,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::{
        InMemoryTaskOrchestrator, InMemoryTaskScheduler, OrchestratorError, OrchestratorTask,
        ScheduleIntent, SchedulerError, TaskOrchestrator, TaskScheduler,
    };
    use crate::task_concurrency::GuardBlockReason;

    #[test]
    fn scheduler_admit_marks_tool_busy_until_release() {
        let mut scheduler = InMemoryTaskScheduler::new();
        let ticket = scheduler
            .admit(ScheduleIntent::write("scope:/tmp/demo.txt"))
            .unwrap();
        let snapshot = scheduler.snapshot();
        assert_eq!(snapshot.active_workers, 1);
        assert!(snapshot.tool_busy);
        assert_eq!(snapshot.active_claims.len(), 1);

        assert_eq!(
            scheduler.admit(ScheduleIntent::read("scope:/tmp/other.txt")),
            Err(SchedulerError::GuardBlocked(GuardBlockReason::ToolBusy))
        );

        scheduler.release(&ticket).unwrap();
        let released = scheduler.snapshot();
        assert_eq!(released.active_workers, 0);
        assert!(!released.tool_busy);
        assert!(released.active_claims.is_empty());
    }

    #[test]
    fn scheduler_respects_quarantine_unless_doctor_bypass_is_present() {
        let mut scheduler = InMemoryTaskScheduler::new();
        scheduler.quarantine_scope("scope:/tmp/quarantined");

        assert_eq!(
            scheduler.admit(ScheduleIntent::write("scope:/tmp/quarantined")),
            Err(SchedulerError::GuardBlocked(
                GuardBlockReason::ScopeQuarantined,
            ))
        );

        let ticket = scheduler
            .admit(ScheduleIntent::write("scope:/tmp/quarantined").with_doctor_bypass())
            .unwrap();
        assert_eq!(ticket.target_scope, "scope:/tmp/quarantined");
        scheduler.release(&ticket).unwrap();
        scheduler.release_quarantine("scope:/tmp/quarantined");
        assert!(scheduler.snapshot().quarantined_scopes.is_empty());
    }

    #[test]
    fn scheduler_reports_underflow_on_extra_release() {
        let mut scheduler = InMemoryTaskScheduler::new();
        assert_eq!(
            scheduler.release(&super::ScheduleTicket {
                worker_slot: 1,
                target_scope: String::from("scope:/tmp/missing"),
                requires_write: true,
                doctor_bypass: false,
            }),
            Err(SchedulerError::WorkerUnderflow)
        );
    }

    #[test]
    fn scheduler_can_use_stricter_worker_pool_cap_than_protocol_limit() {
        let mut scheduler = InMemoryTaskScheduler::new()
            .with_active_workers(1)
            .with_max_workers(1);

        assert_eq!(
            scheduler.admit(ScheduleIntent::read("scope:/tmp/pool-cap")),
            Err(SchedulerError::GuardBlocked(
                GuardBlockReason::WorkerPoolFull,
            ))
        );
    }

    #[test]
    fn orchestrator_claims_tasks_and_renews_active_leases() {
        let mut orchestrator = InMemoryTaskOrchestrator::new().with_lease_ttl_ms(25);
        orchestrator
            .enqueue(OrchestratorTask::new(
                "task-1",
                ScheduleIntent::write("scope:/tmp/task-1"),
                0,
            ))
            .unwrap();
        orchestrator
            .enqueue(OrchestratorTask::new(
                "task-2",
                ScheduleIntent::read("scope:/tmp/task-2"),
                1,
            ))
            .unwrap();

        let claim = orchestrator.claim_next("orch-a", 10).unwrap().unwrap();
        assert_eq!(claim.task.task_id, "task-1");
        assert_eq!(claim.lease.fencing_token, 1);
        assert_eq!(claim.lease.expires_at_ms, 35);

        let renewed = orchestrator
            .renew_lease(&claim.task.task_id, &claim.lease.lease_id, "orch-a", 20)
            .unwrap();
        assert_eq!(renewed.expires_at_ms, 45);

        let snapshot = orchestrator.queue_snapshot();
        assert_eq!(snapshot.queued_tasks.len(), 1);
        assert_eq!(snapshot.queued_tasks[0].task_id, "task-2");
        assert_eq!(snapshot.active_leases.len(), 1);
        assert_eq!(snapshot.active_leases[0].task_id, "task-1");
    }

    #[test]
    fn orchestrator_reaps_expired_leases_and_requeues_tasks() {
        let mut orchestrator = InMemoryTaskOrchestrator::new().with_lease_ttl_ms(10);
        orchestrator
            .enqueue(OrchestratorTask::new(
                "task-expire",
                ScheduleIntent::write("scope:/tmp/task-expire"),
                0,
            ))
            .unwrap();

        let claim = orchestrator.claim_next("orch-a", 0).unwrap().unwrap();
        let expired = orchestrator.reap_expired_leases(11).unwrap();
        assert_eq!(expired, vec![claim.lease.clone()]);

        let reclaimed = orchestrator.claim_next("orch-b", 12).unwrap().unwrap();
        assert_eq!(reclaimed.task.task_id, "task-expire");
        assert_eq!(reclaimed.lease.owner_id, "orch-b");
        assert_eq!(reclaimed.lease.fencing_token, 2);
    }

    #[test]
    fn orchestrator_complete_marks_task_done_and_rejects_wrong_owner() {
        let mut orchestrator = InMemoryTaskOrchestrator::new();
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
            orchestrator.queue_snapshot().completed_task_ids,
            vec![String::from("task-done")]
        );
    }
}
