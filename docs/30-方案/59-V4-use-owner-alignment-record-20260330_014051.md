# V4 use owner alignment record

- 时间：2026-03-30 01:40:51 +0800
- 轮次：M1b Slice 187
- 目标：继续收紧 `session/use` 的当前上下文语义；当 `use` 切到目标任务时，remembered session 的 `owner_id` 也必须跟随目标任务真源恢复，不得沿用旧 session 的残留 owner。

## 本轮动作
- 调整 `tools/mvp/safeclaw_mvp.py`：新增 `resolve_activate_owner_id_selection()`，让 `use` 在未显式传 `--owner-id` 时优先从目标任务最新 lease 的 owner 恢复 `owner_id`；若目标 owner 与当前 session 相同则仍兼容回报 `session`，若不同则明确标成 `task_owner`。
- 扩展 `lookup_task_entry()`：一并读取目标任务最新 `lease_owner_id`，让 `use --task-id ...` 也具备 owner 真源。
- 在 `tools/checks/check_mvp_operator_flow.py` 新增 owner-alignment 场景：先构造 `owner-a` / `owner-b` 两个任务，再 `use` 回到 A，锁住 `owner_id=owner-a`、`owner_id_source=task_owner`，并确认 `service-status.current_session.owner_id` 同步切回 A。

## 结果
- `use` 现在会同时切换“任务身份 / output / owner”三类当前上下文；切任务后 remembered session 不会再把旧 owner 残留到新任务上。
- 兼容口径保持不扩散：若目标 owner 与当前 remembered session owner 一致，`owner_id_source` 仍可保持 `session`；只有真正发生 owner 切换时才显式回报 `task_owner`。

## 验证
- `python -m py_compile tools/mvp/safeclaw_mvp.py tools/checks/check_mvp_operator_flow.py`
- `python tools/checks/check_mvp_operator_flow.py`
- `python tools/checks/check_tooling_smoke.py`
- `git diff --check`

## 下一步
- 已发现另一处高复利残留：`mvp_state_guard.py` 在 Windows 上处理陈旧 `.wrapper-check.lock` 时，`os.kill(pid, 0)` 可能抛 `WinError 87`；下一刀优先把 stale-lock 自恢复收成稳态，避免验证链被假锁打断。