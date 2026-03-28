# V4 docs root README ledger policy 记录

## 本轮动作
- 对齐 `docs/README.md`，把公开文档总入口显式写成现行 ledger-first 自检顺序。
- 扩大 `tools/checks/check_public_docs.py`，把 `docs/README.md` 的这组关键标记锁进公开文档门禁。
- 在 `开发计划.md` 追加本轮计划调整说明，并把下一候选推进到第十五个最小真实消费点。

## 为什么做这刀
- `docs/README.md` 是公开文档总入口，后续维护者进入 `docs/` 时最容易先看到它。
- 如果这里只写索引与目录说明，长期仍可能忽略现行 ledger-first chain 是公开文档层共同遵守的入口顺序。
- 先把公开文档总入口对齐，再由 public docs 门禁锁住，长期收益高于继续补边缘说明页。

## 变更点
1. `docs/README.md`
   - 新增 `当前 selfcheck policy` 段
   - 显式声明 `tools/checks/selfcheck.py` 会先跑 `ledger_index_manifest.py -> check_ledger_alignment.py -> check_consistency.py -> check_versions.py -> check_structure.py -> check_scaffold.py -> check_public_docs.py`
2. `tools/checks/check_public_docs.py`
   - 扩大 `DOCS_README_FILE` 的关键标记集合
   - 把 docs 总入口纳入 ledger-first 公开文档门禁
3. `开发计划.md`
   - 记录本轮为何选择 `docs/README.md`
   - 将下一候选推进到第十五个最小真实消费点

## 最小验证
- `python -m py_compile tools/checks/check_public_docs.py tests/contracts/test_public_docs_check.py`
- `python -m unittest tests.contracts.test_public_docs_check -v`
- `python tools/checks/check_public_docs.py`

## 下一步
- 第十四个最小真实消费点已落到 `docs/README.md`。
- 下一刀继续找第十五个真实消费点，优先仍看长期维护入口或自动化入口。
