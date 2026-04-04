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
                "当前 `24` 项改动已全部纳入三组治理，未归类 `0` 项，现状稳定",
                "提交/归档顺序、批次清单与收口表统一以 `PUSH_LOG.md` 为准，本表不再重复展开提交层细节",
                "docs/chancellor-mode/v2/",
                "历史切片",
            ],
            PUSH_LOG_FILE: [
                BOUNDARY_NOTE_TITLE,
                BOUNDARY_NOTE_DECISION,
                BOUNDARY_NOTE_FUSION,
                CURRENT_SUBMISSION_EXECUTION_SUMMARY_TITLE,
                BATCH_ONE_PRE_SUBMIT_CHECKLIST_TITLE,
                BATCH_TWO_PRE_SUBMIT_CHECKLIST_TITLE,
                BATCH_THREE_PRE_SUBMIT_CHECKLIST_TITLE,
                CURRENT_SUBMISSION_CLOSEOUT_TABLE_TITLE,
                CURRENT_SUBMISSION_READINESS_TABLE_TITLE,
                "当前工作区总改动：24；当前分组情况：边界治理 13 / 自检治理 8 / 个人部署链 3；未归类：0。",
                "本摘要属于提交前快照；任一批次完成 commit 后，必须同步刷新总改动、分组数、批次文件表与收口表，不沿用旧数值。",
                "建议提交顺序：边界治理 -> 自检治理 -> 个人部署链。",
                "批次一文件：`MVP_PROGRESS.md`、`PUSH_LOG.md`",
                "批次二文件：`tests/contracts/test_scaffold_check.py`、`tests/contracts/test_selfcheck.py`",
                "批次三文件：`tests/contracts/test_safeclaw_personal_deploy.py`、`tools/mvp/safeclaw_personal_deploy.py`",
                "`python -X utf8 -m unittest tests.contracts.test_chancellor_panel tests.contracts.test_public_docs_check -v`",
                "`python -X utf8 -m unittest tests.contracts.test_scaffold_check tests.contracts.test_selfcheck tests.contracts.test_worktree_groups -v`",
                "`python -X utf8 -m unittest tests.contracts.test_safeclaw_personal_deploy -v`",
                "`python -X utf8 tools/checks/check_public_docs.py`",
                "`python -X utf8 tools/checks/check_scaffold.py`",
                "`python -X utf8 tools/checks/selfcheck.py`",
                "`python -X utf8 tools/checks/worktree_groups.py`",
                "`git diff --check`",
                "边界治理仍为 13，未归类仍为 0，公开口径不反弹",
                "自检治理仍为 8，未归类仍为 0，自检总入口不绕行，换行门禁不反弹",
                "个人部署链仍为 3，未归类仍为 0，个人部署链继续与外部丞相模式隔离，回滚只切 release 指针的边界不反弹",
                "三组提交前验证清单、收口表、就绪核对与文件级逐项核对已补齐；逐项核对时，未跟踪文件必须用 `git status --short` 补核，随后按顺序进入最终提交/归档收束；不再继续追加治理口径说明",
                "| 边界治理 | 已验 | 公开文档门禁、合同、分组与换行检查已通过 |",
                "| 自检治理 | 已验 | scaffold、自检总入口、分组与换行检查已通过 |",
                "| 个人部署链 | 已验 | 个人部署合同、分组与换行检查已通过 |",
                "| 边界治理 | 13 | 13 | 是 | 可独立提交 |",
                "| 自检治理 | 8 | 8 | 是 | 可独立提交 |",
                "| 个人部署链 | 3 | 3 | 是 | 可独立提交 |",
                "提交顺序：`边界治理 -> 自检治理 -> 个人部署链`。",
                "当前无需新增治理说明，直接进入提交/归档动作。",
                "当前三组文件数与分组改动数一致，没有批次漏挂或跨组混挂迹象。",
                "当前三组批次文件已与脏工作区分组清单逐项核对，一致。",
                "核对方式：已跟踪改动看 `git diff --name-only -- <批次文件>`；未跟踪文件补看 `git status --short`。",
                "本轮补核到的未跟踪文件：自检治理 ` .gitattributes / tests/contracts/test_worktree_groups.py / tools/checks/worktree_groups.py `；个人部署链 ` temp/parked-root/round-log-20260402-130500-personal-thin-panel-delivery.md `。",
                "已实跑 `git status --short -- <批次文件>` 与 `git diff --stat -- <批次文件>`；三组均只命中本组文件，可独立提交。",
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
