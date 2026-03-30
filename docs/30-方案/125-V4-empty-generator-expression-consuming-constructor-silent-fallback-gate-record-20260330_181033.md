# V4 empty generator expression consuming constructor silent fallback gate record

- 时间：2026-03-30 18:10:33 +0800
- 轮次：M1b Slice 253
- 本轮动作：调整 	ools/checks/check_reference_redlines.py，把 GeneratorExp 的空 iterable 静态判定接入静态求值与 known-name 运行值解析，并新增 generator expression 空值哨兵；只有在 list/tuple/dict/set/frozenset 这组 consuming constructor 消费空 generator expression 时，才把结果折叠为 []/()/ {}/set()/frozenset()。
- 代码收口：现在 except ValueError: return list(item for item in ())、except TypeError: payload = set(); return tuple(item for item in payload) 与 except OSError: pairs = []; return dict((key, value) for key, value in pairs) 会被视为 direct 静默降级并触发 fail-closed 门禁。
- 合同补齐：	ests/contracts/test_reference_redlines_check.py 同步补齐 3 条 empty generator expression 必败合同，并覆盖 direct return、known-name alias 与 constructor 消费三种入口。
- 基线结果：这一刀把 silent fallback 的表达式级空容器缺口继续从 comprehension 推进到 generator expression consuming constructor，后续不容易再靠一层 generator 语法糖吞掉异常上下文。
- 验证：python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py、python -m unittest tests.contracts.test_reference_redlines_check -v、python tools/checks/check_reference_redlines.py、python tools/checks/check_ledger_alignment.py、git diff --check
- 为什么这样做：若直接把 GeneratorExp 求值成某种空容器，会误伤本来合法的 direct generator return；因此本刀用“空 generator 哨兵 + consuming constructor 折叠”的更难方案，短期稍复杂，但长期边界更稳。
- 下一步：继续盘 expression-level silent fallback 是否还剩 ytes/bytearray 等其他 consuming constructor 缺口；若 generator family 已基本收平，再切回另一条同级高复利 fail-closed 红线。