from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.checks.spec_index import build_spec_index  # noqa: E402


class SpecsContractsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.index = build_spec_index()

    def test_specs_directory_is_not_empty(self) -> None:
        self.assertGreater(len(self.index.documents), 0)

    def test_every_spec_has_contract_metadata(self) -> None:
        required_keys = {"$schema", "$id", "title", "version"}
        for doc in self.index.documents:
            with self.subTest(doc=doc.relpath):
                self.assertTrue(required_keys.issubset(doc.data.keys()))

    def test_worker_lifecycle_has_unique_state_ids(self) -> None:
        worker = self.index.require("specs/state-machines/worker_lifecycle.json").data
        states = worker.get("states", {})
        state_ids = [state["state_id"] for state in states.values()]
        self.assertEqual(len(state_ids), len(set(state_ids)))

    def test_worker_lifecycle_has_unique_event_ids(self) -> None:
        worker = self.index.require("specs/state-machines/worker_lifecycle.json").data
        transitions = worker.get("transitions", [])
        event_ids = [item["event_id"] for item in transitions]
        self.assertEqual(len(event_ids), len(set(event_ids)))

    def test_worker_transitions_reference_defined_states(self) -> None:
        worker = self.index.require("specs/state-machines/worker_lifecycle.json").data
        states = set(worker.get("states", {}).keys())
        transitions = worker.get("transitions", [])
        for item in transitions:
            with self.subTest(event_id=item["event_id"]):
                self.assertIn(item["from"], states)
                self.assertIn(item["to"], states)

    def test_effect_ledger_has_append_only_transitions_contract(self) -> None:
        effect = self.index.require("specs/schemas/effect_ledger.json").data
        props = effect.get("properties", {})
        transitions = props.get("transitions", {})
        self.assertEqual(transitions.get("type"), "array")
        items = transitions.get("items", {})
        required = set(items.get("required", []))
        self.assertTrue({"from_status", "to_status", "at", "triggered_by"}.issubset(required))


if __name__ == "__main__":
    unittest.main()
