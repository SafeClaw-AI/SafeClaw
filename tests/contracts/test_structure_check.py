from __future__ import annotations

import unittest

from tests.contracts import REPO_ROOT
from tools.checks.check_structure import (
    LEDGER_TARGET_PREFIX,
    collect_ledger_path_policy_errors,
)


class StructureCheckTest(unittest.TestCase):
    def test_ledger_target_prefix_is_docs_records(self) -> None:
        self.assertEqual(LEDGER_TARGET_PREFIX, "docs/records/")

    def test_ledger_path_policy_passes_current_baseline(self) -> None:
        self.assertEqual(collect_ledger_path_policy_errors(), [])


if __name__ == "__main__":
    unittest.main()
