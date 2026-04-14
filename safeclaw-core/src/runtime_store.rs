use std::collections::{HashMap, HashSet};

use crate::{InMemoryTaskRuntime, StateApplyResult};

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum RuntimeStoreError {
    BackendUnavailable { operation: &'static str },
    InvalidStoredValue { field: &'static str, value: String },
}

pub trait RuntimeStore {
    fn persist_runtime(
        &mut self,
        runtime: &InMemoryTaskRuntime,
        state_event_id: &str,
        triggered_by: &str,
    ) -> Result<StateApplyResult, RuntimeStoreError>;

    fn load_runtime(
        &self,
        task_id: &str,
        effect_id: &str,
    ) -> Result<Option<InMemoryTaskRuntime>, RuntimeStoreError>;
}

#[derive(Clone, Debug, Default)]
pub struct InMemoryRuntimeStore {
    runtimes_by_task: HashMap<String, InMemoryTaskRuntime>,
    state_event_ids: HashSet<String>,
}

pub type MockRuntimeStore = InMemoryRuntimeStore;

impl InMemoryRuntimeStore {
    pub fn new() -> Self {
        Self::default()
    }
}

impl RuntimeStore for InMemoryRuntimeStore {
    fn persist_runtime(
        &mut self,
        runtime: &InMemoryTaskRuntime,
        state_event_id: &str,
        _triggered_by: &str,
    ) -> Result<StateApplyResult, RuntimeStoreError> {
        if !self.state_event_ids.insert(state_event_id.to_string()) {
            return Ok(StateApplyResult::DuplicateIgnored);
        }

        self.runtimes_by_task
            .insert(runtime.effect.task_id.clone(), runtime.clone());
        Ok(StateApplyResult::Applied)
    }

    fn load_runtime(
        &self,
        task_id: &str,
        effect_id: &str,
    ) -> Result<Option<InMemoryTaskRuntime>, RuntimeStoreError> {
        match self.runtimes_by_task.get(task_id) {
            Some(runtime) if runtime.effect.effect_id == effect_id => Ok(Some(runtime.clone())),
            Some(_) => Err(RuntimeStoreError::InvalidStoredValue {
                field: "runtime_effect_id",
                value: effect_id.to_string(),
            }),
            None => Ok(None),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::{InMemoryRuntimeStore, RuntimeStore, RuntimeStoreError};
    use crate::{
        effect_ledger::{
            EffectAction, EffectActor, EffectRecord, EffectReversibility, EffectStatus, EffectTier,
            ProbeMode,
        },
        ExecutionDisposition, InMemoryTaskRuntime, PreflightDecision, StateApplyResult,
    };

    #[test]
    fn runtime_store_roundtrips_runtime_and_deduplicates_state_event() {
        let effect = demo_effect("effect-runtime-store", "task-runtime-store");
        let mut runtime = InMemoryTaskRuntime::new(effect);
        runtime
            .run_minimal_flow(PreflightDecision::Permit, ExecutionDisposition::Crash)
            .unwrap();

        let mut store = InMemoryRuntimeStore::new();
        assert_eq!(
            store
                .persist_runtime(&runtime, "evt-runtime-1", "runtime-store")
                .unwrap(),
            StateApplyResult::Applied
        );
        assert_eq!(
            store
                .persist_runtime(&runtime, "evt-runtime-1", "runtime-store")
                .unwrap(),
            StateApplyResult::DuplicateIgnored
        );

        let restored = store
            .load_runtime("task-runtime-store", "effect-runtime-store")
            .unwrap()
            .unwrap();
        assert_eq!(restored.worker_state, runtime.worker_state);
        assert_eq!(restored.effect.status, EffectStatus::Uncertain);
        assert_eq!(restored.attempts, runtime.attempts);
    }

    #[test]
    fn runtime_store_surfaces_effect_id_mismatch() {
        let effect = demo_effect("effect-runtime-mismatch", "task-runtime-mismatch");
        let runtime = InMemoryTaskRuntime::new(effect);
        let mut store = InMemoryRuntimeStore::new();
        store
            .persist_runtime(&runtime, "evt-runtime-2", "runtime-store")
            .unwrap();

        assert_eq!(
            store.load_runtime("task-runtime-mismatch", "effect-other"),
            Err(RuntimeStoreError::InvalidStoredValue {
                field: "runtime_effect_id",
                value: String::from("effect-other"),
            })
        );
    }

    fn demo_effect(effect_id: &str, task_id: &str) -> EffectRecord {
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
            ProbeMode::Auto,
        )
    }
}
