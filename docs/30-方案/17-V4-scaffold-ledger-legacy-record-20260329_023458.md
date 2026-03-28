# V4 scaffold ledger legacy 护栏记录

## 目标
- 把第五个真实消费点落到 `check_scaffold.py`。
- 在真正迁移三份主台账前，先锁住 legacy 阶段根台账文件仍须保留。
- 让仓库骨架门禁也开始显式消费 ledger manifest，而不是只检查固定目录和固定文件。

## 本轮动作
1. 更新 `tools/checks/check_scaffold.py`
   - 新增 `collect_ledger_scaffold_errors()`
   - 校验 `legacy-only` / `dual-readable` 阶段的根台账文件仍存在
   - 校验这些 legacy 台账路径仍是根目录文件
2. 新增 `tests/contracts/test_scaffold_check.py`
   - 锁住当前 scaffold ledger 护栏基线
3. 更新 `tools/checks/README.md`
   - 说明 `check_scaffold.py` 已覆盖 legacy 根台账保留护栏
4. 更新迁移方案与三份主台账
   - 把第五消费点落地状态写回计划、进展与流水账

## 结果
- `check_scaffold.py` 已成为第五个真实消费点。
- 骨架门禁开始直接约束 legacy 阶段根台账文件是否仍在。
- 后续若有人在正式切换前提前移走根台账文件，会在 scaffold 阶段直接被拦住。

## 验证
- `python -m py_compile tools/checks/check_scaffold.py`
- `python -m unittest tests.contracts.test_scaffold_check -v`
- `python tools/checks/check_scaffold.py`
- `python tools/checks/check_structure.py`
- `python tools/checks/check_ledger_alignment.py`
- `python tools/checks/check_public_docs.py`

## 下一步
- 继续寻找第六个最小真实消费点。
- 优先挑一个尚未消费 manifest 的真实入口，不重复包裹已有结构、scaffold 与台账门禁。
