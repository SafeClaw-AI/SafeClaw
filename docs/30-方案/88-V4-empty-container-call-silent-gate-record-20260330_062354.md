# V4 empty container call silent gate record

- 时间：2026-03-30 06:23:54 +0800
- 轮次：M1b Slice 216
- 本轮动作：把 `tools/checks/check_reference_redlines.py` 的“空容器” direct silent fallback 识别继续补齐，新增 `_is_empty_container_constructor_call()`，让 `set()` / `frozenset()` 也纳入 `_is_direct_silent_fallback_return_value()`。
- 代码收口：现在 `except ...: return set()` 与 `except ...: return frozenset()` 会和 `[]` / `{}` / `()` 一样，被视为“空容器” direct 静默降级并触发 fail-closed 门禁。
- 合同补齐：`tests/contracts/test_reference_redlines_check.py` 新增 `ValueError -> return set()` 与 `TypeError -> return frozenset()` 两条必败合同，先红后绿完成闭环。
- 基线结果：用 AST 定向扫描全仓 `except ...: return set()` / `frozenset()` 当前为 `NO_HITS`，本轮属于零旧债扩面；无需修平既有业务代码。
- 验证：`python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py`、`python -m unittest tests.contracts.test_reference_redlines_check -v`、`python tools/checks/check_reference_redlines.py`、`python tools/checks/check_ledger_alignment.py`、`git diff --check`
- 为什么这样做：上一刀的文案已写“空容器”，但 Python 空集合不能靠字面量表达；若不把 `set()` / `frozenset()` 一并纳入，语义上会留下“名义闭环、实现漏口”的假收口。
- 下一步：继续沿 `docs/reference/01` 主线找 silent fallback 相邻表达里的零命中漏口，优先补这种“语义已宣告、实现还差最后半步”的高复利切片。