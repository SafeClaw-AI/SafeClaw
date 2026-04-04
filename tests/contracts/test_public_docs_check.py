from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.checks.check_public_docs import (  # noqa: E402
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
    CHANCELLOR_ENTRY_BASELINE_FILE,
    CHANCELLOR_PRODUCT_REBASELINE_FILE,
    DEV_PLAN_FILE,
    LINT_README_FILE,
    MVP_PROGRESS_FILE,
    MVP_README_FILE,
    OPERATOR_PLAYBOOK_FILE,
    PUSH_LOG_FILE,
    README_FILE,
    REFERENCE_HYGIENE_FILE,
    REQUIRED_MARKERS,
    collect_errors,
    collect_reference_rebaseline_errors,
)


class PublicDocsCheckTest(unittest.TestCase):
    def test_boundary_note_files_are_guarded_by_public_docs_check(self) -> None:
        expected_entries = {
            DEV_PLAN_FILE: [
                BOUNDARY_NOTE_TITLE,
                BOUNDARY_NOTE_DECISION,
                BOUNDARY_NOTE_FUSION,
                "docs/chancellor-mode/v2/",
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
                "提交/归档顺序、批次清单与收口表统一以 `PUSH_LOG.md` 为准，本表不再重复展开提交层细节",
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
                "docs/chancellor-mode/v2/",
                "后期拼接融合参考",
                "不属于 SafeClaw 当前开发范围",
            ],
        }

        for doc_file, expected_markers in expected_entries.items():
            with self.subTest(doc=doc_file.relative_to(REPO_ROOT).as_posix()):
                self.assertIn(doc_file, REQUIRED_MARKERS)
                self.assertEqual(REQUIRED_MARKERS[doc_file], expected_markers)

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

    def test_newly_added_public_readmes_are_guarded_by_public_docs_check(self) -> None:
        expected_entries = {
            README_FILE: [
                "specs/",
                "tests/contracts/",
                "tools/checks/",
                "tools/mvp/OPERATOR_PLAYBOOK.md",
                "workspace --name demo",
                "service-run --reset --task-id task-demo --limit 1 --report",
                "service-status --limit 5",
                "verify --json",
                "local-only",
                "preflight --action ai-reason",
                "0.1.1",
                "OpenClaw",
                "English Summary",
                "已经有一层给主人自用的本地中文小面板",
                "还不是对外开箱即用的完整产品",
                "当前可手动体验的本地 MVP",
                "Win11 本地 MVP 已可手用",
                "个人生产位小面板",
                "archive-note -> status -> undo",
            ],
            REPO_ROOT / "docs" / "README.md": [
                BOUNDARY_NOTE_TITLE,
                BOUNDARY_NOTE_DECISION,
                BOUNDARY_NOTE_FUSION,
                "DEVLOG.md",
                "V1_SCOPE.md",
                "V1_TASK_TRIAGE.md",
                "02-V4-目录锁定清单.md",
                "04-V4-repo-hygiene-migration-plan.md",
                "06-V4-ledger-compat-index-spec.md",
                "08-V4-ledger-index-manifest.json",
                "20-V4-reference-compliance-rebaseline-record-20260329_030242.md",
                "docs/chancellor-mode/v2/",
                "01-m1b-exit-and-m2-panel-entry.md",
                "02-m2-panel-command-truth-source.md",
                "03-m2-product-value-rebaseline.md",
                "selfcheck.py",
                "ledger_index_manifest.py",
                "check_ledger_alignment.py",
                "check_consistency.py",
                "check_versions.py",
                "check_structure.py",
                "check_scaffold.py",
                "check_public_docs.py",
                "tests/contracts/",
            ],
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

        for readme_file, expected_markers in expected_entries.items():
            with self.subTest(readme=readme_file.relative_to(REPO_ROOT).as_posix()):
                self.assertIn(readme_file, REQUIRED_MARKERS)
                self.assertEqual(REQUIRED_MARKERS[readme_file], expected_markers)

    def test_reference_rebaseline_doc_passes_current_baseline(self) -> None:
        self.assertEqual(collect_reference_rebaseline_errors(), [])

    def test_public_docs_alignment_passes_current_baseline(self) -> None:
        self.assertEqual(collect_errors(), [])


if __name__ == "__main__":
    unittest.main()
