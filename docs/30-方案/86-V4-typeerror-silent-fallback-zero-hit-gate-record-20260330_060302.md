# V4 typeerror silent fallback zero-hit gate record

- 时间：2026-03-30 06:03:02 +0800
- 轮次：M1b Slice 214
- 本轮动作：把 `TypeError` 纳入 `SILENT_FALLBACK_EXCEPTION_TYPE_ORDER`，继续扩大 direct `None/False` 静默降级红线。
- 代码收口：`tools/checks/check_reference_redlines.py` 现在会阻断 `except TypeError: return None/False` 这类输入/调用形态的静默降级。
- 合同补齐：`tests/contracts/test_reference_redlines_check.py` 新增 `TypeError` direct fallback 必败合同，以及“非 direct None/False 仍允许”合同；同时锁住名单真源顺序。
- 基线结果：全仓当前 `TypeError` catch 命中为 0，本轮属于零旧债扩面；无需修平既有业务代码。
- 验证：python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py、python -m unittest tests.contracts.test_reference_redlines_check -v、python tools/checks/check_reference_redlines.py、python tools/checks/check_ledger_alignment.py、git diff --check
- 为什么这样做：`TypeError` 与 `ValueError` 同属输入/调用边界上最常见的降级异常族；在零命中时先补成 fail-closed，比等未来再次落地后再回头补救更稳。
- 下一步：继续评估空字符串 / 空容器这类降级形态；若仍零命中，则考虑直接补未来门禁而不拖旧代码包袱。
