# CLAUDE.md — SafeClaw 项目 AI 上下文文件

> 本文件供 AI 助手（Claude Code 等）在新会话启动时快速建立项目上下文。
> 人类开发者也可阅读，但优先级低于 `01_文档/` 内的原始文档。

---

## 一、项目本质（一句话）

SafeClaw 是一个**本地运行、可回滚、可审计、让普通人也敢用的 AI 自动化执行系统**。
核心价值：先告知 → 分级确认 → 副作用账本 → 自动止损 → 可恢复。

---

## 二、解决的真实问题

| 痛点 | SafeClaw 的解法 |
|------|----------------|
| 用户不知道 AI 要做什么 | 执行前展示计划 + 风险等级 + 影响范围 |
| 不可中途停止 | 任意时刻可暂停/终止 |
| 出错后无法补救 | retry / recover / reconcile 三条恢复路径 |
| 不知道 AI 动了哪些东西 | Effect Ledger 记录每一个副作用，可追溯 |
| 权限边界不透明 | Action Tier 分级 + 白名单引导 |

---

## 三、仓库结构速查

```
/
├── CLAUDE.md                  ← 本文件（AI 上下文）
├── README.md                  ← 公开项目介绍
├── MVP_PROGRESS.md            ← 整体计划实现进展表（最新进度看这里）
├── PUSH_LOG.md                ← 推送日志
├── 开发计划.md                 ← 内部开发计划（阶段目标、刀次记录）
│
├── 01_文档/                   ← 所有原始设计文档（真源）
│   ├── 01_宪法.md             ← 核心原则，最高优先级
│   ├── 02_决策清单.md
│   ├── 03_开发蓝图.md          ← M1/M1b/M2 阶段定义
│   ├── 05_API规范草案.md
│   ├── 07_架构与模块.md
│   ├── 08_用户旅程.md          ← 4 条关键用户流程
│   └── 09_迭代升级与自动化.md  ← 门禁体系设计
│
├── specs/                     ← JSON 协议真源
│   ├── state-machines/worker_lifecycle.json
│   ├── schemas/effect_ledger.json
│   ├── schemas/action_tiers.json
│   ├── error-codes/sys_errors.json
│   └── config/preflight.json
│
├── tests/contracts/           ← 合同测试（从 specs 推导）
├── tools/checks/              ← 15 个自动门禁检查脚本
├── tools/mvp/                 ← MVP 操作入口（cmd/ps1/py）
│
├── safeclaw-core/src/         ← Rust 核心引擎
│   ├── state_engine.rs        ← 任务状态机
│   ├── effect_ledger.rs       ← 副作用账本
│   ├── worker_lifecycle.rs    ← Worker 生命周期
│   ├── scheduler.rs           ← 调度器
│   ├── recovery/              ← 恢复逻辑
│   ├── task_concurrency.rs    ← 并发 + Lease/Fencing
│   └── runtime_store.rs       ← 状态持久化
│
└── safeclaw-sqlite/           ← SQLite 存储适配
```

---

## 四、当前开发阶段

| 阶段 | 状态 | 说明 |
|------|------|------|
| Phase 0 协议层 | ✅ 完成 | specs/、合同测试、门禁闭环 |
| M1a 生存层基线 | ✅ 完成 | 根入口全链路可手动跑通 |
| M1b 生存层补完 | 🔄 收尾 | reference fail-closed 主线，287+ 刀 |
| M2 价值层首轮 | ⬜ 未开始 | 用户可感知功能，预计 1~2 周 |

> 最新进度以 `MVP_PROGRESS.md` 为准，本文件不维护细粒度刀次记录。

---

## 五、本地可体验的最短路径（Windows）

```bat
safeclaw.cmd workspace --name demo   # 1. 设置工作区
safeclaw.cmd doctor                  # 2. 检查环境
safeclaw.cmd service-run --task ...  # 3. 提交任务
safeclaw.cmd service-status          # 4. 查看状态
safeclaw.cmd verify                  # 5. 验收
safeclaw.cmd recover                 # 6. 出错时恢复
```

完整命令参考：`tools/mvp/README.md`
操作白名单：`tools/mvp/OPERATOR_PLAYBOOK.md`

---

## 六、核心设计原则（AI 辅助时必须遵守）

1. **fail-closed**：遇到不确定情况，拒绝执行，不静默降级
2. **每刀一合同**：每个新功能/修复必须有对应的合同测试锁住
3. **真源唯一**：常量、错误消息、类型名单只能有一个定义点，禁止复制
4. **不跳门禁**：修改代码后必须跑 `tools/checks/selfcheck.py` 确认全绿
5. **小步快跑**：每次改动形成可验证闭环，不做未锁住的大跳跃

---

## 七、门禁体系速查

运行全量自检：
```bash
python tools/checks/selfcheck.py
```

关键门禁脚本：

| 脚本 | 作用 |
|------|------|
| selfcheck.py | 总入口，串联所有检查 |
| check_tooling_smoke.py | MVP 操作入口 smoke 测试 |
| check_mvp_operator_flow.py | operator 完整流程门禁 |
| check_reference_redlines.py | 异常处理红线检查（空 except、静默降级、裸 except）|
| check_consistency.py | 跨文件一致性检查 |
| check_versions.py | 版本号对齐检查 |
| check_public_docs.py | 公开文档完整性检查 |

---

## 八、异常处理红线（check_reference_redlines.py 强制执行）

AI 生成代码时必须遵守：

- **禁止裸 `except:`** → 必须显式捕获类型并绑定 `as error`
- **禁止 broad except 静默降级** → `except Exception` / `except BaseException` 不能直接 `return None/False/\"\"`
- **高风险异常必须绑定上下文** → `OSError`、`RuntimeError`、`KeyError`、`json.JSONDecodeError` 等必须 `as error`
- **禁止空 except 块** → `pass` / `...` 单独出现在 except 块中不合法
- **TODO 必须有元数据** → 格式：`# TODO owner=xxx due=YYYY-MM-DD req=xxx`

---

## 九、产品定位与商业判断（供决策参考）

### 目标用户（当前阶段）
**5~20 人的小团队技术负责人**，有 AI 自动化需求但担心出错、担心权限失控。
不是普通消费者（门槛太高），不是大型企业（需要定制）。

### 核心差异点（真实存在）
- Effect Ledger 副作用账本：执行后可读的操作账单，可回滚
- fail-closed 哲学：出错宁可停住，不静默继续
- 本地运行：数据不出门，隐私可控
- 三条恢复路径：retry / recover / reconcile，覆盖主要失败场景

### 当前最大风险
M2 价值层未拆解 → 用户可感知功能为零 → 进入 M2 后范围可能严重超预期。

### 不适合做的事（当前阶段）
- 不要在 M2 启动前继续堆 M1b 风格的小切片
- 不要贸然为普通消费者做 GUI（需要额外 3~6 个月前端工作）
- 不要把 Effect Ledger 藏在引擎里——它是最有说服力的用户可见差异点

---

## 十、给 AI 助手的工作建议

1. **读进度前先看** `MVP_PROGRESS.md` 头部和 `开发计划.md` 头部，不要只看 git log
2. **改代码前确认**当前主线是 M1b 还是 M2，避免在错误阶段做错误优先级的事
3. **任何新 Python 代码**都要过 `check_reference_redlines.py` 的红线规则
4. **不要自己估进度**，以文档中的明确状态标记为准（`[x]` = 完成，`🔄` = 进行中，`⬜` = 未开始）
5. **提交前跑** `python tools/checks/selfcheck.py`，全绿才算完成
6. **不要合并多个修改点成一次大提交**，保持每刀可独立回滚
7. **遇到不确定的边界情况**，优先问用户，不要自行补全假设

---

_本文件由项目参谋生成，最后更新：2026-04-01。如内容与 `01_文档/` 冲突，以 `01_文档/` 为准。_
