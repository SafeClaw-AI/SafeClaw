# V4 empty iterator alias propagation silent fallback gate record

- 时间：2026-03-30 18:42:57 +0800
- 轮次：M1b Slice 257
- 本轮动作：调整 `tools/checks/check_reference_redlines.py`，把通用空迭代器哨兵纳入 handler 赋值链的可追踪中间值；空迭代器不再只在“立即被 constructor 包裹”的场景可识别，而是允许先赋给别名，再在后续 `list/tuple/set` 等 consuming constructor 中被折叠为静默降级结果。
- 代码收口：现在 `except ValueError: payload = []; items = iter(payload); return list(items)`、`except TypeError: payload = []; items = zip(payload, [1]); return tuple(items)` 与 `except OSError: payload = []; items = (item for item in payload); return set(items)` 会被视为 direct 静默降级并触发 fail-closed 门禁。
- 合同补齐：`tests/contracts/test_reference_redlines_check.py` 同步补齐 3 条空迭代器 alias 必败合同，并分别覆盖 `iter/zip/generator expression` 三条真源。
- 基线结果：这一刀把空迭代器真源真正接进了赋值传播链，前面已经落地的 `generator/zip/iter` 收口范围都同步变宽，后续若再补 `reversed/enumerate` 也能直接吃到这条基础设施。
- 验证：`python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py`、`python -m unittest tests.contracts.test_reference_redlines_check -v`、`python tools/checks/check_reference_redlines.py`、`python tools/checks/check_ledger_alignment.py`、`git diff --check`
- 为什么这样做：与继续单补某个 iterator helper 相比，先把 alias 传播打通是短期更难、长期更省力的做法；后续不用重复补“直接调用”和“先赋值再消费”两条线。
- 下一步：在空迭代器 alias 传播已打通的前提下，继续盘 `reversed/enumerate` 哪一刀更值；若迭代器 family 的高价值缺口基本收平，再切回另一条同级高复利 fail-closed 红线。