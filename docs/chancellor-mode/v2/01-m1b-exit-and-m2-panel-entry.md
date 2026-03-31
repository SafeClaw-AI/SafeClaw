# M1b 收口与 M2 面板入口决议

- Time: 2026-03-31 19:52:12 +0800
- Status: baseline truth source (M2 sequencing superseded by `03-m2-product-value-rebaseline.md`)
- Scope: freeze M1b exit rules and preserve the first M2 panel-visible delivery baseline

## 1. 为什么现在先写这份文档
- 当前风险不在代码质量，而在 `M1b` 何时算完、`M2` 先交什么给用户这两件事没有被当前主线写成单一真源。
- 旧文档里仍保留 `Tauri UI` 口径；当前现行约束已经改成“官方 Codex 面板优先”。如果不先冻结，后续会边做边漂移。

## 2. 本轮冻结的三条决议
- 普通用户主入口：`官方 Codex 面板`。
- 终端角色：只保留给维护、安装、迁移、排障，不再作为普通用户日常入口。
- `Tauri/UI`：保留为历史方案背景，不再作为当前 `M2` 首轮交付目标，也不再作为当前毕业口径。

## 3. M1b 的完成标准（冻结版）
- Gate 1：`reference fail-closed` 只继续收当前同层高杠杆尾包，不再无限外扩到新的大主题。
- Gate 2：根目录 `tmp/` 这条既有阻塞要被治理到不再卡 `check_scaffold.py` / `selfcheck.py`。
- Gate 3：跑一次完整最小毕业链：`check_reference_redlines.py`、`check_versions.py`、`check_consistency.py`、`check_structure.py`、`check_scaffold.py`、`check_ledger_alignment.py`、`check_public_docs.py`、`check_tooling_smoke.py`、`check_mvp_operator_flow.py`、`selfcheck.py`、`git diff --check`。
- Gate 4：补一份 `M1b` 收口记录，写清“哪些算 M1b，哪些正式转入 M2 backlog”。

## 4. 什么不再算进 M1b
- 需要真实 provider、真实 sidecar、真实记忆通道、真实权限网关的新能力。
- 只提升长期价值、但不影响当前 `M1a/M1b` 毕业链全绿的新想法。
- 旧 `Tauri/UI` 路线上的新增工作。

## 5. M2 第一个用户可见输出（冻结版）
- 用户在官方 Codex 面板里直接输入：`丞相状态`、`丞相检查`、`丞相版本`、`丞相验板`。
- 目标不是“功能很多”，而是“普通用户不进终端，也能看懂现在稳不稳、该不该继续、版本从哪里来”。
- 第一阶段只做读多写少的人话结果卡片；`丞相修复` 仍属于维护层动作，要先说明“这是维护层动作”。

## 6. M2 首轮拆解（<= 8 刀）
| 顺序 | 刀 | 目标 | 验收标准 |
| --- | --- | --- | --- |
| 1 | M2-1 | 面板命令真源表 | 四个丞相命令的输入/输出字段固定，可追溯到单一文档 `docs/chancellor-mode/v2/02-m2-panel-command-truth-source.md` |
| 2 | M2-2 | `丞相状态` 聚合 | 能稳定汇总模式、稳态、下一步，人能看懂 |
| 3 | M2-3 | `丞相检查` 最小检查 | 只跑最小必要检查，结果转成人话，不把用户扔回终端 |
| 4 | M2-4 | `丞相版本` 真源回显 | 能明确版本号、版本来源、运行态镜像来源 |
| 5 | M2-5 | `丞相验板` 固定验收单 | 给出稳定的人工验收步骤，不因会话漂移 |
| 6 | M2-6 | `丞相修复` 维护层边界 | 明确哪些能自动修，哪些必须提示，哪些要停下确认 |
| 7 | M2-7 | 面板合同测试 | 四个命令至少有稳定合同/快照，不靠人工记忆 |
| 8 | M2-8 | 首轮收口与切换 | 补文档、补台账、给出下一阶段是否进入 provider/sidecar 的判断 |

## 7. M2 第一可见输出的验收标准
- 在官方 Codex 面板直接输入 `丞相状态`，返回当前模式、是否稳态、下一步建议。
- 在官方 Codex 面板直接输入 `丞相检查`，返回最小必要检查的人话结论，不要求用户理解内部脚本名。
- 在官方 Codex 面板直接输入 `丞相版本`，返回当前版本与来源，不混淆真源与运行态镜像。
- 在官方 Codex 面板直接输入 `丞相验板`，返回固定的人类验收步骤，普通用户照着做就行。

## 8. 进入 M2 前的停线规则
- 若新问题不影响 `M1b` 毕业链，就先记到 `M2 backlog`，不再把 `M1b` 无限拖长。
- 若新问题会让 `M1a/M1b` 现有门禁失真、漂移或误报，仍按 `M1b` 优先级处理。
- 若出现真正高风险变更，再单独升级为需要人工拍板的决策项。

## 9. 毕业检查点
- 2026-03-31 20:33:15 +0800：冻结版 `M1b` 毕业链已完整跑通。
- 当前全绿链路：`check_reference_redlines.py`、`check_versions.py`、`check_consistency.py`、`check_structure.py`、`check_scaffold.py`、`check_ledger_alignment.py`、`check_public_docs.py`、`check_tooling_smoke.py`、`check_mvp_operator_flow.py`、`selfcheck.py`、`git diff --check`。
- 从这一刻开始，`M1b` 视为已毕业；当前主线切换到 `M2-1 面板命令真源表`。
