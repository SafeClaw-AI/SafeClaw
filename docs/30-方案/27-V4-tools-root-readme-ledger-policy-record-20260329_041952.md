# V4 tools root README ledger policy 记录

## 本轮动作
- 对齐 `tools/README.md`，把仓库工具总入口显式写成现行 ledger-first 自检顺序。
- 扩大 `tools/checks/check_public_docs.py`，把 `tools/README.md` 里的这组关键标记锁进公开文档门禁。
- 在 `开发计划.md` 追加本轮计划调整说明，并把下一候选推进到第十一个最小真实消费点。

## 为什么做这刀
- `tools/README.md` 是仓库工具总入口，维护者进入 `tools/` 后最容易先看到它。
- 如果这里只保留 `python tools/checks/selfcheck.py`，长期仍可能按旧理解把它当成黑盒入口。
- 先把总入口说明对齐，再由 public docs 门禁锁住，长期收益高于继续补次级说明页。

## 变更点
1. `tools/README.md`
   - 新增 `Current selfcheck policy` 段
   - 显式列出 `ledger_index_manifest.py -> check_ledger_alignment.py -> check_consistency.py -> check_versions.py -> check_structure.py -> check_scaffold.py -> check_public_docs.py -> Contract tests`
2. `tools/checks/check_public_docs.py`
   - 扩大 `TOOLS_README_FILE` 的关键标记集合
   - 把 tools 根入口也纳入 ledger-first 公开文档门禁
3. `开发计划.md`
   - 记录本轮为何选择 `tools/README.md`
   - 将下一候选推进到第十一个最小真实消费点

## 最小验证
- `python -m py_compile tools/checks/check_public_docs.py tests/contracts/test_public_docs_check.py`
- `python -m unittest tests.contracts.test_public_docs_check -v`
- `python tools/checks/check_public_docs.py`

## 下一步
- 第十个最小真实消费点已落到 `tools/README.md`。
- 下一刀继续找第十一个真实消费点，优先仍看长期维护入口或自动化入口。
