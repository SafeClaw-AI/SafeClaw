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

## 当前支持的动作

- `run`：创建任务并执行到完成
- `demo`：一键演示默认会话的 `run -> status -> report`
- `recover-demo`：一键演示 `seed-crash -> recover -> report`
- `retry-demo`：一键演示 `seed-failed -> retry -> report`
- `report`：查看指定任务 / effect 的治理视图
- `status`：默认查看当前记忆会话，也可配合 `--task-id` 使用
- `session`：显示当前记忆的最近成功会话，并在文本输出里带上 remembered session 文件路径
- `sessions`：列出当前数据库里的最近任务快照；默认优先使用 remembered session 的 `db`，并在文本/JSON 输出里标出来源
- `use`：按 `--index` 或 `--task-id` 激活某条历史会话，并在文本/JSON 输出里标出选择来源及 `db` / `output` / `owner_id` 来源
- `forget`：清空包装层记忆的最近会话，不删除数据库与输出文件；文本/JSON 输出都会显式给出 `reason` 与 `path`
- 若 remembered session 文件损坏，包装层会自动丢弃坏文件并回退为 `session => none`
- `demo` / `recover-demo` / `retry-demo` / `run` / `report` / `status` / `seed-crash` / `recover` / `seed-failed` / `retry` / `session` / `sessions` / `use` / `forget` / `doctor` 支持 `--json`，统一返回 `{ok, action, schema_version, result|error}`
- `doctor`：快速检查包装入口、Rust 工具链、linker 与当前默认会话路径，并显式标出当前 `db` / `output` 来源（`flag` / `session` / `default`）；`--json` 结果还会给出聚合 `status` 与 `failing_checks`
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
- 若当前存在 remembered session，包装层会在错误细节中尽量附带 `remembered_session` 或 `session`，方便脚本决定是否重试或切换上下文。

## 最常用命令

第一次运行可以直接走默认会话路径：

```bat
tools\mvp\safeclaw_mvp.cmd demo
tools\mvp\safeclaw_mvp.cmd demo --json
tools\mvp\safeclaw_mvp.cmd recover-demo
tools\mvp\safeclaw_mvp.cmd recover-demo --json
tools\mvp\safeclaw_mvp.cmd retry-demo
tools\mvp\safeclaw_mvp.cmd retry-demo --json
tools\mvp\safeclaw_mvp.cmd run --reset
tools\mvp\safeclaw_mvp.cmd run --reset --json
tools\mvp\safeclaw_mvp.cmd session
tools\mvp\safeclaw_mvp.cmd session --json
tools\mvp\safeclaw_mvp.cmd sessions
tools\mvp\safeclaw_mvp.cmd use --index 0
tools\mvp\safeclaw_mvp.cmd forget
tools\mvp\safeclaw_mvp.cmd doctor
tools\mvp\safeclaw_mvp.cmd doctor --json
tools\mvp\safeclaw_mvp.cmd status
tools\mvp\safeclaw_mvp.cmd status --json
tools\mvp\safeclaw_mvp.cmd report
tools\mvp\safeclaw_mvp.cmd report --json
tools\mvp\safeclaw_mvp.cmd seed-failed --reset
tools\mvp\safeclaw_mvp.cmd seed-failed --reset --json
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
tools\mvp\safeclaw_mvp.cmd recover --db target\demo\session.db --output target\demo\output.txt --task-id task-demo
tools\mvp\safeclaw_mvp.cmd seed-failed --reset --db target\demo\session.db --output target\demo\output.txt --task-id task-demo
tools\mvp\safeclaw_mvp.cmd retry --db target\demo\session.db --output target\demo\output.txt --task-id task-demo
tools\mvp\safeclaw_mvp.cmd doctor --db target\demo\session.db --output target\demo\output.txt
```
