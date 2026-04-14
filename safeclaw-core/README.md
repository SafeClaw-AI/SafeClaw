# safeclaw-core

> 本文件是 `safeclaw-core` 的 L2 模块入口，用来说明 Rust 纯领域核心的职责边界。
> 当前稳定入口以 `README.md`、`STATUS.md`、`ARCHITECTURE.md`、`DECISIONS.md`、`CHANGELOG.md` 与 `docs/README.md` 为准。
> 协议与治理真源以 `VERSION`、`specs/`、`docs/reference/`、`docs/30-方案/02-V4-目录锁定清单.md` 与 `docs/30-方案/08-V4-ledger-index-manifest.json` 为准。

## 模块角色

- `safeclaw-core` 负责 Rust 纯领域核心，只承接协议语义、状态机约束与恢复语义。
- 实现边界与模块映射见 `safeclaw-core/ARCHITECTURE.md`，不由本文件反向定义字段或状态。
- 生成侧入口是 `generated/rust/`，由 `specs/` 单向推导 Rust 稳定索引。
- 实现推进顺序仍遵循 `docs/IMPLEMENTATION_STRATEGY.md`。

## 对齐链

- 协议版本统一锚定仓库根 `VERSION`。
- 协议字段与状态机来自 `specs/`，Rust 侧只消费这些真源。
- Rust 合同入口见 `safeclaw-core/tests/protocol_contracts.rs`。
- 总验入口仍是 `python tools/checks/selfcheck.py`，任何 `safeclaw-core` 改动都必须通过该门禁。

## 当前稳定边界

- `safeclaw-core` 保持零 UI、零外部 provider 承诺，不把规划中的界面层写成已交付事实。
- 持久化、SQLite 适配与外层 worker runtime 由 `safeclaw-sqlite/` 承接，不回灌到纯领域核心。
- 当前目标是稳住 Rust 核心与协议真源之间的单向对齐，而不是让 README 充当实现真源。
