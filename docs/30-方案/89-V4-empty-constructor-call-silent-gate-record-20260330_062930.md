# V4 empty constructor call silent gate record

- 时间：2026-03-30 06:29:30 +0800
- 轮次：M1b Slice 217
- 本轮动作：把 `tools/checks/check_reference_redlines.py` 里的 direct silent fallback 继续收口为“无参空值构造调用”真源，新增 `_is_empty_fallback_constructor_call()`，统一识别 `str()` / `list()` / `dict()` / `tuple()` / `set()` / `frozenset()`。
- 代码收口：现在 `except ...: return str()`、`return list()`、`return dict()`、`return tuple()` 会和 `''` / `[]` / `{}` / `()` 一样，被视为 direct 静默降级并触发 fail-closed 门禁。
- 合同补齐：`tests/contracts/test_reference_redlines_check.py` 新增 1 条 `_is_empty_fallback_constructor_call()` 稳定性合同，以及 `ValueError -> return str()/dict()`、`TypeError -> return list()/tuple()` 四条 direct fallback 必败合同。
- 基线结果：用 AST 定向扫描全仓 `except ...: return str()/list()/dict()/tuple()` 当前为 `NO_HITS`，本轮属于零旧债扩面；无需修平既有业务代码。
- 验证：`python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py`、`python -m unittest tests.contracts.test_reference_redlines_check -v`、`python tools/checks/check_reference_redlines.py`、`python tools/checks/check_ledger_alignment.py`、`git diff --check`
- 为什么这样做：上一轮虽然已经开始补调用形态，但若只补 `set()` / `frozenset()`，仍会留下 `str()` / `list()` / `dict()` / `tuple()` 这些更常见写法的实现漏口；先在零命中时收成一组真源，长期最省心。
- 下一步：继续沿 `docs/reference/01` 主线找 silent fallback 相邻表达里的最后零命中裂缝，优先补这种“语义已经宣布、实现只差半步”的高复利切片。