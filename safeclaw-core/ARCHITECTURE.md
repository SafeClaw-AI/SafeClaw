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
| `effect_ledger` | `specs/schemas/effect_ledger.json` | Runtime Slice | 先锁核心状态、probe mode、六步协议 |
| `worker_lifecycle` | `specs/state-machines/worker_lifecycle.json` | Runtime Slice | 先锁 uncertain / reconcile / retry guard |
| `task_concurrency` | `specs/schemas/task_concurrency.json` | Test Skeleton | 先锁 auto retry、user retry、scope quarantine |
| `spec_map` | 上述真源映射 | Test Skeleton | 显式记录 spec → 模块 → 下一步 |

## 当前实现边界

- 当前只提供 **类型、常量、关键守卫与测试骨架**
- 当前不实现 SQLite、调度器、恢复器、sidecar 调用
- 当前不伪造“全量运行时”，避免在真源未完全映射前过度承诺

## 下一步顺序

1. 补 `worker_lifecycle` 全量 transition table
2. 补 `effect_ledger` record / transition runtime 结构
3. 接 `task_concurrency` 到真实 guard evaluator
4. 最后进入 probe / reconcile / recovery slice
