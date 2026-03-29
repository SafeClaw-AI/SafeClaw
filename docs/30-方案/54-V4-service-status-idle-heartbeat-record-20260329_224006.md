# V4 service-status idle heartbeat 收口记录（2026-03-29 22:40:06 +0800）

## 本轮动作
- 调整 `tools/mvp/safeclaw_mvp.py` 的 `build_service_heartbeat_payload()`：仅当存在 active lease 时才把顶层 heartbeat 视为真实心跳；若当前只有历史任务，则回到 `idle`。
- 同步更新 `tools/checks/check_mvp_operator_flow.py` 与 `tools/checks/check_tooling_smoke.py`，把“历史已完成任务仍报 failed”改为“无 active lease 心跳时 idle”。
- 同步补 `README.md` 的 `service-status` 说明，明确顶层 heartbeat 不再把历史任务误报成失败。

## 为什么做这刀
- 当前本机真实 `service-status` 会在只有历史已完成任务时仍显示 `heartbeat.status=failed`，这会把“无正在进行的心跳拥有者”和“真故障”混在一起。
- 长期看，心跳应该只表达 active lease 的新鲜度；历史任务是否已完成、是否需要 follow-up，应交给 `coordination` 与 `next_*` 字段表达。
- 这刀短期要动运行时口径与 smoke/flow 合同，难度比继续补文档更高，但长期可读性和判断稳定性更好。

## 结果
1. `tools/mvp/safeclaw_mvp.py`
   - 顶层 `heartbeat` 现在仅在存在 active lease 时才显示 `fresh/slow/lost`；否则回到 `none/idle`。
2. `tools/checks/check_mvp_operator_flow.py` / `tools/checks/check_tooling_smoke.py`
   - 已把历史已完成任务场景的心跳合同更新为 `latest_freshness=none`、`status=idle`、`reason=no_active_lease_heartbeat`。
3. `README.md`
   - 已明确说明：历史已完成/已释放任务不再把顶层 heartbeat 误报成 `failed`。

## 最小验证
- `python -m py_compile tools/mvp/safeclaw_mvp.py tools/checks/check_mvp_operator_flow.py tools/checks/check_tooling_smoke.py`
- `python tools/checks/check_mvp_operator_flow.py`
- `cmd /c safeclaw.cmd service-status --limit 1 --json`
- `git diff --check`

## 下一步
- 若继续沿 M1b 高复利主线推进，优先检查 `service-status` 的 `coordination` / `heartbeat` / `offline_gate` 三块是否还有其他“历史事实和实时状态混淆”的误报点。
