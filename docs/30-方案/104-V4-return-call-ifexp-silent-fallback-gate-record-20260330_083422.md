# V4 return call ifexp silent fallback gate record

- 时间：2026-03-30 08:34:22 +0800
- 轮次：M1b Slice 232
- 本轮动作：调整 `tools/checks/check_reference_redlines.py` 的运行值解析 helper，把 `return list(fallback if True else [1])`、`return bool(True if False else fallback)` 与 `return str(alias if True else "fallback")` 这类 `return constructor(ifexp)` 包装绕行也纳入真源，支持静态分支选择后再解析已知 silent fallback 名字。
- 代码收口：现在 `except ValueError: fallback = []; return list(fallback if True else [1])`、`except TypeError: fallback = bool(False); return bool(True if False else fallback)` 与 `except OSError: empty = "" + ""; alias = empty; return str(alias if True else "fallback")` 会和直接返回空值、constructor 包装返回一样，被视为 direct 静默降级并触发 fail-closed 门禁。
- 合同补齐：`tests/contracts/test_reference_redlines_check.py` 同步补齐 3 条 return-call-ifexp 必败合同，并按 TDD 先跑到红、再实现转绿。
- 基线结果：定向扫描 return call + IfExp silent fallback 当前为 `NO_RETURN_CALL_IFEXP_HITS`。
- 验证：`python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py`、`python -m unittest tests.contracts.test_reference_redlines_check -v`、`python tools/checks/check_reference_redlines.py`、`python tools/checks/check_ledger_alignment.py`、`git diff --check`
- 为什么这样做：如果 direct silent fallback 只拦 constructor 包装与 nested call，不拦 `return constructor(ifexp)`，开发者仍可只在参数层包一个静态分支就继续吞掉异常上下文；趁零旧债时补齐这个小绕行口，长期更稳。
- 下一步：继续沿 `docs/reference/01` 主线盘 silent fallback 家族是否还剩更深 alias 包装或 helper 绕行；若这一族基本收平，再切回另一条同级高复利 fail-closed 红线。
