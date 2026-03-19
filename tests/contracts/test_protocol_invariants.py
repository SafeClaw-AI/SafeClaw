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
        cls.repo_version = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()

    def test_worker_lifecycle_contains_critical_states(self) -> None:
        worker = self.index.require("specs/state-machines/worker_lifecycle.json").data
        states = worker.get("states", {})
        critical_states = {
            "awaiting_confirmation",
            "hibernated",
            "awaiting_doctor",
            "repair_failed",
            "failed_terminal",
        }
        self.assertTrue(critical_states.issubset(states.keys()))

    def test_worker_terminal_states_match_terminal_flags(self) -> None:
        worker = self.index.require("specs/state-machines/worker_lifecycle.json").data
        states = worker.get("states", {})
        flagged_terminal = {
            name for name, value in states.items() if value.get("terminal") is True
        }
        declared_terminal = set(worker.get("terminal_states", []))
        self.assertSetEqual(flagged_terminal, declared_terminal)

    def test_worker_system_budgets_are_positive(self) -> None:
        worker = self.index.require("specs/state-machines/worker_lifecycle.json").data
        budgets = worker.get("system_budgets", {})
        self.assertGreaterEqual(budgets.get("max_frozen_tasks", 0), 1)
        self.assertGreaterEqual(budgets.get("max_freeze_duration_s", 0), 1)
        self.assertGreaterEqual(budgets.get("hibernate_retention_days", 0), 1)
        self.assertGreaterEqual(budgets.get("confirm_queue_size", 0), 1)

    def test_effect_ledger_commit_protocol_keeps_five_steps(self) -> None:
        effect = self.index.require("specs/schemas/effect_ledger.json").data
        commit_order = effect.get("commit_order", {})
        steps = commit_order.get("steps", [])
        self.assertEqual(len(steps), 5)
        self.assertIn("②→③", commit_order.get("highest_risk_breakpoint", ""))
        self.assertIn("禁止盲目重试", commit_order.get("recovery_principle", ""))

    def test_effect_ledger_schema_version_matches_repo_version(self) -> None:
        effect = self.index.require("specs/schemas/effect_ledger.json").data
        schema_version = effect.get("properties", {}).get("schema_version", {}).get("const")
        self.assertEqual(schema_version, self.repo_version)

    def test_preflight_runtime_and_degradation_rules_are_strict(self) -> None:
        preflight = self.index.require("specs/config/preflight.json").data
        action_tiers = self.index.require("specs/schemas/action_tiers.json").data
        degradation = preflight.get("degradation", {})
        runtime = preflight.get("runtime", {})
        rule = action_tiers.get("preflight_rules", {})

        self.assertEqual(degradation.get("on_timeout"), "escalate_to_tier_2")
        self.assertEqual(degradation.get("on_exception"), "escalate_to_tier_2")
        self.assertEqual(degradation.get("on_low_confidence"), "escalate_to_tier_1_with_warn")
        self.assertTrue(runtime.get("escalation_allowed"))
        self.assertTrue(runtime.get("degradation_forbidden"))
        self.assertTrue(runtime.get("delta_confirm_only"))
        self.assertTrue(rule.get("runtime_escalation_only"))
        self.assertTrue(rule.get("runtime_degradation_forbidden"))
        self.assertEqual(rule.get("unknown_action_default_tier"), "TIER_2")
        self.assertGreaterEqual(preflight.get("metrics", {}).get("static_hit_rate_target", 0), 0.9)

    def test_sys_errors_registry_is_unique_and_registered(self) -> None:
        sys_errors = self.index.require("specs/error-codes/sys_errors.json").data
        errors = sys_errors.get("errors", {})
        severity_levels = set(sys_errors.get("severity_levels", {}).keys())
        categories = set(sys_errors.get("categories", []))
        codes = [value.get("code") for value in errors.values()]

        self.assertEqual(len(codes), len(set(codes)))
        for error_name, value in errors.items():
            with self.subTest(error_name=error_name):
                self.assertIn(value.get("severity"), severity_levels)
                self.assertIn(value.get("category"), categories)

    def test_spi_registry_matches_public_extension_points(self) -> None:
        spi = self.index.require("specs/spi/base_fields.json").data
        registry = spi.get("registry", [])
        timeout_schema = spi.get("properties", {}).get("timeout_ms", {})
        spi_names = [item.get("spi_name") for item in registry]

        self.assertEqual(len(spi_names), len(set(spi_names)))
        self.assertSetEqual(
            set(spi_names),
            {"channel_driver", "plugin_runner", "repair_plan", "memory"},
        )
        for item in registry:
            with self.subTest(spi_name=item.get("spi_name")):
                self.assertGreaterEqual(item.get("default_timeout_ms", 0), timeout_schema.get("minimum", 0))
                self.assertLessEqual(item.get("default_timeout_ms", 0), timeout_schema.get("maximum", 10**9))


if __name__ == "__main__":
    unittest.main()
