from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.checks.check_consistency import collect_ledger_manifest_doc_errors  # noqa: E402


class ConsistencyCheckTest(unittest.TestCase):
    def test_ledger_manifest_doc_consistency_passes_current_baseline(self) -> None:
        self.assertEqual(collect_ledger_manifest_doc_errors(), [])


if __name__ == "__main__":
    unittest.main()
