# tools/mvp/

当前 Win11 本地 MVP 的最小操作说明。

当前默认假设：

- 使用 Windows 11
- 使用 `stable-x86_64-pc-windows-gnu` Rust 工具链
- 已安装当前包装脚本内配置的 MinGW GCC linker

## 入口文件

- `tools/mvp/safeclaw_mvp.cmd`：推荐入口，适合 `cmd.exe` 与直接双击/脚本调用
- `tools/mvp/safeclaw_mvp.ps1`：PowerShell 包装，内部转调 `.cmd`

## 当前支持的动作

- `run`：创建任务并执行到完成
- `report`：查看指定任务 / effect 的治理视图
- `status`：只给 `--db` 时自动查看最新任务状态，也可配合 `--task-id` 使用
- `seed-crash`：制造超时后的 uncertain 持久化现场
- `recover`：在租约过期后恢复 uncertain runtime
- `seed-failed`：制造失败态但不自动结案
- `retry`：在租约过期后重新领取失败态并重试

## 最常用命令

```bat
tools\mvp\safeclaw_mvp.cmd run --reset --db target\demo\session.db --output target\demo\output.txt --task-id task-demo
tools\mvp\safeclaw_mvp.cmd report --db target\demo\session.db --output target\demo\output.txt --task-id task-demo
tools\mvp\safeclaw_mvp.cmd status --db target\demo\session.db --output target\demo\output.txt
tools\mvp\safeclaw_mvp.cmd seed-crash --reset --db target\demo\session.db --output target\demo\output.txt --task-id task-demo
tools\mvp\safeclaw_mvp.cmd recover --db target\demo\session.db --output target\demo\output.txt --task-id task-demo
tools\mvp\safeclaw_mvp.cmd seed-failed --reset --db target\demo\session.db --output target\demo\output.txt --task-id task-demo
tools\mvp\safeclaw_mvp.cmd retry --db target\demo\session.db --output target\demo\output.txt --task-id task-demo
```
