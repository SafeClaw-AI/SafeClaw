# docs/

公开文档索引。

## 当前文件

- `docs/DEVLOG.md`：公开开发日志
- `docs/IMPLEMENTATION_STRATEGY.md`：实现推进策略，明确“步步为营，层层推进”的默认节奏
- `docs/V1_SCOPE.md`：当前公开范围说明
- `docs/V1_TASK_TRIAGE.md`：当前任务分级说明
- `docs/30-方案/02-V4-目录锁定清单.md`：当前目录锁定依据，后续目录变更先看这里
- `docs/30-方案/04-V4-repo-hygiene-migration-plan.md`：仓库卫生整改的迁移真源，定义阶段、顺序与回滚思路
- `docs/30-方案/06-V4-ledger-compat-index-spec.md`：台账兼容索引规则，定义新旧路径映射与读取优先级
- `docs/30-方案/08-V4-ledger-index-manifest.json`：台账索引最小机读真源，供后续脚本读取
- `docs/30-方案/20-V4-reference-compliance-rebaseline-record-20260329_030242.md`：当前 reference 合规纠偏快照，说明旧审计里哪些说法已过期
- `docs/chancellor-mode/v2/`：现行丞相模式方案真源目录
- `docs/chancellor-mode/v2/01-m1b-exit-and-m2-panel-entry.md`：现行 `M1b` 收口与 `M2` 面板入口决议真源
- `docs/chancellor-mode/v2/02-m2-panel-command-truth-source.md`：`M2-1` 四个丞相面板命令的输入/输出字段真源表

## 说明

这里的公开文档用于解释当前仓库状态，
但涉及协议真源时，仍以 `README.md`、`VERSION`、`specs/`、`tests/contracts/`、`tools/checks/` 为准。
目录结构是否允许调整，统一以 `docs/30-方案/02-V4-目录锁定清单.md` 为准。

## 当前 selfcheck policy

- `tools/checks/selfcheck.py` 会先跑 `ledger_index_manifest.py`
- 然后依次跑 `check_ledger_alignment.py`、`check_consistency.py`、`check_versions.py`、`check_structure.py`、`check_scaffold.py`、`check_public_docs.py`
- `tests/contracts/` 与其他后续门禁会显式后置在这条 ledger policy chain 之后
