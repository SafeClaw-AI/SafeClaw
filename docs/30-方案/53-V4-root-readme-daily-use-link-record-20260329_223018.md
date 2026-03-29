# V4 根 README 与日用白名单互链收口记录（2026-03-29 22:30:18 +0800）

## 本轮动作
- 在 `README.md` 明确加入 `tools/mvp/OPERATOR_PLAYBOOK.md` 入口，并把 local-only MVP 的本机日用白名单路径写到根入口说明。
- 在 `tools/mvp/OPERATOR_PLAYBOOK.md` 增加回链 `README.md`，形成根入口与操作手册的双向互链。
- 在 `tools/checks/check_public_docs.py` 与 `tests/contracts/test_public_docs_check.py` 把这组互链与关键命令词锁成公开文档合同。

## 为什么做这刀
- 上一刀已把 operator playbook 的日用白名单路径锁住，但根 `README.md` 仍只给了命令参考，没有把“边开发边用”的白名单入口显式钉牢。
- 把根入口与 playbook 做成双向互链，能显著降低后续入口漂移、重复解释与使用路径分叉。
- 这比继续机械扩异常名单更贴近当前“先用起来”的主目标，短期成本低、长期收益高。

## 结果
1. `README.md`
   - 现在显式指向 `tools/mvp/OPERATOR_PLAYBOOK.md`，并写明 local-only MVP 的最短日用路径。
2. `tools/mvp/OPERATOR_PLAYBOOK.md`
   - 现在显式回链 `README.md`，不再只做孤立操作文档。
3. `tools/checks/check_public_docs.py` / `tests/contracts/test_public_docs_check.py`
   - 现在会共同护住根入口、日用白名单与 playbook 的双向互链。

## 最小验证
- `python -m py_compile tools/checks/check_public_docs.py tests/contracts/test_public_docs_check.py`
- `python -m unittest tests.contracts.test_public_docs_check -v`
- `python tools/checks/check_public_docs.py`
- `git diff --check`

## 下一步
- 若继续沿 Plan B 推进，优先把 `README.md` 与 `tools/mvp/README.md` 的“最短上手 / 推荐操作路径”再做一次白名单词汇对齐，减少三处入口的语义漂移。
