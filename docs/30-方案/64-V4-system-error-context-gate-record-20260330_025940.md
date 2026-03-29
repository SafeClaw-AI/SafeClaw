# V4 system error context gate record

- 时间：2026-03-30 02:59:40 +0800
- 轮次：M1b Slice 192
- 目标：把 `SystemError` 也纳入 reference 异常上下文红线，并修平当前唯一真实命中点；避免这类底层探活异常继续无上下文静默吞掉。

## 本轮动作
- 调整 `tools/checks/check_reference_redlines.py`：把 `SystemError` 纳入 `CONTEXT_REQUIRED_EXCEPTION_TYPES`，并补上专门报错“`SystemError` 必须绑定 `as error` 以保留上下文”。
- 修平当前真实命中：`tools/checks/mvp_state_guard.py` 的 `_process_is_running_with_signal()` 改为 `except SystemError as error`，并把异常上下文打印到 `stderr` 后再返回 `False`，不再无上下文吞掉底层信号探活失败。
- 补齐合同：`tests/contracts/test_reference_redlines_check.py` 新增 `SystemError` 裸抓失败 / 绑定并使用通过；`tests/contracts/test_mvp_state_guard.py` 新增 `SystemError` 会返回 `False` 且带上下文日志的回归。

## 结果
- reference 红线继续沿单异常上下文主线扩面，`SystemError` 现在已和 `OSError` / `RuntimeError` / `SyntaxError` 一样进入 fail-closed 门禁。
- Windows/底层探活链路遇到 `SystemError` 时，不再只剩一个无解释的 `False`，后续排障能直接看到 pid 与错误文本。

## 验证
- `python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py tools/checks/mvp_state_guard.py tests/contracts/test_mvp_state_guard.py`
- `python -m unittest tests.contracts.test_reference_redlines_check tests.contracts.test_mvp_state_guard -v`
- `python tools/checks/check_reference_redlines.py`
- `python tools/checks/check_ledger_alignment.py`
- `git diff --check`

## 下一步
- 继续沿 `docs/reference/01` 扩 reference fail-closed 门禁；优先评估下一组“静默降级异常形态”或命中更少、收益更高的复杂度红线。