# 整体计划实现进展表

最后更新时间：2026-03-25 04:28:16 +0800
范围：`01_文档` 对应的整体计划
当前阶段：已进入 M1b，前五刀为 doctor 离线边界诊断 / scope 可见化 / lease 可见化 / next_action 决策提示 / next_command 命令提示
当前预估：
- Win11 本地 MVP / M1a 可手用收口：已完成
- 当前主线（M1b 生存层补完）：约 0.5 ~ 2.5 天
- 下一阶段（M2 首轮价值层）：约 1 ~ 2 周

## 进展
| 状态 | 计划区块 | 文档来源 | 当前实现进展 | 备注 |
| --- | --- | --- | --- | --- |
| [x] | 宪法 / 决策 / 蓝图 / API 真源 | `01_文档/01_宪法.md` `01_文档/02_决策清单.md` `01_文档/03_开发蓝图.md` `01_文档/05_API规范草案.md` | 文档基线、架构冻结、协议真源已形成 | 已进入实现驱动阶段 |
| [x] | specs / contracts / generated / selfcheck 闭环 | `01_文档/03_开发蓝图.md` `01_文档/09_迭代升级与自动化.md` | `specs`、`tests/contracts`、`tools/checks` 已形成门禁 | Phase 0 主干已落地 |
| [x] | Rust core / sqlite / recovery / probe 主线 | `01_文档/03_开发蓝图.md` 生存层 M1 | 仓库已有 `safeclaw-core`、`safeclaw-sqlite`、恢复/探针/worker demos | M1a 关键路径已部分落地 |
| [x] | Win11 本地 MVP wrapper / operator flow | `01_文档/08_用户旅程.md` | `safeclaw.cmd`、`safeclaw.ps1`、`tools/mvp` 已可手动使用 | README 根入口最短路径已纳入自动门禁 |
| [x] | 追踪文档完整性防线 | `01_文档/09_迭代升级与自动化.md` | `MVP_PROGRESS.md`、`PUSH_LOG.md` 已接入公开文档检查 | 可拦截问号或乱码占位符 |
| [x] | M1a 最后一轮可手用验收 | `01_文档/03_开发蓝图.md` M1 验收 | 根入口 `workspace -> doctor -> service-run/retry/recover -> verify` 已进 smoke；`selfcheck` 全绿 | 当前主线已收口 |
| [x] | M1b 首刀：doctor 离线边界诊断 | `01_文档/03_开发蓝图.md` M1b | `doctor` 现已显式返回 `runtime_profile` / `model_provider` / `sidecar`，说明当前 local MVP 离线可跑、无 provider/sidecar 也属正常 | 已落地，降低使用歧义 |
| [x] | M1b 第二刀：service-status scope 可见化 | `01_文档/03_开发蓝图.md` M1b | `service-status` 的 `recent_tasks` 现已显式返回并输出 `target_scope` / `requires_write` / `doctor_bypass`，让当前任务边界直接可见 | 已落地，降低权限边界不可见性 |
| [x] | M1b 第三刀：service-status lease 可见化 | `01_文档/03_开发蓝图.md` M1b | `service-status` 的 `recent_tasks` 现已显式返回并输出 `lease_state` / `lease_owner_id` / `lease_fencing_token`，让最新租约是否 active / expired / released 直接可见 | 已落地，降低恢复判断成本 |
| [x] | M1b 第四刀：service-status next_action 决策提示 | `01_文档/03_开发蓝图.md` M1b | `service-status` 的 `recent_tasks` 现已显式返回 `next_action`，在 success / failed / uncertain 场景下分别给出 `ok` / `retry` / `recover` 提示 | 已落地，降低人工判断成本 |
| [x] | M1b 第五刀：service-status next_command 命令提示 | `01_文档/03_开发蓝图.md` M1b | `service-status` 的 `recent_tasks` 现已显式返回可复制的 `next_command`，让 operator 直接知道下一条推荐命令怎么敲 | 已落地，降低操作摩擦 |
| [ ] | M1b 生存层补完 | `01_文档/03_开发蓝图.md` M1b | 权限 scope / 心跳 / sidecar / 预算 / 并发 / 离线降级其余部分仍需集中实现或收口 | 当前主线 |
| [ ] | M2 价值层 | `01_文档/03_开发蓝图.md` 价值层 | provider sidecar / permission gateway / preflight / memory / scheduler 等待推进 | 未开始系统收口 |
| [ ] | M3 / Phase 2 / Phase 3+ | `01_文档/03_开发蓝图.md` 后续阶段 | 正式 CLI、插件、浏览器自动化、远程节点等属于后续 | 长线 |
