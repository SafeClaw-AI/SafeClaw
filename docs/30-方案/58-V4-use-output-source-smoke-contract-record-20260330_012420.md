# V4 use output-source smoke contract record

- 时间：2026-03-30 01:24:20 +0800
- 轮次：M1b Slice 186
- 目标：补齐 `Slice 185` 遗留的公开门禁债务；让 `check_tooling_smoke.py` 对 `use` 的 `output_source=task_scope` 合同与真实实现重新对齐，避免 broad smoke 继续按旧 `session` 口径报假红。

## 本轮动作
- 在 `tools/checks/check_tooling_smoke.py` 点改 5 处 `use` 合同断言：把 helper 断言、文本输出断言与 JSON 错误信息从 `output_source=session` 收紧到 `output_source=task_scope`。
- 保持 `Slice 185` 的运行时实现不动，只把 broad smoke 恢复为与真实 `use` 语义一致。
- 顺手清理这 5 处改行的换行风格，确保 `git diff --check` 不再把它们判成尾随空白。

## 结果
- `operator-flow` 与 `tooling smoke` 现在对 `use` 的 output 来源口径一致：当 remembered session 切到目标任务且 output 来自 `target_scope` 时，合同稳定认定 `output_source=task_scope`。
- 上一刀的运行时修复已被 broad smoke 接住，不再只停留在局部门禁。

## 验证
- `python tools/checks/check_mvp_operator_flow.py`
- `python tools/checks/check_tooling_smoke.py`
- `git diff --check`

## 下一步
- 已确认下一处同型残留：`use` 切任务时 `owner_id` 仍可能沿用旧 remembered session；下一刀优先把 `owner_id` 也对齐到目标任务真源，并补最小门禁。