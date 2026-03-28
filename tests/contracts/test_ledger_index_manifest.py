from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.checks.ledger_index_manifest import (  # noqa: E402
    LEDGER_INDEX_MANIFEST_FILE,
    load_ledger_index_manifest,
)


class LedgerIndexManifestTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = load_ledger_index_manifest()

    def test_manifest_file_exists(self) -> None:
        self.assertTrue(LEDGER_INDEX_MANIFEST_FILE.exists())

    def test_manifest_contains_expected_ledgers(self) -> None:
        self.assertEqual(
            set(self.manifest.by_logical_id.keys()),
            {"dev-plan", "mvp-progress", "push-log"},
        )

    def test_dev_plan_entry_uses_legacy_only_baseline(self) -> None:
        entry = self.manifest.require("dev-plan")
        self.assertEqual(entry.legacy_path, "开发计划.md")
        self.assertEqual(entry.target_path, "docs/records/开发计划.md")
        self.assertEqual(entry.read_order, ("legacy_path",))
        self.assertEqual(entry.write_mode, "legacy-only")
        self.assertEqual(entry.cutover_state, "legacy-only")

    def test_resolve_existing_path_uses_legacy_baseline(self) -> None:
        entry = self.manifest.require("mvp-progress")
        resolved = entry.resolve_existing_path()
        self.assertEqual(
            resolved.relative_to(REPO_ROOT).as_posix(),
            "MVP_PROGRESS.md",
        )

    def test_conflict_policy_is_complete(self) -> None:
        self.assertEqual(self.manifest.conflict_policy["on_divergence"], "fail-fast")
        self.assertEqual(
            self.manifest.conflict_policy["on_missing_target_when_legacy_only"],
            "fallback-legacy",
        )
        self.assertEqual(
            self.manifest.conflict_policy["on_missing_target_when_target_primary"],
            "error",
        )


if __name__ == "__main__":
    unittest.main()
