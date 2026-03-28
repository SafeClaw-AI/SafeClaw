# V4 ledger version phase 护栏记录

## 目标
- 把第七个真实消费点落到 `check_versions.py`。
- 在真正迁移三份主台账前，先锁住 ledger manifest 的 `manifest_version` 与 `phase` 语义口径。
- 让 version consistency 门禁也开始显式消费 ledger manifest，而不是只校验仓库版本号与 specs 版本号。

## 本轮动作
1. 更新 `tools/checks/check_versions.py`
   - 新增 `collect_ledger_version_errors()`
   - 校验 `manifest_version` 必须是 x.y.z 语义版本
   - 校验所有台账仍为 `legacy-only` 时 `phase` 必须保持 `slice-a-baseline`
2. 新增 `tests/contracts/test_version_check.py`
   - 锁住当前 ledger version / phase 护栏基线
3. 更新 `tools/checks/README.md`
   - 说明 `check_versions.py` 已覆盖 ledger manifest_version / phase 口径不漂移
4. 更新迁移方案与三份主台账
   - 把第七消费点落地状态写回计划、进展与流水账

## 结果
- `check_versions.py` 已成为第七个真实消费点。
- version consistency 门禁开始直接约束 ledger manifest 的版本与阶段语义是否漂移。
- 后续若有人只改 cutover_state 却不更新 phase 口径，会在 versions 阶段直接被拦住。

## 验证
- `python -m py_compile tools/checks/check_versions.py`
- `python -m unittest tests.contracts.test_version_check -v`
- `python tools/checks/check_consistency.py`
- `python tools/checks/check_structure.py`
- `python tools/checks/check_scaffold.py`
- `python tools/checks/check_ledger_alignment.py`
- `python tools/checks/check_public_docs.py`
- 说明：`python tools/checks/check_versions.py` 仍被既有 `specs/spi/*` 占位 JSON 缺少 `version` 阻断，本轮未扩大修复。

## 下一步
- 继续寻找第八个最小真实消费点。
- 优先挑一个尚未消费 manifest 的真实入口，不重复包裹已有 versions、consistency、structure、scaffold 与台账门禁。
