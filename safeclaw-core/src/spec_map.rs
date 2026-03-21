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
    SpecBinding { spec_path: "specs/state-machines/worker_lifecycle.json", module_path: "safeclaw_core::worker_lifecycle", stage: ImplementationStage::RuntimeSlice, next_step: "已接 runtime store / worker loop；后续补 doctor / sidecar service 编排" },
    SpecBinding { spec_path: "specs/schemas/task_concurrency.json", module_path: "safeclaw_core::task_concurrency", stage: ImplementationStage::RuntimeSlice, next_step: "已接 SQLite claim 侧同 scope 写冲突跳过 / same-scope read 透传；后续扩 sidecar 队列调度策略与多 worker 协调" },
    SpecBinding { spec_path: "specs/schemas/task_concurrency.json", module_path: "safeclaw_core::scheduler", stage: ImplementationStage::RuntimeSlice, next_step: "已接 SQLite orchestrator、真实 worker loop、scope 协调、orchestrator / worker_loop read fanout、batch short-circuit、batch conflict、batch release、resume conflict、resume release、retry conflict 与 retry release 示例；后续扩 sidecar queue / 多 worker 协调" },
    SpecBinding { spec_path: "specs/probes/file_write.json", module_path: "safeclaw_core::recovery::probes", stage: ImplementationStage::RuntimeSlice, next_step: "已接 safeclaw-sqlite 真实文件探针；后续扩 sidecar probe executor / richer evidence" },
    SpecBinding { spec_path: "specs/probes/file_delete.json", module_path: "safeclaw_core::recovery::probes", stage: ImplementationStage::RuntimeSlice, next_step: "已接 safeclaw-sqlite 真实文件探针；后续扩 sidecar probe executor / richer evidence" },
    SpecBinding { spec_path: "specs/probes/network_request.json", module_path: "safeclaw_core::recovery::probes", stage: ImplementationStage::RuntimeSlice, next_step: "已接 safeclaw-sqlite 本地 HTTP probe；后续扩 sidecar / HTTPS / richer evidence" },
];
