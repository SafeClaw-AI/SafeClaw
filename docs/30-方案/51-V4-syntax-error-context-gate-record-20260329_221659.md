# V4 SyntaxError 上下文红线收口记录（2026-03-29 22:16:59 +0800）

## 本轮动作
- 在 `tests/contracts/test_reference_redlines_check.py` 新增 `SyntaxError` 裸抓失败 / 绑定并使用通过合同。
- 把 `tools/checks/check_reference_redlines.py` 扩到 `SyntaxError` 必须绑定 `as error` 并保留上下文。
- 同步 `tools/checks/README.md` 与 `tools/README.md` 公开说明。

## 为什么做这刀
- 前五刀已经把 `json.JSONDecodeError`、`FileExistsError`、`OSError`、`KeyError`、`RuntimeError` 纳入单异常上下文红线。
- 当前全仓仅 4 处 `except SyntaxError`，且都在 reference redlines 自身解析链路里，已绑定并真正使用上下文，说明这条护栏可以零修复面落地。
- 这刀虽小，但能把“解析失败必须带上下文”固化为 fail-closed 规则，避免后续把报错信息打回空壳。

## 结果
1. `tools/checks/check_reference_redlines.py`
   - `SyntaxError` 已纳入必须绑定并保留上下文的单异常红线。
2. `tests/contracts/test_reference_redlines_check.py`
   - 新增 `SyntaxError` 裸抓失败 / 绑定并使用通过合同。
3. `tools/checks/README.md` / `tools/README.md`
   - 已同步公开说明：`SyntaxError` 现在也进入单异常上下文护栏。

## 最小验证
- `python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py`
- `python -m unittest tests.contracts.test_reference_redlines_check tests.contracts.test_public_docs_check -v`
- `python tools/checks/check_reference_redlines.py`
- `python tools/checks/check_public_docs.py`
- `git diff --check`

## 下一步
- 若继续沿单异常上下文红线推进，低噪声候选已基本见底；下一刀更可能转回“静默降级/吞异常”与真实入口差集这类更高复利主线。
