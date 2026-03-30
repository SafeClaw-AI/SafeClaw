# V4 named expression silent fallback gate record

- 时间：2026-03-30 09:52:50 +0800
- 轮次：M1b Slice 239
- 本轮动作：调整 `tools/checks/check_reference_redlines.py` 的 direct silent fallback 真源，把 `NamedExpr`（海象表达式）纳入静态求值与 known-name 运行值解析；既覆盖 direct return，也覆盖 constructor 包装场景。
- 代码收口：现在 `except ValueError: return (fallback := [])`、`except TypeError: return (fallback := False)` 与 `except OSError: return str((alias := empty))` 会和其他语法糖包装一样，被视为 direct 静默降级并触发 fail-closed 门禁。
- 合同补齐：`tests/contracts/test_reference_redlines_check.py` 同步补齐 3 条 named expression 必败合同，并按 TDD 先跑到红、再实现转绿。
- 基线结果：定向扫描 except handler 内任意 return 表达式里的 `NamedExpr` 当前为 `NO_RETURN_NAMED_EXPR_ANYWHERE`。
- 验证：`python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py`、`python -m unittest tests.contracts.test_reference_redlines_check -v`、`python tools/checks/check_reference_redlines.py`、`python tools/checks/check_ledger_alignment.py`、`git diff --check`
- 为什么这样做：如果 direct silent fallback 不拦海象表达式，开发者仍可只包一层 `:=` 就继续吞掉异常上下文；这一刀把 static / known-name 两路都收成单点真源，后续不必在更深包装层重复补洞。
- 下一步：继续沿 `docs/reference/01` 主线盘 silent fallback 家族是否还剩零命中 helper 绕行、构造包装或更边角的表达式语法糖；若这一族基本收平，再切回另一条同级高复利 fail-closed 红线。
