# V4 仓库卫生迁移方案

## 目的

- 本文件定义仓库卫生整改的迁移路线。
- 目标不是一次性大搬家，而是按可验证、可回滚、可自动化的顺序推进。
- 当前台账迁移已完成首个主目标：三份根级台账真源已切到 `docs/records/`。

## 当前状态

### 已完成

- 已建立 manifest 驱动索引：`docs/30-方案/08-V4-ledger-index-manifest.json`
- 已创建 `docs/records/`
- 已迁移三份台账真内容：
  - `docs/records/开发计划.md`
  - `docs/records/MVP_PROGRESS.md`
  - `docs/records/PUSH_LOG.md`
- 根目录旧路径已收敛为兼容跳转入口

### 未完成

- `docs/round_logs/` 仍未迁出
- 根目录兼容入口尚未彻底退休
- 仍需继续把历史人工习惯从根路径切走

## 适用范围

- 根目录台账：`MVP_PROGRESS.md`、`PUSH_LOG.md`、`开发计划.md`
- 历史留痕目录：`docs/round_logs/`
- 公开文档门禁：`tools/checks/check_public_docs.py`
- 文档索引与结构约束：`docs/README.md`、`docs/30-方案/02-V4-目录锁定清单.md`

## 迁移目标

### 目标一：文档与日志分层

- 正式说明文档继续留在 `docs/`
- 台账真内容统一落在 `docs/records/`
- 历史轮次日志后续迁到独立日志区

### 目标二：根目录减负

- 根目录只保留入口、配置与必要兼容文件
- legacy 台账不再在根目录承载真实内容

### 目标三：自动化平滑切换

- 所有消费点优先走 manifest
- 迁移过程由门禁 fail-closed 守护
- 每次切换都有明确回滚点

## 当前落点

### 正式文档

- `docs/`

### 台账真源

- `docs/records/开发计划.md`
- `docs/records/MVP_PROGRESS.md`
- `docs/records/PUSH_LOG.md`

### 结构与迁移真源

- `docs/30-方案/`

### 规划中的日志落点

- `logs/rounds/`

## 剩余迁移策略

### Phase 1：台账读取切换

- 已完成：manifest 读取切到 `docs/records/`
- 已完成：根目录台账收为兼容跳转

### Phase 2：消费点去根路径化

- 持续把脚本、文档、人工操作默认口径切到 `docs/records/`
- 根目录文件仅保留兼容价值，不再写真实内容

### Phase 3：迁移历史轮次日志

- 将 `docs/round_logs/` 整体迁入 `logs/rounds/`
- 修复 `PUSH_LOG.md` 与相关历史引用
- 完成后关闭 `docs/round_logs/` 的活跃角色

### Phase 4：收尾清理

- 评估是否移除根目录兼容入口
- 更新目录锁定清单，去掉临时保留口径
- 用自动化门禁锁住新结构

## 风险与控制

### 风险一：新旧路径混写

- 控制：manifest 已切到 `target-primary`
- 控制：根目录旧路径只保留跳转说明

### 风险二：消费点仍偷读根路径

- 控制：逐步改为 manifest 驱动
- 控制：继续用合同与门禁锁住入口

### 风险三：日志迁移与台账迁移混做

- 控制：`docs/round_logs/` 继续单独成刀

## 验收标准

- `docs/records/` 内三份台账可被机器读取
- 根目录三份旧文件不再承载真实内容
- manifest、公开文档与检查脚本对齐
- `selfcheck.py` 持续通过
- 后续不再把新的真实台账内容写回根目录

## 下一步建议

1. 继续推进 `docs/round_logs/` 独立迁移。
2. 继续收紧对根目录兼容入口的依赖。
3. 当所有消费点脱离根路径后，再决定是否移除根级兼容文件。
