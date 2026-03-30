# V4 empty zip iterator silent fallback gate record

- 时间：2026-03-30 18:27:50 +0800
- 轮次：M1b Slice 255
- 本轮动作：调整 `tools/checks/check_reference_redlines.py`，把既有空 `GeneratorExp` 哨兵提升为通用空迭代器哨兵，并把 `zip()` 接入静态求值与 known-name 运行值解析；当 `zip()` 零参数或任一参数可静态判空时，直接把结果视为“空迭代器”。
- 代码收口：现在 `except ValueError: return list(zip())`、`except TypeError: payload = []; return tuple(zip(payload, [1]))` 与 `except OSError: keys = []; values = []; return dict(zip(keys, values))` 会被视为 direct 静默降级并触发 fail-closed 门禁。
- 合同补齐：`tests/contracts/test_reference_redlines_check.py` 同步补齐 3 条 empty zip 必败合同，并覆盖零参数、known-name alias 与 constructor 消费三种入口。
- 基线结果：这一刀不只是补 `zip()`；更重要的是把空迭代器真源抽象出来，后续若继续补 `iter/reversed/enumerate` 等 family，可以直接复用同一条判断链。
- 验证：`python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py`、`python -m unittest tests.contracts.test_reference_redlines_check -v`、`python tools/checks/check_reference_redlines.py`、`python tools/checks/check_ledger_alignment.py`、`git diff --check`
- 为什么这样做：若继续一刀一刀只补具体调用，长期会变成低复利映射堆砌；本刀先抽真源，再接 `zip()`，短期更难一点，但未来补迭代器 family 更稳、更轻。
- 下一步：继续盘 `iter/reversed/enumerate` 是否也能沿通用空迭代器哨兵接入；若迭代器 family 的高价值缺口基本收平，再切回另一条同级高复利 fail-closed 红线。