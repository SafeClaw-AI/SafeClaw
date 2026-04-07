from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


JsonCallable = Callable[..., Any]


@dataclass(frozen=True)
class SessionListingContext:
    repo_root: Path
    python_executable: str
    assert_command_json_result: JsonCallable
    assert_command_json_error: JsonCallable
    assert_session_json_result: JsonCallable
    assert_sessions_json_result: JsonCallable
    assert_session_passthrough_json_result: JsonCallable
    assert_use_json_result: JsonCallable
    load_json_payload: JsonCallable
    extract_json_result: JsonCallable


def _run_text_command(command: list[str], repo_root: Path) -> tuple[subprocess.CompletedProcess[str], str]:
    completed = subprocess.run(
        command,
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    return completed, output


def _load_json_result(
    completed: subprocess.CompletedProcess[str],
    errors: list[str],
    ctx: SessionListingContext,
    name: str,
    action: str,
) -> dict[str, Any] | None:
    payload = ctx.load_json_payload(completed, errors, name, expected_exit=0)
    if payload is None:
        return None
    result = ctx.extract_json_result(payload, errors, name, action)
    return result if isinstance(result, dict) else None


def _append_session_seed_setup_errors(errors: list[str], ctx: SessionListingContext) -> None:
    for task_id, reset in [("task-wrapper-a", True), ("task-wrapper-b", False)]:
        command = [ctx.python_executable, "tools/mvp/safeclaw_mvp.py", "run"]
        if reset:
            command.append("--reset")
        command.extend(["--task-id", task_id])
        completed, output = _run_text_command(command, ctx.repo_root)
        if completed.returncode != 0:
            errors.append(f"mvp-wrapper-run-{task_id[-1]} 执行失败: exit={completed.returncode}")
            continue
        if f"[mvp] accepted task => task={task_id} effect=effect-{task_id}" not in output:
            errors.append(f"mvp-wrapper-run-{task_id[-1]} 输出缺少 {task_id}")


def _append_python_status_text_errors(errors: list[str], ctx: SessionListingContext) -> None:
    completed, output = _run_text_command(
        [ctx.python_executable, "tools/mvp/safeclaw_mvp.py", "status"],
        ctx.repo_root,
    )
    if completed.returncode != 0:
        errors.append(f"mvp-wrapper-status 执行失败: exit={completed.returncode}")
    elif "[mvp] status target => task=task-wrapper-b effect=effect-task-wrapper-b" not in output:
        errors.append("mvp-wrapper-status 输出缺少当前会话 task-wrapper-b")


def _append_python_status_json_errors(errors: list[str], ctx: SessionListingContext) -> None:
    result = _load_json_result(
        subprocess.run(
            [ctx.python_executable, "tools/mvp/safeclaw_mvp.py", "status", "--json"],
            cwd=ctx.repo_root,
            capture_output=True,
            text=True,
        ),
        errors,
        ctx,
        "mvp-wrapper-status-json",
        "status",
    )
    if result is not None:
        prepared = result.get("prepared") or []
        source_hints = result.get("source_hints") or {}
        if not prepared or prepared[0] != "status":
            errors.append("mvp-wrapper-status-json 缺少 prepared status")
        elif "task-wrapper-b" not in str(result.get("captured_output") or ""):
            errors.append("mvp-wrapper-status-json 缺少当前会话 task-wrapper-b 输出")
        elif source_hints.get("task_context") != "session":
            errors.append("mvp-wrapper-status-json 缺少 task_context=session")


def _append_status_argument_errors(errors: list[str], ctx: SessionListingContext) -> None:
    for command, name, message in [
        (
            ["cmd", "/c", r"tools\mvp\safeclaw_mvp.cmd", "status", "--bogus", "--json"],
            "mvp-wrapper-cmd-status-fail-json",
            "unknown argument",
        ),
        (
            ["cmd", "/c", r"tools\mvp\safeclaw_mvp.cmd", "status", "--db", "--json"],
            "mvp-wrapper-cmd-status-missing-db-json",
            "missing value after --db",
        ),
        (
            [ctx.python_executable, "tools/mvp/safeclaw_mvp.py", "status", "--bogus", "--json"],
            "mvp-wrapper-status-fail-json",
            "unknown argument",
        ),
        (
            [ctx.python_executable, "tools/mvp/safeclaw_mvp.py", "status", "--db", "--json"],
            "mvp-wrapper-status-missing-db-json",
            "missing value after --db",
        ),
    ]:
        ctx.assert_command_json_error(
            command,
            errors,
            name,
            "status",
            expected_error_message_substring=message,
            expected_code="invalid-argument",
            expected_remembered_session_task_id="task-wrapper-b",
            error_message_label=f"{name} missing {message}",
            remembered_session_label=f"{name} missing task-wrapper-b",
        )

    for command, name, message in [
        (
            [
                "powershell.exe",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                r"tools\mvp\safeclaw_mvp.ps1",
                "status",
                "--bogus",
                "--json",
            ],
            "mvp-wrapper-ps1-status-fail-json",
            "unknown argument",
        ),
        (
            [
                "powershell.exe",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                r"tools\mvp\safeclaw_mvp.ps1",
                "status",
                "--db",
                "--json",
            ],
            "mvp-wrapper-ps1-status-missing-db-json",
            "missing value after --db",
        ),
    ]:
        ctx.assert_command_json_error(
            command,
            errors,
            name,
            "status",
            expected_error_message_substring=message,
            expected_code="invalid-argument",
            expected_remembered_session_task_id="task-wrapper-b",
            error_message_label=f"{name} missing {message}",
            remembered_session_label=f"{name} missing task-wrapper-b",
        )


def _append_python_session_errors(errors: list[str], ctx: SessionListingContext) -> None:
    completed, output = _run_text_command(
        [ctx.python_executable, "tools/mvp/safeclaw_mvp.py", "session"],
        ctx.repo_root,
    )
    if completed.returncode != 0:
        errors.append(f"mvp-wrapper-session 执行失败: exit={completed.returncode}")
    elif "[mvp-wrapper] session => task=task-wrapper-b effect=effect-task-wrapper-b" not in output:
        errors.append("mvp-wrapper-session 输出缺少当前会话 task-wrapper-b")
    elif r"path=target\mvp\last_session.json" not in output:
        errors.append("mvp-wrapper-session 输出缺少 remembered session 路径")

    result = _load_json_result(
        subprocess.run(
            [ctx.python_executable, "tools/mvp/safeclaw_mvp.py", "session", "--json"],
            cwd=ctx.repo_root,
            capture_output=True,
            text=True,
        ),
        errors,
        ctx,
        "mvp-wrapper-session-json",
        "session",
    )
    if result is not None and (
        result.get("task_id") != "task-wrapper-b"
        or result.get("effect_id") != "effect-task-wrapper-b"
    ):
        errors.append("mvp-wrapper-session-json 输出缺少当前会话 task-wrapper-b")


def _append_python_sessions_text_errors(errors: list[str], ctx: SessionListingContext) -> None:
    completed, output = _run_text_command(
        [ctx.python_executable, "tools/mvp/safeclaw_mvp.py", "sessions"],
        ctx.repo_root,
    )
    if completed.returncode != 0:
        errors.append(f"mvp-wrapper-sessions 执行失败: exit={completed.returncode}")
    elif "[mvp-wrapper] sessions => db=target\\mvp\\session.db limit=5 source=session" not in output:
        errors.append("mvp-wrapper-sessions 输出缺少 db source=session")
    elif "[mvp-wrapper] recent[0] => task=task-wrapper-b effect=effect-task-wrapper-b" not in output:
        errors.append("mvp-wrapper-sessions 输出缺少最近任务 task-wrapper-b")
    elif "[mvp-wrapper] recent[1] => task=task-wrapper-a effect=effect-task-wrapper-a" not in output:
        errors.append("mvp-wrapper-sessions 输出缺少旧任务 task-wrapper-a")


def _append_python_sessions_json_errors(errors: list[str], ctx: SessionListingContext) -> None:
    result = _load_json_result(
        subprocess.run(
            [ctx.python_executable, "tools/mvp/safeclaw_mvp.py", "sessions", "--json"],
            cwd=ctx.repo_root,
            capture_output=True,
            text=True,
        ),
        errors,
        ctx,
        "mvp-wrapper-sessions-json",
        "sessions",
    )
    if result is None:
        return
    rows = result.get("rows") or []
    if result.get("db_source") != "session":
        errors.append("mvp-wrapper-sessions-json 输出缺少 db_source=session")
    elif not rows or rows[0].get("task_id") != "task-wrapper-b":
        errors.append("mvp-wrapper-sessions-json 输出缺少最近任务 task-wrapper-b")
    elif len(rows) < 2 or rows[1].get("task_id") != "task-wrapper-a":
        errors.append("mvp-wrapper-sessions-json 输出缺少旧任务 task-wrapper-a")


def _append_python_sessions_errors(errors: list[str], ctx: SessionListingContext) -> None:
    _append_python_sessions_text_errors(errors, ctx)
    _append_python_sessions_json_errors(errors, ctx)


def _append_shell_session_errors(errors: list[str], ctx: SessionListingContext) -> None:
    completed, output = _run_text_command(
        ["cmd", "/c", r"tools\mvp\safeclaw_mvp.cmd", "session"],
        ctx.repo_root,
    )
    if completed.returncode != 0:
        errors.append(f"mvp-wrapper-cmd-session failed: exit={completed.returncode}")
    elif "[mvp-wrapper] session => task=task-wrapper-b effect=effect-task-wrapper-b" not in output:
        errors.append("mvp-wrapper-cmd-session missing current session task-wrapper-b")
    elif r"path=target\mvp\last_session.json" not in output:
        errors.append("mvp-wrapper-cmd-session missing remembered session path")

    result = ctx.assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            r"tools\mvp\safeclaw_mvp.ps1",
            "session",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-session-json",
        "session",
    )
    ctx.assert_session_json_result(
        result,
        errors,
        "mvp-wrapper-ps1-session-json",
        expected_task_id="task-wrapper-b",
    )

    completed, output = _run_text_command(
        ["cmd", "/c", r"tools\mvp\safeclaw_mvp.cmd", "sessions"],
        ctx.repo_root,
    )
    if completed.returncode != 0:
        errors.append(f"mvp-wrapper-cmd-sessions failed: exit={completed.returncode}")
    elif r"[mvp-wrapper] sessions => db=target\mvp\session.db limit=5 source=session" not in output:
        errors.append("mvp-wrapper-cmd-sessions missing db source=session")
    elif "[mvp-wrapper] current => task=task-wrapper-b effect=effect-task-wrapper-b current_db=true" not in output:
        errors.append("mvp-wrapper-cmd-sessions missing task-wrapper-b row")
    elif "[mvp-wrapper] recent[0] => task=task-wrapper-b effect=effect-task-wrapper-b" not in output:
        errors.append("mvp-wrapper-cmd-sessions missing task-wrapper-b row")
    elif "[mvp-wrapper] recent[1] => task=task-wrapper-a effect=effect-task-wrapper-a" not in output:
        errors.append("mvp-wrapper-cmd-sessions missing task-wrapper-a row")

    result = ctx.assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            r"tools\mvp\safeclaw_mvp.ps1",
            "sessions",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-sessions-json",
        "sessions",
    )
    ctx.assert_sessions_json_result(
        result,
        errors,
        "mvp-wrapper-ps1-sessions-json",
        expected_current_task_id="task-wrapper-b",
        expected_previous_task_id="task-wrapper-a",
    )


def _append_use_errors(errors: list[str], ctx: SessionListingContext) -> None:
    result = ctx.assert_command_json_result(
        ["cmd", "/c", r"tools\mvp\safeclaw_mvp.cmd", "use", "--index", "1", "--json"],
        errors,
        "mvp-wrapper-cmd-use-json",
        "use",
    )
    ctx.assert_use_json_result(
        result,
        errors,
        "mvp-wrapper-cmd-use-json",
        expected_task_id="task-wrapper-a",
        expected_source="index:1",
    )

    result = ctx.assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            r"tools\mvp\safeclaw_mvp.ps1",
            "status",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-status-json",
        "status",
    )
    ctx.assert_session_passthrough_json_result(
        result,
        errors,
        "mvp-wrapper-ps1-status-json",
        action="status",
        expected_task_id="task-wrapper-a",
    )

    result = ctx.assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            r"tools\mvp\safeclaw_mvp.ps1",
            "use",
            "--index",
            "0",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-use-json",
        "use",
    )
    ctx.assert_use_json_result(
        result,
        errors,
        "mvp-wrapper-ps1-use-json",
        expected_task_id="task-wrapper-b",
        expected_source="index:0",
    )

    result = ctx.assert_command_json_result(
        ["cmd", "/c", r"tools\mvp\safeclaw_mvp.cmd", "status", "--json"],
        errors,
        "mvp-wrapper-cmd-status-json",
        "status",
    )
    ctx.assert_session_passthrough_json_result(
        result,
        errors,
        "mvp-wrapper-cmd-status-json",
        action="status",
        expected_task_id="task-wrapper-b",
    )


def _append_report_and_shell_json_errors(errors: list[str], ctx: SessionListingContext) -> None:
    result = ctx.assert_command_json_result(
        ["cmd", "/c", r"tools\mvp\safeclaw_mvp.cmd", "report", "--json"],
        errors,
        "mvp-wrapper-cmd-report-json",
        "report",
    )
    ctx.assert_session_passthrough_json_result(
        result,
        errors,
        "mvp-wrapper-cmd-report-json",
        action="report",
        expected_task_id="task-wrapper-b",
    )

    result = ctx.assert_command_json_result(
        ["cmd", "/c", r"tools\mvp\safeclaw_mvp.cmd", "session", "--json"],
        errors,
        "mvp-wrapper-cmd-session-json",
        "session",
    )
    ctx.assert_session_json_result(
        result,
        errors,
        "mvp-wrapper-cmd-session-json",
        expected_task_id="task-wrapper-b",
    )

    result = ctx.assert_command_json_result(
        ["cmd", "/c", r"tools\mvp\safeclaw_mvp.cmd", "sessions", "--json"],
        errors,
        "mvp-wrapper-cmd-sessions-json",
        "sessions",
    )
    ctx.assert_sessions_json_result(
        result,
        errors,
        "mvp-wrapper-cmd-sessions-json",
        expected_current_task_id="task-wrapper-b",
        expected_previous_task_id="task-wrapper-a",
    )

    result = ctx.assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            r"tools\mvp\safeclaw_mvp.ps1",
            "report",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-report-json",
        "report",
    )
    ctx.assert_session_passthrough_json_result(
        result,
        errors,
        "mvp-wrapper-ps1-report-json",
        action="report",
        expected_task_id="task-wrapper-b",
    )


def append_wrapper_session_listing_errors(
    errors: list[str],
    *,
    repo_root: Path,
    python_executable: str,
    assert_command_json_result: JsonCallable,
    assert_command_json_error: JsonCallable,
    assert_session_json_result: JsonCallable,
    assert_sessions_json_result: JsonCallable,
    assert_session_passthrough_json_result: JsonCallable,
    assert_use_json_result: JsonCallable,
    load_json_payload: JsonCallable,
    extract_json_result: JsonCallable,
) -> None:
    ctx = SessionListingContext(
        repo_root=repo_root,
        python_executable=python_executable,
        assert_command_json_result=assert_command_json_result,
        assert_command_json_error=assert_command_json_error,
        assert_session_json_result=assert_session_json_result,
        assert_sessions_json_result=assert_sessions_json_result,
        assert_session_passthrough_json_result=assert_session_passthrough_json_result,
        assert_use_json_result=assert_use_json_result,
        load_json_payload=load_json_payload,
        extract_json_result=extract_json_result,
    )
    _append_session_seed_setup_errors(errors, ctx)
    _append_python_status_text_errors(errors, ctx)
    _append_python_status_json_errors(errors, ctx)
    _append_status_argument_errors(errors, ctx)
    _append_python_session_errors(errors, ctx)
    _append_python_sessions_errors(errors, ctx)
    _append_shell_session_errors(errors, ctx)
    _append_use_errors(errors, ctx)
    _append_report_and_shell_json_errors(errors, ctx)
