# config/

本目录预留给 SafeClaw 运行时默认配置。

当前阶段仍是 `Phase 0`，因此这里只提供最小骨架，避免未来实现阶段再调整基础目录结构。

## 当前约束

- 协议层真源仍是 `specs/`
- 预检阈值以 `specs/config/preflight.json` 为准
- 动作分级与恢复能力以 `specs/schemas/action_tiers.json` 为准
- 插件信任 MVP 使用 `config/trusted_plugins/` 作为信任路径

## 说明

`default_config.toml` 与 `default_permissions.toml` 当前仅为占位文件，
用于明确后续实现的落点，不代表完整运行时语义已经冻结。
