# V4 service-status live-only heartbeat timestamps record

- 时间：2026-03-29 23:48:02 +0800
- 轮次：M1b Slice 183
- 目标：继续收紧 `service-status` 顶层 `heartbeat` 语义；当最近记录仅为历史已完成/已释放任务且不存在 active lease 时，除了 `status=idle` 外，也不再回显历史 `latest_updated_at` / `latest_age_ms`。

## 本轮动作
- 调整 `tools/mvp/safeclaw_mvp.py` 的 `build_service_heartbeat_payload()`：无 active lease 时把 `latest_updated_at` 与 `latest_age_ms` 一并置为 `None`，只在存在 active lease 时回显实时 heartbeat 时间戳。
- 更新 `tools/checks/check_mvp_operator_flow.py`：把非 active lease 场景的顶层 heartbeat 时间戳合同改为 `None`。
- 更新 `tools/checks/check_tooling_smoke.py`：为 wrapper `service-status` 非活跃场景新增 `heartbeat.latest_updated_at=None` / `heartbeat.latest_age_ms=None` 断言，并把文本快照锁成 `latest_updated_at=none age_ms=none`。
- 更新 `README.md`：说明顶层 heartbeat 在无 active lease 时会同时清空 `latest_updated_at` / `latest_age_ms`，历史年龄只留在 `recent_tasks[*].lease_age_ms`。

## 结果
- 顶层 `heartbeat` 现已彻底代表“实时 active lease 心跳”，不再夹带历史任务更新时间。
- 历史任务的年龄信息仍保留在 `recent_tasks[*].lease_age_ms` / `recent_tasks[*].lease_freshness`，operator 仍可追历史，但不会把历史时间戳误读成实时心跳。

## 验证
- `python -m py_compile tools/mvp/safeclaw_mvp.py tools/checks/check_mvp_operator_flow.py tools/checks/check_tooling_smoke.py`
- `python tools/checks/check_mvp_operator_flow.py`
- `python tools/checks/check_tooling_smoke.py`
- `cmd /c safeclaw.cmd service-status --limit 1 --json`
- `git diff --check`

## 下一步
- 继续盘点 `service-status` / `coordination` / `session` 视图里是否还存在“历史事实”和“实时状态”混叠点，优先处理 operator 真会误判的语义缝隙。
