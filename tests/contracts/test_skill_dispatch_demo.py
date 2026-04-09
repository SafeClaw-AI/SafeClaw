from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from tools.mvp import skill_dispatch_demo


class SkillDispatchDemoTest(unittest.TestCase):
    def test_run_skill_dispatch_demo_writes_file_via_skill_id_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "skill-dispatch.txt"
            result = skill_dispatch_demo.run_skill_dispatch_demo(
                task_id="task-skill-id",
                output_path=output_path,
                content="hello from skill id",
                binding_mode="skill-id",
            )
            self.assertEqual(result["task_id"], "task-skill-id")
            self.assertEqual(result["binding_mode"], "skill-id")
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["result"]["written_content"], "hello from skill id")
            self.assertEqual(
                Path(result["output_path"]).resolve(strict=False),
                output_path.resolve(strict=False),
            )
            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.read_text(encoding="utf-8"), "hello from skill id")

    def test_run_skill_dispatch_demo_writes_file_via_task_kind_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "task-kind-dispatch.txt"
            result = skill_dispatch_demo.run_skill_dispatch_demo(
                task_id="task-task-kind",
                output_path=output_path,
                content="hello from task kind",
                binding_mode="task-kind",
            )
            self.assertEqual(result["binding_mode"], "task-kind")
            self.assertEqual(result["skill_id"], "")
            self.assertEqual(result["task_kind"], skill_dispatch_demo.DEFAULT_TASK_KIND)
            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.read_text(encoding="utf-8"), "hello from task kind")

    def test_main_renders_json_error_for_invalid_binding_mode(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = skill_dispatch_demo.main(
                [
                    "--binding-mode",
                    "bad-mode",
                ]
            )
        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["action"], "skill-dispatch-demo")
        self.assertEqual(payload["schema_version"], "skill-dispatch-demo.v1")
        self.assertEqual(payload["error"]["code"], "invalid_binding_mode")
        self.assertEqual(payload["error"]["reason"], "binding_mode_not_supported")

    def test_main_renders_json_result_for_real_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "cli-dispatch.txt"
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = skill_dispatch_demo.main(
                    [
                        "--task-id",
                        "task-cli",
                        "--output",
                        str(output_path),
                        "--content",
                        "hello from cli",
                        "--binding-mode",
                        "task-kind",
                    ]
                )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["action"], "skill-dispatch-demo")
            self.assertEqual(payload["result"]["binding_mode"], "task-kind")
            self.assertEqual(payload["result"]["status"], "completed")
            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.read_text(encoding="utf-8"), "hello from cli")


if __name__ == "__main__":
    unittest.main()
