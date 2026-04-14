# V4 台账兼容索引方案

## 目的

- 本文件定义三份主台账在迁移完成后的兼容索引规则。
- 当前真源已切到 `docs/records/`，根目录只保留兼容跳转入口。
- 后续消费点必须优先走 manifest，不再硬编码根目录台账内容。

## 适用对象

- `开发计划.md`
- `MVP_PROGRESS.md`
- `PUSH_LOG.md`

## 当前状态

- 当前真实台账路径：
  - `docs/records/开发计划.md`
  - `docs/records/MVP_PROGRESS.md`
  - `docs/records/PUSH_LOG.md`
- 根目录同名文件仍存在，但只保留迁移说明，不再承担真实内容。
- 统一索引真源：`docs/30-方案/08-V4-ledger-index-manifest.json`

## 兼容索引规则

### 一、索引对象

每一份台账都应有以下信息：

- `logical_id`
- `legacy_path`
- `target_path`
- `read_order`
- `write_mode`
- `cutover_state`

### 二、逻辑标识

- `dev-plan`
- `mvp-progress`
- `push-log`

### 三、旧路径与目标路径映射

- `dev-plan`：`开发计划.md` -> `docs/records/开发计划.md`
- `mvp-progress`：`MVP_PROGRESS.md` -> `docs/records/MVP_PROGRESS.md`
- `push-log`：`PUSH_LOG.md` -> `docs/records/PUSH_LOG.md`

## 读取优先级

### Phase A：当前阶段

- 只读旧路径
- 新路径尚未创建
- 任何脚本不得假设新路径已存在

### Phase B：兼容阶段

- 优先读新路径
- 新路径不存在时回退读旧路径
- 若新旧路径同时存在且内容不一致，直接报错，不允许静默取其一

### Phase C：切换完成

- 只读新路径
- 旧路径只允许保留跳转说明或迁移标记，不再作为真实数据源

## 写入规则

### 当前规则

- 写入目标路径 `docs/records/`
- 根目录旧路径只保留兼容说明，不再写真实内容

### 切换状态定义

- `legacy-only`：仅旧路径存在
- `dual-readable`：新旧路径都可读，但以新路径优先
- `target-primary`：新路径为唯一真源
- `legacy-retired`：旧路径只剩跳转说明或已移除

## 当前执行结论

- 三份台账当前已处于 `target-primary + legacy-retired` 组合
- 机器读取统一以 `target_path` 为准
- 根目录入口仅为兼容层，不再作为裁决或更新目标

## 冲突处理规则

### 一、同时存在且内容不一致

- 立即失败
- 不允许自动合并
- 不允许静默覆盖

### 二、目标路径缺失

- 在 `legacy-only` 和 `dual-readable` 阶段允许回退旧路径
- 在 `target-primary` 阶段视为错误

### 三、索引缺项

- 缺少 `logical_id / legacy_path / target_path / cutover_state` 视为配置错误

## 下一步

1. 后续继续推进时，只更新 `docs/records/` 内的三份台账。
2. 等所有直接消费点与人工习惯都脱离根路径后，再评估是否移除根目录兼容入口。
3. `docs/round_logs/` 的迁移继续单独成刀，不与台账路径切换混做。
