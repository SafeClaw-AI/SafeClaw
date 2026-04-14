# 架构与流程决策记录

## 2026-04-15

决策：`README.md` 作为稳定入口，不再复述当前协议具体版本号，只指向根目录 `VERSION`。
原因：README 一旦写入 `3.2.0` 这类动态值，就会把稳定入口重新拉回“会过期的状态页”，与 SSOT 五件套和 README V14 的长期职责冲突。
影响：公开文档门禁新增对 README 动态版本硬编码的 fail-closed 护栏；`check_versions.py` 只保留 `VERSION` / specs / ledger manifest 的机读一致性校验；后续版本变更只改 `VERSION` 及其机读衍生物，不再要求同步手改 README 数字。

## 2026-04-15

决策：`docs/records/` 下的现行台账必须只使用 canonical 路径表述，不再把根目录 legacy 文件名写成当前协作入口。
原因：三份台账的真内容虽然已经迁入 `docs/records/`，但若现行台账内部仍继续用 `开发计划.md`、`MVP_PROGRESS.md`、`PUSH_LOG.md` 指挥协作，就会把兼容入口重新抬成“假真源”。
影响：`docs/records/开发计划.md`、`docs/records/MVP_PROGRESS.md` 统一改写为 `docs/records/...` 口径；`check_public_docs.py` 新增 stale root-path fail-closed 护栏，防止旧协作说法回流。

## 2026-04-15

决策：根级文档切换到 `README.md` / `STATUS.md` / `CHANGELOG.md` / `DECISIONS.md` / `ARCHITECTURE.md` 五件套分责结构。
原因：当前 README 同时承载定位、状态、历史与计划，已经构成“假真源”与过期风险；必须拆分职责，才能把 README 主线收回稳定入口。
影响：后续 README 不再写滚动进度；当前状态统一写入 `STATUS.md`，历史变更写入 `CHANGELOG.md`，关键理由写入 `DECISIONS.md`，系统结构写入 `ARCHITECTURE.md`。

## 2026-04-15

决策：协议与治理裁决层继续固定在 `specs/`、`VERSION`、`docs/reference/`、目录锁定清单与 `docs/30-方案/08-V4-ledger-index-manifest.json`，不由根级说明文档反向定义字段。
原因：SafeClaw 当前最危险的问题仍是真源漂移；如果把 README 或解释文档抬成协议真源，只会重新制造冲突口径。
影响：`README.md` 与 `docs/README.md` 负责导航和入口，`check_public_docs.py` 负责约束其职责边界，协议字段、治理阈值与 ledger 兼容索引仍由 L0 文件裁决。

## 2026-04-15

决策：`开发计划.md`、`MVP_PROGRESS.md`、`PUSH_LOG.md` 暂时保留为迁移期 legacy 文件，不在本轮直接删除。
原因：这些文件仍被目录锁定与现有公开文档合同引用，立即删除会扩大整改面并打断当前门禁基线。
影响：当前主线入口已转到五件套；legacy 文件后续按迁移计划进入 `docs/records/`，在此之前只保留审计价值，不再扩张为新的主线真源。

## 2026-04-15

决策：三份 legacy 台账真内容切到 `docs/records/`，根目录仅保留兼容跳转入口。
原因：README V14 主线已经建立稳定入口，如果继续把计划、进展、推送流水的真实内容留在根目录，会持续放大“假真源”和根目录过重的问题。
影响：manifest 当前进入 `target-primary + legacy-retired` 组合；`check_public_docs.py`、`chancellor_panel.py` 等消费点统一改为 manifest 驱动，后续更新只应写入 `docs/records/`。
