# V4 keyword constructor silent fallback gate record

- 时间：2026-03-30 09:06:16 +0800
- 轮次：M1b Slice 236
- 本轮动作：调整 `tools/checks/check_reference_redlines.py` 的 direct silent fallback 真源，同时支持 `str(object=...)`、`bytes(source=...)` 与 `bytearray(source=...)` 这类单关键字构造调用；既覆盖 direct 静态空值，也覆盖 assignment chain 传播后的已知 silent fallback 名字。
- 代码收口：现在 `except ValueError: return str(object="")`、`except TypeError: return bytes(source=b"")` 与 `except OSError: empty = "" + ""; alias = empty; return str(object=alias)` 会和普通 constructor 包装一样，被视为 direct 静默降级并触发 fail-closed 门禁。
- 合同补齐：`tests/contracts/test_reference_redlines_check.py` 同步补齐 3 条 keyword constructor 必败合同，并按 TDD 先跑到红、再实现转绿。
- 基线结果：定向扫描关键字构造 return silent fallback 当前为 `NO_KEYWORD_CTOR_RETURN_HITS`。
- 验证：`python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py`、`python -m unittest tests.contracts.test_reference_redlines_check -v`、`python tools/checks/check_reference_redlines.py`、`python tools/checks/check_ledger_alignment.py`、`git diff --check`
- 为什么这样做：如果 direct silent fallback 不拦 `str(object=...)` / `bytes(source=...)` 这类关键字构造包装，开发者仍可借一层合法关键字参数继续吞掉异常上下文；趁零旧债时补齐这一层，长期更稳。
- 下一步：继续沿 `docs/reference/01` 主线盘 silent fallback 家族是否还剩零命中更深 alias 包装或 helper 绕行；若这一族基本收平，再切回另一条同级高复利 fail-closed 红线。
