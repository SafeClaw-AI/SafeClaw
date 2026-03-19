# SafeClaw

> 有龙虾灵魂的本地自动化执行工具：先讲风险，再讲操作，最后由你决定是否执行。

---

## 它是什么？

SafeClaw 帮你把本地自动化任务跑起来，但不会擅自替你做决定。

它默认谨慎、默认可查、默认可停，不是黑箱式乱执行。

它开箱即用，离线可跑，所有关键权限都握在你手里。

---

## 它能做什么？

- **流程录制**：把你在桌面上的一段操作录下来，方便重复执行
- **键鼠回放**：把录好的流程重新跑一遍，支持 `dry-run` 预览，再真实执行
- **本地任务执行**：直接在页面里跑本机的 PowerShell / CMD / Bash 命令

---

## 它的原则

1. **Risk First**：每次执行前先讲风险，再讲收益和步骤
2. **Consent First**：关键动作必须你明确确认
3. **Local First**：默认本地、默认离线、默认不出站
4. **Visible First**：全程可见、可查、可停、可回放

---

## 快速开始

双击 `start.bat`（Windows）或 `start.sh`（Linux/macOS），一键启动，无需注册登录，支持完全离线运行。

---

## 当前状态

这是 SafeClaw V1，我们先把“本地自动化执行 + 风险预览 + 用户确认 + 全流程透明”做成一个真正可信的小而美产品。

更多高级能力，会在 V1 发布后，基于真实用户反馈再迭代。

---

## 当前公开内容

当前仓库优先公开 SafeClaw 的**协议层 / 真源层**，用于稳定代码生成、合同测试和多模型协作：

- `specs/state-machines/worker_lifecycle.json`：Worker 生命周期状态机
- `specs/schemas/effect_ledger.json`：副作用账本与三账本提交协议
- `specs/schemas/action_tiers.json`：Tier × Reversibility 正交定义
- `specs/error-codes/sys_errors.json`：系统错误码注册表
- `specs/config/preflight.json`：预检阈值、降级与运行时纠偏规则
- `specs/spi/base_fields.json`：4 类 SPI 统一基础字段
- `VERSION`：当前协议层版本

说明：更完整的架构哲学、路线图和内部决策文档目前仍在私有整理中，后续会按需要逐步开放。

---

## 关于龙虾的灵魂

SafeClaw 的交互逻辑，永远遵循：
- 真诚、克制、像站在你这边的朋友
- 不抢决定权、不故作聪明、不装万能
- 风险先说清，权限先收紧，动作可撤回，过程可追溯

---

## 许可

GPLv3
