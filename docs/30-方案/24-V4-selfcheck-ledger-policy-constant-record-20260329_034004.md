# V4 selfcheck ledger policy 常量化记录

## 本轮动作
- 将 `tools/checks/selfcheck.py` 里的 ledger policy chain 抽成单一常量真源。
- 让 `tests/contracts/test_selfcheck.py` 直接复用这份常量，而不是手写重复前缀列表。
- 本轮不改变任何实际检查内容，只收口顺序真源的维护方式。

## 为什么做这刀
- 上一轮已经把 ledger policy chain 前置，但顺序同时写在 `selfcheck.py` 与 `test_selfcheck.py` 两处。
- 如果后续继续微调阶段名或阶段顺序，双处维护很容易漂移。
- 先把顺序真源集中到一个常量里，后续加减阶段时只改一处，长期收益更高。

## 变更点
1. `tools/checks/selfcheck.py`
   - 新增 `LEDGER_POLICY_CHECKS`
   - 新增 `CONTRACT_TESTS_CHECK_NAME`
   - 用常量拼装 `CHECKS`
2. `tests/contracts/test_selfcheck.py`
   - 改为直接复用 `LEDGER_POLICY_CHECKS`
   - 改为校验 `CONTRACT_TESTS_CHECK_NAME` 必须位于 ledger policy chain 之后

## 最小验证
- `python -m py_compile tools/checks/selfcheck.py tests/contracts/test_selfcheck.py`
- `python -m unittest tests.contracts.test_selfcheck -v`

## 下一步
- 继续寻找第八个最小真实消费点。
- 若后续再调整 `selfcheck.py` 顺序，优先改常量真源，不再双处手写。