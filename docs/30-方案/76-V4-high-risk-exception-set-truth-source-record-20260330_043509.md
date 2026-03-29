# V4 high risk exception set truth source record

- 时间：2026-03-30 04:35:09 +0800
- 轮次：M1b Slice 204
- 本轮动作：把 `SILENT_FALLBACK_EXCEPTION_TYPES` 与 `CONTEXT_REQUIRED_EXCEPTION_TYPES` 统一挂到新的 `HIGH_RISK_EXCEPTION_TYPES` 单一集合真源上；异常顺序仍由 `SILENT_FALLBACK_EXCEPTION_TYPE_ORDER` 负责。
- 代码收口：`tools/checks/check_reference_redlines.py` 的 `_handler_requires_bound_error()` 与 `_is_direct_silent_fallback_handler()` 现在都直接围绕 `HIGH_RISK_EXCEPTION_TYPES` 判断，不再各自依赖两套同值集合名。
- 合同补齐：`tests/contracts/test_reference_redlines_check.py` 新增同体断言，锁住 `HIGH_RISK_EXCEPTION_TYPES`、`SILENT_FALLBACK_EXCEPTION_TYPES`、`CONTEXT_REQUIRED_EXCEPTION_TYPES` 三者共享同一集合对象。
- 结果：高风险异常名单现在不止“值相等”，而是“真源同体”；后续若再扩名单，只需改单处，长期更稳。
- 验证：python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py、python -m unittest tests.contracts.test_reference_redlines_check -v、python tools/checks/check_reference_redlines.py、git diff --check
- 为什么这样做：在 caught_types helper 使用面已收平后，继续压掉两套同值集合的语义重复，可以再缩一层长期维护面，而不必冒进扩大异常类型覆盖。
- 下一步：继续扫 broad / multi-exception 家族最后的小重复点；若这一面基本收平，再谨慎回看更窄的 `ValueError` 子集。
