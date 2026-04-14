# 当前状态（滚动更新）

## 本周进度

- [x] README 主线已切换为根级 SSOT 五件套：`README.md` / `STATUS.md` / `CHANGELOG.md` / `DECISIONS.md` / `ARCHITECTURE.md`
- [x] `docs/README.md` 已改为导航器，不再承担裁决职责
- [x] `docs/README.md` 已纠偏 `docs/records/` 角色口径，不再误写成纯归档落点
- [x] `README.md` 已去掉“当前入口边界 / 当前稳定路径”动态措辞，稳定入口口径与 SSOT 职责一致
- [x] `README.md` 与 `docs/README.md` 已补齐 `08-V4-ledger-index-manifest.json` 真源口径，避免真源摘要漏项
- [x] `DECISIONS.md` 与 `ARCHITECTURE.md` 已补齐 ledger manifest 真源口径，根级五件套真源摘要已收平
- [x] `docs/V1_SCOPE.md` 已改写为“稳定入口 + L0 真源 + 门禁层”口径，并接入 fail-closed 护栏
- [x] `docs/DEVLOG.md` 已改写为“稳定入口 + L0 真源 + 门禁链”口径，并接入 fail-closed 护栏
- [x] `docs/IMPLEMENTATION_STRATEGY.md` 已改写为“稳定入口 + L0 真源 + 门禁链”口径，并接入 fail-closed 护栏
- [x] `docs/V1_TASK_TRIAGE.md` 已改写为“稳定入口 + L0 真源 + 门禁链”口径，并接入 fail-closed 护栏
- [x] `safeclaw-core/README.md` 已改写为稳定 L2 模块入口，并接入 fail-closed 护栏
- [x] `specs/README.md` 已改写为 L0 目录说明，并接入 fail-closed 护栏
- [x] `specs/manifests/README.md` 已改写为 L2 模板说明，并接入 fail-closed 护栏
- [x] `tests/fixtures/README.md` 已改写为 L2 夹具目录说明，并接入 fail-closed 护栏
- [x] `docs/30-方案/02-V4-目录锁定清单.md` 与公开文档门禁已同步到新文档结构
- [x] 根级 SSOT 五件套职责分离已接入 `check_public_docs.py` fail-closed 门禁
- [x] `generated/governance/` 结构化治理索引已落地，`doc_index.json` / `spec_map.json` / `test_matrix.json` / `README.md` 已由 codegen 自动生成
- [x] `tools/checks/check_governance_indexes.py` 与 `tests/contracts/test_governance_indexes.py` 已接入治理门禁链，`selfcheck.py` 已前置执行结构化索引校验
- [x] `python tools/checks/selfcheck.py` 已通过，本轮总验包含 960 项合同测试
- [x] 三份 legacy 台账真内容已迁入 `docs/records/`，根目录只保留兼容跳转入口
- [x] `docs/records/` 现行台账已改写为 canonical 路径表述，`check_public_docs.py` 会 fail-closed 拦截旧根路径协作口径回流
- [x] `README.md` 已去掉动态协议版本硬编码，稳定入口只指向 `VERSION`，不再复述具体版本号
- [ ] `specs/` → `tests/contracts/` → implementation 的 codegen 单向对齐链仍未落地

## 当前风险

- 结构性债务仍未清零，重点压力位仍在 `tools/checks/reference_redlines_static_eval.py` 与 `tools/checks/check_tooling_smoke.py`
- 根目录 legacy 文件虽然已降为兼容跳转入口，但人工习惯与历史引用尚未彻底脱离根路径
- 当前稳定基线仍是 `local-only` MVP；provider / sidecar / `Tauri + React` GUI 还不能当成已交付能力

## 当前瓶颈

- `specs/`、`tests/contracts/`、Rust / Python 实现之间仍主要靠人工对齐，codegen 缺位会持续放大回归成本
- 公开文档与治理脚本已进入 fail-closed 模式，但 legacy 文档与历史叙事尚未彻底退出主线
- `generated/governance/` 已补上结构化地图，但实现侧对 `spec_map.json` 的消费仍停留在只读校验，尚未形成自动回写
- 全量门禁链成本较高，README / 文档治理推进必须优先守住规范，再做后续扩展

## 下周计划

- 继续收紧对根目录兼容跳转入口的依赖，避免新内容回写根路径
- 推进 `specs/` → `tests/contracts/` → implementation 的单向对齐与 codegen 落地
- 推进 `generated/governance/spec_map.json` 与实现层模板/测试模板之间的自动消费闭环
- 继续清偿 reference redlines 与 tooling smoke 的结构性债务
