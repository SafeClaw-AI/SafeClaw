# V4 static empty comprehension silent fallback gate record

- 时间：2026-03-30 12:11:05 +0800
- 轮次：M1b Slice 252
- 本轮动作：调整 `tools/checks/check_reference_redlines.py`，新增 comprehension 空 iterable helper，并把 `ListComp/SetComp/DictComp` 接入静态求值与 known-name 运行值解析；当任一 generator 的 `iter` 可静态判空时，直接把结果视为 `[]/set()/{}`。
- 代码收口：现在 `except ValueError: return [item for item in []]`、`except TypeError: payload = set(); return {item for item in payload}` 与 `except OSError: pairs = []; return dict({key: value for key, value in pairs})` 会和其他语法糖包装一样，被视为 direct 静默降级并触发 fail-closed 门禁。
- 合同补齐：`tests/contracts/test_reference_redlines_check.py` 同步补齐 3 条 empty comprehension 必败合同，并覆盖 direct return、known-name alias 与 constructor 包装三种入口。
- 基线结果：这一刀把 silent fallback 的剩余高价值缺口从零参方法家族切到表达式级推导式，后续不容易再靠一层 comprehension 语法糖吞掉异常上下文。
- 验证：`python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py`、`python -m unittest tests.contracts.test_reference_redlines_check -v`、`python tools/checks/check_reference_redlines.py`、`python tools/checks/check_ledger_alignment.py`、`git diff --check`
- 为什么这样做：当前零参方法家族已基本收平，继续机械补边角方法的复利开始下降；空 comprehension 则是新的表达式级绕行面，优先级更高。
- 下一步：继续盘 expression-level silent fallback 是否还剩 generator expression、constructor 包装或更边角的 helper 缺口；若表达式级空容器已基本收平，再切回另一条同级高复利 fail-closed 红线。