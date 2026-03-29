# V4 handler profile iterator record

- 时间：2026-03-30 05:03:44 +0800
- 轮次：M1b Slice 209
- 本轮动作：新增 `_iter_exception_handler_gate_profiles()`，把“遍历 `try/except` handler + 构建 `HandlerExceptionGateProfile`”收成单一入口。
- 代码收口：`tools/checks/check_reference_redlines.py` 的三条扫描主循环——缺少上下文、绑定未使用、静默降级——现在都统一复用同一份 handler/profile 迭代流，不再各自 `ast.walk(tree)` 并重复建画像。
- 合同补齐：`tests/contracts/test_reference_redlines_check.py` 新增 `test_iter_exception_handler_gate_profiles_is_stable`，锁住迭代顺序、handler 行号与画像字段口径。
- 结果：reference redlines 现在已把“画像内容”与“画像遍历入口”一并真源化；后续若继续加门禁，只需围绕同一迭代入口扩展，长期更稳。
- 验证：python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py、python -m unittest tests.contracts.test_reference_redlines_check -v、python tools/checks/check_reference_redlines.py、python tools/checks/check_ledger_alignment.py、git diff --check
- 为什么这样做：在 handler profile 已承载六层语义后，继续把“如何遍历并分发这份画像”也收成单一入口，能避免三条主循环继续重复建画像和分散迭代逻辑。
- 下一步：继续扫 broad / multi-exception 家族最后的小重复点；若这一面基本收平，再谨慎回看更窄的 `ValueError` 子集。
