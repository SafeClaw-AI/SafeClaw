from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


JsonCallable = Callable[..., Any]
_UNCERTAIN_OUTPUT_FRAGMENTS = (
    "QueueForManualReview",
    "worker=Uncertain",
    "effect=Uncertain",
)
_STATUS_REPORT_SESSION_CRASH_TASK_ID = "task-wrapper-report-session-crash"
_STATUS_REPORT_SESSION_CRASH_DB_PATH = "target/mvp/report-session-crash.db"
_STATUS_REPORT_SESSION_CRASH_OUTPUT_PATH = "target/mvp/report-session-crash.txt"
_RECOVER_CMD_RECOVER_TASK_ID = "task-wrapper-recover-session-crash"
_RECOVER_CMD_RECOVER_DB_PATH = "target/mvp/recover-session-crash.db"
_RECOVER_CMD_RECOVER_OUTPUT_PATH = "target/mvp/recover-session-crash.txt"
_RECOVER_CMD_RECOVER_DB_SNAPSHOT_PATH = (
    "target/mvp/recover-session-crash.seed-snapshot.db"
)
_RECOVER_CMD_RECOVER_OUTPUT_SNAPSHOT_PATH = (
    "target/mvp/recover-session-crash.seed-snapshot.txt"
)
_RECOVER_CMD_RECOVER_SESSION_PATH = Path("target/mvp/last_session.json")
_RECOVER_CMD_RECOVER_SESSION_SNAPSHOT_PATH = Path(
    "target/mvp/recover-session-crash.seed-snapshot.session.json"
)
_RETRY_REPORT_OUTPUT_FRAGMENTS = (
    "RetryEligible",
    "worker=Failed",
    "effect=Prepared",
)
_RETRY_CMD_RETRY_TASK_ID = "task-wrapper-retry-session"
_RETRY_CMD_RETRY_DB_PATH = "target/mvp/retry-session.db"
_RETRY_CMD_RETRY_OUTPUT_PATH = "target/mvp/retry-session.txt"
_RETRY_CMD_RETRY_DB_SNAPSHOT_PATH = "target/mvp/retry-session.seed-snapshot.db"
_RETRY_CMD_RETRY_OUTPUT_SNAPSHOT_PATH = "target/mvp/retry-session.seed-snapshot.txt"
_RETRY_CMD_RETRY_SESSION_PATH = Path("target/mvp/last_session.json")
_RETRY_CMD_RETRY_SESSION_SNAPSHOT_PATH = Path(
    "target/mvp/retry-session.seed-snapshot.session.json"
)
_RECOVER_OUTPUT_FRAGMENTS = (
    "recover blocked before expiry => true",
    "recover result => from=Uncertain",
    "worker=Succeeded",
    "effect=Executed",
    "completed=true",
)
_RETRY_OUTPUT_FRAGMENTS = (
    "retry blocked before expiry => true",
    "worker=Succeeded",
    "effect=Executed",
    "completed=true",
)


@dataclass(frozen=True)
class SessionCrashContext:
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


def _copy_fixture_file(source_path: str, target_path: str) -> None:
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target)


def _append_seed_json_errors(
    errors: list[str],
    ctx: SessionCrashContext,
    *,
    seed_action: str,
    name: str,
    task_id: str,
    db_path: str,
    output_path: str,
) -> None:
    result = ctx.assert_command_json_result(
        [
            ctx.python_executable,
            "tools/mvp/safeclaw_mvp.py",
            seed_action,
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
        seed_action,
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


def _append_command_session_errors(
    errors: list[str],
    ctx: SessionCrashContext,
    *,
    command: list[str],
    name: str,
    action: str,
    task_id: str,
    task_presence: str,
    required_output_fragments: tuple[str, ...],
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
    if _append_task_presence_error(
        errors,
        name=name,
        task_id=task_id,
        task_presence=task_presence,
        prepared=prepared,
        captured_output=captured_output,
    ):
        return
    if _append_required_output_fragment_error(
        errors,
        name=name,
        required_output_fragments=required_output_fragments,
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
    _append_source_hints_errors(
        errors,
        name=name,
        source_hints=source_hints,
        expected_db=expected_source_hints_db,
        expected_task_context=expected_source_hints_task_context,
    )


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


def _append_task_presence_error(
    errors: list[str],
    *,
    name: str,
    task_id: str,
    task_presence: str,
    prepared: list[Any],
    captured_output: str,
) -> bool:
    if task_presence == "captured_output":
        if task_id not in captured_output:
            errors.append(f"{name} missing captured task {task_id}")
            return True
        return False
    if task_id not in prepared:
        errors.append(f"{name} missing prepared task {task_id}")
        return True
    return False


def _append_required_output_fragment_error(
    errors: list[str],
    *,
    name: str,
    required_output_fragments: tuple[str, ...],
    captured_output: str,
) -> bool:
    for fragment in required_output_fragments:
        if fragment not in captured_output:
            errors.append(f"{name} missing {fragment}")
            return True
    return False


def _append_source_hints_errors(
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


def _append_targeted_ps1_report_errors(
    errors: list[str],
    ctx: SessionCrashContext,
    *,
    name: str,
    task_id: str,
    db_path: str,
    required_output_fragments: tuple[str, ...],
) -> None:
    _append_command_session_errors(
        errors,
        ctx,
        command=_build_ps1_command("report", db_path=db_path, task_id=task_id),
        name=name,
        action="report",
        task_id=task_id,
        task_presence="captured_output",
        required_output_fragments=required_output_fragments,
        expected_source_hints_db="flag",
        expected_source_hints_task_context="flag",
    )


def _append_ps1_session_action_errors(
    errors: list[str],
    ctx: SessionCrashContext,
    *,
    action: str,
    name: str,
    task_id: str,
    task_presence: str,
    required_output_fragments: tuple[str, ...],
) -> None:
    _append_command_session_errors(
        errors,
        ctx,
        command=_build_ps1_command(action),
        name=name,
        action=action,
        task_id=task_id,
        task_presence=task_presence,
        required_output_fragments=required_output_fragments,
        expected_source_hints_db="session",
        expected_source_hints_task_context="session",
    )


def _append_cmd_session_action_errors(
    errors: list[str],
    ctx: SessionCrashContext,
    *,
    action: str,
    name: str,
    task_id: str,
    required_output_fragments: tuple[str, ...],
) -> None:
    _append_command_session_errors(
        errors,
        ctx,
        command=_build_cmd_command(action),
        name=name,
        action=action,
        task_id=task_id,
        task_presence="prepared",
        required_output_fragments=required_output_fragments,
        expected_source_hints_db="session",
        expected_source_hints_task_context="session",
    )


def _append_status_session_crash_errors(
    errors: list[str],
    ctx: SessionCrashContext,
) -> None:
    _append_targeted_ps1_report_errors(
        errors,
        ctx,
        name="mvp-wrapper-ps1-report-status-session-crash-json",
        task_id=_STATUS_REPORT_SESSION_CRASH_TASK_ID,
        db_path=_STATUS_REPORT_SESSION_CRASH_DB_PATH,
        required_output_fragments=_UNCERTAIN_OUTPUT_FRAGMENTS,
    )
    _append_ps1_session_action_errors(
        errors,
        ctx,
        action="status",
        name="mvp-wrapper-ps1-status-session-crash-json",
        task_id=_STATUS_REPORT_SESSION_CRASH_TASK_ID,
        task_presence="captured_output",
        required_output_fragments=_UNCERTAIN_OUTPUT_FRAGMENTS,
    )


def _append_status_report_session_crash_seed_errors(
    errors: list[str],
    ctx: SessionCrashContext,
) -> None:
    _append_seed_json_errors(
        errors,
        ctx,
        seed_action="seed-crash",
        name="mvp-wrapper-report-session-crash-seed-json",
        task_id=_STATUS_REPORT_SESSION_CRASH_TASK_ID,
        db_path=_STATUS_REPORT_SESSION_CRASH_DB_PATH,
        output_path=_STATUS_REPORT_SESSION_CRASH_OUTPUT_PATH,
    )


def _append_report_session_crash_errors(
    errors: list[str],
    ctx: SessionCrashContext,
) -> None:
    _append_targeted_ps1_report_errors(
        errors,
        ctx,
        name="mvp-wrapper-ps1-report-report-session-crash-json",
        task_id=_STATUS_REPORT_SESSION_CRASH_TASK_ID,
        db_path=_STATUS_REPORT_SESSION_CRASH_DB_PATH,
        required_output_fragments=_UNCERTAIN_OUTPUT_FRAGMENTS,
    )
    _append_ps1_session_action_errors(
        errors,
        ctx,
        action="report",
        name="mvp-wrapper-ps1-report-session-crash-json",
        task_id=_STATUS_REPORT_SESSION_CRASH_TASK_ID,
        task_presence="captured_output",
        required_output_fragments=_UNCERTAIN_OUTPUT_FRAGMENTS,
    )


def _append_recover_session_crash_errors(
    errors: list[str],
    ctx: SessionCrashContext,
) -> None:
    task_id = _RECOVER_CMD_RECOVER_TASK_ID
    db_path = _RECOVER_CMD_RECOVER_DB_PATH
    _append_seed_json_errors(
        errors,
        ctx,
        seed_action="seed-crash",
        name="mvp-wrapper-recover-session-crash-seed-json",
        task_id=task_id,
        db_path=db_path,
        output_path=_RECOVER_CMD_RECOVER_OUTPUT_PATH,
    )
    _capture_recover_cmd_recover_seed_snapshot(
        errors,
        label="mvp-wrapper-recover-session-crash-seed-json",
    )
    _append_targeted_ps1_report_errors(
        errors,
        ctx,
        name="mvp-wrapper-ps1-report-recover-session-crash-json",
        task_id=task_id,
        db_path=db_path,
        required_output_fragments=_UNCERTAIN_OUTPUT_FRAGMENTS,
    )
    _append_ps1_session_action_errors(
        errors,
        ctx,
        action="recover",
        name="mvp-wrapper-ps1-recover-session-crash-json",
        task_id=task_id,
        task_presence="prepared",
        required_output_fragments=_RECOVER_OUTPUT_FRAGMENTS,
    )


def _capture_recover_cmd_recover_seed_snapshot(
    errors: list[str],
    *,
    label: str,
) -> None:
    output_path = Path(_RECOVER_CMD_RECOVER_OUTPUT_PATH)
    output_snapshot_path = Path(_RECOVER_CMD_RECOVER_OUTPUT_SNAPSHOT_PATH)
    try:
        _copy_fixture_file(
            _RECOVER_CMD_RECOVER_DB_PATH,
            _RECOVER_CMD_RECOVER_DB_SNAPSHOT_PATH,
        )
        if output_path.exists():
            _copy_fixture_file(
                _RECOVER_CMD_RECOVER_OUTPUT_PATH,
                _RECOVER_CMD_RECOVER_OUTPUT_SNAPSHOT_PATH,
            )
        elif output_snapshot_path.exists():
            output_snapshot_path.unlink()
        if _RECOVER_CMD_RECOVER_SESSION_PATH.exists():
            _copy_fixture_file(
                str(_RECOVER_CMD_RECOVER_SESSION_PATH),
                str(_RECOVER_CMD_RECOVER_SESSION_SNAPSHOT_PATH),
            )
        elif _RECOVER_CMD_RECOVER_SESSION_SNAPSHOT_PATH.exists():
            _RECOVER_CMD_RECOVER_SESSION_SNAPSHOT_PATH.unlink()
    except FileNotFoundError as error:
        errors.append(f"{label} missing seeded fixture for snapshot: {error}")
    except OSError as error:
        errors.append(f"{label} failed to snapshot seeded fixture: {error}")


def _restore_recover_cmd_recover_seed_snapshot(
    errors: list[str],
    *,
    label: str,
) -> None:
    output_path = Path(_RECOVER_CMD_RECOVER_OUTPUT_PATH)
    output_snapshot_path = Path(_RECOVER_CMD_RECOVER_OUTPUT_SNAPSHOT_PATH)
    try:
        _copy_fixture_file(
            _RECOVER_CMD_RECOVER_DB_SNAPSHOT_PATH,
            _RECOVER_CMD_RECOVER_DB_PATH,
        )
        if output_snapshot_path.exists():
            _copy_fixture_file(
                _RECOVER_CMD_RECOVER_OUTPUT_SNAPSHOT_PATH,
                _RECOVER_CMD_RECOVER_OUTPUT_PATH,
            )
        elif output_path.exists():
            output_path.unlink()
        if _RECOVER_CMD_RECOVER_SESSION_SNAPSHOT_PATH.exists():
            _copy_fixture_file(
                str(_RECOVER_CMD_RECOVER_SESSION_SNAPSHOT_PATH),
                str(_RECOVER_CMD_RECOVER_SESSION_PATH),
            )
        elif _RECOVER_CMD_RECOVER_SESSION_PATH.exists():
            _RECOVER_CMD_RECOVER_SESSION_PATH.unlink()
    except FileNotFoundError as error:
        errors.append(f"{label} missing saved seed snapshot for restore: {error}")
    except OSError as error:
        errors.append(f"{label} failed to restore seed snapshot: {error}")


def _append_cmd_recover_session_crash_errors(
    errors: list[str],
    ctx: SessionCrashContext,
) -> None:
    task_id = _RECOVER_CMD_RECOVER_TASK_ID
    db_path = _RECOVER_CMD_RECOVER_DB_PATH
    _restore_recover_cmd_recover_seed_snapshot(
        errors,
        label="mvp-wrapper-cmd-recover-session-crash-seed-json",
    )
    _append_targeted_ps1_report_errors(
        errors,
        ctx,
        name="mvp-wrapper-ps1-report-cmd-recover-session-crash-json",
        task_id=task_id,
        db_path=db_path,
        required_output_fragments=_UNCERTAIN_OUTPUT_FRAGMENTS,
    )
    _append_cmd_session_action_errors(
        errors,
        ctx,
        action="recover",
        name="mvp-wrapper-cmd-recover-session-crash-json",
        task_id=task_id,
        required_output_fragments=_RECOVER_OUTPUT_FRAGMENTS,
    )


def _append_retry_session_errors(
    errors: list[str],
    ctx: SessionCrashContext,
) -> None:
    _append_targeted_ps1_report_errors(
        errors,
        ctx,
        name="mvp-wrapper-ps1-report-retry-session-json",
        task_id=_RETRY_CMD_RETRY_TASK_ID,
        db_path=_RETRY_CMD_RETRY_DB_PATH,
        required_output_fragments=_RETRY_REPORT_OUTPUT_FRAGMENTS,
    )
    _append_ps1_session_action_errors(
        errors,
        ctx,
        action="retry",
        name="mvp-wrapper-ps1-retry-session-json",
        task_id=_RETRY_CMD_RETRY_TASK_ID,
        task_presence="prepared",
        required_output_fragments=_RETRY_OUTPUT_FRAGMENTS,
    )


def _append_retry_cmd_retry_seed_errors(
    errors: list[str],
    ctx: SessionCrashContext,
) -> None:
    _append_seed_json_errors(
        errors,
        ctx,
        seed_action="seed-failed",
        name="mvp-wrapper-retry-session-seed-failed-json",
        task_id=_RETRY_CMD_RETRY_TASK_ID,
        db_path=_RETRY_CMD_RETRY_DB_PATH,
        output_path=_RETRY_CMD_RETRY_OUTPUT_PATH,
    )
    _capture_retry_cmd_retry_seed_snapshot(
        errors,
        label="mvp-wrapper-retry-session-seed-failed-json",
    )


def _capture_retry_cmd_retry_seed_snapshot(
    errors: list[str],
    *,
    label: str,
) -> None:
    output_path = Path(_RETRY_CMD_RETRY_OUTPUT_PATH)
    output_snapshot_path = Path(_RETRY_CMD_RETRY_OUTPUT_SNAPSHOT_PATH)
    try:
        _copy_fixture_file(_RETRY_CMD_RETRY_DB_PATH, _RETRY_CMD_RETRY_DB_SNAPSHOT_PATH)
        if output_path.exists():
            _copy_fixture_file(
                _RETRY_CMD_RETRY_OUTPUT_PATH,
                _RETRY_CMD_RETRY_OUTPUT_SNAPSHOT_PATH,
            )
        elif output_snapshot_path.exists():
            output_snapshot_path.unlink()
        if _RETRY_CMD_RETRY_SESSION_PATH.exists():
            _copy_fixture_file(
                str(_RETRY_CMD_RETRY_SESSION_PATH),
                str(_RETRY_CMD_RETRY_SESSION_SNAPSHOT_PATH),
            )
        elif _RETRY_CMD_RETRY_SESSION_SNAPSHOT_PATH.exists():
            _RETRY_CMD_RETRY_SESSION_SNAPSHOT_PATH.unlink()
    except FileNotFoundError as error:
        errors.append(f"{label} missing seeded fixture for snapshot: {error}")
    except OSError as error:
        errors.append(f"{label} failed to snapshot seeded fixture: {error}")


def _restore_retry_cmd_retry_seed_snapshot(
    errors: list[str],
    *,
    label: str,
) -> None:
    output_path = Path(_RETRY_CMD_RETRY_OUTPUT_PATH)
    output_snapshot_path = Path(_RETRY_CMD_RETRY_OUTPUT_SNAPSHOT_PATH)
    try:
        _copy_fixture_file(_RETRY_CMD_RETRY_DB_SNAPSHOT_PATH, _RETRY_CMD_RETRY_DB_PATH)
        if output_snapshot_path.exists():
            _copy_fixture_file(
                _RETRY_CMD_RETRY_OUTPUT_SNAPSHOT_PATH,
                _RETRY_CMD_RETRY_OUTPUT_PATH,
            )
        elif output_path.exists():
            output_path.unlink()
        if _RETRY_CMD_RETRY_SESSION_SNAPSHOT_PATH.exists():
            _copy_fixture_file(
                str(_RETRY_CMD_RETRY_SESSION_SNAPSHOT_PATH),
                str(_RETRY_CMD_RETRY_SESSION_PATH),
            )
        elif _RETRY_CMD_RETRY_SESSION_PATH.exists():
            _RETRY_CMD_RETRY_SESSION_PATH.unlink()
    except FileNotFoundError as error:
        errors.append(f"{label} missing saved seed snapshot for restore: {error}")
    except OSError as error:
        errors.append(f"{label} failed to restore seed snapshot: {error}")


def _append_cmd_retry_session_errors(
    errors: list[str],
    ctx: SessionCrashContext,
) -> None:
    _restore_retry_cmd_retry_seed_snapshot(
        errors,
        label="mvp-wrapper-cmd-retry-session-seed-json",
    )
    _append_targeted_ps1_report_errors(
        errors,
        ctx,
        name="mvp-wrapper-ps1-report-cmd-retry-session-json",
        task_id=_RETRY_CMD_RETRY_TASK_ID,
        db_path=_RETRY_CMD_RETRY_DB_PATH,
        required_output_fragments=_RETRY_REPORT_OUTPUT_FRAGMENTS,
    )
    _append_cmd_session_action_errors(
        errors,
        ctx,
        action="retry",
        name="mvp-wrapper-cmd-retry-session-json",
        task_id=_RETRY_CMD_RETRY_TASK_ID,
        required_output_fragments=_RETRY_OUTPUT_FRAGMENTS,
    )


def append_wrapper_session_crash_errors(
    errors: list[str],
    *,
    python_executable: str,
    assert_command_json_result: JsonCallable,
    assert_run_json_result: JsonCallable,
) -> None:
    ctx = SessionCrashContext(
        python_executable=python_executable,
        assert_command_json_result=assert_command_json_result,
        assert_run_json_result=assert_run_json_result,
    )
    _append_status_report_session_crash_seed_errors(errors, ctx)
    _append_status_session_crash_errors(errors, ctx)
    _append_report_session_crash_errors(errors, ctx)
    _append_recover_session_crash_errors(errors, ctx)
    _append_cmd_recover_session_crash_errors(errors, ctx)
    _append_retry_cmd_retry_seed_errors(errors, ctx)
    _append_retry_session_errors(errors, ctx)
    _append_cmd_retry_session_errors(errors, ctx)
