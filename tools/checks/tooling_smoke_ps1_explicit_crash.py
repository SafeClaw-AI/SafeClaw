from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


JsonCallable = Callable[..., Any]
_CRASH_OUTPUT_FRAGMENTS = (
    "QueueForManualReview",
    "worker=Uncertain",
    "effect=Uncertain",
)


@dataclass(frozen=True)
class Ps1ExplicitCrashContext:
    python_executable: str
    assert_command_json_result: JsonCallable
    assert_run_json_result: JsonCallable


def _append_seed_crash_json_errors(
    errors: list[str],
    ctx: Ps1ExplicitCrashContext,
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
            "seed-crash",
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
        "seed-crash",
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


def _append_ps1_explicit_crash_output_errors(
    errors: list[str],
    ctx: Ps1ExplicitCrashContext,
    *,
    action: str,
    name: str,
    task_id: str,
    db_path: str,
) -> None:
    result = ctx.assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            r"tools\mvp\safeclaw_mvp.ps1",
            action,
            "--db",
            db_path,
            "--task-id",
            task_id,
            "--json",
        ],
        errors,
        name,
        action,
    )
    if result is None:
        return

    prepared = result.get("prepared") or []
    remembered_session = result.get("remembered_session") or {}
    source_hints = result.get("source_hints") or {}
    captured_output = str(result.get("captured_output") or "")

    if _append_prepared_and_capture_errors(
        errors,
        name=name,
        action=action,
        task_id=task_id,
        prepared=prepared,
        captured_output=captured_output,
    ):
        return
    if _append_remembered_session_errors(
        errors,
        name=name,
        task_id=task_id,
        remembered_session=remembered_session,
    ):
        return
    _append_source_hints_errors(errors, name=name, source_hints=source_hints)


def _append_prepared_and_capture_errors(
    errors: list[str],
    *,
    action: str,
    name: str,
    task_id: str,
    prepared: list[Any],
    captured_output: str,
) -> bool:
    if not prepared or prepared[0] != action:
        errors.append(f"{name} missing prepared {action}")
        return True
    if task_id not in captured_output:
        errors.append(f"{name} missing captured task {task_id}")
        return True
    for fragment in _CRASH_OUTPUT_FRAGMENTS:
        if fragment not in captured_output:
            errors.append(f"{name} missing {fragment}")
            return True
    return False


def _append_remembered_session_errors(
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


def _append_source_hints_errors(
    errors: list[str],
    *,
    name: str,
    source_hints: Any,
) -> None:
    if not isinstance(source_hints, dict) or source_hints.get("db") != "flag":
        errors.append(f"{name} missing source_hints.db=flag")
    elif source_hints.get("output") != "session":
        errors.append(f"{name} missing source_hints.output=session")
    elif source_hints.get("owner_id") != "session":
        errors.append(f"{name} missing source_hints.owner_id=session")
    elif source_hints.get("task_context") != "flag":
        errors.append(f"{name} missing source_hints.task_context=flag")


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


def _append_ps1_session_explicit_crash_json_errors(
    errors: list[str],
    ctx: Ps1ExplicitCrashContext,
) -> None:
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
        "mvp-wrapper-ps1-session-explicit-crash-json",
        "session",
    )
    if result is None:
        return

    _append_mapping_field_errors(
        errors,
        name="mvp-wrapper-ps1-session-explicit-crash-json",
        payload=result,
        label="",
        expected_fields=(
            ("task_id", "task-wrapper-session-explicit-crash", None),
            (
                "effect_id",
                "effect-task-wrapper-session-explicit-crash",
                None,
            ),
            ("db", "target/mvp/session-explicit-crash.db", None),
            ("output", "target/mvp/session-explicit-crash.txt", None),
            ("owner_id", "safeclaw-mvp", None),
        ),
    )


def _append_sessions_current_session_errors(
    errors: list[str],
    *,
    name: str,
    current_session: Any,
) -> bool:
    if _append_named_task_identity_error(
        errors,
        name=name,
        payload=current_session,
        label="current_session",
        task_id="task-wrapper-sessions-explicit-crash",
    ):
        return True
    return _append_mapping_field_errors(
        errors,
        name=name,
        payload=current_session,
        label="current_session",
        expected_fields=(
            (
                "effect_id",
                "effect-task-wrapper-sessions-explicit-crash",
                None,
            ),
            ("db", "target/mvp/sessions-explicit-crash.db", None),
            ("output", "target/mvp/sessions-explicit-crash.txt", None),
            ("owner_id", "safeclaw-mvp", None),
        ),
    )


def _append_sessions_first_row_errors(
    errors: list[str],
    *,
    name: str,
    rows: Any,
) -> bool:
    if not rows or rows[0].get("task_id") != "task-wrapper-sessions-explicit-crash":
        errors.append(
            f"{name} missing rows[0] task-wrapper-sessions-explicit-crash"
        )
        return True
    return _append_mapping_field_errors(
        errors,
        name=name,
        payload=rows[0],
        label="rows[0]",
        expected_fields=(
            (
                "effect_id",
                "effect-task-wrapper-sessions-explicit-crash",
                None,
            ),
            ("worker_state", "uncertain", None),
            ("effect_status", "uncertain", None),
            ("next_action", "recover", None),
            ("coordination_summary", "recover_now", None),
            ("current", True, "true"),
        ),
    )


def _append_ps1_sessions_explicit_crash_json_errors(
    errors: list[str],
    ctx: Ps1ExplicitCrashContext,
) -> None:
    name = "mvp-wrapper-ps1-sessions-explicit-crash-json"
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
        name,
        "sessions",
    )
    if result is None:
        return

    if _append_mapping_field_errors(
        errors,
        name=name,
        payload=result,
        label="",
        expected_fields=(
            ("db", "target/mvp/sessions-explicit-crash.db", None),
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
    ):
        return
    _append_sessions_first_row_errors(errors, name=name, rows=rows)


def _append_status_explicit_crash_errors(
    errors: list[str],
    ctx: Ps1ExplicitCrashContext,
) -> None:
    _append_seed_crash_json_errors(
        errors,
        ctx,
        name="mvp-wrapper-status-explicit-crash-seed-json",
        task_id="task-wrapper-status-explicit-crash",
        db_path="target/mvp/status-explicit-crash.db",
        output_path="target/mvp/status-explicit-crash.txt",
    )
    _append_ps1_explicit_crash_output_errors(
        errors,
        ctx,
        action="status",
        name="mvp-wrapper-ps1-status-explicit-crash-json",
        task_id="task-wrapper-status-explicit-crash",
        db_path="target/mvp/status-explicit-crash.db",
    )


def _append_report_explicit_crash_errors(
    errors: list[str],
    ctx: Ps1ExplicitCrashContext,
) -> None:
    _append_seed_crash_json_errors(
        errors,
        ctx,
        name="mvp-wrapper-report-explicit-crash-seed-json",
        task_id="task-wrapper-report-explicit-crash",
        db_path="target/mvp/report-explicit-crash.db",
        output_path="target/mvp/report-explicit-crash.txt",
    )
    _append_ps1_explicit_crash_output_errors(
        errors,
        ctx,
        action="report",
        name="mvp-wrapper-ps1-report-explicit-crash-json",
        task_id="task-wrapper-report-explicit-crash",
        db_path="target/mvp/report-explicit-crash.db",
    )


def _append_session_explicit_crash_errors(
    errors: list[str],
    ctx: Ps1ExplicitCrashContext,
) -> None:
    _append_seed_crash_json_errors(
        errors,
        ctx,
        name="mvp-wrapper-session-explicit-crash-seed-json",
        task_id="task-wrapper-session-explicit-crash",
        db_path="target/mvp/session-explicit-crash.db",
        output_path="target/mvp/session-explicit-crash.txt",
    )
    _append_ps1_explicit_crash_output_errors(
        errors,
        ctx,
        action="report",
        name="mvp-wrapper-ps1-report-session-explicit-crash-json",
        task_id="task-wrapper-session-explicit-crash",
        db_path="target/mvp/session-explicit-crash.db",
    )
    _append_ps1_session_explicit_crash_json_errors(errors, ctx)


def _append_sessions_explicit_crash_errors(
    errors: list[str],
    ctx: Ps1ExplicitCrashContext,
) -> None:
    _append_seed_crash_json_errors(
        errors,
        ctx,
        name="mvp-wrapper-sessions-explicit-crash-seed-json",
        task_id="task-wrapper-sessions-explicit-crash",
        db_path="target/mvp/sessions-explicit-crash.db",
        output_path="target/mvp/sessions-explicit-crash.txt",
    )
    _append_ps1_explicit_crash_output_errors(
        errors,
        ctx,
        action="report",
        name="mvp-wrapper-ps1-report-sessions-explicit-crash-json",
        task_id="task-wrapper-sessions-explicit-crash",
        db_path="target/mvp/sessions-explicit-crash.db",
    )
    _append_ps1_sessions_explicit_crash_json_errors(errors, ctx)


def append_wrapper_ps1_explicit_crash_errors(
    errors: list[str],
    *,
    python_executable: str,
    assert_command_json_result: JsonCallable,
    assert_run_json_result: JsonCallable,
) -> None:
    ctx = Ps1ExplicitCrashContext(
        python_executable=python_executable,
        assert_command_json_result=assert_command_json_result,
        assert_run_json_result=assert_run_json_result,
    )
    _append_status_explicit_crash_errors(errors, ctx)
    _append_report_explicit_crash_errors(errors, ctx)
    _append_session_explicit_crash_errors(errors, ctx)
    _append_sessions_explicit_crash_errors(errors, ctx)
