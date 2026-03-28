from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.checks.check_structure import (  # noqa: E402
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
