# tools/codegen/

用于从当前 `specs/` 生成最小稳定索引。

当前支持：

- `python tools/codegen/main.py --target rust`
- `python tools/codegen/main.py --target python`
- `python tools/codegen/main.py --target ts`
- `python tools/codegen/regenerate_all.py`

当前生成产物：

- `generated/<target>/manifest.json`
- `generated/<target>/stable_ids.json`
- `generated/index.json`

这些产物是 Phase 0 的最小稳定索引，便于后续 AI 生成、测试、审阅与回归检查。

## 当前 ledger-first policy

- `python tools/codegen/regenerate_all.py` 会先把 `generated/index.json` 与各 target 的 `manifest.json`、`stable_ids.json` 刷到当前 `specs/` 基线
- 然后由 `tools/checks/selfcheck.py` 与 `.github/workflows/contracts.yml` 先跑 `ledger_index_manifest.py`
- 再依次跑 `check_ledger_alignment.py`、`check_consistency.py`、`check_versions.py`、`check_structure.py`、`check_scaffold.py`、`check_public_docs.py`，然后才进入 `Contract tests`
