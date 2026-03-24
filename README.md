# SafeClaw

> 希望在自动化越来越强、越来越快的时代，  
> 还能有一个系统愿意慢一点、讲清楚一点、对你温柔一点。

---

## 先说一句大实话

自动化工具已经很多了，而且很多都做得很好。

但我们注意到一件事：  
**越强大的工具，普通人越不敢用。**

不是因为笨，而是因为——

- 看不懂它到底要做什么  
- 不知道点完"执行"之后还能不能停  
- 出了问题不知道能不能补救  
- 遇到权限、脚本、命令行就开始紧张  

这些恐惧是真实的，也是合理的。  
但几乎没有工具愿意正视它。

SafeClaw 想做的，就是**从这里开始**。

---

## 它是什么

SafeClaw 是一个**在你自己电脑上运行**的自动化执行系统。

它可以联网调用云端的 AI 模型，但你的数据、记忆、操作日志全部留在本地。  
不绑定账号，不依赖云端存储——控制权始终在你手里。

它做事的方式是这样的：

1. **先告诉你**它打算做什么、会碰哪些文件、风险在哪  
2. **等你点头**才开始动手  
3. **做的过程中**你随时能暂停、能终止  
4. **做完之后**如果后悔了，尽量能撤回来  
5. **做错了**它会停在原地，不会把事情搞得更大  

一句话：  
**它宁可慢一点、笨一点，也不愿意让你承担一次说不清楚的风险。**

---

## 为什么会有 SafeClaw

市面上的自动化工具在能力上已经非常强了。  
我们不是要和谁竞争，也没有那个资格。

我们只是觉得，有一块很重要的东西长期缺着：

> **"用起来安不安心"这件事，好像一直没人认真做。**

目前已经有很多优秀的 Claw 系统（OpenClaw、ZeroClaw、IronClaw 等），  
它们在能力、性能、安全性上都做得很好。  
SafeClaw 选择了一个**它们没有选择的方向**：

- **OpenClaw** 关注"能做多少" → SafeClaw 关注"你敢不敢放心用"
- **ZeroClaw** 关注"跑多快、占多少" → SafeClaw 关注"出了事能不能恢复"
- **IronClaw** 关注"企业合规" → SafeClaw 关注"普通人也能看懂的安全"

简单说：  
其他 Claw 让 AI 变得更强大。  
SafeClaw 让你在 AI 面前**不用担心**。

我们希望把复杂留给系统，把轻松留给用户。  
**不是能力的空白，是安心感的空白。**

---

## 我们的态度

SafeClaw 的每一行代码、每一个设计决策，都从同一个问题出发：

> **「如果我是用户，我希望这个系统怎么对我？」**

所以我们给自己定了几条规矩：

- **不吓人**。看不懂的东西不往用户脸上怼  
- **不强迫**。任何动作都可以拒绝、暂停、回头  
- **不藏风险**。高危操作一定提前讲清楚  
- **不甩锅**。出了问题先想怎么帮用户补救，而不是弹一个冷冰冰的错误码  
- **不套路**。不偷偷升级权限、不暗中扩大范围、不搞"你不注意就默认同意了"  
- **不绑架**。你的数据随时可以导出、迁移、删除，我们不锁你  

这不是口号，是写进系统底层规则里的硬约束。  
代码层面违反了，系统会自动拦截。

---

## 当前公开的内容

SafeClaw 目前还处于非常早期的阶段。  
我们优先公开的是**协议层**——也就是系统内部所有模块必须遵守的规矩：

| 文件 | 说明 |
|------|------|
| [Worker 状态机](specs/state-machines/worker_lifecycle.json) | 任务从创建到结束的完整生命周期 |
| [副作用账本](specs/schemas/effect_ledger.json) | 系统对外部世界做过什么，一笔一笔记得清清楚楚 |
| [动作分级](specs/schemas/action_tiers.json) | 什么操作可以直接做、什么必须你点头、什么必须再三确认 |
| [错误码](specs/error-codes/sys_errors.json) | 出了问题不说"未知错误"，而是告诉你到底哪里出了问题 |
| [预检策略](specs/config/preflight.json) | 在动手之前先分析风险，不确定的一律从严处理 |
| [扩展接口](specs/spi/base_fields.json) | 未来新增能力的标准插槽，不用动核心就能扩展 |
| [版本锚点](VERSION) | 当前公开协议层版本，供生成、测试与发布统一引用 |
| [合同测试](tests/contracts/README.md) | 从协议直接推出的最小合同测试骨架 |
| [自检门禁](tools/checks/selfcheck.py) | 串起合同测试、一致性检查、版本检查、结构检查 |

为什么先公开这些？  
因为**规矩比功能重要**。能力可以慢慢加，但底线必须一开始就定死。

协议层（`specs/`）从第一天起就完全公开。  
内部设计文档会随着项目成熟逐步开放。  
好的安全理念不应该被藏起来。

---

## 当前状态

```
版本：3.2.0
阶段：Phase 0 — 协议真源闭环 + Rust Core 起步前夜
重点：四阶段 Effect Ledger / Probe / Fencing / Scope Quarantine / Reconcile
可体验路径：Win11 本地 MVP 操作入口（tools/mvp/）
```

SafeClaw 还在很早期。  
很多功能还没有，很多体验还会粗糙。

**如果你不懂代码：** 现在打开仓库你会看到一堆 JSON 和文档，还没有能直接用的界面。请再等等我们，界面和功能都在路上。  
**如果你是开发者：** 欢迎来看我们的协议层，提 Issue、挑毛病、贡献代码都欢迎。

但方向不会变：  
**做一个让普通人用起来安心的自动化系统。**

我们慢慢来，但会认真做。


## 当前可手动体验的本地 MVP

目前还没有正式 GUI，也还不是“开箱即用的产品”。  
但在当前 Windows GNU 开发环境下，已经可以按 **人工操作台** 的方式手动完成最小闭环。

- 推荐入口：`safeclaw.cmd`
- PowerShell 入口：`safeclaw.ps1`
- 底层 wrapper：`tools/mvp/safeclaw_mvp.cmd`
- 完整命令参考：`tools/mvp/README.md`

### 最短上手路径

第一次体验时，建议先固定一个 workspace，再做环境检查与正常执行：

```bat
safeclaw.cmd workspace --name demo
safeclaw.cmd doctor
safeclaw.cmd service-run --reset --task-id task-demo --limit 1 --report
```

如果要验证异常链，建议分别走 failed 与 uncertain 两条恢复路径：

```bat
safeclaw.cmd seed-failed --reset --task-id task-demo-failed
safeclaw.cmd service-retry --task-id task-demo-failed --limit 1 --report

safeclaw.cmd seed-crash --reset --task-id task-demo-uncertain
safeclaw.cmd service-recover --task-id task-demo-uncertain --limit 1 --report
```

如果要确认当前包装层仍处于可交付状态，可直接运行：

```bat
safeclaw.cmd verify
safeclaw.cmd verify --json
```

### 当前最小能力

- `workspace`：固定当前命名 workspace 的默认 `db` / `output`；`--clear` 回退到全局默认路径
- `doctor`：检查 launcher、Rust 工具链、linker、当前 session / workspace 路径，并显式标出当前 `db` / `output` 来源；当前 local MVP 即使未配置 model provider / sidecar 也可正常离线使用
- `service-status`：查看当前 service 队列 / worker / effect / probe 摘要，并显式展示 recent task 的 `scope` / `write` / `doctor_bypass`、最新 lease 新鲜度，以及 `next_action` 决策提示
- `service-run --report`：一条命令串起正常执行、服务态摘要与治理视图
- `service-retry --report`：用于 failed 任务的首选恢复路径
- `service-recover --report`：用于 uncertain 任务的首选恢复路径
- `session` / `sessions` / `use` / `forget`：管理 remembered session，减少重复传参
- `demo` / `recover-demo` / `retry-demo` / `run` / `report` / `status` / `seed-crash` / `recover` / `seed-failed` / `retry` / `session` / `sessions` / `use` / `forget` / `workspace` / `doctor` / `verify` 支持 `--json`，统一返回 `{ok, action, schema_version, result|error}` 信封，便于脚本接入

### 当前边界

- 这是 **MVP-first** 路线，不是最终产品形态
- 当前更像单 worker 的本地治理操作台，不是完整多用户系统
- 当前最适合开发者或愿意手动执行命令的早期体验者
- 当前已经能手动跑通正常执行、失败重试、不确定恢复与环境自检，但还没有正式 GUI、安装器与长期稳定分发入口
---

## 技术栈

> 给想了解技术细节的朋友。

| 层 | 技术 | 为什么选它 |
|----|------|-----------|
| 核心引擎 | Rust | 内存安全，不容易崩 |
| 界面 | Tauri 2.x + React | 体积小，跨平台 |
| AI 调用 | Python sidecar | AI 生态几乎都在 Python |
| 数据 | SQLite | 单文件、零依赖、你能直接打开看 |
| 契约真源 | specs/ (JSON Schema) | 所有代码从这里生成，不会走偏 |

---

## 许可

SafeClaw 采用 [GPL-3.0](LICENSE) 开源许可。

简单说：

- **个人使用、学习、研究** — 完全自由，没有任何限制  
- **开源项目集成** — 欢迎，我们一起把事情做好  
- **修改后分发** — 必须同样开源（这是 GPL 的核心要求）  
- **商业闭源集成** — 我们提供商业授权，欢迎联系洽谈  

我们选择 GPL，是因为它和 SafeClaw 的价值观一致：  
**好的安全能力应该持续开放地演进，而不是被锁进任何一家的围墙里。**

SafeClaw 的核心协议和引擎永远开源免费。  
未来如果项目成熟了，我们会通过提供高级工具和企业服务来赚取合理的利润。  
现在还早，先把东西做好。

---

## 联系

📮 **safeclaw.ai@gmail.com**

无论是合作、授权、建议，还是单纯想聊聊，都欢迎。  
如果不是私密内容，我们更推荐优先在 GitHub Discussions / Issues 里交流：  
**https://github.com/SafeClaw-AI/SafeClaw**

邮件和留言我们都会认真阅读，  
但因为项目仍在早期，未必能做到一一及时回复，还请见谅。

---

## English Summary

SafeClaw is an automation system designed for ordinary users, not just developers.  
It is built around a simple idea:  
**automation should feel understandable, controllable, and recoverable.**

Instead of pushing users to trust a black box, SafeClaw tries to:

- explain what it is going to do before it acts
- ask for confirmation when risk is involved
- keep a clear effect ledger of external actions
- stop, recover, or roll back whenever possible
- keep core control on the user's own machine

Licensed under GPL-3.0. Commercial closed-source licensing is available upon request.

Current status: Version `3.2.0` · Phase `0` · protocol source-of-truth closed loop, with an early Win11 local MVP operator path under `tools/mvp/`.

📮 **safeclaw.ai@gmail.com** · [GitHub](https://github.com/SafeClaw-AI/SafeClaw)

---

<sub>SafeClaw™ is a trademark of Tian (田).</sub>
