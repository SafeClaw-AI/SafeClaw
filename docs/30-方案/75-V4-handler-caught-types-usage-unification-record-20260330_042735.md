# V4 handler caught types usage unification record

- 时间：2026-03-30 04:27:35 +0800
- 轮次：M1b Slice 203
- 本轮动作：把 `_handler_context_requirement()` 与 `_silent_fallback_requirement()` 里残留的 caught_types 直连解析统一切到 `_handler_caught_types()`；现在这两条门禁不再各自手写 `set(_collect_exception_type_names(...))`。
- 代码收口：`tools/checks/check_reference_redlines.py` 删除 `_is_broad_exception_handler_type()` 这层一次性分支，让 broad family / multi-exception / high-risk 三条判断都继续围绕 `_handler_caught_types()` 与 `_handler_uses_broad_exception_family()` 工作。
- 合同状态：`tests/contracts/test_reference_redlines_check.py` 的 `_handler_caught_types()` 稳定性合同已继续覆盖 `subprocess.TimeoutExpired`、`(OSError, ValueError)`、`(Exception, ValueError)` 三种解析口径，本轮无需再扩测试面。
- 结果：reference redlines 的 handler caught_types 真源已从“已经存在 helper”推进到“关键消费点全面复用”，后续继续补 broad / multi-exception 家族门禁时更稳、更不容易再漂移。
- 验证：python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py、python -m unittest tests.contracts.test_reference_redlines_check -v、python tools/checks/check_reference_redlines.py、python tools/checks/check_ledger_alignment.py、git diff --check
- 为什么这样做：在 broad family 行为、提示文案与 helper 真源都已落地后，继续压平最后两处内部重复解析，能先把长期维护面收小，而不必贸然扩大高爆炸面的异常覆盖。
- 下一步：继续扫 broad / multi-exception 家族最后的小重复点；若这一面基本收平，再谨慎回看更窄的 `ValueError` 子集。