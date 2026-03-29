# V4 FileExistsError 上下文红线收口记录（2026-03-29 21:14:08 +0800）

## 本轮动作
- 在 `tests/contracts/test_reference_redlines_check.py` 新增 `FileExistsError` 裸抓失败 / 绑定并使用通过合同。
- 把 `tools/checks/check_reference_redlines.py` 扩到 `FileExistsError` 必须绑定 `as error` 并保留上下文。
- 修平 `tools/checks/mvp_state_guard.py` 的当前唯一命中点，把锁竞争场景显式带上 `create_error` 上下文。
- 同步 `tools/checks/README.md` 与 `tools/README.md` 公开说明。

## 为什么做这刀
- `json.JSONDecodeError` 上下文门禁已收口后，下一步最稳的推进是继续沿“单异常必须保留上下文”推进，而不是立刻切到误伤面更大的体量红线。
- 全仓当前只有 1 个 `FileExistsError` 裸抓命中点，误伤面极小，正适合继续小步 fail-closed 推进。

## 结果
1. `tools/checks/check_reference_redlines.py`
   - `FileExistsError` 已纳入必须绑定并保留上下文的单异常红线。
2. `tools/checks/mvp_state_guard.py`
   - 锁文件已存在时，最终异常现在会带上 `create_error` 上下文，不再丢掉创建冲突信息。
3. `tests/contracts/test_reference_redlines_check.py`
   - 新增 `FileExistsError` 裸抓失败 / 绑定并使用通过合同。

## 最小验证
- `python -m py_compile tools/checks/check_reference_redlines.py tools/checks/mvp_state_guard.py tests/contracts/test_reference_redlines_check.py tests/contracts/test_mvp_state_guard.py`
- `python -m unittest tests.contracts.test_reference_redlines_check tests.contracts.test_mvp_state_guard tests.contracts.test_public_docs_check -v`
- `python tools/checks/check_reference_redlines.py`
- `python tools/checks/check_public_docs.py`
- `git diff --check`

## 下一步
- 若继续沿异常红线推进，优先扫描更多“单异常但无上下文降级”形态；若误伤面开始放大，再回切真实消费点。
