# MVP Operator Playbook

This playbook keeps only the shortest path that is actually useful for the current Win11 local MVP wrapper.

The goal is not to expose every command.
The goal is to lock one path that can run, inspect, recover, and be verified repeatedly.

## Recommended Entry

- Primary operator entry: `tools/mvp/safeclaw_mvp.cmd`
- Start with `doctor`
- Prefer combo actions first: `service-run`, `service-retry`, `service-recover`
- Use `report` when you need the detailed governance view

## Main Path

### 1. Environment check

```bat
tools\mvp\safeclaw_mvp.cmd doctor
tools\mvp\safeclaw_mvp.cmd doctor --json
```

### 2. Normal execution path

`service-run` already performs `run -> service-status`.
If you need the detailed governance view after that, run `report`.

```bat
tools\mvp\safeclaw_mvp.cmd service-run --reset --task-id task-demo --db target\mvp\operator-demo.db --output target\mvp\operator-demo.txt --limit 1
tools\mvp\safeclaw_mvp.cmd report
tools\mvp\safeclaw_mvp.cmd service-status --db target\mvp\operator-demo.db --limit 5
```

### 3. Failed recovery path

When the task is failed, use `service-retry` first.

```bat
tools\mvp\safeclaw_mvp.cmd seed-failed --reset --task-id task-demo-failed --db target\mvp\operator-retry.db --output target\mvp\operator-retry.txt
tools\mvp\safeclaw_mvp.cmd service-retry --db target\mvp\operator-retry.db --task-id task-demo-failed --limit 1
tools\mvp\safeclaw_mvp.cmd report
tools\mvp\safeclaw_mvp.cmd service-status --db target\mvp\operator-retry.db --limit 5
```

### 4. Uncertain recovery path

When the task is uncertain, use `service-recover` first.

```bat
tools\mvp\safeclaw_mvp.cmd seed-crash --reset --task-id task-demo-uncertain --db target\mvp\operator-recover.db --output target\mvp\operator-recover.txt
tools\mvp\safeclaw_mvp.cmd service-recover --db target\mvp\operator-recover.db --task-id task-demo-uncertain --limit 1
tools\mvp\safeclaw_mvp.cmd report
tools\mvp\safeclaw_mvp.cmd service-status --db target\mvp\operator-recover.db --limit 5
```

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

- Treat `doctor -> service-run -> report` as the normal operator path
- Treat `service-retry` as the first recovery action for failed tasks
- Treat `service-recover` as the first recovery action for uncertain tasks
- Before adding more wrapper commands, keep this path stable and regression-safe
