from __future__ import annotations

import ast
import io
import inspect
import json
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
TOOLS_CHECKS_ROOT = REPO_ROOT / "tools" / "checks"
if str(TOOLS_CHECKS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_CHECKS_ROOT))

import tools.checks.check_mvp_operator_flow as operator_flow  # noqa: E402


class MvpOperatorFlowCheckTest(unittest.TestCase):
    def test_first_unique_db_steps_skip_redundant_reset_flags(self) -> None:
        source = inspect.getsource(operator_flow)
        module = ast.parse(source)
        run_json_args_by_label: dict[str, list[str]] = {}
        for node in ast.walk(module):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name) or node.func.id != "run_json":
                continue
            if len(node.args) < 2:
                continue
            if not isinstance(node.args[0], ast.List) or not isinstance(node.args[1], ast.Constant):
                continue
            label = node.args[1].value
            if not isinstance(label, str):
                continue
            run_json_args_by_label[label] = [
                str(item.value)
                for item in node.args[0].elts
                if isinstance(item, ast.Constant) and isinstance(item.value, str)
            ]

        first_unique_db_labels = [
            "operator-flow/service-run",
            "operator-flow/seed-failed",
            "operator-flow/seed-crash",
            "operator-flow/seed-hibernated",
            "operator-flow/seed-failed-stalled",
            "operator-flow/seed-failed-contended-a",
            "operator-flow/seed-failed-quarantine-a",
            "operator-flow/seed-crash-reconcile",
            "operator-flow/seed-crash-session-priority-a",
            "operator-flow/seed-crash-owner-alignment-a",
        ]
        for label in first_unique_db_labels:
            self.assertIn(label, run_json_args_by_label)
            self.assertNotIn("--reset", run_json_args_by_label[label], label)

    def test_operator_flow_keeps_only_core_session_wait_labels(self) -> None:
        source = inspect.getsource(operator_flow)
        module = ast.parse(source)
        wait_labels: list[str] = []
        for node in ast.walk(module):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name) or node.func.id != "wait_for_session":
                continue
            if len(node.args) < 5 or not isinstance(node.args[4], ast.Constant):
                continue
            wait_labels.append(str(node.args[4].value))

        self.assertEqual(
            wait_labels,
            [
                "operator-flow/service-run",
                "operator-flow/seed-failed",
                "operator-flow/seed-crash",
                "operator-flow/seed-hibernated",
            ],
        )

    def test_service_resume_combo_omits_report_step_in_operator_flow(self) -> None:
        source = inspect.getsource(operator_flow)
        resume_block = source.split("service_resume = run_json(", 1)[1].split(
            "seed_failed_stalled = run_json(",
            1,
        )[0]
        self.assertNotIn('"--report"', resume_block)
        self.assertNotIn('expected_steps=["resume", "service-status", "report"]', resume_block)
        self.assertNotIn("expect_report_payload=True", resume_block)

    def test_reset_operator_flow_progress_resets_counter_and_refreshes_start_time(self) -> None:
        with mock.patch("tools.checks.check_mvp_operator_flow.time.monotonic", return_value=12.5):
            operator_flow._OPERATOR_FLOW_STEP_COUNTER = 9
            operator_flow.reset_operator_flow_progress()
        self.assertEqual(operator_flow._OPERATOR_FLOW_STEP_COUNTER, 0)
        self.assertEqual(operator_flow._OPERATOR_FLOW_STARTED_AT, 12.5)

    def test_run_json_emits_start_and_done_markers(self) -> None:
        payload = {
            "ok": True,
            "action": "doctor",
            "schema_version": operator_flow.SCHEMA_VERSION,
            "result": {},
        }
        errors: list[str] = []
        stdout = io.StringIO()
        with mock.patch.object(operator_flow, "_OPERATOR_FLOW_STEP_COUNTER", 0), mock.patch.object(
            operator_flow,
            "_OPERATOR_FLOW_STARTED_AT",
            5.0,
        ), mock.patch(
            "tools.checks.check_mvp_operator_flow.time.monotonic",
            side_effect=[10.0, 11.5],
        ), mock.patch(
            "tools.checks.check_mvp_operator_flow.load_json",
            return_value=(0, json.dumps(payload), payload),
        ) as load_json_mock, redirect_stdout(stdout):
            result = operator_flow.run_json(["doctor"], "operator-flow/doctor", errors)

        self.assertEqual(result, payload)
        self.assertEqual(errors, [])
        load_json_mock.assert_called_once_with(["doctor"])
        output = stdout.getvalue()
        self.assertIn(
            "[operator-flow 001] start +5.0s => operator-flow/doctor :: doctor --json",
            output,
        )
        self.assertIn("[operator-flow 001] done exit=0 status=ok duration=1.5s", output)

    def test_load_json_runs_wrapper_main_in_process(self) -> None:
        payload = {
            "ok": True,
            "action": "doctor",
            "schema_version": operator_flow.SCHEMA_VERSION,
            "result": {},
        }
        module = mock.Mock()

        def fake_main(argv: list[str]) -> int:
            print(json.dumps(payload))
            return 0

        module.main.side_effect = fake_main
        with mock.patch(
            "tools.checks.check_mvp_operator_flow.load_safeclaw_mvp_module",
            return_value=module,
        ):
            exit_code, output, loaded = operator_flow.load_json(["doctor"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(loaded, payload)
        self.assertEqual(output, json.dumps(payload))
        module.main.assert_called_once_with(["safeclaw_mvp.py", "doctor", "--json"])

    def test_wait_for_session_emits_matched_done_marker(self) -> None:
        payload = {
            "ok": True,
            "action": "session",
            "result": {
                "task_id": "task-a",
                "db": "db.sqlite",
                "output": "out.txt",
                "owner_id": "owner-a",
            },
        }
        errors: list[str] = []
        stdout = io.StringIO()
        with mock.patch.object(operator_flow, "_OPERATOR_FLOW_STEP_COUNTER", 0), mock.patch.object(
            operator_flow,
            "_OPERATOR_FLOW_STARTED_AT",
            2.0,
        ), mock.patch(
            "tools.checks.check_mvp_operator_flow.time.monotonic",
            side_effect=[4.0, 4.2],
        ), mock.patch.object(
            operator_flow,
            "load_json",
            return_value=(0, "", payload),
        ), redirect_stdout(stdout):
            operator_flow.wait_for_session(
                "task-a",
                "db.sqlite",
                "out.txt",
                errors,
                "operator-flow/wait",
                owner_id="owner-a",
            )

        self.assertEqual(errors, [])
        output = stdout.getvalue()
        self.assertIn(
            "[operator-flow 001] start +2.0s => operator-flow/wait :: wait-session task=task-a",
            output,
        )
        self.assertIn(
            "[operator-flow 001] done exit=0 status=matched tries=1 duration=0.2s",
            output,
        )


if __name__ == "__main__":
    unittest.main()
