# V4 static binary silent fallback gate record

- 时间：2026-03-30 07:46:58 +0800
- 轮次：M1b Slice 227
- 本轮动作：调整 `tools/checks/check_reference_redlines.py` 的静态表达式求值逻辑，把静态 `BinOp` 也纳入 direct silent fallback 真源，识别 `return "" + ""`、`return {} | {}`、`return [] + []` 这类二元表达式绕行。
- 代码收口：现在 `except ValueError: return "" + ""`、`except TypeError: return {} | {}` 与 `except OSError: fallback = [] + []; return fallback` 会和普通空值字面量、构造器 alias、条件 / 布尔表达式一样，被视为 direct 静默降级并触发 fail-closed 门禁。
- 合同补齐：`tests/contracts/test_reference_redlines_check.py` 同步补齐 1 条 helper 稳定性合同，以及 3 条 direct / assignment 静态二元表达式必败合同。
- 基线结果：定向扫描 direct 静态 `BinOp` silent fallback 当前为 `NO_HITS`。
- 验证：`python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py`、`python -m unittest tests.contracts.test_reference_redlines_check -v`、`python tools/checks/check_reference_redlines.py`、`python tools/checks/check_ledger_alignment.py`、`git diff --check`
- 为什么这样做：如果 direct silent fallback 只拦条件 / 布尔表达式与构造器 alias，不拦静态 `BinOp`，开发者仍可只包一层拼接、并集或重复语法糖就继续吞掉异常上下文；趁零命中时补齐这一层，长期更稳。
- 下一步：继续沿 `docs/reference/01` 主线盘 silent fallback 家族是否还剩零命中包装层或 helper 绕行；若这一族基本收平，再切回另一条同级高复利 fail-closed 红线。
