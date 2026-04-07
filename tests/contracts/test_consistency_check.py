from __future__ import annotations

import unittest

from tests.contracts import REPO_ROOT
from tools.checks.check_consistency import collect_ledger_manifest_doc_errors


class ConsistencyCheckTest(unittest.TestCase):
    def test_ledger_manifest_doc_consistency_passes_current_baseline(self) -> None:
        self.assertEqual(collect_ledger_manifest_doc_errors(), [])


if __name__ == "__main__":
    unittest.main()
