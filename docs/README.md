# docs/

`docs/README.md` 只负责导航，不负责裁决。

协议与治理真源仍以 `specs/`、`VERSION`、`docs/reference/` 与 `docs/30-方案/02-V4-目录锁定清单.md` 为准；当前机器验收结果请直接看 `STATUS.md` 或运行 `selfcheck.py`。

## 根级 SSOT 五件套

| 文件 | 角色 | 使用规则 |
| --- | --- | --- |
| `README.md` | 稳定入口 | 只说明项目定位、边界、入口与真源链接 |
| `STATUS.md` | 当前状态 | 只记录滚动状态、风险、瓶颈与近期待办 |
| `CHANGELOG.md` | 历史记录 | 只记录已经发生的变更，不覆盖旧记录 |
| `DECISIONS.md` | 决策记录 | 只记录关键决策、原因与影响 |
| `ARCHITECTURE.md` | 架构真源 | 只说明系统结构、依赖关系、不变量与设计原则 |

## 文档四层

| 层级 | 角色 | 当前落点 | 使用规则 |
| --- | --- | --- | --- |
| L0 | 唯一可信真源 | `specs/` 下 JSON、`VERSION`、`docs/reference/01-反屎山工程规范.md`、`docs/reference/02-结构性债务台账.md`、`docs/reference/03-绕过白名单.md`、`docs/30-方案/02-V4-目录锁定清单.md`、`docs/30-方案/08-V4-ledger-index-manifest.json` | 只在这里定义规格、阈值、目录边界、结构债与绕过登记 |
| L1 | 由真源派生的机读产物 | `generated/index.json`、`generated/root_index.json`、`generated/targets.json`、`generated/rust/manifest.json`、`generated/python/manifest.json`、`generated/ts/manifest.json`、各目标 `stable_ids.json` | 只能从真源生成，不得反向改写 L0 |
| L2 | 给人看的稳定说明 | `README.md`、`ARCHITECTURE.md`、`docs/README.md`、`docs/DEVLOG.md`、`docs/V1_SCOPE.md`、`docs/V1_TASK_TRIAGE.md`、`docs/IMPLEMENTATION_STRATEGY.md`、`safeclaw-core/ARCHITECTURE.md` | 解释现状、给出入口、链接真源，不裁决协议字段 |
| L3 | 状态与历史记录 | `STATUS.md`、`CHANGELOG.md`、`DECISIONS.md`、`docs/records/`、`docs/chancellor-mode/v2/`、`docs/30-方案/20-V4-reference-compliance-rebaseline-record-20260329_030242.md`、`docs/round_logs/` | 保留操作状态、历史切片与审计轨迹，不反向定义当前规格 |

## L0 真源导航

| 主题 | 真源文件 | 说明 |
| --- | --- | --- |
| 协议规格 | `specs/` | 规格本体；重点包括 worker lifecycle、effect ledger、action tiers、preflight、probe、SPI |
| 版本边界 | `VERSION` | 对外协议版本号 |
| 治理阈值 | `docs/reference/01-反屎山工程规范.md` | 复杂度、规模与红线约束 |
| 结构债台账 | `docs/reference/02-结构性债务台账.md` | 结构性债务白名单、核心业务路径、到期日 |
| 绕过登记 | `docs/reference/03-绕过白名单.md` | `# noqa`、warning filter 等显式绕过登记 |
| 目录边界 | `docs/30-方案/02-V4-目录锁定清单.md` | 当前仓库的目录锁定依据 |
| 台账索引 | `docs/30-方案/08-V4-ledger-index-manifest.json` | 机读兼容索引真源 |

## 公开入口

| 文档 | 作用 | 备注 |
| --- | --- | --- |
| `README.md` | 对外唯一稳定入口 | 介绍项目、说明边界、链接真源 |
| `STATUS.md` | 当前状态 | 记录本周进度、风险、瓶颈与下周计划 |
| `ARCHITECTURE.md` | 高层架构 | 描述系统边界、依赖关系与不变量 |
| `DECISIONS.md` | 决策审计 | 解释为什么这么做 |
| `CHANGELOG.md` | 历史变更 | 按日期追加，不回写当前状态 |
| `safeclaw-core/ARCHITECTURE.md` | Rust 子系统解释 | 实现侧说明，不替代 `specs/` |

## 历史与治理记录

这些文件需要保留，但不应该再冒充主线真源：

- `docs/records/`：旧 `开发计划.md`、`MVP_PROGRESS.md`、`PUSH_LOG.md` 的归档落点
- `docs/chancellor-mode/v2/`：历史外部模式方案与产品叙事材料
- `docs/30-方案/04-V4-repo-hygiene-migration-plan.md`：仓库卫生迁移计划，属于治理方案，不是协议真源
- `docs/30-方案/06-V4-ledger-compat-index-spec.md`：台账兼容索引设计说明，不替代 `08-V4-ledger-index-manifest.json`
- `docs/30-方案/20-V4-reference-compliance-rebaseline-record-20260329_030242.md`：阶段性纠偏记录，保留审计轨迹

## 验真入口

当前公开门禁链仍以 `selfcheck.py` 为总入口，顺序如下：

1. `ledger_index_manifest.py`
2. `check_ledger_alignment.py`
3. `check_consistency.py`
4. `check_versions.py`
5. `check_structure.py`
6. `check_scaffold.py`
7. `check_public_docs.py`
8. `check_reference_redlines.py`
9. `tests/contracts/`

## 建议读取顺序

1. 先看 `README.md`，理解项目定位、入口与稳定边界。
2. 再看 `STATUS.md`，确认当前状态与风险。
3. 接着看 `ARCHITECTURE.md` 与 `safeclaw-core/ARCHITECTURE.md`，建立架构视图。
4. 然后看 `specs/` 与 `docs/reference/`，确认协议与治理真源。
5. 最后再看 `CHANGELOG.md`、`DECISIONS.md`、`docs/records/` 与 `docs/chancellor-mode/v2/`，补历史背景与审计轨迹。

<sub>SafeClaw™ is a trademark of Tian (田).</sub>
