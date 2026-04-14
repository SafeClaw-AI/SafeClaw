# 整体计划实现进展表（兼容入口）

当前进展台账真源已迁至 `docs/records/MVP_PROGRESS.md`。

当前根文件只保留兼容跳转说明，不再作为更新真源。

- `logical_id`: `mvp-progress`
- `target_path`: `docs/records/MVP_PROGRESS.md`
- `write_mode`: `target-primary`
- `cutover_state`: `legacy-retired`

后续读取、检查与消费请统一走：

1. `docs/30-方案/08-V4-ledger-index-manifest.json`
2. `docs/records/MVP_PROGRESS.md`

如需继续推进 README V14 主线，请在 `docs/records/MVP_PROGRESS.md` 上更新，而不是回写本根文件。
