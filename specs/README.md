# SafeClaw specs/ — 单一真源

> `specs/` 是当前公开仓库的协议真源。
> 合同测试、检查脚本、最小生成产物都从这里推导。

## 目录结构

```
specs/
  schemas/
    effect_ledger.json       # 副作用账本 + transitions
    action_tiers.json        # Tier × Reversibility 正交
    permission_scope.json    # 权限作用域 glob
    task_concurrency.json    # 并发模型 + 自动重试
    sidecar_lifecycle.json   # Sidecar 状态机
    memory_policy.json       # 记忆持久化策略
  state-machines/
    worker_lifecycle.json    # Worker 16 状态 + 29 事件
  error-codes/
    sys_errors.json          # 30 错误码
  config/
    preflight.json           # 预检阈值与降级
    heartbeat.json           # 心跳协议 0 token
  spi/
    base_fields.json         # 4 SPI 公共字段
    keystore/                # 密钥抽象层预留接口
    boot-integrity/          # 启动完整性抽象层预留接口
    storage-encryption/      # 存储加密抽象层预留接口
  manifests/
    README.md                # 非权威模板说明
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
