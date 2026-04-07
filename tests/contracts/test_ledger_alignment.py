from __future__ import annotations

import unittest

from tests.contracts import REPO_ROOT
from tools.checks.check_ledger_alignment import collect_ledger_errors


class LedgerAlignmentTest(unittest.TestCase):
    def test_collect_ledger_errors_passes_current_baseline(self) -> None:
        self.assertEqual(collect_ledger_errors(), [])


if __name__ == "__main__":
    unittest.main()
