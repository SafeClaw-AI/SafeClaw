from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


JsonErrorCallable = Callable[..., Any]


@dataclass(frozen=True)
class InvalidArgumentCase:
    command_kind: str
    command_args: tuple[str, ...]
    name: str
    action: str
    expected_error_message_substring: str
    error_message_label: str | None = None
    expected_code: str | None = None
    expected_remembered_session_task_id: str | None = None
    remembered_session_label: str | None = None


@dataclass(frozen=True)
class InvalidArgumentContext:
    repo_root: Path
    python_executable: str
    subprocess_module: Any
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


def _build_command(
    python_executable: str,
    case: InvalidArgumentCase,
) -> list[str]:
    if case.command_kind == "cmd":
        return _cmd_command(*case.command_args)
    if case.command_kind == "ps1":
        return _ps1_command(*case.command_args)
    return _py_command(python_executable, *case.command_args)


def _append_invalid_argument_case(
    errors: list[str],
    ctx: InvalidArgumentContext,
    *,
    case: InvalidArgumentCase,
) -> None:
    expectations: dict[str, Any] = {
        "expected_error_message_substring": case.expected_error_message_substring,
    }
    if case.error_message_label is not None:
        expectations["error_message_label"] = case.error_message_label
    if case.expected_code is not None:
        expectations["expected_code"] = case.expected_code
    if case.expected_remembered_session_task_id is not None:
        expectations["expected_remembered_session_task_id"] = (
            case.expected_remembered_session_task_id
        )
    if case.remembered_session_label is not None:
        expectations["remembered_session_label"] = case.remembered_session_label
    ctx.assert_command_json_error(
        _build_command(ctx.python_executable, case),
        errors,
        case.name,
        case.action,
        **expectations,
    )


def _append_invalid_json_base_errors(
    errors: list[str],
    ctx: InvalidArgumentContext,
) -> None:
    result = ctx.subprocess_module.run(
        _py_command(
            ctx.python_executable,
            "run",
            "--reset",
            "--task-id",
            "task-wrapper-invalid-json-base",
        ),
        cwd=ctx.repo_root,
        capture_output=True,
        text=True,
    )
    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        errors.append(
            f"mvp-wrapper-invalid-json-base 执行失败: exit={result.returncode}"
        )
    elif (
        "[mvp] accepted task => task=task-wrapper-invalid-json-base "
        "effect=effect-task-wrapper-invalid-json-base"
        not in output
    ):
        errors.append(
            "mvp-wrapper-invalid-json-base 输出缺少基座会话 task-wrapper-invalid-json-base"
        )


_INVALID_ARGUMENT_CASES = (
    InvalidArgumentCase(
        command_kind="cmd",
        command_args=("report", "--bogus", "--json"),
        name="mvp-wrapper-cmd-report-invalid-json",
        action="report",
        expected_error_message_substring="unknown argument",
        error_message_label="mvp-wrapper-cmd-report-invalid-json missing unknown argument",
        expected_code="invalid-argument",
        expected_remembered_session_task_id="task-wrapper-invalid-json-base",
        remembered_session_label="mvp-wrapper-cmd-report-invalid-json missing invalid-json-base",
    ),
    InvalidArgumentCase(
        command_kind="ps1",
        command_args=("report", "--bogus", "--json"),
        name="mvp-wrapper-ps1-report-invalid-json",
        action="report",
        expected_error_message_substring="unknown argument",
        error_message_label="mvp-wrapper-ps1-report-invalid-json missing unknown argument",
        expected_code="invalid-argument",
        expected_remembered_session_task_id="task-wrapper-invalid-json-base",
        remembered_session_label="mvp-wrapper-ps1-report-invalid-json missing invalid-json-base",
    ),
    InvalidArgumentCase(
        command_kind="py",
        command_args=("report", "--bogus", "--json"),
        name="mvp-wrapper-report-invalid-json",
        action="report",
        expected_error_message_substring="unknown argument",
        error_message_label="mvp-wrapper-report-invalid-json 缺少 wrapper 级 unknown argument",
        expected_code="invalid-argument",
        expected_remembered_session_task_id="task-wrapper-invalid-json-base",
        remembered_session_label="mvp-wrapper-report-invalid-json remembered_session 缺少基座会话",
    ),
    InvalidArgumentCase(
        command_kind="cmd",
        command_args=("recover", "--bogus", "--json"),
        name="mvp-wrapper-cmd-recover-invalid-json",
        action="recover",
        expected_error_message_substring="unknown argument",
        error_message_label="mvp-wrapper-cmd-recover-invalid-json missing unknown argument",
        expected_code="invalid-argument",
        expected_remembered_session_task_id="task-wrapper-invalid-json-base",
        remembered_session_label="mvp-wrapper-cmd-recover-invalid-json missing invalid-json-base",
    ),
    InvalidArgumentCase(
        command_kind="ps1",
        command_args=("recover", "--bogus", "--json"),
        name="mvp-wrapper-ps1-recover-invalid-json",
        action="recover",
        expected_error_message_substring="unknown argument",
        error_message_label="mvp-wrapper-ps1-recover-invalid-json missing unknown argument",
        expected_code="invalid-argument",
        expected_remembered_session_task_id="task-wrapper-invalid-json-base",
        remembered_session_label="mvp-wrapper-ps1-recover-invalid-json missing invalid-json-base",
    ),
    InvalidArgumentCase(
        command_kind="py",
        command_args=("recover", "--bogus", "--json"),
        name="mvp-wrapper-recover-invalid-json",
        action="recover",
        expected_error_message_substring="unknown argument",
        error_message_label="mvp-wrapper-recover-invalid-json 缺少 wrapper 级 unknown argument",
        expected_code="invalid-argument",
        expected_remembered_session_task_id="task-wrapper-invalid-json-base",
        remembered_session_label="mvp-wrapper-recover-invalid-json remembered_session 缺少基座会话",
    ),
    InvalidArgumentCase(
        command_kind="cmd",
        command_args=("retry", "--bogus", "--json"),
        name="mvp-wrapper-cmd-retry-invalid-json",
        action="retry",
        expected_error_message_substring="unknown argument",
        error_message_label="mvp-wrapper-cmd-retry-invalid-json missing unknown argument",
        expected_code="invalid-argument",
        expected_remembered_session_task_id="task-wrapper-invalid-json-base",
        remembered_session_label="mvp-wrapper-cmd-retry-invalid-json missing invalid-json-base",
    ),
    InvalidArgumentCase(
        command_kind="ps1",
        command_args=("retry", "--bogus", "--json"),
        name="mvp-wrapper-ps1-retry-invalid-json",
        action="retry",
        expected_error_message_substring="unknown argument",
        error_message_label="mvp-wrapper-ps1-retry-invalid-json missing unknown argument",
        expected_code="invalid-argument",
        expected_remembered_session_task_id="task-wrapper-invalid-json-base",
        remembered_session_label="mvp-wrapper-ps1-retry-invalid-json missing invalid-json-base",
    ),
    InvalidArgumentCase(
        command_kind="py",
        command_args=("retry", "--bogus", "--json"),
        name="mvp-wrapper-retry-invalid-json",
        action="retry",
        expected_error_message_substring="unknown argument",
        error_message_label="mvp-wrapper-retry-invalid-json 缺少 wrapper 级 unknown argument",
        expected_code="invalid-argument",
        expected_remembered_session_task_id="task-wrapper-invalid-json-base",
        remembered_session_label="mvp-wrapper-retry-invalid-json remembered_session 缺少基座会话",
    ),
    InvalidArgumentCase(
        command_kind="cmd",
        command_args=("session", "--bogus", "--json"),
        name="mvp-wrapper-cmd-invalid-session-json",
        action="session",
        expected_error_message_substring="unknown argument",
    ),
    InvalidArgumentCase(
        command_kind="ps1",
        command_args=("session", "--bogus", "--json"),
        name="mvp-wrapper-ps1-invalid-session-json",
        action="session",
        expected_error_message_substring="unknown argument",
    ),
    InvalidArgumentCase(
        command_kind="cmd",
        command_args=("doctor", "--db", "--json"),
        name="mvp-wrapper-cmd-invalid-doctor-json",
        action="doctor",
        expected_error_message_substring="missing value after --db",
    ),
    InvalidArgumentCase(
        command_kind="ps1",
        command_args=("doctor", "--db", "--json"),
        name="mvp-wrapper-ps1-invalid-doctor-json",
        action="doctor",
        expected_error_message_substring="missing value after --db",
    ),
    InvalidArgumentCase(
        command_kind="cmd",
        command_args=("sessions", "--limit", "bad", "--json"),
        name="mvp-wrapper-cmd-invalid-sessions-json",
        action="sessions",
        expected_error_message_substring="invalid --limit",
    ),
    InvalidArgumentCase(
        command_kind="ps1",
        command_args=("sessions", "--limit", "bad", "--json"),
        name="mvp-wrapper-ps1-invalid-sessions-json",
        action="sessions",
        expected_error_message_substring="invalid --limit",
    ),
    InvalidArgumentCase(
        command_kind="py",
        command_args=("session", "--bogus", "--json"),
        name="mvp-wrapper-invalid-session-json",
        action="session",
        expected_error_message_substring="unknown argument",
    ),
    InvalidArgumentCase(
        command_kind="py",
        command_args=("doctor", "--db", "--json"),
        name="mvp-wrapper-invalid-doctor-json",
        action="doctor",
        expected_error_message_substring="missing value after --db",
    ),
)


def append_wrapper_invalid_argument_errors(
    errors: list[str],
    *,
    repo_root: Path,
    python_executable: str,
    subprocess_module: Any,
    assert_command_json_error: JsonErrorCallable,
) -> None:
    ctx = InvalidArgumentContext(
        repo_root=repo_root,
        python_executable=python_executable,
        subprocess_module=subprocess_module,
        assert_command_json_error=assert_command_json_error,
    )
    _append_invalid_json_base_errors(errors, ctx)
    for case in _INVALID_ARGUMENT_CASES:
        _append_invalid_argument_case(errors, ctx, case=case)
