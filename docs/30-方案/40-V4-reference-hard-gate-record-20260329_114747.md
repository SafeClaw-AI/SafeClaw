# V4 reference hard gate 记录

## 时间
- `2026-03-29 11:47:47 +0800`

## 本轮动作
- 把 `docs/reference/` 的可机器化规则下沉进 `tools/checks/check_scaffold.py`，不再只靠人工提醒执行。
- 让 `check_scaffold.py` 直接消费 `docs/30-方案/02-V4-目录锁定清单.md`，把当前获批根目录/根文件白名单变成 fail-closed 校验。
- 新增 reference 路径禁词检查，直接拦截 `最终版`、`临时版`、`new2`、`test1` 这类无语义命名。
- 扩大 `tests/contracts/test_scaffold_check.py`，锁住 reference 真源文件、根目录锁定覆盖面、禁词常量与当前基线。
- 同步更新 `tools/checks/README.md`、`tools/README.md` 与 `tools/checks/check_public_docs.py`，把“reference 已硬门禁化”的入口说明也锁进公开文档门禁。

## 为什么做这刀
- `docs/reference/` 之前只有高优先级口径与纠偏说明，但仓库自动化里仍缺少直接 fail-closed 的执行层。
- 继续只补消费点，长期会让规范停留在“知道要遵守”，而不是“机器保证不漂移”。
- 先把 reference 落成硬门禁，后续所有切片都会自动继承，不需要每轮再人工提醒，长期复利高于继续补单个说明入口。

## 结果
1. `tools/checks/check_scaffold.py`
   - 新增 reference 真源存在性检查
   - 新增目录锁定清单关键标记检查
   - 新增根目录/根文件白名单校验
   - 新增路径禁词命名校验
2. `tests/contracts/test_scaffold_check.py`
   - 锁住 `REFERENCE_REQUIRED_FILES`
   - 锁住 `FORBIDDEN_NAME_TOKENS`
   - 锁住当前根目录基线必须被目录锁定清单覆盖
   - 锁住 `collect_reference_guardrail_errors()` 当前必须通过
3. `tools/checks/README.md` 与 `tools/README.md`
   - 明确 `check_scaffold.py` 已把 `docs/reference/` 与 `02-V4-目录锁定清单.md` 转成硬门禁
4. `tools/checks/check_public_docs.py`
   - 把上述入口说明纳入公开文档门禁，避免后续说明回退成“仍靠人工提醒”

## 最小验证
- `python -m py_compile tools/checks/check_scaffold.py tools/checks/check_public_docs.py tests/contracts/test_scaffold_check.py tests/contracts/test_public_docs_check.py`
- `python -m unittest tests.contracts.test_scaffold_check tests.contracts.test_public_docs_check -v`
- `python tools/checks/check_scaffold.py`
- `python tools/checks/check_public_docs.py`
- `python tools/checks/selfcheck.py`：已尝试，当前仍被既有 `specs/spi/*` 占位 JSON 缺少 `version` 的历史问题阻断在 `check_versions.py`，本轮未扩大修复

## 下一步
- 继续把 `docs/reference/01-反屎山AI研发执行总纲（Codex专用浓缩对照版）.md` 里还未机器化的红线，优先转成可执行校验，例如无主 TODO、空异常处理、超长函数/类等。
- 若与现有存量代码冲突，仍按“先补测试、再小步整改、避免一次性大搬家”推进。
