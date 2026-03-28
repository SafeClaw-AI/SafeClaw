from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.checks.check_scaffold import (  # noqa: E402
    LEGACY_REQUIRED_STATES,
    collect_ledger_scaffold_errors,
)


class ScaffoldCheckTest(unittest.TestCase):
    def test_legacy_required_states_are_stable(self) -> None:
        self.assertEqual(LEGACY_REQUIRED_STATES, {"legacy-only", "dual-readable"})

    def test_ledger_scaffold_policy_passes_current_baseline(self) -> None:
        self.assertEqual(collect_ledger_scaffold_errors(), [])


if __name__ == "__main__":
    unittest.main()
