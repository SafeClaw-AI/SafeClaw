# V4 RuntimeError 上下文红线收口记录（2026-03-29 22:08:29 +0800）

## 本轮动作
- 在 `tests/contracts/test_reference_redlines_check.py` 新增 `RuntimeError` 裸抓失败 / 绑定并使用通过合同。
- 把 `tools/checks/check_reference_redlines.py` 扩到 `RuntimeError` 必须绑定 `as error` 并保留上下文。
- 同步 `tools/checks/README.md` 与 `tools/README.md` 公开说明。

## 为什么做这刀
- 前四刀已经把 `json.JSONDecodeError`、`FileExistsError`、`OSError`、`KeyError` 纳入单异常上下文红线。
- 当前全仓仅 2 处 `except RuntimeError`，且都已绑定并真正使用上下文，说明这条护栏可以零修复面落地。
- `RuntimeError` 比 `SyntaxError` 更贴近日常业务包装异常，长期收益更高，且明显比 `ValueError` 噪音更低。

## 结果
1. `tools/checks/check_reference_redlines.py`
   - `RuntimeError` 已纳入必须绑定并保留上下文的单异常红线。
2. `tests/contracts/test_reference_redlines_check.py`
   - 新增 `RuntimeError` 裸抓失败 / 绑定并使用通过合同。
3. `tools/checks/README.md` / `tools/README.md`
   - 已同步公开说明：`RuntimeError` 现在也进入单异常上下文护栏。

## 最小验证
- `python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py`
- `python -m unittest tests.contracts.test_reference_redlines_check tests.contracts.test_public_docs_check -v`
- `python tools/checks/check_reference_redlines.py`
- `python tools/checks/check_public_docs.py`
- `git diff --check`

## 下一步
- 若继续沿异常红线推进，优先评估 `SyntaxError` 是否值得纳入；若收益不足，则回到“静默降级/吞异常”与真实入口差集的更高复利切片。
