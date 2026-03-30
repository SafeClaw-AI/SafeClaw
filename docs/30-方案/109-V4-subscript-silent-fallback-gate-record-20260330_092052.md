# V4 subscript silent fallback gate record

- 时间：2026-03-30 09:20:52 +0800
- 轮次：M1b Slice 237
- 本轮动作：调整 `tools/checks/check_reference_redlines.py` 的 direct silent fallback 真源，新增 `Subscript` 运行值求值能力；既覆盖 direct 静态切片，也覆盖 assignment chain 传播后的已知 silent fallback 名字切片。
- 代码收口：现在 `except ValueError: return [][:]`、`except TypeError: empty = "" + ""; return empty[:]` 与 `except OSError: payload = b""; return payload[:]` 会和其他语法糖包装一样，被视为 direct 静默降级并触发 fail-closed 门禁。
- 合同补齐：`tests/contracts/test_reference_redlines_check.py` 同步补齐 3 条 subscript 必败合同，并按 TDD 先跑到红、再实现转绿。
- 基线结果：定向扫描 except handler 内的 `Subscript` silent fallback 当前为 `NO_RETURN_SUBSCRIPT_HITS`。
- 验证：`python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py`、`python -m unittest tests.contracts.test_reference_redlines_check -v`、`python tools/checks/check_reference_redlines.py`、`python tools/checks/check_ledger_alignment.py`、`git diff --check`
- 为什么这样做：如果 direct silent fallback 不拦 `return alias[:]` 这类低成本切片语法糖，开发者仍可只包一层 `Subscript` 就继续吞掉异常上下文；趁当前全仓零旧债时补齐这一层，长期更稳。
- 下一步：继续沿 `docs/reference/01` 主线盘 silent fallback 家族是否还剩零命中更深 alias 包装或 helper 绕行；若这一族基本收平，再切回另一条同级高复利 fail-closed 红线。
