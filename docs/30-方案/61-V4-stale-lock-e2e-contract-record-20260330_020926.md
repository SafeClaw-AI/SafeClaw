# V4 stale lock e2e contract record

- 时间：2026-03-30 02:09:26 +0800
- 轮次：M1b Slice 189
- 目标：把 `acquire_mvp_state_lock()` 的 stale-lock 自恢复补成端到端合同，而不只停留在 helper 级进程探活测试；确保陈旧 `.wrapper-check.lock` 会被真实回收并重新获取。

## 本轮动作
- 在 `tests/contracts/test_mvp_state_guard.py` 新增 `test_acquire_lock_recovers_stale_holder_file()`：使用真实临时锁文件构造 `check_tooling_smoke pid=999999` 的 stale-lock，再通过 `acquire_mvp_state_lock()` 重新获取，锁住“旧锁会被清掉，新锁会写入当前 check/pid，退出后文件会释放”。
- 复用现有 `mvp_state_guard` 运行时实现，不再改业务代码；本轮只把 `Slice 188` 的恢复语义补成端到端回归，提升验证链稳定性。
- 回归确认 `test_mvp_state_guard.py`、`check_mvp_operator_flow.py`、`check_tooling_smoke.py` 继续全绿。

## 结果
- stale-lock 恢复现在同时有 helper 级与 contextmanager 级两层门禁；Windows 假锁恢复不再只靠手工复现确认。
- 验证链的“陈旧锁 -> 自动回收 -> 重新获取 -> 退出释放”闭环已机器化锁住。

## 验证
- `python -m py_compile tests/contracts/test_mvp_state_guard.py`
- `python -m unittest tests.contracts.test_mvp_state_guard -v`
- `python tools/checks/check_mvp_operator_flow.py`
- `python tools/checks/check_tooling_smoke.py`
- `git diff --check`

## 下一步
- 继续排查验证链上是否还有其他“旧全局状态残留”只靠运行时经验兜底、但尚未端到端合同化的点；优先考虑 `LOCK_ENV` 嵌套复用语义是否也值得补独立合同。