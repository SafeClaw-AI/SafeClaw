# V4 public docs reference rebaseline 消费记录

## 本轮动作
- 让 `tools/checks/check_public_docs.py` 开始显式消费 `docs/30-方案/20-V4-reference-compliance-rebaseline-record-20260329_030242.md`。
- 给 `docs/README.md` 补上这份纠偏快照索引，避免公开文档索引遗漏当前有效基线。
- 新增 `tests/contracts/test_public_docs_check.py`，锁住这份纠偏快照在当前基线下可通过公开文档门禁。

## 为什么做这刀
- 上一轮虽然已经补了纠偏快照，但它还没有接进任何自动化门禁。
- 如果后续有人改坏或遗漏这份快照，计划层又可能重新按旧审计的过期说法判断现状。
- 先把快照接进公开文档门禁，能把“当前应该按哪份合规判断依据推进”固定下来。

## 变更点
1. `tools/checks/check_public_docs.py`
   - 新增 `REFERENCE_REBASELINE_FILE`
   - 新增 `collect_reference_rebaseline_errors()`
   - 要求纠偏快照保留“已经过期的旧结论”“目录锁定清单”“公开文档门禁”“docs/round_logs/”“先止血、后迁移”等关键口径
2. `docs/README.md`
   - 补上 `20-V4-reference-compliance-rebaseline-record-20260329_030242.md` 公开索引
3. `tests/contracts/test_public_docs_check.py`
   - 锁住当前纠偏快照在公开文档门禁下通过

## 最小验证
- `python -m py_compile tools/checks/check_public_docs.py tests/contracts/test_public_docs_check.py`
- `python -m unittest tests.contracts.test_public_docs_check -v`
- `python tools/checks/check_public_docs.py`

## 下一步
- 继续寻找第八个最小真实消费点。
- 不在本轮顺手启动根台账迁移或 `docs/round_logs/` 历史迁移。