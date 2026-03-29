# V4 runtime silent fallback gate record

- 时间：2026-03-30 03:11:34 +0800
- 轮次：M1b Slice 194
- 目标：继续沿 reference fail-closed 主线扩“静默降级异常”门禁，把 `SystemError` / `subprocess.TimeoutExpired` 也纳入“不能直接 `return None/False`”的护栏；优先选择低命中、当前基线可零运行时改动通过的切片。

## 本轮动作
- 调整 `tools/checks/check_reference_redlines.py`：把 `SystemError` 与 `subprocess.TimeoutExpired` 接入 `SILENT_FALLBACK_EXCEPTION_TYPES`，并把静默降级报错改成按真实命中异常动态生成，避免继续写死旧的 `OSError / json.JSONDecodeError` 提示。
- 在 `tests/contracts/test_reference_redlines_check.py` 更新既有 `OSError` 合同口径，并新增两条合同：锁住 `SystemError` 直接 `return False` 必须失败、`subprocess.TimeoutExpired` 直接 `return False` 必须失败。
- 保持运行时代码零改动；当前真实 `subprocess.TimeoutExpired` 命中已使用 `str(error)` 回传上下文，`SystemError` 当前基线也已不再属于 direct fallback 形态。

## 结果
- reference 红线现在对“无上下文直接 `return None/False`”的运行时异常家族覆盖更完整：`OSError`、`SystemError`、`json.JSONDecodeError`、`subprocess.TimeoutExpired` 都会被 fail-closed 拦截。
- 后续若有人把探活失败或 subprocess 超时直接静默降级成布尔值，门禁会给出对应异常名的人话提示，不再误导成旧的固定文案。

## 验证
- `python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py`
- `python -m unittest tests.contracts.test_reference_redlines_check -v`
- `python tools/checks/check_reference_redlines.py`
- `python tools/checks/check_ledger_alignment.py`
- `git diff --check`

## 下一步
- 继续沿 `docs/reference/01` 挑低命中静默降级异常推进；在命中面与收益没有把握前，不贸然扩 `ValueError` 或体量红线。