# tools/lint/

这里放的是 **稳定命名约束检查**。

当前 `check_naming.py` 主要锁定：

- spec 文件与目录命名
- Worker `state_id / event_id`
- `tier_id / rev_id`
- `error code`
- `spi_name`
- effect action 名称

目标不是做风格偏好检查，
而是保护已经冻结的稳定标识不被随意改坏。
