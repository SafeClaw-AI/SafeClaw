# SafeClaw 当前任务分级

> 本文件已替代早期偏产品功能导向的 V1 任务清单。
> 当前分级以最新 `specs/` 与协议层门禁建设为主。

## P0

必须优先完成，决定当前公开协议层是否可信：

- `specs/` 关键契约保持一致
- 合同测试覆盖继续补强
- 一致性 / 版本 / 结构 / 命名门禁持续收紧
- CI 门禁稳定运行
- 公开 README 与 `docs/` 不再出现历史漂移
- codegen / schema diff / manifests 入口保持可用

## P1

可以在不改变核心协议语义的前提下继续推进：

- `generated/` 占位目录与说明文档
- `tests/fixtures/` 占位目录与后续 simulation 说明
- 更强的只读检查工具与开发者脚本
- 从既有 specs 自动推出更多测试骨架
- 对公开文档做中英同步与索引整理

## Frozen

在当前公开仓库中，不应被自动当作已承诺功能：

- 新增核心协议字段 / 状态 / 错误码 / SPI 字段
- 修改权限模型或安全策略语义
- 修改不可逆操作规则
- 把私有架构推导文档直接公开
- 在没有最新 specs 支撑时承诺完整产品功能

## 说明

如果某项内容无法从当前 `specs/`、命名规则、版本规则或最新 README 中稳定推断，
就不应直接写进公开计划，而应等待新的权威文档先定稿。

## 当前 selfcheck policy

- `tools/checks/selfcheck.py` 与 `.github/workflows/contracts.yml` 会先跑 `ledger_index_manifest.py`
- 然后依次跑 `check_ledger_alignment.py`、`check_consistency.py`、`check_versions.py`、`check_structure.py`、`check_scaffold.py`、`check_public_docs.py`
- `Contract tests` 与其他后续门禁会显式后置在这条 ledger policy chain 之后
