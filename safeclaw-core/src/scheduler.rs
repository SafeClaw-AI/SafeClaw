use crate::task_concurrency::{
    schedule_decision, GuardBlockReason, GuardDecision, ScopeClaim,
    TaskScheduleRequest,
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

#[derive(Clone, Debug, Default)]
pub struct InMemoryTaskScheduler {
    active_workers: usize,
    tool_busy: bool,
    active_claims: Vec<ScopeClaim>,
    quarantined_scopes: Vec<String>,
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
}

impl TaskScheduler for InMemoryTaskScheduler {
    fn admit(&mut self, intent: ScheduleIntent) -> Result<ScheduleTicket, SchedulerError> {
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
            if let Some(index) = self.active_claims.iter().position(|claim| {
                claim.scope == ticket.target_scope && claim.is_write
            }) {
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

#[cfg(test)]
mod tests {
    use super::{
        InMemoryTaskScheduler, ScheduleIntent, SchedulerError, TaskScheduler,
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
            .admit(
                ScheduleIntent::write("scope:/tmp/quarantined")
                    .with_doctor_bypass(),
            )
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
}
