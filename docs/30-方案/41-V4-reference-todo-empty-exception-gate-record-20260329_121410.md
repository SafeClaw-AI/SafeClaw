# V4 reference TODO / empty exception gate 记录

## 时间
- `2026-03-29 12:14:10 +0800`

## 本轮动作
- 新增 `tools/checks/check_reference_redlines.py`，把 `docs/reference/01-反屎山AI研发执行总纲（Codex专用浓缩对照版）.md` 里最值得机器化的两组红线直接落成代码门禁。
- 第一组红线：无主 TODO。当前先对 `tools/`、`tests/`、`safeclaw-core/`、`safeclaw-sqlite/`、`modules/` 与根执行脚本扫描 `TODO` 注记，要求同一行同时带 `owner / due / req`。
- 第二组红线：空异常处理。当前先拦 `except ...: pass` / `except ...: ...` 以及 PowerShell 空 `catch {}` / 只含注释的 `catch`。
- 修平现有基线里的空异常处理旧债：`tools/checks/mvp_state_guard.py` 不再使用 `except ...: pass`。
- 把新门禁接进 `tools/checks/selfcheck.py` 与 `.github/workflows/contracts.yml`，确保默认自检与 CI 都会执行。
- 补上 `tests/contracts/test_reference_redlines_check.py`、调整 `tests/contracts/test_selfcheck.py` 与 `tests/contracts/test_contracts_workflow.py`，锁住规则与顺序。
- 同步更新 `tools/checks/README.md`、`tools/README.md`、`tools/checks/check_public_docs.py`，避免入口说明回退成“还靠人工提醒”。

## 为什么做这刀
- 上一轮只是把 `docs/reference/` 变成“目录/命名/根布局”的硬门禁，但《总纲》里的代码红线还没有真正落地。
- `无主 TODO` 与 `空异常处理` 是最容易在自动化开发里悄悄堆积、又最适合先做成 fail-closed 的两条红线。
- 先把这两条落成硬门禁，后续所有新增程序都会自动继承，不需要每轮再人工口头提醒。

## 结果
1. `tools/checks/check_reference_redlines.py`
   - 新增 TODO 元数据校验
   - 新增 Python / PowerShell 空异常处理校验
   - 提供 `collect_errors()` 给自检与合同测试复用
2. `tools/checks/mvp_state_guard.py`
   - 去掉三处 `except ...: pass`
   - 改为保留上下文或显式输出释放失败信息
3. `tools/checks/selfcheck.py` 与 `.github/workflows/contracts.yml`
   - 新增 `Reference redlines` / `Run reference redline check`
   - 放在 `Public docs alignment` 之后、`Naming lint` 之前
4. `tests/contracts/test_reference_redlines_check.py`
   - 锁住 TODO 元数据格式
   - 锁住 Python / PowerShell 空异常处理判定
   - 锁住当前仓库基线必须通过

## 最小验证
- `python -m py_compile tools/checks/check_reference_redlines.py tools/checks/selfcheck.py tools/checks/check_public_docs.py tools/checks/mvp_state_guard.py tests/contracts/test_reference_redlines_check.py tests/contracts/test_selfcheck.py tests/contracts/test_contracts_workflow.py`
- `python -m unittest tests.contracts.test_reference_redlines_check tests.contracts.test_selfcheck tests.contracts.test_contracts_workflow tests.contracts.test_public_docs_check -v`
- `python tools/checks/check_reference_redlines.py`
- `python tools/checks/check_public_docs.py`
- `python tools/checks/selfcheck.py`：已尝试，当前仍被既有 `specs/spi/*` 占位 JSON 缺少 `version` 的历史问题阻断在 `check_versions.py`，本轮未扩大修复

## 下一步
- 继续扩大 `docs/reference/01` 的硬门禁覆盖，优先候选是：
  - 把“异常必须带上下文、禁止无上下文降级”继续机器化
  - 或把“单函数 / 单类体量红线”转成可执行检查
- 继续坚持：先补合同、再落实现、最后接入主链，不做口头规范伪落地。
