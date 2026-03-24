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
- Failed recovery path: `service-retry --report -> service-status`.
- Uncertain recovery path: `service-recover --report -> service-status`.


## 当前支持的动作

- `run`：创建任务并执行到完成
- `demo`：一键演示默认会话的 `run -> status -> report`
- `recover-demo`：一键演示 `seed-crash -> recover -> report`
- `retry-demo`：一键演示 `seed-failed -> retry -> report`
- `service-demo`: one-command worker service governance summary for `resolved / confirmation` queues
- `service-run`: run a task and immediately print the matching service summary
- `service-retry`: retry a failed task and immediately print the matching service summary
- `service-recover`: recover an uncertain task and immediately print the matching service summary
- `--report`: append `report` after `service-status`, so the practical path can end with a governance view in one command
- `service-status`: queue / lease / task snapshot summary for the selected db, including recent task `scope` / `write` / `doctor_bypass` visibility, latest lease freshness, a `next_action` hint, a copyable `next_command`, and a short `next_reason`
- `report`：查看指定任务 / effect 的治理视图
- `status`：默认查看当前记忆会话，也可配合 `--task-id` 使用
- `session`：显示当前记忆的最近成功会话，并在文本输出里带上 remembered session 文件路径
- `sessions`：列出当前数据库里的最近任务快照；默认优先使用 remembered session 的 `db`，并在文本/JSON 输出里标出来源
- `use`：按 `--index` 或 `--task-id` 激活某条历史会话，并在文本/JSON 输出里标出选择来源及 `db` / `output` / `owner_id` 来源
- `forget`：清空包装层记忆的最近会话，不删除数据库与输出文件；文本/JSON 输出都会显式给出 `reason` 与 `path`
- `workspace`: show or activate a named workspace; it fixes default `db` / `output`; `--clear` returns to global defaults while remembered session stays independent
- 若 remembered session 文件损坏，包装层会自动丢弃坏文件并回退为 `session => none`
- `demo` / `recover-demo` / `retry-demo` / `run` / `report` / `status` / `seed-crash` / `recover` / `seed-failed` / `retry` / `session` / `sessions` / `use` / `forget` / `workspace` / `doctor` / `verify` 支持 `--json`，统一返回 `{ok, action, schema_version, result|error}`
- `doctor`: checks wrapper entrypoints, Rust toolchain, linker, remembered session / workspace paths, reports current `db` / `output` sources (`flag` / `session` / `workspace` / `default`), and states that the current local MVP remains runnable without a model provider / sidecar; `--json` also returns `status`, `failing_checks`, `runtime_profile`, `model_provider`, and `sidecar`
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
- `status` / `report` / `recover` / `retry` 的成功 `--json` 结果现在会额外给出 `result.source_hints`，标出 `db` / `output` / `owner_id` / `task_context` 的来源，便于脚本确认是否复用了 remembered session。
- `demo` / `recover-demo` / `retry-demo` 的成功 `--json` 结果现在也会在 `result.steps[*].source_hints` 标出每一步的来源，便于脚本判断组合动作何时切换到 remembered session。
- `demo` / `recover-demo` / `retry-demo` 的成功 `--json` 结果现在会显式返回 `result.remembered_session`；`result.session` 仅作兼容别名，脚本应优先读取 `remembered_session`。
- `service-demo` successful `--json` returns structured fields like `resolved_run`, `resolved_governance`, `confirmation_governance`, and `db_path`.
- `service-run` successful `--json` returns combo `steps`, a nested `run` result, and `service_status` summary fields.
- `service-retry` successful `--json` returns combo `steps`, a nested `retry` result, and `service_status` summary fields.
- `service-recover` successful `--json` returns combo `steps`, a nested `recover` result, and `service_status` summary fields.
- `service-status` successful `--json` returns structured fields like `queue`, `workers`, `effects`, `probes`, and `recent_tasks`; each recent task now also includes `target_scope`, `requires_write`, `doctor_bypass`, `lease_state`, `lease_owner_id`, latest lease snapshot fields, `next_action` (`ok` / `retry` / `recover` / `inspect`), a copyable `next_command`, and a short `next_reason`.
- 若组合动作在底层执行阶段失败，错误 JSON 的 `error.details.steps[*].source_hints` 也会保留已进入失败步骤的来源，便于脚本区分“预处理失败”与“底层动作失败”。

## 最常用命令

第一次运行可以直接走默认会话路径：

```bat
tools\mvp\safeclaw_mvp.cmd demo
tools\mvp\safeclaw_mvp.cmd demo --json
tools\mvp\safeclaw_mvp.cmd recover-demo
tools\mvp\safeclaw_mvp.cmd recover-demo --json
tools\mvp\safeclaw_mvp.cmd retry-demo
tools\mvp\safeclaw_mvp.cmd service-demo
tools\mvp\safeclaw_mvp.cmd service-run --reset --limit 1
tools\mvp\safeclaw_mvp.cmd service-run --reset --limit 1 --report
tools\mvp\safeclaw_mvp.cmd service-recover --task-id task-demo --limit 1
tools\mvp\safeclaw_mvp.cmd service-recover --task-id task-demo --limit 1 --report
tools\mvp\safeclaw_mvp.cmd service-status
tools\mvp\safeclaw_mvp.cmd retry-demo --json
tools\mvp\safeclaw_mvp.cmd service-demo --json
tools\mvp\safeclaw_mvp.cmd service-run --reset --limit 1 --json
tools\mvp\safeclaw_mvp.cmd service-run --reset --limit 1 --report --json
tools\mvp\safeclaw_mvp.cmd service-recover --task-id task-demo --limit 1 --json
tools\mvp\safeclaw_mvp.cmd service-recover --task-id task-demo --limit 1 --report --json
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
tools\mvp\safeclaw_mvp.cmd verify
tools\mvp\safeclaw_mvp.cmd doctor --json
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
```

如果你想显式控制路径，也仍然支持完整参数：

```bat
tools\mvp\safeclaw_mvp.cmd run --reset --db target\demo\session.db --output target\demo\output.txt --task-id task-demo
tools\mvp\safeclaw_mvp.cmd report --db target\demo\session.db --output target\demo\output.txt --task-id task-demo
tools\mvp\safeclaw_mvp.cmd status --db target\demo\session.db --output target\demo\output.txt
tools\mvp\safeclaw_mvp.cmd seed-crash --reset --db target\demo\session.db --output target\demo\output.txt --task-id task-demo
tools\mvp\safeclaw_mvp.cmd service-recover --db target\demo\session.db --output target\demo\output.txt --task-id task-demo --limit 1
tools\mvp\safeclaw_mvp.cmd recover --db target\demo\session.db --output target\demo\output.txt --task-id task-demo
tools\mvp\safeclaw_mvp.cmd seed-failed --reset --db target\demo\session.db --output target\demo\output.txt --task-id task-demo
tools\mvp\safeclaw_mvp.cmd service-retry --db target\demo\session.db --output target\demo\output.txt --task-id task-demo --limit 1
tools\mvp\safeclaw_mvp.cmd retry --db target\demo\session.db --output target\demo\output.txt --task-id task-demo
tools\mvp\safeclaw_mvp.cmd doctor --db target\demo\session.db --output target\demo\output.txt
tools\mvp\safeclaw_mvp.cmd service-run --reset --db target\demo\session.db --output target\demo\output.txt --task-id task-demo --limit 1
```
