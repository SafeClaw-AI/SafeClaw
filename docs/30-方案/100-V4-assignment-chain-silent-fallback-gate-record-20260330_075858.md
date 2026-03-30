# V4 assignment chain silent fallback gate record

- 时间：2026-03-30 07:58:58 +0800
- 轮次：M1b Slice 228
- 本轮动作：调整 `tools/checks/check_reference_redlines.py` 的 direct silent fallback 赋值链识别逻辑，把多步 `Assign` / `AnnAssign` alias chain 也纳入真源，识别 `fallback = [] ; alias = fallback ; return alias`、`fallback = bool(False) ; alias: object = fallback ; return alias` 与 `empty = "" + "" ; fallback = empty ; return fallback` 这类中转绕行。
- 代码收口：现在 `except ValueError: fallback = []; alias = fallback; return alias`、`except TypeError: fallback = bool(False); alias: object = fallback; return alias` 与 `except OSError: empty = "" + ""; fallback = empty; return fallback` 会和普通空值字面量、构造器 alias、条件 / 布尔 / 二元表达式 alias 一样，被视为 direct 静默降级并触发 fail-closed 门禁。
- 合同补齐：`tests/contracts/test_reference_redlines_check.py` 同步补齐 3 条 assignment chain alias 必败合同，并按 TDD 先跑到红、再实现转绿。
- 基线结果：定向扫描多步 assignment chain silent fallback 当前为 `NO_ASSIGN_CHAIN_HITS`。
- 验证：`python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py`、`python -m unittest tests.contracts.test_reference_redlines_check -v`、`python tools/checks/check_reference_redlines.py`、`python tools/checks/check_ledger_alignment.py`、`git diff --check`
- 为什么这样做：如果 direct silent fallback 只拦静态表达式 alias，不拦多步赋值链中转，开发者仍可只加一层名字转手就继续吞掉异常上下文；趁当前零旧债时补齐这一层，长期更稳。
- 下一步：继续沿 `docs/reference/01` 主线盘 silent fallback 家族是否还剩零命中 helper 包装层或更深别名绕行；若这一族基本收平，再切回另一条同级高复利 fail-closed 红线。
