# 更新日志

## 2026-04-15

- 引入根级 SSOT 五件套：`README.md`、`STATUS.md`、`CHANGELOG.md`、`DECISIONS.md`、`ARCHITECTURE.md`
- 将 `README.md` 重写为稳定入口，把动态状态迁出到 `STATUS.md`
- 将 `docs/README.md` 收敛为导航器，并同步文档四层结构
- 同步 `docs/30-方案/02-V4-目录锁定清单.md` 与 `check_public_docs.py`，把新文档结构接入治理门禁
- 将 `开发计划.md`、`MVP_PROGRESS.md`、`PUSH_LOG.md` 的真内容迁入 `docs/records/`，并把根路径降级为兼容跳转入口
- 将 `docs/records/` 现行台账改写为 canonical 路径表述，并让 `check_public_docs.py` fail-closed 拦截旧根路径协作口径
- 将 `README.md` 改为只指向 `VERSION`，并让 `check_public_docs.py` fail-closed 拦截动态协议版本硬编码
- 将 `check_versions.py` 收回到 `VERSION` / specs / ledger manifest 的机读一致性校验，不再要求 README 回填版本字面值
- 为根级 SSOT 五件套增加职责分离 fail-closed 门禁，防止 README / STATUS / CHANGELOG / DECISIONS / ARCHITECTURE 串层
- 纠正 `docs/README.md` 对 `docs/records/` 的角色表述，并让 `check_public_docs.py` fail-closed 拦截“纯归档落点”旧口径
- 将 `README.md` 中“当前入口边界 / 当前稳定路径”措辞改写为稳定边界口径，并让 `check_public_docs.py` fail-closed 拦截旧动态表述
- 补齐 `README.md` 与 `docs/README.md` 对 `08-V4-ledger-index-manifest.json` 的真源摘要口径，并让 `check_public_docs.py` fail-closed 拦截旧漏项写法
- 补齐 `DECISIONS.md` 与 `ARCHITECTURE.md` 对 `08-V4-ledger-index-manifest.json` 的真源摘要口径，并让 `check_public_docs.py` fail-closed 拦截旧五件套摘要写法
- 将 `docs/V1_SCOPE.md` 从旧“公开真源总表”改写为“稳定入口 + L0 真源 + 门禁层”口径，并让 `check_public_docs.py` fail-closed 拦截旧摘要
- 将 `docs/DEVLOG.md` 从旧“公开层总表”改写为“稳定入口 + L0 真源 + 门禁链”口径，并让 `check_public_docs.py` fail-closed 拦截旧摘要
- 将 `docs/IMPLEMENTATION_STRATEGY.md` 从旧实现总表摘要改写为“稳定入口 + L0 真源 + 门禁链”口径，并让 `check_public_docs.py` fail-closed 拦截旧摘要
- 将 `docs/V1_TASK_TRIAGE.md` 从旧“specs + 门禁建设”摘要改写为“稳定入口 + L0 真源 + 门禁链”口径，并让 `check_public_docs.py` fail-closed 拦截旧摘要
- 将 `safeclaw-core/README.md` 改写为稳定 L2 模块入口，并让 `check_public_docs.py` fail-closed 拦截旧“Rust Core 最小脚手架”摘要口径
- 将 `specs/README.md` 改写为 L0 目录说明，并让 `check_public_docs.py` fail-closed 拦截旧动态分段口径
- 将 `specs/manifests/README.md` 改写为 L2 模板说明，并让 `check_public_docs.py` fail-closed 拦截私有蓝图/Phase 摘要口径
- 将 `tests/fixtures/README.md` 改写为 L2 夹具目录说明，并让 `check_public_docs.py` fail-closed 拦截旧占位摘要口径
- 新增 `tools/codegen/governance_index.py`，自动生成 `generated/governance/doc_index.json`、`spec_map.json`、`test_matrix.json` 与治理摘要 `README.md`
- 新增 `tools/checks/check_governance_indexes.py` 与 `tests/contracts/test_governance_indexes.py`，把结构化治理索引接入独立门禁与合同测试
- 将 Governance indexes 接入 `tools/codegen/regenerate_all.py`、`tools/checks/selfcheck.py` 与 `tests/contracts/test_selfcheck.py`，把结构化治理链前置到 public docs 对齐之前
- 将治理层级判定、spec/test 映射与实现候选收集改为结构化扫描，不再依赖文案 marker 与红线叙事
