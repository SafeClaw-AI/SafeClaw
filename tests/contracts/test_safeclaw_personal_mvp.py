from __future__ import annotations

import subprocess
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from tests.contracts import REPO_ROOT
from tools.mvp.safeclaw_personal_mvp import (
    ARCHIVE_ROOT,
    DB_PATH,
    RUNTIME_CARGO_MISSING_NEXT,
    RUNTIME_CARGO_MISSING_REASON,
    RUNTIME_LINKER_MISSING_NEXT,
    RUNTIME_LINKER_MISSING_REASON,
    build_archive_note_command,
    build_archive_output_path,
    build_task_id,
    check_configured_linker_accessible,
    resolve_safeclaw_mvp_runtime_command,
    run_checked,
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

    def test_resolve_safeclaw_mvp_runtime_command_prefers_prebuilt_example(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            example_path = repo_root / "target" / "debug" / "examples" / "safeclaw_mvp_entry.exe"
            example_path.parent.mkdir(parents=True, exist_ok=True)
            example_path.write_bytes(b"fake exe")
            runtime_command = resolve_safeclaw_mvp_runtime_command(
                build_archive_note_command(
                    "Weekly Standup",
                    "2026-04-02",
                    "# Weekly standup\n- shipped\n",
                    "task-safeclaw-personal-20260402-073045-weekly-standup",
                ),
                repo_root=repo_root,
            )
        self.assertEqual(runtime_command[0], str(example_path))
        self.assertEqual(runtime_command[1], "archive-note")

    def test_check_configured_linker_accessible_tolerates_permission_error(self) -> None:
        with patch(
            "tools.mvp.safeclaw_personal_mvp.Path.exists",
            side_effect=PermissionError("access denied"),
        ):
            with patch("builtins.print") as print_mock:
                accessible = check_configured_linker_accessible()
        self.assertTrue(accessible)
        print_mock.assert_any_call(
            "[personal] linker probe permission denied => "
            "C:\\Users\\tianduan999\\AppData\\Local\\Microsoft\\WinGet\\Packages\\BrechtSanders."
            "WinLibs.POSIX.UCRT_Microsoft.Winget.Source_8wekyb3d8bbwe\\mingw64\\bin\\"
            "x86_64-w64-mingw32-gcc.exe (access denied)"
        )

    def test_run_checked_uses_cargo_runtime_when_prebuilt_example_missing(self) -> None:
        completed = subprocess.CompletedProcess(args=["cargo", "test"], returncode=0)
        with patch("tools.mvp.safeclaw_personal_mvp.resolve_safeclaw_mvp_runtime_command", return_value=["cargo", "test"]):
            with patch("tools.mvp.safeclaw_personal_mvp.shutil.which", return_value=r"C:\Rust\cargo.exe"):
                with patch("tools.mvp.safeclaw_personal_mvp.check_configured_linker_accessible", return_value=True):
                    with patch("tools.mvp.safeclaw_personal_mvp.subprocess.run", return_value=completed) as run_mock:
                        exit_code = run_checked(["cargo", "test"])
        self.assertEqual(exit_code, 0)
        run_mock.assert_called_once()

    def test_run_checked_explains_missing_cargo_with_next_step(self) -> None:
        with patch("tools.mvp.safeclaw_personal_mvp.resolve_safeclaw_mvp_runtime_command", return_value=["cargo", "test"]):
            with patch("tools.mvp.safeclaw_personal_mvp.shutil.which", return_value=None):
                with patch("builtins.print") as print_mock:
                    exit_code = run_checked(["cargo", "test"])
        self.assertEqual(exit_code, 1)
        self.assertEqual(
            [call.args[0] for call in print_mock.call_args_list],
            [
                "[personal] summary => 当前机器还没准备好个人归档运行环境。",
                f"[personal] {RUNTIME_CARGO_MISSING_REASON}",
                f"[personal] next => {RUNTIME_CARGO_MISSING_NEXT}",
            ],
        )

    def test_run_checked_explains_missing_linker_with_next_step(self) -> None:
        with patch("tools.mvp.safeclaw_personal_mvp.resolve_safeclaw_mvp_runtime_command", return_value=["cargo", "test"]):
            with patch("tools.mvp.safeclaw_personal_mvp.shutil.which", return_value=r"C:\Rust\cargo.exe"):
                with patch("tools.mvp.safeclaw_personal_mvp.check_configured_linker_accessible", return_value=False):
                    with patch("builtins.print") as print_mock:
                        exit_code = run_checked(["cargo", "test"])
        self.assertEqual(exit_code, 1)
        self.assertEqual(
            [call.args[0] for call in print_mock.call_args_list],
            [
                "[personal] summary => 当前机器还没准备好个人归档运行环境。",
                f"[personal] {RUNTIME_LINKER_MISSING_REASON}",
                f"[personal] next => {RUNTIME_LINKER_MISSING_NEXT}",
            ],
        )


if __name__ == "__main__":
    unittest.main()
