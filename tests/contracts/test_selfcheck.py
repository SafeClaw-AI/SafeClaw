from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.checks.selfcheck import (  # noqa: E402
    ASYNC_TAIL_CHECKS,
    ASYNC_TAIL_START_CHECK_NAME,
    CHECKS,
    CONTRACT_TESTS_CHECK_NAME,
    LEDGER_POLICY_CHECKS,
    SUBPROCESS_ENV_OVERRIDES,
    TOOLING_SMOKE_CHECK_NAME,
    TOOLING_SMOKE_COVERED_CHECKS,
    build_check_env,
)

REFERENCE_REDLINES_CHECK_NAME = "Reference redlines"
NAMING_LINT_CHECK_NAME = "Naming lint"
MVP_OPERATOR_FLOW_CHECK_NAME = "MVP operator flow"
EXAMPLE_SMOKE_CHECK_NAME = "Example smoke"
GENERATED_SYNC_CHECK_NAME = "Generated sync"


class SelfcheckTest(unittest.TestCase):
    def test_ledger_policy_chain_is_front_loaded(self) -> None:
        expected_prefix = [name for name, _ in LEDGER_POLICY_CHECKS]
        self.assertEqual([name for name, _ in CHECKS[: len(expected_prefix)]], expected_prefix)

    def test_reference_redlines_run_after_ledger_policy_chain(self) -> None:
        names = [name for name, _ in CHECKS]
        self.assertEqual(names.index(REFERENCE_REDLINES_CHECK_NAME), len(LEDGER_POLICY_CHECKS))
        self.assertLess(names.index(REFERENCE_REDLINES_CHECK_NAME), names.index(NAMING_LINT_CHECK_NAME))

    def test_contract_tests_run_after_reference_redlines(self) -> None:
        names = [name for name, _ in CHECKS]
        self.assertGreater(names.index(CONTRACT_TESTS_CHECK_NAME), names.index(REFERENCE_REDLINES_CHECK_NAME))

    def test_tooling_smoke_transitively_covers_mvp_operator_flow(self) -> None:
        names = [name for name, _ in CHECKS]
        self.assertIn(TOOLING_SMOKE_CHECK_NAME, names)
        self.assertNotIn(MVP_OPERATOR_FLOW_CHECK_NAME, names)
        self.assertEqual(
            TOOLING_SMOKE_COVERED_CHECKS[TOOLING_SMOKE_CHECK_NAME],
            (MVP_OPERATOR_FLOW_CHECK_NAME,),
        )

    def test_async_tail_checks_are_isolated_to_slow_non_locking_checks(self) -> None:
        async_names = [name for name, _ in ASYNC_TAIL_CHECKS]
        self.assertEqual(async_names, [EXAMPLE_SMOKE_CHECK_NAME, GENERATED_SYNC_CHECK_NAME])

    def test_async_tail_starts_at_tooling_smoke_boundary(self) -> None:
        self.assertEqual(ASYNC_TAIL_START_CHECK_NAME, TOOLING_SMOKE_CHECK_NAME)

    def test_selfcheck_subprocess_env_pins_default_warning_behavior(self) -> None:
        self.assertEqual(SUBPROCESS_ENV_OVERRIDES, {"PYTHONWARNINGS": "default"})

    def test_build_check_env_keeps_existing_env_and_resets_warning_behavior(self) -> None:
        with mock.patch.dict("os.environ", {"FOO": "bar", "PYTHONWARNINGS": "error"}, clear=True):
            env = build_check_env()
        self.assertEqual(env["FOO"], "bar")
        self.assertEqual(env["PYTHONWARNINGS"], "default")


if __name__ == "__main__":
    unittest.main()
