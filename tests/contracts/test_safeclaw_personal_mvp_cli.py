from __future__ import annotations

import os
import shutil
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
PERSONAL_MVP = REPO_ROOT / "tools" / "mvp" / "safeclaw_personal_mvp.py"
TEST_ROOT = REPO_ROOT / "target" / "test-safeclaw-personal-cli"
ARCHIVE_DATE = "2026-04-02"
ARCHIVE_NAME = "CLI Roundtrip"
ARCHIVE_FILE = TEST_ROOT / "archive" / "2026-04" / "2026-04-02-cli-roundtrip.md"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.mvp.safeclaw_personal_mvp import run_checked  # noqa: E402
from tools.mvp.safeclaw_personal_panel import build_personal_panel_result_text  # noqa: E402


class SafeclawPersonalMvpCliTest(unittest.TestCase):
    def setUp(self) -> None:
        if TEST_ROOT.exists():
            shutil.rmtree(TEST_ROOT)

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

    def write_invalid_last_note_state(self) -> None:
        state_dir = TEST_ROOT / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "last_note.json").write_text("[]\n", encoding="utf-8")

    def assert_archive_note_failure(
        self,
        completed: subprocess.CompletedProcess[str],
        expected_reason: str,
    ) -> None:
        self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
        self.assertIn("[personal] summary => 这次还没写成笔记。", completed.stdout)
        self.assertIn(f"[personal] {expected_reason}", completed.stdout)
        self.assertIn(
            "[personal] next => tools\\mvp\\safeclaw_personal_mvp.cmd archive-note --name <name> --content <text>",
            completed.stdout,
        )
        self.assertLess(
            completed.stdout.index("[personal] summary => 这次还没写成笔记。"),
            completed.stdout.index(f"[personal] {expected_reason}"),
        )
        self.assertLess(
            completed.stdout.index(f"[personal] {expected_reason}"),
            completed.stdout.index(
                "[personal] next => tools\\mvp\\safeclaw_personal_mvp.cmd archive-note --name <name> --content <text>"
            ),
        )
        self.assertEqual(completed.stderr, "")

    def assert_runtime_failure_output(
        self,
        output_text: str,
        expected_reason: str,
        expected_next: str,
    ) -> None:
        self.assertIn("[personal] summary => 当前机器还没准备好个人归档运行环境。", output_text)
        self.assertIn(f"[personal] {expected_reason}", output_text)
        self.assertIn(f"[personal] next => {expected_next}", output_text)

    def assert_runtime_failure_panel_rendered(
        self,
        output_text: str,
        expected_reason: str,
        expected_next: str,
    ) -> None:
        completed = subprocess.CompletedProcess(
            args=["archive-note"],
            returncode=1,
            stdout=output_text,
            stderr="",
        )
        rendered = build_personal_panel_result_text("archive-note", completed)
        self.assertIn("结果：当前机器还没准备好个人归档运行环境。", rendered)
        self.assertIn(f"原因：{expected_reason}", rendered)
        self.assertIn(f"下一步：{expected_next}", rendered)
        self.assertNotIn("退出码：", rendered)

    def test_archive_note_without_name_explains_human_next_step(self) -> None:
        completed = self.run_personal("archive-note", "--content", "个人最小版回路验证")
        self.assert_archive_note_failure(completed, "标题不能为空。")

    def test_archive_note_without_content_explains_human_next_step(self) -> None:
        completed = self.run_personal("archive-note", "--name", ARCHIVE_NAME)
        self.assert_archive_note_failure(completed, "内容不能为空。")

    def test_archive_note_with_missing_content_file_explains_human_next_step(self) -> None:
        completed = self.run_personal(
            "archive-note",
            "--name",
            ARCHIVE_NAME,
            "--content-file",
            str(TEST_ROOT / "missing.md"),
        )
        self.assert_archive_note_failure(
            completed,
            "archive-note content-file missing => target\\test-safeclaw-personal-cli\\missing.md",
        )

    def test_run_checked_guides_missing_cargo_in_human_words(self) -> None:
        output = StringIO()
        expected_next = "先安装 Rust cargo，再重试当前命令。"
        with (
            redirect_stdout(output),
            patch("tools.mvp.safeclaw_personal_mvp.resolve_safeclaw_mvp_runtime_command", return_value=["archive-note"]),
            patch("tools.mvp.safeclaw_personal_mvp.shutil.which", return_value=None),
        ):
            exit_code = run_checked(["archive-note"])
        self.assertEqual(exit_code, 1)
        rendered_output = output.getvalue()
        self.assert_runtime_failure_output(
            rendered_output,
            "当前机器还没装好 Rust cargo。",
            expected_next,
        )
        self.assert_runtime_failure_panel_rendered(
            rendered_output,
            "当前机器还没装好 Rust cargo。",
            expected_next,
        )

    def test_run_checked_guides_missing_linker_in_human_words(self) -> None:
        output = StringIO()
        expected_next = "先装好 GNU linker，或把它的路径改对，再重试当前命令。"
        with (
            redirect_stdout(output),
            patch("tools.mvp.safeclaw_personal_mvp.resolve_safeclaw_mvp_runtime_command", return_value=["archive-note"]),
            patch("tools.mvp.safeclaw_personal_mvp.shutil.which", return_value=r"C:\Users\demo\.cargo\bin\cargo.exe"),
            patch("tools.mvp.safeclaw_personal_mvp.check_configured_linker_accessible", return_value=False),
        ):
            exit_code = run_checked(["archive-note"])
        self.assertEqual(exit_code, 1)
        rendered_output = output.getvalue()
        self.assert_runtime_failure_output(
            rendered_output,
            "当前机器还没装好 GNU linker。",
            expected_next,
        )
        self.assert_runtime_failure_panel_rendered(
            rendered_output,
            "当前机器还没装好 GNU linker。",
            expected_next,
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
        self.assertIn("[personal] 还没有最近笔记，所以这次没法撤销。", completed.stdout)
        self.assertIn(
            "[personal] next => tools\\mvp\\safeclaw_personal_mvp.cmd archive-note --name <name> --content <text>",
            completed.stdout,
        )
        self.assertLess(
            completed.stdout.index("[personal] summary => 这次没有可撤销的最近笔记。"),
            completed.stdout.index("[personal] 还没有最近笔记，所以这次没法撤销。"),
        )
        self.assertLess(
            completed.stdout.index("[personal] 还没有最近笔记，所以这次没法撤销。"),
            completed.stdout.index(
                "[personal] next => tools\\mvp\\safeclaw_personal_mvp.cmd archive-note --name <name> --content <text>"
            ),
        )

    def test_status_with_invalid_last_note_file_explains_human_next_step(self) -> None:
        self.write_invalid_last_note_state()
        completed = self.run_personal("status")
        self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
        self.assertIn("[personal] summary => 最近笔记状态文件有问题，这次没法继续。", completed.stdout)
        self.assertIn("[personal] invalid last note file => target\\test-safeclaw-personal-cli\\state\\last_note.json", completed.stdout)
        self.assertIn(
            "[personal] next => 先检查并修复 target\\test-safeclaw-personal-cli\\state\\last_note.json，再重试当前命令。",
            completed.stdout,
        )
        self.assertEqual(completed.stderr, "")

    def test_undo_with_invalid_last_note_file_explains_human_next_step(self) -> None:
        self.write_invalid_last_note_state()
        completed = self.run_personal("undo")
        self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
        self.assertIn("[personal] summary => 最近笔记状态文件有问题，这次没法继续。", completed.stdout)
        self.assertIn("[personal] invalid last note file => target\\test-safeclaw-personal-cli\\state\\last_note.json", completed.stdout)
        self.assertIn(
            "[personal] next => 先检查并修复 target\\test-safeclaw-personal-cli\\state\\last_note.json，再重试当前命令。",
            completed.stdout,
        )
        self.assertEqual(completed.stderr, "")

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
