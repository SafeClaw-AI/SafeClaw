# V4 unpack literal silent fallback gate record

- 时间：2026-03-30 09:42:38 +0800
- 轮次：M1b Slice 238
- 本轮动作：调整 `tools/checks/check_reference_redlines.py` 的 direct silent fallback 真源，把 container literal 求值 helper 扩到 unpack 语法糖；现在同时支持 `[*alias]` / `{**mapping}` 这类 starred sequence 与 dict unpack。
- 代码收口：现在 `except ValueError: return [*[]]`、`except TypeError: empty = "" + ""; return [*empty]`、`except OSError: return {**{}}` 与 `except RuntimeError: mapping = {}; return {**mapping}` 会和其他语法糖包装一样，被视为 direct 静默降级并触发 fail-closed 门禁。
- 合同补齐：`tests/contracts/test_reference_redlines_check.py` 同步补齐 4 条 unpack literal 必败合同，并按 TDD 先跑到红、再实现转绿。
- 基线结果：定向扫描 except handler 内的 unpack literal silent fallback 当前为 `NO_UNPACK_LITERAL_RETURN_HITS`。
- 验证：`python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py`、`python -m unittest tests.contracts.test_reference_redlines_check -v`、`python tools/checks/check_reference_redlines.py`、`python tools/checks/check_ledger_alignment.py`、`git diff --check`
- 为什么这样做：如果 direct silent fallback 不拦 `[*alias]` / `{**mapping}` 这类 unpack 语法糖，开发者仍可只包一层展开表达式继续吞掉异常上下文；这次顺手把 static 与 known-name 两路 container literal 求值一并收成共享真源，后续维护更轻。
- 下一步：继续沿 `docs/reference/01` 主线盘 silent fallback 家族是否还剩零命中更深 alias 包装、helper 绕行或更边角的表达式语法糖；若这一族基本收平，再切回另一条同级高复利 fail-closed 红线。
