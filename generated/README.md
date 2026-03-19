# generated/

本目录用于承接未来由 `specs/` 自动生成的产物。

当前阶段仍是 `Phase 0`，因此这里只保留稳定目录骨架，避免未来 codegen 落地时再改仓库结构。

## 目标子目录

- `generated/rust/`：Rust 类型与契约映射
- `generated/python/`：Python 类型与运行时辅助对象
- `generated/ts/`：TypeScript 类型与前端契约映射

## 规则

- 本目录内容应尽量由工具生成，而不是手写维护
- 当前已生成最小稳定索引：`manifest.json` 与 `stable_ids.json`
- 更完整的类型与运行时代码生成将在 M1 随 `tools/codegen/` 继续演进
