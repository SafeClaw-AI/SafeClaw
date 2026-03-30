# V4 set algebra method silent fallback gate record

- 时间：2026-03-30 11:40:30 +0800
- 轮次：M1b Slice 249
- 本轮动作：调整 `tools/checks/check_reference_redlines.py` 的 direct silent fallback 真源，把 `difference/intersection/union` 这组 zero-arg set algebra method 纳入静态求值与 known-name 运行值解析；既覆盖 direct return，也覆盖 constructor 包装场景。
- 代码收口：现在 `except ValueError: return set().difference()`、`except TypeError: payload = set(); return payload.union()` 与 `except OSError: payload = frozenset(); return set(payload.intersection())` 会和其他语法糖包装一样，被视为 direct 静默降级并触发 fail-closed 门禁。
- 合同补齐：`tests/contracts/test_reference_redlines_check.py` 同步补齐 3 条 set algebra method 必败合同，并按 TDD 先跑到红、再实现转绿。
- 基线结果：定向扫描 except handler 内的 set algebra method return 当前为 `NO_RETURN_SET_ALGEBRA_METHOD_HITS`。
- 验证：`python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py`、`python -m unittest tests.contracts.test_reference_redlines_check -v`、`python tools/checks/check_reference_redlines.py`、`python tools/checks/check_ledger_alignment.py`、`git diff --check`
- 为什么这样做：如果 direct silent fallback 不拦 `.difference()/.intersection()/.union()` 这类 zero-arg set algebra 方法，开发者仍可只包一层方法调用继续吞掉异常上下文；这一刀在同一抽象层继续收平集合语义绕行。
- 下一步：继续沿 `docs/reference/01` 主线盘 silent fallback 家族是否还剩零命中 helper 绕行、constructor 包装或更边角的 zero-arg method / expression 语法糖；若这一族基本收平，再切回另一条同级高复利 fail-closed 红线。
