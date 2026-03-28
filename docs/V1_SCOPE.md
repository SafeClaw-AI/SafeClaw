# SafeClaw 当前公开范围

> 本文件已替代早期的 "V1 功能范围" 文档。
> 当前仓库以最新 `README.md`、`specs/`、`tests/contracts/`、`tools/checks/` 为准。

---

## 当前定位

SafeClaw 当前公开仓库的重点不是完整产品功能清单，
而是 **Phase 0 协议层冻结**：

- 用 `specs/` 固定核心契约
- 用 `tests/contracts/` 固定合同测试
- 用 `tools/checks/` 固定一致性、版本、结构与命名门禁
- 用 `tools/codegen/`、`tools/schema_diff/`、`specs/manifests/` 预留后续自动化入口

一句话：
**先把规矩定死，再把实现铺开。**

---

## 当前公开真源

以下内容共同构成当前公开层的有效范围：

| 路径 | 作用 |
| --- | --- |
| `README.md` | 对外定位、愿景、公开内容与沟通方式 |
| `VERSION` | 当前公开协议版本 |
| `specs/` | 协议层单一真源 |
| `tests/contracts/` | 从协议推出的合同测试 |
| `tools/checks/` | 一致性 / 版本 / 结构 / 自检门禁 |
| `tools/lint/` | 命名稳定性门禁 |
| `.github/workflows/contracts.yml` | CI 自动化门禁 |

---

## 当前在范围内的工作

这些工作与当前蓝图一致，可以持续推进：

- 扩展 `specs/` 既有契约的测试覆盖
- 加强跨文件一致性检查
- 加强命名、版本、结构门禁
- 为 codegen / schema diff / manifest 保留稳定入口
- 清理公开文档中的历史漂移，确保对外口径一致

---

## 当前不应在公开仓库中假定已成立的内容

如果没有被最新 `specs/` 或当前 README 明确声明，就不应在公开文档里写成既成事实：

- 流程录制 / 键鼠回放
- Web Doctor 的具体交互体验
- 完整 UI 功能与页面承诺
- 真模型接入细节
- 尚未冻结的新协议字段、新状态、新错误码、新 SPI 字段

这些方向不是永久否定，
而是 **在当前公开协议尚未定义前，不提前承诺**。

---

## 当前成功标准

当前公开层是否达标，主要看以下几件事：

- `specs/` 无语义冲突
- 合同测试持续通过
- 一致性 / 版本 / 结构 / 命名门禁持续通过
- README 与公开文档不互相矛盾
- 后续 AI 可以基于公开协议稳定生成、审阅、扩展

---

## 当前 selfcheck policy

- `tools/checks/selfcheck.py` 与 `.github/workflows/contracts.yml` 会先跑 `ledger_index_manifest.py`
- 然后依次跑 `check_ledger_alignment.py`、`check_consistency.py`、`check_versions.py`、`check_structure.py`、`check_scaffold.py`、`check_public_docs.py`
- `Contract tests` 与其他后续门禁会显式后置在这条 ledger policy chain 之后
