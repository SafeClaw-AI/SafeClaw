# safeclaw-core 架构梳理

## 当前文件树

```text
safeclaw-core/
  Cargo.toml
  README.md
  ARCHITECTURE.md
  src/
    lib.rs
    protocol.rs
    effect_ledger.rs
    task_concurrency.rs
    worker_lifecycle.rs
    spec_map.rs
  tests/
    protocol_contracts.rs
```

## 模块与真源映射

| Rust 模块 | 对应真源 | 当前阶段 | 说明 |
|---|---|---|---|
| `protocol` | `VERSION` | 已锚定 | Rust 入口统一读取仓库协议版本 |
| `effect_ledger` | `specs/schemas/effect_ledger.json` | Runtime Slice | 已覆盖四阶段、attempt、lease、补偿独立化 |
| `worker_lifecycle` | `specs/state-machines/worker_lifecycle.json` | Runtime Slice | 已覆盖完整转移表、uncertain、reconcile、doctor/repair 闭环 |
| `task_concurrency` | `specs/schemas/task_concurrency.json` | Runtime Slice | 已覆盖 retry guard、scope quarantine、worker/tool/scope 调度准入 |
| `recovery::probes` | `specs/probes/*.json` | Test Skeleton | 已提供 probe 定义目录、receipt 模型、mock adapter 接口 |
| `spec_map` | 上述真源映射 | Runtime Slice | 显式记录 spec → 模块 → 下一步 |

## 当前实现边界

- 当前提供 **纯内存 runtime slice + 关键守卫 + 合同测试**
- 当前不实现 SQLite、真实调度器、sidecar 调用、UI
- 当前只覆盖 Phase 1 允许的纯核心恢复路径，不伪造持久化语义

## 下一步顺序

1. 将 runtime slice 接到真实 `State Engine` / WAL 持久化
2. 将 `task_concurrency` guard 接到 orchestrator / sidecar 队列
3. 将 `recovery::probes` trait 接到外层 adapter / sidecar probe executor
4. 最后进入 Chaos / Doctor / 持久化恢复联调
