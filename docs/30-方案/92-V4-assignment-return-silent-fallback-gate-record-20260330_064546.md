# V4 assignment-return silent fallback gate record

- 时间：2026-03-30 06:45:46 +0800
- 轮次：M1b Slice 220
- 本轮动作：把 `tools/checks/check_reference_redlines.py` 的 direct silent fallback 再补一层，新增 `_is_assignment_then_same_name_return_silent_fallback()`，识别 `fallback = 空值; return fallback` 这类两步静默降级。
- 代码收口：现在 `except ...: fallback = None; return fallback`、`fallback = list(); return fallback` 会和直接 `return None/list()` 一样，被视为 direct 静默降级并触发 fail-closed 门禁。
- 合同补齐：`tests/contracts/test_reference_redlines_check.py` 新增 `OSError -> fallback=None -> return fallback` 与 `TypeError -> fallback=list() -> return fallback` 两条 direct fallback 必败合同。
- 基线结果：AST 定向扫描全仓“先赋空值再 return 同名变量”的 silent fallback 形态当前为 `NO_HITS`，本轮属于零旧债扩面；无需修平既有业务代码。
- 验证：`python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py`、`python -m unittest tests.contracts.test_reference_redlines_check -v`、`python tools/checks/check_reference_redlines.py`、`python tools/checks/check_ledger_alignment.py`、`git diff --check`
- 为什么这样做：如果门禁只拦最直白的 `return 空值`，轻微改写成“两步返回”就能绕过；趁当前零命中时补上这层，长期最省返工成本。
- 下一步：继续沿 `docs/reference/01` 主线盘 silent fallback 家族里最后的零命中绕行表达；若这一族基本收平，再切到另一条同级 fail-closed 红线。