# V4 empty reversed iterator silent fallback gate record

- 时间：2026-03-30 18:53:09 +0800
- 轮次：M1b Slice 258
- 本轮动作：调整 `tools/checks/check_reference_redlines.py`，沿通用空迭代器哨兵把 `reversed()` 接入静态求值与 known-name 运行值解析；当 `reversed()` 的单参数属于“可逆且已知为空”的值时，直接把结果视为“空迭代器”。
- 代码收口：现在 `except ValueError: return list(reversed(()))`、`except TypeError: payload = []; return tuple(reversed(payload))` 与 `except OSError: payload = b''; items = reversed(payload); return bytes(items)` 会被视为 direct 静默降级并触发 fail-closed 门禁。
- 合同补齐：`tests/contracts/test_reference_redlines_check.py` 同步补齐 3 条 empty reversed 必败合同，并覆盖 direct、known-name 与 alias 三种入口。
- 基线结果：这一刀说明空迭代器真源已经足够稳，可以继续承接 `reversed()` 这类标准库 iterator helper；后续若继续补 `enumerate()`，也会更轻。
- 验证：`python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py`、`python -m unittest tests.contracts.test_reference_redlines_check -v`、`python tools/checks/check_reference_redlines.py`、`python tools/checks/check_ledger_alignment.py`、`git diff --check`
- 为什么这样做：`reversed()` 切口小、判空边界稳，而且在 alias 传播已打通后，一刀就覆盖两条消费路径，长期收益明显高于继续补零散语法糖。
- 下一步：继续盘 `enumerate()` 是否能沿同一真源接入；若空迭代器 family 的高价值缺口基本收平，再切回另一条同级高复利 fail-closed 红线。