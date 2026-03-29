# tools/checks/

这里放的是 **协议层门禁脚本**。

## 当前入口

- `spec_index.py`：加载 `specs/` 索引
- `check_ledger_alignment.py`：台账索引与三份主台账内容对齐检查
- `check_consistency.py`：跨文件一致性检查，并锁机读 ledger manifest 与文字方案映射不漂移
- `check_versions.py`：版本一致性检查，并锁 ledger manifest_version / phase 口径不漂移
- `check_structure.py`：结构完整性检查，并约束 ledger 目标路径不得提前落地
- `check_public_docs.py`：公开文档对齐检查
- `check_scaffold.py`：仓库骨架检查，并把 `docs/reference/` + `docs/30-方案/02-V4-目录锁定清单.md` 落成 fail-closed 根目录/命名护栏；legacy 阶段根台账文件仍须保留
- `check_reference_redlines.py`：把 `docs/reference/01` 中已机器化的红线直接落成代码门禁；当前先拦无主 TODO、空异常处理、多异常 `except` 必须绑定并真正使用 `as error`、`OSError` / `json.JSONDecodeError` / `FileExistsError` / `KeyError` 必须绑定并保留上下文，以及高风险 `OSError/json.JSONDecodeError` 不能直接静默降级为 `None/False`
- `check_tooling_smoke.py`：工具烟测
- `check_mvp_operator_flow.py`: practical MVP operator flow check covering `doctor / service-run / report / service-retry / service-recover`
- `check_examples_smoke.py`：高层示例烟测，并要求覆盖 `safeclaw-sqlite/examples/*.rs` 全量示例
- `check_generated_sync.py`：生成产物同步检查
- `selfcheck.py`：串起全部门禁的统一入口

## 迁移期优先链路

- `selfcheck.py` 当前会先跑 `ledger_index_manifest.py`
- 然后依次跑 `check_ledger_alignment.py`、`check_consistency.py`、`check_versions.py`、`check_structure.py`、`check_scaffold.py`、`check_public_docs.py`
- 其中 `check_scaffold.py` 会直接把 `docs/reference/` 与 `docs/30-方案/02-V4-目录锁定清单.md` 转成 fail-closed 校验，并拦截 `最终版`、`临时版`、`new2`、`test1` 这类禁词路径
- 这条 ledger policy chain 之后，会继续跑 `check_reference_redlines.py`，把无主 TODO、空异常处理、异常上下文绑定/使用、`OSError` / `json.JSONDecodeError` / `FileExistsError` / `KeyError` 上下文保留，以及高风险 I/O/JSON 静默降级挡在 `Naming lint` 和 `Contract tests` 之前
- 这条 ledger policy chain 会显式前置在 `Contract tests` 之前，避免历史失败提前遮住迁移护栏

## 推荐顺序

- 先运行 `python tools/codegen/regenerate_all.py`
- 再运行 `python tools/checks/selfcheck.py`

当前目标不是覆盖一切，
而是优先锁死最容易在自动化开发中漂移的地方。
