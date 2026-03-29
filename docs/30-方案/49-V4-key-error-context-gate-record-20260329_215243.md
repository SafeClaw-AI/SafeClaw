# V4 KeyError 上下文红线收口记录（2026-03-29 21:52:43 +0800）

## 本轮动作
- 在 `tests/contracts/test_reference_redlines_check.py` 新增 `KeyError` 裸抓失败 / 绑定并使用通过合同。
- 把 `tools/checks/check_reference_redlines.py` 扩到 `KeyError` 必须绑定 `as error` 并保留上下文。
- 同步 `tools/checks/README.md` 与 `tools/README.md` 公开说明。

## 为什么做这刀
- 前三刀已经把 `json.JSONDecodeError`、`FileExistsError`、`OSError` 纳入单异常上下文红线。
- 当前全仓 `KeyError` 捕获都已绑定并真正使用上下文，说明这条护栏可以零修复面落地，收益大于风险。
- 这让字典/索引缺失类异常也纳入统一上下文保留路径，继续沿长期 fail-closed 方向推进。

## 结果
1. `tools/checks/check_reference_redlines.py`
   - `KeyError` 已纳入必须绑定并保留上下文的单异常红线。
2. `tests/contracts/test_reference_redlines_check.py`
   - 新增 `KeyError` 裸抓失败 / 绑定并使用通过合同。
3. `tools/checks/README.md` / `tools/README.md`
   - 已同步公开说明：`KeyError` 现在也进入单异常上下文护栏。

## 最小验证
- `python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py`
- `python -m unittest tests.contracts.test_reference_redlines_check tests.contracts.test_public_docs_check -v`
- `python tools/checks/check_reference_redlines.py`
- `python tools/checks/check_public_docs.py`
- `git diff --check`

## 下一步
- 若继续沿异常红线推进，优先盘点下一批“零修复面”的单异常候选；当前 `RuntimeError` / `SyntaxError` 已在少量内部点位满足，可继续评估是否值得纳入。
