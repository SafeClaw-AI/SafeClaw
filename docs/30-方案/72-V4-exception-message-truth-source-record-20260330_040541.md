# V4 exception message truth source record

- 时间：2026-03-30 04:05:41 +0800
- 轮次：M1b Slice 200
- 本轮动作：把 reference redlines 里的异常上下文 / 静默降级核心提示文案收成单一真源，避免后续继续扩异常门禁时再到处手写同一句中文。
- 合同补齐：tests/contracts/test_reference_redlines_check.py 新增 1 条消息真源稳定性合同，锁住 CONTEXT_REQUIRED_SUFFIX、SILENT_FALLBACK_SUFFIX、bare/broad/multi 三组消息常量的语义口径。
- 代码收口：tools/checks/check_reference_redlines.py 新增上下文与静默降级的消息常量，并让 _handler_context_requirement() / _silent_fallback_requirement() 统一复用这些真源片段生成提示。
- 结果：异常门禁文案从“多处手写字符串”收成“单点常量 + 组合生成”，后续继续补 broad / high-risk 规则时更稳，也更不容易再出现编码漂移。
- 验证：python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py、python -m unittest tests.contracts.test_reference_redlines_check -v、python tools/checks/check_reference_redlines.py、python tools/checks/check_ledger_alignment.py、git diff --check
- 为什么这样做：这一轮已经反复触到重复中文文案的维护风险；先把提示文本真源化，比继续往外扩异常类型更能降低后续维护成本。
- 下一步：继续扫 broad / multi-exception 家族是否还有剩余双写点；若这一面基本收平，再谨慎评估更窄的 ValueError 子集。
