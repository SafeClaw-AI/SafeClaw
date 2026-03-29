# V4 service-status current-session coordination record

- 时间：2026-03-30 00:19:11 +0800
- 轮次：M1b Slice 184
- 目标：继续收紧 `service-status` 顶层治理语义；当 remembered session 命中的当前任务仍在 recent window 内时，顶层 `coordination` 应优先跟随当前任务，不再被更新更近的历史行抢走摘要。

## 本轮动作
- 调整 `tools/mvp/safeclaw_mvp.py` 的 `build_service_coordination_payload()`：优先选择 `recent_tasks[*].current=true` 的当前任务行；若当前任务不在 recent window 内，再回退到最近一行。
- 在 `tools/checks/check_mvp_operator_flow.py` 新增“current task 不在 recent_tasks[0]”场景：同一 DB 内放入较新的 failed 任务和较旧但被 `use` 选中的 uncertain 任务，要求顶层 `coordination` 跟随当前任务而非更近历史行。
- 更新 `README.md`：明确顶层 `coordination` 在 remembered session 命中 recent window 时会优先跟随当前任务。

## 结果
- `service-status` 顶层 `coordination` 现已与 `session/use` 上下文对齐，不再因列表按更新时间排序而把更近历史任务误当成当前治理摘要。
- `recent_tasks` 排序与逐行事实保持不变；只收紧顶层摘要选行逻辑，降低 operator 对“当前任务”与“最近历史任务”的混读风险。

## 验证
- `python -m py_compile tools/mvp/safeclaw_mvp.py tools/checks/check_mvp_operator_flow.py`
- `python tools/checks/check_mvp_operator_flow.py`
- `python tools/checks/check_tooling_smoke.py`
- `cmd /c safeclaw.cmd service-status --limit 2 --json`
- `git diff --check`

## 下一步
- 继续盘点 `service-status` / `session` / `workspace` 顶层摘要里是否仍有“当前上下文”和“历史排序”混叠点，优先处理会误导 operator 行动的字段。
