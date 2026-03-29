# V4 timeout expired context gate record

- 时间：2026-03-30 03:04:59 +0800
- 轮次：M1b Slice 193
- 目标：把 `subprocess.TimeoutExpired` 也纳入 reference 单异常上下文红线；优先选命中仅 1 处、当前基线已天然合规的高复利切片，继续小步扩面而不触碰高爆炸面。

## 本轮动作
- 调整 `tools/checks/check_reference_redlines.py`：把 `subprocess.TimeoutExpired` 纳入 `CONTEXT_REQUIRED_EXCEPTION_TYPES`，并补上专门报错“`subprocess.TimeoutExpired` 必须绑定 `as error` 以保留上下文”。
- 在 `tests/contracts/test_reference_redlines_check.py` 新增两条合同：锁住 `except subprocess.TimeoutExpired:` 未绑定时必须失败，`except subprocess.TimeoutExpired as error:` 且真实使用上下文时必须通过。
- 维持运行时代码零改动；当前真实命中 `tools/mvp/safeclaw_mvp.py` 已用 `as error` 并把上下文写入返回值，本轮只把既有约定沉成 fail-closed 门禁。

## 结果
- reference 红线继续沿“单异常上下文”主线稳步扩面，`subprocess.TimeoutExpired` 现在也和 `SystemError` / `RuntimeError` / `SyntaxError` 一样进入可回归合同。
- 未来若有人在 subprocess 超时场景里写出无上下文兜底，会被 `check_reference_redlines.py` 直接拦下，不再依赖人工 code review 发现。

## 验证
- `python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py`
- `python -m unittest tests.contracts.test_reference_redlines_check -v`
- `python tools/checks/check_reference_redlines.py`
- `python tools/checks/check_ledger_alignment.py`
- `git diff --check`

## 下一步
- 继续沿 `docs/reference/01` 挑“命中更少的静默降级异常形态”推进；在确认真实收益前，不贸然碰 `ValueError` 或体量红线这类高爆炸面。