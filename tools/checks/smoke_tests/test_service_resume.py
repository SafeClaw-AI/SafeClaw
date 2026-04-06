"""Service resume tests for CMD/PowerShell entry points."""

from .command_assertions import (
    assert_command_json_result,
    assert_command_json_error,
    assert_workspace_seed_json_result,
    assert_preflight_ai_reason_blocked_json_error,
)
from .service_assertions import (
    assert_service_run_json_result,
    assert_service_resume_json_result,
)
from .test_service_ps1 import append_root_ps1_service_resume_errors


PYTHON = "python"


def append_root_cmd_service_resume_invalid_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "seed-failed", "--reset", "--task-id", "task-readme-root-failed-resume-cmd", "--json"],
        errors,
        "safeclaw-root-cmd-service-resume-not-hibernated-seed-failed-json",
        "seed-failed",
    )
    assert_workspace_seed_json_result(
        result,
        errors,
        "safeclaw-root-cmd-service-resume-not-hibernated-seed-failed-json",
        expected_action="seed-failed",
        expected_task_id="task-readme-root-failed-resume-cmd",
    )
    assert_command_json_error(
        ["cmd", "/c", "safeclaw.cmd", "service-resume", "--task-id", "task-readme-root-failed-resume-cmd", "--limit", "1", "--json"],
        errors,
        "safeclaw-root-cmd-service-resume-not-hibernated-json",
        "service-resume",
        expected_exit=1,
        expected_error_message_substring="failed step=resume",
        expected_top_level_error_code="resume-target-not-hibernated",
        expected_top_level_error_reason="resume_target_not_hibernated",
        expected_failed_step="resume",
        expected_code="resume-target-not-hibernated",
        expected_details_message_substring="resume only works for hibernated tasks",
    )
    result = assert_command_json_result(
        ["cmd", "/c", "safeclaw.cmd", "service-run", "--reset", "--task-id", "task-readme-root-missing-resume-cmd", "--limit", "1", "--report", "--json"],
        errors,
        "safeclaw-root-cmd-service-resume-missing-service-run-json",
        "service-run",
    )
    assert_service_run_json_result(
        result,
        errors,
        "safeclaw-root-cmd-service-resume-missing-service-run-json",
        expected_db="target/mvp/workspaces/readme-root/session.db",
        expected_db_source="session",
        expected_task_id="task-readme-root-missing-resume-cmd",
        expected_limit=1,
        expected_steps=["run", "service-status", "report"],
        expect_report_payload=True,
        expected_run_db_source="workspace",
    )
    assert_command_json_error(
        ["cmd", "/c", "safeclaw.cmd", "service-resume", "--task-id", "task-readme-root-missing-resume-cmd", "--limit", "1", "--json"],
        errors,
        "safeclaw-root-cmd-service-resume-missing-json",
        "service-resume",
        expected_exit=1,
        expected_error_message_substring="failed step=resume",
        expected_top_level_error_code="resume-target-missing",
        expected_top_level_error_reason="hibernated_runtime_missing",
        expected_failed_step="resume",
        expected_code="resume-target-missing",
        expected_details_message_substring="resume requires a hibernated runtime for the selected task",
    )
def append_root_cmd_service_resume_hibernated_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "seed-hibernated", "--reset", "--task-id", "task-readme-root-hibernated-cmd", "--json"],
        errors,
        "safeclaw-root-cmd-service-resume-seed-hibernated-json",
        "seed-hibernated",
    )
    assert_workspace_seed_json_result(
        result,
        errors,
        "safeclaw-root-cmd-service-resume-seed-hibernated-json",
        expected_action="seed-hibernated",
        expected_task_id="task-readme-root-hibernated-cmd",
    )
    assert_preflight_ai_reason_blocked_json_error(
        ["cmd", "/c", "safeclaw.cmd", "service-resume", "--task-id", "task-readme-root-hibernated-cmd", "--limit", "1", "--report", "--preflight", "--preflight-action", "ai-reason", "--json"],
        errors,
        "safeclaw-root-cmd-service-resume-preflight-ai-json",
        "service-resume",
    )
    result = assert_command_json_result(
        ["cmd", "/c", "safeclaw.cmd", "service-resume", "--task-id", "task-readme-root-hibernated-cmd", "--limit", "1", "--report", "--json"],
        errors,
        "safeclaw-root-cmd-service-resume-json",
        "service-resume",
    )
    assert_service_resume_json_result(
        result,
        errors,
        "safeclaw-root-cmd-service-resume-json",
        expected_db="target/mvp/workspaces/readme-root/session.db",
        expected_db_source="session",
        expected_task_id="task-readme-root-hibernated-cmd",
        expected_limit=1,
        expected_steps=["resume", "service-status", "report"],
        expect_report_payload=True,
    )


def append_root_service_resume_errors(errors: list[str]) -> None:
    append_root_cmd_service_resume_invalid_errors(errors)
    append_root_cmd_service_resume_hibernated_errors(errors)
    append_root_ps1_service_resume_errors(errors)
