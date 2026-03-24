# 整体计划实现进展表

最后更新时间：2026-03-25 07:04:21 +0800
范围：`01_文档` 对应的整体计划
当前阶段：已进入 M1b，前十五刀为 doctor 离线边界诊断 / scope 可见化 / lease 可见化 / next_action 决策提示 / next_command 命令提示 / next_reason 原因提示 / active lease 等待提示 / next_blocker 阻断提示 / next_summary 一行摘要提示 / preflight 离线门禁 / permission 决策可见化 / preflight scope 权限预检 / preflight 严格权限阻断 / preflight 常见动作权限模板 / service 前置门禁
当前预估：
- Win11 本地 MVP / M1a 可手用收口：已完成
- 当前主线（M1b 生存层补完）：约 0.1 天
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
| [x] | M1b 第六刀：service-status next_reason 原因提示 | `01_文档/03_开发蓝图.md` M1b | `service-status` 的 `recent_tasks` 现已显式返回 `next_reason`，补足“为什么推荐这条命令”的稳定原因字符串 | 已落地，降低判断歧义 |
| [x] | M1b 第七刀：service-status active lease 等待提示 | `01_文档/03_开发蓝图.md` M1b | `service-status` 的 `recent_tasks` 现已显式返回 `lease_remaining_ms`，在 active lease 现场直接给出剩余等待时间 | 已落地，降低误操作风险 |
| [x] | M1b 第八刀：service-status next_blocker 阻断提示 | `01_文档/03_开发蓝图.md` M1b | `service-status` 的 `recent_tasks` 现已显式返回 `next_blocker`，区分当前无阻断、active lease 阻断或需人工检查等状态 | 已落地，降低阻断判断成本 |
| [x] | M1b 第九刀：service-status next_summary 一行摘要 | `01_文档/03_开发蓝图.md` M1b | `service-status` 的 `recent_tasks` 现已显式返回 `next_summary`，把 action / blocker / reason 压成一行，便于复制、抄录与快速判断 | 已落地，降低阅读与转述成本 |
| [x] | M1b 第十刀：preflight 离线门禁 | `01_文档/03_开发蓝图.md` M1b | `preflight --action <name>` 现已显式返回 `tier` / `decision` / `offline_ready` / `degradation_mode`；已知本地动作允许，未知动作默认从严拒绝 | 已落地，降低离线执行歧义 |
| [x] | M1b 第十一刀：permission 决策可见化 | `01_文档/03_开发蓝图.md` M1b | `service-status` 的 `recent_tasks` 现已显式返回 `permission_tier` / `permission_policy` / `permission_reason`，把 scope 可见化推进到可直接判断是否 allow / confirm / deny | 已落地，降低权限判断成本 |
| [x] | M1b 第十二刀：preflight scope 权限预检 | `01_文档/03_开发蓝图.md` M1b | `preflight` 现已支持可选 `--scope` / `--write` / `--doctor-bypass`，在执行前返回 `permission_tier` / `permission_policy` / `permission_reason`；默认动作级 allow / deny 语义保持不变 | 已落地，降低执行前权限判断成本 |
| [x] | M1b 第十三刀：preflight 严格权限阻断 | `01_文档/03_开发蓝图.md` M1b | `preflight` 新增 `--enforce-permission`；当显式提供权限上下文后，`confirm` / `deny` 会直接非零退出，`allow` 才放行；同时返回 `action_allowed` / `action_decision` / `action_reason` 供脚本区分动作门禁与权限门禁 | 已落地，降低脚本接入误放行风险 |
| [x] | M1b 第十四刀：preflight 常见动作权限模板 | `01_文档/03_开发蓝图.md` M1b | `preflight` 现可为常见 wrapper / session 动作自动从 remembered session / workspace / 默认 output 推断 `scope/write` 上下文，并显式返回 `permission_context_source`；显式 `--scope` / `--write` / `--doctor-bypass` 仍可覆盖 | 已落地，降低预检传参摩擦 |
| [x] | M1b 第十五刀：service 前置门禁 | `01_文档/03_开发蓝图.md` M1b | `service-run` / `service-retry` / `service-recover` 新增 `--preflight` / `--enforce-permission`；可在执行前用同一次实际参数跑门禁，必要时直接在 `preflight` 步阻断，并在 JSON 错误细节中返回 `preflight` 载荷 | 已落地，降低实际执行误放行风险 |
| [ ] | M1b 生存层补完 | `01_文档/03_开发蓝图.md` M1b | 心跳 / sidecar / 预算 / 并发 / 离线降级其余部分仍需集中实现或收口 | 当前主线 |
| [ ] | M2 价值层 | `01_文档/03_开发蓝图.md` 价值层 | provider sidecar / permission gateway / preflight / memory / scheduler 等待推进 | 未开始系统收口 |
| [ ] | M3 / Phase 2 / Phase 3+ | `01_文档/03_开发蓝图.md` 后续阶段 | 正式 CLI、插件、浏览器自动化、远程节点等属于后续 | 长线 |
