# tools/

仓库工具入口索引。

## 当前子目录

- `tools/checks/`：协议层门禁检查（含 reference 红线门禁）
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
- 其中 `check_scaffold.py` 会把 `docs/reference/` 与 `docs/30-方案/02-V4-目录锁定清单.md` 转成硬门禁，不再依赖人工提醒
- 在这条 ledger policy chain 之后，会继续跑 `check_reference_redlines.py`，直接拦截无主 TODO、空异常处理、异常上下文未绑定/未使用、`json.JSONDecodeError` 上下文丢失，以及高风险 I/O/JSON 直接静默降级
- 这条 ledger policy chain 会显式前置在 `Contract tests` 之前
