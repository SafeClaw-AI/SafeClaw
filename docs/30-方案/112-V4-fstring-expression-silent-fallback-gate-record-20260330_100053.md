# V4 fstring expression silent fallback gate record

- 时间：2026-03-30 10:00:53 +0800
- 轮次：M1b Slice 240
- 本轮动作：调整 `tools/checks/check_reference_redlines.py` 的 direct silent fallback 真源，把 `JoinedStr` / `f-string` 表达式纳入静态求值与 known-name 运行值解析；既覆盖 direct return，也覆盖 constructor 包装场景。
- 代码收口：现在 `except ValueError: return f"{''}"`、`except TypeError: empty = '' + ''; return f"{empty}"` 与 `except OSError: return str(f"{empty}")` 会和其他语法糖包装一样，被视为 direct 静默降级并触发 fail-closed 门禁。
- 合同补齐：`tests/contracts/test_reference_redlines_check.py` 同步补齐 3 条 f-string expression 必败合同，并按 TDD 先跑到红、再实现转绿。
- 基线结果：定向扫描 except handler 内的 direct / constructor-wrapped f-string return 当前为 `NO_RETURN_FSTRING_HITS`。
- 验证：`python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py`、`python -m unittest tests.contracts.test_reference_redlines_check -v`、`python tools/checks/check_reference_redlines.py`、`python tools/checks/check_ledger_alignment.py`、`git diff --check`
- 为什么这样做：如果 direct silent fallback 不拦 `f-string` 表达式，开发者仍可只包一层格式化字符串继续吞掉异常上下文；这一刀把 direct 与 known-name 两路都收成共享 helper，后续不必在 call 包装层重复补洞。
- 下一步：继续沿 `docs/reference/01` 主线盘 silent fallback 家族是否还剩零命中 helper 绕行、constructor 包装或更边角的表达式语法糖；若这一族基本收平，再切回另一条同级高复利 fail-closed 红线。
