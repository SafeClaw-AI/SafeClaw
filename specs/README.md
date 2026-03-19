# SafeClaw specs/ — 单一真源

> `specs/` 是当前公开仓库的协议真源。
> 合同测试、检查脚本、最小生成产物都从这里推导。

## 目录结构

```
specs/
  schemas/
    effect_ledger.json     # 副作用账本 schema
    action_tiers.json      # Tier × Reversibility 正交定义
  state-machines/
    worker_lifecycle.json  # Worker 16 状态 + 29 事件转移
  error-codes/
    sys_errors.json        # 系统错误码注册表
  config/
    preflight.json         # 预检阈值与降级策略
  spi/
    base_fields.json       # 4 个 SPI 公共字段
  manifests/
    README.md              # 非权威模板说明
    plugin_runner.template.jsonc
```

## 当前规则

1. `specs/` 是当前公开仓库中的协议真源。
2. `state_id / event_id / tier_id / rev_id / error code` 属于稳定标识，测试可直接引用。
3. `specs/` 变更必须同步通过合同测试与所有门禁检查。
4. `manifests/` 当前是 **Phase 0 非权威模板**，用于预留自动化落点，不代表完整冻结 schema。

## 当前闭环

```text
specs/
  -> tests/contracts/
  -> tools/checks/
  -> tools/lint/
  -> tools/codegen/
  -> generated/
```

## 当前 codegen 产物

当前已经可以从 `specs/` 生成最小稳定索引：

- `generated/index.json`
- `generated/rust/manifest.json`
- `generated/rust/stable_ids.json`
- `generated/python/manifest.json`
- `generated/python/stable_ids.json`
- `generated/ts/manifest.json`
- `generated/ts/stable_ids.json`
