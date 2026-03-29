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

## 当前 ledger-first policy

- `python tools/schema_diff/main.py` 用于先比较 schema 输入差异，帮助在进入公开门禁前提前看到结构偏移
- 然后由 `tools/checks/selfcheck.py` 与 `.github/workflows/contracts.yml` 先跑 `ledger_index_manifest.py`
- 再依次跑 `check_ledger_alignment.py`、`check_consistency.py`、`check_versions.py`、`check_structure.py`、`check_scaffold.py`、`check_public_docs.py`，然后才进入 `Contract tests`
