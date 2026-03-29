# V4 use session output alignment record

- 时间：2026-03-30 00:51:37 +0800
- 轮次：M1b Slice 185
- 目标：继续收紧 `session/use` 的当前上下文语义；当 `use` 切到目标任务时，remembered session 的 `output` 也必须跟随目标任务的 `target_scope` 恢复，不得沿用旧 session 的残留输出路径。

## 本轮动作
- 调整 `tools/mvp/safeclaw_mvp.py`：新增 `extract_output_path_from_target_scope()` 与 `resolve_activate_output_selection()`，让 `use` 在未显式传 `--output` 时优先从目标任务的 `target_scope` 恢复 `output`；仅当目标任务缺少 `target_scope` 时，才回退到同任务 session / workspace / default。
- 扩展 `lookup_task_entry()`：连同 `orchestrator_tasks.target_scope` 一起读取，确保 `use --task-id ...` 和 `use --index ...` 走同一份任务级 output 真源。
- 在 `tools/checks/check_mvp_operator_flow.py` 补齐 `use` 输出对齐门禁：锁住 contended / quarantine / session-priority 三类场景下 remembered session 的 `output` 与目标任务 scope 对齐，不再沿用旧任务 output。

## 结果
- `use` 现在会同时切换“当前任务身份”和“当前任务 output 上下文”；切任务后 remembered session 不会再把旧 output 残留到新任务上。
- 对共享 scope 场景，remembered session 会稳定回到共享 `target_scope` 对应的 output；对独占 scope 场景，则稳定回到目标任务自己的 output。

## 验证
- `python -m py_compile tools/mvp/safeclaw_mvp.py tools/checks/check_mvp_operator_flow.py`
- `python tools/checks/check_mvp_operator_flow.py`
- `git diff --check`

## 下一步
- 继续盘点 `session/use` 与 `service-status/current_session` 之间是否还有其他“身份已切但上下文未切”的残留点；优先处理会把 operator 写入落到旧 scope 的语义缝隙。
