# V4 reference exception context usage gate 记录

## 时间
- `2026-03-29 12:39:04 +0800`

## 本轮动作
- 继续扩大 `tools/checks/check_reference_redlines.py` 的异常红线覆盖，从“必须绑定 `as error`”推进到“绑定后的异常上下文必须真正使用”。
- 新增 `collect_unused_bound_exception_context_errors_for_python_text()`，拦截 `except (...) as error:` 后只做 `_ = error` 这类占位赋值的伪使用。
- 补上 `tests/contracts/test_reference_redlines_check.py` 合同，锁住“绑定了异常对象但只做占位赋值必须失败 / 真正传递上下文则通过”。
- 修平当前唯一命中点：`tools/mvp/safeclaw_mvp.py` 的 `load_heartbeat_config()` 现在会把异常类型写进 `fallback_reason`，不再只是 `_ = error`。

## 为什么做这刀
- 第二阶段已经要求多异常 / broad except 必须显式绑定 `as error`，但如果代码只是绑定后又丢掉，长期仍然无法形成真正的上下文传递能力。
- 先把“必须真正使用异常上下文”做成第三阶段硬门禁，能稳步逼近《总纲》要求，又不会一下子误伤大量历史代码。

## 结果
1. `tools/checks/check_reference_redlines.py`
   - 新增“已绑定异常上下文必须真正使用”的 AST 校验
   - 现已形成三层异常红线：空异常处理 → 必须绑定上下文 → 绑定后必须真正使用
2. `tests/contracts/test_reference_redlines_check.py`
   - 新增占位赋值失败 / 真正使用通过的合同
3. `tools/mvp/safeclaw_mvp.py`
   - `load_heartbeat_config()` 现在把 fallback 原因显式编码为 `fallback_reason`

## 最小验证
- `python -m unittest tests.contracts.test_reference_redlines_check -v`
- `python tools/checks/check_reference_redlines.py`

## 下一步
- 继续扩大异常红线，优先把“无上下文降级/吞异常”做成下一阶段硬门禁。
- 若误伤面开始升高，再切到“单函数 / 单类体量红线”这条长期高收益支线。
