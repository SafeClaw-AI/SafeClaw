use std::collections::{HashMap, HashSet};

use crate::effect_ledger::{EffectStatus, ProbeState};
use crate::worker_lifecycle::WorkerState;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct StateEvent {
    pub state_event_id: String,
    pub task_id: String,
    pub worker_state: WorkerState,
    pub effect_status: EffectStatus,
    pub probe_state: Option<ProbeState>,
    pub fencing_token: u64,
    pub triggered_by: String,
    pub at: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct TaskSnapshot {
    pub task_id: String,
    pub worker_state: WorkerState,
    pub effect_status: EffectStatus,
    pub probe_state: Option<ProbeState>,
    pub last_state_event_id: String,
    pub fencing_token: u64,
    pub version: u64,
    pub updated_at: String,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum StateApplyResult {
    Applied,
    DuplicateIgnored,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum StateEngineError {
    StaleFencingToken { current: u64, provided: u64 },
    BackendUnavailable { operation: &'static str },
}

pub trait StateEngine {
    fn apply_event(&mut self, event: StateEvent) -> Result<StateApplyResult, StateEngineError>;

    fn load_snapshot(&self, task_id: &str) -> Result<Option<TaskSnapshot>, StateEngineError>;

    fn event_count(&self) -> usize {
        0
    }
}

#[derive(Clone, Debug, Default)]
pub struct InMemoryStateEngine {
    snapshots: HashMap<String, TaskSnapshot>,
    applied_event_ids: HashSet<String>,
    current_fencing_tokens: HashMap<String, u64>,
    events: Vec<StateEvent>,
}

pub type MockStateEngine = InMemoryStateEngine;

impl InMemoryStateEngine {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn snapshot(&self, task_id: &str) -> Option<&TaskSnapshot> {
        self.snapshots.get(task_id)
    }
}

impl StateEngine for InMemoryStateEngine {
    fn apply_event(&mut self, event: StateEvent) -> Result<StateApplyResult, StateEngineError> {
        if self.applied_event_ids.contains(&event.state_event_id) {
            return Ok(StateApplyResult::DuplicateIgnored);
        }

        let current_fencing_token = self
            .current_fencing_tokens
            .get(&event.task_id)
            .copied()
            .unwrap_or(0);
        if event.fencing_token < current_fencing_token {
            return Err(StateEngineError::StaleFencingToken {
                current: current_fencing_token,
                provided: event.fencing_token,
            });
        }

        let next_version = self
            .snapshots
            .get(&event.task_id)
            .map(|snapshot| snapshot.version + 1)
            .unwrap_or(1);
        let snapshot = TaskSnapshot {
            task_id: event.task_id.clone(),
            worker_state: event.worker_state,
            effect_status: event.effect_status,
            probe_state: event.probe_state,
            last_state_event_id: event.state_event_id.clone(),
            fencing_token: event.fencing_token,
            version: next_version,
            updated_at: event.at.clone(),
        };

        self.current_fencing_tokens
            .insert(event.task_id.clone(), event.fencing_token);
        self.applied_event_ids.insert(event.state_event_id.clone());
        self.events.push(event.clone());
        self.snapshots.insert(event.task_id, snapshot);
        Ok(StateApplyResult::Applied)
    }

    fn load_snapshot(&self, task_id: &str) -> Result<Option<TaskSnapshot>, StateEngineError> {
        Ok(self.snapshot(task_id).cloned())
    }

    fn event_count(&self) -> usize {
        self.events.len()
    }
}
