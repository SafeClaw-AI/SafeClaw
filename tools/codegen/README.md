# tools/codegen/

用于从当前 `specs/` 生成最小稳定索引。

当前支持：

- `python tools/codegen/main.py --target rust`
- `python tools/codegen/main.py --target python`
- `python tools/codegen/main.py --target ts`
- `python tools/codegen/regenerate_all.py`

当前生成产物：

- `generated/<target>/manifest.json`
- `generated/<target>/stable_ids.json`
- `generated/index.json`

这些产物是 Phase 0 的最小稳定索引，便于后续 AI 生成、测试、审阅与回归检查。
