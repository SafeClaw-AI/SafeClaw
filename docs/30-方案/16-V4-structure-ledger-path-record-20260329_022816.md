# V4 structure ledger path 护栏记录

## 目标
- 把第四个真实消费点落到 `check_structure.py`。
- 在真正迁移三份主台账前，先锁住 `docs/records/` 不得提前落地。
- 让结构卫生门禁也开始显式消费 ledger manifest，而不是只在文档和台账检查器里消费。

## 本轮动作
1. 更新 `tools/checks/check_structure.py`
   - 新增 `collect_ledger_path_policy_errors()`
   - 校验 `legacy_path` 必须保持根文件
   - 校验 `target_path` 必须落在 `docs/records/`
   - 校验 `legacy-only` 阶段不得提前创建目标文件或 `docs/records/`
2. 新增 `tests/contracts/test_structure_check.py`
   - 锁住当前结构路径护栏基线
3. 更新 `tools/checks/README.md`
   - 说明 `check_structure.py` 已覆盖 ledger 目标路径提前落地护栏
4. 更新迁移方案与三份主台账
   - 把第四消费点落地状态写回计划、进展与流水账

## 结果
- `check_structure.py` 已成为第四个真实消费点。
- 结构门禁开始直接约束台账迁移目标路径，不再只检查 `specs/`。
- 后续若有人提前创建 `docs/records/`，会在结构阶段直接被拦住。

## 验证
- `python -m py_compile tools/checks/check_structure.py`
- `python -m unittest tests.contracts.test_structure_check -v`
- `python tools/checks/check_structure.py`
- `python tools/checks/check_ledger_alignment.py`
- `python tools/checks/check_public_docs.py`

## 下一步
- 继续寻找第五个最小真实消费点。
- 优先挑一个尚未消费 manifest 的真实入口，不重复包裹已有结构门禁与台账门禁。
