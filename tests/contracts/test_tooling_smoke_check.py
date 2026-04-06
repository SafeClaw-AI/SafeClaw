from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
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

import tools.checks.check_tooling_smoke as tooling_smoke  # noqa: E402
import tools.mvp.safeclaw_mvp as safeclaw_mvp  # noqa: E402


def normalize_source_whitespace(source: str) -> str:
    return " ".join(source.split())


class ToolingSmokeCheckTest(unittest.TestCase):
    def test_root_ps1_verify_uses_lightweight_invalid_json_guard(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        normalized_source = normalize_source_whitespace(source)
        self.assertIn(
            '"safeclaw.ps1", "verify", "--bogus", "--json"',
            normalized_source,
        )
        self.assertNotIn(
            '"safeclaw.ps1", "verify", "--json"]',
            normalized_source,
        )

    def test_root_cmd_verify_keeps_success_json_guard(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('"safeclaw.cmd", "verify", "--json"', source)

    def test_root_cmd_verify_uses_success_json_guard_with_sitecustomize(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        verify_command = '["cmd", "/c", "safeclaw.cmd", "verify", "--json"]'
        verify_index = source.index(verify_command)
        window = source[max(0, verify_index - 1200) : verify_index + 1200]
        self.assertIn("with tempfile.TemporaryDirectory() as verify_mock_dir:", window)
        self.assertIn("write_smoke_verify_sitecustomize(Path(verify_mock_dir))", window)
        self.assertIn("build_smoke_pythonpath_env(Path(verify_mock_dir))", window)

    def test_wrapper_cmd_verify_uses_success_json_guard(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('"tools\\mvp\\safeclaw_mvp.cmd", "verify", "--json"', source)
        self.assertNotIn('"tools\\mvp\\safeclaw_mvp.cmd", "verify"],', source)
        self.assertIn("write_smoke_verify_sitecustomize", source)
        self.assertIn("build_smoke_pythonpath_env", source)

    def test_build_smoke_pythonpath_env_prefixes_temp_dir(self) -> None:
        extra_path = Path("C:/temp/sitecustomize")
        with mock.patch.dict(os.environ, {"PYTHONPATH": "tail-segment"}, clear=False):
            env = tooling_smoke.build_smoke_pythonpath_env(extra_path)
        self.assertEqual(env["PYTHONPATH"], f"{extra_path}{os.pathsep}tail-segment")

    def test_assert_default_service_status_json_result_accepts_root_defaults(self) -> None:
        payload = {
            "db": r"target\mvp\session.db",
            "db_source": "default",
            "limit": 5,
            "current_session": None,
            "current_db": False,
            "runtime_profile": {
                "mode": "local_mvp",
                "offline_ready": True,
            },
            "model_provider": {
                "status": "not-configured",
                "degradation_mode": "local_only_ok",
            },
            "sidecar": {"status": "not-configured"},
            "offline_gate": {
                "status": "blocked",
                "reason": "ERR_AI_PROVIDER_UNAVAILABLE",
                "summary": "ai_actions_require_provider",
                "requested_action": "ai-reason",
                "requires_model": True,
                "requires_sidecar": True,
                "error_code": "ERR_AI_PROVIDER_UNAVAILABLE",
                "next_command": "safeclaw.cmd preflight --action ai-reason",
            },
        }
        errors: list[str] = []

        tooling_smoke.assert_default_service_status_json_result(
            payload,
            errors,
            "safeclaw-root-cmd-service-status-json",
            expected_db="target/mvp/session.db",
        )

        self.assertEqual(errors, [])

    def test_assert_default_service_status_json_result_rejects_current_session(
        self,
    ) -> None:
        payload = {
            "db": r"target\mvp\session.db",
            "db_source": "default",
            "limit": 5,
            "current_session": {"task_id": "task-demo"},
            "current_db": False,
            "runtime_profile": {
                "mode": "local_mvp",
                "offline_ready": True,
            },
            "model_provider": {
                "status": "not-configured",
                "degradation_mode": "local_only_ok",
            },
            "sidecar": {"status": "not-configured"},
            "offline_gate": {
                "status": "blocked",
                "reason": "ERR_AI_PROVIDER_UNAVAILABLE",
                "summary": "ai_actions_require_provider",
                "requested_action": "ai-reason",
                "requires_model": True,
                "requires_sidecar": True,
                "error_code": "ERR_AI_PROVIDER_UNAVAILABLE",
                "next_command": "safeclaw.cmd preflight --action ai-reason",
            },
        }
        errors: list[str] = []

        tooling_smoke.assert_default_service_status_json_result(
            payload,
            errors,
            "safeclaw-root-cmd-service-status-json",
            expected_db="target/mvp/session.db",
        )

        self.assertEqual(
            errors,
            ["safeclaw-root-cmd-service-status-json unexpected current_session"],
        )

    def test_collect_errors_uses_root_service_run_helper(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        normalized_source = normalize_source_whitespace(source)
        self.assertIn("append_root_service_run_errors(errors)", normalized_source)

    def test_append_root_service_run_errors_keeps_shell_labels(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        helper_block = source.split(
            "def append_root_service_run_errors(errors: list[str]) -> None:",
            1,
        )[1].split("def ", 1)[0]
        self.assertIn('"safeclaw-root-cmd-service-run-json"', helper_block)
        self.assertIn('"safeclaw-root-ps1-service-run-json"', helper_block)
        self.assertIn("assert_preflight_ai_reason_blocked_json_error(", helper_block)

    def test_collect_errors_uses_root_service_retry_helper(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        normalized_source = normalize_source_whitespace(source)
        self.assertIn("append_root_service_retry_errors(errors)", normalized_source)

    def test_append_root_service_retry_errors_keeps_retry_and_seed_labels(
        self,
    ) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        helper_block = source.split(
            "def append_root_service_retry_errors(errors: list[str]) -> None:",
            1,
        )[1].split("def ", 1)[0]
        self.assertIn('"safeclaw-root-cmd-seed-failed-json"', helper_block)
        self.assertIn('"safeclaw-root-cmd-service-retry-json"', helper_block)
        self.assertIn("assert_workspace_seed_json_result(", helper_block)
        self.assertIn("append_root_ps1_service_retry_errors(errors)", helper_block)

    def test_collect_errors_uses_root_service_recover_helper(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        normalized_source = normalize_source_whitespace(source)
        self.assertIn("append_root_service_recover_errors(errors)", normalized_source)

    def test_append_root_service_recover_errors_keeps_recover_and_seed_labels(
        self,
    ) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        helper_block = source.split(
            "def append_root_service_recover_errors(errors: list[str]) -> None:",
            1,
        )[1].split("def ", 1)[0]
        self.assertIn('"safeclaw-root-cmd-seed-crash-json"', helper_block)
        self.assertIn('"safeclaw-root-cmd-service-recover-json"', helper_block)
        self.assertIn("assert_workspace_seed_json_result(", helper_block)
        self.assertIn("append_root_ps1_service_recover_errors(errors)", helper_block)

    def test_collect_errors_uses_root_service_resume_helper(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        normalized_source = normalize_source_whitespace(source)
        self.assertIn("append_root_service_resume_errors(errors)", normalized_source)

    def test_append_root_service_resume_errors_calls_cmd_and_ps1_helpers(
        self,
    ) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        helper_block = source.split(
            "def append_root_service_resume_errors(errors: list[str]) -> None:",
            1,
        )[1].split("def ", 1)[0]
        self.assertIn("append_root_cmd_service_resume_invalid_errors(errors)", helper_block)
        self.assertIn(
            "append_root_cmd_service_resume_hibernated_errors(errors)", helper_block
        )
        self.assertIn("append_root_ps1_service_resume_errors(errors)", helper_block)

    def test_collect_errors_uses_root_service_reconcile_helper(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        normalized_source = normalize_source_whitespace(source)
        self.assertIn("append_root_service_reconcile_errors(errors)", normalized_source)

    def test_append_root_service_reconcile_errors_keeps_reconcile_labels(
        self,
    ) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        helper_block = source.split(
            "def append_root_service_reconcile_errors(errors: list[str]) -> None:",
            1,
        )[1].split("def ", 1)[0]
        self.assertIn('"safeclaw-root-cmd-service-reconcile-seed-crash-json"', helper_block)
        self.assertIn('"safeclaw-root-cmd-service-reconcile-json"', helper_block)
        self.assertIn("assert_workspace_seed_json_result(", helper_block)
        self.assertIn("append_root_ps1_service_reconcile_errors(errors)", helper_block)
        self.assertNotIn("append_root_ps1_service_recover_errors(errors)", helper_block)

    def test_collect_errors_uses_root_verify_helper(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        normalized_source = normalize_source_whitespace(source)
        self.assertIn("append_root_verify_errors(errors)", normalized_source)

    def test_append_root_verify_errors_keeps_verify_labels(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        helper_block = source.split(
            "def append_root_verify_errors(errors: list[str]) -> None:",
            1,
        )[1].split("def ", 1)[0]
        self.assertIn('"safeclaw-root-ps1-verify-invalid-json"', helper_block)
        self.assertIn('"safeclaw-root-cmd-verify-json"', helper_block)
        self.assertIn("with tempfile.TemporaryDirectory() as verify_mock_dir:", helper_block)
        self.assertIn("write_smoke_verify_sitecustomize(Path(verify_mock_dir))", helper_block)
        self.assertIn(
            'assert_verify_json_result(result, errors, "safeclaw-root-cmd-verify-json")',
            helper_block,
        )
        self.assertNotIn('"safeclaw-root-cmd-workspace-clear-json"', helper_block)

    def test_collect_errors_uses_root_workspace_clear_helper(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        normalized_source = normalize_source_whitespace(source)
        self.assertIn("append_root_workspace_clear_errors(errors)", normalized_source)

    def test_append_root_workspace_clear_errors_keeps_workspace_labels(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        helper_block = source.split(
            "def append_root_workspace_clear_errors(errors: list[str]) -> None:",
            1,
        )[1].split("def ", 1)[0]
        self.assertIn('"safeclaw-root-cmd-workspace-clear-json"', helper_block)
        self.assertIn('"safeclaw-root-ps1-workspace-clear-json"', helper_block)
        self.assertIn('"target\\mvp\\workspace.json"', helper_block)
        self.assertIn('clear_state not in {(True, "removed"), (False, "none")}', helper_block)
        self.assertNotIn('"safeclaw-root-ps1-seed-crash-json"', helper_block)

    def test_collect_errors_uses_root_ps1_seed_crash_failed_helper(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        normalized_source = normalize_source_whitespace(source)
        self.assertIn("append_root_ps1_seed_crash_failed_errors(errors)", normalized_source)

    def test_append_root_ps1_seed_crash_failed_errors_keeps_seed_labels(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        helper_block = source.split(
            "def append_root_ps1_seed_crash_failed_errors(errors: list[str]) -> None:",
            1,
        )[1].split("def ", 1)[0]
        self.assertIn('"safeclaw-root-ps1-seed-crash-json"', helper_block)
        self.assertIn('"safeclaw-root-ps1-seed-failed-json"', helper_block)
        self.assertIn('"target/mvp/root-ps1-seed-crash-json.db"', helper_block)
        self.assertIn('"target/mvp/root-ps1-seed-failed-json.db"', helper_block)
        self.assertNotIn('"safeclaw-root-ps1-seed-hibernated-json"', helper_block)

    def test_collect_errors_uses_root_ps1_seed_hibernated_helper(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        normalized_source = normalize_source_whitespace(source)
        self.assertIn("append_root_ps1_seed_hibernated_errors(errors)", normalized_source)

    def test_append_root_ps1_seed_hibernated_errors_keeps_seed_labels(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        helper_block = source.split(
            "def append_root_ps1_seed_hibernated_errors(errors: list[str]) -> None:",
            1,
        )[1].split("def ", 1)[0]
        self.assertIn('"safeclaw-root-ps1-seed-hibernated-json"', helper_block)
        self.assertIn('"target/mvp/root-ps1-seed-hibernated-json.db"', helper_block)
        self.assertIn("assert_run_json_result(", helper_block)
        self.assertNotIn('"safeclaw-root-ps1-resume-json"', helper_block)

    def test_collect_errors_uses_root_ps1_resume_helper(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        normalized_source = normalize_source_whitespace(source)
        self.assertIn("append_root_ps1_resume_errors(errors)", normalized_source)

    def test_append_root_ps1_resume_errors_keeps_resume_labels(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        helper_block = source.split(
            "def append_root_ps1_resume_errors(errors: list[str]) -> None:",
            1,
        )[1].split("def ", 1)[0]
        self.assertIn("append_root_ps1_resume_seed_errors(errors)", helper_block)
        self.assertIn('"safeclaw-root-ps1-resume-json"', helper_block)
        self.assertIn('"target/mvp/root-ps1-resume-json.db"', helper_block)
        self.assertIn('"safeclaw-root-ps1-resume-json missing source_hints.owner_id=session"', helper_block)
        self.assertNotIn('"safeclaw-root-cmd-resume-json"', helper_block)

    def test_collect_errors_uses_root_cmd_seed_hibernated_helper(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        normalized_source = normalize_source_whitespace(source)
        self.assertIn("append_root_cmd_seed_hibernated_errors(errors)", normalized_source)

    def test_append_root_cmd_seed_hibernated_errors_keeps_seed_labels(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        helper_block = source.split(
            "def append_root_cmd_seed_hibernated_errors(errors: list[str]) -> None:",
            1,
        )[1].split("def ", 1)[0]
        self.assertIn('"safeclaw-root-cmd-seed-hibernated-json"', helper_block)
        self.assertIn('"target/mvp/root-cmd-seed-hibernated-json.db"', helper_block)
        self.assertIn("assert_run_json_result(", helper_block)
        self.assertNotIn('"safeclaw-root-cmd-resume-json"', helper_block)

    def test_collect_errors_uses_root_cmd_resume_helper(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        normalized_source = normalize_source_whitespace(source)
        self.assertIn("append_root_cmd_resume_errors(errors)", normalized_source)

    def test_append_root_cmd_resume_errors_keeps_resume_labels(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        helper_block = source.split(
            "def append_root_cmd_resume_errors(errors: list[str]) -> None:",
            1,
        )[1].split("def ", 1)[0]
        self.assertIn("append_root_cmd_resume_seed_errors(errors)", helper_block)
        self.assertIn('"safeclaw-root-cmd-resume-json"', helper_block)
        self.assertIn('"target/mvp/root-cmd-resume-json.db"', helper_block)
        self.assertIn('"safeclaw-root-cmd-resume-json missing source_hints.owner_id=session"', helper_block)
        self.assertNotIn('"safeclaw-root-cmd-forget-json"', helper_block)

    def test_collect_errors_uses_root_forget_helper(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        normalized_source = normalize_source_whitespace(source)
        self.assertIn("append_root_forget_errors(errors)", normalized_source)

    def test_append_root_forget_errors_keeps_forget_labels(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        helper_block = source.split(
            "def append_root_forget_errors(errors: list[str]) -> None:",
            1,
        )[1].split("def ", 1)[0]
        self.assertIn('"safeclaw-root-cmd-forget-json"', helper_block)
        self.assertIn('"safeclaw-root-ps1-forget-json"', helper_block)
        self.assertIn('"target\\mvp\\last_session.json"', helper_block)
        self.assertIn('forget_state not in {(True, "removed"), (False, "none")}', helper_block)
        self.assertNotIn('"safeclaw-root-cmd-preflight-service-run-json"', helper_block)

    def test_collect_errors_uses_root_cmd_preflight_local_action_helper(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        normalized_source = normalize_source_whitespace(source)
        self.assertIn(
            "append_root_cmd_preflight_local_action_errors(errors)", normalized_source
        )

    def test_append_root_cmd_preflight_local_action_errors_keeps_preflight_labels(
        self,
    ) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        helper_block = source.split(
            "def append_root_cmd_preflight_local_action_errors(errors: list[str]) -> None:",
            1,
        )[1].split("def ", 1)[0]
        self.assertIn('"safeclaw-root-cmd-preflight-service-run-json"', helper_block)
        self.assertIn('"safeclaw-root-cmd-preflight-demo-json"', helper_block)
        self.assertIn('"scope:target/mvp/output.txt"', helper_block)
        self.assertIn('expected_action_reason="current_mvp_action_is_local_only"', helper_block)
        self.assertNotIn('"safeclaw-root-cmd-preflight-ai-reason-json"', helper_block)

    def test_collect_errors_uses_root_cmd_preflight_ai_reason_helper(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        normalized_source = normalize_source_whitespace(source)
        self.assertIn(
            "append_root_cmd_preflight_ai_reason_errors(errors)", normalized_source
        )

    def test_append_root_cmd_preflight_ai_reason_errors_keeps_preflight_labels(
        self,
    ) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        helper_block = source.split(
            "def append_root_cmd_preflight_ai_reason_errors(errors: list[str]) -> None:",
            1,
        )[1].split("def ", 1)[0]
        self.assertIn('"safeclaw-root-cmd-preflight-ai-reason-json"', helper_block)
        self.assertIn('expected_action_class="ai-action"', helper_block)
        self.assertIn('expected_degradation_mode="provider_unavailable"', helper_block)
        self.assertIn('expected_error_code="ERR_AI_PROVIDER_UNAVAILABLE"', helper_block)
        self.assertNotIn('"safeclaw-root-ps1-preflight-ai-reason-json"', helper_block)

    def test_collect_errors_uses_root_ps1_preflight_ai_reason_helper(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        normalized_source = normalize_source_whitespace(source)
        self.assertIn(
            "append_root_ps1_preflight_ai_reason_errors(errors)", normalized_source
        )

    def test_append_root_ps1_preflight_ai_reason_errors_keeps_preflight_labels(
        self,
    ) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        helper_block = source.split(
            "def append_root_ps1_preflight_ai_reason_errors(errors: list[str]) -> None:",
            1,
        )[1].split("def ", 1)[0]
        self.assertIn('"safeclaw-root-ps1-preflight-ai-reason-json"', helper_block)
        self.assertIn('expected_action_class="ai-action"', helper_block)
        self.assertIn('expected_degradation_mode="provider_unavailable"', helper_block)
        self.assertIn('expected_error_code="ERR_AI_PROVIDER_UNAVAILABLE"', helper_block)
        self.assertNotIn('"safeclaw-root-ps1-preflight-service-run-json"', helper_block)

    def test_collect_errors_uses_root_ps1_preflight_local_action_helper(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        normalized_source = normalize_source_whitespace(source)
        self.assertIn(
            "append_root_ps1_preflight_local_action_errors(errors)", normalized_source
        )

    def test_append_root_ps1_preflight_local_action_errors_keeps_preflight_labels(
        self,
    ) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        helper_block = source.split(
            "def append_root_ps1_preflight_local_action_errors(errors: list[str]) -> None:",
            1,
        )[1].split("def ", 1)[0]
        self.assertIn('"safeclaw-root-ps1-preflight-service-run-json"', helper_block)
        self.assertIn('"safeclaw-root-ps1-preflight-demo-json"', helper_block)
        self.assertIn('"safeclaw-root-cmd-demo-preflight-ai-json"', helper_block)
        self.assertIn('"safeclaw-root-ps1-demo-preflight-ai-json"', helper_block)
        self.assertIn('expected_action_reason="current_mvp_action_is_local_only"', helper_block)
        self.assertNotIn('"mvp-wrapper-cmd-doctor-json"', helper_block)

    def test_collect_errors_uses_wrapper_doctor_shell_json_helper(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        normalized_source = normalize_source_whitespace(source)
        self.assertIn("append_wrapper_doctor_shell_json_errors(errors)", normalized_source)

    def test_append_wrapper_doctor_shell_json_errors_keeps_doctor_labels(
        self,
    ) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        helper_block = source.split(
            "def append_wrapper_doctor_shell_json_errors(errors: list[str]) -> None:",
            1,
        )[1].split("def ", 1)[0]
        self.assertIn('"mvp-wrapper-cmd-doctor-json"', helper_block)
        self.assertIn('"mvp-wrapper-ps1-doctor-json"', helper_block)
        self.assertIn("doctor-wrapper-cmd.db", helper_block)
        self.assertIn("doctor-wrapper-ps1.db", helper_block)
        self.assertNotIn('"mvp-wrapper-doctor-json"', helper_block)

    def test_collect_errors_uses_wrapper_doctor_text_helper(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        normalized_source = normalize_source_whitespace(source)
        self.assertIn("append_wrapper_doctor_text_errors(errors)", normalized_source)

    def test_append_wrapper_doctor_text_errors_keeps_doctor_labels(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        helper_block = source.split(
            "def append_wrapper_doctor_text_errors(errors: list[str]) -> None:",
            1,
        )[1].split("def ", 1)[0]
        self.assertIn('"target/mvp/doctor-check.db"', helper_block)
        self.assertIn('"mvp-wrapper-doctor 输出缺少 cargo 检查"', helper_block)
        self.assertIn('"[mvp-wrapper] doctor summary => ready"', helper_block)
        self.assertIn('"[mvp-wrapper] doctor budget =>"', helper_block)
        self.assertNotIn('"mvp-wrapper-doctor-json"', helper_block)

    def test_collect_errors_uses_wrapper_doctor_json_helper(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        normalized_source = normalize_source_whitespace(source)
        self.assertIn("append_wrapper_doctor_json_errors(errors)", normalized_source)

    def test_append_wrapper_doctor_json_errors_keeps_doctor_labels(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        helper_block = source.split(
            "def append_wrapper_doctor_json_errors(errors: list[str]) -> None:",
            1,
        )[1].split("def ", 1)[0]
        self.assertIn('"mvp-wrapper-doctor-json"', helper_block)
        self.assertIn('"target/mvp/doctor-check.db"', helper_block)
        self.assertIn('expected_db_path="target\\\\mvp\\\\doctor-check.db"', helper_block)
        self.assertIn(
            'expected_output_path="target\\\\mvp\\\\doctor-check.txt"', helper_block
        )
        self.assertNotIn('"mvp-wrapper-preflight missing allow summary"', helper_block)

    def test_collect_errors_uses_wrapper_preflight_text_helper(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        normalized_source = normalize_source_whitespace(source)
        self.assertIn("append_wrapper_preflight_text_errors(errors)", normalized_source)

    def test_append_wrapper_preflight_text_errors_keeps_preflight_labels(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        helper_block = source.split(
            "def append_wrapper_preflight_text_errors(errors: list[str]) -> None:",
            1,
        )[1].split("def ", 1)[0]
        self.assertIn('"tools/mvp/safeclaw_mvp.py"', helper_block)
        self.assertIn('"mvp-wrapper-preflight missing allow summary"', helper_block)
        self.assertIn(
            '"[mvp-wrapper] preflight => action=service-run known=true class=local-action',
            helper_block,
        )
        self.assertNotIn('"mvp-wrapper-preflight-json"', helper_block)

    def test_collect_errors_uses_wrapper_preflight_allow_json_helper(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        normalized_source = normalize_source_whitespace(source)
        self.assertIn(
            "append_wrapper_preflight_allow_json_errors(errors)", normalized_source
        )

    def test_append_wrapper_preflight_allow_json_errors_keeps_preflight_labels(
        self,
    ) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        helper_block = source.split(
            "def append_wrapper_preflight_allow_json_errors(errors: list[str]) -> None:",
            1,
        )[1].split("def ", 1)[0]
        self.assertIn('"mvp-wrapper-preflight-json"', helper_block)
        self.assertIn('"mvp-wrapper-cmd-preflight-json"', helper_block)
        self.assertIn('expected_requested_action="service-run"', helper_block)
        self.assertIn('expected_target_scope="scope:target/mvp/output.txt"', helper_block)
        self.assertNotIn('"mvp-wrapper-preflight-unknown missing deny summary"', helper_block)

    def test_collect_errors_uses_wrapper_preflight_unknown_text_helper(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        normalized_source = normalize_source_whitespace(source)
        self.assertIn(
            "append_wrapper_preflight_unknown_text_errors(errors)", normalized_source
        )

    def test_append_wrapper_preflight_unknown_text_errors_keeps_deny_labels(
        self,
    ) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        helper_block = source.split(
            "def append_wrapper_preflight_unknown_text_errors(errors: list[str]) -> None:",
            1,
        )[1].split("def ", 1)[0]
        self.assertIn('"external-send"', helper_block)
        self.assertIn('"mvp-wrapper-preflight-unknown missing deny summary"', helper_block)
        self.assertIn("unknown_action_defaults_to_strict_deny", helper_block)
        self.assertNotIn('"mvp-wrapper-preflight-ai-reason"', helper_block)

    def test_collect_errors_uses_wrapper_preflight_unknown_json_helper(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        normalized_source = normalize_source_whitespace(source)
        self.assertIn(
            "append_wrapper_preflight_unknown_json_errors(errors)", normalized_source
        )

    def test_append_wrapper_preflight_unknown_json_errors_keeps_unknown_labels(
        self,
    ) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        helper_block = source.split(
            "def append_wrapper_preflight_unknown_json_errors(errors: list[str]) -> None:",
            1,
        )[1].split("def ", 1)[0]
        self.assertIn('"mvp-wrapper-preflight-unknown-json"', helper_block)
        self.assertIn('"external-send"', helper_block)
        self.assertIn('expected_known=False', helper_block)
        self.assertIn('expected_action_class="unknown"', helper_block)
        self.assertNotIn('"mvp-wrapper-preflight-ai-reason"', helper_block)

    def test_write_smoke_verify_sitecustomize_creates_stub(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            sitecustomize_path = tooling_smoke.write_smoke_verify_sitecustomize(
                Path(temp_dir)
            )
            source = sitecustomize_path.read_text(encoding="utf-8")
        self.assertTrue(sitecustomize_path.name == "sitecustomize.py")
        self.assertIn("subprocess.CompletedProcess", source)
        self.assertIn("MVP operator flow check passed.", source)

    def test_write_smoke_demo_sitecustomize_creates_combo_stub(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            sitecustomize_path = tooling_smoke.write_smoke_demo_sitecustomize(
                Path(temp_dir)
            )
            source = sitecustomize_path.read_text(encoding="utf-8")
        self.assertTrue(sitecustomize_path.name == "sitecustomize.py")
        self.assertIn("subprocess.run = _patched_run", source)
        self.assertIn("safeclaw_mvp_entry", source)
        self.assertIn("worker_service_governance_demo", source)
        self.assertIn(
            "[demo] service governance resolved => total=2 resolved=2 confirmation=0 manual_review=0",
            source,
        )
        self.assertIn("[mvp] report target => task=", source)
        self.assertIn("if action.startswith('seed-'):", source)
        self.assertIn("task={task_id}", source)
        self.assertIn("db={db_path}", source)
        self.assertIn("output={output_path}", source)

    def test_write_smoke_report_sitecustomize_creates_report_stub(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            sitecustomize_path = tooling_smoke.write_smoke_report_sitecustomize(
                Path(temp_dir)
            )
            source = sitecustomize_path.read_text(encoding="utf-8")
        self.assertTrue(sitecustomize_path.name == "sitecustomize.py")
        self.assertIn("safeclaw_mvp_entry", source)
        self.assertIn("task-wrapper-report-explicit-crash", source)
        self.assertIn("QueueForManualReview", source)
        self.assertIn("RetryEligible", source)
        self.assertIn("subprocess.CompletedProcess", source)

    def test_wrapper_python_combo_success_paths_use_demo_stub_selector(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        normalized_source = normalize_source_whitespace(source)
        self.assertIn("write_smoke_demo_sitecustomize", source)
        self.assertIn(
            "should_use_smoke_demo_sitecustomize( command )",
            normalized_source,
        )
        self.assertIn("build_smoke_demo_pythonpath_env(", source)
        self.assertIn("_SMOKE_DEMO_STUB_TASK_IDS", source)

    def test_should_use_smoke_demo_sitecustomize_matches_combo_success_paths(
        self,
    ) -> None:
        self.assertTrue(
            tooling_smoke.should_use_smoke_demo_sitecustomize(
                [
                    sys.executable,
                    "tools/mvp/safeclaw_mvp.py",
                    "demo",
                    "--task-id",
                    "task-wrapper-demo-json",
                    "--json",
                ]
            )
        )
        self.assertTrue(
            tooling_smoke.should_use_smoke_demo_sitecustomize(
                [
                    sys.executable,
                    "tools/mvp/safeclaw_mvp.py",
                    "recover-demo",
                    "--task-id",
                    "task-wrapper-recover-demo-json",
                    "--json",
                ]
            )
        )
        self.assertTrue(
            tooling_smoke.should_use_smoke_demo_sitecustomize(
                [
                    sys.executable,
                    "tools/mvp/safeclaw_mvp.py",
                    "retry-demo",
                    "--task-id",
                    "task-wrapper-retry-demo-json",
                    "--json",
                ]
            )
        )
        self.assertFalse(
            tooling_smoke.should_use_smoke_demo_sitecustomize(
                [
                    sys.executable,
                    "tools/mvp/safeclaw_mvp.py",
                    "demo",
                    "--task-id",
                    "task-wrapper-demo-json",
                    "--bogus",
                ]
            )
        )
        self.assertFalse(
            tooling_smoke.should_use_smoke_demo_sitecustomize(
                [
                    "cmd",
                    "/c",
                    "tools\\mvp\\safeclaw_mvp.cmd",
                    "demo",
                    "--task-id",
                    "task-wrapper-demo-json",
                    "--json",
                ]
            )
        )
        self.assertTrue(
            tooling_smoke.should_use_smoke_demo_sitecustomize(
                [sys.executable, "tools/mvp/safeclaw_mvp.py", "service-demo", "--json"]
            )
        )
        self.assertFalse(
            tooling_smoke.should_use_smoke_demo_sitecustomize(
                [
                    sys.executable,
                    "tools/mvp/safeclaw_mvp.py",
                    "service-demo",
                    "--bogus",
                    "--json",
                ]
            )
        )

    def test_wrapper_shell_service_success_paths_use_demo_stub_selector(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("should_use_smoke_wrapper_service_sitecustomize(command)", source)
        self.assertIn("_SMOKE_WRAPPER_SERVICE_STUB_ACTIONS", source)
        self.assertIn("_SMOKE_WRAPPER_SERVICE_STUB_TASK_IDS", source)

    def test_wrapper_shell_report_success_paths_use_report_stub_selector(self) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("should_use_smoke_wrapper_report_sitecustomize(command)", source)
        self.assertIn("write_smoke_report_sitecustomize", source)
        self.assertIn("build_smoke_report_pythonpath_env(", source)
        self.assertIn("_SMOKE_WRAPPER_REPORT_STUB_TASK_OUTPUTS", source)

    def test_wrapper_shell_service_report_success_paths_use_report_stub_selector(
        self,
    ) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "should_use_smoke_wrapper_service_report_sitecustomize(command)", source
        )
        self.assertIn("_SMOKE_WRAPPER_SERVICE_REPORT_STUB_TASK_IDS", source)
        self.assertIn("build_smoke_report_pythonpath_env(", source)

    def test_root_ps1_service_report_success_paths_use_report_stub_selector(
        self,
    ) -> None:
        source = (REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "should_use_smoke_root_ps1_service_report_sitecustomize(command)", source
        )
        self.assertIn("_SMOKE_ROOT_PS1_SERVICE_REPORT_STUB_TASK_IDS", source)
        self.assertIn("build_smoke_report_pythonpath_env(", source)

    def test_should_use_smoke_wrapper_service_sitecustomize_matches_shell_success_paths(
        self,
    ) -> None:
        self.assertTrue(
            tooling_smoke.should_use_smoke_wrapper_service_sitecustomize(
                [
                    "cmd",
                    "/c",
                    "tools\\mvp\\safeclaw_mvp.cmd",
                    "service-run",
                    "--task-id",
                    "task-wrapper-service-run-json",
                    "--limit",
                    "1",
                    "--json",
                ]
            )
        )
        self.assertTrue(
            tooling_smoke.should_use_smoke_wrapper_service_sitecustomize(
                [
                    "powershell.exe",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "tools\\mvp\\safeclaw_mvp.ps1",
                    "service-run",
                    "--task-id",
                    "task-wrapper-service-run-report-json",
                    "--limit",
                    "1",
                    "--report",
                    "--json",
                ]
            )
        )
        self.assertTrue(
            tooling_smoke.should_use_smoke_wrapper_service_sitecustomize(
                [
                    "powershell.exe",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "tools\\mvp\\safeclaw_mvp.ps1",
                    "service-run",
                    "--task-id",
                    "task-wrapper-service-run-json",
                    "--limit",
                    "1",
                ]
            )
        )
        self.assertTrue(
            tooling_smoke.should_use_smoke_wrapper_service_sitecustomize(
                [
                    "cmd",
                    "/c",
                    "tools\\mvp\\safeclaw_mvp.cmd",
                    "service-demo",
                    "--json",
                ]
            )
        )
        self.assertFalse(
            tooling_smoke.should_use_smoke_wrapper_service_sitecustomize(
                [
                    sys.executable,
                    "tools/mvp/safeclaw_mvp.py",
                    "service-run",
                    "--task-id",
                    "task-wrapper-service-run-json",
                    "--json",
                ]
            )
        )
        self.assertFalse(
            tooling_smoke.should_use_smoke_wrapper_service_sitecustomize(
                [
                    "cmd",
                    "/c",
                    "tools\\mvp\\safeclaw_mvp.cmd",
                    "service-demo",
                    "--bogus",
                    "--json",
                ]
            )
        )
        self.assertFalse(
            tooling_smoke.should_use_smoke_wrapper_service_sitecustomize(
                [
                    "cmd",
                    "/c",
                    "tools\\mvp\\safeclaw_mvp.cmd",
                    "service-retry",
                    "--task-id",
                    "task-wrapper-service-retry-report-json",
                    "--limit",
                    "1",
                    "--json",
                ]
            )
        )

    def test_should_use_smoke_wrapper_report_sitecustomize_matches_shell_success_paths(
        self,
    ) -> None:
        self.assertTrue(
            tooling_smoke.should_use_smoke_wrapper_report_sitecustomize(
                [
                    "powershell.exe",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "tools\\mvp\\safeclaw_mvp.ps1",
                    "report",
                    "--db",
                    "target/mvp/report-explicit-crash.db",
                    "--task-id",
                    "task-wrapper-report-explicit-crash",
                    "--json",
                ]
            )
        )
        self.assertFalse(
            tooling_smoke.should_use_smoke_wrapper_report_sitecustomize(
                [
                    "cmd",
                    "/c",
                    "tools\\mvp\\safeclaw_mvp.cmd",
                    "report",
                    "--db",
                    "target/mvp/report-explicit-crash.db",
                    "--task-id",
                    "task-wrapper-report-explicit-crash",
                    "--json",
                ]
            )
        )
        self.assertFalse(
            tooling_smoke.should_use_smoke_wrapper_report_sitecustomize(
                [
                    "powershell.exe",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "tools\\mvp\\safeclaw_mvp.ps1",
                    "report",
                    "--task-id",
                    "task-wrapper-report-explicit-crash",
                    "--json",
                ]
            )
        )
        self.assertFalse(
            tooling_smoke.should_use_smoke_wrapper_report_sitecustomize(
                [
                    "powershell.exe",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "tools\\mvp\\safeclaw_mvp.ps1",
                    "report",
                    "--db",
                    "target/mvp/report-explicit-crash.db",
                    "--task-id",
                    "task-wrapper-report-explicit-crash",
                    "--bogus",
                    "--json",
                ]
            )
        )
        self.assertFalse(
            tooling_smoke.should_use_smoke_wrapper_report_sitecustomize(
                [
                    "powershell.exe",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "tools\\mvp\\safeclaw_mvp.ps1",
                    "report",
                    "--db",
                    "target/mvp/report-without-session.db",
                    "--json",
                ]
            )
        )

    def test_should_use_smoke_wrapper_service_report_sitecustomize_matches_shell_success_paths(
        self,
    ) -> None:
        self.assertTrue(
            tooling_smoke.should_use_smoke_wrapper_service_report_sitecustomize(
                [
                    "powershell.exe",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "tools\\mvp\\safeclaw_mvp.ps1",
                    "service-retry",
                    "--db",
                    "target/mvp/service-retry-report-json.db",
                    "--task-id",
                    "task-wrapper-service-retry-report-json",
                    "--limit",
                    "1",
                    "--report",
                    "--json",
                ]
            )
        )
        self.assertTrue(
            tooling_smoke.should_use_smoke_wrapper_service_report_sitecustomize(
                [
                    "powershell.exe",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "tools\\mvp\\safeclaw_mvp.ps1",
                    "service-recover",
                    "--db",
                    "target/mvp/service-recover-report-json.db",
                    "--task-id",
                    "task-wrapper-service-recover-report-json",
                    "--limit",
                    "1",
                    "--report",
                    "--json",
                ]
            )
        )
        self.assertTrue(
            tooling_smoke.should_use_smoke_wrapper_service_report_sitecustomize(
                [
                    "powershell.exe",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "tools\\mvp\\safeclaw_mvp.ps1",
                    "service-resume",
                    "--db",
                    "target/mvp/service-resume-report-json.db",
                    "--task-id",
                    "task-wrapper-service-resume-report-json",
                    "--limit",
                    "1",
                    "--report",
                    "--json",
                ]
            )
        )
        self.assertTrue(
            tooling_smoke.should_use_smoke_wrapper_service_report_sitecustomize(
                [
                    "powershell.exe",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "tools\\mvp\\safeclaw_mvp.ps1",
                    "service-reconcile",
                    "--db",
                    "target/mvp/service-reconcile-report-json.db",
                    "--task-id",
                    "task-wrapper-service-reconcile-report-json",
                    "--decision",
                    "executed",
                    "--limit",
                    "1",
                    "--report",
                    "--json",
                ]
            )
        )
        self.assertFalse(
            tooling_smoke.should_use_smoke_wrapper_service_report_sitecustomize(
                [
                    "cmd",
                    "/c",
                    "tools\\mvp\\safeclaw_mvp.cmd",
                    "service-retry",
                    "--db",
                    "target/mvp/service-retry-report-json.db",
                    "--task-id",
                    "task-wrapper-service-retry-report-json",
                    "--limit",
                    "1",
                    "--report",
                    "--json",
                ]
            )
        )
        self.assertFalse(
            tooling_smoke.should_use_smoke_wrapper_service_report_sitecustomize(
                [
                    "powershell.exe",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "tools\\mvp\\safeclaw_mvp.ps1",
                    "service-retry",
                    "--db",
                    "target/mvp/service-retry-report-json.db",
                    "--task-id",
                    "task-wrapper-service-retry-report-json",
                    "--limit",
                    "1",
                    "--json",
                ]
            )
        )
        self.assertFalse(
            tooling_smoke.should_use_smoke_wrapper_service_report_sitecustomize(
                [
                    "powershell.exe",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "tools\\mvp\\safeclaw_mvp.ps1",
                    "service-retry",
                    "--db",
                    "target/mvp/service-retry-report-json.db",
                    "--task-id",
                    "task-wrapper-service-retry-report-json",
                    "--limit",
                    "1",
                    "--bogus",
                    "--report",
                    "--json",
                ]
            )
        )

    def test_should_use_smoke_root_ps1_service_report_sitecustomize_matches_shell_success_paths(
        self,
    ) -> None:
        self.assertTrue(
            tooling_smoke.should_use_smoke_root_ps1_service_report_sitecustomize(
                [
                    "powershell.exe",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "safeclaw.ps1",
                    "service-run",
                    "--reset",
                    "--task-id",
                    "task-readme-root",
                    "--limit",
                    "1",
                    "--report",
                    "--json",
                ]
            )
        )
        self.assertTrue(
            tooling_smoke.should_use_smoke_root_ps1_service_report_sitecustomize(
                [
                    "powershell.exe",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "safeclaw.ps1",
                    "service-retry",
                    "--task-id",
                    "task-readme-root-failed-ps1",
                    "--limit",
                    "1",
                    "--report",
                    "--json",
                ]
            )
        )
        self.assertTrue(
            tooling_smoke.should_use_smoke_root_ps1_service_report_sitecustomize(
                [
                    "powershell.exe",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "safeclaw.ps1",
                    "service-recover",
                    "--task-id",
                    "task-readme-root-uncertain-ps1",
                    "--limit",
                    "1",
                    "--report",
                    "--json",
                ]
            )
        )
        self.assertTrue(
            tooling_smoke.should_use_smoke_root_ps1_service_report_sitecustomize(
                [
                    "powershell.exe",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "safeclaw.ps1",
                    "service-resume",
                    "--task-id",
                    "task-readme-root-hibernated-ps1",
                    "--limit",
                    "1",
                    "--report",
                    "--json",
                ]
            )
        )
        self.assertTrue(
            tooling_smoke.should_use_smoke_root_ps1_service_report_sitecustomize(
                [
                    "powershell.exe",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "safeclaw.ps1",
                    "service-reconcile",
                    "--task-id",
                    "task-readme-root-assumed-ps1",
                    "--decision",
                    "executed",
                    "--limit",
                    "1",
                    "--report",
                    "--json",
                ]
            )
        )
        self.assertFalse(
            tooling_smoke.should_use_smoke_root_ps1_service_report_sitecustomize(
                [
                    "cmd",
                    "/c",
                    "safeclaw.cmd",
                    "service-retry",
                    "--task-id",
                    "task-readme-root-failed-ps1",
                    "--limit",
                    "1",
                    "--report",
                    "--json",
                ]
            )
        )
        self.assertFalse(
            tooling_smoke.should_use_smoke_root_ps1_service_report_sitecustomize(
                [
                    "powershell.exe",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "safeclaw.ps1",
                    "service-retry",
                    "--task-id",
                    "task-readme-root-failed-ps1",
                    "--limit",
                    "1",
                    "--json",
                ]
            )
        )
        self.assertFalse(
            tooling_smoke.should_use_smoke_root_ps1_service_report_sitecustomize(
                [
                    "powershell.exe",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "safeclaw.ps1",
                    "service-retry",
                    "--task-id",
                    "task-readme-root-failed-ps1",
                    "--limit",
                    "1",
                    "--report",
                    "--preflight",
                    "--preflight-action",
                    "ai-reason",
                    "--json",
                ]
            )
        )
        self.assertFalse(
            tooling_smoke.should_use_smoke_root_ps1_service_report_sitecustomize(
                [
                    "powershell.exe",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "safeclaw.ps1",
                    "service-retry",
                    "--task-id",
                    "task-readme-root-failed-ps1",
                    "--limit",
                    "1",
                    "--bogus",
                    "--report",
                    "--json",
                ]
            )
        )

    def test_run_verify_plain_still_prints_success_marker(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["python", "tools/checks/check_mvp_operator_flow.py"],
            returncode=0,
            stdout="MVP operator flow check passed.\n",
            stderr="",
        )
        stdout = io.StringIO()
        with mock.patch(
            "tools.mvp.safeclaw_mvp.subprocess.run", return_value=completed
        ), redirect_stdout(stdout):
            exit_code = safeclaw_mvp.run_verify([])
        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertIn("MVP operator flow check passed.", output)
        self.assertIn("[mvp-wrapper] verify => passed", output)

    def test_run_verify_json_emits_operator_flow_payload(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["python", "tools/checks/check_mvp_operator_flow.py"],
            returncode=0,
            stdout="MVP operator flow check passed.\n",
            stderr="",
        )
        stdout = io.StringIO()
        with mock.patch(
            "tools.mvp.safeclaw_mvp.subprocess.run", return_value=completed
        ), redirect_stdout(stdout):
            exit_code = safeclaw_mvp.run_verify(["--json"])
        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["action"], "verify")
        self.assertEqual(payload["schema_version"], "mvp-wrapper.v1")
        result = payload["result"]
        self.assertEqual(result["script"], "tools/checks/check_mvp_operator_flow.py")
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("MVP operator flow check passed.", result["captured_output"])

    def test_resolve_safeclaw_mvp_runtime_command_prefers_prebuilt_example(
        self,
    ) -> None:
        command = [
            "cargo",
            f"+{safeclaw_mvp.TOOLCHAIN}",
            "run",
            "-p",
            "safeclaw-sqlite",
            "--example",
            "safeclaw_mvp_entry",
            "--quiet",
            "--",
            "doctor",
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            example_path = (
                repo_root / "target" / "debug" / "examples" / "safeclaw_mvp_entry.exe"
            )
            example_path.parent.mkdir(parents=True, exist_ok=True)
            example_path.write_bytes(b"fake exe")
            runtime_command = safeclaw_mvp.resolve_safeclaw_mvp_runtime_command(
                command, repo_root=repo_root
            )
        self.assertEqual(runtime_command[0], str(example_path))
        self.assertEqual(runtime_command[1:], ["doctor"])

    def test_resolve_safeclaw_mvp_runtime_command_keeps_other_examples_on_cargo(
        self,
    ) -> None:
        command = [
            "cargo",
            f"+{safeclaw_mvp.TOOLCHAIN}",
            "run",
            "-p",
            "safeclaw-sqlite",
            "--example",
            "worker_service_governance_demo",
            "--quiet",
            "--",
            "service-demo",
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            example_path = (
                repo_root / "target" / "debug" / "examples" / "safeclaw_mvp_entry.exe"
            )
            example_path.parent.mkdir(parents=True, exist_ok=True)
            example_path.write_bytes(b"fake exe")
            runtime_command = safeclaw_mvp.resolve_safeclaw_mvp_runtime_command(
                command, repo_root=repo_root
            )
        self.assertEqual(runtime_command, command)

    def test_run_sqlite_example_capture_uses_prebuilt_example_when_available(
        self,
    ) -> None:
        completed = subprocess.CompletedProcess(
            args=[
                r"V:\260317SafeClaw\target\debug\examples\safeclaw_mvp_entry.exe",
                "doctor",
            ],
            returncode=0,
            stdout="doctor ok\n",
            stderr="",
        )
        with mock.patch(
            "tools.mvp.safeclaw_mvp.resolve_safeclaw_mvp_runtime_command",
            return_value=[
                r"V:\260317SafeClaw\target\debug\examples\safeclaw_mvp_entry.exe",
                "doctor",
            ],
        ), mock.patch(
            "tools.mvp.safeclaw_mvp.build_rust_env",
            return_value=({}, None, None),
        ), mock.patch(
            "tools.mvp.safeclaw_mvp.subprocess.run",
            return_value=completed,
        ) as run_mock:
            exit_code, output = safeclaw_mvp.run_sqlite_example_capture(
                "safeclaw_mvp_entry",
                example_args=["doctor"],
                action="doctor",
            )
        self.assertEqual(exit_code, 0)
        self.assertEqual(output, "doctor ok\n")
        run_mock.assert_called_once_with(
            [
                r"V:\260317SafeClaw\target\debug\examples\safeclaw_mvp_entry.exe",
                "doctor",
            ],
            cwd=safeclaw_mvp.REPO_ROOT,
            env={},
            capture_output=True,
            text=True,
        )

    def test_run_sqlite_example_capture_keeps_other_examples_on_cargo(self) -> None:
        completed = subprocess.CompletedProcess(
            args=[r"C:\Rust\cargo.exe", "run"],
            returncode=0,
            stdout="service demo ok\n",
            stderr="",
        )
        with mock.patch(
            "tools.mvp.safeclaw_mvp.build_rust_env",
            return_value=({}, r"C:\Rust\cargo.exe", None),
        ), mock.patch(
            "tools.mvp.safeclaw_mvp.subprocess.run",
            return_value=completed,
        ) as run_mock:
            exit_code, output = safeclaw_mvp.run_sqlite_example_capture(
                "worker_service_governance_demo",
                example_args=["service-demo"],
                action="service-demo",
            )
        self.assertEqual(exit_code, 0)
        self.assertEqual(output, "service demo ok\n")
        run_mock.assert_called_once_with(
            [
                r"C:\Rust\cargo.exe",
                f"+{safeclaw_mvp.TOOLCHAIN}",
                "run",
                "-p",
                "safeclaw-sqlite",
                "--example",
                "worker_service_governance_demo",
                "--quiet",
                "--",
                "service-demo",
            ],
            cwd=safeclaw_mvp.REPO_ROOT,
            env={},
            capture_output=True,
            text=True,
        )

    def test_reset_smoke_progress_resets_counter_and_refreshes_start_time(self) -> None:
        with mock.patch(
            "tools.checks.check_tooling_smoke.time.monotonic", return_value=12.5
        ):
            tooling_smoke._SMOKE_RUN_COUNTER = 9
            tooling_smoke.reset_smoke_progress()
        self.assertEqual(tooling_smoke._SMOKE_RUN_COUNTER, 0)
        self.assertEqual(tooling_smoke._SMOKE_STARTED_AT, 12.5)

    def test_run_smoke_subprocess_emits_start_and_done_markers(self) -> None:
        process = mock.Mock()
        process.communicate.return_value = ("ok", "")
        process.returncode = 0
        stdout = io.StringIO()
        with mock.patch.object(
            tooling_smoke, "_SMOKE_RUN_COUNTER", 0
        ), mock.patch.object(
            tooling_smoke,
            "_SMOKE_STARTED_AT",
            5.0,
        ), mock.patch.object(
            tooling_smoke,
            "_SMOKE_PARENT_PID",
            4321,
        ), mock.patch(
            "tools.checks.check_tooling_smoke.time.monotonic",
            side_effect=[10.0, 11.5],
        ), mock.patch.object(
            tooling_smoke,
            "_smoke_parent_is_running",
            return_value=True,
        ), mock.patch.object(
            tooling_smoke._ORIGINAL_SUBPROCESS_MODULE,
            "Popen",
            return_value=process,
        ) as popen_mock, redirect_stdout(
            stdout
        ):
            result = tooling_smoke.run_smoke_subprocess(
                ["python", "--version"],
                cwd=tooling_smoke.REPO_ROOT,
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.args, ["python", "--version"])
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "ok")
        self.assertEqual(result.stderr, "")
        popen_mock.assert_called_once_with(
            ["python", "--version"],
            cwd=tooling_smoke.REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        output = stdout.getvalue()
        self.assertIn("[tooling-smoke 001] start +5.0s => python --version", output)
        self.assertIn("[tooling-smoke 001] done exit=0 duration=1.5s", output)

    def test_tracing_subprocess_proxy_keeps_completed_process_type(self) -> None:
        self.assertIs(
            tooling_smoke.subprocess.CompletedProcess, subprocess.CompletedProcess
        )

    def test_run_smoke_subprocess_terminates_child_when_parent_exits(self) -> None:
        process = mock.Mock()
        process.communicate.side_effect = subprocess.TimeoutExpired(["python"], 0.5)
        process.poll.return_value = None
        stdout = io.StringIO()
        with mock.patch.object(
            tooling_smoke, "_SMOKE_RUN_COUNTER", 0
        ), mock.patch.object(
            tooling_smoke,
            "_SMOKE_STARTED_AT",
            0.0,
        ), mock.patch.object(
            tooling_smoke,
            "_SMOKE_PARENT_PID",
            9999,
        ), mock.patch(
            "tools.checks.check_tooling_smoke.time.monotonic",
            side_effect=[1.0, 1.2, 1.3],
        ), mock.patch.object(
            tooling_smoke,
            "_smoke_parent_is_running",
            return_value=False,
        ), mock.patch.object(
            tooling_smoke._ORIGINAL_SUBPROCESS_MODULE,
            "Popen",
            return_value=process,
        ), redirect_stdout(
            stdout
        ):
            with self.assertRaisesRegex(RuntimeError, "tooling smoke parent exited"):
                tooling_smoke.run_smoke_subprocess(
                    ["python", "--version"],
                    cwd=tooling_smoke.REPO_ROOT,
                    capture_output=True,
                    text=True,
                )
        process.terminate.assert_called_once()
        process.wait.assert_called_once_with(timeout=1.0)

    def test_run_smoke_subprocess_terminates_child_on_interrupt(self) -> None:
        process = mock.Mock()
        process.communicate.side_effect = KeyboardInterrupt()
        process.poll.return_value = None
        stdout = io.StringIO()
        with mock.patch.object(
            tooling_smoke._ORIGINAL_SUBPROCESS_MODULE,
            "Popen",
            return_value=process,
        ), mock.patch.object(
            tooling_smoke,
            "_SMOKE_RUN_COUNTER",
            0,
        ), redirect_stdout(
            stdout
        ):
            with self.assertRaises(KeyboardInterrupt):
                tooling_smoke.run_smoke_subprocess(
                    ["python", "--version"],
                    cwd=tooling_smoke.REPO_ROOT,
                    capture_output=True,
                    text=True,
                )
        process.terminate.assert_called_once()
        process.wait.assert_called_once_with(timeout=1.0)


if __name__ == "__main__":
    unittest.main()
