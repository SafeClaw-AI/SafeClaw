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


class SelfcheckTest(unittest.TestCase):
    def test_ledger_policy_chain_is_front_loaded(self) -> None:
        expected_prefix = [name for name, _ in LEDGER_POLICY_CHECKS]
        self.assertEqual([name for name, _ in CHECKS[: len(expected_prefix)]], expected_prefix)

    def test_contract_tests_run_after_ledger_policy_chain(self) -> None:
        names = [name for name, _ in CHECKS]
        self.assertGreater(names.index(CONTRACT_TESTS_CHECK_NAME), len(LEDGER_POLICY_CHECKS) - 1)


if __name__ == "__main__":
    unittest.main()