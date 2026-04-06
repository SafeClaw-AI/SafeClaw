# check_tooling_smoke.py 重构状态报告

## 执行时间
- 开始时间：2026-04-06
- 当前状态：进行中（Phase 2 部分完成）

## 原始文件状态
- **总行数：16,896 行**
- **主要问题：**
  - 单一巨型文件，难以维护
  - collect_errors() 函数 11,672 行
  - 26 个 assert_ 函数（约 2000-3000 行）
  - 43 个 append_ 函数（约 3000-5000 行）
  - 缺乏模块化结构

## 已完成工作

### Phase 1: 准备与备份 ✅
- ✅ 创建备份文件 `check_tooling_smoke.py.backup`
- ✅ 创建重构计划 `REFACTOR_PLAN.md`
- ✅ 所有变更已推送到远程仓库

### Phase 2: 提取工具函数 ✅（部分完成）

已创建 `smoke_utils/` 工具包，提取了 **1,028 行代码**：

#### 1. subprocess_runner.py (195 行)
- `run_smoke_subprocess()` - 带监控的 subprocess 包装器
- `reset_smoke_progress()` - 重置进度计数器
- `_smoke_parent_is_running()` - 父进程检查
- `_terminate_smoke_process()` - 进程终止
- `_TracingSubprocessModule` - subprocess 追踪类

#### 2. constants.py (135 行)
- 所有 `SMOKE_*` 常量配置
- `CHECKS` 列表（codegen 和 schema-diff）
- `REPO_ROOT` 和 `PYTHON` 路径
- 各种 stub actions 和 task IDs

#### 3. sitecustomize_factory.py (376 行)
- 5 个 `should_use_*_sitecustomize()` 检测函数
- 2 个 `build_*_pythonpath_env()` 环境构建函数
- 3 个 `write_*_sitecustomize()` 写入函数（完整实现）

#### 4. json_assertions.py (252 行)
- `load_json_payload()` - JSON 解析
- `extract_json_error()` / `extract_json_result()` - 提取器
- `assert_verify_json_result()` - verify 命令断言
- `assert_doctor_json_result()` - doctor 命令断言
- `assert_workspace_json_result()` - workspace 命令断言
- `assert_use_json_result()` - use 命令断言
- `assert_session_json_result()` - session 命令断言
- `assert_sessions_json_result()` - sessions 命令断言
- `assert_json_null_result()` - null 结果断言

#### 5. service_assertions.py (69 行)
- `assert_service_demo_json_result()` - service-demo 命令断言

#### 6. smoke_tests/ 包
- 已创建目录结构，为后续拆分做准备

## 当前进度
- **已提取：1,028 行（约 6%）**
- **剩余：15,868 行（约 94%）**

## 剩余工作

### Phase 2: 继续提取工具函数（预计 2-3 小时）
- [ ] 提取剩余 20+ 个 assert_ 函数到 json_assertions.py 和 service_assertions.py
- [ ] 创建 preflight_assertions.py（preflight 相关断言）
- [ ] 创建 command_assertions.py（通用命令断言）

### Phase 3: 拆分测试模块（预计 3-4 小时）
- [ ] 创建 smoke_tests/root_tests.py（29 个 append_root_* 函数）
- [ ] 创建 smoke_tests/wrapper_tests.py（10 个 append_wrapper_* 函数）
- [ ] 创建 smoke_tests/helper_tests.py（4 个辅助函数）

### Phase 4: 重写主入口（预计 2-3 小时）
- [ ] 重写 collect_errors() 函数（从 11,672 行 -> <200 行）
- [ ] 更新导入语句
- [ ] 简化主文件结构

### Phase 5: 验证测试（预计 1 小时）
- [ ] 运行完整的 smoke test
- [ ] 修复任何导入或引用问题
- [ ] 确保所有测试通过

### Phase 6: 清理文档（预计 30 分钟）
- [ ] 更新 REFACTOR_PLAN.md
- [ ] 删除备份文件
- [ ] 更新相关文档

## 预估剩余时间
- **总计：8-11 小时**
- 建议分 3 天完成：
  - 第 1 天：完成 Phase 2（2-3 小时）
  - 第 2 天：完成 Phase 3（3-4 小时）
  - 第 3 天：完成 Phase 4-6（3-4 小时）

## 技术债务分析

### 当前架构问题
1. **单一职责违反**：一个文件承担了所有测试逻辑
2. **可维护性差**：16,896 行代码难以理解和修改
3. **测试隔离性差**：所有测试耦合在一起
4. **代码重复**：大量相似的断言逻辑

### 目标架构
```
tools/checks/
├── check_tooling_smoke.py          # 主入口 (<200 行)
├── smoke_utils/                     # 工具函数包
│   ├── __init__.py
│   ├── constants.py                 # 常量配置
│   ├── subprocess_runner.py         # 进程管理
│   ├── sitecustomize_factory.py     # sitecustomize 生成
│   ├── json_assertions.py           # JSON 断言
│   ├── service_assertions.py        # Service 断言
│   ├── preflight_assertions.py      # Preflight 断言
│   └── command_assertions.py        # 通用命令断言
└── smoke_tests/                     # 测试模块包
    ├── __init__.py
    ├── root_tests.py                # 根命令测试
    ├── wrapper_tests.py             # 包装器测试
    └── helper_tests.py              # 辅助测试
```

## 风险与缓解

### 风险
1. **回归风险**：重构可能引入 bug
   - 缓解：保留备份，每次提交后推送到远程
2. **时间风险**：工作量超出预期
   - 缓解：分阶段进行，每阶段可独立验证
3. **兼容性风险**：导入路径变化可能影响其他文件
   - 缓解：使用相对导入，保持向后兼容

### 回滚策略
如果重构失败，可以：
1. 使用 `git revert` 回滚到任何提交点
2. 恢复 `check_tooling_smoke.py.backup`
3. 删除 `smoke_utils/` 和 `smoke_tests/` 目录

## 提交历史
1. `486cbf5` - refactor: add JSON assertion utilities
2. `1d2b762` - refactor: add sitecustomize factory functions
3. `09d07e5` - refactor: extract subprocess runner and constants
4. `091867a` - refactor: create directory structure for smoke tests
5. `111ec25` - refactor: 完善 sitecustomize 写入函数实现
6. `0740da9` - refactor: 创建 smoke_tests 测试模块目录
7. `3828986` - refactor: 添加更多 JSON 断言函数
8. `f320fe5` - refactor: 创建 service_assertions 模块

## 下次继续时的建议
1. 从 Phase 2 继续：提取剩余的 assert_ 函数
2. 优先提取简单的断言函数（参数少、逻辑简单）
3. 复杂的断言函数（如 assert_service_status_json_result）可以放到最后
4. 每提取 5-10 个函数就提交一次，保持提交粒度合理

## 参考资料
- 原始重构计划：`REFACTOR_PLAN.md`
- 备份文件：`check_tooling_smoke.py.backup`
- 相关测试：`tests/contracts/test_tooling_smoke_check.py`
