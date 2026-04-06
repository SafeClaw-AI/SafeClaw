"""Workspace management smoke tests for CMD/PowerShell entry points."""

from .command_assertions import assert_command_json_result


def append_root_workspace_clear_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        ["cmd", "/c", "safeclaw.cmd", "workspace", "--clear", "--json"],
        errors,
        "safeclaw-root-cmd-workspace-clear-json",
        "workspace",
    )
    if result is not None:
        clear_state = (result.get("cleared"), result.get("reason"))
        if result.get("path") != "target\mvp\workspace.json":
            errors.append("safeclaw-root-cmd-workspace-clear-json missing workspace path")
        elif clear_state not in {(True, "removed"), (False, "none")}:
            errors.append(
                "safeclaw-root-cmd-workspace-clear-json unexpected clear state"
            )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "safeclaw.ps1",
            "workspace",
            "--clear",
            "--json",
        ],
        errors,
        "safeclaw-root-ps1-workspace-clear-json",
        "workspace",
    )
    if result is not None:
        clear_state = (result.get("cleared"), result.get("reason"))
        if result.get("path") != "target\mvp\workspace.json":
            errors.append("safeclaw-root-ps1-workspace-clear-json missing workspace path")
        elif clear_state != (False, "none"):
            errors.append(
                "safeclaw-root-ps1-workspace-clear-json unexpected clear state"
            )
