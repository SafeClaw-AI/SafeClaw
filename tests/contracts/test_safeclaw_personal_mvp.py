from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.mvp.safeclaw_personal_mvp import (  # noqa: E402
    ARCHIVE_ROOT,
    DB_PATH,
    build_archive_note_command,
    build_archive_output_path,
    build_task_id,
    sanitize_note_name,
)


class SafeclawPersonalMvpTest(unittest.TestCase):
    def test_sanitize_note_name_matches_archive_slug_rules(self) -> None:
        self.assertEqual(sanitize_note_name(" Weekly_Standup !!! "), "weekly-standup")

    def test_build_archive_output_path_uses_month_scope_and_slug(self) -> None:
        output_path = build_archive_output_path(
            Path("C:/personal/archive"),
            "2026-04-02",
            "Weekly Standup",
        )
        self.assertEqual(
            output_path,
            Path("C:/personal/archive/2026-04/2026-04-02-weekly-standup.md"),
        )

    def test_build_task_id_uses_timestamp_and_slug(self) -> None:
        task_id = build_task_id(
            "Weekly Standup",
            datetime(2026, 4, 2, 7, 30, 45),
        )
        self.assertEqual(task_id, "task-safeclaw-personal-20260402-073045-weekly-standup")

    def test_build_archive_note_command_pins_personal_paths(self) -> None:
        command = build_archive_note_command(
            "Weekly Standup",
            "2026-04-02",
            "# Weekly standup\n- shipped\n",
            "task-safeclaw-personal-20260402-073045-weekly-standup",
        )
        self.assertEqual(command[0:9], [
            "cargo",
            "+stable-x86_64-pc-windows-gnu",
            "run",
            "-p",
            "safeclaw-sqlite",
            "--example",
            "safeclaw_mvp_entry",
            "--quiet",
            "--",
        ])
        self.assertIn(str(DB_PATH), command)
        self.assertIn(str(ARCHIVE_ROOT), command)
        self.assertIn("archive-note", command)


if __name__ == "__main__":
    unittest.main()
