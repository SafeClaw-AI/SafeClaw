use std::collections::HashMap;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct BudgetEntry {
    pub task_id: String,
    pub allocated: u64,
    pub refunded: u64,
    pub status: BudgetStatus,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum BudgetStatus {
    Reserved,
    Charged,
    Refunded,
    Disputed,
}

#[derive(Clone, Debug, Default)]
pub struct BudgetLedger {
    entries: HashMap<String, BudgetEntry>,
}

impl BudgetLedger {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn reserve(&mut self, task_id: impl Into<String>, amount: u64) -> &mut BudgetEntry {
        let task_id = task_id.into();
        let entry = BudgetEntry {
            task_id: task_id.clone(),
            allocated: amount,
            refunded: 0,
            status: BudgetStatus::Reserved,
        };
        self.entries.insert(task_id.clone(), entry);
        self.entries.get_mut(&task_id).unwrap()
    }

    pub fn charge(&mut self, task_id: &str) -> Result<(), BudgetError> {
        let entry = self.entries.get_mut(task_id).ok_or(BudgetError::NotFound)?;
        if entry.status != BudgetStatus::Reserved {
            return Err(BudgetError::InvalidTransition {
                from: entry.status,
                to: BudgetStatus::Charged,
            });
        }
        entry.status = BudgetStatus::Charged;
        Ok(())
    }

    pub fn refund(&mut self, task_id: &str) -> Result<u64, BudgetError> {
        let entry = self.entries.get_mut(task_id).ok_or(BudgetError::NotFound)?;
        if entry.status == BudgetStatus::Reserved || entry.status == BudgetStatus::Charged {
            entry.refunded = entry.allocated;
            entry.status = BudgetStatus::Refunded;
            Ok(entry.allocated)
        } else if entry.status == BudgetStatus::Refunded {
            Ok(0)
        } else {
            Err(BudgetError::InvalidTransition {
                from: entry.status,
                to: BudgetStatus::Refunded,
            })
        }
    }

    pub fn dispute(&mut self, task_id: &str) -> Result<(), BudgetError> {
        let entry = self.entries.get_mut(task_id).ok_or(BudgetError::NotFound)?;
        if entry.status == BudgetStatus::Reserved || entry.status == BudgetStatus::Charged {
            entry.status = BudgetStatus::Disputed;
            Ok(())
        } else {
            Err(BudgetError::InvalidTransition {
                from: entry.status,
                to: BudgetStatus::Disputed,
            })
        }
    }

    pub fn get(&self, task_id: &str) -> Option<&BudgetEntry> {
        self.entries.get(task_id)
    }

    pub fn allocated_total(&self) -> u64 {
        self.entries.values().map(|e| e.allocated).sum()
    }

    pub fn refunded_total(&self) -> u64 {
        self.entries.values().map(|e| e.refunded).sum()
    }

    pub fn net_outstanding(&self) -> u64 {
        self.allocated_total() - self.refunded_total()
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum BudgetError {
    NotFound,
    InvalidTransition { from: BudgetStatus, to: BudgetStatus },
}

#[cfg(test)]
mod tests {
    use super::{BudgetLedger, BudgetStatus, BudgetError};

    #[test]
    fn reserve_and_charge() {
        let mut ledger = BudgetLedger::new();
        ledger.reserve("task-1", 100);
        assert_eq!(ledger.get("task-1").unwrap().status, BudgetStatus::Reserved);
        assert_eq!(ledger.net_outstanding(), 100);

        ledger.charge("task-1").unwrap();
        assert_eq!(ledger.get("task-1").unwrap().status, BudgetStatus::Charged);
        assert_eq!(ledger.net_outstanding(), 100);
    }

    #[test]
    fn refund_returns_preallocated_amount() {
        let mut ledger = BudgetLedger::new();
        ledger.reserve("task-1", 100);
        let refunded = ledger.refund("task-1").unwrap();
        assert_eq!(refunded, 100);
        assert_eq!(ledger.get("task-1").unwrap().status, BudgetStatus::Refunded);
        assert_eq!(ledger.refunded_total(), 100);
        assert_eq!(ledger.net_outstanding(), 0);
    }

    #[test]
    fn cannot_charge_after_refund() {
        let mut ledger = BudgetLedger::new();
        ledger.reserve("task-1", 100);
        ledger.refund("task-1").unwrap();
        let err = ledger.charge("task-1").unwrap_err();
        assert!(matches!(err, BudgetError::InvalidTransition { .. }));
    }

    #[test]
    fn dispute_marks_transaction() {
        let mut ledger = BudgetLedger::new();
        ledger.reserve("task-1", 100);
        ledger.dispute("task-1").unwrap();
        assert_eq!(ledger.get("task-1").unwrap().status, BudgetStatus::Disputed);
    }

    #[test]
    fn multiple_tasks_track_independently() {
        let mut ledger = BudgetLedger::new();
        ledger.reserve("task-1", 100);
        ledger.reserve("task-2", 50);
        ledger.charge("task-1").unwrap();
        ledger.refund("task-2").unwrap();

        assert_eq!(ledger.get("task-1").unwrap().status, BudgetStatus::Charged);
        assert_eq!(ledger.get("task-2").unwrap().status, BudgetStatus::Refunded);
        assert_eq!(ledger.allocated_total(), 150);
        assert_eq!(ledger.refunded_total(), 50);
        assert_eq!(ledger.net_outstanding(), 100);
    }
}
