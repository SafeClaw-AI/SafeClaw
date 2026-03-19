# SafeClaw manifests/ 预留目录

本目录用于放置插件与扩展的 manifest 模板。

当前阶段仍是 Phase 0，公开仓库只提供**非权威模板**，用于：

- 给 `Preflight Analyzer` 提供权限 / 预算 / IO schema 的输入形状参考
- 给未来 `tools/codegen/` 与合约测试预留稳定落点
- 避免在协议未冻结前，过早发布正式 manifest schema

当前约束来源：

- `specs/spi/base_fields.json`：统一 `spi_version` / `timeout_ms` / `capabilities`
- 私有蓝图中对 Plugin Runner 的最小要求：声明权限、IO schema、资源限制
- MVP 信任模型：`blake3` + `trusted_plugins/`

因此本目录内的模板**可复制、可扩展，但当前不视为冻结契约**。
