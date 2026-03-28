# V4 tools checks README ledger policy 记录

## 本轮动作
- 给 `tools/checks/README.md` 补出迁移期优先链路，显式说明 `selfcheck.py` 会先跑哪条 ledger policy chain。
- 扩大 `check_public_docs.py` 对 `tools/checks/README.md` 的关键标记约束，锁住这条说明不再漂移。
- 扩大 `tests/contracts/test_public_docs_check.py`，让当前 public docs 全量基线也进入合同测试。

## 为什么做这刀
- 上一轮虽然已经把 `selfcheck.py` 顺序调稳，但公开文档还没有把这条现行顺序写清楚。
- 如果 README 不同步，后续维护者看到的入口说明就会落后于真实门禁，排障成本会重新变高。
- 先把 README 与 public docs 门禁一起锁住，能让上一刀真正收口。

## 变更点
1. `tools/checks/README.md`
   - 新增“迁移期优先链路”段落
   - 显式列出 `ledger_index_manifest.py -> check_ledger_alignment.py -> check_consistency.py -> check_versions.py -> check_structure.py -> check_scaffold.py -> check_public_docs.py -> Contract tests`
2. `tools/checks/check_public_docs.py`
   - 扩大 `TOOLS_README_FILE` 的关键标记要求
   - 锁住 `迁移期优先链路`、关键脚本名与 `Contract tests` 口径
3. `tests/contracts/test_public_docs_check.py`
   - 在保留纠偏快照测试的同时，追加当前 public docs 全量基线测试

## 最小验证
- `python -m py_compile tools/checks/check_public_docs.py tests/contracts/test_public_docs_check.py`
- `python -m unittest tests.contracts.test_public_docs_check -v`
- `python tools/checks/check_public_docs.py`

## 下一步
- 继续寻找第八个最小真实消费点。
- 不在本轮顺手迁移根台账或 `docs/round_logs/`。