from __future__ import annotations

import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PERSONAL_MVP = REPO_ROOT / "tools" / "mvp" / "safeclaw_personal_mvp.py"
TEST_ROOT = REPO_ROOT / "target" / "test-safeclaw-personal-cli"
ARCHIVE_DATE = "2026-04-02"
ARCHIVE_NAME = "CLI Roundtrip"
ARCHIVE_FILE = TEST_ROOT / "archive" / "2026-04" / "2026-04-02-cli-roundtrip.md"


class SafeclawPersonalMvpCliTest(unittest.TestCase):
    def setUp(self) -> None:
        shutil.rmtree(TEST_ROOT, ignore_errors=True)

    def run_personal(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["SAFECLAW_PERSONAL_ROOT"] = str(TEST_ROOT)
        return subprocess.run(
            [sys.executable, "-X", "utf8", str(PERSONAL_MVP), *args],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_status_without_last_note_guides_to_archive_note(self) -> None:
        completed = self.run_personal("status")
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("[personal] summary => 当前还没有最近笔记。", completed.stdout)
        self.assertIn("[personal] last note => none", completed.stdout)
        self.assertIn("archive-note --name <name> --content <text>", completed.stdout)
        self.assertLess(
            completed.stdout.index("[personal] summary => 当前还没有最近笔记。"),
            completed.stdout.index("[personal] profile => "),
        )
        self.assertLess(
            completed.stdout.index("[personal] last note => none"),
            completed.stdout.index("[personal] next => "),
        )

    def test_undo_without_last_note_explains_human_next_step(self) -> None:
        completed = self.run_personal("undo")
        self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
        self.assertIn("[personal] summary => 这次没有可撤销的最近笔记。", completed.stdout)
        self.assertIn("[personal] no last note recorded; run archive-note first", completed.stdout)
        self.assertIn(
            "[personal] next => tools\\mvp\\safeclaw_personal_mvp.cmd archive-note --name <name> --content <text>",
            completed.stdout,
        )
        self.assertLess(
            completed.stdout.index("[personal] summary => 这次没有可撤销的最近笔记。"),
            completed.stdout.index("[personal] no last note recorded; run archive-note first"),
        )
        self.assertLess(
            completed.stdout.index("[personal] no last note recorded; run archive-note first"),
            completed.stdout.index(
                "[personal] next => tools\\mvp\\safeclaw_personal_mvp.cmd archive-note --name <name> --content <text>"
            ),
        )

    def test_archive_note_then_undo_roundtrip(self) -> None:
        archive_completed = self.run_personal(
            "archive-note",
            "--name",
            ARCHIVE_NAME,
            "--date",
            ARCHIVE_DATE,
            "--content",
            "个人最小版回路验证",
        )
        self.assertEqual(archive_completed.returncode, 0, archive_completed.stdout + archive_completed.stderr)
        self.assertIn("[mvp] archive note => created", archive_completed.stdout)
        self.assertIn("[personal] summary => 最近一次笔记已归档，需要时可以直接撤销。", archive_completed.stdout)
        self.assertIn("[personal] next => tools\\mvp\\safeclaw_personal_mvp.cmd undo", archive_completed.stdout)
        self.assertTrue(ARCHIVE_FILE.exists())

        status_completed = self.run_personal("status")
        self.assertEqual(status_completed.returncode, 0, status_completed.stdout + status_completed.stderr)
        self.assertIn("[personal] summary => 最近一次笔记还在，需要时可以直接撤销。", status_completed.stdout)
        self.assertIn("[personal] archive exists => True", status_completed.stdout)
        self.assertIn("[personal] next => tools\\mvp\\safeclaw_personal_mvp.cmd undo", status_completed.stdout)
        self.assertLess(
            status_completed.stdout.index("[personal] summary => 最近一次笔记还在，需要时可以直接撤销。"),
            status_completed.stdout.index("[personal] profile => "),
        )
        self.assertLess(
            status_completed.stdout.index("[personal] archive exists => True"),
            status_completed.stdout.index("[personal] next => tools\\mvp\\safeclaw_personal_mvp.cmd undo"),
        )

        undo_completed = self.run_personal("undo")
        self.assertEqual(undo_completed.returncode, 0, undo_completed.stdout + undo_completed.stderr)
        self.assertIn("[mvp] undo result => worker=RolledBack effect=RolledBack compensation=0", undo_completed.stdout)
        self.assertIn("[personal] summary => 已撤销最近一次归档。", undo_completed.stdout)
        self.assertIn("[personal] archive exists => False", undo_completed.stdout)
        self.assertFalse(ARCHIVE_FILE.exists())


if __name__ == "__main__":
    unittest.main()
