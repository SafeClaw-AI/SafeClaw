# V4 contracts readme ledger policy 记录

## 本轮动作
- 对齐 `tests/contracts/README.md`，把 contracts 测试入口显式写成现行 ledger-first 自检顺序。
- 扩大 `tools/checks/check_public_docs.py`，把 `tests/contracts/README.md` 里的这组关键标记锁进公开文档门禁。
- 在 `开发计划.md` 追加本轮计划调整说明，并把下一候选推进到第十三个最小真实消费点。

## 为什么做这刀
- `tests/contracts/README.md` 是 contracts 测试的长期入口，后续维护测试人员很容易先看这里。
- 如果这里只说合同测试与其他门禁的分工，长期仍可能忽略 Contract tests 其实是后置于 ledger-first chain 的现行顺序。
- 先把测试入口对齐，再由 public docs 门禁锁住，长期收益高于继续补二级索引页。

## 变更点
1. `tests/contracts/README.md`
   - 在“与其他门禁的关系”段补出 ledger-first policy chain
   - 显式声明 `Contract tests` 后置于 `ledger_index_manifest.py -> check_ledger_alignment.py -> check_consistency.py -> check_versions.py -> check_structure.py -> check_scaffold.py -> check_public_docs.py`
2. `tools/checks/check_public_docs.py`
   - 扩大 `CONTRACTS_README_FILE` 的关键标记集合
   - 把 contracts 测试入口纳入 ledger-first 公开文档门禁
3. `开发计划.md`
   - 记录本轮为何选择 `tests/contracts/README.md`
   - 将下一候选推进到第十三个最小真实消费点

## 最小验证
- `python -m py_compile tools/checks/check_public_docs.py tests/contracts/test_public_docs_check.py`
- `python -m unittest tests.contracts.test_public_docs_check -v`
- `python tools/checks/check_public_docs.py`

## 下一步
- 第十二个最小真实消费点已落到 `tests/contracts/README.md`。
- 下一刀继续找第十三个真实消费点，优先仍看长期维护入口或自动化入口。
