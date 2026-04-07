from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


JsonCallable = Callable[..., Any]


@dataclass(frozen=True)
class Ps1ExplicitTargetingContext:
    python_executable: str
    assert_command_json_result: JsonCallable
    assert_run_json_result: JsonCallable


def _append_seed_json_errors(
    errors: list[str],
    ctx: Ps1ExplicitTargetingContext,
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


def _append_ps1_targeted_json_errors(
    errors: list[str],
    ctx: Ps1ExplicitTargetingContext,
    *,
    action: str,
    name: str,
    task_id: str,
    db_path: str,
    required_output_fragments: tuple[str, ...] = (),
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
        required_output_fragments=required_output_fragments,
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
    required_output_fragments: tuple[str, ...] = (),
) -> bool:
    if not prepared or prepared[0] != action:
        errors.append(f"{name} missing prepared {action}")
        return True
    if task_id not in captured_output:
        errors.append(f"{name} missing captured task {task_id}")
        return True
    for fragment in required_output_fragments:
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


def append_wrapper_ps1_explicit_targeting_errors(
    errors: list[str],
    *,
    python_executable: str,
    assert_command_json_result: JsonCallable,
    assert_run_json_result: JsonCallable,
) -> None:
    ctx = Ps1ExplicitTargetingContext(
        python_executable=python_executable,
        assert_command_json_result=assert_command_json_result,
        assert_run_json_result=assert_run_json_result,
    )
    _append_seed_json_errors(
        errors,
        ctx,
        seed_action="seed-failed",
        name="mvp-wrapper-retry-json-seed-failed-ps1-json",
        task_id="task-wrapper-retry-json",
        db_path="target/mvp/retry-json.db",
        output_path="target/mvp/retry-json.txt",
    )
    _append_ps1_targeted_json_errors(
        errors,
        ctx,
        action="retry",
        name="mvp-wrapper-ps1-retry-json",
        task_id="task-wrapper-retry-json",
        db_path="target/mvp/retry-json.db",
    )
    _append_seed_json_errors(
        errors,
        ctx,
        seed_action="seed-crash",
        name="mvp-wrapper-recover-json-seed-crash-ps1-json",
        task_id="task-wrapper-recover-json",
        db_path="target/mvp/recover-json.db",
        output_path="target/mvp/recover-json.txt",
    )
    for action, name in [
        ("recover", "mvp-wrapper-ps1-recover-json"),
        ("status", "mvp-wrapper-ps1-status-explicit-json"),
        ("report", "mvp-wrapper-ps1-report-explicit-json"),
    ]:
        _append_ps1_targeted_json_errors(
            errors,
            ctx,
            action=action,
            name=name,
            task_id="task-wrapper-recover-json",
            db_path="target/mvp/recover-json.db",
        )
