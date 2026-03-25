# tools/mvp/

当前 Win11 本地 MVP 的最小操作说明。

当前默认假设：

- 使用 Windows 11
- 使用 `stable-x86_64-pc-windows-gnu` Rust 工具链
- 已安装当前包装脚本内配置的 MinGW GCC linker

## 入口文件

- `tools/mvp/safeclaw_mvp.cmd`：推荐入口，适合 `cmd.exe` 与直接双击/脚本调用
- `tools/mvp/safeclaw_mvp.ps1`：PowerShell 包装，内部转调 `.cmd`
- `tools/mvp/safeclaw_mvp.py`：会话薄层实现，负责默认路径与最近会话复用


## Recommended Operator Path

- See `tools/mvp/OPERATOR_PLAYBOOK.md` for the shortest practical operator flow.
- Normal path first: `workspace --name demo -> doctor -> service-run --report`.
- `service-run` already includes one `service-status` summary; rerun `service-status` only when you need another queue / worker / effect snapshot.
- Optional explicit offline gate: `preflight --action service-run` before executing the local flow; `preflight --action ai-reason` now demonstrates the provider-unavailable deny path in the current local-only MVP; common wrapper / session actions auto-infer permission context from remembered session / workspace / default output, add `--scope demo.workspace` / `--write` / `--doctor-bypass` to override, and add `--enforce-permission` when scripts should fail closed on `confirm` / `deny`.
- Failed recovery path: `service-retry --report -> service-status`.
- Uncertain recovery path: `service-recover --report -> service-status`.


## 当前支持的动作

- `run`：创建任务并执行到完成
- `demo`：一键演示默认会话的 `run -> status -> report`
- `recover-demo`：一键演示 `seed-crash -> recover -> report`
- `retry-demo`：一键演示 `seed-failed -> retry -> report`
- `service-demo`: one-command worker service governance summary for `resolved / confirmation` queues
- `service-run`: run a task and immediately print the matching service summary; optional `--preflight` shows the gate for the exact prepared action, and `--enforce-permission` turns that gate into a fail-closed blocker
- `service-retry`: retry a failed task and immediately print the matching service summary; optional `--preflight` / `--enforce-permission` work the same way as `service-run`
- `service-recover`: recover an uncertain task and immediately print the matching service summary; optional `--preflight` / `--enforce-permission` work the same way as `service-run`
- `--report`: append `report` after `service-status`, so the practical path can end with a governance view in one command
- `service-status`: queue / lease / task snapshot summary for the selected db, including heartbeat / coordination summaries plus top-level local runtime snapshots (`runtime_profile`, `model_provider`, `sidecar`), recent task `scope` / `write` / `doctor_bypass` visibility, same-scope peer / scope-quarantine visibility (`scope_peer_count` / `scope_active_peer_count` / `scope_active_peer_task_id` / `scope_quarantine_active` / `scope_quarantine_source` / `scope_quarantine_task_id` / `scope_quarantine_count`), current `permission_tier` / `permission_policy` / `permission_reason`, latest lease freshness, active-lease wait timing, a `next_action` hint, a focused `next_task_id`, a copyable `next_command`, a short `next_reason`, the current `next_blocker` (including `scope_quarantine`), task-level `coordination_status` / `coordination_reason` / `coordination_summary`, a one-line `next_summary`, and explicit `reconcile_commands.executed` / `reconcile_commands.not_executed` choices for `executed_assumed` closeout scenes
- `preflight`: explicit gate for whether a target action stays allowed in the current local-only MVP entry; known local actions allow, unknown actions default deny, the preflight-only placeholder `ai-reason` now fails closed with `ERR_AI_PROVIDER_UNAVAILABLE`, common wrapper / session actions auto-infer permission context from remembered session / workspace / default output, optional `--scope` / `--write` / `--doctor-bypass` override that inferred context and surface `permission_tier` / `permission_policy` / `permission_reason`, and `--enforce-permission` turns that surfaced permission decision into a fail-closed gate
- `report`：查看指定任务 / effect 的治理视图
- `status`：默认查看当前记忆会话，也可配合 `--task-id` 使用
- `session`：显示当前记忆的最近成功会话，并在文本输出里带上 remembered session 文件路径
- `sessions`：列出当前数据库里的最近任务快照；默认优先使用 remembered session 的 `db`，并在文本/JSON 输出里标出来源
- `use`：按 `--index` 或 `--task-id` 激活某条历史会话，并在文本/JSON 输出里标出选择来源及 `db` / `output` / `owner_id` 来源
- `forget`：清空包装层记忆的最近会话，不删除数据库与输出文件；文本/JSON 输出都会显式给出 `reason` 与 `path`
- `workspace`: show or activate a named workspace; it fixes default `db` / `output`; `--clear` returns to global defaults while remembered session stays independent
- 若 remembered session 文件损坏，包装层会自动丢弃坏文件并回退为 `session => none`
- `demo` / `recover-demo` / `retry-demo` / `run` / `report` / `status` / `seed-crash` / `recover` / `seed-failed` / `retry` / `session` / `sessions` / `use` / `forget` / `workspace` / `doctor` / `preflight` / `verify` 支持 `--json`，统一返回 `{ok, action, schema_version, result|error}`
- `doctor`: checks wrapper entrypoints, Rust toolchain, linker, remembered session / workspace paths, reports current `db` / `output` sources (`flag` / `session` / `workspace` / `default`), and states that the current local MVP remains runnable without a model provider / sidecar; `--json` also returns `status`, `failing_checks`, `runtime_profile`, `model_provider`, and `sidecar`
- `preflight`: checks whether a target action remains allowed in the current local-only MVP entry; `ai-reason` is recognized as a preflight-only AI placeholder and returns `ERR_AI_PROVIDER_UNAVAILABLE` in the current offline MVP; `--json` also returns `tier`, `decision`, `offline_ready`, optional `target_scope` / `requires_write` / `doctor_bypass`, `permission_context_source`, `permission_context_applied`, `permission_enforced`, `action_allowed` / `action_decision` / `action_reason`, optional `error_code`, `permission_tier` / `permission_policy` / `permission_reason`, and current runtime/provider snapshots
- `verify`: run the practical operator flow gate via the current wrapper entry; `--json` returns script path, python path, exit code, and captured output
- `seed-crash`：制造超时后的 uncertain 持久化现场
- `recover`：在租约过期后恢复 uncertain runtime
- `seed-failed`：制造失败态但不自动结案
- `retry`：在租约过期后重新领取失败态并重试

## JSON 错误约定

- 包装层失败统一返回 `{ok: false, action, schema_version, error}`。
- `error.message` 是稳定的 wrapper 级错误消息，不再要求脚本解析底层 cargo 文案。
- `error.details.code` 当前已稳定提供：`invalid-argument`、`missing-task-context`。
- `invalid-argument` 表示包装层已识别出未知参数或缺少 flag 值，如 `--bogus`、`--db` 后缺值。
- `missing-task-context` 表示 `report` / `recover` / `retry` 缺少 `--task-id`，且当前没有可复用 remembered session；此时可显式传入 `--task-id`，或先执行 `use` / `run` / `seed-crash` / `seed-failed` 建立上下文。
- 对 `demo` / `recover-demo` / `retry-demo` 这类组合动作，若失败发生在 wrapper 预处理阶段，`error.details` 还会带上 `failed_step`、`code`、`error_message`，便于脚本直接定位失败步骤。
- 若当前存在 remembered session，包装层会在错误细节中尽量附带 `remembered_session`，方便脚本决定是否重试或切换上下文。
- `status` / `report` / `recover` / `retry` / `reconcile` successful `--json` results also expose `result.source_hints`, showing where `db` / `output` / `owner_id` / `task_context` came from.
- `demo` / `recover-demo` / `retry-demo` / `service-run` / `service-retry` / `service-recover` / `service-reconcile` successful `--json` results also expose `result.steps[*].source_hints`, so scripts can see when a combo starts reusing the remembered session.
- `demo` / `recover-demo` / `retry-demo` / `service-run` / `service-retry` / `service-recover` / `service-reconcile` successful `--json` results now return `result.remembered_session`; `result.session` remains only a compatibility alias.
- `service-demo` successful `--json` returns structured fields like `resolved_run`, `resolved_governance`, `confirmation_governance`, and `db_path`.
- `service-run` successful `--json` returns combo `steps`, a nested `run` result, and `service_status` summary fields.
- `service-retry` successful `--json` returns combo `steps`, a nested `retry` result, and `service_status` summary fields.
- `service-recover` successful `--json` returns combo `steps`, a nested `recover` result, and `service_status` summary fields.
- `service-reconcile` successful `--json` returns combo `steps`, a nested `reconcile` result, and `service_status` summary fields; after reconciliation it also closes the stale orchestrator lease so queue state returns to `expired=0`.
- `service-status` successful `--json` returns structured fields like top-level `runtime_profile`, `model_provider`, `sidecar`, `queue`, `workers`, `effects`, `probes`, top-level `heartbeat`, top-level `coordination`, and `recent_tasks`; top-level `coordination` now also carries `next_task_id`, and each recent task now also includes `target_scope`, `requires_write`, `doctor_bypass`, `permission_tier`, `permission_policy`, `permission_reason`, `lease_state`, `lease_owner_id`, latest lease snapshot fields, `lease_remaining_ms` for active leases, same-scope peer / scope-quarantine visibility (`scope_peer_count` / `scope_active_peer_count` / `scope_active_peer_task_id` / `scope_quarantine_active` / `scope_quarantine_source` / `scope_quarantine_task_id` / `scope_quarantine_count`), `next_action` (`ok` / `retry` / `recover` / `inspect`), `next_task_id`, a copyable `next_command`, a short `next_reason`, `next_blocker` (`none` / `active_lease` / `scope_quarantine` / `manual_review_needed`), task-level `coordination_status` / `coordination_reason` / `coordination_summary`, a concise `next_summary`, and `reconcile_commands.executed` / `reconcile_commands.not_executed` for the `executed_assumed` path; the text output also prints matching `service runtime => ...`, `service model => ...`, `service sidecar => ...`, and `service recent[i] reconcile => ...` lines.
- 若组合动作在底层执行阶段失败，错误 JSON 的 `error.details.steps[*].source_hints` 也会保留已进入失败步骤的来源，便于脚本区分“预处理失败”与“底层动作失败”。

## 最常用命令

第一次运行可以直接走默认会话路径：

```bat
tools\mvp\safeclaw_mvp.cmd demo
tools\mvp\safeclaw_mvp.cmd demo --preflight
tools\mvp\safeclaw_mvp.cmd demo --json
tools\mvp\safeclaw_mvp.cmd demo --preflight --json
tools\mvp\safeclaw_mvp.cmd recover-demo
tools\mvp\safeclaw_mvp.cmd recover-demo --preflight
tools\mvp\safeclaw_mvp.cmd recover-demo --json
tools\mvp\safeclaw_mvp.cmd recover-demo --preflight --json
tools\mvp\safeclaw_mvp.cmd retry-demo
tools\mvp\safeclaw_mvp.cmd retry-demo --preflight
tools\mvp\safeclaw_mvp.cmd retry-demo --json
tools\mvp\safeclaw_mvp.cmd retry-demo --preflight --json
tools\mvp\safeclaw_mvp.cmd service-demo
tools\mvp\safeclaw_mvp.cmd service-run --reset --limit 1
tools\mvp\safeclaw_mvp.cmd service-run --reset --limit 1 --preflight
tools\mvp\safeclaw_mvp.cmd service-run --reset --limit 1 --report
tools\mvp\safeclaw_mvp.cmd service-recover --task-id task-demo --limit 1
tools\mvp\safeclaw_mvp.cmd service-recover --task-id task-demo --limit 1 --report
tools\mvp\safeclaw_mvp.cmd seed-crash --reset --probe-mode none --task-id task-demo-assumed
tools\mvp\safeclaw_mvp.cmd service-reconcile --task-id task-demo-assumed --decision executed --limit 1
tools\mvp\safeclaw_mvp.cmd service-reconcile --task-id task-demo-assumed --decision executed --limit 1 --report
tools\mvp\safeclaw_mvp.cmd service-status
tools\mvp\safeclaw_mvp.cmd service-demo --json
tools\mvp\safeclaw_mvp.cmd service-run --reset --limit 1 --json
tools\mvp\safeclaw_mvp.cmd service-run --reset --limit 1 --preflight --json
tools\mvp\safeclaw_mvp.cmd service-run --reset --limit 1 --report --json
tools\mvp\safeclaw_mvp.cmd service-recover --task-id task-demo --limit 1 --json
tools\mvp\safeclaw_mvp.cmd service-recover --task-id task-demo --limit 1 --report --json
tools\mvp\safeclaw_mvp.cmd seed-crash --reset --probe-mode none --task-id task-demo-assumed --json
tools\mvp\safeclaw_mvp.cmd service-reconcile --task-id task-demo-assumed --decision executed --limit 1 --json
tools\mvp\safeclaw_mvp.cmd service-reconcile --task-id task-demo-assumed --decision executed --limit 1 --report --json
tools\mvp\safeclaw_mvp.cmd service-status --json
tools\mvp\safeclaw_mvp.cmd run --reset
tools\mvp\safeclaw_mvp.cmd run --reset --json
tools\mvp\safeclaw_mvp.cmd workspace
tools\mvp\safeclaw_mvp.cmd workspace --json
tools\mvp\safeclaw_mvp.cmd workspace --name demo
tools\mvp\safeclaw_mvp.cmd workspace --clear
tools\mvp\safeclaw_mvp.cmd session
tools\mvp\safeclaw_mvp.cmd session --json
tools\mvp\safeclaw_mvp.cmd sessions
tools\mvp\safeclaw_mvp.cmd use --index 0
tools\mvp\safeclaw_mvp.cmd forget
tools\mvp\safeclaw_mvp.cmd doctor
tools\mvp\safeclaw_mvp.cmd preflight --action service-run
tools\mvp\safeclaw_mvp.cmd preflight --action service-run --enforce-permission
tools\mvp\safeclaw_mvp.cmd preflight --action service-run --scope demo.workspace
tools\mvp\safeclaw_mvp.cmd preflight --action service-status --scope demo.workspace --write --enforce-permission
tools\mvp\safeclaw_mvp.cmd verify
tools\mvp\safeclaw_mvp.cmd doctor --json
tools\mvp\safeclaw_mvp.cmd preflight --action service-run --json
tools\mvp\safeclaw_mvp.cmd preflight --action service-status --scope demo.workspace --write --json
tools\mvp\safeclaw_mvp.cmd preflight --action service-status --scope demo.workspace --write --enforce-permission --json
tools\mvp\safeclaw_mvp.cmd verify --json
tools\mvp\safeclaw_mvp.cmd status
tools\mvp\safeclaw_mvp.cmd status --json
tools\mvp\safeclaw_mvp.cmd report
tools\mvp\safeclaw_mvp.cmd report --json
tools\mvp\safeclaw_mvp.cmd seed-failed --reset
tools\mvp\safeclaw_mvp.cmd service-retry --task-id task-demo --limit 1
tools\mvp\safeclaw_mvp.cmd seed-failed --reset --json
tools\mvp\safeclaw_mvp.cmd service-retry --task-id task-demo --limit 1 --json
tools\mvp\safeclaw_mvp.cmd retry
tools\mvp\safeclaw_mvp.cmd retry --json
tools\mvp\safeclaw_mvp.cmd seed-crash --reset
tools\mvp\safeclaw_mvp.cmd seed-crash --reset --json
tools\mvp\safeclaw_mvp.cmd recover
tools\mvp\safeclaw_mvp.cmd recover --json
tools\mvp\safeclaw_mvp.cmd reconcile --task-id task-demo-assumed --decision executed
tools\mvp\safeclaw_mvp.cmd reconcile --task-id task-demo-assumed --decision executed --json
```

如果你想显式控制路径，也仍然支持完整参数：

```bat
tools\mvp\safeclaw_mvp.cmd run --reset --db target\demo\session.db --output target\demo\output.txt --task-id task-demo
tools\mvp\safeclaw_mvp.cmd report --db target\demo\session.db --output target\demo\output.txt --task-id task-demo
tools\mvp\safeclaw_mvp.cmd status --db target\demo\session.db --output target\demo\output.txt
tools\mvp\safeclaw_mvp.cmd seed-crash --reset --db target\demo\session.db --output target\demo\output.txt --task-id task-demo
tools\mvp\safeclaw_mvp.cmd service-recover --db target\demo\session.db --output target\demo\output.txt --task-id task-demo --limit 1
tools\mvp\safeclaw_mvp.cmd recover --db target\demo\session.db --output target\demo\output.txt --task-id task-demo
tools\mvp\safeclaw_mvp.cmd seed-crash --reset --probe-mode none --db target\demo\session.db --output target\demo\output.txt --task-id task-demo-assumed
tools\mvp\safeclaw_mvp.cmd service-reconcile --db target\demo\session.db --output target\demo\output.txt --task-id task-demo-assumed --decision executed --limit 1
tools\mvp\safeclaw_mvp.cmd reconcile --db target\demo\session.db --output target\demo\output.txt --task-id task-demo-assumed --decision executed
tools\mvp\safeclaw_mvp.cmd seed-failed --reset --db target\demo\session.db --output target\demo\output.txt --task-id task-demo
tools\mvp\safeclaw_mvp.cmd service-retry --db target\demo\session.db --output target\demo\output.txt --task-id task-demo --limit 1
tools\mvp\safeclaw_mvp.cmd retry --db target\demo\session.db --output target\demo\output.txt --task-id task-demo
tools\mvp\safeclaw_mvp.cmd doctor --db target\demo\session.db --output target\demo\output.txt
tools\mvp\safeclaw_mvp.cmd service-run --reset --db target\demo\session.db --output target\demo\output.txt --task-id task-demo --limit 1
```
