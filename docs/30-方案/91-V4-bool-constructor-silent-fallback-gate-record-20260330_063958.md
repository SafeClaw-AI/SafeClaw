# V4 bool constructor silent fallback gate record

- 时间：2026-03-30 06:39:58 +0800
- 轮次：M1b Slice 219
- 本轮动作：把 `tools/checks/check_reference_redlines.py` 里无参构造调用 helper 从 `_is_empty_fallback_constructor_call()` 更名为 `_is_silent_fallback_constructor_call()`，并把 `bool()` 一并纳入 direct silent fallback 构造调用真源。
- 代码收口：现在 `except ...: return bool()` 会和 `return False` 一样，被视为 direct 静默降级并触发 fail-closed 门禁；helper 命名也从“empty”升级为与真实职责一致的“silent fallback”。
- 合同补齐：`tests/contracts/test_reference_redlines_check.py` 把 helper 稳定性合同升级为 `silent_fallback_constructor` 口径，并新增 `ValueError -> return bool()` 的 direct fallback 必败合同。
- 基线结果：AST 定向扫描全仓 `except ...: return bool()` 当前为 `NO_HITS`，本轮属于零旧债扩面；无需修平既有业务代码。
- 验证：`python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py`、`python -m unittest tests.contracts.test_reference_redlines_check -v`、`python tools/checks/check_reference_redlines.py`、`python tools/checks/check_ledger_alignment.py`、`git diff --check`
- 为什么这样做：如果 `False` 已经被拦，但 `bool()` 还能漏过去，就会留下同义表达的调用形态裂缝；趁零命中时直接补齐，成本最低，收益最长。
- 下一步：继续沿 `docs/reference/01` 主线，盘点 silent fallback 家族里最后的零命中相邻表达；若这一族基本收平，再切到另一条同级 fail-closed 红线。