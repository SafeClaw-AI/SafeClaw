# V4 annassign return silent fallback gate record

- 时间：2026-03-30 06:50:58 +0800
- 轮次：M1b Slice 221
- 本轮动作：把 `tools/checks/check_reference_redlines.py` 里的 `_is_assignment_then_same_name_return_silent_fallback()` 再补一层，支持 `AnnAssign`，识别 `fallback: T = 空值; return fallback` 这类带类型标注的两步静默降级。
- 代码收口：现在 `except ...: fallback: object = None; return fallback`、`fallback: list[str] = []; return fallback` 会和普通 `fallback = 空值; return fallback` 一样，被视为 direct 静默降级并触发 fail-closed 门禁。
- 合同补齐：`tests/contracts/test_reference_redlines_check.py` 新增 `OSError -> fallback: object = None -> return fallback` 与 `TypeError -> fallback: list[str] = [] -> return fallback` 两条 direct fallback 必败合同。
- 基线结果：AST 定向扫描全仓带类型标注的“先赋空值再 return 同名变量”形态当前为 `NO_HITS`，本轮属于零旧债扩面；无需修平既有业务代码。
- 验证：`python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py`、`python -m unittest tests.contracts.test_reference_redlines_check -v`、`python tools/checks/check_reference_redlines.py`、`python tools/checks/check_ledger_alignment.py`、`git diff --check`
- 为什么这样做：如果只拦普通赋值的两步静默降级，开发者只需加一个类型注解就能绕过；趁零命中时把这层补上，长期更稳。
- 下一步：继续沿 `docs/reference/01` 主线盘 silent fallback 家族里最后的零命中语法绕行；若这一族基本收平，再切到另一条同级 fail-closed 红线。