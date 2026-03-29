# V4 reference scan text truth source record

- 时间：2026-03-30 05:20:54 +0800
- 轮次：M1b Slice 212
- 本轮动作：新增 `_iter_reference_redline_scan_texts()` 与 `ReferenceRedlineScanText`，把顶层 reference 扫描器共有的“筛后缀 / 读文件 / 转相对路径”骨架收成单一入口。
- 代码收口：`tools/checks/check_reference_redlines.py` 的 `collect_todo_metadata_errors()`、`collect_empty_exception_errors()` 与 `_collect_python_reference_redline_errors()` 现已统一复用同一份文件文本扫描真源。
- 合同补齐：`tests/contracts/test_reference_redlines_check.py` 新增 `test_iter_reference_redline_scan_texts_is_stable`，锁住后缀过滤、相对路径传递与文本透传口径。
- 结果：reference redlines 现已同时具备“文件枚举真源 + 文件文本扫描真源 + Python 解析真源 + handler 画像真源”；后续继续补规则时，重复改动面更小。
- 验证：python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py、python -m unittest tests.contracts.test_reference_redlines_check -v、python tools/checks/check_reference_redlines.py、python tools/checks/check_ledger_alignment.py、git diff --check
- 为什么这样做：上一刀只收平了三条 Python 顶层扫描器，但 TODO 与 empty-exception 仍各自重复做读盘与相对路径转换；本轮继续往上一层抽，长期更稳。
- 下一步：回到 `docs/reference/01` 的异常红线扩面；若后续再出现扫描骨架重复，直接基于这一真源继续收口。
