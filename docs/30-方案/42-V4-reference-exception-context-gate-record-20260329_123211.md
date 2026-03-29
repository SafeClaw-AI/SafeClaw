# V4 reference exception context gate 记录

## 时间
- `2026-03-29 12:32:11 +0800`

## 本轮动作
- 继续扩大 `tools/checks/check_reference_redlines.py` 的异常红线覆盖，从“空异常处理”推进到第二阶段。
- 新增 Python 多异常 `except (...)` / broad `except Exception` 必须显式绑定 `as error` 的门禁函数。
- 补上 `tests/contracts/test_reference_redlines_check.py` 合同，锁住“多异常 except 未绑定上下文必须失败 / 已绑定则通过”。
- 修平当前唯一命中点：`tools/mvp/safeclaw_mvp.py` 的 `load_heartbeat_config()` 不再使用未绑定的多异常 `except`。
- 同步更新 `tools/checks/README.md`、`tools/README.md` 与 `开发计划.md`，让入口与计划口径都跟上第二阶段规则。

## 为什么做这刀
- 第一阶段已经拦住了 `pass-only catch` 和空 `catch {}`，但多异常 `except` 如果不绑定异常对象，后续扩到真正的“上下文携带”会很难稳定推进。
- 先把“必须显式绑定上下文”做成硬门禁，误伤面小、长期收益高，是继续扩大异常红线最稳的一步。

## 结果
1. `tools/checks/check_reference_redlines.py`
   - 新增 `collect_uncontextualized_exception_errors_for_python_text()`
   - 把多异常 `except` / broad `Exception` 未绑定 `as error` 视为红线
2. `tests/contracts/test_reference_redlines_check.py`
   - 新增多异常异常上下文合同
3. `tools/mvp/safeclaw_mvp.py`
   - `load_heartbeat_config()` 的多异常捕获改为显式绑定 `as error`

## 最小验证
- `python -m unittest tests.contracts.test_reference_redlines_check -v`
- `python tools/checks/check_reference_redlines.py`

## 下一步
- 继续扩大异常红线，优先把“无上下文降级/吞异常”做成下一阶段硬门禁。
- 若误伤面过大，再考虑转做“单函数 / 单类体量红线”。
