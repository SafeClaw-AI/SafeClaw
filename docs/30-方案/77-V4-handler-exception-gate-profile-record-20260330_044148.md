# V4 handler exception gate profile record

- 时间：2026-03-30 04:41:48 +0800
- 轮次：M1b Slice 205
- 本轮动作：新增 `HandlerExceptionGateProfile` 与 `_build_handler_exception_gate_profile()`，把 `caught_types`、`is_bare_handler`、`uses_multi_exception_family`、`uses_broad_exception_family` 收成单一画像真源。
- 代码收口：`tools/checks/check_reference_redlines.py` 的 `_handler_requires_bound_error()`、`_handler_uses_broad_exception_family()`、`_handler_context_requirement()`、`_is_direct_silent_fallback_handler()`、`_silent_fallback_requirement()` 现在都统一围绕同一份 handler profile 工作。
- 合同补齐：`tests/contracts/test_reference_redlines_check.py` 新增 `test_handler_exception_gate_profile_is_stable`，锁住 bare handler、普通 tuple、broad tuple 三种画像口径。
- 结果：reference redlines 的 handler 识别链从“多个 helper + 多处 if 分叉”进一步压成“单画像真源 + 多消费点复用”，后续继续补 broad / multi-exception 家族门禁时更稳。
- 验证：python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py、python -m unittest tests.contracts.test_reference_redlines_check -v、python tools/checks/check_reference_redlines.py、git diff --check
- 为什么这样做：在 caught_types helper 与高风险异常集合都已真源化后，继续把 handler 画像整体收成一份 profile，能明显缩小后续维护面，而不需要冒进扩大异常覆盖范围。
- 下一步：继续扫 broad / multi-exception 家族最后的小重复点；若这一面基本收平，再谨慎回看更窄的 `ValueError` 子集。
