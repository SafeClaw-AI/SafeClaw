from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


JsonCallable = Callable[..., Any]
_FAILED_OUTPUT_FRAGMENTS = (
    "RetryEligible",
    "worker=Failed",
    "effect=Prepared",
)


@dataclass(frozen=True)
class FailedSessionContext:
    python_executable: str
    assert_command_json_result: JsonCallable
    assert_run_json_result: JsonCallable


def _build_ps1_command(
    action: str,
    *,
    db_path: str | None = None,
    task_id: str | None = None,
) -> list[str]:
    command = [
        "powershell.exe",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        r"tools\mvp\safeclaw_mvp.ps1",
        action,
    ]
    if db_path is not None:
        command.extend(["--db", db_path])
    if task_id is not None:
        command.extend(["--task-id", task_id])
    command.append("--json")
    return command


def _build_cmd_command(action: str) -> list[str]:
    return ["cmd", "/c", r"tools\mvp\safeclaw_mvp.cmd", action, "--json"]


def _append_seed_failed_json_errors(
    errors: list[str],
    ctx: FailedSessionContext,
    *,
    name: str,
    task_id: str,
    db_path: str,
    output_path: str,
) -> None:
    result = ctx.assert_command_json_result(
        [
            ctx.python_executable,
            "tools/mvp/safeclaw_mvp.py",
            "seed-failed",
            "--reset",
            "--task-id",
            task_id,
            "--db",
            db_path,
            "--output",
            output_path,
            "--json",
        ],
        errors,
        name,
        "seed-failed",
    )
    ctx.assert_run_json_result(
        result,
        errors,
        name,
        expected_task_id=task_id,
        expected_db_path=db_path,
        expected_output_path=output_path,
        expected_db_source="flag",
        expected_output_source="flag",
    )


def _append_prepared_action_error(
    errors: list[str],
    *,
    name: str,
    action: str,
    prepared: list[Any],
) -> bool:
    if not prepared or prepared[0] != action:
        errors.append(f"{name} missing prepared {action}")
        return True
    return False


def _append_captured_task_error(
    errors: list[str],
    *,
    name: str,
    task_id: str,
    captured_output: str,
) -> bool:
    if task_id not in captured_output:
        errors.append(f"{name} missing captured task {task_id}")
        return True
    return False


def _append_required_output_fragment_error(
    errors: list[str],
    *,
    name: str,
    captured_output: str,
) -> bool:
    for fragment in _FAILED_OUTPUT_FRAGMENTS:
        if fragment not in captured_output:
            errors.append(f"{name} missing {fragment}")
            return True
    return False


def _append_remembered_session_error(
    errors: list[str],
    *,
    name: str,
    task_id: str,
    remembered_session: Any,
) -> bool:
    if (
        not isinstance(remembered_session, dict)
        or remembered_session.get("task_id") != task_id
    ):
        errors.append(f"{name} missing remembered session {task_id}")
        return True
    return False


def _append_source_hints_error(
    errors: list[str],
    *,
    name: str,
    source_hints: Any,
    expected_db: str,
    expected_task_context: str,
) -> None:
    if not isinstance(source_hints, dict) or source_hints.get("db") != expected_db:
        errors.append(f"{name} missing source_hints.db={expected_db}")
    elif source_hints.get("output") != "session":
        errors.append(f"{name} missing source_hints.output=session")
    elif source_hints.get("owner_id") != "session":
        errors.append(f"{name} missing source_hints.owner_id=session")
    elif source_hints.get("task_context") != expected_task_context:
        errors.append(
            f"{name} missing source_hints.task_context={expected_task_context}"
        )


def _append_command_output_errors(
    errors: list[str],
    ctx: FailedSessionContext,
    *,
    command: list[str],
    name: str,
    action: str,
    task_id: str,
    expected_source_hints_db: str,
    expected_source_hints_task_context: str,
) -> None:
    result = ctx.assert_command_json_result(command, errors, name, action)
    if result is None:
        return

    prepared = result.get("prepared") or []
    remembered_session = result.get("remembered_session") or {}
    source_hints = result.get("source_hints") or {}
    captured_output = str(result.get("captured_output") or "")
    if _append_prepared_action_error(errors, name=name, action=action, prepared=prepared):
        return
    if _append_captured_task_error(
        errors,
        name=name,
        task_id=task_id,
        captured_output=captured_output,
    ):
        return
    if _append_required_output_fragment_error(
        errors,
        name=name,
        captured_output=captured_output,
    ):
        return
    if _append_remembered_session_error(
        errors,
        name=name,
        task_id=task_id,
        remembered_session=remembered_session,
    ):
        return
    _append_source_hints_error(
        errors,
        name=name,
        source_hints=source_hints,
        expected_db=expected_source_hints_db,
        expected_task_context=expected_source_hints_task_context,
    )


def _append_mapping_field_errors(
    errors: list[str],
    *,
    name: str,
    payload: Any,
    label: str,
    expected_fields: tuple[tuple[str, Any, str | None], ...],
) -> bool:
    if not isinstance(payload, dict):
        return True
    prefix = f"{label} " if label else ""
    for field_name, expected_value, rendered_value in expected_fields:
        if payload.get(field_name) != expected_value:
            shown_value = rendered_value if rendered_value is not None else expected_value
            errors.append(f"{name} missing {prefix}{field_name}={shown_value}")
            return True
    return False


def _append_named_task_identity_error(
    errors: list[str],
    *,
    name: str,
    payload: Any,
    label: str,
    task_id: str,
) -> bool:
    if not isinstance(payload, dict) or payload.get("task_id") != task_id:
        errors.append(f"{name} missing {label} {task_id}")
        return True
    return False


def _append_session_identity_errors(
    errors: list[str],
    ctx: FailedSessionContext,
    *,
    command: list[str],
    name: str,
    task_id: str,
    db_path: str,
    output_path: str,
) -> None:
    result = ctx.assert_command_json_result(command, errors, name, "session")
    if result is None:
        return
    _append_mapping_field_errors(
        errors,
        name=name,
        payload=result,
        label="",
        expected_fields=(
            ("task_id", task_id, None),
            ("effect_id", f"effect-{task_id}", None),
            ("db", db_path, None),
            ("output", output_path, None),
            ("owner_id", "safeclaw-mvp", None),
        ),
    )


def _append_sessions_current_session_errors(
    errors: list[str],
    *,
    name: str,
    current_session: Any,
    task_id: str,
    db_path: str,
    output_path: str,
) -> bool:
    if _append_named_task_identity_error(
        errors,
        name=name,
        payload=current_session,
        label="current_session",
        task_id=task_id,
    ):
        return True
    return _append_mapping_field_errors(
        errors,
        name=name,
        payload=current_session,
        label="current_session",
        expected_fields=(
            ("effect_id", f"effect-{task_id}", None),
            ("db", db_path, None),
            ("output", output_path, None),
            ("owner_id", "safeclaw-mvp", None),
        ),
    )


def _append_sessions_first_row_errors(
    errors: list[str],
    *,
    name: str,
    rows: Any,
    task_id: str,
) -> bool:
    if not rows or rows[0].get("task_id") != task_id:
        errors.append(f"{name} missing rows[0] {task_id}")
        return True
    return _append_mapping_field_errors(
        errors,
        name=name,
        payload=rows[0],
        label="rows[0]",
        expected_fields=(
            ("effect_id", f"effect-{task_id}", None),
            ("worker_state", "failed", None),
            ("effect_status", "prepared", None),
            ("next_action", "retry", None),
            ("coordination_summary", "retry_now", None),
            ("current", True, "true"),
        ),
    )


def _append_sessions_listing_errors(
    errors: list[str],
    ctx: FailedSessionContext,
    *,
    command: list[str],
    name: str,
    task_id: str,
    db_path: str,
    output_path: str,
) -> None:
    result = ctx.assert_command_json_result(command, errors, name, "sessions")
    if result is None:
        return
    if _append_mapping_field_errors(
        errors,
        name=name,
        payload=result,
        label="",
        expected_fields=(
            ("db", db_path, None),
            ("db_source", "session", None),
            ("limit", 5, None),
        ),
    ):
        return
    current_session = result.get("current_session") or {}
    rows = result.get("rows") or []
    if _append_sessions_current_session_errors(
        errors,
        name=name,
        current_session=current_session,
        task_id=task_id,
        db_path=db_path,
        output_path=output_path,
    ):
        return
    _append_sessions_first_row_errors(
        errors,
        name=name,
        rows=rows,
        task_id=task_id,
    )


def _append_status_failed_session_errors(
    errors: list[str],
    ctx: FailedSessionContext,
) -> None:
    task_id = "task-wrapper-status-failed-session"
    db_path = "target/mvp/status-failed-session.db"
    _append_seed_failed_json_errors(
        errors,
        ctx,
        name="mvp-wrapper-status-failed-session-seed-failed-json",
        task_id=task_id,
        db_path=db_path,
        output_path="target/mvp/status-failed-session.txt",
    )
    _append_command_output_errors(
        errors,
        ctx,
        command=_build_ps1_command("report", db_path=db_path, task_id=task_id),
        name="mvp-wrapper-ps1-report-status-failed-session-json",
        action="report",
        task_id=task_id,
        expected_source_hints_db="flag",
        expected_source_hints_task_context="flag",
    )
    _append_command_output_errors(
        errors,
        ctx,
        command=_build_ps1_command("status"),
        name="mvp-wrapper-ps1-status-failed-session-json",
        action="status",
        task_id=task_id,
        expected_source_hints_db="session",
        expected_source_hints_task_context="session",
    )
    _append_command_output_errors(
        errors,
        ctx,
        command=_build_cmd_command("status"),
        name="mvp-wrapper-cmd-status-failed-session-json",
        action="status",
        task_id=task_id,
        expected_source_hints_db="session",
        expected_source_hints_task_context="session",
    )


def _append_report_failed_session_errors(
    errors: list[str],
    ctx: FailedSessionContext,
) -> None:
    task_id = "task-wrapper-report-failed-session"
    db_path = "target/mvp/report-failed-session.db"
    _append_seed_failed_json_errors(
        errors,
        ctx,
        name="mvp-wrapper-report-failed-session-seed-failed-json",
        task_id=task_id,
        db_path=db_path,
        output_path="target/mvp/report-failed-session.txt",
    )
    _append_command_output_errors(
        errors,
        ctx,
        command=_build_ps1_command("report", db_path=db_path, task_id=task_id),
        name="mvp-wrapper-ps1-report-report-failed-session-json",
        action="report",
        task_id=task_id,
        expected_source_hints_db="flag",
        expected_source_hints_task_context="flag",
    )
    _append_command_output_errors(
        errors,
        ctx,
        command=_build_ps1_command("report"),
        name="mvp-wrapper-ps1-report-failed-session-json",
        action="report",
        task_id=task_id,
        expected_source_hints_db="session",
        expected_source_hints_task_context="session",
    )
    _append_command_output_errors(
        errors,
        ctx,
        command=_build_cmd_command("report"),
        name="mvp-wrapper-cmd-report-failed-session-json",
        action="report",
        task_id=task_id,
        expected_source_hints_db="session",
        expected_source_hints_task_context="session",
    )


def _append_session_failed_errors(
    errors: list[str],
    ctx: FailedSessionContext,
) -> None:
    task_id = "task-wrapper-session-failed"
    db_path = "target/mvp/session-failed.db"
    output_path = "target/mvp/session-failed.txt"
    _append_seed_failed_json_errors(
        errors,
        ctx,
        name="mvp-wrapper-session-failed-seed-json",
        task_id=task_id,
        db_path=db_path,
        output_path=output_path,
    )
    _append_command_output_errors(
        errors,
        ctx,
        command=_build_ps1_command("report", db_path=db_path, task_id=task_id),
        name="mvp-wrapper-ps1-report-session-failed-json",
        action="report",
        task_id=task_id,
        expected_source_hints_db="flag",
        expected_source_hints_task_context="flag",
    )
    _append_session_identity_errors(
        errors,
        ctx,
        command=_build_ps1_command("session"),
        name="mvp-wrapper-ps1-session-failed-json",
        task_id=task_id,
        db_path=db_path,
        output_path=output_path,
    )
    _append_session_identity_errors(
        errors,
        ctx,
        command=_build_cmd_command("session"),
        name="mvp-wrapper-cmd-session-failed-json",
        task_id=task_id,
        db_path=db_path,
        output_path=output_path,
    )


def _append_sessions_failed_errors(
    errors: list[str],
    ctx: FailedSessionContext,
) -> None:
    task_id = "task-wrapper-sessions-failed"
    db_path = "target/mvp/sessions-failed.db"
    output_path = "target/mvp/sessions-failed.txt"
    _append_seed_failed_json_errors(
        errors,
        ctx,
        name="mvp-wrapper-sessions-failed-seed-json",
        task_id=task_id,
        db_path=db_path,
        output_path=output_path,
    )
    _append_command_output_errors(
        errors,
        ctx,
        command=_build_ps1_command("report", db_path=db_path, task_id=task_id),
        name="mvp-wrapper-ps1-report-sessions-failed-json",
        action="report",
        task_id=task_id,
        expected_source_hints_db="flag",
        expected_source_hints_task_context="flag",
    )
    _append_sessions_listing_errors(
        errors,
        ctx,
        command=_build_ps1_command("sessions"),
        name="mvp-wrapper-ps1-sessions-failed-json",
        task_id=task_id,
        db_path=db_path,
        output_path=output_path,
    )
    _append_sessions_listing_errors(
        errors,
        ctx,
        command=_build_cmd_command("sessions"),
        name="mvp-wrapper-cmd-sessions-failed-json",
        task_id=task_id,
        db_path=db_path,
        output_path=output_path,
    )


def append_wrapper_failed_session_errors(
    errors: list[str],
    *,
    python_executable: str,
    assert_command_json_result: JsonCallable,
    assert_run_json_result: JsonCallable,
) -> None:
    ctx = FailedSessionContext(
        python_executable=python_executable,
        assert_command_json_result=assert_command_json_result,
        assert_run_json_result=assert_run_json_result,
    )
    _append_status_failed_session_errors(errors, ctx)
    _append_report_failed_session_errors(errors, ctx)
    _append_session_failed_errors(errors, ctx)
    _append_sessions_failed_errors(errors, ctx)
