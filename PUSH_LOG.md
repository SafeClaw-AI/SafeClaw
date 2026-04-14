# 提交推送流水账（兼容入口）

当前推送流水真源已迁至 `docs/records/PUSH_LOG.md`。

当前根文件只保留兼容跳转说明，不再作为更新真源。

- `logical_id`: `push-log`
- `target_path`: `docs/records/PUSH_LOG.md`
- `write_mode`: `target-primary`
- `cutover_state`: `legacy-retired`

后续读取、检查与消费请统一走：

1. `docs/30-方案/08-V4-ledger-index-manifest.json`
2. `docs/records/PUSH_LOG.md`

如需继续推进 README V14 主线，请在 `docs/records/PUSH_LOG.md` 上更新，而不是回写本根文件。
