# MVP Operator Playbook

这份手册只保留当前 Win11 本地 MVP 命令入口真正有用的最短操作路径。

目标不是把所有命令都摊开。
目标是锁住一条能反复执行、检查、恢复、验证的白名单路径。

## 推荐入口

- 主操作入口：`tools/mvp/safeclaw_mvp.cmd`
- 根说明与总入口：`README.md`
- 字段级合同与维护层细节：`tools/mvp/README.md`
- 默认从 `workspace --name demo` 开始，再执行 `doctor`
- 优先使用组合动作：`service-run`、`service-retry`、`service-recover`
- 需要详细治理视图时再补 `report`

## 日用护栏

- 当前命令入口仍是**纯本地（local-only）**路径，即使尚未接入 AI 提供方或 sidecar 也可使用
- 把 `workspace --name demo -> doctor -> service-run --report -> service-status --limit 5 -> verify --json` 视为日用白路径
- failed 任务的第一恢复动作固定为 `service-retry --report`
- uncertain 任务的第一恢复动作固定为 `service-recover --report`
- `preflight --action ai-reason` 只用于确认当前纯本地 MVP 下 AI 路径仍保持阻断

## 主路径

下列示例优先只保留每条路径的主命令。若某一步执行完后你还想再看一次当前队列快照，再补 `tools\mvp\safeclaw_mvp.cmd service-status --limit 5`。

### 0. Workspace 选择

先固定一个命名 workspace，让命令入口复用稳定的 `db/output` 路径，避免重复传参数。

```bat
tools\mvp\safeclaw_mvp.cmd workspace --name demo
tools\mvp\safeclaw_mvp.cmd workspace --json
```

### 1. 环境检查

```bat
tools\mvp\safeclaw_mvp.cmd doctor
tools\mvp\safeclaw_mvp.cmd doctor --json
```

### 2. 正常执行路径

`service-run --report` 会在一条命令里完成 `run -> service-status -> report`。

```bat
tools\mvp\safeclaw_mvp.cmd service-run --reset --task-id task-demo --limit 1 --report
```

### 3. failed 恢复路径

任务进入 failed 后，先用 `service-retry --report`。

```bat
tools\mvp\safeclaw_mvp.cmd seed-failed --reset --task-id task-demo-failed
tools\mvp\safeclaw_mvp.cmd service-retry --task-id task-demo-failed --limit 1 --report
```

### 4. uncertain 恢复路径

任务进入 uncertain 后，先用 `service-recover --report`。

```bat
tools\mvp\safeclaw_mvp.cmd seed-crash --reset --task-id task-demo-uncertain
tools\mvp\safeclaw_mvp.cmd service-recover --task-id task-demo-uncertain --limit 1 --report
```

提示：workspace 只固定默认 `db/output`；读动作是否复用 task/effect，仍由最近一次成功会话记忆决定。

## 验证

先用当前命令入口跑一遍最小可用验收：

```bat
tools\mvp\safeclaw_mvp.cmd verify
tools\mvp\safeclaw_mvp.cmd verify --json
```

再用任意能执行当前命令入口的 Python 跑完整协议门禁：

```bat
set SAFECLAW_MVP_PYTHON=C:\path\to\python.exe
%SAFECLAW_MVP_PYTHON% tools\checks\selfcheck.py
```

当前 selfcheck 策略：

- `verify` 只跑当前最小可用白路径验收
- `tools/checks/selfcheck.py` 会先跑 `ledger_index_manifest.py`
- 然后依次跑 `check_ledger_alignment.py`、`check_consistency.py`、`check_versions.py`、`check_structure.py`、`check_scaffold.py`、`check_public_docs.py`
- 这条台账门禁链会显式前置在合同测试（Contract tests）之前
