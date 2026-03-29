# V4 lint readme ledger policy 记录

## 本轮动作
- 对齐 `tools/lint/README.md`，把稳定命名门禁入口显式写成现行 ledger-first 自检顺序。
- 扩大 `tools/checks/check_public_docs.py`，把 `tools/lint/README.md` 的这组关键标记锁进公开文档门禁，并补齐上一刀 `tools/mvp/README.md` 只声明常量、未实际纳入门禁的同类缺口。
- 补上 `tests/contracts/test_public_docs_check.py`，锁住新增 public README 入口必须真正接入 `REQUIRED_MARKERS`，避免后续再出现“只加路径常量、未接门禁”的假收口。
- 在 `开发计划.md` 追加本轮计划调整说明，并把下一候选推进到第二十三个最小真实消费点。

## 为什么做这刀
- `tools/lint/README.md` 是稳定命名门禁入口，后续维护者很容易先从这里理解命名约束与公开门禁的关系。
- 如果这里只写命名规则，而不显式说明现行 ledger-first policy chain，后续执行顺序仍可能回退到旧口径。
- 先把 lint 命名入口对齐，再由 public docs 门禁锁住，长期收益高于继续补边缘说明页。

## 变更点
1. `tools/lint/README.md`
   - 新增 `当前 ledger-first policy` 段
   - 显式声明 ledger policy chain 会先于 `tools/lint/check_naming.py` 执行，然后才进入 `Contract tests`
2. `tools/checks/check_public_docs.py`
   - 新增 `LINT_README_FILE` 门禁项
   - 把 lint 命名入口纳入 ledger-first 公开文档门禁
   - 同时补齐 `MVP_README_FILE` 的公开门禁映射，修掉上一刀遗留的同类漏口
3. `tests/contracts/test_public_docs_check.py`
   - 新增 `test_newly_added_public_readmes_are_guarded_by_public_docs_check`
   - 锁住 `MVP_README_FILE` 与 `LINT_README_FILE` 必须都被 `REQUIRED_MARKERS` 消费
4. `开发计划.md`
   - 记录本轮为何选择 `tools/lint/README.md`
   - 将下一候选推进到第二十三个最小真实消费点

## 最小验证
- `python -m py_compile tools/checks/check_public_docs.py tests/contracts/test_public_docs_check.py`
- `python -m unittest tests.contracts.test_public_docs_check -v`
- `python tools/checks/check_public_docs.py`

## 下一步
- 第二十二个最小真实消费点已落到 `tools/lint/README.md`。
- 下一刀继续找第二十三个真实消费点，优先仍看长期维护入口或自动化入口。
