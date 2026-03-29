# V4 handler high risk profile record

- 时间：2026-03-30 04:45:58 +0800
- 轮次：M1b Slice 206
- 本轮动作：把 `ordered_high_risk_exception_names` 与 `uses_high_risk_exception_family` 也并入 `HandlerExceptionGateProfile`，让高风险异常交叉与有序名单从“消费点现算”推进到“画像真源内建”。
- 代码收口：`tools/checks/check_reference_redlines.py` 的 `_handler_requires_bound_error()`、`_handler_context_requirement()`、`_is_direct_silent_fallback_handler()`、`_silent_fallback_requirement()` 现在都不再自己交叉 `HIGH_RISK_EXCEPTION_TYPES` 或重复排序。
- 合同补齐：`tests/contracts/test_reference_redlines_check.py` 继续扩充 `test_handler_exception_gate_profile_is_stable`，锁住 bare handler、普通 tuple、broad tuple 三种画像的高风险字段口径。
- 结果：handler profile 现已同时承载 bare / multi / broad / high-risk 四层语义，后续继续补 broad / multi-exception 家族门禁时只需围绕一份画像扩展。
- 验证：python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py、python -m unittest tests.contracts.test_reference_redlines_check -v、python tools/checks/check_reference_redlines.py、git diff --check
- 为什么这样做：在 handler 画像骨架已落地后，继续把高风险派生字段并进同一 profile，比继续在各消费点散落 set 交叉和排序判断更稳、更省维护。
- 下一步：继续扫 broad / multi-exception 家族最后的小重复点；若这一面基本收平，再谨慎回看更窄的 `ValueError` 子集。
