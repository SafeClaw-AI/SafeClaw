# V4 selfcheck ledger policy chain 记录

## 本轮动作
- 调整 `tools/checks/selfcheck.py` 的检查顺序，把 ledger 迁移前的策略链显式前置。
- 新增 `tests/contracts/test_selfcheck.py`，锁住这条策略链的前置顺序。
- 本轮不新增业务功能，不触碰台账真实迁移，只加总门禁顺序护栏。

## 为什么做这刀
- `selfcheck.py` 是统一总门禁，但此前 `Contract tests` 放得过早，容易被历史失败提前打断，遮住后面的 ledger 细粒度护栏。
- 把 ledger 策略链前置后，即使后面还有历史债，当前迁移期最关键的结构/版本/文档/脚手架口径仍能先显式失败。
- 这刀短期只是顺序调整，但长期能持续提升排障效率和回归定位速度。

## 变更点
1. `tools/checks/selfcheck.py`
   - 将 `Cross-file consistency`
   - `Version consistency`
   - `Structure completeness`
   - `Scaffold layout`
   - `Public docs alignment`
   显式前置到 `Contract tests` 之前
2. `tests/contracts/test_selfcheck.py`
   - 锁住 ledger policy chain 前缀顺序
   - 锁住 `Contract tests` 必须晚于 `Public docs alignment`

## 最小验证
- `python -m py_compile tools/checks/selfcheck.py tests/contracts/test_selfcheck.py`
- `python -m unittest tests.contracts.test_selfcheck -v`

## 下一步
- 继续寻找第八个最小真实消费点。
- 若后续再补 selfcheck 相关刀，优先考虑“显式阶段可读性”而不是重复堆同类规则。