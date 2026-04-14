from __future__ import annotations

import unittest

from tests.contracts import REPO_ROOT
from tools.checks.worktree_groups import (
    BOUNDARY_GOVERNANCE_GROUP,
    PERSONAL_DEPLOY_GROUP,
    SELFCHECK_GOVERNANCE_GROUP,
    UNCLASSIFIED_GROUP,
    classify_path,
    group_dirty_worktree_entries,
    parse_status_line,
    render_grouped_entries,
)


class WorktreeGroupsTest(unittest.TestCase):
    def test_parse_status_line_keeps_status_and_normalizes_path(self) -> None:
        self.assertEqual(parse_status_line(" M docs\\README.md"), ("M", "docs/README.md"))
        self.assertEqual(parse_status_line("?? temp\\parked-root\\note.md"), ("??", "temp/parked-root/note.md"))

    def test_parse_status_line_uses_rename_target(self) -> None:
        self.assertEqual(
            parse_status_line("R  old\\name.md -> docs\\README.md"),
            ("R", "docs/README.md"),
        )

    def test_parse_status_line_strips_wrapping_quotes(self) -> None:
        self.assertEqual(
            parse_status_line(' M "docs/reference/01-反屎山工程规范.md"'),
            ("M", "docs/reference/01-反屎山工程规范.md"),
        )

    def test_classify_path_groups_current_governance_clusters(self) -> None:
        self.assertEqual(classify_path("开发计划.md"), BOUNDARY_GOVERNANCE_GROUP)
        self.assertEqual(classify_path("docs/records/开发计划.md"), BOUNDARY_GOVERNANCE_GROUP)
        self.assertEqual(classify_path("tools/checks/selfcheck.py"), SELFCHECK_GOVERNANCE_GROUP)
        self.assertEqual(
            classify_path("temp/parked-root/round-log-20260402-130500-personal-thin-panel-delivery.md"),
            PERSONAL_DEPLOY_GROUP,
        )

    def test_classify_path_marks_unknown_paths_as_unclassified(self) -> None:
        self.assertEqual(classify_path("docs/some-new-area/unknown.md"), UNCLASSIFIED_GROUP)

    def test_render_grouped_entries_starts_with_summary_then_lists_details(self) -> None:
        grouped = group_dirty_worktree_entries(
            [
                ("M", "开发计划.md"),
                ("M", "tools/checks/selfcheck.py"),
                ("??", "docs/some-new-area/unknown.md"),
            ]
        )

        rendered = render_grouped_entries(grouped)

        self.assertIn("当前脏工作区摘要：", rendered)
        self.assertIn("- 总改动：3", rendered)
        self.assertIn("- 分组：边界治理 1，自检治理 1，未归类 1", rendered)
        self.assertIn("- 未归类：有 1 项，收口前需要继续处理。", rendered)
        self.assertIn("- 收口判断：改动已按治理分组归拢，可按分组逐项验证。", rendered)
        self.assertIn("详细清单：", rendered)
        self.assertIn("- 边界治理（1）", rendered)
        self.assertIn("  M 开发计划.md", rendered)
        self.assertIn("- 自检治理（1）", rendered)
        self.assertIn("  M tools/checks/selfcheck.py", rendered)
        self.assertIn("- 未归类（1）", rendered)
        self.assertIn("  ?? docs/some-new-area/unknown.md", rendered)

    def test_render_grouped_entries_reports_clean_worktree(self) -> None:
        self.assertEqual(render_grouped_entries(group_dirty_worktree_entries([])), "工作区干净：当前没有未提交改动。")


if __name__ == "__main__":
    unittest.main()
