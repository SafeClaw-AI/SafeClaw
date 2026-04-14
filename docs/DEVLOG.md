# SafeClaw 开发日志

> 当前稳定入口以 `README.md`、`STATUS.md`、`ARCHITECTURE.md`、`DECISIONS.md`、`CHANGELOG.md` 与 `docs/README.md` 为准。
> 协议与治理真源以 `VERSION`、`specs/`、`docs/reference/`、`docs/30-方案/02-V4-目录锁定清单.md` 与 `docs/30-方案/08-V4-ledger-index-manifest.json` 为准。
> 更早历史如有需要，可再基于 Git 提交记录补齐。

## 2026-03-29

### ledger-first policy chain 公开收口
- 补充 `docs/DEVLOG.md`，显式说明当前公开门禁顺序已收口为 `tools/checks/selfcheck.py` 与 `.github/workflows/contracts.yml` 先跑 `ledger_index_manifest.py`。
- 继续明确后续顺序为 `check_ledger_alignment.py`、`check_consistency.py`、`check_versions.py`、`check_structure.py`、`check_scaffold.py`、`check_public_docs.py`，然后才进入 `Contract tests`。
- 这样即使后续维护者先看开发日志，也能先看到现行 ledger-first policy chain，而不是回退到旧的宽泛测试叙述。

## 2026-03-20

### 工程推进原则冻结
- 新增 `docs/IMPLEMENTATION_STRATEGY.md`，明确后续实现默认采用“步步为营，层层推进”的节奏。
- 规定默认顺序为：先梳理边界，再立测试骨架，再做最小垂直切片，最后扩展到并发、恢复与外围集成。
- 明确禁止跳过梳理、跳过测试、绕过真源与门禁的捷径式实现。

### safeclaw-core 第一层骨架
- 新增 `safeclaw-core/ARCHITECTURE.md`，明确 Rust Core 当前文件树、模块边界与 spec 映射。
- 将 `safeclaw-core/src/` 拆出 `protocol`、`effect_ledger`、`worker_lifecycle`、`task_concurrency`、`spec_map` 五个最小模块。
- 新增 `safeclaw-core/tests/protocol_contracts.rs`，先锁版本锚点、核心状态、retry guard、reconcile 与 scope quarantine 的测试骨架。

### 协议层门禁补强
- 新增 `tools/lint/check_naming.py`，把稳定标识的命名规则收口为自动 lint。
- 将 naming lint 接入 `tools/checks/selfcheck.py` 与 `.github/workflows/contracts.yml`。
- 补强 `tests/contracts/`，新增协议不变量测试，覆盖 Worker 关键状态、三账本提交协议、Preflight 严格降级规则、错误码唯一性、SPI 注册表等。

### 公开文档对齐
- `README.md` 补齐英文摘要，并在联系方式中明确：公开问题更推荐在 GitHub Discussions / Issues 交流。
- 重写 `docs/V1_SCOPE.md` 与 `docs/V1_TASK_TRIAGE.md`，清理与当前协议层不一致的旧方向描述。
- 明确当前公开仓库的重点是 `Phase 0` 协议层冻结，而不是提前承诺尚未在 specs 中定义的产品功能。

## 2026-03-17

### 文档收口：V1 范围与定位
- 新增 `docs/V1_SCOPE.md` 与 `docs/V1_TASK_TRIAGE.md` 的最早版本，用于整理当时的方向性思考。
- 随着协议层与蓝图定稿，这批内容已被后续版本替换，不再作为当前公开真源。

### 文档修正：商标说明
- 调整 `README.md` 中的商标说明。
- 统一为当前文案：`SafeClaw™ is a trademark of Tian (田).`
