# V4 公开文档门禁台账消费记录 2026-03-29 01:13:23 +0800

## 动作
- 将 	ools/checks/check_public_docs.py 从“直接硬编码根目录台账路径”改成“通过 load_ledger_index_manifest() 解析台账路径”。
- 在 	ools/checks/ledger_index_manifest.py 增加 esolve_existing_path()，让消费点可按 manifest 的 ead_order 找到当前可读路径。
- 在 	ests/contracts/test_ledger_index_manifest.py 增加最小合同测试，锁住 mvp-progress 的 legacy-only 解析行为。

## 结果
- check_public_docs.py 现在已经成为第一个真正消费台账 manifest 的脚本。
- 台账路径不再在这个脚本里散写为固定常量，后续迁移时只需改 manifest 与共享读取逻辑。
- 这为下一刀继续扩展到第二个消费点提供了可复用模式。

## 理由
- 先拿最小消费点开刀，风险最小，验证最快。
- 一旦这条链跑通，后续把更多脚本改成索引驱动就不再需要重复摸索。

## 下一步
- 下一刀优先选择第二个最小消费点继续接 manifest。
- 在真正迁移任何台账文件前，先让至少两个消费点都跑在索引驱动模式上。
