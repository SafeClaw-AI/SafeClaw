from __future__ import annotations

import json
import unittest
from pathlib import Path

from tests.contracts import REPO_ROOT
from tools.checks.check_governance_indexes import REQUIRED_LAYER_PATHS, collect_errors
from tools.checks.spec_index import build_spec_index
from tools.codegen.governance_index import (
    DOC_INDEX_PATH,
    README_STATUS_PATH,
    SPEC_MAP_PATH,
    TEST_MATRIX_PATH,
    build_doc_index,
    build_governance_readme,
    build_spec_map,
    build_test_matrix,
)


class GovernanceIndexesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_version = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
        cls.spec_index = build_spec_index()
        cls.expected_doc_index = build_doc_index(cls.repo_version)
        cls.expected_test_matrix = build_test_matrix(cls.repo_version)
        cls.expected_spec_map = build_spec_map(
            cls.repo_version,
            cls.spec_index,
            cls.expected_test_matrix,
        )
        cls.expected_readme = build_governance_readme(
            cls.expected_doc_index,
            cls.expected_spec_map,
            cls.expected_test_matrix,
        )

    def load_json(self, path: Path) -> dict:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        self.assertIsInstance(data, dict)
        return data

    def test_governance_json_outputs_match_current_structure(self) -> None:
        expected_payloads = {
            DOC_INDEX_PATH: self.expected_doc_index,
            SPEC_MAP_PATH: self.expected_spec_map,
            TEST_MATRIX_PATH: self.expected_test_matrix,
        }
        for path, expected_payload in expected_payloads.items():
            with self.subTest(path=path.relative_to(REPO_ROOT).as_posix()):
                self.assertTrue(path.exists())
                self.assertEqual(self.load_json(path), expected_payload)

    def test_governance_readme_matches_current_structure(self) -> None:
        self.assertTrue(README_STATUS_PATH.exists())
        self.assertEqual(README_STATUS_PATH.read_text(encoding="utf-8"), self.expected_readme)

    def test_governance_doc_index_covers_all_layers(self) -> None:
        summary = self.expected_doc_index["summary"]["layers"]
        for layer in ("L0", "L1", "L2", "L3"):
            with self.subTest(layer=layer):
                self.assertGreater(summary[layer], 0)

    def test_governance_doc_index_contains_required_layer_paths(self) -> None:
        entries = {entry["path"]: entry["layer"] for entry in self.expected_doc_index["entries"]}
        for layer, relpath in REQUIRED_LAYER_PATHS.items():
            with self.subTest(layer=layer, path=relpath):
                self.assertEqual(entries.get(relpath), layer)

    def test_governance_indexes_pass_current_baseline(self) -> None:
        self.assertEqual(collect_errors(), [])


if __name__ == "__main__":
    unittest.main()
