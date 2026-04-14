# specs/

> 本文件是 `specs/` 的 L0 目录说明，用来解释协议真源如何组织。
> 当前稳定入口以 `README.md`、`STATUS.md`、`ARCHITECTURE.md`、`DECISIONS.md`、`CHANGELOG.md` 与 `docs/README.md` 为准。
> 协议与治理真源以 `VERSION`、`specs/`、`docs/reference/`、`docs/30-方案/02-V4-目录锁定清单.md` 与 `docs/30-方案/08-V4-ledger-index-manifest.json` 为准。

## 真源职责

- `specs/` 负责冻结协议字段、状态机、错误码、配置 schema 与 SPI 边界。
- `state_id / event_id / tier_id / rev_id / error code` 属于稳定标识，测试与实现可直接引用。
- `generated/` 只接受 `specs/` 单向派生，不反向裁决 schema 与字段。
- `manifests/README.md` 与 `plugin_runner.template.jsonc` 只提供模板与落点说明，不冒充完整冻结 schema。

## 目录结构

```text
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

## 对齐链

```text
specs/
  -> tests/contracts/
  -> tools/checks/
  -> tools/lint/
  -> tools/codegen/
  -> generated/
```

`specs/` 变更必须先通过 ledger-first policy chain：`tools/checks/selfcheck.py` 与 `.github/workflows/contracts.yml` 会先跑 `ledger_index_manifest.py -> check_ledger_alignment.py -> check_consistency.py -> check_versions.py -> check_structure.py -> check_scaffold.py -> check_public_docs.py`，然后才进入 `Contract tests`。

## 派生产物边界

当前 `specs/` 会单向生成最小稳定索引：

- `generated/index.json`
- `generated/rust/manifest.json`
- `generated/rust/stable_ids.json`
- `generated/python/manifest.json`
- `generated/python/stable_ids.json`
- `generated/ts/manifest.json`
- `generated/ts/stable_ids.json`
