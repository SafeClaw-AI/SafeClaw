# trusted_plugins/

MVP 阶段的插件信任路径。

- 放在此目录下的插件，代表已被用户显式加入信任路径
- 完整性校验仍以 `blake3` 为准
- 更完整的来源认证（如签名 / trust_store）留到后续阶段
