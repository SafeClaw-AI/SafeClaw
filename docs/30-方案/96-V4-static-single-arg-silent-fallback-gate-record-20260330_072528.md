# V4 static single-arg silent fallback gate record

- 时间：2026-03-30 07:25:28 +0800
- 轮次：M1b Slice 224
- 本轮动作：调整 `tools/checks/check_reference_redlines.py` 的 direct silent fallback 识别逻辑，新增静态表达式求值与运行值判定，把 `bool(False)`、`dict([])`、`bytes([])`、`list(())` 这类静态单参空值构造 alias 也纳入真源。
- 代码收口：现在 `except ValueError: return dict([])`、`except TypeError: return bytes([])` 与 `except OSError: fallback = bool(False); return fallback` 会和普通空值字面量、零参构造、两步返回一样，被视为 direct 静默降级并触发 fail-closed 门禁。
- 合同补齐：`tests/contracts/test_reference_redlines_check.py` 同步补齐 1 条 helper 稳定性合同，以及 3 条 direct / assignment 静态单参空值构造必败合同。
- 基线结果：AST 定向扫描全仓单参 direct silent fallback 构造 alias 当前为 `NO_HITS`，本轮属于零旧债扩面；无需修平既有业务代码。
- 验证：`python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py`、`python -m unittest tests.contracts.test_reference_redlines_check -v`、`python tools/checks/check_reference_redlines.py`、`python tools/checks/check_ledger_alignment.py`、`git diff --check`
- 为什么这样做：如果 direct silent fallback 只拦字面量、零参构造和两步返回，不拦一参静态空值构造，开发者仍可只包一层构造器就继续吞掉异常上下文；趁全仓零命中时补齐这一层，长期更稳。
- 下一步：继续沿 `docs/reference/01` 主线盘 silent fallback 家族是否还剩零命中包装层或 helper 绕行；若这一族基本收平，再切回另一条同级高复利 fail-closed 红线。
