# V4 handler caught types truth source record

- 时间：2026-03-30 04:16:58 +0800
- 轮次：M1b Slice 202
- 本轮动作：把 handler 的 caught_types 解析继续压实为单一真源；现在 `_handler_context_requirement()` 与 `_silent_fallback_requirement()` 也统一复用 `_handler_caught_types()`，不再各自手写 `set(_collect_exception_type_names(...))`。
- 合同补齐：tests/contracts/test_reference_redlines_check.py 新增 1 条 `_handler_caught_types()` 稳定性合同，锁住 attribute 异常、普通 tuple、多异常 broad tuple 三种解析口径。
- 代码收口：tools/checks/check_reference_redlines.py 让所有 broad/high-risk 相关判定都围绕 `_handler_caught_types()` 与 `_handler_uses_broad_exception_family()` 这两层真源展开。
- 结果：reference redlines 的异常识别逻辑进一步从“散落解析 + 多处 set(...)”收成单点 helper，后续继续补规则时更稳、更不容易再漏改。
- 验证：python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py、python -m unittest tests.contracts.test_reference_redlines_check -v、python tools/checks/check_reference_redlines.py、python tools/checks/check_ledger_alignment.py、git diff --check
- 为什么这样做：在 broad family 行为、文案、helper 真源已基本收平后，继续压缩 caught_types 重复解析，能进一步降低后续维护成本，而无需冒进扩大异常覆盖面。
- 下一步：继续扫 broad / multi-exception 家族最后的小重复点；若这一面基本收平，再谨慎回看更窄的 ValueError 子集。
