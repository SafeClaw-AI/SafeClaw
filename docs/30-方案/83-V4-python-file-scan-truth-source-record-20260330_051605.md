# V4 python file scan truth source record

- 时间：2026-03-30 05:16:05 +0800
- 轮次：M1b Slice 211
- 本轮动作：新增 `_collect_python_reference_redline_errors()`，把三条顶层 Python 文件扫描器里重复的“筛 `.py` / 读文件 / 转相对路径 / 调 collector”骨架收成单一入口。
- 代码收口：`tools/checks/check_reference_redlines.py` 的 `collect_uncontextualized_exception_errors()`、`collect_unused_bound_exception_context_errors()`、`collect_silent_fallback_exception_errors()` 现已统一复用同一份 Python 文件扫描真源。
- 合同补齐：`tests/contracts/test_reference_redlines_check.py` 新增 `test_collect_python_reference_redline_errors_is_stable`，锁住 `.py` 过滤、相对路径传递与文本透传口径。
- 结果：reference redlines 现已同时具备 Python 解析真源与 Python 文件扫描真源；后续若继续补 Python 规则，只需围绕这两层入口扩展，长期更稳。
- 验证：python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py、python -m unittest tests.contracts.test_reference_redlines_check -v、python tools/checks/check_reference_redlines.py、python tools/checks/check_ledger_alignment.py、git diff --check
- 为什么这样做：在 Python 解析骨架已收平后，继续把顶层 `.py` 文件扫描骨架也收成单一入口，能进一步降低后续加规则时的重复改动面。
- 下一步：继续评估把顶层 TODO / empty-exception / PowerShell 扫描器也抽成同类入口，或回到 broad / multi-exception 家族最后的小重复点。
