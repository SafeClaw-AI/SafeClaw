from __future__ import annotations

import unittest

from tests.contracts import REPO_ROOT
from tools.checks.check_versions import (
    LEDGER_SLICE_A_PHASE,
    collect_errors,
    collect_ledger_version_errors,
)


class VersionCheckTest(unittest.TestCase):
    def test_ledger_slice_a_phase_is_stable(self) -> None:
        self.assertEqual(LEDGER_SLICE_A_PHASE, "slice-a-baseline")

    def test_ledger_version_policy_passes_current_baseline(self) -> None:
        self.assertEqual(collect_ledger_version_errors(), [])

    def test_version_consistency_passes_current_baseline(self) -> None:
        self.assertEqual(collect_errors(), [])


if __name__ == "__main__":
    unittest.main()
