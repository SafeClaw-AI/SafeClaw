# safeclaw-core 架构梳理

> 本文件属于 L2 架构说明，用来解释 `safeclaw-core` 的当前模块边界。
> 协议真源仍以 `specs/`、`VERSION` 与治理真源文档为准，不以本文件反向定义字段或状态。

## 当前文件树

```text
safeclaw-core/
  Cargo.toml
  README.md
  ARCHITECTURE.md
  src/
    lib.rs
    budget.rs
    protocol.rs
    effect_ledger.rs
    fsync_trust.rs
    worker_lifecycle.rs
    task_concurrency.rs
    scheduler.rs
    state_engine.rs
    runtime_store.rs
    spec_map.rs
    recovery/
      mod.rs
      probes.rs
  tests/
    protocol_contracts.rs
```

## 模块与真源映射

| Rust 模块 | 对应真源 | 当前阶段 | 说明 |
|---|---|---|---|
| `protocol` | `VERSION` | 已锚定 | Rust 入口统一读取仓库协议版本 |
| `budget` | 当前无独立冻结 spec；与 `effect_ledger` / `task_concurrency` 的运行时治理约束相关 | Runtime Utility | 负责预扣减、退款、争议等预算账本原语；现阶段属于实现侧先行落点，不应被误认为协议真源 |
| `effect_ledger` | `specs/schemas/effect_ledger.json` | Runtime Slice | 已覆盖四阶段、attempt、lease、补偿独立化 |
| `fsync_trust` | 当前无独立冻结 spec；与恢复/耐久化降级策略相关 | Runtime Utility | 负责 fsync 可信度探测与降级建议；现阶段属于运行时能力探针，不应被误认为协议真源 |
| `worker_lifecycle` | `specs/state-machines/worker_lifecycle.json` | Runtime Slice | 已覆盖完整转移表、uncertain、reconcile、doctor/repair 闭环 |
| `task_concurrency` | `specs/schemas/task_concurrency.json` | Runtime Slice | 已覆盖 retry guard、scope quarantine、worker/tool/scope 调度准入 |
| `recovery::probes` | `specs/probes/*.json` | Runtime Slice | 已提供 probe catalog、receipt 模型、mock adapter 与运行时 probe 协调入口 |
| `scheduler` | `specs/schemas/task_concurrency.json` | Runtime Slice | 已提供 scheduler / orchestrator trait、内存 mock；外层 `safeclaw-sqlite` 已接入 SQLite orchestrator，并落地同 scope 写冲突跳过 / same-scope read 透传 |
| `state_engine` | `specs/state-machine.schema.json` 等恢复约束 | Adapter Ready | 已提供纯核 trait + 内存实现；外层 `safeclaw-sqlite` 已接入 SQLite 状态落盘 |
| `runtime_store` | `worker_lifecycle` + `effect_ledger` 恢复闭环 | Adapter Ready | 已提供 runtime 持久化 trait + mock；外层 `safeclaw-sqlite` 已落地恢复链路 |
| `spec_map` | 上述真源映射 | Runtime Slice | 显式记录 spec → 模块 → 当前阶段 / 下一步 |

## 当前实现边界

- `safeclaw-core` 保持 **零 IO / 零 SQLite 依赖**，只负责纯领域状态机、guard、恢复语义与合同约束。
- 外层 `safeclaw-sqlite` 已承接 SQLite WAL 适配、probe executor、sandbox executor、orchestrator、runtime 持久化与单 worker loop。
- 当前 crate 已同时存在内联 `#[cfg(test)]` 测试与 `tests/protocol_contracts.rs` 这类独立 Rust 测试；“Rust 零测试覆盖”不再是当前事实，真正缺口在于 CI 接入、spec 映射与覆盖率治理。
- 当前已具备单 worker 最小闭环：`claim -> execute -> crash -> persist -> restore -> probe -> complete` 的真实回归测试，并提供 `worker_loop_batch_failure_demo`、`worker_loop_batch_conflict_demo`、`worker_loop_batch_release_demo`、覆盖 fresh / retry / resume / probe 四分流的 `worker_loop_dispatch_demo`、覆盖批量 fresh / retry / resume 排空与 uncertain probe 排空的 `worker_loop_dispatch_batch_demo`、`worker_loop_empty_queue_demo`、`worker_loop_persisted_probe_demo`、`worker_loop_read_fanout_demo`、`worker_loop_resume_conflict_demo`、`worker_loop_resume_missing_runtime_demo`、`worker_loop_resume_release_demo`、`worker_loop_retry_conflict_demo`、`worker_loop_retry_missing_runtime_demo`、`worker_loop_retry_pre_exec_spawn_demo`、`worker_loop_retry_release_demo`、`worker_loop_write_under_reads_demo`、`worker_loop_write_serial_under_reads_demo` 在内的 `worker_loop_*`、`worker_loop_scope_*`、`orchestrator_scope_read_fanout_demo`、`orchestrator_scope_write_under_reads_demo`、`orchestrator_scope_write_serial_under_reads_demo` 与 `full_lifecycle_demo` 示例。
- UI、sidecar、Doctor force-kill 仍位于核心外层，不进入本 crate。

## 下一步顺序

1. 在外层 adapter / sidecar 从单 worker loop 继续扩到长驻 worker service、sidecar queue 与多 worker 租约协调。
2. 将 Doctor force-kill、观测链路、远端 probe / executor 接到外围基础设施层，不回灌核心依赖。
3. 维持 `safeclaw-core` 收敛，只做协议/语义级变更与保护性测试。
