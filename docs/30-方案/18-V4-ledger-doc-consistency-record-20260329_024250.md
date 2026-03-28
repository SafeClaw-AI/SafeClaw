# V4 ledger doc consistency 护栏记录

## 目标
- 把第六个真实消费点落到 `check_consistency.py`。
- 在真正迁移三份主台账前，先锁住机读 manifest 与文字方案映射不分叉。
- 让 cross-file consistency 门禁也开始显式消费 ledger manifest，而不是只校验 specs JSON 之间的关系。

## 本轮动作
1. 更新 `tools/checks/check_consistency.py`
   - 新增 `collect_ledger_manifest_doc_errors()`
   - 校验 `08-V4-ledger-index-manifest.json` 中每条映射都写入 `06-V4-ledger-compat-index-spec.md`
   - 校验 `legacy-only` 阶段的文字方案仍保留 Phase A 与“只读旧路径”说明
2. 新增 `tests/contracts/test_consistency_check.py`
   - 锁住当前 ledger 文档映射一致性基线
3. 更新 `tools/checks/README.md`
   - 说明 `check_consistency.py` 已覆盖 ledger 机读与文字方案映射不漂移
4. 更新迁移方案与三份主台账
   - 把第六消费点落地状态写回计划、进展与流水账

## 结果
- `check_consistency.py` 已成为第六个真实消费点。
- cross-file consistency 门禁开始直接约束 ledger 机读真源与文字方案是否分叉。
- 后续若有人只改 manifest 或只改文字方案，consistency 阶段会直接拦住。

## 验证
- `python -m py_compile tools/checks/check_consistency.py`
- `python -m unittest tests.contracts.test_consistency_check -v`
- `python tools/checks/check_consistency.py`
- `python tools/checks/check_structure.py`
- `python tools/checks/check_scaffold.py`
- `python tools/checks/check_ledger_alignment.py`
- `python tools/checks/check_public_docs.py`

## 下一步
- 继续寻找第七个最小真实消费点。
- 优先挑一个尚未消费 manifest 的真实入口，不重复包裹已有 consistency、structure、scaffold 与台账门禁。
