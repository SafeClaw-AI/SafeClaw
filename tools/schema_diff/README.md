# tools/schema_diff/

用于比较两个 schema 文件或两个 schema 目录。

当前支持：

- 文本摘要输出
- `--json-out`：输出机器可读 JSON
- `--fail-on-diff`：发现差异时返回非 0，便于自动化门禁

示例：

- `python tools/schema_diff/main.py specs specs`
- `python tools/schema_diff/main.py specs specs --json-out tmp/schema_diff.json`
- `python tools/schema_diff/main.py old_dir new_dir --fail-on-diff`
