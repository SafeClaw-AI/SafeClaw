from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.checks.selfcheck import (  # noqa: E402
    CHECKS,
    CONTRACT_TESTS_CHECK_NAME,
    LEDGER_POLICY_CHECKS,
)

REFERENCE_REDLINES_CHECK_NAME = "Reference redlines"
NAMING_LINT_CHECK_NAME = "Naming lint"


class SelfcheckTest(unittest.TestCase):
    def test_ledger_policy_chain_is_front_loaded(self) -> None:
        expected_prefix = [name for name, _ in LEDGER_POLICY_CHECKS]
        self.assertEqual([name for name, _ in CHECKS[: len(expected_prefix)]], expected_prefix)

    def test_reference_redlines_run_after_ledger_policy_chain(self) -> None:
        names = [name for name, _ in CHECKS]
        self.assertEqual(names.index(REFERENCE_REDLINES_CHECK_NAME), len(LEDGER_POLICY_CHECKS))
        self.assertLess(names.index(REFERENCE_REDLINES_CHECK_NAME), names.index(NAMING_LINT_CHECK_NAME))

    def test_contract_tests_run_after_reference_redlines(self) -> None:
        names = [name for name, _ in CHECKS]
        self.assertGreater(names.index(CONTRACT_TESTS_CHECK_NAME), names.index(REFERENCE_REDLINES_CHECK_NAME))


if __name__ == "__main__":
    unittest.main()