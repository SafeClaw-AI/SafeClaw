# V4 contracts workflow ledger policy 记录

## 本轮动作
- 让 `.github/workflows/contracts.yml` 显式接入 ledger policy chain。
- 在 CI 中补上 `ledger_index_manifest.py` 与 `check_ledger_alignment.py` 两个前置步骤。
- 调整 workflow 顺序，让 `Contract tests` 晚于 `check_consistency.py`、`check_versions.py`、`check_structure.py`、`check_scaffold.py`、`check_public_docs.py` 与 `Naming lint`。
- 新增 `tests/contracts/test_contracts_workflow.py`，锁住这条 CI 顺序。

## 为什么做这刀
- `.github/workflows/contracts.yml` 是长期会被持续运行的真实入口，属于比局部说明更硬的门禁。
- 之前 workflow 还没有显式跑 `ledger_index_manifest.py` 与 `check_ledger_alignment.py`，而且 `Contract tests` 放得过早。
- 把 CI 调整到与现行 ledger policy chain 一致后，即使后续还有历史债，迁移期最关键的口径也会先被 CI 显式拦住。

## 变更点
1. `.github/workflows/contracts.yml`
   - 新增 `Run ledger index manifest check`
   - 新增 `Run ledger alignment check`
   - 调整各 step 顺序，使 CI 长期入口与现行 ledger policy chain 对齐
2. `tests/contracts/test_contracts_workflow.py`
   - 锁住 CI workflow 中 ledger policy chain 与 `Run contract tests` 的相对顺序

## 最小验证
- `python -m py_compile tests/contracts/test_contracts_workflow.py`
- `python -m unittest tests.contracts.test_contracts_workflow -v`
- `git diff --check`

## 下一步
- 现在第八个真实消费点已落到 CI contracts workflow。
- 下一刀应继续寻找第九个最小真实消费点。