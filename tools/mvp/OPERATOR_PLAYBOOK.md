# MVP Operator Playbook

This playbook keeps only the shortest path that is actually useful for the current Win11 local MVP wrapper.

The goal is not to expose every command.
The goal is to lock one path that can run, inspect, recover, and be verified repeatedly.

## Recommended Entry

- Primary operator entry: `tools/mvp/safeclaw_mvp.cmd`
- Start with `workspace --name demo`, then `doctor`
- Prefer combo actions first: `service-run`, `service-retry`, `service-recover`
- Use `report` when you need the detailed governance view


## Main Path

### 0. Workspace selection

Pick one named workspace first so the wrapper can reuse stable `db/output` paths without repeating flags.

```bat
tools\mvp\safeclaw_mvp.cmd workspace --name demo
tools\mvp\safeclaw_mvp.cmd workspace --json
```

### 1. Environment check

```bat
tools\mvp\safeclaw_mvp.cmd doctor
tools\mvp\safeclaw_mvp.cmd doctor --json
```

### 2. Normal execution path

`service-run --report` performs `run -> service-status -> report` in one command.

```bat
tools\mvp\safeclaw_mvp.cmd service-run --reset --task-id task-demo --limit 1 --report
tools\mvp\safeclaw_mvp.cmd service-status --limit 5
```

### 3. Failed recovery path

When the task is failed, use `service-retry --report` first.

```bat
tools\mvp\safeclaw_mvp.cmd seed-failed --reset --task-id task-demo-failed
tools\mvp\safeclaw_mvp.cmd service-retry --task-id task-demo-failed --limit 1 --report
tools\mvp\safeclaw_mvp.cmd service-status --limit 5
```

### 4. Uncertain recovery path

When the task is uncertain, use `service-recover --report` first.

```bat
tools\mvp\safeclaw_mvp.cmd seed-crash --reset --task-id task-demo-uncertain
tools\mvp\safeclaw_mvp.cmd service-recover --task-id task-demo-uncertain --limit 1 --report
tools\mvp\safeclaw_mvp.cmd service-status --limit 5
```

Remember: workspace only fixes default `db/output`; remembered session still controls task/effect reuse for read actions.

## Verification

Use the wrapper first for the practical MVP gate:

```bat
tools\mvp\safeclaw_mvp.cmd verify
tools\mvp\safeclaw_mvp.cmd verify --json
```

Run the full protocol gate with any Python that can execute the wrapper:

```bat
set SAFECLAW_MVP_PYTHON=C:\path\to\python.exe
%SAFECLAW_MVP_PYTHON% tools\checks\selfcheck.py
```

## Current Guidance

- Treat `workspace -> doctor -> service-run --report` as the normal operator path
- Treat `service-retry --report` as the first recovery action for failed tasks
- Treat `service-recover --report` as the first recovery action for uncertain tasks
- Before adding more wrapper commands, keep this path stable and regression-safe
