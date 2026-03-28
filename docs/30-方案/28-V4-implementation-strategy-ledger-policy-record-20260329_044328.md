# V4 implementation strategy ledger policy 记录

## 本轮动作
- 对齐 `docs/IMPLEMENTATION_STRATEGY.md`，把长期策略文档显式写成现行 ledger-first 自检顺序。
- 扩大 `tools/checks/check_public_docs.py`，把 `docs/IMPLEMENTATION_STRATEGY.md` 的这组关键标记锁进公开文档门禁。
- 在 `开发计划.md` 追加本轮计划调整说明，并把下一候选推进到第十二个最小真实消费点。

## 为什么做这刀
- `docs/IMPLEMENTATION_STRATEGY.md` 是长期策略入口，后续推进很容易回看这份文档。
- 如果这里只有“`selfcheck.py` 继续通过”，长期仍可能把现行顺序理解成黑盒，不利于后续开发保持一致。
- 先把长期策略入口对齐，再由 public docs 门禁锁住，长期收益高于继续补边缘说明页。

## 变更点
1. `docs/IMPLEMENTATION_STRATEGY.md`
   - 新增 `当前 selfcheck policy` 段
   - 显式列出 `ledger_index_manifest.py -> check_ledger_alignment.py -> check_consistency.py -> check_versions.py -> check_structure.py -> check_scaffold.py -> check_public_docs.py -> Contract tests`
2. `tools/checks/check_public_docs.py`
   - 新增 `IMPLEMENTATION_STRATEGY_FILE`
   - 把长期策略文档纳入 ledger-first 公开文档门禁
3. `开发计划.md`
   - 记录本轮为何选择 `docs/IMPLEMENTATION_STRATEGY.md`
   - 将下一候选推进到第十二个最小真实消费点

## 最小验证
- `python -m py_compile tools/checks/check_public_docs.py tests/contracts/test_public_docs_check.py`
- `python -m unittest tests.contracts.test_public_docs_check -v`
- `python tools/checks/check_public_docs.py`

## 下一步
- 第十一个最小真实消费点已落到 `docs/IMPLEMENTATION_STRATEGY.md`。
- 下一刀继续找第十二个真实消费点，优先仍看长期维护入口或自动化入口。
