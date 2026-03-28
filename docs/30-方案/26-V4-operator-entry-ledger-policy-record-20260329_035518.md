# V4 operator entry ledger policy 记录

## 本轮动作
- 对齐根 `README.md` 里的 `selfcheck.py` 描述，让公开入口反映现行 ledger-first 门禁顺序。
- 对齐 `tools/mvp/OPERATOR_PLAYBOOK.md` 的 Verification 段，明确 `verify` 只跑 practical operator flow，而 `selfcheck.py` 会先跑 ledger policy chain。
- 扩大 `check_public_docs.py`，把根 README 与 Operator Playbook 里的这两处入口说明一起锁住。

## 为什么做这刀
- `.github/workflows/contracts.yml` 已成为第八个真实消费点，但普通维护者最先看到的仍是根 README 和 Operator Playbook。
- 如果入口说明继续落后，维护层会再次按旧口径理解 `selfcheck.py`。
- 先把这两个长期入口对齐并纳入 public docs 门禁，能把“现行 ledger-first 自检顺序”稳定传达到人和自动化两边。

## 变更点
1. `README.md`
   - 将 `selfcheck.py` 说明更新为 ledger-first 顺序
2. `tools/mvp/OPERATOR_PLAYBOOK.md`
   - 在 Verification 段补出 `verify` 与 `selfcheck.py` 的职责区别
   - 显式列出 `ledger_index_manifest.py -> check_ledger_alignment.py -> check_consistency.py -> check_versions.py -> check_structure.py -> check_scaffold.py -> check_public_docs.py -> Contract tests`
3. `tools/checks/check_public_docs.py`
   - 扩大根 README 的关键标记
   - 新增 `OPERATOR_PLAYBOOK_FILE` 并锁住当前 ledger-first 入口说明

## 最小验证
- `python -m py_compile tools/checks/check_public_docs.py tests/contracts/test_public_docs_check.py`
- `python -m unittest tests.contracts.test_public_docs_check -v`
- `python tools/checks/check_public_docs.py`

## 下一步
- 现在第九个最小切片已落到维护入口说明层。
- 下一刀继续找第十个真实消费点，优先仍看长期维护或自动化入口。