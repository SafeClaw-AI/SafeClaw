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


## 推荐维护路径

- 这份 README 主要服务维护层 MVP 流程，不承担面对普通使用者的完整上手说明。
- 如果你只想走主人自用的个人 MVP 闭环，优先看 `tools/mvp/PERSONAL_MVP_PLAYBOOK.md`，并使用那里部署出来的生产位入口。
- 个人生产位的 `safeclaw-personal-panel.cmd/.ps1` 当前会拉起 `safeclaw_personal_panel.pyw`，也就是一层轻量 Python/Tkinter 面板；它不是规划中的 Tauri/React 桌面界面。
- 最短维护路径看 `tools/mvp/OPERATOR_PLAYBOOK.md`；若要先部署一套可回退的个人生产位，可执行 `python -X utf8 tools/mvp/safeclaw_personal_deploy.py deploy`。
- 默认先走 `workspace --name demo -> doctor -> service-run --report`。
- `service-run` 已经自带一次 `service-status` 摘要；只有在你还想再看 queue / worker / effect 快照时，才需要额外执行 `service-status`。
- 若要在真正执行前显式确认离线门禁，可先跑 `preflight --action service-run`。
- `preflight --action ai-reason` 会稳定显示“当前 local-only MVP 还不能调用 AI 提供方”这一拒绝结果；`service-status` 顶层 `offline_gate` 会镜像同一事实。
- 常见命令入口 / session 动作会自动从最近一次成功会话、workspace、默认 output 推断权限上下文；如需显式覆盖，使用 `--scope demo.workspace` / `--write` / `--doctor-bypass`；如需在 `confirm` / `deny` 时直接硬阻断，加 `--enforce-permission`；如需让组合动作复用 AI 离线门禁合同，加 `--preflight-action ai-reason`。
- failed 恢复路径先走 `service-retry --report`；若还想再看一次当前队列快照，再补 `service-status`。
- uncertain 恢复路径先走 `service-recover --report`；若还想再看一次当前队列快照，再补 `service-status`。


## 当前支持的动作

- `run`：创建任务并执行到完成
- `demo`：一键演示默认会话的 `run -> status -> report`
- `recover-demo`：一键演示 `seed-crash -> recover -> report`
- `retry-demo`：一键演示 `seed-failed -> retry -> report`
- `service-demo`：一条命令输出 `resolved / confirmation` 队列的 worker service 治理摘要。
- `service-run`：执行任务后立刻打印对应的 service 摘要；可选 `--preflight` 会先展示同一动作的门禁结果，`--enforce-permission` 会把该门禁直接变成硬阻断。
- `service-retry`：重试 failed 任务后立刻打印对应的 service 摘要；`--preflight` / `--enforce-permission` 语义与 `service-run` 相同。
- `service-recover`：恢复 uncertain 任务后立刻打印对应的 service 摘要；`--preflight` / `--enforce-permission` 语义与 `service-run` 相同。
- `service-resume`：恢复 hibernated 任务后立刻打印对应的 service 摘要；`--preflight` / `--enforce-permission` 语义与 `service-run` 相同；若目标任务已不再 hibernated，`--json` 会稳定返回 `resume-target-missing` / `resume-target-not-hibernated`，并附带 `service-status` 提示。
- `--report`：在 `service-status` 之后顺手补 `report`，把同一路径收口到治理视图；`service-resume --report` 现已成为 hibernated 任务的一条命令收口路径。
- `service-status`：查看所选 db 的 queue / lease / coordination 快照，并镜像顶层本地 runtime 快照（`runtime_profile`、`model_provider`、`sidecar`、`offline_gate`）、recent task 的 `next_*` 提示、remembered-session-aware 顶层 `coordination` 与 `executed_assumed` 的 reconcile 选择；精确 JSON 字段见下方“JSON 错误约定”。
- `preflight`：显式检查某个目标动作在当前 local-only MVP 下是否仍被允许；已知命令入口 / session 动作放行，未知动作默认拒绝，`ai-reason` 会稳定返回 `ERR_AI_PROVIDER_UNAVAILABLE`，也就是“当前还不能调用 AI 提供方”；可用 `--scope` / `--write` / `--doctor-bypass` 覆盖推断上下文，用 `--enforce-permission` 做硬阻断，用 `--preflight-action <name>` 让组合动作复用另一条门禁合同。
- `report`：查看指定任务 / effect 的治理视图
- `status`：默认查看当前记忆会话，也可配合 `--task-id` 使用
- `session`：显示当前记忆的最近成功会话，并在文本输出里带上对应记忆文件路径
- `sessions`：列出当前数据库里的最近任务快照；默认优先使用最近一次成功会话记忆里的 `db`，并在文本/JSON 输出里标出来源
- `use`：按 `--index` 或 `--task-id` 激活某条历史会话，并在文本/JSON 输出里标出选择来源及 `db` / `output` / `owner_id` 来源
- `forget`：清空包装层记忆的最近会话，不删除数据库与输出文件；文本/JSON 输出都会显式给出 `reason` 与 `path`
- `workspace`：显示或激活一个命名 workspace，并固定默认 `db` / `output`；`--clear` 会回到全局默认路径，但 remembered session 仍保持独立。
- 若 remembered session 文件损坏，包装层会自动丢弃坏文件并回退为 `session => none`
- `demo` / `recover-demo` / `retry-demo` / `service-run` / `service-retry` / `service-recover` / `service-resume` / `run` / `report` / `status` / `seed-crash` / `seed-hibernated` / `recover` / `seed-failed` / `retry` / `resume` / `session` / `sessions` / `use` / `forget` / `workspace` / `doctor` / `preflight` / `verify` 支持 `--json`，统一返回 `{ok, action, schema_version, result|error}`
- `doctor`：检查命令入口、Rust 工具链、linker、最近一次成功会话记忆 / workspace 路径，并报告当前 `db` / `output` 来源（`flag` / `session` / `workspace` / `default`）；同时明确当前 local MVP 即使没有 model provider / sidecar 仍可运行；`--json` 还会返回 `status`、`failing_checks`、`runtime_profile`、`model_provider`、`sidecar`。
- `verify`：通过当前命令入口执行最小可用白路径验收；`--json` 会返回 script path、python path、exit code 与 captured output。
- `seed-crash`：制造超时后的 uncertain 持久化现场
- `recover`：在租约过期后恢复 uncertain runtime
- `seed-failed`：制造失败态但不自动结案
- `retry`：在租约过期后重新领取失败态并重试

## JSON 错误约定

- 失败统一返回 `{ok: false, action, schema_version, error}`；成功统一返回 `{ok: true, action, schema_version, result}`。
- `error.message` 是稳定的命令入口级错误消息，不再要求脚本解析底层 cargo 文案；基础错误码看 `error.details.code`。
- 当前稳定错误码可先按这 5 类理解：
  - `invalid-argument`：参数未知或缺少 flag 值。
  - `missing-task-context`：`report` / `recover` / `retry` / `resume` 缺少 `--task-id`，且当前没有可复用 remembered session。
  - `preflight-blocked`：动作被入口层 preflight 拦下。
  - `resume-target-missing`：当前没有可继续的 hibernated runtime。
  - `resume-target-not-hibernated`：当前任务不是 hibernated，`resume` 不适用。
- 对被 preflight 拦下的组合动作，顶层会稳定镜像 `error.code=preflight-blocked`、`error.reason`、可选 `error.error_code`、`error.degradation_mode`、`error.requires_model`、`error.requires_sidecar`、`error.summary`、`error.requested_action`；完整 preflight 载荷保留在 `error.details.preflight`，浅层快捷镜像保留在 `error.details.preflight_*`。若使用 `--preflight-action ai-reason`，可稳定读取 `error.details.preflight.error_code=ERR_AI_PROVIDER_UNAVAILABLE`。
- `service-resume` 在 `resume-target-missing` / `resume-target-not-hibernated` 场景下，还会在 `error.details` 里补上 `error_message` / `next_command`，减少人工回看成本。
- 组合动作若失败在入口层预处理阶段，`error.details` 会带 `failed_step` / `code` / `error_message`；若失败在底层执行阶段，`error.details.steps[*].source_hints` 会保留已进入失败步骤的来源。
- 若当前存在 remembered session，错误细节中会尽量附带 `remembered_session`，方便脚本决定是否重试或切换上下文。
- 成功结果的来源字段统一按两层看：
  - 单步动作：`result.source_hints` 说明 `db` / `output` / `owner_id` / `task_context` 来源。
  - 组合动作：`result.steps[*].source_hints` 说明每一步何时开始复用 remembered session。
- `demo` / `recover-demo` / `retry-demo` / `service-run` / `service-retry` / `service-recover` / `service-resume` / `service-reconcile` 成功时会稳定返回 `result.remembered_session`；`result.session` 只保留兼容别名。
- 常见成功载荷可按 4 组记：
  - `service-demo`：返回 `resolved_run` / `resolved_governance` / `confirmation_governance` / `db_path`。
  - `service-run` / `service-retry` / `service-recover` / `service-reconcile`：返回组合 `steps`、嵌套动作结果与 `service_status` 摘要；其中 `service-reconcile` 还会把过期 orchestrator lease 收回，让队列回到 `expired=0`。
  - `service-status`：返回顶层 `runtime_profile` / `model_provider` / `sidecar` / `offline_gate` / `queue` / `workers` / `effects` / `probes` / `heartbeat` / `coordination` / `recent_tasks`；`offline_gate` 镜像当前 `preflight --action ai-reason` 阻断事实，`coordination` 带 `next_task_id`，`recent_tasks[*]` 带 `next_*`、权限、租约与 `reconcile_commands.*`。
  - 文本输出仍会同步打印 `service runtime => ...`、`service model => ...`、`service sidecar => ... detail=...`、`service offline => ...`、`service recent[i] reconcile => ...`，方便脚本外人工排障。
- `preflight --json` 只要命令格式合法，就始终返回成功信封 `{ok: true, action: "preflight", result: ...}`；是否允许执行由 `result.allowed` 与进程退出码表达，而不是切成错误信封。

### 常用 JSON 成功载荷

`preflight --json`

| 字段 / 字段组 | 含义 |
| --- | --- |
| `requested_action` | 当前正在判定的目标动作名，例如 `service-run` 或 `ai-reason` |
| `known` / `action_class` / `tier` / `writes_state` | 当前动作是否已知、属于本地动作还是会话动作、对应的风险层级，以及是否写状态 |
| `permission_context_source` / `permission_context_applied` | 权限上下文来自显式参数、动作模板还是不存在；是否真正拿到了可评估的上下文 |
| `target_scope` / `requires_write` / `doctor_bypass` | 预检最终使用的 scope / 写入意图 / doctor 特权上下文 |
| `permission_tier` / `permission_policy` / `permission_reason` | 入口层给出的权限判定建议；`permission_policy` 可能是 `allow` / `confirm` / `deny` / `not_evaluated` |
| `permission_enforced` / `action_allowed` / `action_decision` / `action_reason` | 动作本身是否在当前 local-only MVP 白名单内，以及白名单层的判定原因 |
| `allowed` / `decision` / `reason` | 最终 preflight 结论；脚本通常直接读取这组字段决定是否继续 |
| `offline_ready` / `requires_model` / `requires_sidecar` / `degradation_mode` / `error_code` / `detail` | 当前动作在离线 MVP 下是否可执行，以及如果被 AI/provider 阻断时的降级与错误事实 |
| `runtime_profile` / `model_provider` / `sidecar` | 当前本地运行态快照；结构与 `service-status --json` 顶层对应字段一致 |

`verify --json`

| 字段 | 含义 |
| --- | --- |
| `python` | 当前 wrapper 实际使用的 Python 解释器路径 |
| `script` | 固定为 `tools/checks/check_mvp_operator_flow.py` |
| `exit_code` | 验证脚本退出码；成功时为 `0` |
| `captured_output` | 合并后的 stdout/stderr 文本，保留完整 operator-flow 日志 |

`service-status --json`

| 字段 / 字段组 | 含义 |
| --- | --- |
| `db` / `db_source` / `limit` | 本次读取的状态库路径、路径来源（如 `flag` / `session` / `workspace` / `default`）和 recent task 数量上限 |
| `current_session` / `current_db` | 当前 remembered session；若没有已记住的最近会话则为 `null` / `false` |
| `runtime_profile` / `model_provider` / `sidecar` | 当前 local-only MVP 的运行态快照；用于显式说明 provider / sidecar 仍未接通 |
| `offline_gate` | `preflight --action ai-reason` 的镜像摘要，包含 `status` / `reason` / `summary` / `requested_action` / `requires_*` / `next_command` / `error_code` / `detail` |
| `queue` | 固定四个计数字段：`queued` / `active` / `expired` / `completed` |
| `workers` / `effects` / `probes` | 稀疏计数 map；只返回当前实际出现的状态键，例如 `{"failed": 1}` 或 `{"none": 1}` |
| `heartbeat` | 顶层活跃租约心跳摘要，固定返回 `interval_ms` / `event_driven` / `latest_updated_at` / `latest_age_ms` / `latest_freshness` / `status` / `reason`；若没有 active lease，则 `latest_*` 为 `null` 且 `status=idle` |
| `coordination` | 当前服务级建议动作摘要；优先选 remembered session 对应 task，否则退回 recent_tasks 第一条。包含 `status` / `reason` / `summary` / `task_id` / `target_scope` / `next_*` / `scope_*` |
| `recent_tasks[*]` | 单条任务快照；稳定包含任务身份字段、权限字段、租约字段、scope 协调字段、`next_*`、`coordination_*`、`current` 与按需出现的 `reconcile_commands` |

`service-run --json` / `service-retry --json` / `service-recover --json` / `service-resume --json` / `service-reconcile --json`

| 字段 / 字段组 | 含义 |
| --- | --- |
| `steps` | 组合步骤列表。基础顺序是 `[session-action, service-status]`；带 `--report` 时追加 `report`；带 `--preflight` 时最前面插入 `preflight` |
| `steps[*].action` | 固定动作名之一：`preflight`、底层会话动作（`run` / `retry` / `recover` / `resume` / `reconcile`）、`service-status`、可选 `report` |
| `steps[*].ok` / `steps[*].exit_code` | 每一步自己的成功状态与退出码，方便脚本定位失败步骤 |
| `steps[*].source_hints` | 每一步的参数来源；会话动作通常带 `db` / `output` / `owner_id` / `task_context`，`service-status` 只带 `db` / `task_context`，`preflight` 只带 `permission_context` |
| `remembered_session` / `session` | 顶层记忆会话快照；`session` 只是兼容别名，内容与 `remembered_session` 相同 |
| `<session-action>` | 动态嵌套键，对应底层会话动作名：`run` / `retry` / `recover` / `resume` / `reconcile`。结构与单步动作结果一致，稳定包含 `prepared` / `captured_output` / `saved_session` / `remembered_session` / `source_hints` |
| `service_status` | 紧跟组合动作执行后的 `service-status` 完整 payload，结构与单独执行 `service-status --json` 相同 |
| `preflight` | 仅在带 `--preflight` 或 `--enforce-permission` 时出现；结构与单独执行 `preflight --json` 相同 |
| `report` | 仅在带 `--report` 时出现；结构与单步 `report` 结果一致，稳定包含 `prepared` / `captured_output` / `saved_session` / `remembered_session` / `source_hints` |

关于组合 JSON，有 3 条容易误用的固定事实：

- 顶层嵌套键不是固定叫 `run`；它会随组合动作变化，例如 `service-retry --json` 返回 `result.retry`，`service-resume --json` 返回 `result.resume`。
- `service_status` 总是组合结果里的完整快照，不是简化摘要；脚本可以直接复用它而不必再额外跑一次 `service-status --json`。
- `steps` 是最稳定的机器可读执行轨迹；如果只关心执行顺序和来源，优先消费 `steps[*]`，再按需读取嵌套 payload。

`service-resume --json` 失败时的专属错误合同

| 场景 | 顶层 `error.code` | `error.reason` | `error.details` 补充字段 |
| --- | --- | --- | --- |
| 当前没有可继续的 hibernated runtime | `resume-target-missing` | `hibernated_runtime_missing` | `code` / `error_message` / `summary` / `next_command` |
| 当前任务存在，但已不是 hibernated | `resume-target-not-hibernated` | `resume_target_not_hibernated` | `code` / `error_message` / `summary` / `next_command` |

这两类 `service-resume` 失败都会保留：

- `error.message=failed step=resume`
- `error.details.failed_step=resume`
- `error.details.steps[0].action=resume`
- `error.details.captured_output` 保留底层原始输出，便于排障

`doctor --json` / `session --json` / `sessions --json` / `use --json` / `forget --json` / `workspace --json`

| 动作 | 稳定字段 / 结构 | 说明 |
| --- | --- | --- |
| `doctor --json` | `repo` / `status` / `failing_checks` / `python` / `entrypoints` / `cargo` / `toolchain` / `linker` / `runtime_profile` / `model_provider` / `sidecar` / `session` / `session_path` / `workspace` / `db` / `output` | 当前入口层总健康检查；`db` 与 `output` 是对象，分别带 `path` / `exists` / `source` |
| `session --json` | `task_id` / `effect_id` / `db` / `output` / `owner_id` | 当前 remembered session 快照；如果没有 remembered session，则 `result=null` |
| `sessions --json` | `db` / `db_source` / `limit` / `current_session` / `rows` | `rows[*]` 结构接近 `service-status.recent_tasks[*]`，但不附带 `next_summary` / `next_command` / `reconcile_commands` |
| `use --json` | `task_id` / `effect_id` / `db` / `db_source` / `output` / `output_source` / `owner_id` / `owner_id_source` / `source` | 激活某条历史会话；`source` 形如 `task:<task-id>`，其余 `*_source` 会随 `--task-id` / `--index` / `--db` 的选择路径变化 |
| `forget --json` | `forgot` / `path` / `reason` | 只清 remembered session 文件，不删数据库与输出；`reason` 通常是 `removed` 或 `none` |
| `workspace --json` | 共有 `path`；其余按模式分 3 种 | 见下方“workspace 三种结果形态” |

关于这组管理动作，有 4 条固定事实：

- `doctor --json` 正常情况下仍走成功信封；是否健康主要看 `result.status` 与 `result.failing_checks`，而不是只看是否有 JSON 输出。
- `session --json` 与顶层 `remembered_session` 不同，它只返回当前 remembered session 本体，不再包 `source_hints`。
- `sessions --json` 的 `rows[*].current` 只表示“这一行是否等于当前 remembered session”，不表示该任务一定是最新更新时间或唯一推荐动作。
- `use --json` 的 `db_source` / `output_source` / `owner_id_source` 是来源提示，不是固定常量；当你显式传 `--db` 时，它们和默认走 remembered session 的结果可能不同。

`workspace --json` 三种结果形态

| 触发方式 | 结果结构 | 说明 |
| --- | --- | --- |
| `workspace --json` | `active` / `name` / `db` / `output` / `path` | 查询当前 workspace 状态；未激活时 `active=false`、`name=null`，`db/output` 回到默认路径 |
| `workspace --name demo --json` | `active` / `name` / `db` / `output` / `path` / `changed` | 激活命名 workspace；`changed=true` 表示当前命令刚写入了 workspace 选择 |
| `workspace --clear --json` | `cleared` / `path` / `reason` | 清除 workspace 记忆；`reason` 通常是 `removed` 或 `none` |

## 最常用命令

优先按场景取最短路径，不再把同一动作按所有参数排列一遍。

```bat
:: 日常白名单路径
tools\mvp\safeclaw_mvp.cmd workspace --name demo
tools\mvp\safeclaw_mvp.cmd doctor
tools\mvp\safeclaw_mvp.cmd service-run --reset --task-id task-demo --limit 1 --report
tools\mvp\safeclaw_mvp.cmd service-status --limit 5
tools\mvp\safeclaw_mvp.cmd verify --json

:: 异常恢复路径
tools\mvp\safeclaw_mvp.cmd seed-failed --reset --task-id task-demo-failed
tools\mvp\safeclaw_mvp.cmd service-retry --task-id task-demo-failed --limit 1 --report
tools\mvp\safeclaw_mvp.cmd seed-crash --reset --task-id task-demo-uncertain
tools\mvp\safeclaw_mvp.cmd service-recover --task-id task-demo-uncertain --limit 1 --report
tools\mvp\safeclaw_mvp.cmd seed-crash --reset --probe-mode none --task-id task-demo-assumed
tools\mvp\safeclaw_mvp.cmd service-reconcile --task-id task-demo-assumed --decision executed --limit 1 --report

:: JSON / 脚本入口
tools\mvp\safeclaw_mvp.cmd demo --json
tools\mvp\safeclaw_mvp.cmd preflight --action service-run --json
tools\mvp\safeclaw_mvp.cmd service-run --reset --limit 1 --report --json
tools\mvp\safeclaw_mvp.cmd service-status --json
tools\mvp\safeclaw_mvp.cmd verify --json

:: 会话与显式路径
tools\mvp\safeclaw_mvp.cmd session
tools\mvp\safeclaw_mvp.cmd sessions
tools\mvp\safeclaw_mvp.cmd use --index 0
tools\mvp\safeclaw_mvp.cmd forget
tools\mvp\safeclaw_mvp.cmd workspace --clear
tools\mvp\safeclaw_mvp.cmd run --reset --db target\demo\session.db --output target\demo\output.txt --task-id task-demo
tools\mvp\safeclaw_mvp.cmd service-recover --db target\demo\session.db --output target\demo\output.txt --task-id task-demo --limit 1
tools\mvp\safeclaw_mvp.cmd service-reconcile --db target\demo\session.db --output target\demo\output.txt --task-id task-demo-assumed --decision executed --limit 1
```

如果你只想快速扫一遍命令覆盖面，再看这些动作名即可：

```text
demo / recover-demo / retry-demo
run / report / status
service-run / service-retry / service-recover / service-resume / service-reconcile / service-status
workspace / session / sessions / use / forget / doctor / preflight / verify
seed-failed / seed-crash / seed-hibernated / retry / recover / resume / reconcile
```

如果你想显式控制路径，也仍然支持完整参数；以下保留最小对照样例：

```bat
tools\mvp\safeclaw_mvp.cmd status --db target\demo\session.db --output target\demo\output.txt
tools\mvp\safeclaw_mvp.cmd preflight --action service-run
tools\mvp\safeclaw_mvp.cmd preflight --action service-run --enforce-permission
tools\mvp\safeclaw_mvp.cmd preflight --action service-status --scope demo.workspace --write --json
tools\mvp\safeclaw_mvp.cmd report --db target\demo\session.db --output target\demo\output.txt --task-id task-demo
tools\mvp\safeclaw_mvp.cmd service-retry --db target\demo\session.db --output target\demo\output.txt --task-id task-demo --limit 1
tools\mvp\safeclaw_mvp.cmd doctor --db target\demo\session.db --output target\demo\output.txt
tools\mvp\safeclaw_mvp.cmd service-run --reset --db target\demo\session.db --output target\demo\output.txt --task-id task-demo --limit 1
```

## 台账优先策略

- `tools/mvp/README.md` 只保留当前可手用 MVP 的最短操作链，不重复展开底层 ledger policy chain 细节。
- `tools/checks/selfcheck.py` 与 `.github/workflows/contracts.yml` 会先跑 `ledger_index_manifest.py`，确认协议台账入口完整，再继续后续门禁。
- 随后串行执行 `check_ledger_alignment.py`、`check_consistency.py`、`check_versions.py`、`check_structure.py`、`check_scaffold.py`、`check_public_docs.py`，全部通过后才进入 `Contract tests`。
