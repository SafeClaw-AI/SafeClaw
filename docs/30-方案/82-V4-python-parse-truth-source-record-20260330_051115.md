# V4 python parse truth source record

- 时间：2026-03-30 05:11:15 +0800
- 轮次：M1b Slice 210
- 本轮动作：新增 `_parse_python_text_for_reference_check()` 与 `PythonTextParseResult`，把“`path.as_posix()` + `ast.parse()` + `SyntaxError` 转人话”四处重复骨架收成单一真源。
- 代码收口：`tools/checks/check_reference_redlines.py` 的空异常、缺少上下文、绑定未使用、静默降级四条 Python 检查链路现在都统一复用同一份 parse 结果，不再各自重复解析。
- 合同补齐：`tests/contracts/test_reference_redlines_check.py` 新增 `test_parse_python_text_for_reference_check_is_stable`，锁住有效 Python 与无效 Python 两种返回口径。
- 结果：reference redlines 现已把 handler 画像真源、遍历真源与 Python 解析真源接成同一条链；后续若继续加 Python 规则，只需围绕这三层真源扩展。
- 验证：python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py、python -m unittest tests.contracts.test_reference_redlines_check -v、python tools/checks/check_reference_redlines.py、python tools/checks/check_ledger_alignment.py、git diff --check
- 为什么这样做：在 handler/profile 主线已基本收平后，继续压掉四处重复的 Python 解析骨架，能显著降低后续扩规则时的边际维护成本，而不需贸然碰高爆炸面的异常覆盖。
- 下一步：继续扫 broad / multi-exception 家族最后的小重复点，或开始评估把顶层 Python 文件扫描器也收成单一入口。
