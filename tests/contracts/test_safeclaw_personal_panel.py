from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.mvp.safeclaw_personal_panel import (  # noqa: E402
    PERSONAL_PANEL_ENTRY_PATH_ENV,
    build_archive_note_panel_arguments,
    build_personal_panel_result_text,
    resolve_personal_panel_entry_command,
)


class SafeclawPersonalPanelTest(unittest.TestCase):
    def test_resolve_personal_panel_entry_command_prefers_production_cmd(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_root = Path(temp_dir)
            entry_path = home_root / ".safeclaw-personal-production" / "safeclaw-personal.cmd"
            entry_path.parent.mkdir(parents=True, exist_ok=True)
            entry_path.write_text("@echo off\n", encoding="utf-8")
            command = resolve_personal_panel_entry_command(
                env={},
                user_home=home_root,
                repo_root=Path("V:/repo"),
            )
        self.assertEqual(command[:2], ["cmd", "/c"])
        self.assertEqual(command[-1], str(entry_path))

    def test_resolve_personal_panel_entry_command_honors_override_path(self) -> None:
        command = resolve_personal_panel_entry_command(
            env={PERSONAL_PANEL_ENTRY_PATH_ENV: r"C:\SafeClaw\safeclaw-personal.ps1"},
            repo_root=Path("V:/repo"),
        )
        self.assertEqual(
            command,
            [
                "powershell.exe",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                r"C:\SafeClaw\safeclaw-personal.ps1",
            ],
        )

    def test_build_archive_note_panel_arguments_use_content_file(self) -> None:
        content_file = Path("C:/tmp/note.md")
        arguments = build_archive_note_panel_arguments("晨间记录", content_file)
        self.assertEqual(
            arguments,
            ["archive-note", "--name", "晨间记录", "--content-file", str(content_file)],
        )

    def test_build_personal_panel_result_text_renders_status_summary(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["status"],
            returncode=0,
            stdout=(
                "[personal] profile => C:/demo/.safeclaw-personal\n"
                "[personal] db => C:/demo/.safeclaw-personal/state/session.db\n"
                "[personal] archive_root => C:/demo/.safeclaw-personal/archive\n"
                "[personal] last note => none\n"
                "[personal] next => safeclaw-personal.cmd archive-note --name <name> --content <text>\n"
            ),
            stderr="",
        )
        rendered = build_personal_panel_result_text("status", completed)
        self.assertIn("【查看状态】", rendered)
        self.assertIn("结果：已刷新当前状态", rendered)
        self.assertIn("最近笔记：还没有", rendered)
        self.assertIn("下一步：safeclaw-personal.cmd archive-note --name <name> --content <text>", rendered)

    def test_build_personal_panel_result_text_renders_undo_failure_hint(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["undo"],
            returncode=1,
            stdout="[personal] no last note recorded; run archive-note first\n",
            stderr="",
        )
        rendered = build_personal_panel_result_text("undo", completed)
        self.assertIn("【撤销上一步】", rendered)
        self.assertIn("结果：执行失败", rendered)
        self.assertIn("提示：还没有最近笔记，先点“写笔记”。", rendered)


if __name__ == "__main__":
    unittest.main()
