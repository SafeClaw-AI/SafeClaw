# 系统架构真源

## 模块划分

- `specs/`：协议规格真源，定义状态机、schema、error code、SPI 与配置边界
- `tests/contracts/`：合同测试层，校验公开契约、包装层与实现是否仍与规格一致
- `tools/checks/`：治理门禁层，负责结构、文档、reference redlines 与总验入口
- `generated/`：由真源派生的机读产物，只接受生成，不反向定义规格
- `safeclaw-core/`：Rust 纯领域核心，承载状态机、effect ledger、task concurrency、恢复语义
- `safeclaw-sqlite/`：SQLite 与 worker loop 适配层，负责 runtime store、orchestrator、持久化恢复链
- `tools/mvp/`：本地 operator 入口，提供 launcher、Python/Tkinter 小面板与 MVP 包装层
- `docs/`：面向人的解释与导航层，不反向裁决协议字段

## 依赖关系

- `README.md` / `STATUS.md` / `CHANGELOG.md` / `DECISIONS.md` / `ARCHITECTURE.md` -> 面向人的入口与记录层
- `specs/` + `VERSION` + `docs/reference/` + `docs/30-方案/02-V4-目录锁定清单.md` + `docs/30-方案/08-V4-ledger-index-manifest.json` -> 当前协议与治理裁决层
- `generated/` <- 由 L0 真源生成
- `tests/contracts/` + `tools/checks/` -> 校验 L0 真源、L1 派生物与实现层是否一致
- `safeclaw-core/` <- 服从 `specs/` 语义约束
- `safeclaw-sqlite/` <- 适配 `safeclaw-core/`，并把运行时能力落到 SQLite / worker loop
- `tools/mvp/` <- 调用 `safeclaw-sqlite/` 与 launcher，形成当前 operator path

## 不变量（必须长期成立）

- 协议字段、治理阈值与 ledger 兼容索引只能由 `specs/`、`VERSION`、`docs/reference/`、目录锁定清单与 `docs/30-方案/08-V4-ledger-index-manifest.json` 裁决
- `generated/` 只能从真源生成，不能反向改写 `specs/`
- 公开说明文档只能解释与导航，不能冒充协议真源
- 高风险外部动作必须保留 preflight、ledger、recover / undo 之类的保护路径
- 当前稳定基线仍是 `local-only`；provider / sidecar / GUI 扩展不得回写成既成事实

## 关键设计原则

- Protocol-first：先定义规格与不变量，再扩展实现
- Governance-first：先把目录、文档、结构与绕过纳入门禁，再继续开发
- Local-first：默认把控制权、数据与恢复路径留在用户本机
- Explain-before-act：任何高风险动作都应先解释、再确认、后执行
- Recoverability-over-speed：恢复能力优先于表面速度

## 参考

- Rust 子系统细节见 `safeclaw-core/ARCHITECTURE.md`
- 当前状态与风险见 `STATUS.md`
- 关键决策见 `DECISIONS.md`
