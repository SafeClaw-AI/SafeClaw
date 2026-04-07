"""Setup and help command smoke tests."""

import subprocess
from pathlib import Path

# Import from sibling modules
from .command_assertions import assert_command_json_result
from .output_assertions import (
    append_expected_substring_errors,
    append_help_usage_error,
    load_help_output,
)


REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
PYTHON = "python"

# These will be imported from check_tooling_smoke.py
CHECKS = []
_SMOKE_WRAPPER_HELP_EXPECTATIONS = []
_SMOKE_WRAPPER_HELP_GROUPED_EXPECTATIONS = []


def append_smoke_setup_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "workspace", "--clear", "--json"],
        errors,
        "mvp-wrapper-workspace-clear-before-json",
        "workspace",
    )
    if result is not None:
        clear_state = (result.get("cleared"), result.get("reason"))
        if result.get("path") != r"target\mvp\workspace.json":
            errors.append("mvp-wrapper-workspace-clear-before-json missing workspace path")
        elif clear_state not in {(True, "removed"), (False, "none")}:
            errors.append(
                "mvp-wrapper-workspace-clear-before-json unexpected clear state"
            )
    result = assert_command_json_result(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "forget", "--json"],
        errors,
        "mvp-wrapper-forget-before-json",
        "forget",
    )
    if result is not None:
        forget_state = (result.get("forgot"), result.get("reason"))
        if result.get("path") != r"target\mvp\last_session.json":
            errors.append("mvp-wrapper-forget-before-json missing session path")
        elif forget_state not in {(True, "removed"), (False, "none")}:
            errors.append("mvp-wrapper-forget-before-json unexpected forget state")
    for name, command, expected in CHECKS:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        output = (completed.stdout or "") + (completed.stderr or "")
        if completed.returncode != 0:
            errors.append(f"{name} 执行失败: exit={completed.returncode}")
            continue
        if expected not in output:
            errors.append(f"{name} 输出缺少关键文本: {expected}")


def append_wrapper_help_errors(errors: list[str]) -> None:
    output = load_help_output(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "help"],
        errors,
        "mvp-wrapper-help",
        failure_verb="执行失败",
    )
    if output is None:
        return
    append_expected_substring_errors(
        output,
        errors,
        _SMOKE_WRAPPER_HELP_EXPECTATIONS,
        _SMOKE_WRAPPER_HELP_GROUPED_EXPECTATIONS,
    )


def append_entrypoint_help_errors(errors: list[str]) -> None:
    append_help_usage_error(
        errors,
        "mvp-wrapper-cmd-help",
        ["cmd", "/c", "tools\\mvp\\safeclaw_mvp.cmd", "help"],
        "[mvp-wrapper] usage => tools\\mvp\\safeclaw_mvp.cmd <action> [flags]",
        "mvp-wrapper-cmd-help 输出缺少 usage",
        failure_verb="执行失败",
    )
    append_help_usage_error(
        errors,
        "mvp-wrapper-ps1-help",
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\\mvp\\safeclaw_mvp.ps1",
            "help",
        ],
        "[mvp-wrapper] usage => tools\\mvp\\safeclaw_mvp.cmd <action> [flags]",
        "mvp-wrapper-ps1-help 输出缺少 usage",
        failure_verb="执行失败",
    )
    append_help_usage_error(
        errors,
        "safeclaw-root-cmd-help",
        ["cmd", "/c", "safeclaw.cmd", "help"],
        "[mvp-wrapper] usage => safeclaw.cmd <action> [flags]",
        "safeclaw-root-cmd-help missing usage",
        failure_verb="failed",
    )
    append_help_usage_error(
        errors,
        "safeclaw-root-ps1-help",
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "safeclaw.ps1",
            "help",
        ],
        "[mvp-wrapper] usage => safeclaw.cmd <action> [flags]",
        "safeclaw-root-ps1-help missing usage",
        failure_verb="failed",
    )
