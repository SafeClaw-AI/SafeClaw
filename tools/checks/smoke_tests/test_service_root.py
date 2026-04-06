"""Service command smoke tests for CMD/PowerShell entry points."""

from .command_assertions import (
    assert_command_json_result,
    assert_preflight_ai_reason_blocked_json_error,
    assert_workspace_seed_json_result,
)
from .service_assertions import (
    assert_service_run_json_result,
    assert_service_retry_json_result,
    assert_service_recover_json_result,
)
from .subprocess_runner import run_wrapper_command, load_json_payload
from .json_assertions import extract_json_result
from .test_service_ps1 import (
    append_root_ps1_service_retry_errors,
    append_root_ps1_service_recover_errors,
)


def append_root_service_run_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        ["cmd", "/c", "safeclaw.cmd", "service-run", "--reset", "--task-id", "task-readme-root", "--limit", "1", "--report", "--json"],
        errors,
        "safeclaw-root-cmd-service-run-json",
        "service-run",
    )
    assert_service_run_json_result(
        result,
        errors,
        "safeclaw-root-cmd-service-run-json",
        expected_db="target/mvp/workspaces/readme-root/session.db",
        expected_db_source="session",
        expected_task_id="task-readme-root",
        expected_limit=1,
        expected_steps=["run", "service-status", "report"],
        expect_report_payload=True,
        expected_run_db_source="workspace",
    )
    assert_preflight_ai_reason_blocked_json_error(
        ["cmd", "/c", "safeclaw.cmd", "service-run", "--reset", "--task-id", "task-readme-root-service-run-preflight-ai-cmd", "--limit", "1", "--report", "--preflight", "--preflight-action", "ai-reason", "--json"],
        errors,
        "safeclaw-root-cmd-service-run-preflight-ai-json",
        "service-run",
    )
    assert_preflight_ai_reason_blocked_json_error(
        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", "safeclaw.ps1", "service-run", "--reset", "--task-id", "task-readme-root-service-run-preflight-ai-ps1", "--limit", "1", "--report", "--preflight", "--preflight-action", "ai-reason", "--json"],
        errors,
        "safeclaw-root-ps1-service-run-preflight-ai-json",
        "service-run",
    )
    result = assert_command_json_result(
        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", "safeclaw.ps1", "service-run", "--reset", "--task-id", "task-readme-root", "--limit", "1", "--report", "--json"],
        errors,
        "safeclaw-root-ps1-service-run-json",
        "service-run",
    )
    assert_service_run_json_result(
        result,
        errors,
        "safeclaw-root-ps1-service-run-json",
        expected_db="target/mvp/workspaces/readme-root/session.db",
        expected_db_source="session",
        expected_task_id="task-readme-root",
        expected_limit=1,
        expected_steps=["run", "service-status", "report"],
        expect_report_payload=True,
        expected_run_db_source="workspace",
    )
def append_root_service_retry_errors(errors: list[str]) -> None:
    payload = load_json_payload(
        run_wrapper_command(
            ["cmd", "/c", "safeclaw.cmd", "seed-failed", "--reset", "--task-id", "task-readme-root-failed", "--json"]
        ),
        errors,
        "safeclaw-root-cmd-seed-failed-json",
        0,
    )
    result = None if payload is None else extract_json_result(
        payload,
        errors,
        "safeclaw-root-cmd-seed-failed-json",
        "seed-failed",
    )
    assert_workspace_seed_json_result(
        result,
        errors,
        "safeclaw-root-cmd-seed-failed-json",
        expected_action="seed-failed",
        expected_task_id="task-readme-root-failed",
    )
    assert_preflight_ai_reason_blocked_json_error(
        ["cmd", "/c", "safeclaw.cmd", "service-retry", "--task-id", "task-readme-root-failed", "--limit", "1", "--report", "--preflight", "--preflight-action", "ai-reason", "--json"],
        errors,
        "safeclaw-root-cmd-service-retry-preflight-ai-json",
        "service-retry",
    )
    result = assert_command_json_result(
        ["cmd", "/c", "safeclaw.cmd", "service-retry", "--task-id", "task-readme-root-failed", "--limit", "1", "--report", "--json"],
        errors,
        "safeclaw-root-cmd-service-retry-json",
        "service-retry",
    )
    assert_service_retry_json_result(
        result,
        errors,
        "safeclaw-root-cmd-service-retry-json",
        expected_db="target/mvp/workspaces/readme-root/session.db",
        expected_db_source="session",
        expected_task_id="task-readme-root-failed",
        expected_limit=1,
        expected_steps=["retry", "service-status", "report"],
        expect_report_payload=True,
    )
    append_root_ps1_service_retry_errors(errors)

def append_root_service_recover_errors(errors: list[str]) -> None:
    payload = load_json_payload(
        run_wrapper_command(
            ["cmd", "/c", "safeclaw.cmd", "seed-crash", "--reset", "--task-id", "task-readme-root-uncertain", "--json"]
        ),
        errors,
        "safeclaw-root-cmd-seed-crash-json",
        0,
    )
    result = None if payload is None else extract_json_result(
        payload,
        errors,
        "safeclaw-root-cmd-seed-crash-json",
        "seed-crash",
    )
    assert_workspace_seed_json_result(
        result,
        errors,
        "safeclaw-root-cmd-seed-crash-json",
        expected_action="seed-crash",
        expected_task_id="task-readme-root-uncertain",
    )
    assert_preflight_ai_reason_blocked_json_error(
        ["cmd", "/c", "safeclaw.cmd", "service-recover", "--task-id", "task-readme-root-uncertain", "--limit", "1", "--report", "--preflight", "--preflight-action", "ai-reason", "--json"],
        errors,
        "safeclaw-root-cmd-service-recover-preflight-ai-json",
        "service-recover",
    )
    result = assert_command_json_result(
        ["cmd", "/c", "safeclaw.cmd", "service-recover", "--task-id", "task-readme-root-uncertain", "--limit", "1", "--report", "--json"],
        errors,
        "safeclaw-root-cmd-service-recover-json",
        "service-recover",
    )
    assert_service_recover_json_result(
        result,
        errors,
        "safeclaw-root-cmd-service-recover-json",
        expected_db="target/mvp/workspaces/readme-root/session.db",
        expected_db_source="session",
        expected_task_id="task-readme-root-uncertain",
        expected_limit=1,
        expected_steps=["recover", "service-status", "report"],
        expect_report_payload=True,
    )
    append_root_ps1_service_recover_errors(errors)

