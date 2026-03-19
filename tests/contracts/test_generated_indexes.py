from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.checks.spec_index import build_spec_index  # noqa: E402
from tools.codegen.main import SUPPORTED_TARGETS, build_generated_index, build_manifest, build_stable_ids  # noqa: E402


class GeneratedIndexesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.index = build_spec_index()
        cls.repo_version = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
        cls.generated_root = REPO_ROOT / "generated"
        cls.expected_stable_ids = build_stable_ids(cls.index)

    def load_json(self, path: Path) -> dict:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        self.assertIsInstance(data, dict)
        return data

    def test_generated_targets_exist(self) -> None:
        for target in SUPPORTED_TARGETS:
            with self.subTest(target=target):
                self.assertTrue((self.generated_root / target).is_dir())

    def test_generated_manifest_matches_specs(self) -> None:
        for target in SUPPORTED_TARGETS:
            with self.subTest(target=target):
                manifest_path = self.generated_root / target / "manifest.json"
                actual = self.load_json(manifest_path)
                expected = build_manifest(target, self.repo_version, self.index)
                self.assertEqual(actual, expected)

    def test_generated_stable_ids_match_specs(self) -> None:
        for target in SUPPORTED_TARGETS:
            with self.subTest(target=target):
                stable_ids_path = self.generated_root / target / "stable_ids.json"
                actual = self.load_json(stable_ids_path)
                self.assertEqual(actual, self.expected_stable_ids)

    def test_generated_manifest_versions_are_consistent(self) -> None:
        for target in SUPPORTED_TARGETS:
            with self.subTest(target=target):
                manifest = self.load_json(self.generated_root / target / "manifest.json")
                self.assertEqual(manifest.get("protocol_version"), self.repo_version)
                specs = manifest.get("specs", [])
                self.assertEqual(manifest.get("spec_count"), len(specs))
                self.assertEqual(len(specs), len(self.index.documents))

    def test_generated_stable_ids_include_critical_protocol_axes(self) -> None:
        for target in SUPPORTED_TARGETS:
            with self.subTest(target=target):
                stable_ids = self.load_json(self.generated_root / target / "stable_ids.json")
                self.assertIn("worker", stable_ids)
                self.assertIn("tiers", stable_ids)
                self.assertIn("reversibility", stable_ids)
                self.assertIn("error_codes", stable_ids)
                self.assertIn("spi_names", stable_ids)

    def test_generated_root_index_matches_targets(self) -> None:
        outputs = [
            {
                "target": target,
                "target_dir": str((self.generated_root / target).resolve()),
                "manifest": str((self.generated_root / target / "manifest.json").resolve()),
                "stable_ids": str((self.generated_root / target / "stable_ids.json").resolve()),
            }
            for target in SUPPORTED_TARGETS
        ]
        actual = self.load_json(self.generated_root / "index.json")
        expected = build_generated_index(self.repo_version, outputs)
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
