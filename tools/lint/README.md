# tools/lint/

这里放的是 **稳定命名约束检查**。

当前 `check_naming.py` 主要锁定：

- spec 文件与目录命名
- Worker `state_id / event_id`
- `tier_id / rev_id`
- `error code`
- `spi_name`
- effect action 名称

目标不是做风格偏好检查，
而是保护已经冻结的稳定标识不被随意改坏。

## 当前 ledger-first policy

- `tools/lint/check_naming.py` 负责锁定稳定标识的命名不漂移，但现行公开门禁顺序仍以 ledger policy chain 为前置
- `tools/checks/selfcheck.py` 与 `.github/workflows/contracts.yml` 会先跑 `ledger_index_manifest.py`、`check_ledger_alignment.py`、`check_consistency.py`、`check_versions.py`、`check_structure.py`、`check_scaffold.py`、`check_public_docs.py`
- 然后才会进到 `tools/lint/check_naming.py`，并在后续再进入 `Contract tests`
