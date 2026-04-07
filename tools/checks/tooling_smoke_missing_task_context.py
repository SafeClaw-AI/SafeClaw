from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


JsonErrorCallable = Callable[..., Any]


@dataclass(frozen=True)
class MissingTaskContextCase:
    command_kind: str
    command_args: tuple[str, ...]
    name: str
    action: str
    error_message_substring: str
    error_message_label: str
    expected_code: str
    expected_failed_step: str | None = None
    expected_details_message_substring: str | None = None
    expect_no_remembered_session: bool = True


@dataclass(frozen=True)
class MissingTaskContextContext:
    python_executable: str
    assert_command_json_error: JsonErrorCallable


def _cmd_command(*args: str) -> list[str]:
    return ["cmd", "/c", r"tools\mvp\safeclaw_mvp.cmd", *args]


def _ps1_command(*args: str) -> list[str]:
    return [
        "powershell.exe",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        r"tools\mvp\safeclaw_mvp.ps1",
        *args,
    ]


def _py_command(python_executable: str, *args: str) -> list[str]:
    return [python_executable, "tools/mvp/safeclaw_mvp.py", *args]


def _append_missing_task_context_case(
    errors: list[str],
    ctx: MissingTaskContextContext,
    *,
    case: MissingTaskContextCase,
) -> None:
    expectations: dict[str, Any] = {
        "expected_error_message_substring": case.error_message_substring,
        "error_message_label": case.error_message_label,
        "expected_code": case.expected_code,
        "expect_no_remembered_session": case.expect_no_remembered_session,
    }
    if case.expected_failed_step is not None:
        expectations["expected_failed_step"] = case.expected_failed_step
    if case.expected_details_message_substring is not None:
        expectations["expected_details_message_substring"] = (
            case.expected_details_message_substring
        )
    command = _build_command(ctx.python_executable, case)
    ctx.assert_command_json_error(
        command,
        errors,
        case.name,
        case.action,
        **expectations,
    )


def _build_command(
    python_executable: str,
    case: MissingTaskContextCase,
) -> list[str]:
    if case.command_kind == "cmd":
        return _cmd_command(*case.command_args)
    if case.command_kind == "ps1":
        return _ps1_command(*case.command_args)
    return _py_command(python_executable, *case.command_args)


_MISSING_TASK_CONTEXT_CASES = (
    MissingTaskContextCase(
        command_kind="cmd",
        command_args=("report", "--json"),
        name="mvp-wrapper-cmd-report-without-session-json",
        action="report",
        error_message_substring="missing task context",
        error_message_label="mvp-wrapper-cmd-report-without-session-json missing wrapper error",
        expected_code="missing-task-context",
    ),
    MissingTaskContextCase(
        command_kind="ps1",
        command_args=("report", "--json"),
        name="mvp-wrapper-ps1-report-without-session-json",
        action="report",
        error_message_substring="missing task context",
        error_message_label="mvp-wrapper-ps1-report-without-session-json missing wrapper error",
        expected_code="missing-task-context",
    ),
    MissingTaskContextCase(
        command_kind="py",
        command_args=("report", "--json"),
        name="mvp-wrapper-report-without-session-json",
        action="report",
        error_message_substring="missing task context",
        error_message_label="mvp-wrapper-report-without-session-json 缺少 wrapper 级错误消息",
        expected_code="missing-task-context",
    ),
    MissingTaskContextCase(
        command_kind="cmd",
        command_args=("recover", "--json"),
        name="mvp-wrapper-cmd-recover-without-session-json",
        action="recover",
        error_message_substring="missing task context",
        error_message_label="mvp-wrapper-cmd-recover-without-session-json missing wrapper error",
        expected_code="missing-task-context",
    ),
    MissingTaskContextCase(
        command_kind="ps1",
        command_args=("recover", "--json"),
        name="mvp-wrapper-ps1-recover-without-session-json",
        action="recover",
        error_message_substring="missing task context",
        error_message_label="mvp-wrapper-ps1-recover-without-session-json missing wrapper error",
        expected_code="missing-task-context",
    ),
    MissingTaskContextCase(
        command_kind="py",
        command_args=("recover", "--json"),
        name="mvp-wrapper-recover-without-session-json",
        action="recover",
        error_message_substring="missing task context",
        error_message_label="mvp-wrapper-recover-without-session-json ?? wrapper ?????",
        expected_code="missing-task-context",
    ),
    MissingTaskContextCase(
        command_kind="cmd",
        command_args=("retry", "--json"),
        name="mvp-wrapper-cmd-retry-without-session-json",
        action="retry",
        error_message_substring="missing task context",
        error_message_label="mvp-wrapper-cmd-retry-without-session-json missing wrapper error",
        expected_code="missing-task-context",
    ),
    MissingTaskContextCase(
        command_kind="ps1",
        command_args=("retry", "--json"),
        name="mvp-wrapper-ps1-retry-without-session-json",
        action="retry",
        error_message_substring="missing task context",
        error_message_label="mvp-wrapper-ps1-retry-without-session-json missing wrapper error",
        expected_code="missing-task-context",
    ),
    MissingTaskContextCase(
        command_kind="py",
        command_args=("retry", "--json"),
        name="mvp-wrapper-retry-without-session-json",
        action="retry",
        error_message_substring="missing task context",
        error_message_label="mvp-wrapper-retry-without-session-json 缺少 wrapper 级错误消息",
        expected_code="missing-task-context",
    ),
    MissingTaskContextCase(
        command_kind="py",
        command_args=("service-resume", "--json"),
        name="mvp-wrapper-service-resume-without-session-json",
        action="service-resume",
        error_message_substring="failed step=resume",
        error_message_label="mvp-wrapper-service-resume-without-session-json missing wrapper error",
        expected_code="missing-task-context",
        expected_failed_step="resume",
        expected_details_message_substring="missing task context",
    ),
    MissingTaskContextCase(
        command_kind="py",
        command_args=("resume", "--db", "target/mvp/resume-missing.db", "--json"),
        name="mvp-wrapper-resume-missing-task-json",
        action="resume",
        error_message_substring="missing task context",
        error_message_label="mvp-wrapper-resume-missing-task-json missing wrapper error",
        expected_code="missing-task-context",
    ),
    MissingTaskContextCase(
        command_kind="cmd",
        command_args=("resume", "--db", "target/mvp/resume-missing-cmd.db", "--json"),
        name="mvp-wrapper-cmd-resume-missing-task-json",
        action="resume",
        error_message_substring="missing task context",
        error_message_label="mvp-wrapper-cmd-resume-missing-task-json missing wrapper error",
        expected_code="missing-task-context",
    ),
    MissingTaskContextCase(
        command_kind="ps1",
        command_args=("resume", "--db", "target/mvp/resume-missing-ps1.db", "--json"),
        name="mvp-wrapper-ps1-resume-missing-task-json",
        action="resume",
        error_message_substring="missing task context",
        error_message_label="mvp-wrapper-ps1-resume-missing-task-json missing wrapper error",
        expected_code="missing-task-context",
    ),
    MissingTaskContextCase(
        command_kind="cmd",
        command_args=(
            "reconcile",
            "--db",
            "target/mvp/reconcile-missing-cmd.db",
            "--decision",
            "executed",
            "--json",
        ),
        name="mvp-wrapper-cmd-reconcile-missing-task-json",
        action="reconcile",
        error_message_substring="missing task context",
        error_message_label="mvp-wrapper-cmd-reconcile-missing-task-json missing wrapper error",
        expected_code="missing-task-context",
    ),
    MissingTaskContextCase(
        command_kind="ps1",
        command_args=(
            "reconcile",
            "--db",
            "target/mvp/reconcile-missing-ps1.db",
            "--decision",
            "executed",
            "--json",
        ),
        name="mvp-wrapper-ps1-reconcile-missing-task-json",
        action="reconcile",
        error_message_substring="missing task context",
        error_message_label="mvp-wrapper-ps1-reconcile-missing-task-json missing wrapper error",
        expected_code="missing-task-context",
    ),
    MissingTaskContextCase(
        command_kind="py",
        command_args=(
            "reconcile",
            "--db",
            "target/mvp/reconcile-missing.db",
            "--decision",
            "executed",
            "--json",
        ),
        name="mvp-wrapper-reconcile-missing-task-json",
        action="reconcile",
        error_message_substring="missing task context",
        error_message_label="mvp-wrapper-reconcile-missing-task-json missing wrapper error",
        expected_code="missing-task-context",
    ),
    MissingTaskContextCase(
        command_kind="py",
        command_args=(
            "service-reconcile",
            "--db",
            "target/mvp/service-reconcile-missing.db",
            "--decision",
            "executed",
            "--json",
        ),
        name="mvp-wrapper-service-reconcile-missing-task-json",
        action="service-reconcile",
        error_message_substring="failed step=reconcile",
        error_message_label="mvp-wrapper-service-reconcile-missing-task-json missing wrapper error",
        expected_code="missing-task-context",
        expected_failed_step="reconcile",
        expected_details_message_substring="missing task context",
    ),
)


def append_wrapper_missing_task_context_errors(
    errors: list[str],
    *,
    python_executable: str,
    assert_command_json_error: JsonErrorCallable,
) -> None:
    ctx = MissingTaskContextContext(
        python_executable=python_executable,
        assert_command_json_error=assert_command_json_error,
    )
    for case in _MISSING_TASK_CONTEXT_CASES:
        _append_missing_task_context_case(errors, ctx, case=case)
