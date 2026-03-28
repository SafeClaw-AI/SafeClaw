from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.checks.check_ledger_alignment import collect_ledger_errors  # noqa: E402


class LedgerAlignmentTest(unittest.TestCase):
    def test_collect_ledger_errors_passes_current_baseline(self) -> None:
        self.assertEqual(collect_ledger_errors(), [])


if __name__ == "__main__":
    unittest.main()
