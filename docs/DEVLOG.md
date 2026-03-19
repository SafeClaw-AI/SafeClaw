# SafeClaw 开发日志

> 说明：当前仓库的公开层以 `README.md`、`VERSION`、`specs/`、`tests/contracts/`、`tools/checks/` 为准。
> 更早历史如有需要，可再基于 Git 提交记录补齐。

## 2026-03-20

### 协议层门禁补强
- 新增 `tools/lint/check_naming.py`，把稳定标识的命名规则收口为自动 lint。
- 将 naming lint 接入 `tools/checks/selfcheck.py` 与 `.github/workflows/contracts.yml`。
- 补强 `tests/contracts/`，新增协议不变量测试，覆盖 Worker 关键状态、三账本提交协议、Preflight 严格降级规则、错误码唯一性、SPI 注册表等。

### 公开文档对齐
- `README.md` 补齐英文摘要，并在联系方式中明确：公开问题更推荐在 GitHub Discussions / Issues 交流。
- 重写 `docs/V1_SCOPE.md` 与 `docs/V1_TASK_TRIAGE.md`，清理与当前协议层不一致的旧方向描述。
- 明确当前公开仓库的重点是 `Phase 0` 协议层冻结，而不是提前承诺尚未在 specs 中定义的产品功能。

## 2026-03-17

### 文档收口：V1 范围与定位
- 新增 `docs/V1_SCOPE.md` 与 `docs/V1_TASK_TRIAGE.md` 的最早版本，用于整理当时的方向性思考。
- 随着协议层与蓝图定稿，这批内容已被后续版本替换，不再作为当前公开真源。

### 文档修正：商标说明
- 调整 `README.md` 中的商标说明。
- 统一为当前文案：`SafeClaw™ is a trademark of Tian (田).`
