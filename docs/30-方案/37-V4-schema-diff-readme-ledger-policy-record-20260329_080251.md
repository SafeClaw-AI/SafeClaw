# V4 schema diff readme ledger policy 记录

## 本轮动作
- 对齐 `tools/schema_diff/README.md`，把 schema diff 自动化入口显式写成现行 ledger-first 自检顺序。
- 扩大 `tools/checks/check_public_docs.py`，把 `tools/schema_diff/README.md` 的这组关键标记锁进公开文档门禁。
- 在 `开发计划.md` 追加本轮计划调整说明，并把下一候选推进到第二十一个最小真实消费点。

## 为什么做这刀
- `tools/schema_diff/README.md` 是 schema diff 自动化入口，后续维护者与门禁脚本很容易先从这里理解差异输出与下游检查的关系。
- 如果这里只写 diff 命令，而不显式说明现行 ledger-first policy chain，后续执行顺序仍可能回退到旧口径。
- 先把 schema diff 入口对齐，再由 public docs 门禁锁住，长期收益高于继续补边缘说明页。

## 变更点
1. `tools/schema_diff/README.md`
   - 新增 `当前 ledger-first policy` 段
   - 显式声明 `python tools/schema_diff/main.py` 主要用于提前看 schema 差异，之后仍会由 `tools/checks/selfcheck.py` 与 `.github/workflows/contracts.yml` 先跑 `ledger_index_manifest.py -> check_ledger_alignment.py -> check_consistency.py -> check_versions.py -> check_structure.py -> check_scaffold.py -> check_public_docs.py`，然后才进入 `Contract tests`
2. `tools/checks/check_public_docs.py`
   - 扩大 `SCHEMA_DIFF_README_FILE` 的关键标记集合
   - 把 schema diff 入口纳入 ledger-first 公开文档门禁
3. `开发计划.md`
   - 记录本轮为何选择 `tools/schema_diff/README.md`
   - 将下一候选推进到第二十一个最小真实消费点

## 最小验证
- `python -m py_compile tools/checks/check_public_docs.py tests/contracts/test_public_docs_check.py`
- `python -m unittest tests.contracts.test_public_docs_check -v`
- `python tools/checks/check_public_docs.py`

## 下一步
- 第二十个最小真实消费点已落到 `tools/schema_diff/README.md`。
- 下一刀继续找第二十一个真实消费点，优先仍看长期维护入口或自动化入口。
