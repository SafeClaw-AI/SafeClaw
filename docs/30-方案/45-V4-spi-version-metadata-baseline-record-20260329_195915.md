# V4 spi version metadata baseline 记录

## 时间
- `2026-03-29 19:59:15 +0800`

## 本轮动作
- 先用 `tests/contracts/test_version_check.py` 补上一条当前基线合同，让 `collect_errors()` 直接覆盖 `check_versions.py` 的完整规则，而不只盯 ledger phase。
- 修平 `specs/spi/` 下 6 个安全抽象占位 JSON：补齐 `version`、`$schema`、`$id` 与 `title`，让它们真正满足 spec contract 元数据要求。
- 执行 `python tools/codegen/regenerate_all.py`，把 `generated/` 三个 target 的 manifest 与 root index 同步到最新 22 份 spec 基线。
- 顺带复核完整协议门禁链；最终静默 `selfcheck` 已通过，并把输出留存在 `target/mvp/selfcheck-20260329-195318.log`。

## 为什么做这刀
- 之前 `selfcheck` 一直被 `specs/spi/*` 缺少 `version` 卡在 `check_versions.py`，这是当前最直接、最影响全链验证的历史阻塞。
- 既然已经开始修这批 `spi` 文件，就顺手把同批 contract metadata 与 generated 索引旧债一起收干净，长期收益高于只补 6 个 `version` 字段后留下下一层红灯。

## 结果
1. `tests/contracts/test_version_check.py`
   - 新增 `test_version_consistency_passes_current_baseline()`
   - 以后 `check_versions.py` 再出现 spec/version 漏口，会直接在合同层红灯
2. `specs/spi/boot-integrity/software-check.json`
   - `specs/spi/boot-integrity/hardware-check-placeholder.json`
   - `specs/spi/keystore/software-keystore.json`
   - `specs/spi/keystore/hardware-keystore-placeholder.json`
   - `specs/spi/storage-encryption/software-encryption.json`
   - `specs/spi/storage-encryption/hardware-encryption-placeholder.json`
   - 以上 6 个文件现已补齐 `version/$schema/$id/title`
3. `generated/rust/manifest.json`
   - `generated/python/manifest.json`
   - `generated/ts/manifest.json`
   - `generated/index.json` / `generated/root_index.json` / `generated/targets.json`
   - 已与当前 22 份 spec 基线重新同步
4. 全链门禁
   - `check_versions.py`、`test_specs_contracts.py`、`test_generated_indexes.py`、`check_tooling_smoke.py`、`check_mvp_operator_flow.py`、`check_examples_smoke.py`、`check_generated_sync.py` 与静默 `selfcheck` 全部通过

## 最小验证
- `python -m unittest tests.contracts.test_version_check tests.contracts.test_specs_contracts tests.contracts.test_generated_indexes -v`
- `python tools/checks/check_versions.py`
- `python tools/checks/check_tooling_smoke.py`
- `python tools/checks/check_mvp_operator_flow.py`
- `python tools/checks/check_examples_smoke.py`
- `python tools/checks/check_generated_sync.py`
- `python tools/checks/selfcheck.py *> target/mvp/selfcheck-20260329-195318.log`
- `git diff --check`

## 下一步
- `selfcheck` 全绿后，主线瓶颈已从历史 spec 阻塞切回到 `docs/reference/01` 的下一层硬门禁扩容。
- 若继续亮式推进，优先在“更多单异常无上下文降级形态”与“单函数 / 单类体量红线”之间选最小高复利切口。
