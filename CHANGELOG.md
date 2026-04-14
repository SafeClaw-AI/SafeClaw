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
