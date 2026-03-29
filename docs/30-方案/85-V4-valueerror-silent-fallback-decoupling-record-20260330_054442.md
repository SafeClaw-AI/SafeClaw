# V4 valueerror silent fallback decoupling record

- 时间：2026-03-30 05:44:42 +0800
- 轮次：M1b Slice 213
- 本轮动作：把 `SILENT_FALLBACK_EXCEPTION_TYPE_ORDER` 从 `CONTEXT_REQUIRED_EXCEPTION_TYPE_ORDER` 里拆出来，并把 `ValueError` 只纳入“直接静默降级”红线，不强行扩大到“必须绑定 `as error`”面。
- 代码收口：`tools/checks/check_reference_redlines.py` 现已分离“上下文强绑定名单”与“静默降级阻断名单”；`ValueError -> return None/False` 现在会被 fail-closed 拦住。
- 旧代码修平：`tools/mvp/safeclaw_mvp.py` 已收平 3 个真实命中点：ISO 时间解析、preflight 权限推断、`get_flag()` 标志检索。
- 合同补齐：`tests/contracts/test_reference_redlines_check.py` 新增 `ValueError` 静默降级阻断合同与“非 direct None/False 仍允许”合同，并锁住新的名单拆分口径。
- 结果：reference redlines 现在能更精准地拦“可疑的输入解析静默降级”，同时不把所有 `ValueError` 一次性都拉进绑定上下文高噪音面。
- 验证：python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py tools/mvp/safeclaw_mvp.py、python -m unittest tests.contracts.test_reference_redlines_check -v、python tools/checks/check_reference_redlines.py、python tools/checks/check_ledger_alignment.py、git diff --check
- 为什么这样做：这刀选择“更难但更稳”的拆分方案，先把两类风险名单真源分开，避免今后只想扩“静默降级红线”时被迫连带扩大“上下文绑定”面。
- 下一步：优先回到 `docs/reference/01` 的异常降级主线，继续评估 `None/False` 之外的空容器 / 空字符串降级形态。
