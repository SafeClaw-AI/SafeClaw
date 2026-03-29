# V4 high risk exception truth source alignment record

- 时间：2026-03-30 03:25:45 +0800
- 轮次：M1b Slice 196
- 目标：继续削掉 `check_reference_redlines.py` 里高风险异常规则的双写点，让“上下文提示”也复用同一份真源；再补一条稳定性合同，防止后续扩面时名单重新漂移。

## 本轮动作
- 调整 `tools/checks/check_reference_redlines.py`：新增 `_ordered_high_risk_exception_names()`，并让 `_handler_context_requirement()` 与 `_silent_fallback_requirement()` 统一复用 `SILENT_FALLBACK_EXCEPTION_TYPE_ORDER`；不再为每个异常类型手写一串分支提示。
- 在 `tests/contracts/test_reference_redlines_check.py` 新增 `test_high_risk_exception_truth_sources_are_aligned()`：锁住 `SILENT_FALLBACK_EXCEPTION_TYPE_ORDER`、`SILENT_FALLBACK_EXCEPTION_TYPES`、`CONTEXT_REQUIRED_EXCEPTION_TYPES` 三者保持一致。
- 保持现有异常行为不变；既有单异常与静默降级合同继续全部通过，本轮重点是消除未来扩面时的维护分叉。

## 结果
- 高风险异常真源现在既控制“哪些异常必须绑定上下文”，也控制“哪些异常不能 direct fallback”，并驱动上下文提示文本；后续继续扩异常只需改单处。
- 新增的稳定性合同能直接拦截名单顺序或集合漂移，降低未来继续推进时的回归成本。

## 验证
- `python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py`
- `python -m unittest tests.contracts.test_reference_redlines_check -v`
- `python tools/checks/check_reference_redlines.py`
- `python tools/checks/check_ledger_alignment.py`
- `git diff --check`

## 下一步
- 继续沿 `docs/reference/01` 主线推进；优先找还能并入同类真源、且不需要碰高爆炸面运行时代码的规则切片。