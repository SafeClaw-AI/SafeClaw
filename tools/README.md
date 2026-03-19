# tools/

仓库工具入口索引。

## 当前子目录

- `tools/checks/`：协议层门禁检查
- `tools/lint/`：稳定命名检查
- `tools/codegen/`：最小稳定索引生成
- `tools/schema_diff/`：schema 比较与自动化 diff

## 推荐入口

- 重建生成产物：`python tools/codegen/regenerate_all.py`
- 运行全量门禁：`python tools/checks/selfcheck.py`
