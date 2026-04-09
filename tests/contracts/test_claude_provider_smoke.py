from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.mvp import claude_provider_smoke as provider_smoke


class ClaudeProviderSmokeTest(unittest.TestCase):
    def test_strip_markdown_code_fences_removes_python_fence(self) -> None:
        payload = provider_smoke.strip_markdown_code_fences(
            "```python\nprint('ok')\n```\n"
        )
        self.assertEqual(payload, "print('ok')\n")

    def test_strip_markdown_code_fences_keeps_plain_text(self) -> None:
        payload = provider_smoke.strip_markdown_code_fences("print('ok')\n")
        self.assertEqual(payload, "print('ok')\n")

    def test_extract_generated_code_reads_json_result(self) -> None:
        payload = (
            '{"type":"result","result":"\\n\\ndef add(a, b):\\n    return a + b\\n"}'
        )
        extracted = provider_smoke.extract_generated_code(payload)
        self.assertEqual(extracted, "def add(a, b):\n    return a + b")

    def test_extract_generated_code_prefers_structured_output(self) -> None:
        payload = (
            '{"type":"result","structured_output":"def add(a, b):\\n    return a + b\\n",'
            '"result":"print(\\"fallback\\")"}'
        )
        extracted = provider_smoke.extract_generated_code(payload)
        self.assertEqual(extracted, "def add(a, b):\n    return a + b")

    def test_extract_generated_code_raises_on_invalid_json_payload(self) -> None:
        with self.assertRaisesRegex(ValueError, "provider returned invalid json payload"):
            provider_smoke.extract_generated_code('{"type":"result","result":')

    def test_resolve_claude_command_wraps_powershell_script(self) -> None:
        with patch(
            "tools.mvp.claude_provider_smoke.resolve_executable_candidate",
            side_effect=[
                None,
                r"C:\Users\tianduan999\anaconda3\claude.ps1",
                r"C:\Program Files\PowerShell\7\pwsh.exe",
            ],
        ):
            command = provider_smoke.resolve_claude_command(("claude",))
        self.assertEqual(
            command,
            [
                r"C:\Program Files\PowerShell\7\pwsh.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                r"C:\Users\tianduan999\anaconda3\claude.ps1",
            ],
        )

    def test_build_provider_smoke_prompt_mentions_python_and_output_only(self) -> None:
        prompt = provider_smoke.build_provider_smoke_prompt()
        self.assertIn("Python", prompt)
        self.assertIn("Output only the code", prompt)
        self.assertIn("def add", prompt)

    def test_run_provider_smoke_writes_generated_code(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "generated.py"
            with patch(
                "tools.mvp.claude_provider_smoke.run_checked_command",
                side_effect=[
                    subprocess.CompletedProcess(
                        args=["claude", "--version"],
                        returncode=0,
                        stdout="2.1.71\n",
                        stderr="",
                    ),
                    subprocess.CompletedProcess(
                        args=["claude", "-p", "prompt"],
                        returncode=0,
                        stdout=(
                            '{"type":"result","result":"\\n\\ndef add(a, b):\\n    return a + b\\n"}'
                        ),
                        stderr="",
                    ),
                ],
            ) as mocked_run:
                with patch(
                    "tools.mvp.claude_provider_smoke.resolve_claude_command",
                    return_value=["claude"],
                ):
                    result = provider_smoke.run_provider_smoke(output_path=output_path)
                written_code = output_path.read_text(encoding="utf-8")
                self.assertEqual(result.version_text, "2.1.71")
                self.assertEqual(result.output_path, output_path)
                self.assertEqual(
                    written_code,
                    "def add(a, b):\n    return a + b\n",
                )
                self.assertEqual(mocked_run.call_count, 2)

    def test_run_provider_smoke_fails_on_empty_provider_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "generated.py"
            with patch(
                "tools.mvp.claude_provider_smoke.run_checked_command",
                side_effect=[
                    subprocess.CompletedProcess(
                        args=["claude", "--version"],
                        returncode=0,
                        stdout="2.1.71\n",
                        stderr="",
                    ),
                    subprocess.CompletedProcess(
                        args=["claude", "-p", "prompt"],
                        returncode=0,
                        stdout='{"type":"result","result":"   "}',
                        stderr="",
                    ),
                ],
            ):
                with patch(
                    "tools.mvp.claude_provider_smoke.resolve_claude_command",
                    return_value=["claude"],
                ):
                    with self.assertRaisesRegex(ValueError, "provider returned empty code payload"):
                        provider_smoke.run_provider_smoke(output_path=output_path)


if __name__ == "__main__":
    unittest.main()
