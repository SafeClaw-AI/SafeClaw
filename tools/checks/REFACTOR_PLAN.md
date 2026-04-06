# check_tooling_smoke.py 重构计划

## 当前状态

- **文件行数**: 16896 行
- **最大函数**: `collect_errors()` 11644 行
- **函数总数**: 96 个
- **核心问题**: 违反 <800 行规范，不可维护

## 重构目标

将 16896 行的单文件拆分为模块化结构，每个文件 <800 行。

## 目标结构

```
tools/checks/
├── check_tooling_smoke.py          # 主入口（<200 行）
├── smoke_tests/
│   ├── __init__.py                 # 导出所有测试模块
│   ├── base.py                     # 基础类和共享逻辑
│   ├── test_wrapper.py             # wrapper 相关测试
│   ├── test_root_cmd.py            # root cmd 测试
│   ├── test_root_ps1.py            # root ps1 测试
│   ├── test_preflight.py           # preflight 测试
│   ├── test_service.py             # service-* 测试
│   ├── test_session.py             # session 测试
│   ├── test_codegen.py             # codegen 测试
│   └── test_schema_diff.py         # schema-diff 测试
└── smoke_utils/
    ├── __init__.py                 # 导出所有工具
    ├── subprocess_runner.py        # subprocess 封装
    ├── json_assertions.py          # JSON 断言工具
    └── sitecustomize_factory.py    # sitecustomize 生成
```

## 重构步骤

### Phase 1: 准备与备份（10 分钟）

1. **创建备份**
   ```bash
   cp tools/checks/check_tooling_smoke.py tools/checks/check_tooling_smoke.py.backup
   git add tools/checks/check_tooling_smoke.py.backup
   git commit -m "backup: save check_tooling_smoke.py before refactor"
   ```

2. **创建目录结构**
   ```bash
   mkdir -p tools/checks/smoke_tests
   mkdir -p tools/checks/smoke_utils
   touch tools/checks/smoke_tests/__init__.py
   touch tools/checks/smoke_utils/__init__.py
   ```

3. **提交初始结构**
   ```bash
   git add tools/checks/smoke_tests/ tools/checks/smoke_utils/
   git commit -m "refactor: create directory structure for smoke tests"
   ```

### Phase 2: 提取工具函数（30 分钟）

**目标**: 将通用工具函数提取到 `smoke_utils/`

#### 2.1 提取 subprocess 工具

文件: `smoke_utils/subprocess_runner.py`

提取函数:
- `run_wrapper_command()`
- `run_smoke_subprocess()`
- `_smoke_parent_is_running()`
- `_terminate_smoke_process()`
- `reset_smoke_progress()`
- `_TracingSubprocessModule` 类

#### 2.2 提取 JSON 工具

文件: `smoke_utils/json_assertions.py`

提取函数:
- `load_json_payload()`
- `extract_json_error()`
- `extract_json_result()`
- `assert_verify_json_result()`
- `assert_doctor_json_result()`
- `assert_preflight_json_result()`
- `assert_workspace_json_result()`
- `assert_service_demo_json_result()`
- `assert_service_status_json_result()`
- `assert_service_run_json_result()`
- `assert_service_retry_json_result()`
- `assert_service_recover_json_result()`
- `assert_service_resume_json_result()`
- `assert_service_reconcile_json_result()`
- `assert_run_json_result()`
- `assert_use_json_result()`
- `assert_session_passthrough_json_result()`
- `assert_session_json_result()`

#### 2.3 提取 sitecustomize 工具

文件: `smoke_utils/sitecustomize_factory.py`

提取函数:
- `build_smoke_pythonpath_env()`
- `write_smoke_verify_sitecustomize()`
- `write_smoke_demo_sitecustomize()`
- `write_smoke_report_sitecustomize()`
- `write_smoke_wrapper_service_sitecustomize()`
- `write_smoke_wrapper_service_report_sitecustomize()`
- `write_smoke_root_ps1_service_report_sitecustomize()`
- `format_smoke_command()`
- `get_smoke_command_flag()`
- `should_use_smoke_demo_sitecustomize()`
- `should_use_smoke_wrapper_service_sitecustomize()`
- `should_use_smoke_wrapper_report_sitecustomize()`
- `should_use_smoke_wrapper_service_report_sitecustomize()`
- `should_use_smoke_root_ps1_service_report_sitecustomize()`

**提交点 1**:
```bash
git add tools/checks/smoke_utils/
git commit -m "refactor: extract utility functions to smoke_utils/"
git push
```

### Phase 3: 拆分测试模块（2 小时）

#### 3.1 创建基础模块

文件: `smoke_tests/base.py`

内容:
- 导入所有常量
- 导入 smoke_utils
- 定义共享的辅助函数

**提交点 2**:
```bash
git add tools/checks/smoke_tests/base.py
git commit -m "refactor: create base module for smoke tests"
git push
```

#### 3.2 拆分 wrapper 测试

文件: `smoke_tests/test_wrapper.py`

提取函数（约 30 个）:
- `append_wrapper_help_errors()`
- `append_wrapper_doctor_*_errors()`
- `append_wrapper_preflight_*_errors()`
- 其他 wrapper 相关的 `append_*_errors()` 函数

**提交点 3**:
```bash
git add tools/checks/smoke_tests/test_wrapper.py
git commit -m "refactor: extract wrapper tests to test_wrapper.py"
git push
```

#### 3.3 拆分 root cmd 测试

文件: `smoke_tests/test_root_cmd.py`

提取函数:
- `append_root_default_entry_errors()`
- `append_root_workspace_entry_errors()`
- `append_root_cmd_*_errors()`
- 其他 root cmd 相关函数

**提交点 4**:
```bash
git add tools/checks/smoke_tests/test_root_cmd.py
git commit -m "refactor: extract root cmd tests to test_root_cmd.py"
git push
```

#### 3.4 拆分 root ps1 测试

文件: `smoke_tests/test_root_ps1.py`

提取函数:
- `append_root_ps1_*_errors()`
- 其他 PowerShell 相关函数

**提交点 5**:
```bash
git add tools/checks/smoke_tests/test_root_ps1.py
git commit -m "refactor: extract root ps1 tests to test_root_ps1.py"
git push
```

#### 3.5 拆分 preflight 测试

文件: `smoke_tests/test_preflight.py`

提取函数:
- 所有 preflight 相关的测试函数

**提交点 6**:
```bash
git add tools/checks/smoke_tests/test_preflight.py
git commit -m "refactor: extract preflight tests to test_preflight.py"
git push
```

#### 3.6 拆分 service 测试

文件: `smoke_tests/test_service.py`

提取函数:
- `append_root_service_run_errors()`
- `append_root_service_retry_errors()`
- `append_root_service_recover_errors()`
- `append_root_service_resume_errors()`
- `append_root_service_reconcile_errors()`

**提交点 7**:
```bash
git add tools/checks/smoke_tests/test_service.py
git commit -m "refactor: extract service tests to test_service.py"
git push
```

#### 3.7 拆分 session 测试

文件: `smoke_tests/test_session.py`

提取函数:
- 所有 session 相关的测试函数

**提交点 8**:
```bash
git add tools/checks/smoke_tests/test_session.py
git commit -m "refactor: extract session tests to test_session.py"
git push
```

#### 3.8 拆分 codegen 测试

文件: `smoke_tests/test_codegen.py`

提取函数:
- `append_smoke_setup_errors()` 中的 codegen 部分

**提交点 9**:
```bash
git add tools/checks/smoke_tests/test_codegen.py
git commit -m "refactor: extract codegen tests to test_codegen.py"
git push
```

#### 3.9 拆分 schema_diff 测试

文件: `smoke_tests/test_schema_diff.py`

提取函数:
- `append_smoke_setup_errors()` 中的 schema_diff 部分

**提交点 10**:
```bash
git add tools/checks/smoke_tests/test_schema_diff.py
git commit -m "refactor: extract schema_diff tests to test_schema_diff.py"
git push
```

### Phase 4: 重写主入口（30 分钟）

文件: `check_tooling_smoke.py`

新内容（<200 行）:
```python
from __future__ import annotations

from pathlib import Path
from mvp_state_guard import acquire_mvp_state_lock

from smoke_tests import (
    test_wrapper,
    test_root_cmd,
    test_root_ps1,
    test_preflight,
    test_service,
    test_session,
    test_codegen,
    test_schema_diff,
)
from smoke_utils.subprocess_runner import reset_smoke_progress

REPO_ROOT = Path(__file__).resolve().parents[2]


def collect_errors() -> list[str]:
    """收集所有 smoke 测试错误"""
    errors: list[str] = []
    reset_smoke_progress()
    
    # 按模块收集错误
    test_codegen.collect_errors(errors)
    test_schema_diff.collect_errors(errors)
    test_wrapper.collect_errors(errors)
    test_root_cmd.collect_errors(errors)
    test_root_ps1.collect_errors(errors)
    test_preflight.collect_errors(errors)
    test_service.collect_errors(errors)
    test_session.collect_errors(errors)
    
    return errors


def _main() -> int:
    errors = collect_errors()
    
    if errors:
        print("Tooling smoke check failed:")
        for item in errors:
            print(f"- {item}")
        return 1
    
    print("Tooling smoke check passed.")
    return 0


def main() -> int:
    try:
        with acquire_mvp_state_lock("check_tooling_smoke"):
            return _main()
    except RuntimeError as error:
        print(f"Tooling smoke check failed: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

**提交点 11**:
```bash
git add tools/checks/check_tooling_smoke.py
git commit -m "refactor: rewrite main entry point (<200 lines)"
git push
```

### Phase 5: 验证与测试（30 分钟）

1. **运行 smoke 测试**
   ```bash
   python tools/checks/check_tooling_smoke.py
   ```

2. **运行合同测试**
   ```bash
   python -m pytest tests/contracts/test_tooling_smoke_check.py -v
   ```

3. **运行完整自检**
   ```bash
   python tools/checks/selfcheck.py
   ```

**提交点 12**:
```bash
git add .
git commit -m "refactor: verify all tests pass after refactoring"
git push
```

### Phase 6: 清理与文档（15 分钟）

1. **删除备份文件**
   ```bash
   git rm tools/checks/check_tooling_smoke.py.backup
   ```

2. **更新文档**
   - 更新 `tools/checks/README.md`
   - 添加模块说明

**提交点 13**:
```bash
git add .
git commit -m "refactor: cleanup and update documentation"
git push
```

## 回滚策略

### 如果重构失败

**方案 A: 回滚到最近的提交点**
```bash
git log --oneline | head -20  # 查看提交历史
git reset --hard <commit-hash>
git push --force
```

**方案 B: 恢复备份文件**
```bash
git checkout <commit-hash> -- tools/checks/check_tooling_smoke.py.backup
mv tools/checks/check_tooling_smoke.py.backup tools/checks/check_tooling_smoke.py
rm -rf tools/checks/smoke_tests/
rm -rf tools/checks/smoke_utils/
git add .
git commit -m "revert: restore original check_tooling_smoke.py"
git push
```

## 风险控制

### 高风险操作

1. ❌ **不要一次性删除原文件**
2. ❌ **不要跳过提交点**
3. ❌ **不要在未验证前推送**

### 安全措施

1. ✅ **每个 Phase 结束后立即提交推送**
2. ✅ **每次提交前运行测试**
3. ✅ **保留备份文件直到最后**
4. ✅ **使用 git stash 保存临时修改**

## 预期时间

- Phase 1: 10 分钟
- Phase 2: 30 分钟
- Phase 3: 2 小时
- Phase 4: 30 分钟
- Phase 5: 30 分钟
- Phase 6: 15 分钟

**总计: 约 4 小时**

## 成功标准

1. ✅ 所有文件 <800 行
2. ✅ `check_tooling_smoke.py` <200 行
3. ✅ 所有测试通过
4. ✅ 行为与原文件完全一致
5. ✅ 代码可读性显著提升

## 注意事项

1. **保持行为一致**: 重构不改变任何测试逻辑
2. **及时提交**: 每完成一个模块立即提交
3. **频繁推送**: 每个提交点都推送到远程
4. **测试驱动**: 每次修改后立即运行测试
5. **小步快跑**: 不要试图一次性完成所有重构

## 开始前检查清单

- [ ] 已阅读完整重构计划
- [ ] 已理解回滚策略
- [ ] 已确认 git 状态干净
- [ ] 已确认测试可以正常运行
- [ ] 已准备好至少 4 小时的连续时间
- [ ] 已通知团队成员（如有）

## 开始重构

准备好后，从 Phase 1 开始执行。
