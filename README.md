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

## 文档结构

SafeClaw 采用双层文档结构：

- **README.md** - 项目介绍（你正在看的）
- **[docs/](docs/)** - 公开技术文档
  - 实现策略、架构说明、使用指南
- **[specs/](specs/)** - 协议层规范（完全公开）
  - [Worker 状态机](specs/state-machines/worker_lifecycle.json) - 任务生命周期
  - [副作用账本](specs/schemas/effect_ledger.json) - 外部行为记录
  - [动作分级](specs/schemas/action_tiers.json) - 操作风险分类
  - [错误码](specs/error-codes/sys_errors.json) - 结构化错误信息
  - [预检策略](specs/config/preflight.json) - 风险预判规则
  - [扩展接口](specs/spi/base_fields.json) - 插件标准接口
- **[tests/contracts/](tests/contracts/)** - 合同测试
- **[tools/](tools/)** - 工具链与检查脚本
- **[tools/checks/](tools/checks/)** - 协议层门禁与总验收入口

内部设计文档不在公开仓库中。如需了解核心设计理念，请参考公开的协议层规范。

为什么先公开协议层？  
因为**规矩比功能重要**。能力可以慢慢加，但底线必须一开始就定死。

---

## 当前状态

```
版本：3.2.0
阶段：Phase 0 — 协议真源闭环 + Win11 本地 MVP 已可手用 ✅
重点：本地 MVP 操作链 + 个人生产位 Python/Tkinter 小面板 + `archive-note -> status -> undo`
可体验路径：仓库维护入口（`tools/mvp/`）+ 个人生产位入口（`%USERPROFILE%\.safeclaw-personal-production\`）

实现进度：
- ✅ 协议层 specs 已对齐 v3.2（effect_ledger、worker_lifecycle、task_concurrency）
- ✅ 合同测试框架已搭建，smoke test 已重构（快照恢复机制）
- ✅ 四阶段/探针/fencing/reconcile 合同夹具的第一轮确定性对齐已完成
- ✅ Rust 核心（safeclaw-core）单 worker 闭环已跑通
- ✅ 个人生产位 Python/Tkinter 小面板已部署，支持 archive-note / status / undo
- ✅ 当前工作区 `selfcheck.py` 已恢复全绿，`tests/contracts` 925 项合同测试全部通过
```

SafeClaw 还在很早期。  
很多功能还没有，很多体验还会粗糙。

**如果你不懂代码：** 现在已经有一层给主人自用的本地中文小面板，当前通过 `.cmd/.ps1` launcher 启动 Python/Tkinter 面板；它不是 Tauri/React 图形界面，也还不是对外开箱即用的完整产品。如果你只是想自己先试，请直接走下方“当前可手动体验的本地 MVP”里的个人生产位入口。
**如果你是开发者：** 欢迎来看我们的协议层，提 Issue、挑毛病、贡献代码都欢迎。

但方向不会变：  
**做一个让普通人用起来安心的自动化系统。**

我们慢慢来，但会认真做。

当前仓库已经把脚手架治理、公开文档门禁与确定性合同假失败压下去；下一阶段重点转到 specs → tests → implementation 的 codegen 单向溯源，以及 Rust 单测覆盖率建设。

### 版本说明

- 根目录 `VERSION` 里的当前版本号（当前为 `3.2.0`）是公开协议版本，`specs/` 与公开合同测试按这一层对齐。
- `safeclaw-core` / `safeclaw-sqlite` 的 `Cargo.toml` 当前仍是 `0.1.0`，这表示 Rust crate 迭代号，不等同于对外协议版本。
- 当前仓库对外先以协议版本沟通；crate 版本主要服务内部 Rust 包演进，现阶段不要求与协议版本强行同步。


## 当前可手动体验的本地 MVP

下面只列当前已经能实际进入的本地入口。
在当前 Windows GNU 开发环境下，仓库主人已经可以用 **Python/Tkinter 小面板 + 生产位** 跑最小闭环。

- 主人自用入口：先看 `tools/mvp/PERSONAL_MVP_PLAYBOOK.md`，优先使用 `%USERPROFILE%\.safeclaw-personal-production\safeclaw-personal-panel.cmd` / `%USERPROFILE%\.safeclaw-personal-production\safeclaw-personal-panel.ps1`；CLI 备份入口仍保留 `%USERPROFILE%\.safeclaw-personal-production\safeclaw-personal.cmd` / `%USERPROFILE%\.safeclaw-personal-production\safeclaw-personal.ps1`
- 维护层入口：统一从 `safeclaw.cmd` / `safeclaw.ps1` / `tools/mvp/safeclaw_mvp.cmd` 进入；本机日用白名单看 `tools/mvp/OPERATOR_PLAYBOOK.md`，完整命令参考看 `tools/mvp/README.md`

这里的 `safeclaw-personal-panel.*` 是启动个人 Python/Tkinter 小面板的 launcher；同时保留 CLI 备份入口。

### 最短上手路径

主人自用先走个人生产位：

```bat
%USERPROFILE%\.safeclaw-personal-production\safeclaw-personal-panel.cmd
```

若面板当时不可用，再退回 CLI 备份路径：

```bat
%USERPROFILE%\.safeclaw-personal-production\safeclaw-personal.cmd status
%USERPROFILE%\.safeclaw-personal-production\safeclaw-personal.cmd archive-note --name "Morning Note" --content "先跑一轮"
%USERPROFILE%\.safeclaw-personal-production\safeclaw-personal.cmd undo
```

维护 / 排障 / 开发先走维护入口：

```bat
safeclaw.cmd workspace --name demo
safeclaw.cmd doctor
safeclaw.cmd service-run --reset --task-id task-demo --limit 1 --report
```

这一步只负责把你带到维护入口。继续按当前 **local-only** MVP 的本机日用白名单推进时，请直接看 `tools/mvp/OPERATOR_PLAYBOOK.md`；字段级合同与权限细节统一看 `tools/mvp/README.md`。

维护前若要先判定门禁，可优先执行：

```bat
safeclaw.cmd preflight --action service-run
safeclaw.cmd preflight --action ai-reason
safeclaw.cmd service-status --limit 5
```

其中 `preflight --action ai-reason` 与 `service-status` 顶层 `offline_gate` 会稳定回显“当前离线 MVP 还不能调用 AI 提供方”这一事实；更细权限覆盖、`--enforce-permission` 与 `--preflight-action ai-reason` 的组合规则，统一看 `tools/mvp/README.md`。

如果要确认当前包装层仍处于可交付状态，最小验收入口保留如下；failed / uncertain / executed_assumed 的收口顺序仍以 `tools/mvp/OPERATOR_PLAYBOOK.md` 为准：

```bat
safeclaw.cmd verify
safeclaw.cmd verify --json
```

### 当前最小能力

- `workspace` / `doctor`：固定默认 `db` / `output`，并确认 launcher、Rust/linker、session/workspace 路径与当前离线 runtime 快照是否健康。
- `preflight` / `service-status`：一个负责显式预检，一个负责查看 queue / lease / coordination 摘要；`ai-reason` 用来稳定显示“当前 local-only MVP 还不能调用 AI 提供方”这一阻断结果，`service-status` 会同步镜像 `runtime_profile` / `model_provider` / `sidecar` / `offline_gate` 与 recent task 的 `next_*` 提示。
- `service-*` 组合动作：`service-run` / `service-retry` / `service-recover` / `service-resume` / `service-reconcile` 分别覆盖正常执行、failed 重试、uncertain 恢复、hibernated 恢复与 `executed_assumed` 收口；白路径顺序统一以 `tools/mvp/OPERATOR_PLAYBOOK.md` 为准。
- `session` / `sessions` / `use` / `forget`：管理“最近一次成功会话”的记忆，减少重复传参。
- `verify`：确认当前包装层仍处于可交付状态。
- 常用 demo / service / seed / recover / session / workspace / doctor / preflight / verify 动作均支持 `--json`，统一返回 `{ok, action, schema_version, result|error}`；字段级合同细节见 `tools/mvp/README.md`。

### 当前边界

- 这是 **MVP-first** 路线，不是最终产品形态
- 当前更像单 worker 的本地治理操作台，不是完整多用户系统
- 当前最适合开发者或愿意手动执行命令的早期体验者
- README 中提到的 Tauri + React 与 Python sidecar 目前仍是目标架构，不是当前 MVP 已交付实现
- 当前已经能手动跑通正常执行、失败重试、不确定恢复与环境自检，但还没有正式的 Tauri/React GUI、安装器与长期稳定分发入口
---

## 技术栈

> 给想了解技术细节的朋友。

| 层 | 当前状态 / 技术 | 说明 |
|----|-----------------|------|
| 核心引擎 | Rust | 当前已实现的运行时主干 |
| 当前入口 | `.cmd` / `.ps1` launcher + Python/Tkinter 小面板 + Rust CLI | 当前已交付的是轻量本地小面板与 CLI 备份入口 |
| 规划界面 | Tauri 2.x + React | 这是目标方向，当前仓库尚未实现 GUI |
| 规划 AI 调用 | Python sidecar | 这是目标方向，当前 local-only MVP 仍未接通 provider / sidecar |
| 数据 | SQLite | 单文件、零依赖、你能直接打开看 |
| 契约真源 | specs/ (JSON Schema) | 所有代码从这里生成，不会走偏 |

---

## 许可

SafeClaw 采用 [GPL-3.0](LICENSE) 开源许可。

简单说：

- **个人使用、学习、研究**：完全自由
- **修改后分发**：必须继续开源
- **商业闭源集成**：可联系申请商业授权

我们选择 GPL，是因为 SafeClaw 希望把核心安全能力持续开放地演进，而不是锁进任何一家的围墙里。当前项目还早，先把协议和核心能力做好；后续若项目成熟，再通过高级工具和企业服务获取合理收入。

---

## 联系

📮 **safeclaw.ai@gmail.com**

合作、授权、建议都欢迎。
如果不是私密内容，更推荐优先在 GitHub Discussions / Issues 里交流：
**https://github.com/SafeClaw-AI/SafeClaw**

邮件和留言我们都会认真看；但项目仍在早期，未必能做到一一及时回复，还请见谅。

---

## English Summary

SafeClaw is an early automation system aimed at ordinary users, not just developers.
Its core idea is simple:
**automation should stay understandable, controllable, and recoverable.**

The public repo is still protocol-first. There is already an owner-only Chinese local small panel backed by Python/Tkinter plus a personal production slot on Win11, but it is not yet the planned Tauri/React desktop app or a public turnkey product. The current local MVP operator path lives under `tools/mvp/`.

The root `VERSION` file tracks the public protocol version. The Rust crates keep separate crate versions for internal package iteration, so those numbers are not expected to match the public protocol version one-to-one.

SafeClaw still tries to keep a few rules stable:

- explain before acting
- ask for confirmation when risk is involved
- keep a clear effect ledger of external actions
- preserve stop, recover, and rollback paths whenever possible
- keep core control on the user's own machine

Licensed under GPL-3.0. Commercial closed-source licensing is available upon request.

Current status: Version `3.2.0` · Phase `0` · protocol source-of-truth closed loop, with an early Win11 local MVP operator path under `tools/mvp/`.

📮 **safeclaw.ai@gmail.com** · [GitHub](https://github.com/SafeClaw-AI/SafeClaw)

---

<sub>SafeClaw™ is a trademark of Tian (田).</sub>
