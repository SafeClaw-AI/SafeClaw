# 当前状态（滚动更新）

## 本周进度

- [x] README 主线已切换为根级 SSOT 五件套：`README.md` / `STATUS.md` / `CHANGELOG.md` / `DECISIONS.md` / `ARCHITECTURE.md`
- [x] `docs/README.md` 已改为导航器，不再承担裁决职责
- [x] `docs/30-方案/02-V4-目录锁定清单.md` 与公开文档门禁已同步到新文档结构
- [x] `python tools/checks/selfcheck.py` 已通过，本轮总验包含 930 项合同测试
- [ ] `specs/` → `tests/contracts/` → implementation 的 codegen 单向对齐链仍未落地

## 当前风险

- 结构性债务仍未清零，重点压力位仍在 `tools/checks/reference_redlines_static_eval.py` 与 `tools/checks/check_tooling_smoke.py`
- 根目录 legacy 文件 `开发计划.md`、`MVP_PROGRESS.md`、`PUSH_LOG.md` 仍处于迁移前保留状态，尚未完全归档到 `docs/records/`
- 当前稳定基线仍是 `local-only` MVP；provider / sidecar / `Tauri + React` GUI 还不能当成已交付能力

## 当前瓶颈

- `specs/`、`tests/contracts/`、Rust / Python 实现之间仍主要靠人工对齐，codegen 缺位会持续放大回归成本
- 公开文档与治理脚本已进入 fail-closed 模式，但 legacy 文档与历史叙事尚未彻底退出主线
- 全量门禁链成本较高，README / 文档治理推进必须优先守住规范，再做后续扩展

## 下周计划

- 继续把根目录 legacy 台账迁入 `docs/records/`，收紧主线入口
- 推进 `specs/` → `tests/contracts/` → implementation 的单向对齐与 codegen 落地
- 继续清偿 reference redlines 与 tooling smoke 的结构性债务
