from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tests.contracts import REPO_ROOT
from tools.checks.check_ledger_alignment import (
    ROOT_COMPAT_STUB_FORBIDDEN_MARKERS,
    ROOT_COMPAT_STUB_REQUIRED_MARKERS,
    collect_root_compat_stub_errors,
)
from tools.checks.ledger_index_manifest import (
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

    def test_dev_plan_entry_uses_target_primary_baseline(self) -> None:
        entry = self.manifest.require("dev-plan")
        self.assertEqual(entry.legacy_path, "开发计划.md")
        self.assertEqual(entry.target_path, "docs/records/开发计划.md")
        self.assertEqual(entry.read_order, ("target_path",))
        self.assertEqual(entry.write_mode, "target-primary")
        self.assertEqual(entry.cutover_state, "legacy-retired")

    def test_resolve_existing_path_uses_target_baseline(self) -> None:
        resolved = self.manifest.resolve_existing_path("mvp-progress")
        self.assertEqual(
            resolved.relative_to(REPO_ROOT).as_posix(),
            "docs/records/MVP_PROGRESS.md",
        )

    def test_read_resolved_text_supports_dev_plan(self) -> None:
        resolved, text = self.manifest.read_resolved_text("dev-plan")
        self.assertEqual(
            resolved.relative_to(REPO_ROOT).as_posix(),
            "docs/records/开发计划.md",
        )
        self.assertIn("# 开发计划", text)
        self.assertIn("当前主线", text)

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

    def test_root_compat_stubs_keep_required_markers(self) -> None:
        for logical_id, markers in ROOT_COMPAT_STUB_REQUIRED_MARKERS.items():
            entry = self.manifest.require(logical_id)
            text = (REPO_ROOT / entry.legacy_path).read_text(encoding="utf-8")
            for marker in markers:
                self.assertIn(marker, text)

    def test_collect_root_compat_stub_errors_accepts_current_repo_state(self) -> None:
        self.assertEqual(collect_root_compat_stub_errors(self.manifest, REPO_ROOT), [])

    def test_collect_root_compat_stub_errors_rejects_retired_body_markers(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            for logical_id, entry in self.manifest.by_logical_id.items():
                content = "\n".join(ROOT_COMPAT_STUB_REQUIRED_MARKERS[logical_id]) + "\n"
                if logical_id == "dev-plan":
                    content += f"\n{ROOT_COMPAT_STUB_FORBIDDEN_MARKERS[0]}\n"
                (temp_root / entry.legacy_path).write_text(content, encoding="utf-8")

            errors = collect_root_compat_stub_errors(self.manifest, temp_root)

        self.assertTrue(
            any(
                "开发计划.md" in item and ROOT_COMPAT_STUB_FORBIDDEN_MARKERS[0] in item
                for item in errors
            )
        )


if __name__ == "__main__":
    unittest.main()
