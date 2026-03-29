# V4 json decode error context gate 记录

## 时间
- `2026-03-29 20:25:42 +0800`

## 本轮动作
- 继续沿 `docs/reference/01` 的异常红线主线推进，把 `json.JSONDecodeError` 从“可裸抓”升级为“必须绑定并保留上下文”。
- 先在 `tests/contracts/test_reference_redlines_check.py` 补失败合同与通过合同，锁住“裸抓 JSON 解析异常必须失败 / 绑定并真正使用异常上下文则通过”。
- 扩大 `tools/checks/check_reference_redlines.py` 的 AST 门禁，让 `json.JSONDecodeError` 与多异常 / broad except 一样进入“必须绑定 `as error`”与“绑定后必须真正使用”的同一规则链。
- 修平当前 3 个真实命中点：`tools/checks/check_mvp_operator_flow.py` 的 `load_json()`、`tools/checks/check_tooling_smoke.py` 的 `load_json_payload()` 与 `load_json_file_payload()`，都改成显式回传解析上下文。

## 为什么做这刀
- 上一刀已经收住高风险 `OSError/json.JSONDecodeError` 的静默降级，但 `json.JSONDecodeError` 仍可能被裸抓，导致 JSON 解析失败时上下文被直接丢掉。
- 当前全仓只有 3 个真实命中点，误伤面极小，正适合继续按“短期难一点、长期更稳”的方式把异常红线向前压一层。

## 结果
1. `tools/checks/check_reference_redlines.py`
   - 新增 `json.JSONDecodeError` 必须绑定 `as error` 的门禁
   - 已让“绑定后必须真正使用”这层红线自动覆盖到 `json.JSONDecodeError`
2. `tests/contracts/test_reference_redlines_check.py`
   - 新增 `json.JSONDecodeError` 裸抓失败 / 绑定并使用通过合同
3. `tools/checks/check_mvp_operator_flow.py`
   - `load_json()` 解析失败时现在会把 `invalid json: <error>` 拼进返回文本
4. `tools/checks/check_tooling_smoke.py`
   - `load_json_payload()` / `load_json_file_payload()` 现在会把异常详情写进 `输出不是合法 JSON: <error>`
5. `tools/checks/README.md`
   - `tools/README.md`
   - 已同步公开说明：reference 红线现在也覆盖 `json.JSONDecodeError` 的上下文保留要求

## 最小验证
- `python -m py_compile tools/checks/check_reference_redlines.py tools/checks/check_mvp_operator_flow.py tools/checks/check_tooling_smoke.py tests/contracts/test_reference_redlines_check.py`
- `python -m unittest tests.contracts.test_reference_redlines_check tests.contracts.test_public_docs_check -v`
- `python tools/checks/check_reference_redlines.py`
- `python tools/checks/check_mvp_operator_flow.py`
- `python tools/checks/check_tooling_smoke.py`
- `python tools/checks/check_public_docs.py`
- `git diff --check`

## 下一步
- 若继续沿异常红线推进，优先扩大到更多“单异常但无上下文降级”形态，而不只盯 `json.JSONDecodeError`。
- 若希望换到另一条同样高复利的支线，就切去“单函数 / 单类体量红线”的可执行检查。
