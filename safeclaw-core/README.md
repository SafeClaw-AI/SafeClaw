# safeclaw-core

SafeClaw 的 Rust Core 最小脚手架。

当前目标：
- 为后续状态机、调度器、Effect Ledger 运行时提供 Rust 入口
- 先与仓库根 `VERSION` 保持单点对齐
- 后续从 `specs/` 与 `generated/rust/` 接入类型与协议实现

## 默认推进规则

`safeclaw-core` 后续实现默认遵循 `docs/IMPLEMENTATION_STRATEGY.md`：

1. 先梳理模块边界与 spec 映射
2. 先落测试骨架，再写运行时实现
3. 先完成最小垂直切片，再扩到并发、恢复、sidecar、UI
4. 每推进一层，都必须保持 `selfcheck.py` 通过

## 当前骨架内容

- 模块梳理：见 `safeclaw-core/ARCHITECTURE.md`
- Rust 协议测试骨架：见 `safeclaw-core/tests/protocol_contracts.rs`
- 当前已包含纯领域 `state_engine` / `recovery::probes` trait 与 mock adapter 骨架
- 当前目标是锁定协议边界，而不是提前实现完整 runtime
