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
    SpecBinding { spec_path: "specs/schemas/effect_ledger.json", module_path: "safeclaw_core::effect_ledger", stage: ImplementationStage::RuntimeSlice, next_step: "继续扩外层 adapter 的持久化、审计与恢复编排" },
    SpecBinding { spec_path: "specs/state-machines/worker_lifecycle.json", module_path: "safeclaw_core::worker_lifecycle", stage: ImplementationStage::RuntimeSlice, next_step: "待接 doctor / sidecar / 外层 state adapter 编排" },
    SpecBinding { spec_path: "specs/schemas/task_concurrency.json", module_path: "safeclaw_core::task_concurrency", stage: ImplementationStage::RuntimeSlice, next_step: "继续扩 orchestrator / sidecar 队列调度策略" },
    SpecBinding { spec_path: "specs/schemas/task_concurrency.json", module_path: "safeclaw_core::scheduler", stage: ImplementationStage::RuntimeSlice, next_step: "已接 SQLite orchestrator；后续组装 sidecar queue 与真实 worker loop" },
    SpecBinding { spec_path: "specs/probes/file_write.json", module_path: "safeclaw_core::recovery::probes", stage: ImplementationStage::RuntimeSlice, next_step: "已接 safeclaw-sqlite 文件探针；后续扩 sidecar probe executor" },
    SpecBinding { spec_path: "specs/probes/file_delete.json", module_path: "safeclaw_core::recovery::probes", stage: ImplementationStage::RuntimeSlice, next_step: "已接 safeclaw-sqlite 文件探针；后续扩 sidecar probe executor" },
    SpecBinding { spec_path: "specs/probes/network_request.json", module_path: "safeclaw_core::recovery::probes", stage: ImplementationStage::TestSkeleton, next_step: "待接网络探针 adapter 与 sidecar 执行实现" },
];
