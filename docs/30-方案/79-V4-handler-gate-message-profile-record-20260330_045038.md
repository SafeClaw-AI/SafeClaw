# V4 handler gate message profile record

- 时间：2026-03-30 04:50:38 +0800
- 轮次：M1b Slice 207
- 本轮动作：把 `context_requirement_message` 与 `silent_fallback_requirement_message` 也并入 `HandlerExceptionGateProfile`，让“画像 → 门禁文案”从消费点现算推进到画像真源内建。
- 代码收口：`tools/checks/check_reference_redlines.py` 的 `_handler_context_requirement()` 与 `_silent_fallback_requirement()` 现已退化成纯透传 helper，不再各自保留一套条件分叉。
- 合同补齐：`tests/contracts/test_reference_redlines_check.py` 扩充 `test_handler_exception_gate_profile_is_stable`，锁住 bare handler、普通 tuple、broad tuple、单高风险异常四种画像对应的门禁文案。
- 结果：handler profile 现已同时承载 bare / multi / broad / high-risk / message 五层语义，后续继续补门禁时只需围绕一份画像扩展，长期更稳。
- 验证：python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py、python -m unittest tests.contracts.test_reference_redlines_check -v、python tools/checks/check_reference_redlines.py、git diff --check
- 为什么这样做：在高风险字段已并入画像后，继续把门禁文案也并进同一 profile，能进一步压缩重复分支和条件漂移，而不需贸然扩大异常覆盖范围。
- 下一步：继续扫 broad / multi-exception 家族最后的小重复点；若这一面基本收平，再谨慎回看更窄的 `ValueError` 子集。
