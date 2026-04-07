from __future__ import annotations

import io
import json
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from tools.checks import tooling_smoke_refactor


class ToolingSmokeRefactorTest(unittest.TestCase):
    def test_collect_refactor_blocks_groups_helpers_and_inline_segments(self) -> None:
        source = textwrap.dedent(
            """
            def append_alpha_errors(errors):
                return None

            def append_beta_errors(errors):
                return None

            def collect_errors():
                errors = []
                reset_smoke_progress()
                append_alpha_errors(errors)
                result = assert_command_json_result(
                    [],
                    errors,
                    "mvp-wrapper-inline-json",
                    "seed-crash",
                )
                assert_run_json_result(result, errors, "mvp-wrapper-inline-json")
                append_beta_errors(errors)
                wrapper_service = subprocess.run([])
                if wrapper_service.returncode != 0:
                    errors.append("mvp-wrapper-inline-text missing output")
                return errors
            """
        )

        blocks = tooling_smoke_refactor.collect_refactor_blocks(source)

        self.assertEqual(
            [(block.kind, block.label) for block in blocks],
            [
                ("inline", "collect-errors-setup"),
                ("helper", "append_alpha_errors"),
                ("inline", "mvp-wrapper-inline-json"),
                ("helper", "append_beta_errors"),
                ("inline", "mvp-wrapper-inline-text"),
            ],
        )
        self.assertEqual(blocks[2].statement_count, 2)
        self.assertEqual(blocks[4].statement_count, 3)

    def test_render_block_map_can_filter_inline_blocks(self) -> None:
        blocks = [
            tooling_smoke_refactor.RefactorBlock("inline", "collect-errors-setup", 10, 11, 2),
            tooling_smoke_refactor.RefactorBlock("helper", "append_alpha_errors", 12, 12, 1),
            tooling_smoke_refactor.RefactorBlock("inline", "mvp-wrapper-inline-json", 13, 20, 2),
        ]

        rendered = tooling_smoke_refactor.render_block_map(
            blocks,
            inline_only=True,
            limit=1,
        )

        self.assertIn("total_blocks=3 inline_blocks=2", rendered)
        self.assertIn("01. kind=inline lines=10-11 statements=2 label=collect-errors-setup", rendered)
        self.assertNotIn("append_alpha_errors", rendered)
        self.assertNotIn("mvp-wrapper-inline-json", rendered)

    def test_build_refactor_check_commands_with_filter(self) -> None:
        commands = tooling_smoke_refactor.build_refactor_check_commands(
            "service_recover_json_seed_crash_json"
        )

        self.assertEqual(len(commands), 3)
        self.assertEqual(commands[0][-2:], ["-k", "service_recover_json_seed_crash_json"])
        self.assertEqual(commands[1][0], tooling_smoke_refactor.sys.executable)
        self.assertIn("py_compile", commands[1])
        self.assertEqual(commands[2][-1], "-q")

    def test_main_map_json_outputs_inline_payload(self) -> None:
        source = textwrap.dedent(
            """
            def append_alpha_errors(errors):
                return None

            def collect_errors():
                errors = []
                append_alpha_errors(errors)
                result = assert_command_json_result([], errors, "mvp-wrapper-inline-json", "seed")
                return errors
            """
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "sample.py"
            source_path.write_text(source, encoding="utf-8")
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = tooling_smoke_refactor.main(
                    ["map", "--path", str(source_path), "--inline-only", "--json"]
                )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(len(payload), 2)
        self.assertEqual(payload[0]["label"], "collect-errors-setup")
        self.assertEqual(payload[1]["label"], "mvp-wrapper-inline-json")


if __name__ == "__main__":
    unittest.main()
