# V4 scope readme ledger policy 记录

## 本轮动作
- 对齐 `docs/V1_SCOPE.md`，把当前公开范围入口显式写成现行 ledger-first 自检顺序。
- 扩大 `tools/checks/check_public_docs.py`，把 `docs/V1_SCOPE.md` 的这组关键标记锁进公开文档门禁。
- 在 `开发计划.md` 追加本轮计划调整说明，并把下一候选推进到第十七个最小真实消费点。

## 为什么做这刀
- `docs/V1_SCOPE.md` 是当前公开范围入口，后续维护者判断“仓库当前到底公开到哪里”时最容易先看这里。
- 如果这里只写协议冻结与公开范围，长期仍可能忽略现行 ledger-first policy chain 是公开范围的一部分。
- 先把公开范围入口对齐，再由 public docs 门禁锁住，长期收益高于继续补边缘说明页。

## 变更点
1. `docs/V1_SCOPE.md`
   - 新增 `当前 selfcheck policy` 段
   - 显式声明 `tools/checks/selfcheck.py` 与 `.github/workflows/contracts.yml` 会先跑 `ledger_index_manifest.py -> check_ledger_alignment.py -> check_consistency.py -> check_versions.py -> check_structure.py -> check_scaffold.py -> check_public_docs.py`，然后才进入 `Contract tests`
2. `tools/checks/check_public_docs.py`
   - 扩大 `SCOPE_FILE` 的关键标记集合
   - 把当前公开范围入口纳入 ledger-first 公开文档门禁
3. `开发计划.md`
   - 记录本轮为何选择 `docs/V1_SCOPE.md`
   - 将下一候选推进到第十七个最小真实消费点

## 最小验证
- `python -m py_compile tools/checks/check_public_docs.py tests/contracts/test_public_docs_check.py`
- `python -m unittest tests.contracts.test_public_docs_check -v`
- `python tools/checks/check_public_docs.py`

## 下一步
- 第十六个最小真实消费点已落到 `docs/V1_SCOPE.md`。
- 下一刀继续找第十七个真实消费点，优先仍看长期维护入口或自动化入口。
