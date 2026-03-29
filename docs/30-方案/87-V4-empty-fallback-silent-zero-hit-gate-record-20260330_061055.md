# V4 empty fallback silent zero-hit gate record

- 时间：2026-03-30 06:10:55 +0800
- 轮次：M1b Slice 215
- 本轮动作：把 `tools/checks/check_reference_redlines.py` 的 direct 静默降级门禁从 `None/False` 扩到空字符串 / 空容器，并把 helper 真源语义统一改名为 `_is_direct_silent_fallback_return_value()` / `_is_direct_silent_fallback_return_handler()`。
- 代码收口：`SILENT_FALLBACK_SUFFIX` 现在统一描述为“不能直接静默降级为 None/False/空字符串/空容器”，`except ...: return ''`、`return []`、`return {}`、`return ()` 都会被 future fail-closed 门禁阻断。
- 合同补齐：`tests/contracts/test_reference_redlines_check.py` 新增 `ValueError -> return ''` 与 `TypeError -> return []` 两条必败合同，并同步所有静默降级断言到新后缀真源。
- 基线结果：用 AST 定向扫描全仓 `except ...: return '' / [] / {} / ()` 当前为 `NO_HITS`，本轮属于零旧债扩面；无需修平既有业务代码。
- 验证：`python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py`、`python -m unittest tests.contracts.test_reference_redlines_check -v`、`python tools/checks/check_reference_redlines.py`、`python tools/checks/check_ledger_alignment.py`、`git diff --check`
- 为什么这样做：空字符串 / 空容器看似“有返回值”，但在异常路径里本质仍是吞上下文的静默降级；在零命中时先补门禁，比等未来真实代码长出来后再回头排雷更稳、更省维护成本。
- 下一步：继续沿 `docs/reference/01` 的异常红线主线，优先找还能零债并入现有真源的 silent fallback 相邻形态；只要能 future fail-closed，就继续先补规则，不拖业务债。