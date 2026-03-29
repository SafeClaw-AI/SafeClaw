# V4 unified high risk silent fallback gate record

- 时间：2026-03-30 03:19:52 +0800
- 轮次：M1b Slice 195
- 目标：把静默降级门禁从零散异常名收成统一真源：凡已列入 reference 单异常上下文红线的高风险运行时异常，都不允许直接 `return None/False`；优先以零运行时改动完成长线规则统一。

## 本轮动作
- 调整 `tools/checks/check_reference_redlines.py`：新增 `SILENT_FALLBACK_EXCEPTION_TYPE_ORDER` 作为静默降级真源顺序，并让 `SILENT_FALLBACK_EXCEPTION_TYPES` 与 `CONTEXT_REQUIRED_EXCEPTION_TYPES` 统一对齐；`_silent_fallback_requirement()` 现在也复用同一真源生成报错。
- 在 `tests/contracts/test_reference_redlines_check.py` 扩静默降级合同：除既有 `OSError` / `SystemError` / `subprocess.TimeoutExpired` 外，再锁住 `KeyError` 直接 `return None` 必须失败、`RuntimeError` 直接 `return False` 必须失败。
- 保持运行时代码零改动；当前基线不命中新扩面异常，说明这轮规则统一没有额外拖慢主线。

## 结果
- reference 红线里“要保留上下文的异常”与“不能 direct fallback 的异常”现在已收成同一份真源，不再双处手写维护，后续继续扩面只需改单处。
- 高风险运行时异常家族的 direct fallback fail-closed 门禁更完整，也更不容易因文案或名单漂移而回退。

## 验证
- `python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py`
- `python -m unittest tests.contracts.test_reference_redlines_check -v`
- `python tools/checks/check_reference_redlines.py`
- `python tools/checks/check_ledger_alignment.py`
- `git diff --check`

## 下一步
- 继续沿 `docs/reference/01` 主线推进；若还要扩静默降级，优先继续找低命中异常或更值得统一成真源的规则，避免直接跳进 `ValueError` 高爆炸面。