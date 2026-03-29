# V4 nested mvp lock reuse contract record

- 时间：2026-03-30 02:35:17 +0800
- 轮次：M1b Slice 190
- 目标：把 `acquire_mvp_state_lock()` 在已有 `LOCK_ENV` 时的嵌套复用语义补成端到端合同；确保内层检查会复用外层锁，不会重写 holder 文件，也不会污染环境变量恢复。

## 本轮动作
- 在 `tests/contracts/test_mvp_state_guard.py` 新增 `test_acquire_lock_reuses_existing_lock_env_without_rewriting_file()`：通过真实临时锁文件进入外层 `acquire_mvp_state_lock("outer_lock_check")`，再嵌套进入内层 `acquire_mvp_state_lock("inner_lock_check")`，锁住“内层不改写外层 holder、不新增额外锁文件、`LOCK_ENV` 始终保持外层值”。
- 维持 `tools/checks/mvp_state_guard.py` 运行时实现不变；本轮只把既有复用约定补成合同，优先做长期高复利的验证稳态化。
- 重新执行 `test_mvp_state_guard.py`、`check_mvp_operator_flow.py`、`check_tooling_smoke.py`，并在复验前清理一次由超时校验残留的活锁进程，确认验证链回到干净稳态。

## 结果
- `acquire_mvp_state_lock()` 现在同时具备 stale-lock 恢复合同与 nested-lock reuse 合同；验证链里的“检查器套检查器”场景不再只靠实现细节维持。
- `LOCK_ENV -> 锁文件 -> 退出恢复` 三段语义已形成完整闭环，更适合后续继续扩验证基础设施而不互相踩锁。

## 验证
- `python -m py_compile tests/contracts/test_mvp_state_guard.py`
- `python -m unittest tests.contracts.test_mvp_state_guard -v`
- `python tools/checks/check_mvp_operator_flow.py`
- `python tools/checks/check_tooling_smoke.py`
- `git diff --check`

## 下一步
- 回到 `docs/reference/01` 的高复利 fail-closed 门禁扩面；优先评估“单函数 / 单类体量红线”或下一批异常静默降级形态，避免在验证基础设施上重复原地打转。