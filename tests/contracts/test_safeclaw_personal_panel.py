from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from queue import Queue
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.mvp.safeclaw_personal_panel import (  # noqa: E402
    PERSONAL_PANEL_ENTRY_PATH_ENV,
    SafeclawPersonalPanelController,
    build_archive_note_panel_arguments,
    build_personal_panel_exception_text,
    build_personal_panel_undo_confirmation_text,
    build_personal_panel_result_text,
    build_personal_panel_progress_text,
    resolve_personal_panel_entry_command,
)


class SafeclawPersonalPanelTest(unittest.TestCase):
    def assert_known_failure_guidance(
        self,
        action_name: str,
        output_text: str,
        expected_title: str,
        expected_result: str,
        expected_reason: str,
        expected_next: str,
    ) -> None:
        completed = subprocess.CompletedProcess(
            args=[action_name],
            returncode=1,
            stdout=output_text,
            stderr="",
        )
        rendered = build_personal_panel_result_text(action_name, completed)
        self.assertIn(expected_title, rendered)
        self.assertIn(f"结果：{expected_result}", rendered)
        self.assertIn(f"原因：{expected_reason}", rendered)
        self.assertIn(f"下一步：{expected_next}", rendered)
        self.assertLess(rendered.index(f"结果：{expected_result}"), rendered.index(f"原因：{expected_reason}"))
        self.assertLess(
            rendered.index(f"原因：{expected_reason}"),
            rendered.index(f"下一步：{expected_next}"),
        )
        self.assertNotIn("退出码：", rendered)
        self.assertNotIn("【原始输出】", rendered)

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
                "[personal] summary => 当前还没有最近笔记。\n"
                "[personal] last note => none\n"
                "[personal] next => safeclaw-personal.cmd archive-note --name <name> --content <text>\n"
            ),
            stderr="",
        )
        rendered = build_personal_panel_result_text("status", completed)
        self.assertIn("【查看状态】", rendered)
        self.assertIn("结果：当前还没有最近笔记。", rendered)
        self.assertIn("最近笔记：还没有", rendered)
        self.assertIn("下一步：safeclaw-personal.cmd archive-note --name <name> --content <text>", rendered)
        self.assertNotIn("退出码：0", rendered)
        self.assertNotIn("【原始输出】", rendered)

    def test_build_personal_panel_result_text_renders_undo_failure_guidance(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["undo"],
            returncode=1,
            stdout=(
                "[personal] summary => 这次没有可撤销的最近笔记。\n"
                "[personal] no last note recorded; run archive-note first\n"
                "[personal] next => tools\\mvp\\safeclaw_personal_mvp.cmd archive-note --name <name> --content <text>\n"
            ),
            stderr="",
        )
        rendered = build_personal_panel_result_text("undo", completed)
        self.assertIn("【撤销上一步】", rendered)
        self.assertIn("结果：这次没有可撤销的最近笔记。", rendered)
        self.assertIn("原因：还没有最近笔记。", rendered)
        self.assertIn(
            "下一步：tools\\mvp\\safeclaw_personal_mvp.cmd archive-note --name <name> --content <text>",
            rendered,
        )
        self.assertLess(rendered.index("结果：这次没有可撤销的最近笔记。"), rendered.index("原因：还没有最近笔记。"))
        self.assertLess(
            rendered.index("原因：还没有最近笔记。"),
            rendered.index("下一步：tools\\mvp\\safeclaw_personal_mvp.cmd archive-note --name <name> --content <text>"),
        )
        self.assertNotIn("退出码：", rendered)
        self.assertNotIn("【原始输出】", rendered)

    def test_build_personal_panel_result_text_guides_missing_note_title(self) -> None:
        self.assert_known_failure_guidance(
            action_name="archive-note",
            output_text="[personal] archive-note requires --name\n",
            expected_title="【写笔记】",
            expected_result="这次还没写成笔记。",
            expected_reason="标题不能为空。",
            expected_next="先填标题，再点“写笔记”。",
        )

    def test_build_personal_panel_result_text_guides_missing_note_content(self) -> None:
        self.assert_known_failure_guidance(
            action_name="archive-note",
            output_text="[personal] archive-note requires --content or --content-file\n",
            expected_title="【写笔记】",
            expected_result="这次还没写成笔记。",
            expected_reason="内容不能为空。",
            expected_next="先填内容，再点“写笔记”。",
        )

    def test_build_personal_panel_result_text_guides_missing_undo_target(self) -> None:
        self.assert_known_failure_guidance(
            action_name="undo",
            output_text="[mvp] undo target missing at C:/demo/archive/demo.md\n",
            expected_title="【撤销上一步】",
            expected_result="这次没能撤销最近笔记。",
            expected_reason="要撤销的归档文件已经不存在。",
            expected_next="先点“查看状态”，确认当前情况。",
        )

    def test_build_personal_panel_result_text_keeps_raw_output_for_unknown_failure(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["status"],
            returncode=2,
            stdout="unexpected failure\nline two\n",
            stderr="",
        )
        rendered = build_personal_panel_result_text("status", completed)
        self.assertIn("结果：执行失败", rendered)
        self.assertIn("原因：程序没有正常完成（退出码：2）。", rendered)
        self.assertIn("下一步：看下面原始输出，再决定怎么处理。", rendered)
        self.assertIn("【原始输出】", rendered)
        self.assertIn("unexpected failure", rendered)

    def test_build_personal_panel_exception_text_guides_missing_entry(self) -> None:
        rendered = build_personal_panel_exception_text(
            "status",
            FileNotFoundError("[WinError 2] 系统找不到指定的文件。"),
            ["cmd", "/c", r"C:\missing\safeclaw-personal.cmd"],
        )
        self.assertIn("【查看状态】", rendered)
        self.assertIn("结果：这次没能完成操作。", rendered)
        self.assertIn("原因：当前入口程序找不到了。", rendered)
        self.assertIn('下一步：先检查入口是否还在：cmd /c C:\\missing\\safeclaw-personal.cmd', rendered)
        self.assertNotIn("【原始错误】", rendered)

    def test_run_action_worker_converts_exception_to_rendered_result(self) -> None:
        controller = object.__new__(SafeclawPersonalPanelController)
        controller.entry_command = ["cmd", "/c", r"C:\missing\safeclaw-personal.cmd"]
        controller.result_queue = Queue()
        with patch(
            "tools.mvp.safeclaw_personal_panel.run_personal_panel_action",
            side_effect=FileNotFoundError("[WinError 2] 系统找不到指定的文件。"),
        ):
            SafeclawPersonalPanelController._run_action_worker(controller, "status", "", "")
        action_name, rendered = controller.result_queue.get_nowait()
        self.assertEqual(action_name, "status")
        self.assertIn("结果：这次没能完成操作。", rendered)
        self.assertIn("原因：当前入口程序找不到了。", rendered)

    def test_build_personal_panel_progress_text_uses_human_readable_copy(self) -> None:
        self.assertEqual(build_personal_panel_progress_text("archive-note"), "正在写入笔记，请稍等。")
        self.assertEqual(build_personal_panel_progress_text("status"), "正在刷新状态，请稍等。")
        self.assertEqual(build_personal_panel_progress_text("undo"), "正在撤销上一步，请稍等。")

    def test_build_personal_panel_undo_confirmation_text_explains_risk(self) -> None:
        confirmation_text = build_personal_panel_undo_confirmation_text()
        self.assertIn("这会尝试撤销最近一次归档笔记。", confirmation_text)
        self.assertIn("对应文件可能会被删除。", confirmation_text)
        self.assertIn("确定继续吗？", confirmation_text)


if __name__ == "__main__":
    unittest.main()
