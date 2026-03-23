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
- `session`：显示当前记忆的最近成功会话
- `sessions`：列出当前数据库里的最近任务快照
- `use`：按 `--index` 或 `--task-id` 激活某条历史会话
- `forget`：清空包装层记忆的最近会话，不删除数据库与输出文件
- `doctor`：快速检查包装入口、Rust 工具链、linker 与当前默认会话路径
- `seed-crash`：制造超时后的 uncertain 持久化现场
- `recover`：在租约过期后恢复 uncertain runtime
- `seed-failed`：制造失败态但不自动结案
- `retry`：在租约过期后重新领取失败态并重试

## 最常用命令

第一次运行可以直接走默认会话路径：

```bat
tools\mvp\safeclaw_mvp.cmd demo
tools\mvp\safeclaw_mvp.cmd recover-demo
tools\mvp\safeclaw_mvp.cmd retry-demo
tools\mvp\safeclaw_mvp.cmd run --reset
tools\mvp\safeclaw_mvp.cmd session
tools\mvp\safeclaw_mvp.cmd sessions
tools\mvp\safeclaw_mvp.cmd use --index 0
tools\mvp\safeclaw_mvp.cmd forget
tools\mvp\safeclaw_mvp.cmd doctor
tools\mvp\safeclaw_mvp.cmd status
tools\mvp\safeclaw_mvp.cmd report
tools\mvp\safeclaw_mvp.cmd seed-failed --reset
tools\mvp\safeclaw_mvp.cmd retry
tools\mvp\safeclaw_mvp.cmd seed-crash --reset
tools\mvp\safeclaw_mvp.cmd recover
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
