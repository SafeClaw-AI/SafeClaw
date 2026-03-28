from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.checks.check_versions import (  # noqa: E402
    LEDGER_SLICE_A_PHASE,
    collect_ledger_version_errors,
)


class VersionCheckTest(unittest.TestCase):
    def test_ledger_slice_a_phase_is_stable(self) -> None:
        self.assertEqual(LEDGER_SLICE_A_PHASE, "slice-a-baseline")

    def test_ledger_version_policy_passes_current_baseline(self) -> None:
        self.assertEqual(collect_ledger_version_errors(), [])


if __name__ == "__main__":
    unittest.main()
