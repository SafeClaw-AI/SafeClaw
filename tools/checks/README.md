# tools/checks/

这里放的是 **协议层门禁脚本**。

## 当前入口

- `spec_index.py`：加载 `specs/` 索引
- `check_consistency.py`：跨文件一致性检查
- `check_versions.py`：版本一致性检查
- `check_structure.py`：结构完整性检查
- `check_public_docs.py`：公开文档对齐检查
- `check_scaffold.py`：仓库骨架检查
- `check_tooling_smoke.py`：工具烟测
- `check_generated_sync.py`：生成产物同步检查
- `selfcheck.py`：串起全部门禁的统一入口

## 推荐顺序

- 先运行 `python tools/codegen/regenerate_all.py`
- 再运行 `python tools/checks/selfcheck.py`

当前目标不是覆盖一切，
而是优先锁死最容易在自动化开发中漂移的地方。
