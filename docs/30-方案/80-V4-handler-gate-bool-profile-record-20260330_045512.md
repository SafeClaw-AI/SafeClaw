# V4 handler gate bool profile record

- 时间：2026-03-30 04:55:12 +0800
- 轮次：M1b Slice 208
- 本轮动作：把 `requires_bound_error` 与 `is_direct_silent_fallback` 也并入 `HandlerExceptionGateProfile`，让最后两段门禁布尔判定从消费点现算推进到画像真源内建。
- 代码收口：`tools/checks/check_reference_redlines.py` 的 `_handler_requires_bound_error()` 与 `_is_direct_silent_fallback_handler()` 现已退化成纯透传 helper，不再各自保留条件分叉。
- 合同补齐：`tests/contracts/test_reference_redlines_check.py` 继续扩充 `test_handler_exception_gate_profile_is_stable`，锁住 bare handler、普通 tuple、broad tuple、单高风险异常四种画像对应的两项布尔字段。
- 结果：handler profile 现已同时承载 bare / multi / broad / high-risk / message / bool 六层语义，后续继续补门禁时只需围绕一份画像扩展。
- 验证：python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py、python -m unittest tests.contracts.test_reference_redlines_check -v、python tools/checks/check_reference_redlines.py、git diff --check
- 为什么这样做：在门禁文案刚并入画像后，继续把最终两段布尔判定也并进同一 profile，能把 handler 门禁链彻底压成单一真源，长期最省维护。
- 下一步：继续扫 broad / multi-exception 家族最后的小重复点；若这一面基本收平，再谨慎回看更窄的 `ValueError` 子集。
