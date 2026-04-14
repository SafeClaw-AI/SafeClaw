# 架构与流程决策记录

## 2026-04-15

决策：根级文档切换到 `README.md` / `STATUS.md` / `CHANGELOG.md` / `DECISIONS.md` / `ARCHITECTURE.md` 五件套分责结构。
原因：当前 README 同时承载定位、状态、历史与计划，已经构成“假真源”与过期风险；必须拆分职责，才能把 README 主线收回稳定入口。
影响：后续 README 不再写滚动进度；当前状态统一写入 `STATUS.md`，历史变更写入 `CHANGELOG.md`，关键理由写入 `DECISIONS.md`，系统结构写入 `ARCHITECTURE.md`。

## 2026-04-15

决策：协议与治理裁决层继续固定在 `specs/`、`VERSION`、`docs/reference/` 与目录锁定清单，不由根级说明文档反向定义字段。
原因：SafeClaw 当前最危险的问题仍是真源漂移；如果把 README 或解释文档抬成协议真源，只会重新制造冲突口径。
影响：`README.md` 与 `docs/README.md` 负责导航和入口，`check_public_docs.py` 负责约束其职责边界，协议字段与治理阈值仍由 L0 文件裁决。

## 2026-04-15

决策：`开发计划.md`、`MVP_PROGRESS.md`、`PUSH_LOG.md` 暂时保留为迁移期 legacy 文件，不在本轮直接删除。
原因：这些文件仍被目录锁定与现有公开文档合同引用，立即删除会扩大整改面并打断当前门禁基线。
影响：当前主线入口已转到五件套；legacy 文件后续按迁移计划进入 `docs/records/`，在此之前只保留审计价值，不再扩张为新的主线真源。

## 2026-04-15

决策：三份 legacy 台账真内容切到 `docs/records/`，根目录仅保留兼容跳转入口。
原因：README V14 主线已经建立稳定入口，如果继续把计划、进展、推送流水的真实内容留在根目录，会持续放大“假真源”和根目录过重的问题。
影响：manifest 当前进入 `target-primary + legacy-retired` 组合；`check_public_docs.py`、`chancellor_panel.py` 等消费点统一改为 manifest 驱动，后续更新只应写入 `docs/records/`。
