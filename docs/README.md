# docs/

SafeClaw 公开文档索引。

## 先说一句大实话

本轮已把治理门禁从双位数失败收敛到仅剩少量残项；`scaffold` 已恢复，剩余阻塞集中在公开文档对齐与结构性债务台账漂移。

**这不是"快完成了"，这是"骨架立起来了，脏腑还需要对齐"。**

当前 Phase 0 的核心价值是：协议层规范（`specs/`）已经完备，Rust 核心编译通过，个人生产位 MVP 可手跑。但规格-测试-实现三者之间仍有裂缝，当前主要剩在结构性债务台账与公开文档门禁，而不再是四阶段/探针/reconcile 这类确定性假失败。

以下文档将诚实地说明当前边界。

---

## 当前边界说明（2026-04-14 修订）

兼容旧门禁检索标题：当前边界说明（2026-04-04）

- **Chancellor 模式**：SafeClaw 当前不单独开发丞相模式/大都督模式等外部解释层功能。若后续需要接入，只做外部程序拼接融合，不在 SafeClaw 仓内继续扩写独立模式功能。下文出现的 `docs/chancellor-mode/v2/` 仅代表历史方案与后期拼接融合参考，不代表 SafeClaw 当前主线功能承诺。
- **四阶段协议**：合同测试夹具已完成第一轮对齐，`compensates_effect_id`、状态同步与 SQLite API 用法等确定性假失败已收掉；后续真正要补的是 specs → tests → implementation 的 codegen 单向溯源。
- **目录治理**：根目录 scratch 已转存到 `temp/parked-root/root-scratch-20260414/`，`scaffold` 已恢复；若未来要把这些路径升级为正式真源，再修改目录锁定清单，而不是把临时物料直接写进白名单。
- **治理检查**：`tools/chaos/chaos_monkey.py` 的 Python 解析错误已修复；当前治理残项不再卡在该脚本。
- **Rust 测试**：safeclaw-core 和 safeclaw-sqlite 目前零单元测试覆盖，全部验证依赖 Python 合同测试 + 手动 example 跑通。

---

## 当前文件

### 协议与规范
- `specs/` — 协议层规范（完全公开），包括：
  - [Worker 状态机](specs/state-machines/worker_lifecycle.json) — 任务生命周期（16 状态，v3.2）
  - [副作用账本](specs/schemas/effect_ledger.json) — 外部行为记录（含四阶段提交协议）
  - [动作分级](specs/schemas/action_tiers.json) — 操作风险分类
  - [错误码](specs/error-codes/sys_errors.json) — 结构化错误信息
  - [预检策略](specs/config/preflight.json) — 风险预判规则
  - [探针规范](specs/probes/) — file_write / file_delete / network_request 三类探针
  - [SPI 接口](specs/spi/) — 插件标准接口
- `tests/contracts/` — 合同测试（当前 926 通过 / 2 失败，剩余治理残项见下文）
- `tools/checks/` — 协议层门禁与总验收入口

### 开发文档
- `docs/DEVLOG.md` — 公开开发日志
- `docs/IMPLEMENTATION_STRATEGY.md` — 实现推进策略，明确"步步为营，层层推进"的默认节奏
- `docs/V1_SCOPE.md` — 当前公开范围说明
- `docs/V1_TASK_TRIAGE.md` — 当前任务分级说明
- `docs/reference/01-反屎山工程规范.md` — 治理阈值与红线真源
- `docs/reference/02-结构性债务台账.md` — 当前结构性债务白名单、核心业务路径与到期日台账
- `docs/reference/03-绕过白名单.md` — 当前允许保留的 `# noqa` / warning filter 等绕过登记表

### 方案文档
- `docs/30-方案/02-V4-目录锁定清单.md` — 当前目录锁定依据；根目录 scratch 本轮已转存到 `temp/parked-root/root-scratch-20260414/`
- `docs/30-方案/04-V4-repo-hygiene-migration-plan.md` — 仓库卫生整改的迁移真源
- `docs/30-方案/06-V4-ledger-compat-index-spec.md` — 台账兼容索引规则
- `docs/30-方案/08-V4-ledger-index-manifest.json` — 台账索引最小机读真源
- `docs/30-方案/20-V4-reference-compliance-rebaseline-record-20260329_030242.md` — 当前 reference 合规纠偏快照

### Chancellor 模式（历史参考，非当前主线）
- `docs/chancellor-mode/v2/` — 外部丞相模式历史方案，不属于 SafeClaw 当前开发范围
- `docs/chancellor-mode/v2/01-m1b-exit-and-m2-panel-entry.md` — 历史基线决议快照
- `docs/chancellor-mode/v2/02-m2-panel-command-truth-source.md` — 四命令字段快照
- `docs/chancellor-mode/v2/03-m2-product-value-rebaseline.md` — 历史改序快照

### 记录文档（历史）
- `docs/records/开发计划.md` — 开发计划（legacy）
- `docs/records/MVP_PROGRESS.md` — MVP 进度（legacy）
- `docs/records/PUSH_LOG.md` — 推送流水（legacy）

---

## 协议真源层级

涉及协议真源时，以以下顺序为准（从高到低）：

1. `specs/*.json` — 协议层规范（JSON Schema，架构冻结版 v3.2）
2. `VERSION` — 当前协议版本号（`3.2.0`）
3. `tests/contracts/*.py` — 合同测试（**⚠️ 仍需持续对齐规格**，当前主要剩治理残项）
4. `safeclaw-core/src/*.rs` — Rust 核心实现（编译通过，零测试覆盖）
5. `safeclaw-sqlite/src/*.rs` — SQLite 集成实现（编译通过，零测试覆盖）
6. `tools/mvp/safeclaw_mvp.py` — MVP Python 包装层
7. `README.md` — 项目介绍（可能存在与实际状态的偏差）

**目录结构是否允许调整，统一以 `docs/30-方案/02-V4-目录锁定清单.md` 为准（⚠️ 该文件当前已过期）。**

---

## selfcheck policy

`tools/checks/selfcheck.py` 按以下顺序执行：

1. `ledger_index_manifest.py` — 台账索引真源
2. `check_ledger_alignment.py` — 台账对齐检查
3. `check_consistency.py` — 跨文件一致性
4. `check_versions.py` — 版本一致性（当前 ✅ v3.2.0）
5. `check_structure.py` — 结构完整性（当前 ✅）
6. `check_scaffold.py` — 脚手架检查 ✅ 本轮已恢复
7. `check_public_docs.py` — 公开文档检查

合同测试 `tests/contracts/` 在门禁链之后执行（当前仅剩少量治理残项）。

---

## 当前真实状态（2026-04-14 评估）

### 已完成 ✅

| 能力 | 状态 | 说明 |
|------|------|------|
| 协议层 specs v3.2 | ✅ | effect_ledger、worker_lifecycle、task_concurrency 等核心规格已冻结 |
| Worker 生命周期状态机 | ✅ | 16 个状态，27 个转移事件，4 个终态 |
| 四阶段提交协议（规格层） | ✅ | prepared→dispatched→executed→committing，规格定义完整 |
| 探针机制（规格层） | ✅ | file_write / file_delete / network_request 三类探针 JSON 定义完整 |
| Effect Ledger Schema | ✅ | Rust 有 compensates_effect_id、幂等约束等字段 ⚠️ Python 测试不对齐 |
| Fencing Token 机制（规格层） | ✅ | doctor 特权绕过 scope 锁定，规格完整 |
| executed_assumed + scope_quarantine（规格层） | ✅ | probe_mode:none → 脏终态 + 隔离 |
| 合同测试框架 | ✅ | 本轮已把四阶段 / probe / reconcile 的确定性假失败收掉 |
| Rust safeclaw-core 编译 | ✅ | 编译通过，零测试覆盖 |
| Rust safeclaw-sqlite 编译 | ✅ | 编译通过，零测试覆盖 |
| Worker Loop Examples | ✅ | 30+ 个 worker_loop_* demo 覆盖各种场景 |
| 个人生产位 Python/Tkinter 面板 | ✅ | safeclaw_personal_panel.pyw 可部署 |
| MVP Python 包装层 | ✅ | safeclaw_mvp.py 支持 session/service/workspace 等动作 |
| Sandbox Executor | ⚠️ | 存在但未接入 worker_loop 主路径 |
| Ledger Alignment / Consistency / Version / Structure 检查 | ✅ | selfcheck 前 4 项全部通过 |
| Scaffold 根目录治理 | ✅ | 根目录 scratch 已转存，当前 scaffold 检查恢复通过 |
| Chaos Monkey | ✅ | Python 3.11 解析错误已修复 |

### 已失败 ❌（需修复）

| 问题 | 原因 | 影响 |
|------|------|------|
| 结构性债务台账漂移 | 多个 tracked 大文件与未跟踪合同文件超出当前台账快照 | reference governance / redlines 仍失败 |
| Rust 零测试覆盖 | safeclaw-core 和 safeclaw-sqlite 均无 #[cfg(test)] 模块 | 重构无安全网 |

### 规划中 📋

| 能力 | 前置条件 | 优先级 |
|------|----------|--------|
| Rust 单元测试（目标 80%+） | 先建立 codegen 从 specs 生成测试骨架 | 🔴 最高 |
| 规格→测试→实现的 codegen 机制 | 消除三者之间的"各写各的" | 🔴 最高 |
| 结构性债务台账重基线 | 先确认 tracked 大文件和新增合同文件是否纳入真源 | 🟠 高 |
| 公开文档门禁持续对齐 | docs/README.md 与 public docs marker 保持同源 | 🟠 高 |
| 幂等约束实现 | 在 Rust store + Python 测试中同步落地规格 invariant | 🟠 高 |
| 状态转换自动同步 | effect_store.rs 的 insert_transition 应同步更新 status | 🟠 高 |
| AI Provider 接入 | 从 local-only 到 openai-compatible / Claude CLI | 🟡 中 |
| Tauri/React GUI | MVP GUI 化，从命令行到图形界面 | 🟡 中 |
| Docker 沙箱主路径接入 | sandbox_executor.rs 接入 worker_loop | 🟡 中 |
| Rust-first CLI | 从 Python wrapper 到 Rust native CLI | 🟡 中 |
| 多 worker 并行调度 | 从单 worker 到 worker_pool | 🟡 中 |
| CI/CD 流水线 | build → contract tests → smoke → coverage | 🟡 中 |
| Chaos / Benchmark harness | 稳定性基线 + A/B 测试 | 🟢 低 |

---

## 实现推进策略

遵循"步步为营，层层推进"的默认节奏：

1. **先止血**：继续收完公开文档门禁与结构性债务台账残项
2. **再对齐**：改造合同测试为 codegen 驱动，消除规格↔测试↔实现的裂缝
3. **后覆盖**：建立 Rust 单元测试体系，达到 80%+ 覆盖率
4. **再扩展**：AI Provider 接入 → GUI → Docker → 多 worker

---

## 为什么先公开协议层

因为**规矩比功能重要**。能力可以慢慢加，但底线必须一开始就定死。

但有一个诚实的前提：协议层规范（`specs/*.json`）目前是最接近"真源"的文件。合同测试应该从规格生成，而不是反过来手写期望。当前 11 个失败的测试恰好说明了这个问题。

---

<sub>SafeClaw™ is a trademark of Tian (田).</sub>
