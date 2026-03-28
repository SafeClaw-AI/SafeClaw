# V4 tests root README ledger policy 记录

## 本轮动作
- 对齐 `tests/README.md`，把测试总入口显式写成现行 ledger-first 自检顺序。
- 扩大 `tools/checks/check_public_docs.py`，把 `tests/README.md` 的这组关键标记锁进公开文档门禁。
- 在 `开发计划.md` 追加本轮计划调整说明，并把下一候选推进到第十四个最小真实消费点。

## 为什么做这刀
- `tests/README.md` 是测试总入口，后续维护者进入 `tests/` 时最容易先看到它。
- 如果这里只写 contracts/fixtures 的目录分工，长期仍可能忽略 contracts 测试其实后置于 ledger-first chain 的现行顺序。
- 先把测试总入口对齐，再由 public docs 门禁锁住，长期收益高于继续补边缘说明页。

## 变更点
1. `tests/README.md`
   - 在“当前重点”段补出 ledger-first policy chain
   - 显式声明 `tests/contracts/` 后置于 `ledger_index_manifest.py -> check_ledger_alignment.py -> check_consistency.py -> check_versions.py -> check_structure.py -> check_scaffold.py -> check_public_docs.py`
2. `tools/checks/check_public_docs.py`
   - 扩大 `TESTS_README_FILE` 的关键标记集合
   - 把 tests 总入口纳入 ledger-first 公开文档门禁
3. `开发计划.md`
   - 记录本轮为何选择 `tests/README.md`
   - 将下一候选推进到第十四个最小真实消费点

## 最小验证
- `python -m py_compile tools/checks/check_public_docs.py tests/contracts/test_public_docs_check.py`
- `python -m unittest tests.contracts.test_public_docs_check -v`
- `python tools/checks/check_public_docs.py`

## 下一步
- 第十三个最小真实消费点已落到 `tests/README.md`。
- 下一刀继续找第十四个真实消费点，优先仍看长期维护入口或自动化入口。
