from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.checks.check_public_docs import (  # noqa: E402
    LINT_README_FILE,
    MVP_README_FILE,
    OPERATOR_PLAYBOOK_FILE,
    REQUIRED_MARKERS,
    collect_errors,
    collect_reference_rebaseline_errors,
)


class PublicDocsCheckTest(unittest.TestCase):
    def test_newly_added_public_readmes_are_guarded_by_public_docs_check(self) -> None:
        expected_entries = {
            MVP_README_FILE: [
                "tools/mvp/README.md",
                ".github/workflows/contracts.yml",
                "ledger_index_manifest.py",
                "check_ledger_alignment.py",
                "check_consistency.py",
                "check_versions.py",
                "check_structure.py",
                "check_scaffold.py",
                "check_public_docs.py",
                "Contract tests",
            ],
            OPERATOR_PLAYBOOK_FILE: [
                "workspace --name demo",
                "doctor",
                "service-run --report",
                "service-status --limit 5",
                "service-retry --report",
                "service-recover --report",
                "verify --json",
                "local-only",
                "ai-reason",
                "tools\\checks\\selfcheck.py",
                "ledger_index_manifest.py",
                "check_ledger_alignment.py",
                "check_consistency.py",
                "check_versions.py",
                "check_structure.py",
                "check_scaffold.py",
                "check_public_docs.py",
                "Contract tests",
            ],
            LINT_README_FILE: [
                "tools/lint/check_naming.py",
                ".github/workflows/contracts.yml",
                "ledger_index_manifest.py",
                "check_ledger_alignment.py",
                "check_consistency.py",
                "check_versions.py",
                "check_structure.py",
                "check_scaffold.py",
                "check_public_docs.py",
                "Contract tests",
            ],
        }

        for readme_file, expected_markers in expected_entries.items():
            with self.subTest(readme=readme_file.relative_to(REPO_ROOT).as_posix()):
                self.assertIn(readme_file, REQUIRED_MARKERS)
                self.assertEqual(REQUIRED_MARKERS[readme_file], expected_markers)

    def test_reference_rebaseline_doc_passes_current_baseline(self) -> None:
        self.assertEqual(collect_reference_rebaseline_errors(), [])

    def test_public_docs_alignment_passes_current_baseline(self) -> None:
        self.assertEqual(collect_errors(), [])


if __name__ == "__main__":
    unittest.main()
