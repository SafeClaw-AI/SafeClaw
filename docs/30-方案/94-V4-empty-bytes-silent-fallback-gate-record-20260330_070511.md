# V4 empty bytes silent fallback gate record

- 时间：2026-03-30 07:05:11 +0800
- 轮次：M1b Slice 222
- 本轮动作：调整 `tools/checks/check_reference_redlines.py` 的 `SILENT_FALLBACK_SUFFIX` 与 silent fallback 识别逻辑，把 `b''`、`bytes()`、`bytearray()` 也纳入 direct 静默降级真源。
- 代码收口：现在 `except ValueError: return b''`、`except TypeError: return bytes()`、`except ValueError: return bytearray()` 会和 `None/False/空字符串/空字节串/空容器` 一样，被视为 direct 静默降级并触发 fail-closed 门禁。
- 合同补齐：`tests/contracts/test_reference_redlines_check.py` 同步补齐 1 条 helper 稳定性合同与 3 条空字节串 direct fallback 必败合同，并把所有旧错误消息断言统一到“空字符串/空字节串/空容器”新口径。
- 基线结果：AST 定向扫描全仓 `return b''` / `return bytes()` / `return bytearray()` 形态当前为 `NO_HITS`，本轮属于零旧债扩面；无需修平既有业务代码。
- 验证：`python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py`、`python -m unittest tests.contracts.test_reference_redlines_check -v`、`python tools/checks/check_reference_redlines.py`、`python tools/checks/check_ledger_alignment.py`、`git diff --check`
- 为什么这样做：如果 direct silent fallback 只拦文本/容器空值，不拦空字节串，开发者仍可用二进制空值继续吞掉异常上下文；趁全仓零命中时补齐这一层，长期更稳。
- 下一步：继续沿 `docs/reference/01` 主线盘 silent fallback 家族是否还剩零命中别名或绕行写法；若这一族基本收平，再切回另一条同级高复利 fail-closed 红线。
