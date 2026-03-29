from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.checks.check_reference_redlines import (  # noqa: E402
    TODO_METADATA_REQUIREMENTS,
    collect_empty_exception_errors_for_powershell_text,
    collect_empty_exception_errors_for_python_text,
    collect_errors,
    collect_todo_metadata_errors_for_text,
)


class ReferenceRedlinesCheckTest(unittest.TestCase):
    def test_todo_metadata_requirements_are_stable(self) -> None:
        self.assertEqual(
            TODO_METADATA_REQUIREMENTS,
            ("owner", "due", "req"),
        )

    def test_orphan_todo_is_blocked(self) -> None:
        errors = collect_todo_metadata_errors_for_text(
            Path("sample.py"),
            "# TODO: fix later\n",
        )
        self.assertEqual(
            errors,
            [
                "TODO 缺少责任元数据: sample.py:1 -> 需要同时包含 owner / due / req",
            ],
        )

    def test_owned_todo_passes(self) -> None:
        self.assertEqual(
            collect_todo_metadata_errors_for_text(
                Path("sample.py"),
                "# TODO(owner=alice, due=2026-03-31, req=SC-123): fix later\n",
            ),
            [],
        )

    def test_python_pass_only_except_is_blocked(self) -> None:
        errors = collect_empty_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    pass\n",
        )
        self.assertEqual(
            errors,
            ["空异常处理违规: sample.py:3 -> except 块不能只写 pass/省略号"],
        )

    def test_powershell_empty_catch_is_blocked(self) -> None:
        errors = collect_empty_exception_errors_for_powershell_text(
            Path("sample.ps1"),
            "try { Invoke-Thing } catch {\n    # ignore\n}\n",
        )
        self.assertEqual(
            errors,
            ["空异常处理违规: sample.ps1:1 -> catch 块不能为空或只含注释"],
        )

    def test_non_empty_exception_handling_passes(self) -> None:
        self.assertEqual(
            collect_empty_exception_errors_for_python_text(
                Path("sample.py"),
                "try:\n    work()\nexcept OSError as error:\n    raise RuntimeError(str(error))\n",
            ),
            [],
        )
        self.assertEqual(
            collect_empty_exception_errors_for_powershell_text(
                Path("sample.ps1"),
                "try { Invoke-Thing } catch { throw $_ }\n",
            ),
            [],
        )

    def test_reference_redlines_pass_current_baseline(self) -> None:
        self.assertEqual(collect_errors(), [])


if __name__ == "__main__":
    unittest.main()
