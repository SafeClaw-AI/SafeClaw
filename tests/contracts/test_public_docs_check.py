from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tests.contracts import REPO_ROOT
from tools.checks.check_public_docs import (
    BOUNDARY_NOTE_DECISION,
    BOUNDARY_NOTE_FUSION,
    BOUNDARY_NOTE_SCOPE,
    BOUNDARY_NOTE_TITLE,
    CURRENT_CLOSEOUT_OVERVIEW_TITLE,
    CURRENT_SUBMISSION_EXECUTION_SUMMARY_TITLE,
    BATCH_ONE_PRE_SUBMIT_CHECKLIST_TITLE,
    BATCH_TWO_PRE_SUBMIT_CHECKLIST_TITLE,
    BATCH_THREE_PRE_SUBMIT_CHECKLIST_TITLE,
    CURRENT_SUBMISSION_CLOSEOUT_TABLE_TITLE,
    CURRENT_SUBMISSION_READINESS_TABLE_TITLE,
    CHANGELOG_FILE,
    CHANCELLOR_ENTRY_BASELINE_FILE,
    CHANCELLOR_PRODUCT_REBASELINE_FILE,
    DECISIONS_FILE,
    DEV_PLAN_FILE,
    FORBIDDEN_MARKERS,
    LINT_README_FILE,
    MVP_PROGRESS_FILE,
    MVP_README_FILE,
    OPERATOR_PLAYBOOK_FILE,
    PUSH_LOG_FILE,
    README_FILE,
    REFERENCE_HYGIENE_FILE,
    ROOT_ARCHITECTURE_FILE,
    ROOT_SSOT_ROLE_FORBIDDEN_MARKERS,
    REQUIRED_MARKERS,
    STATUS_FILE,
    collect_errors,
    collect_reference_rebaseline_errors,
    collect_root_ssot_role_errors,
)


class PublicDocsCheckTest(unittest.TestCase):
    def _assert_required_markers(
        self,
        expected_entries: dict[Path, list[str]],
        label: str,
    ) -> None:
        for doc_file, expected_markers in expected_entries.items():
            with self.subTest(**{label: doc_file.relative_to(REPO_ROOT).as_posix()}):
                self.assertIn(doc_file, REQUIRED_MARKERS)
                self.assertEqual(REQUIRED_MARKERS[doc_file], expected_markers)

    def test_boundary_note_files_are_guarded_by_public_docs_check(self) -> None:
        expected_entries = {
            DEV_PLAN_FILE: [
                BOUNDARY_NOTE_TITLE,
                BOUNDARY_NOTE_DECISION,
                BOUNDARY_NOTE_FUSION,
                "docs/chancellor-mode/v2/",
                "docs/records/开发计划.md",
                "docs/records/MVP_PROGRESS.md",
                "docs/records/PUSH_LOG.md",
                "tools/mvp/",
                "archive-note -> undo",
            ],
            MVP_PROGRESS_FILE: [
                BOUNDARY_NOTE_TITLE,
                BOUNDARY_NOTE_DECISION,
                BOUNDARY_NOTE_FUSION,
                CURRENT_CLOSEOUT_OVERVIEW_TITLE,
                "边界治理",
                "自检治理",
                "个人部署链",
                "当前工作区已干净",
                "未归类改动：0 项",
                "只作为历史切片与后期拼接融合参考",
                "不作为当前主线真源",
                "`tools/mvp/chancellor_panel.py` 只保留快照消费与兼容检查",
                "`python -X utf8 tools/checks/check_public_docs.py` 必须继续全绿",
                "`python -X utf8 tools/checks/selfcheck.py` 继续作为唯一总验收入口",
                "`tools/checks/worktree_groups.py` 继续输出摘要优先、明细随后的人话收口视图",
                "`.gitattributes` 继续作为当前仓库的换行真源",
                "`tmp/` 只允许放临时验证产物",
                "`safeclaw-personal.cmd` / `safeclaw-personal.ps1` 继续只服务 `archive-note -> status -> undo` 个人金线",
                "`tools/mvp/safeclaw_personal_deploy.py` 只保留 `deploy / rollback / status`",
                "回滚只切 release 指针，不碰个人数据目录",
                "个人部署链继续与外部丞相模式隔离",
                "本轮已提交 `80fe243`",
                "本轮已提交 `f6ca6a1`",
                "本轮已提交 `7937fa4`",
                "当前这一轮三组治理已全部完成提交，工作区干净",
                "提交/归档顺序、批次清单与收口表统一以 `docs/records/PUSH_LOG.md` 为准，本表不再重复展开提交层细节",
                "若后续开启新一轮迭代，先刷新顶部摘要再新增改动，不沿用本轮旧数字",
                "docs/chancellor-mode/v2/",
                "历史切片",
            ],
            PUSH_LOG_FILE: [
                BOUNDARY_NOTE_TITLE,
                BOUNDARY_NOTE_DECISION,
                BOUNDARY_NOTE_FUSION,
                CURRENT_SUBMISSION_EXECUTION_SUMMARY_TITLE,
                CURRENT_SUBMISSION_CLOSEOUT_TABLE_TITLE,
                "当前工作区总改动：0；当前工作区已干净；未归类：0。",
                "本轮三批提交已完成：边界治理 13 / 自检治理 8 / 个人部署链 3。",
                "`7937fa4 feat: lock personal deploy governance closeout`",
                "`f6ca6a1 test: lock selfcheck governance closeout`",
                "`80fe243 docs: lock boundary governance closeout`",
                "下一步：若开启新一轮迭代，先刷新本摘要与分组表，再新增批次清单。",
                "| 边界治理 | 已提交 | `80fe243` |",
                "| 自检治理 | 已提交 | `f6ca6a1` |",
                "| 个人部署链 | 已提交 | `7937fa4` |",
                "当前三组已完成提交，工作区干净。",
                "若后续出现新改动，重新生成分组摘要和批次清单，不沿用本轮旧数字。",
                "历史流水",
            ],
            REFERENCE_HYGIENE_FILE: [
                "先分类,再落盘",
                "绝对红线禁令",
                "自动化门禁",
            ],
        }

        self._assert_required_markers(expected_entries, label="doc")

    def test_current_ledger_docs_forbid_stale_root_path_instructions(self) -> None:
        expected_entries = {
            README_FILE: [
                "当前公开协议版本号为 `",
                "## 当前入口边界",
                "当前稳定入口仍然是本地 operator 路径，而不是公有 GUI 产品：",
                "The current stable operator path is still local-only",
                "协议与治理真源在 `specs/`、`VERSION`、`docs/reference/` 与 `docs/30-方案/02-V4-目录锁定清单.md`",
            ],
            DEV_PLAN_FILE: [
                "- 当前 SafeClaw 主线以 `README.md`、`开发计划.md`、`tools/mvp/` 现行最小闭环为准；`docs/chancellor-mode/v2/` 仅保留外部模式历史方案与后期拼接融合参考。",
                "- 每轮完成后必须同步：`MVP_PROGRESS.md`、`PUSH_LOG.md`、`开发计划.md`。",
                "- 若行为变化可见，必须同步 `MVP_PROGRESS.md`、`PUSH_LOG.md` 和 `开发计划.md`。",
                "- 台账写法要求：`MVP_PROGRESS.md`、`PUSH_LOG.md` 尽量使用中文、短句、小学生能懂；先写“做了什么”，再写“有什么用”。",
                "- 台账：`MVP_PROGRESS.md`、`PUSH_LOG.md`",
            ],
            MVP_PROGRESS_FILE: [
                "`MVP_PROGRESS.md`、`PUSH_LOG.md` 已接入公开文档检查",
                "提交/归档顺序、批次清单与收口表统一以 `PUSH_LOG.md` 为准，本表不再重复展开提交层细节",
            ],
        }
        for doc_file, forbidden_markers in expected_entries.items():
            with self.subTest(doc=doc_file.relative_to(REPO_ROOT).as_posix()):
                self.assertIn(doc_file, FORBIDDEN_MARKERS)
                self.assertEqual(FORBIDDEN_MARKERS[doc_file], forbidden_markers)

    def test_root_ssot_suite_forbids_cross_role_sections(self) -> None:
        expected_entries = {
            README_FILE: [
                "## 本周进度",
                "## 当前风险",
                "## 当前瓶颈",
                "## 下周计划",
            ],
            STATUS_FILE: [
                "## 模块划分",
                "## 依赖关系",
                "## 不变量（必须长期成立）",
                "## 关键设计原则",
            ],
            CHANGELOG_FILE: [
                "## 本周进度",
                "## 当前风险",
                "## 当前瓶颈",
                "## 下周计划",
            ],
            DECISIONS_FILE: [
                "## 本周进度",
                "## 当前风险",
                "## 当前瓶颈",
                "## 下周计划",
            ],
            ROOT_ARCHITECTURE_FILE: [
                "## 本周进度",
                "## 当前风险",
                "## 当前瓶颈",
                "## 下周计划",
                "## 更新日志",
            ],
        }
        for doc_file, forbidden_markers in expected_entries.items():
            with self.subTest(doc=doc_file.relative_to(REPO_ROOT).as_posix()):
                self.assertIn(doc_file, ROOT_SSOT_ROLE_FORBIDDEN_MARKERS)
                self.assertEqual(ROOT_SSOT_ROLE_FORBIDDEN_MARKERS[doc_file], forbidden_markers)

    def test_collect_root_ssot_role_errors_rejects_cross_role_marker(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            for source_file in ROOT_SSOT_ROLE_FORBIDDEN_MARKERS:
                temp_path = temp_root / source_file.name
                temp_path.write_text("# placeholder\n", encoding="utf-8")

            readme_path = temp_root / README_FILE.name
            readme_path.write_text("# SafeClaw\n\n## 本周进度\n", encoding="utf-8")

            errors = collect_root_ssot_role_errors(
                {
                    README_FILE: readme_path,
                    STATUS_FILE: temp_root / STATUS_FILE.name,
                    CHANGELOG_FILE: temp_root / CHANGELOG_FILE.name,
                    DECISIONS_FILE: temp_root / DECISIONS_FILE.name,
                    ROOT_ARCHITECTURE_FILE: temp_root / ROOT_ARCHITECTURE_FILE.name,
                }
            )

        self.assertTrue(
            any("README.md" in item and "## 本周进度" in item for item in errors)
        )

    def test_chancellor_entry_baseline_is_guarded_by_public_docs_check(self) -> None:
        expected_markers = [
            BOUNDARY_NOTE_DECISION,
            BOUNDARY_NOTE_FUSION,
            BOUNDARY_NOTE_SCOPE,
            "官方 Codex 面板",
            "`丞相状态`",
            "`丞相检查`",
            "`丞相版本`",
            "`丞相验板`",
        ]
        self.assertIn(CHANCELLOR_ENTRY_BASELINE_FILE, REQUIRED_MARKERS)
        self.assertEqual(REQUIRED_MARKERS[CHANCELLOR_ENTRY_BASELINE_FILE], expected_markers)

    def test_chancellor_panel_truth_source_is_guarded_by_public_docs_check(self) -> None:
        panel_truth_file = (
            REPO_ROOT / "docs" / "chancellor-mode" / "v2" / "02-m2-panel-command-truth-source.md"
        )
        expected_markers = [
            BOUNDARY_NOTE_DECISION,
            BOUNDARY_NOTE_FUSION,
            BOUNDARY_NOTE_SCOPE,
            "官方 Codex 面板",
            "`丞相状态`",
            "`丞相检查`",
            "`丞相版本`",
            "`丞相验板`",
            "`mode`",
            "`stability`",
            "`next_step`",
            "`checks_run`",
            "`version_source`",
            "`steps`",
        ]
        self.assertIn(panel_truth_file, REQUIRED_MARKERS)
        self.assertEqual(REQUIRED_MARKERS[panel_truth_file], expected_markers)

    def test_chancellor_product_rebaseline_is_guarded_by_public_docs_check(self) -> None:
        expected_markers = [
            BOUNDARY_NOTE_DECISION,
            BOUNDARY_NOTE_FUSION,
            BOUNDARY_NOTE_SCOPE,
            "`M2-1` / `M2-2` 已经证明",
            "可读账单",
            "真实任务",
            "`undo`",
            "官方 Codex 面板",
            "终端仍只保留给维护",
            "M2-P0-1",
            "M2-P0-4",
        ]
        self.assertIn(CHANCELLOR_PRODUCT_REBASELINE_FILE, REQUIRED_MARKERS)
        self.assertEqual(REQUIRED_MARKERS[CHANCELLOR_PRODUCT_REBASELINE_FILE], expected_markers)

    def test_root_readme_is_guarded_by_public_docs_check(self) -> None:
        expected_entries = {
            README_FILE: [
                "specs/",
                "tests/contracts/",
                "tools/checks/",
                "tools/mvp/OPERATOR_PLAYBOOK.md",
                "local-only",
                "稳定入口边界",
                "08-V4-ledger-index-manifest.json",
                "STATUS.md",
                "CHANGELOG.md",
                "DECISIONS.md",
                "ARCHITECTURE.md",
                "Python/Tkinter",
                "Tauri + React",
                "protocol-first",
                "模型路由矩阵（稳定边界）",
                "高层路线图",
                "成功指标",
                "English Summary",
                "The stable operator path is local-only",
            ],
        }
        self._assert_required_markers(expected_entries, label="readme")

    def test_docs_readme_is_guarded_by_public_docs_check(self) -> None:
        expected_entries = {
            REPO_ROOT / "docs" / "README.md": [
                "README.md",
                "STATUS.md",
                "CHANGELOG.md",
                "DECISIONS.md",
                "ARCHITECTURE.md",
                "safeclaw-core/ARCHITECTURE.md",
                "L0",
                "L1",
                "L2",
                "L3",
                "DEVLOG.md",
                "V1_SCOPE.md",
                "V1_TASK_TRIAGE.md",
                "02-V4-目录锁定清单.md",
                "08-V4-ledger-index-manifest.json",
                "generated/index.json",
                "docs/records/",
                "docs/chancellor-mode/v2/",
                "selfcheck.py",
                "tests/contracts/",
                "已迁移台账的现行状态、历史记录与审计留痕落点",
            ],
        }
        self._assert_required_markers(expected_entries, label="readme")

    def test_docs_readme_forbids_stale_records_archive_wording(self) -> None:
        docs_readme_file = REPO_ROOT / "docs" / "README.md"
        expected_markers = [
            "旧 `开发计划.md`、`MVP_PROGRESS.md`、`PUSH_LOG.md` 的归档落点",
            "协议与治理真源仍以 `specs/`、`VERSION`、`docs/reference/` 与 `docs/30-方案/02-V4-目录锁定清单.md` 为准",
        ]
        self.assertIn(docs_readme_file, FORBIDDEN_MARKERS)
        self.assertEqual(FORBIDDEN_MARKERS[docs_readme_file], expected_markers)

    def test_scope_doc_is_guarded_by_public_docs_check(self) -> None:
        expected_entries = {
            REPO_ROOT / "docs" / "V1_SCOPE.md": [
                "STATUS.md",
                "ARCHITECTURE.md",
                "DECISIONS.md",
                "CHANGELOG.md",
                "docs/README.md",
                "VERSION",
                "Phase 0",
                "specs/",
                "docs/reference/",
                "02-V4-目录锁定清单.md",
                "08-V4-ledger-index-manifest.json",
                "tests/contracts/",
                "tools/checks/",
                "tools/lint/",
                "selfcheck.py",
                "ledger_index_manifest.py",
                "check_ledger_alignment.py",
                "check_consistency.py",
                "check_versions.py",
                "check_structure.py",
                "check_scaffold.py",
                "check_public_docs.py",
                "Contract tests",
            ],
        }
        self._assert_required_markers(expected_entries, label="scope")

    def test_scope_doc_forbids_stale_public_truth_summary(self) -> None:
        scope_file = REPO_ROOT / "docs" / "V1_SCOPE.md"
        expected_markers = [
            "当前仓库以最新 `README.md`、`specs/`、`tests/contracts/`、`tools/checks/` 为准。",
            "## 当前公开真源",
        ]
        self.assertIn(scope_file, FORBIDDEN_MARKERS)
        self.assertEqual(FORBIDDEN_MARKERS[scope_file], expected_markers)

    def test_devlog_doc_is_guarded_by_public_docs_check(self) -> None:
        expected_entries = {
            REPO_ROOT / "docs" / "DEVLOG.md": [
                "STATUS.md",
                "ARCHITECTURE.md",
                "DECISIONS.md",
                "CHANGELOG.md",
                "docs/README.md",
                "VERSION",
                "README.md",
                "specs/",
                "docs/reference/",
                "02-V4-目录锁定清单.md",
                "08-V4-ledger-index-manifest.json",
                "Phase 0",
                "selfcheck.py",
                ".github/workflows/contracts.yml",
                "ledger_index_manifest.py",
                "check_ledger_alignment.py",
                "check_consistency.py",
                "check_versions.py",
                "check_structure.py",
                "check_scaffold.py",
                "check_public_docs.py",
                "Contract tests",
            ],
        }
        self._assert_required_markers(expected_entries, label="devlog")

    def test_devlog_doc_forbids_stale_public_layer_summary(self) -> None:
        devlog_file = REPO_ROOT / "docs" / "DEVLOG.md"
        expected_markers = [
            "当前仓库的公开层以 `README.md`、`VERSION`、`specs/`、`tests/contracts/`、`tools/checks/` 为准。",
        ]
        self.assertIn(devlog_file, FORBIDDEN_MARKERS)
        self.assertEqual(FORBIDDEN_MARKERS[devlog_file], expected_markers)

    def test_implementation_strategy_doc_is_guarded_by_public_docs_check(self) -> None:
        expected_entries = {
            REPO_ROOT / "docs" / "IMPLEMENTATION_STRATEGY.md": [
                "STATUS.md",
                "ARCHITECTURE.md",
                "DECISIONS.md",
                "CHANGELOG.md",
                "docs/README.md",
                "VERSION",
                "README.md",
                "specs/",
                "docs/reference/",
                "02-V4-目录锁定清单.md",
                "08-V4-ledger-index-manifest.json",
                "tests/contracts/",
                "tools/checks/",
                "selfcheck.py",
                "ledger_index_manifest.py",
                "check_ledger_alignment.py",
                "check_consistency.py",
                "check_versions.py",
                "check_structure.py",
                "check_scaffold.py",
                "check_public_docs.py",
                "Contract tests",
            ],
        }
        self._assert_required_markers(expected_entries, label="implementation")

    def test_implementation_strategy_doc_forbids_stale_summary(self) -> None:
        implementation_file = REPO_ROOT / "docs" / "IMPLEMENTATION_STRATEGY.md"
        expected_markers = [
            "任何后续实现，优先保证与 `README.md`、`VERSION`、`specs/`、`tests/contracts/`、`tools/checks/` 一致。",
        ]
        self.assertIn(implementation_file, FORBIDDEN_MARKERS)
        self.assertEqual(FORBIDDEN_MARKERS[implementation_file], expected_markers)

    def test_root_ssot_suite_files_are_guarded_by_public_docs_check(self) -> None:
        expected_entries = {
            STATUS_FILE: [
                "当前状态（滚动更新）",
                "本周进度",
                "当前风险",
                "当前瓶颈",
                "下周计划",
                "README 主线",
                "specs/` → `tests/contracts/` → implementation",
                "local-only",
            ],
            CHANGELOG_FILE: [
                "更新日志",
                "SSOT 五件套",
                "README.md",
                "STATUS.md",
                "DECISIONS.md",
                "ARCHITECTURE.md",
                "check_public_docs.py",
            ],
            DECISIONS_FILE: [
                "架构与流程决策记录",
                "README.md",
                "STATUS.md",
                "CHANGELOG.md",
                "DECISIONS.md",
                "ARCHITECTURE.md",
                "specs/",
                "docs/reference/",
                "08-V4-ledger-index-manifest.json",
                "开发计划.md",
                "PUSH_LOG.md",
            ],
            ROOT_ARCHITECTURE_FILE: [
                "系统架构真源",
                "模块划分",
                "依赖关系",
                "不变量",
                "关键设计原则",
                "safeclaw-core/",
                "safeclaw-sqlite/",
                "tools/checks/",
                "tools/mvp/",
                "specs/",
                "08-V4-ledger-index-manifest.json",
            ],
        }
        self._assert_required_markers(expected_entries, label="doc")

    def test_decisions_and_architecture_forbid_stale_truth_source_summary(self) -> None:
        expected_entries = {
            DECISIONS_FILE: [
                "决策：协议与治理裁决层继续固定在 `specs/`、`VERSION`、`docs/reference/` 与目录锁定清单，不由根级说明文档反向定义字段。",
            ],
            ROOT_ARCHITECTURE_FILE: [
                "- `specs/` + `VERSION` + `docs/reference/` + `docs/30-方案/02-V4-目录锁定清单.md` -> 当前协议与治理裁决层",
                "- 协议字段与治理阈值只能由 `specs/`、`VERSION`、`docs/reference/` 与目录锁定清单裁决",
            ],
        }
        for doc_file, forbidden_markers in expected_entries.items():
            with self.subTest(doc=doc_file.relative_to(REPO_ROOT).as_posix()):
                self.assertIn(doc_file, FORBIDDEN_MARKERS)
                self.assertEqual(FORBIDDEN_MARKERS[doc_file], forbidden_markers)

    def test_operator_and_tooling_readmes_are_guarded_by_public_docs_check(self) -> None:
        expected_entries = {
            MVP_README_FILE: [
                "tools/mvp/README.md",
                ".github/workflows/contracts.yml",
                "ledger_index_manifest.py",
                "check_ledger_alignment.py",
                "check_consistency.py",
                "check_versions.py",
                "check_structure.py",
                "check_scaffold.py",
                "check_public_docs.py",
                "Contract tests",
            ],
            OPERATOR_PLAYBOOK_FILE: [
                "README.md",
                "workspace --name demo",
                "doctor",
                "service-run --report",
                "service-status --limit 5",
                "service-retry --report",
                "service-recover --report",
                "verify --json",
                "local-only",
                "ai-reason",
                "tools\\checks\\selfcheck.py",
                "ledger_index_manifest.py",
                "check_ledger_alignment.py",
                "check_consistency.py",
                "check_versions.py",
                "check_structure.py",
                "check_scaffold.py",
                "check_public_docs.py",
                "Contract tests",
            ],
            LINT_README_FILE: [
                "tools/lint/check_naming.py",
                ".github/workflows/contracts.yml",
                "ledger_index_manifest.py",
                "check_ledger_alignment.py",
                "check_consistency.py",
                "check_versions.py",
                "check_structure.py",
                "check_scaffold.py",
                "check_public_docs.py",
                "Contract tests",
            ],
        }
        self._assert_required_markers(expected_entries, label="readme")

    def test_reference_rebaseline_doc_passes_current_baseline(self) -> None:
        self.assertEqual(collect_reference_rebaseline_errors(), [])

    def test_public_docs_alignment_passes_current_baseline(self) -> None:
        self.assertEqual(collect_errors(), [])


if __name__ == "__main__":
    unittest.main()
