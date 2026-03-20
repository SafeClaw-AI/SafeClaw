from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.checks.spec_index import build_spec_index  # noqa: E402


class ProtocolInvariantsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.index = build_spec_index()

    # === Effect Ledger 四阶段协议 ===

    def test_effect_ledger_has_four_phase_statuses(self) -> None:
        effect = self.index.require("specs/schemas/effect_ledger.json").data
        statuses = effect["properties"]["status"]["enum"]
        for required in ("prepared", "dispatched", "executed", "uncertain", "executed_assumed"):
            self.assertIn(required, statuses)

    def test_effect_ledger_commit_protocol_has_six_steps(self) -> None:
        effect = self.index.require("specs/schemas/effect_ledger.json").data
        steps = effect["commit_order"]["steps"]
        self.assertEqual(len(steps), 6)
        self.assertIn("prepared", steps[0])
        self.assertIn("dispatched", steps[1])

    def test_effect_ledger_highest_risk_breakpoint_is_dispatched_to_executed(self) -> None:
        effect = self.index.require("specs/schemas/effect_ledger.json").data
        self.assertIn("dispatched", effect["commit_order"]["highest_risk_breakpoint"])

    def test_effect_ledger_has_probe_mode_field(self) -> None:
        effect = self.index.require("specs/schemas/effect_ledger.json").data
        probe_mode = effect["properties"]["probe_mode"]
        self.assertIn("none", probe_mode["enum"])
        self.assertIn("auto", probe_mode["enum"])

    def test_effect_ledger_has_probe_state_field(self) -> None:
        effect = self.index.require("specs/schemas/effect_ledger.json").data
        probe_state = effect["properties"]["probe_state"]
        for state in ("probe_pending", "probing", "probe_failed", "human_frozen"):
            self.assertIn(state, probe_state["enum"])

    def test_effect_ledger_has_intent_key_not_idempotency_key(self) -> None:
        effect = self.index.require("specs/schemas/effect_ledger.json").data
        self.assertIn("intent_key", effect["required"])
        self.assertNotIn("idempotency_key", effect["required"])

    def test_effect_ledger_has_compensates_effect_id(self) -> None:
        effect = self.index.require("specs/schemas/effect_ledger.json").data
        self.assertIn("compensates_effect_id", effect["properties"])

    def test_effect_ledger_invariants_mention_scope_quarantine(self) -> None:
        effect = self.index.require("specs/schemas/effect_ledger.json").data
        invariants = " ".join(effect.get("invariants", []))
        self.assertIn("scope_quarantined", invariants)

    # === Effect Attempt 平级 Entity ===

    def test_effect_attempt_is_separate_schema(self) -> None:
        attempt = self.index.require("specs/schemas/effect_attempt.json").data
        self.assertIn("attempt_seq", attempt["required"])
        self.assertIn("fencing_token", attempt["required"])

    def test_effect_attempt_has_unique_constraint(self) -> None:
        attempt = self.index.require("specs/schemas/effect_attempt.json").data
        constraint = attempt.get("x-unique-constraint", [])
        self.assertIn("effect_id", constraint)
        self.assertIn("attempt_seq", constraint)

    # === Worker 状态机 ===

    def test_worker_lifecycle_has_uncertain_state(self) -> None:
        worker = self.index.require("specs/state-machines/worker_lifecycle.json").data
        self.assertIn("uncertain", worker["states"])

    def test_worker_lifecycle_uncertain_transitions(self) -> None:
        worker = self.index.require("specs/state-machines/worker_lifecycle.json").data
        events_from_uncertain = [
            t["event_id"] for t in worker["transitions"] if t["from"] == "uncertain"
        ]
        self.assertIn("EV_PROBE_SUCCESS", events_from_uncertain)
        self.assertIn("EV_PROBE_FAILURE", events_from_uncertain)
        self.assertIn("EV_PROBE_ASSUMED", events_from_uncertain)

    def test_worker_user_retry_has_guards(self) -> None:
        worker = self.index.require("specs/state-machines/worker_lifecycle.json").data
        retry_transition = next(
            t for t in worker["transitions"] if t["event_id"] == "EV_USER_RETRY"
        )
        guards = retry_transition.get("x-guards", [])
        self.assertIn("no_uncertain_effects", guards)
        self.assertIn("no_dispatched_effects", guards)
        self.assertIn("no_executed_assumed_effects", guards)

    def test_worker_has_reconcile_transitions(self) -> None:
        worker = self.index.require("specs/state-machines/worker_lifecycle.json").data
        event_ids = {t["event_id"] for t in worker["transitions"]}
        self.assertIn("EV_USER_RECONCILE_SUCCESS", event_ids)
        self.assertIn("EV_USER_RECONCILE_FAILURE", event_ids)

    def test_worker_reconcile_success_goes_to_committing(self) -> None:
        worker = self.index.require("specs/state-machines/worker_lifecycle.json").data
        t = next(t for t in worker["transitions"] if t["event_id"] == "EV_USER_RECONCILE_SUCCESS")
        self.assertEqual(t["from"], "failed")
        self.assertEqual(t["to"], "committing")

    def test_worker_reconcile_failure_goes_to_failed_terminal(self) -> None:
        worker = self.index.require("specs/state-machines/worker_lifecycle.json").data
        t = next(t for t in worker["transitions"] if t["event_id"] == "EV_USER_RECONCILE_FAILURE")
        self.assertEqual(t["from"], "failed")
        self.assertEqual(t["to"], "failed_terminal")

    def test_worker_invariants_mention_fencing_and_scope(self) -> None:
        worker = self.index.require("specs/state-machines/worker_lifecycle.json").data
        invariants = " ".join(worker.get("invariants", []))
        self.assertIn("fencing_token", invariants)
        self.assertIn("scope_quarantined", invariants)

    # === Task Concurrency ===

    def test_task_concurrency_auto_retry_only_prepared(self) -> None:
        tc = self.index.require("specs/schemas/task_concurrency.json").data
        blocked = tc["auto_retry"]["blocked_states"]
        for state in ("dispatched", "uncertain", "executed_assumed", "probing"):
            self.assertIn(state, blocked)

    def test_task_concurrency_has_scope_quarantine(self) -> None:
        tc = self.index.require("specs/schemas/task_concurrency.json").data
        self.assertIn("scope_quarantine", tc)
        self.assertIn("x-doctor-bypass", tc["scope_quarantine"])

    def test_task_concurrency_user_retry_guard(self) -> None:
        tc = self.index.require("specs/schemas/task_concurrency.json").data
        guard = tc["user_retry_guard"]
        blocked = guard["blocked_effect_states"]
        self.assertIn("executed_assumed", blocked)

    # === Chaos Failure Model ===

    def test_failure_model_declares_covered_and_not_covered(self) -> None:
        fm = self.index.require("specs/chaos/failure_model.json").data
        self.assertGreater(len(fm["covered_failures"]), 0)
        self.assertGreater(len(fm["not_covered"]), 0)

    def test_failure_model_wal_dirty_tail_has_limitation(self) -> None:
        fm = self.index.require("specs/chaos/failure_model.json").data
        wal = next(f for f in fm["covered_failures"] if f["id"] == "F_WAL_DIRTY_TAIL")
        self.assertIn("limitation", wal)

    # === Probe Specs ===

    def test_probe_specs_exist_for_file_operations(self) -> None:
        self.index.require("specs/probes/file_write.json")
        self.index.require("specs/probes/file_delete.json")

    # === 反例: 不应存在的旧协议 ===

    def test_no_legacy_pending_status(self) -> None:
        """旧 'pending' 状态已被 prepared/dispatched 替代"""
        effect = self.index.require("specs/schemas/effect_ledger.json").data
        statuses = effect["properties"]["status"]["enum"]
        self.assertNotIn("pending", statuses)

    def test_no_legacy_idempotency_key_in_required(self) -> None:
        """旧 idempotency_key 已被 intent_key 替代"""
        effect = self.index.require("specs/schemas/effect_ledger.json").data
        self.assertNotIn("idempotency_key", effect["required"])

    def test_no_legacy_three_step_commit(self) -> None:
        """旧三步协议已被六步四阶段替代"""
        effect = self.index.require("specs/schemas/effect_ledger.json").data
        steps = effect["commit_order"]["steps"]
        self.assertGreaterEqual(len(steps), 6)

    def test_worker_no_unguarded_retry(self) -> None:
        """EV_USER_RETRY 必须有 x-guards,不允许裸 failed→planning"""
        worker = self.index.require("specs/state-machines/worker_lifecycle.json").data
        retry = next(t for t in worker["transitions"] if t["event_id"] == "EV_USER_RETRY")
        self.assertIn("x-guards", retry)
        self.assertGreater(len(retry["x-guards"]), 0)


class PreflightAndSpiInvariantsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.index = build_spec_index()

    def test_preflight_runtime_and_degradation_rules_are_strict(self) -> None:
        preflight = self.index.require("specs/config/preflight.json").data
        action_tiers = self.index.require("specs/schemas/action_tiers.json").data
        degradation = preflight.get("degradation", {})
        runtime = preflight.get("runtime", {})
        rule = action_tiers.get("preflight_rules", {})
        self.assertEqual(degradation.get("on_timeout"), "escalate_to_tier_2")
        self.assertEqual(degradation.get("on_exception"), "escalate_to_tier_2")
        self.assertTrue(runtime.get("escalation_allowed"))
        self.assertTrue(runtime.get("degradation_forbidden"))
        self.assertTrue(rule.get("runtime_escalation_only"))

    def test_spi_registry_matches_public_extension_points(self) -> None:
        spi = self.index.require("specs/spi/base_fields.json").data
        registry = spi.get("registry", [])
        spi_names = [item.get("spi_name") for item in registry]
        self.assertEqual(len(spi_names), len(set(spi_names)))
        self.assertSetEqual(
            set(spi_names),
            {"channel_driver", "plugin_runner", "repair_plan", "memory"},
        )

    def test_sys_errors_registry_is_unique(self) -> None:
        sys_errors = self.index.require("specs/error-codes/sys_errors.json").data
        errors = sys_errors.get("errors", {})
        codes = [v.get("code") for v in errors.values()]
        self.assertEqual(len(codes), len(set(codes)))


if __name__ == "__main__":
    unittest.main()
