# tools/

仓库工具入口索引。

## 当前子目录

- `tools/checks/`：协议层门禁检查
- `tools/lint/`：稳定命名检查
- `tools/codegen/`：最小稳定索引生成
- `tools/schema_diff/`：schema 比较与自动化 diff
- `tools/mvp/`：当前 Win11 本地 MVP 操作入口与示例命令

## 推荐入口

- 重建生成产物：`python tools/codegen/regenerate_all.py`
- 运行全量门禁：`python tools/checks/selfcheck.py`

## Current selfcheck policy

- `tools/checks/selfcheck.py` 会先跑 `ledger_index_manifest.py`
- 然后依次跑 `check_ledger_alignment.py`、`check_consistency.py`、`check_versions.py`、`check_structure.py`、`check_scaffold.py`、`check_public_docs.py`
- 这条 ledger policy chain 会显式前置在 `Contract tests` 之前
