# V4 specs root README ledger policy 记录

## 本轮动作
- 对齐 `specs/README.md`，把协议真源总入口显式写成现行 ledger-first 自检顺序。
- 扩大 `tools/checks/check_public_docs.py`，把 `specs/README.md` 的这组关键标记锁进公开文档门禁。
- 在 `开发计划.md` 追加本轮计划调整说明，并把下一候选推进到第十六个最小真实消费点。

## 为什么做这刀
- `specs/README.md` 是协议真源总入口，后续维护者看协议边界时最容易先看这里。
- 如果这里只写“通过合同测试与所有门禁检查”，长期仍可能把现行执行顺序理解成黑盒，不利于后续开发保持一致。
- 先把协议真源总入口对齐，再由 public docs 门禁锁住，长期收益高于继续补边缘说明页。

## 变更点
1. `specs/README.md`
   - 在“当前规则”段显式写出 ledger-first policy chain
   - 声明 `tools/checks/selfcheck.py` 与 `.github/workflows/contracts.yml` 会先跑 `ledger_index_manifest.py -> check_ledger_alignment.py -> check_consistency.py -> check_versions.py -> check_structure.py -> check_scaffold.py -> check_public_docs.py`，然后才进入 `Contract tests`
2. `tools/checks/check_public_docs.py`
   - 扩大 `SPECS_README_FILE` 的关键标记集合
   - 把 specs 真源总入口纳入 ledger-first 公开文档门禁
3. `开发计划.md`
   - 记录本轮为何选择 `specs/README.md`
   - 将下一候选推进到第十六个最小真实消费点

## 最小验证
- `python -m py_compile tools/checks/check_public_docs.py tests/contracts/test_public_docs_check.py`
- `python -m unittest tests.contracts.test_public_docs_check -v`
- `python tools/checks/check_public_docs.py`

## 下一步
- 第十五个最小真实消费点已落到 `specs/README.md`。
- 下一刀继续找第十六个真实消费点，优先仍看长期维护入口或自动化入口。
