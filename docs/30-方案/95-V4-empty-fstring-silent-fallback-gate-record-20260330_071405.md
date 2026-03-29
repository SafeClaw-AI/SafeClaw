# V4 empty fstring silent fallback gate record

- 时间：2026-03-30 07:14:05 +0800
- 轮次：M1b Slice 223
- 本轮动作：调整 `tools/checks/check_reference_redlines.py` 的 direct silent fallback 识别逻辑，把空 `f-string` 语法别名也纳入真源，识别 `return f""` 这类空字符串降级。
- 代码收口：现在 `except ValueError: return f""` 与 `except TypeError: fallback = f""; return fallback` 会和普通空字符串字面量一样，被视为 direct 静默降级并触发 fail-closed 门禁。
- 合同补齐：`tests/contracts/test_reference_redlines_check.py` 同步补齐 1 条 helper 稳定性合同，以及 2 条 direct / assignment 空 `f-string` 必败合同。
- 基线结果：AST 定向扫描全仓 direct 与两步 `f""` 静默降级形态当前为 `NO_HITS`，本轮属于零旧债扩面；无需修平既有业务代码。
- 验证：`python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py`、`python -m unittest tests.contracts.test_reference_redlines_check -v`、`python tools/checks/check_reference_redlines.py`、`python tools/checks/check_ledger_alignment.py`、`git diff --check`
- 为什么这样做：如果 direct silent fallback 只拦普通空字符串字面量，不拦空 `f-string`，开发者仍可只换一层语法糖就继续吞掉异常上下文；趁全仓零命中时补齐这一层，长期更稳。
- 下一步：继续沿 `docs/reference/01` 主线盘 silent fallback 家族是否还剩零命中语法糖或别名绕行；若这一族基本收平，再切回另一条同级高复利 fail-closed 红线。
