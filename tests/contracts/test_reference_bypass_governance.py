from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.checks.reference_bypass_governance import (
    BYPASS_KEY_TO_LABEL,
    NOQA_BYPASS,
    collect_bypass_whitelist_errors,
    collect_observed_bypass_occurrences,
    load_bypass_whitelist,
)


class ReferenceBypassGovernanceTest(unittest.TestCase):
    def test_bypass_whitelist_passes_current_baseline(self) -> None:
        self.assertEqual(collect_bypass_whitelist_errors(), [])

    def test_bypass_whitelist_detects_current_supported_types(self) -> None:
        whitelist = load_bypass_whitelist()
        by_type = {entry.bypass_key for entry in whitelist}
        self.assertEqual(
            by_type,
            {NOQA_BYPASS},
        )
        self.assertEqual(BYPASS_KEY_TO_LABEL[NOQA_BYPASS], "# noqa")

    def test_bypass_whitelist_requires_registration_for_new_noqa(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            source_file = repo_root / "pkg" / "sample.py"
            source_file.parent.mkdir(parents=True, exist_ok=True)
            source_file.write_text("from sample import value  # noqa: E402\n", encoding="utf-8")

            whitelist_file = repo_root / "docs" / "reference" / "03-绕过白名单.md"
            whitelist_file.parent.mkdir(parents=True, exist_ok=True)
            whitelist_file.write_text(
                "# 绕过白名单\n\n## 绕过白名单\n\n| 对象标识 | 绕过类型 | 标记 | 责任人 | 复查周期 | 原因 |\n"
                "| --- | --- | --- | --- | --- | --- |\n",
                encoding="utf-8",
            )

            from tools.checks import reference_bypass_governance as module

            original_repo_root = module.REPO_ROOT
            original_whitelist_file = module.REFERENCE_BYPASS_WHITELIST_FILE
            try:
                module.REPO_ROOT = repo_root
                module.REFERENCE_BYPASS_WHITELIST_FILE = whitelist_file
                errors = collect_bypass_whitelist_errors()
            finally:
                module.REPO_ROOT = original_repo_root
                module.REFERENCE_BYPASS_WHITELIST_FILE = original_whitelist_file

        self.assertEqual(
            errors,
            ["绕过未登记: pkg/sample.py:1 -> # noqa (# noqa: E402)"],
        )

    def test_bypass_whitelist_detects_stale_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            whitelist_file = repo_root / "docs" / "reference" / "03-绕过白名单.md"
            whitelist_file.parent.mkdir(parents=True, exist_ok=True)
            whitelist_file.write_text(
                "# 绕过白名单\n\n## 绕过白名单\n\n| 对象标识 | 绕过类型 | 标记 | 责任人 | 复查周期 | 原因 |\n"
                "| --- | --- | --- | --- | --- | --- |\n"
                "| `pkg/sample.py:1` | `# noqa` | `# noqa: E402` | `tests-owner` | `每季度` | `临时测试条目。` |\n",
                encoding="utf-8",
            )

            from tools.checks import reference_bypass_governance as module

            original_repo_root = module.REPO_ROOT
            original_whitelist_file = module.REFERENCE_BYPASS_WHITELIST_FILE
            try:
                module.REPO_ROOT = repo_root
                module.REFERENCE_BYPASS_WHITELIST_FILE = whitelist_file
                errors = collect_bypass_whitelist_errors()
            finally:
                module.REPO_ROOT = original_repo_root
                module.REFERENCE_BYPASS_WHITELIST_FILE = original_whitelist_file

        self.assertEqual(
            errors,
            ["绕过白名单未清零: pkg/sample.py:1 -> # noqa"],
        )

    def test_warning_filter_scan_skips_test_assertion_literals(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            test_file = repo_root / "tests" / "test_sample.py"
            test_file.parent.mkdir(parents=True, exist_ok=True)
            test_file.write_text(
                'self.assertEqual(value, "ignore::DeprecationWarning")\n',
                encoding="utf-8",
            )

            from tools.checks import reference_bypass_governance as module

            original_repo_root = module.REPO_ROOT
            try:
                module.REPO_ROOT = repo_root
                occurrences = collect_observed_bypass_occurrences()
            finally:
                module.REPO_ROOT = original_repo_root

        self.assertEqual(occurrences, ())

    def test_comment_style_bypass_scan_ignores_python_string_literals(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            module_file = repo_root / "pkg" / "labels.py"
            module_file.parent.mkdir(parents=True, exist_ok=True)
            module_file.write_text(
                'NOQA_LABEL = "# noqa"\n'
                'TYPE_IGNORE_LABEL = "type: ignore"\n'
                'PRAGMA_LABEL = "pragma: no cover"\n'
                'NOLINT_LABEL = "nolint"\n',
                encoding="utf-8",
            )

            from tools.checks import reference_bypass_governance as module

            original_repo_root = module.REPO_ROOT
            try:
                module.REPO_ROOT = repo_root
                occurrences = collect_observed_bypass_occurrences()
            finally:
                module.REPO_ROOT = original_repo_root

        self.assertEqual(occurrences, ())
