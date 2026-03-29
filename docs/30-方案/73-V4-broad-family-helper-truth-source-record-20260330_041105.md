# V4 broad family helper truth source record

- 时间：2026-03-30 04:11:05 +0800
- 轮次：M1b Slice 201
- 本轮动作：把 broad family 的 handler 识别逻辑收成 helper 真源；现在 handler 的 caught_types 解析与 broad family 判定不再在多处重复手写。
- 合同补齐：tests/contracts/test_reference_redlines_check.py 新增 1 条 broad family helper 稳定性合同，锁住 direct Exception/BaseException 与 tuple broad 变体都会被识别为 broad family，而普通多异常不会误判。
- 代码收口：tools/checks/check_reference_redlines.py 新增 `_handler_caught_types()` 与 `_handler_uses_broad_exception_family()`，并让 `_handler_requires_bound_error()`、`_handler_context_requirement()`、`_is_direct_silent_fallback_handler()`、`_silent_fallback_requirement()` 统一复用。
- 结果：broad family 的“识别真源”从散落条件判断收成单点 helper，后续继续维护 context/fallback 两条门禁时更稳，也更不容易漏改。
- 验证：python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py、python -m unittest tests.contracts.test_reference_redlines_check -v、python tools/checks/check_reference_redlines.py、python tools/checks/check_ledger_alignment.py、git diff --check
- 为什么这样做：在行为与文案都已基本收平后，下一步最有复利的是把识别逻辑也收成单点真源，减少同一条件在多处重复展开。
- 下一步：继续扫 broad / multi-exception 家族是否还有最后的小重复点；若这一面基本收平，再谨慎回看更窄的 ValueError 子集。
