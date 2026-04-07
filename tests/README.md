# tests/

测试目录索引。

## 当前子目录

- `tests/contracts/`：协议级合同测试
- `tests/fixtures/`：后续 simulation / replay / chaos 夹具预留目录

## 当前重点

当前阶段优先保证合同测试稳定，
夹具目录先保留落点，后续再按协议与场景逐步补齐。

- `selfcheck.py` 与 `.github/workflows/contracts.yml` 会先跑 `ledger_index_manifest.py`
- 然后依次跑 `check_ledger_alignment.py`、`check_consistency.py`、`check_versions.py`、`check_structure.py`、`check_scaffold.py`、`check_public_docs.py`
- 随后的 `check_reference_redlines.py` 还会继续锁 `docs/reference/01-反屎山工程规范.md`、`docs/reference/02-结构性债务台账.md` 与 `docs/reference/03-绕过白名单.md`
- `tests/contracts/` 会显式后置在这条 ledger policy chain 之后
