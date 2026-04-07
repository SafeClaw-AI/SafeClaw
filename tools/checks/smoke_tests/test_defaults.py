"""Default workspace and runtime smoke tests."""

from .command_assertions import assert_command_json_result, assert_workspace_json_result, assert_doctor_json_result
from .service_assertions import assert_default_service_status_json_result


def append_root_default_workspace_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", "safeclaw.ps1", "workspace", "--json"],
        errors,
        "safeclaw-root-ps1-workspace-state-json",
        "workspace",
    )
    assert_workspace_json_result(
        result,
        errors,
        "safeclaw-root-ps1-workspace-state-json",
        expected_active=False,
        expected_name=None,
        expected_db_path="target/mvp/session.db",
        expected_output_path="target/mvp/output.txt",
    )
    result = assert_command_json_result(
        ["cmd", "/c", "safeclaw.cmd", "workspace", "--json"],
        errors,
        "safeclaw-root-cmd-workspace-state-json",
        "workspace",
    )
    assert_workspace_json_result(
        result,
        errors,
        "safeclaw-root-cmd-workspace-state-json",
        expected_active=False,
        expected_name=None,
        expected_db_path="target/mvp/session.db",
        expected_output_path="target/mvp/output.txt",
    )


def append_root_default_runtime_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        ["cmd", "/c", "safeclaw.cmd", "doctor", "--json"],
        errors,
        "safeclaw-root-cmd-doctor-default-json",
        "doctor",
    )
    assert_doctor_json_result(
        result,
        errors,
        "safeclaw-root-cmd-doctor-default-json",
        expected_db_path=r"target\mvp\session.db",
        expected_output_path=r"target\mvp\output.txt",
        expected_db_source="default",
        expected_output_source="default",
        expected_workspace_active=False,
    )
    result = assert_command_json_result(
        ["cmd", "/c", "safeclaw.cmd", "service-status", "--limit", "5", "--json"],
        errors,
        "safeclaw-root-cmd-service-status-json",
        "service-status",
    )
    assert_default_service_status_json_result(
        result,
        errors,
        "safeclaw-root-cmd-service-status-json",
        expected_db="target/mvp/session.db",
    )
    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "safeclaw.ps1",
            "service-status",
            "--limit",
            "5",
            "--json",
        ],
        errors,
        "safeclaw-root-ps1-service-status-json",
        "service-status",
    )
    assert_default_service_status_json_result(
        result,
        errors,
        "safeclaw-root-ps1-service-status-json",
        expected_db="target/mvp/session.db",
    )


def append_root_default_entry_errors(errors: list[str]) -> None:
    append_root_default_workspace_errors(errors)
    append_root_default_runtime_errors(errors)


def append_root_workspace_entry_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", "safeclaw.ps1", "workspace", "--name", "readme-root-ps1", "--json"],
        errors,
        "safeclaw-root-ps1-workspace-json",
        "workspace",
    )
    assert_workspace_json_result(
        result,
        errors,
        "safeclaw-root-ps1-workspace-json",
        expected_active=True,
        expected_name="readme-root-ps1",
        expected_db_path="target/mvp/workspaces/readme-root-ps1/session.db",
        expected_output_path="target/mvp/workspaces/readme-root-ps1/output.txt",
        expected_changed=True,
    )
    result = assert_command_json_result(
        ["cmd", "/c", "safeclaw.cmd", "workspace", "--name", "readme-root", "--json"],
        errors,
        "safeclaw-root-cmd-workspace-json",
        "workspace",
    )
    assert_workspace_json_result(
        result,
        errors,
        "safeclaw-root-cmd-workspace-json",
        expected_active=True,
        expected_name="readme-root",
        expected_db_path="target/mvp/workspaces/readme-root/session.db",
        expected_output_path="target/mvp/workspaces/readme-root/output.txt",
        expected_changed=True,
    )
    result = assert_command_json_result(
        ["cmd", "/c", "safeclaw.cmd", "doctor", "--json"],
        errors,
        "safeclaw-root-cmd-doctor-json",
        "doctor",
    )
    assert_doctor_json_result(
        result,
        errors,
        "safeclaw-root-cmd-doctor-json",
        expected_db_path=r"target\mvp\workspaces\readme-root\session.db",
        expected_output_path=r"target\mvp\workspaces\readme-root\output.txt",
        expected_db_source="workspace",
        expected_output_source="workspace",
        expected_workspace_active=True,
        expected_workspace_name="readme-root",
    )
