# V4 broad tuple context gate record

- 时间：2026-03-30 03:58:45 +0800
- 轮次：M1b Slice 199
- 本轮动作：继续收口 broad exception family 在 tuple 形态下的缺少上下文提示；现在 except (Exception, ValueError) 与 except (BaseException, KeyError) 不再落到“多异常 except”，而是统一按 broad except 语义要求绑定 as error。
- 合同补齐：tests/contracts/test_reference_redlines_check.py 新增 2 条 tuple-broad uncontextualized 合同，锁住 broad family 在 tuple 形态下的上下文文案不会回退到多异常提示。
- 代码收口：tools/checks/check_reference_redlines.py 让 _handler_context_requirement() 也复用 caught_types 级 broad 判定；tuple 中只要包含 Exception / BaseException，就优先返回 broad except 提示。
- 结果：broad exception family 现在在上下文门禁与静默降级门禁两条线上，都对单异常、裸 except、tuple broad 形态保持统一语义，后续维护更稳。
- 验证：python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py、python -m unittest tests.contracts.test_reference_redlines_check -v、python tools/checks/check_reference_redlines.py、python tools/checks/check_ledger_alignment.py、git diff --check
- 为什么这样做：这是 broad family 主线最后一类低命中语法边角；先收平这类变体，比提前扩更大异常面更稳、更省回滚成本。
- 下一步：继续盘 broad / multi-exception 家族是否还有同类双写或漏口；若这一面基本收平，再谨慎回看更窄的 ValueError 子集。
