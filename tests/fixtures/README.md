# tests/fixtures/

> 本文件是 `tests/fixtures/` 的 L2 夹具目录说明，用来解释测试夹具目录的公开边界。
> 当前稳定入口以 `README.md`、`STATUS.md`、`ARCHITECTURE.md`、`DECISIONS.md`、`CHANGELOG.md` 与 `docs/README.md` 为准。
> 协议与治理真源以 `VERSION`、`specs/`、`docs/reference/`、`docs/30-方案/02-V4-目录锁定清单.md` 与 `docs/30-方案/08-V4-ledger-index-manifest.json` 为准。

## 目录职责

- `tests/fixtures/` 只承接 simulation / chaos / replay 等测试夹具落点，不裁决协议字段。
- 夹具场景命名与内容边界由 `specs/`、`tests/contracts/` 与 `tests/README.md` 共同约束。
- 机器门禁仍由 `tools/checks/` 与 `python tools/checks/selfcheck.py` 统一收口。

## 使用边界

- 新增夹具时，优先服务合同测试、恢复链路验证与回归重放，不把目录说明写成实现承诺。
- 若未来补入场景数据，应先让 `specs/` 与 `tests/contracts/` 对齐，再将夹具作为验证材料落到本目录。
- `Contract tests` 会在 ledger policy chain 之后消费这些夹具与说明。
