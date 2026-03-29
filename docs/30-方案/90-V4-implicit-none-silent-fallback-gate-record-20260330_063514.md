# V4 implicit none silent fallback gate record

- 时间：2026-03-30 06:35:14 +0800
- 轮次：M1b Slice 218
- 本轮动作：把 `tools/checks/check_reference_redlines.py` 的 direct silent fallback 继续补齐到 `except ...: return` 的隐式 `None` 形态，并同步收平 `tools/mvp/safeclaw_mvp.py` 中 2 个 `OSError` 真实命中。
- 代码收口：`_is_direct_silent_fallback_return_value()` 现在把 bare `return` 也视为 direct silent fallback；`repair_invalid_workspace()` 与 `repair_invalid_session()` 改写为 `try/except/else`，避免异常分支再通过隐式 `None` 直接回退。
- 合同补齐：`tests/contracts/test_reference_redlines_check.py` 新增 `OSError -> return` 与 `ValueError -> return` 两条隐式 bare return 必败合同，先红后绿完成闭环。
- 基线结果：AST 定向扫描全仓 `except ...: return` 当前为 `NO_HITS`；本轮不只是补门禁，还顺手清掉了仓内仅剩的 2 个真实命中。
- 验证：`python -m py_compile tools/checks/check_reference_redlines.py tools/mvp/safeclaw_mvp.py tests/contracts/test_reference_redlines_check.py`、`python -m unittest tests.contracts.test_reference_redlines_check -v`、`python tools/checks/check_reference_redlines.py`、`python tools/checks/check_ledger_alignment.py`、`git diff --check`
- 为什么这样做：如果只拦显式 `return None`，却放过 bare `return`，silent fallback 的语义就不完整；而这类漏口在仓内已经落成真实代码，优先收平可直接提升长期稳定性。
- 下一步：继续沿 `docs/reference/01` 主线，优先找 silent fallback 里最后的零命中相邻表达；若这一族基本收平，再评估是否切到另一条同级红线的 fail-closed 门禁。