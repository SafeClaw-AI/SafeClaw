# V4 台账索引读取入口记录 2026-03-29 01:03:25 +0800

## 动作
- 新建 	ools/checks/ledger_index_manifest.py，实现台账索引 manifest 的最小读取入口。
- 新建 	ests/contracts/test_ledger_index_manifest.py，锁住三份台账逻辑标识、路径映射和冲突策略基线。
- 更新 	ools/checks/check_public_docs.py，让公开文档门禁真正读取 manifest 并校验三份台账的基线映射。

## 结果
- 后续脚本现在有稳定入口读取 docs/30-方案/08-V4-ledger-index-manifest.json。
- 三份主台账的基线读取规则已被合同测试与公开文档门禁同时锁住。
- 这让下一刀可以直接把其他脚本逐步改成“先读 manifest，再找台账”。

## 理由
- 先做读取入口，短期更慢，但能避免未来每个脚本各自解析 manifest、各自发明规则。
- 这样后续迁移 开发计划.md 时，只需改 manifest 和读取逻辑，不必再全仓散改路径常量。

## 下一步
- 下一刀优先把另一个最小脚本改成“索引驱动读取”，建议从 check_public_docs.py 之外的消费点继续扩展。
- 未完成首个索引驱动读取闭环前，不直接迁移三份主台账。
