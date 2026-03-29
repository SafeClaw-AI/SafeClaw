# V4 reference silent fallback gate 记录

## 时间
- `2026-03-29 19:30:55 +0800`

## 本轮动作
- 继续扩大 `tools/checks/check_reference_redlines.py` 的异常红线覆盖，把“高风险 `OSError / json.JSONDecodeError` 直接 `return None/False`”落成第四阶段硬门禁。
- 新增 `collect_silent_fallback_exception_errors_for_python_text()`，只拦最小但高风险的静默降级形态，先不一口气误伤所有单异常分支。
- 补上 `tests/contracts/test_reference_redlines_check.py` 合同，锁住“高风险异常直接静默降级必须失败 / 真正消费异常上下文则通过”。
- 补上 `tests/contracts/test_mvp_state_guard.py`，顺手把 `tools/checks/mvp_state_guard.py` 的进程探活根因修平：`EPERM` 现在会被视为“进程仍活着”，不再误判为已退出。

## 为什么做这刀
- 第三阶段已经要求“绑定并真正使用异常上下文”，但单异常分支里仍可能存在“高风险 I/O/JSON 失败后直接静默降级”的漏口。
- 先只收最小且风险最高的 `None/False` 直降级形态，能继续逼近《总纲》要求，同时把误伤面压到当前唯一真实命中点。

## 结果
1. `tools/checks/check_reference_redlines.py`
   - 新增高风险静默降级 AST 校验
   - 现已形成四层异常红线：空异常处理 → 必须绑定上下文 → 绑定后必须真正使用 → 高风险异常不能直接静默降级
2. `tests/contracts/test_reference_redlines_check.py`
   - 新增静默降级失败 / 上下文化降级通过合同
3. `tools/checks/mvp_state_guard.py`
   - `_process_is_running()` 现在会把 `errno.EPERM` 视为“目标进程仍存在”
4. `tests/contracts/test_mvp_state_guard.py`
   - 新增 `EPERM` / `ESRCH` 两条根因回归测试

## 最小验证
- `python -m py_compile tools/checks/check_reference_redlines.py tools/checks/mvp_state_guard.py tests/contracts/test_reference_redlines_check.py tests/contracts/test_mvp_state_guard.py`
- `python -m unittest tests.contracts.test_reference_redlines_check tests.contracts.test_mvp_state_guard -v`
- `python tools/checks/check_reference_redlines.py`
- `git diff --check`

## 下一步
- 若继续沿异常红线推进，优先考虑扩大到更多“单异常但无上下文降级”形态，例如 `continue` / 更复杂的空载回退。
- 若误伤面开始上升，就切去“单函数 / 单类体量红线”这条同样高复利的支线。
