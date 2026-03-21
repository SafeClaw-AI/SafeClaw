#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ImplementationStage { Planned, TestSkeleton, RuntimeSlice, Full }

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct SpecBinding {
    pub spec_path: &'static str,
    pub module_path: &'static str,
    pub stage: ImplementationStage,
    pub next_step: &'static str,
}

pub const CORE_SPEC_BINDINGS: [SpecBinding; 7] = [
    SpecBinding { spec_path: "specs/schemas/effect_ledger.json", module_path: "safeclaw_core::effect_ledger", stage: ImplementationStage::RuntimeSlice, next_step: "待接外层 adapter 的状态持久化实现" },
    SpecBinding { spec_path: "specs/state-machines/worker_lifecycle.json", module_path: "safeclaw_core::worker_lifecycle", stage: ImplementationStage::RuntimeSlice, next_step: "待接 doctor / 外层 state adapter 编排" },
    SpecBinding { spec_path: "specs/schemas/task_concurrency.json", module_path: "safeclaw_core::task_concurrency", stage: ImplementationStage::RuntimeSlice, next_step: "待接 orchestrator / sidecar 队列调度" },
    SpecBinding { spec_path: "specs/schemas/task_concurrency.json", module_path: "safeclaw_core::scheduler", stage: ImplementationStage::TestSkeleton, next_step: "待接外层 orchestrator / sidecar queue 实现" },
    SpecBinding { spec_path: "specs/probes/file_write.json", module_path: "safeclaw_core::recovery::probes", stage: ImplementationStage::TestSkeleton, next_step: "待接外层 probe adapter 执行实现" },
    SpecBinding { spec_path: "specs/probes/file_delete.json", module_path: "safeclaw_core::recovery::probes", stage: ImplementationStage::TestSkeleton, next_step: "待接外层 probe adapter 执行实现" },
    SpecBinding { spec_path: "specs/probes/network_request.json", module_path: "safeclaw_core::recovery::probes", stage: ImplementationStage::TestSkeleton, next_step: "待接外层 probe adapter 执行实现" },
];
