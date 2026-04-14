# SafeClaw 实现推进策略

> 默认工程节奏：**步步为营，层层推进。**
> 当前稳定入口以 `README.md`、`STATUS.md`、`ARCHITECTURE.md`、`DECISIONS.md`、`CHANGELOG.md` 与 `docs/README.md` 为准。
> 协议与治理真源以 `VERSION`、`specs/`、`docs/reference/`、`docs/30-方案/02-V4-目录锁定清单.md` 与 `docs/30-方案/08-V4-ledger-index-manifest.json` 为准。
> 任何后续实现，优先保证稳定入口、L0 真源、`tests/contracts/` 合同测试与门禁链一致。

## 核心原则

| 原则 | 含义 |
|------|------|
| 先梳理，后实现 | 先明确模块边界、真源映射、运行时主链路，再写代码 |
| 先测试，后扩展 | 先锁协议测试与不变量，再增加行为与性能优化 |
| 先小闭环，后大集成 | 先完成最小可验证垂直切片，再接调度、恢复、UI、sidecar |
| 先真源，后便利 | 实现不得为了开发方便绕过 `specs/` 与门禁 |
| 先保守，后提速 | 先保证正确、可审计、可回退，再考虑吞吐与并发优化 |

## 默认推进顺序

| 阶段 | 目标 | 通过标准 |
|------|------|----------|
| 1. 梳理 | 明确模块边界、文件树、spec → runtime 映射 | 文档可读，职责不重叠 |
| 2. 测试骨架 | 先建立 Rust 侧协议测试、状态测试、守卫测试 | 测试先于运行时实现存在 |
| 3. 最小垂直切片 | 优先打通 `effect_ledger` + `worker_lifecycle` 只读/校验层 | 至少一条主链路可验证 |
| 4. 守卫与并发 | 接入 `task_concurrency`、`scope_quarantine`、`fencing` | 核心守卫有自动测试 |
| 5. 恢复与执行 | 再进入 probe、reconcile、scheduler、recovery | 不破坏前四层闭环 |
| 6. 外围集成 | 最后再接 Tauri、Python sidecar、SQLite 落地细节 | 不变量与门禁持续通过 |

## 明确禁止

- 不允许跳过梳理阶段，直接堆砌运行时代码
- 不允许在 Rust 中私自简化 `specs/` 已冻结的不变量
- 不允许先做大而全框架，再回头补协议测试
- 不允许为了“先跑起来”绕过 `selfcheck.py` 与合同测试

## safeclaw-core 当前执行法

当前 `safeclaw-core/` 默认按以下顺序推进：

1. `protocol_version` 等真源锚点先锁定
2. Worker / Effect / Retry Guard 的类型与测试骨架先落地
3. `effect_ledger` 与 `worker_lifecycle` 的最小运行时实现先打通
4. `task_concurrency` / `scope_quarantine` / `fencing` 再接入
5. probe / reconcile / recovery 最后进入

## 完成定义

某一层只有在以下条件同时满足时，才进入下一层：

- 对应文档已写清楚边界与责任
- 自动测试已覆盖该层核心不变量
- `python tools/checks/selfcheck.py` 继续通过
- 没有引入新的真源漂移

## 当前 selfcheck policy

- `python tools/checks/selfcheck.py` 会先跑 `ledger_index_manifest.py`
- 然后依次跑 `check_ledger_alignment.py`、`check_consistency.py`、`check_versions.py`、`check_structure.py`、`check_scaffold.py`、`check_public_docs.py`
- 这条 ledger policy chain 会显式前置在 `Contract tests` 之前
