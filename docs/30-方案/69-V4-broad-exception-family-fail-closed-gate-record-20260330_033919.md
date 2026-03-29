# V4 broad exception family fail-closed gate record

- 时间：2026-03-30 03:39:19 +0800
- 轮次：M1b Slice 197
- 本轮动作：调整 tools/checks/check_reference_redlines.py，把 BaseException 纳入 broad except 语义；同时把 except: / except Exception / except BaseException 的 direct return None/False 收成 fail-closed 门禁。
- 合同补齐：tests/contracts/test_reference_redlines_check.py 新增 BaseException 上下文门禁、三类 broad/裸 except 静默降级门禁，以及 BROAD_EXCEPTION_TYPE_NAMES 稳定性合同。
- 结果：reference redlines 现在对“广义兜底异常家族”形成统一语义——要么保留上下文，要么不能静默降级，减少后续继续扩异常家族时的双写和漏网。
- 验证：python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py、python -m unittest tests.contracts.test_reference_redlines_check -v、python tools/checks/check_reference_redlines.py、python tools/checks/check_ledger_alignment.py、git diff --check
- 为什么这样做：这刀命中面极小、零运行时业务改动，却能补掉 BaseException 与 broad except direct fallback 的 fail-open 缺口，长期收益高于贸然扩 ValueError。
- 下一步：继续沿 reference fail-closed 主线找“低命中 + 可统一真源”的切片，优先评估 broad handler 家族是否还有剩余双写点，再决定要不要试探更窄的 ValueError 子集。
