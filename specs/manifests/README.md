# specs/manifests/

> 本文件是 `specs/manifests/` 的 L2 模板说明，用来解释 manifest 模板目录的公开边界。
> 当前稳定入口以 `README.md`、`STATUS.md`、`ARCHITECTURE.md`、`DECISIONS.md`、`CHANGELOG.md` 与 `docs/README.md` 为准。
> 协议与治理真源以 `VERSION`、`specs/`、`docs/reference/`、`docs/30-方案/02-V4-目录锁定清单.md` 与 `docs/30-方案/08-V4-ledger-index-manifest.json` 为准。

## 目录职责

- `plugin_runner.template.jsonc` 只是非权威模板，不裁决正式 manifest schema。
- 模板字段边界仍受 `specs/spi/base_fields.json` 与 `specs/README.md` 约束。
- `tests/contracts/`、`tools/checks/` 与 `tools/codegen/` 只把这里当作稳定落点，不把本目录说明反向当成协议真源。

## 使用边界

- 这里的模板用于给插件/扩展 manifest 预留输入形状与自动化落点。
- 正式 manifest 契约如需冻结，必须先回到 `specs/` 主真源与门禁链落地，再进入 `generated/` 等派生产物。
- 总验入口仍是 `python tools/checks/selfcheck.py`；公开门禁会在 `Contract tests` 之前先校验本目录边界。
