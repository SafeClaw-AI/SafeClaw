# V4 dev-plan manifest 消费补点记录

## 目标
- 在不迁移文件的前提下，继续扩大 manifest 的真实消费面。
- 让 `tools/checks/check_public_docs.py` 把 `dev-plan` 也纳入实际读取。
- 让 `dev-plan` 与 `mvp-progress`、`push-log` 一起进入同一门禁口径。

## 本轮动作
1. `tools/checks/ledger_index_manifest.py`
   - 新增 `LedgerIndexManifest.resolve_existing_path(logical_id)`
   - 新增 `LedgerIndexManifest.read_resolved_text(logical_id)`
2. `tools/checks/check_public_docs.py`
   - 为 `dev-plan` 增加关键标记校验
   - 改为通过 manifest 辅助方法统一读取台账文本
3. `tests/contracts/test_ledger_index_manifest.py`
   - 新增 `dev-plan` 读取辅助的合同测试
4. `docs/30-方案/04-V4-repo-hygiene-migration-plan.md`
   - 修正文档中的当前状态描述
   - 把下一步建议更新为“第三消费点”

## 结果
- `check_public_docs.py` 已通过 manifest 实际消费三份主台账。
- 迁移方案文档与代码现状重新对齐。
- 后续新增消费点时，可直接复用 manifest helper，减少重复读取逻辑。

## 验证
- `python -m py_compile tools/checks/ledger_index_manifest.py tools/checks/check_public_docs.py`
- `python -m unittest tests.contracts.test_ledger_index_manifest -v`
- `python tools/checks/check_public_docs.py`

## 下一步
- 优先找第三个最小真实消费点继续接 manifest。
- 在第三消费点稳定前，不直接迁移三份主台账文件。
