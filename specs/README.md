# SafeClaw specs/ — 单一真源

> Phase 0 产物。所有代码/文档/测试从此生成。

## 目录结构

```
specs/
  schemas/
    effect_ledger.json     # 副作用账本 schema
    action_tiers.json      # Tier × Reversibility 正交定义
  state-machines/
    worker_lifecycle.json  # Worker 16 状态 + 29 事件转移
  error-codes/
    sys_errors.json        # 30 个错误码(人类可读+机器可识别)
  config/
    preflight.json         # 预检阈值与降级策略
  spi/
    base_fields.json       # 4 SPI 公共字段
  manifests/               # 插件 manifest 模板(M3)
```

## 规则

1. **Phase 0 只搓 Schema,不写业务代码。**
2. 所有 state_id / event_id / tier_id / rev_id / error code 一旦发布即为稳定标识,测试直接引用。
3. 公开仓库中的协议真源以 `specs/` 为准；内部设计文档另行维护。
4. specs/ 变更必须同时更新合同测试(`tests/contracts/`)。

## Codegen 流水线(M1 启用)

```
specs/ → tools/codegen/ → generated/{rust,python,ts} + tests/contracts/
```
