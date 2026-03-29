# V4 tuple broad fallback fail-closed gate record

- 时间：2026-03-30 03:50:42 +0800
- 轮次：M1b Slice 198
- 本轮动作：继续收口 broad exception family 在 tuple 形态下的剩余漏口；现在 except (Exception, ValueError) 与 except (BaseException, KeyError) 这类 direct return None/False 也会被 reference redlines fail-closed 拦下。
- 合同补齐：tests/contracts/test_reference_redlines_check.py 新增 2 条 tuple-broad direct fallback 合同，锁住 broad family 在元组形态下不会绕过静默降级门禁。
- 代码收口：tools/checks/check_reference_redlines.py 新增 caught_types 级 broad 判定，silent fallback 门禁与文案都按 broad family 优先生效，不再被 tuple 中的其他异常名分流。
- 结果：broad exception family 的 fail-closed 语义从单异常 / 裸 except 扩展到 tuple broad handler，减少后续继续扩异常家族时的漏网边角。
- 验证：python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py、python -m unittest tests.contracts.test_reference_redlines_check -v、python tools/checks/check_reference_redlines.py、python tools/checks/check_ledger_alignment.py、git diff --check
- 为什么这样做：这刀命中面极小，但能把 broad family 的最后一类常见语法变体收平；比贸然扩更大面的异常类型更稳、更有复利。
- 下一步：继续检查 broad / multi-exception 家族是否还有同类漏口；若这一面基本收平，再回到更窄、更可控的 ValueError 子集评估。
