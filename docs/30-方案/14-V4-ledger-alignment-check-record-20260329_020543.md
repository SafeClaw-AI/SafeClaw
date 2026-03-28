# V4 ledger alignment 独立检查器记录

## 目标
- 把台账校验从 `check_public_docs.py` 中抽离成独立检查器。
- 形成第三个 manifest 真实消费点，而不是继续把逻辑堆在单脚本里。
- 让 `selfcheck.py` 显式拥有台账对齐阶段，为后续迁移台账提供更稳定的门禁边界。

## 本轮动作
1. 新增 `tools/checks/check_ledger_alignment.py`
   - 统一承载台账索引基线校验
   - 统一承载三份主台账关键标记校验
   - 统一承载编码损坏护栏
2. 更新 `tools/checks/check_public_docs.py`
   - 改为复用 `collect_ledger_errors()`
   - 去掉脚本内重复的台账常量与读取逻辑
3. 更新 `tools/checks/selfcheck.py`
   - 新增 `Ledger alignment` 检查阶段
4. 更新 `tools/checks/README.md`
   - 把独立台账检查器纳入入口说明
5. 新增 `tests/contracts/test_ledger_alignment.py`
   - 锁住当前台账对齐基线通过状态

## 结果
- manifest 现在已有第三个独立真实消费点：`tools/checks/check_ledger_alignment.py`。
- `check_public_docs.py` 与台账校验逻辑完成解耦，后续继续扩点时更容易复用。
- `selfcheck.py` 的台账链路已形成：manifest 读取 -> ledger alignment -> public docs alignment。

## 验证
- `python -m py_compile tools/checks/check_ledger_alignment.py tools/checks/check_public_docs.py tools/checks/selfcheck.py`
- `python -m unittest tests.contracts.test_ledger_index_manifest tests.contracts.test_ledger_alignment -v`
- `python tools/checks/check_ledger_alignment.py`
- `python tools/checks/check_public_docs.py`

## 下一步
- 优先寻找第四个最小真实消费点继续接 manifest。
- 若继续走长期收益路线，优先考虑把某个非公开文档入口也接到独立 ledger checker，而不是直接迁移台账文件。
