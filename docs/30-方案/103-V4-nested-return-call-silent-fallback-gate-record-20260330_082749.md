# V4 nested return call silent fallback gate record

- 时间：2026-03-30 08:27:49 +0800
- 轮次：M1b Slice 231
- 本轮动作：调整 `tools/checks/check_reference_redlines.py` 的运行值解析 helper，把 `return list(list(fallback))`、`return bool(bool(alias))` 与 `return str(str(alias))` 这类“已知 silent fallback 名字再包两层单参 constructor”的绕行也纳入真源，同时保持 assignment chain 传播语义不回退。
- 代码收口：现在 `except ValueError: fallback = []; return list(list(fallback))`、`except TypeError: fallback = bool(False); return bool(bool(fallback))` 与 `except OSError: empty = '' + ''; alias = empty; return str(str(alias))` 会和单层 constructor 包装一样，被视为 direct 静默降级并触发 fail-closed 门禁。
- 合同补齐：`tests/contracts/test_reference_redlines_check.py` 同步补齐 3 条 nested return call 必败合同，并按 TDD 先跑到红、再实现转绿。
- 基线结果：定向扫描 nested return call silent fallback 当前为 `NO_NESTED_RETURN_CALL_HITS`。
- 验证：`python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py`、`python -m unittest tests.contracts.test_reference_redlines_check -v`、`python tools/checks/check_reference_redlines.py`、`python tools/checks/check_ledger_alignment.py`、`git diff --check`
- 为什么这样做：如果 direct silent fallback 只拦单层 constructor 包装返回，不拦嵌套 call，开发者仍可只再包一层 `list(...)` / `bool(...)` / `str(...)` 就继续吞掉异常上下文；趁零旧债时补齐这个语法糖漏口，长期更稳。
- 下一步：继续沿 `docs/reference/01` 主线盘 silent fallback 家族是否还剩更深 alias 包装或 helper 绕行；若这一族基本收平，再切回另一条同级高复利 fail-closed 红线。
