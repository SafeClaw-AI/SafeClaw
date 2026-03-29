# V4 windows stale lock recovery record

- 时间：2026-03-30 01:55:09 +0800
- 轮次：M1b Slice 188
- 目标：把 Windows 下 `.wrapper-check.lock` 的 stale-lock 自恢复收成稳态；避免 `check_tooling_smoke.py` 或 `check_mvp_operator_flow.py` 超时退出后，下一轮验证被假锁拦住，且 `os.kill(pid, 0)` 再抛 `WinError 87` / `SystemError`。

## 本轮动作
- 调整 `tools/checks/mvp_state_guard.py`：把进程探活拆成 `_process_is_running_with_signal()` 与 `_process_is_running_with_winapi()`；在 Windows 上改用 `kernel32.OpenProcess + GetExitCodeProcess` 做真实探活，不再继续赌 `os.kill(pid, 0)`。
- 保留非 Windows 路径的 signal 探活，并在 signal 路径上把 `SystemError` 也视为“进程不存在/不可用”，避免 stale pid 再把恢复流程炸死。
- 在 `tests/contracts/test_mvp_state_guard.py` 新增 Windows 回归：锁住“invalid parameter -> false”与“STILL_ACTIVE -> true”两条合同，同时保留原有 `EPERM/ESRCH` 路径。

## 结果
- stale `.wrapper-check.lock` 现在在 Windows 上可稳定自恢复；验证链不会再因为死 pid + `WinError 87` 卡死在 guard 层。
- `check_mvp_operator_flow.py`、`check_tooling_smoke.py` 与 `test_mvp_state_guard.py` 已一起回归通过。

## 验证
- `python -m py_compile tools/checks/mvp_state_guard.py tests/contracts/test_mvp_state_guard.py`
- `python -m unittest tests.contracts.test_mvp_state_guard -v`
- `python tools/checks/check_mvp_operator_flow.py`
- `python tools/checks/check_tooling_smoke.py`
- `git diff --check`

## 下一步
- 继续排查验证链上是否还有“局部超时后留下全局假状态”的残留点；优先考虑给 `acquire_mvp_state_lock()` 再补一条 stale-lock 端到端合同，而不只停留在 helper 级回归。