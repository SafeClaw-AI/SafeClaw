from __future__ import annotations

import unittest

from tests.contracts import REPO_ROOT
from tools.checks.spec_index import build_spec_index


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
        states = worker["states"]
        state_ids = [s["state_id"] for s in states.values()]
        self.assertEqual(len(state_ids), len(set(state_ids)))

    def test_worker_lifecycle_has_unique_event_ids(self) -> None:
        worker = self.index.require("specs/state-machines/worker_lifecycle.json").data
        event_ids = [t["event_id"] for t in worker["transitions"]]
        self.assertEqual(len(event_ids), len(set(event_ids)))

    def test_worker_transitions_reference_defined_states(self) -> None:
        worker = self.index.require("specs/state-machines/worker_lifecycle.json").data
        states = set(worker["states"].keys())
        for t in worker["transitions"]:
            with self.subTest(event_id=t["event_id"]):
                self.assertIn(t["from"], states)
                self.assertIn(t["to"], states)

    def test_worker_terminal_states_match_flags(self) -> None:
        worker = self.index.require("specs/state-machines/worker_lifecycle.json").data
        flagged = {n for n, v in worker["states"].items() if v.get("terminal")}
        declared = set(worker["terminal_states"])
        self.assertSetEqual(flagged, declared)

    def test_effect_ledger_has_append_only_transitions(self) -> None:
        effect = self.index.require("specs/schemas/effect_ledger.json").data
        transitions = effect["properties"]["transitions"]
        self.assertEqual(transitions["type"], "array")
        required = set(transitions["items"]["required"])
        self.assertTrue({"from_status", "to_status", "at", "triggered_by"}.issubset(required))

    def test_effect_attempt_schema_exists_and_is_valid(self) -> None:
        attempt = self.index.require("specs/schemas/effect_attempt.json").data
        self.assertIn("attempt_seq", attempt["required"])
        self.assertIn("fencing_token", attempt["required"])
        self.assertIn("effect_id", attempt["required"])

    def test_probe_specs_have_required_fields(self) -> None:
        for probe_path in ("specs/probes/file_write.json", "specs/probes/file_delete.json"):
            probe = self.index.require(probe_path).data
            with self.subTest(probe=probe_path):
                self.assertIn("probe_mode", probe)
                self.assertIn("probe_spec", probe)
                self.assertIn("probe_receipt", probe)

    def test_failure_model_has_required_structure(self) -> None:
        fm = self.index.require("specs/chaos/failure_model.json").data
        self.assertIn("covered_failures", fm)
        self.assertIn("not_covered", fm)
        for f in fm["covered_failures"]:
            self.assertIn("id", f)
            self.assertIn("expected_recovery", f)

    def test_task_concurrency_version_is_3_2(self) -> None:
        tc = self.index.require("specs/schemas/task_concurrency.json").data
        self.assertEqual(tc["version"], "3.2.0")


if __name__ == "__main__":
    unittest.main()
