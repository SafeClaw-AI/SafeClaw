from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.checks.selfcheck import CHECKS  # noqa: E402


class SelfcheckTest(unittest.TestCase):
    def test_ledger_policy_chain_is_front_loaded(self) -> None:
        expected_prefix = [
            "Ledger index manifest",
            "Ledger alignment",
            "Cross-file consistency",
            "Version consistency",
            "Structure completeness",
            "Scaffold layout",
            "Public docs alignment",
        ]
        self.assertEqual([name for name, _ in CHECKS[: len(expected_prefix)]], expected_prefix)

    def test_contract_tests_run_after_public_docs_alignment(self) -> None:
        names = [name for name, _ in CHECKS]
        self.assertGreater(names.index("Contract tests"), names.index("Public docs alignment"))


if __name__ == "__main__":
    unittest.main()