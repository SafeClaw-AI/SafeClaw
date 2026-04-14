# SafeClaw

> 希望在自动化越来越强、越来越快的时代，
> 还能有一个系统愿意慢一点、讲清楚一点、对你温柔一点。

## 概述

SafeClaw 是一个面向本地执行的 automation system。
它的目标不是把用户推出控制环，而是在自动化越来越强的时代，仍然把理解权、确认权、暂停权和恢复权留在用户自己手里。

本仓库坚持 `protocol-first` 与 `local-only` 的稳定基线：

- 协议与治理真源在 `specs/`、`VERSION`、`docs/reference/` 与 `docs/30-方案/02-V4-目录锁定清单.md`
- 合同与机器门禁在 `tests/contracts/` 与 `tools/checks/`
- 面向人的主线入口固定为 `README.md`、`STATUS.md`、`ARCHITECTURE.md`、`DECISIONS.md`、`CHANGELOG.md`

## 核心理念

- 先解释，再执行。
- 先确认风险，再触碰外部状态。
- 先保留恢复路径，再追求速度。
- 先让机器可验证，再让叙事变漂亮。
- 先把控制权留在本机，再谈云端扩展。

## 系统架构（高层）

| 模块 | 职责 | 当前边界 |
| --- | --- | --- |
| `specs/` | 协议规格与 JSON 真源 | 定义状态机、schema、error code、SPI |
| `tests/contracts/` | 合同测试 | 校验规格、包装层、公开契约与治理基线 |
| `tools/checks/` | 机器门禁 | 校验结构、文档、reference redlines、总验入口 |
| `safeclaw-core/` | Rust 纯领域核心 | 承担协议语义、状态机、恢复语义与约束 |
| `safeclaw-sqlite/` | 持久化与适配层 | 承担 SQLite、worker loop、runtime store 等外层适配 |
| `tools/mvp/` | 本地 operator 入口 | 提供 `.cmd/.ps1` launcher、Python/Tkinter 面板与 MVP 包装层 |
| `generated/` | 派生产物 | 仅接受真源生成，不反向裁决规格 |
| `docs/` | 解释与导航 | 帮人读懂系统，不反向定义协议字段 |

更细的实现边界见 [ARCHITECTURE.md](ARCHITECTURE.md) 与 [safeclaw-core/ARCHITECTURE.md](safeclaw-core/ARCHITECTURE.md)。

## 文档与真源

根级文档五件套按职责分离：

- [README.md](README.md)：稳定入口，只说明项目是什么、为什么存在、如何进入真源
- [STATUS.md](STATUS.md)：当前状态与风险滚动更新
- [CHANGELOG.md](CHANGELOG.md)：已发生变更的历史记录
- [DECISIONS.md](DECISIONS.md)：关键架构与流程决策
- [ARCHITECTURE.md](ARCHITECTURE.md)：系统架构真源

协议与治理裁决层不在这些说明文档里，而在以下真源：

- [specs/](specs/)
- `VERSION`
- [docs/reference/01-反屎山工程规范.md](docs/reference/01-反屎山工程规范.md)
- [docs/reference/02-结构性债务台账.md](docs/reference/02-结构性债务台账.md)
- [docs/reference/03-绕过白名单.md](docs/reference/03-绕过白名单.md)
- [docs/30-方案/02-V4-目录锁定清单.md](docs/30-方案/02-V4-目录锁定清单.md)

当前公开协议版本以根目录 `VERSION` 为准。
`README.md` 只负责说明版本边界由谁裁决，不复述具体版本号，也不承担滚动状态播报。

## 稳定入口边界

稳定入口是本地 operator 路径，而不是公有 GUI 产品：

- 日用入口是 `.cmd/.ps1` launcher + Python/Tkinter 小面板 + Rust CLI
- 维护入口与最短操作链统一看 [tools/mvp/OPERATOR_PLAYBOOK.md](tools/mvp/OPERATOR_PLAYBOOK.md)
- 稳定承诺是 `local-only` MVP，不把 provider / sidecar 当成已交付事实
- `Tauri + React` 与远端 AI provider 属于后续扩展方向，不属于当前稳定边界

## 模型路由矩阵（稳定边界）

| 场景 | 当前稳定路径 | 说明 |
| --- | --- | --- |
| 本地执行 | Rust runtime + launcher | 当前默认执行面，强调可控与可恢复 |
| 个人生产位 | Python/Tkinter 小面板 + personal production slot | 面向仓库主人自用的本地入口 |
| 远端 AI 推理 | 未纳入当前稳定基线 | provider / sidecar 尚未接通，不写成已交付能力 |
| 图形界面扩展 | `Tauri + React` 规划态 | 目标方向，不冒充当前实现 |

## 高层路线图

- Phase 1：稳住协议真源、治理门禁与本地 operator MVP
- Phase 2：把 `specs/` → `tests/contracts/` → implementation 收成单向对齐链，落地 codegen
- Phase 3：在稳定治理基线之上扩展 provider、GUI、多 worker、CI/CD 与 chaos harness

## 成功指标

- 可理解：高风险动作在执行前可读、可解释、可追溯
- 可控制：用户能确认、暂停、终止、回退关键动作
- 可恢复：系统长期保留 `undo / recover / reconcile` 路径
- 可验证：规格、测试、实现、文档之间的冲突能够被机器门禁拦下
- 可扩展：新增 provider、GUI、worker 不破坏当前 local-first 基线

## 继续阅读

- 当前状态与风险： [STATUS.md](STATUS.md)
- 架构边界： [ARCHITECTURE.md](ARCHITECTURE.md)
- 决策记录： [DECISIONS.md](DECISIONS.md)
- 历史变更： [CHANGELOG.md](CHANGELOG.md)
- 文档导航： [docs/README.md](docs/README.md)
- 协议真源： [specs/](specs/)
- 合同测试： [tests/contracts/](tests/contracts/)
- 机器门禁： [tools/checks/](tools/checks/)

## 许可

SafeClaw 采用 [GPL-3.0](LICENSE) 开源许可。

简单说：

- 个人使用、学习、研究：完全自由
- 修改后分发：必须继续开源
- 商业闭源集成：可联系申请商业授权

## 联系

**safeclaw.ai@gmail.com**

公开讨论优先走 GitHub Issues / Discussions：
https://github.com/SafeClaw-AI/SafeClaw

## English Summary

SafeClaw is a local-first automation system built around one constraint:
automation must stay understandable, controllable, and recoverable.

This `README.md` is intentionally stable. It points to the live operational status in `STATUS.md`, the architecture source in `ARCHITECTURE.md`, the decision log in `DECISIONS.md`, the change history in `CHANGELOG.md`, and the protocol truth in `specs/`, `VERSION`, and governance references.

The stable operator path is local-only: launcher scripts, a Python/Tkinter panel, and Rust runtime components. Remote providers, sidecars, and `Tauri + React` GUI work remain planned expansions rather than shipped guarantees.

<sub>SafeClaw™ is a trademark of Tian (田).</sub>
