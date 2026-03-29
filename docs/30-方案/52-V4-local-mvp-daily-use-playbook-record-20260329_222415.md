# V4 本机日用白名单路径收口记录（2026-03-29 22:24:15 +0800）

## 本轮动作
- 在 `tools/mvp/OPERATOR_PLAYBOOK.md` 增补“Daily-Use Guardrails”，明确当前 local-only MVP 的本机日用白名单路径。
- 在 `tools/checks/check_public_docs.py` 把这些关键操作词与 local-only / ai-reason 边界纳入公开文档门禁。
- 在 `tests/contracts/test_public_docs_check.py` 补合同，锁住 operator playbook 的最小日用合同。

## 为什么做这刀
- 单异常上下文红线已把低噪声候选基本吃干净，继续扩名单收益开始下降。
- 当前真正阻碍“边开发边用”的不是再多一条异常名单，而是本机日用路径虽存在，却还没有被机器锁成公开合同。
- 把日用白名单路径写进 playbook 并接入 public docs gate，能让后续迭代不轻易把可手用路径写散。

## 结果
1. `tools/mvp/OPERATOR_PLAYBOOK.md`
   - 新增 `Daily-Use Guardrails`，明确 `workspace -> doctor -> service-run --report -> service-status -> verify --json` 是本机日用白名单。
2. `tools/checks/check_public_docs.py`
   - `OPERATOR_PLAYBOOK_FILE` 现在会强制检查 `local-only`、`ai-reason` 以及关键日用命令词。
3. `tests/contracts/test_public_docs_check.py`
   - 新增 operator playbook 标记合同，防止日用路径在公开文档里静默漂移。

## 最小验证
- `python -m py_compile tools/checks/check_public_docs.py tests/contracts/test_public_docs_check.py`
- `python -m unittest tests.contracts.test_public_docs_check -v`
- `python tools/checks/check_public_docs.py`
- `git diff --check`

## 下一步
- 若继续沿 Plan B 路线推进，优先把 `README.md` 的根入口最短白名单与 `OPERATOR_PLAYBOOK.md` 再做一次显式互链和语义对齐。
