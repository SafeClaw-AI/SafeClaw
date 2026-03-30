# V4 bytes bytearray generator expression consuming constructor silent fallback gate record

- 时间：2026-03-30 18:19:55 +0800
- 轮次：M1b Slice 254
- 本轮动作：调整 	ools/checks/check_reference_redlines.py，把空 GeneratorExp 被 ytes/bytearray 消费的场景也接入 generator expression 空值哨兵折叠；当 generator 的 iter 可静态判空时，ytes/bytearray 这组构造器会直接折叠为 ""/bytearray()。
- 代码收口：现在 except ValueError: return bytes(item for item in ())、except TypeError: payload = []; return bytearray(item for item in payload) 与 except OSError: payload = []; return bytes(source=(item for item in payload)) 会被视为 direct 静默降级并触发 fail-closed 门禁。
- 合同补齐：	ests/contracts/test_reference_redlines_check.py 同步补齐 3 条 bytes/bytearray generator expression 必败合同，并覆盖单参数、known-name alias 与 keyword constructor 三种入口。
- 基线结果：这一刀把 generator expression consuming constructor 家族从容器类继续扩到字节构造器，后续不容易再靠一层 ytes/bytearray 语法糖吞掉异常上下文。
- 验证：python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py、python -m unittest tests.contracts.test_reference_redlines_check -v、python tools/checks/check_reference_redlines.py、python tools/checks/check_ledger_alignment.py、git diff --check
- 为什么这样做：继续沿用“generator 哨兵 + consuming constructor 折叠”方案，能把空 generator 的字节构造器绕行收平，同时保持 direct generator return 不被误伤，短期更难一点，但长期边界更稳。
- 下一步：继续盘 generator family 是否还剩其他 consuming constructor 边角；若这一族基本收平，再切回另一条同级高复利 fail-closed 红线。