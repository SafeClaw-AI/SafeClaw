# V4 empty iter iterator silent fallback gate record

- 时间：2026-03-30 18:35:41 +0800
- 轮次：M1b Slice 256
- 本轮动作：调整 `tools/checks/check_reference_redlines.py`，沿通用空迭代器哨兵把 `iter()` 接入静态求值与 known-name 运行值解析；当 `iter()` 的单参数可静态判空时，直接把其结果视为“空迭代器”。
- 代码收口：现在 `except ValueError: return list(iter(()))`、`except TypeError: payload = []; return tuple(iter(payload))` 与 `except OSError: payload = []; return bytes(iter(payload))` 会被视为 direct 静默降级并触发 fail-closed 门禁。
- 合同补齐：`tests/contracts/test_reference_redlines_check.py` 同步补齐 3 条 empty iter 必败合同，并覆盖 direct、known-name alias 与 bytes consuming constructor 三种入口。
- 基线结果：这一刀继续验证通用空迭代器真源是有效的；后续若继续补 `reversed/enumerate` 等 family，可继续沿同一条判断链推进。
- 验证：`python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py`、`python -m unittest tests.contracts.test_reference_redlines_check -v`、`python tools/checks/check_reference_redlines.py`、`python tools/checks/check_ledger_alignment.py`、`git diff --check`
- 为什么这样做：与继续堆具体 consuming constructor 映射相比，沿通用空迭代器真源补 `iter()` 更有复利；短期多抽一层 helper，但长期维护更轻、更稳。
- 下一步：继续盘 `reversed/enumerate` 是否能沿同一真源接入；若空迭代器 family 的高价值缺口基本收平，再切回另一条同级高复利 fail-closed 红线。