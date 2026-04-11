from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


JsonCallable = Callable[..., Any]
AssertionCallable = Callable[..., Any]

_TASK_ID = "task-wrapper-service-reconcile-json"
_DB_PATH = "target/mvp/service-reconcile-json.db"
_OUTPUT_PATH = "target/mvp/service-reconcile-json.txt"
_DB_SNAPSHOT_PATH = "target/mvp/service-reconcile-json.seed-snapshot.db"
_OUTPUT_SNAPSHOT_PATH = "target/mvp/service-reconcile-json.seed-snapshot.txt"
_EXPECTED_DB = r"target\mvp\service-reconcile-json.db"
_SEED_LABEL = "mvp-wrapper-service-reconcile-seed-crash-json"
_STATUS_TEXT_LABEL = "mvp-wrapper-service-reconcile-status-before"
_STATUS_JSON_LABEL = "mvp-wrapper-service-reconcile-status-before-json"
_CMD_LABEL = "mvp-wrapper-cmd-service-reconcile-json"
_PS1_SEED_LABEL = "mvp-wrapper-service-reconcile-json-seed-crash-ps1-json"
_PS1_LABEL = "mvp-wrapper-ps1-service-reconcile-json"
_COORDINATION_SUMMARY = "reconcile_self_before_scope_write"
_COORDINATION_REASON = "self_executed_assumed_scope_quarantine"
_NEXT_REASON = "executed_assumed_requires_reconcile"
_EXECUTED_COMMAND = (
    'safeclaw.cmd service-reconcile --db "target/mvp/service-reconcile-json.db" '
    '--task-id "task-wrapper-service-reconcile-json" --decision executed '
    "--limit 1 --report"
)
_NOT_EXECUTED_COMMAND = (
    'safeclaw.cmd service-reconcile --db "target/mvp/service-reconcile-json.db" '
    '--task-id "task-wrapper-service-reconcile-json" --decision not-executed '
    "--limit 1 --report"
)


@dataclass(frozen=True)
class ServiceReconcileSuccessContext:
    repo_root: Path
    python_executable: str
    subprocess_module: Any
    assert_command_json_result: JsonCallable
    assert_run_json_result: AssertionCallable
    assert_service_reconcile_json_result: AssertionCallable


def _python_command(python_executable: str, *args: str) -> list[str]:
    return [python_executable, "tools/mvp/safeclaw_mvp.py", *args]


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


def _copy_fixture_file(source_path: str, target_path: str) -> None:
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target)


def _capture_seed_snapshot(errors: list[str], *, label: str) -> None:
    try:
        _copy_fixture_file(_DB_PATH, _DB_SNAPSHOT_PATH)
        output_path = Path(_OUTPUT_PATH)
        output_snapshot_path = Path(_OUTPUT_SNAPSHOT_PATH)
        if output_path.exists():
            _copy_fixture_file(_OUTPUT_PATH, _OUTPUT_SNAPSHOT_PATH)
        elif output_snapshot_path.exists():
            output_snapshot_path.unlink()
    except FileNotFoundError as error:
        errors.append(f"{label} missing seeded fixture for snapshot: {error}")
    except OSError as error:
        errors.append(f"{label} failed to snapshot seeded fixture: {error}")


def _restore_seed_snapshot(errors: list[str], *, label: str) -> None:
    try:
        _copy_fixture_file(_DB_SNAPSHOT_PATH, _DB_PATH)
        output_path = Path(_OUTPUT_PATH)
        output_snapshot_path = Path(_OUTPUT_SNAPSHOT_PATH)
        if output_snapshot_path.exists():
            _copy_fixture_file(_OUTPUT_SNAPSHOT_PATH, _OUTPUT_PATH)
        elif output_path.exists():
            output_path.unlink()
    except FileNotFoundError as error:
        errors.append(f"{label} missing saved seed snapshot for restore: {error}")
    except OSError as error:
        errors.append(f"{label} failed to restore seed snapshot: {error}")


def _append_seed_json_errors(
    errors: list[str],
    ctx: ServiceReconcileSuccessContext,
    *,
    label: str,
) -> None:
    result = ctx.assert_command_json_result(
        _python_command(
            ctx.python_executable,
            "seed-crash",
            "--reset",
            "--probe-mode",
            "none",
            "--task-id",
            _TASK_ID,
            "--db",
            _DB_PATH,
            "--output",
            _OUTPUT_PATH,
            "--json",
        ),
        errors,
        label,
        "seed-crash",
    )
    ctx.assert_run_json_result(
        result,
        errors,
        label,
        expected_task_id=_TASK_ID,
        expected_db_path=_DB_PATH,
        expected_output_path=_OUTPUT_PATH,
        expected_db_source="flag",
        expected_output_source="flag",
    )
    if result is not None:
        _capture_seed_snapshot(errors, label=label)


def _append_restore_seed_errors(errors: list[str], *, label: str) -> None:
    # Reuse the executed-assumed base before the slower PowerShell wrapper path.
    _restore_seed_snapshot(errors, label=label)


def _append_status_before_text_errors(
    errors: list[str],
    ctx: ServiceReconcileSuccessContext,
) -> None:
    wrapper_service_status_reconcile = ctx.subprocess_module.run(
        _python_command(
            ctx.python_executable,
            "service-status",
            "--db",
            _DB_PATH,
            "--limit",
            "1",
        ),
        cwd=ctx.repo_root,
        capture_output=True,
        text=True,
    )

    output = (wrapper_service_status_reconcile.stdout or "") + (
        wrapper_service_status_reconcile.stderr or ""
    )

    if wrapper_service_status_reconcile.returncode != 0:
        errors.append(
            f"{_STATUS_TEXT_LABEL} failed: exit={wrapper_service_status_reconcile.returncode}"
        )
        return

    if (
        "[mvp-wrapper] service coordination => status=quarantined "
        f"reason={_COORDINATION_REASON} summary={_COORDINATION_SUMMARY} task={_TASK_ID}"
        not in output
    ):
        errors.append(
            "mvp-wrapper-service-reconcile-status-before missing self quarantine coordination summary"
        )
        return

    if (
        "next=inspect "
        f"next_reason={_NEXT_REASON} blocker=scope_quarantine coordination=quarantined "
        f"coordination_reason={_COORDINATION_REASON} coordination_summary={_COORDINATION_SUMMARY}"
        not in output
    ):
        errors.append(
            "mvp-wrapper-service-reconcile-status-before missing reconcile next hint"
        )
        return

    if (
        f"[mvp-wrapper] service recent[0] reconcile => executed={_EXECUTED_COMMAND} "
        f"not_executed={_NOT_EXECUTED_COMMAND}"
        not in output
    ):
        errors.append(
            "mvp-wrapper-service-reconcile-status-before missing reconcile command choices"
        )


def _append_status_before_json_errors(
    errors: list[str],
    ctx: ServiceReconcileSuccessContext,
) -> None:
    result = ctx.assert_command_json_result(
        _python_command(
            ctx.python_executable,
            "service-status",
            "--db",
            _DB_PATH,
            "--limit",
            "1",
            "--json",
        ),
        errors,
        _STATUS_JSON_LABEL,
        "service-status",
    )
    if result is None:
        return

    if not _validate_status_before_coordination(
        errors,
        result.get("current_session"),
        result.get("coordination"),
    ):
        return

    recent_task = _extract_status_before_recent_task(errors, result.get("recent_tasks"))
    if recent_task is None:
        return

    if not _validate_status_before_recent_task(errors, recent_task):
        return

    _validate_status_before_reconcile_commands(errors, recent_task)


def _validate_status_before_coordination(
    errors: list[str],
    current_session: Any,
    coordination: Any,
) -> bool:
    if not isinstance(current_session, dict) or current_session.get("task_id") != _TASK_ID:
        errors.append(
            "mvp-wrapper-service-reconcile-status-before-json missing current_session task-wrapper-service-reconcile-json"
        )
        return False

    coordination_dict = coordination if isinstance(coordination, dict) else {}
    expectations = (
        (
            "status",
            "quarantined",
            "mvp-wrapper-service-reconcile-status-before-json missing coordination.status=quarantined",
        ),
        (
            "reason",
            _COORDINATION_REASON,
            "mvp-wrapper-service-reconcile-status-before-json missing coordination.reason=self_executed_assumed_scope_quarantine",
        ),
        (
            "summary",
            _COORDINATION_SUMMARY,
            "mvp-wrapper-service-reconcile-status-before-json missing coordination.summary=reconcile_self_before_scope_write",
        ),
        (
            "scope_quarantine_active",
            True,
            "mvp-wrapper-service-reconcile-status-before-json missing coordination.scope_quarantine_active=true",
        ),
        (
            "scope_quarantine_source",
            "self",
            "mvp-wrapper-service-reconcile-status-before-json missing coordination.scope_quarantine_source=self",
        ),
        (
            "scope_quarantine_task_id",
            _TASK_ID,
            "mvp-wrapper-service-reconcile-status-before-json missing coordination.scope_quarantine_task_id=task-wrapper-service-reconcile-json",
        ),
        (
            "next_task_id",
            _TASK_ID,
            "mvp-wrapper-service-reconcile-status-before-json missing coordination.next_task_id=task-wrapper-service-reconcile-json",
        ),
    )
    return _append_first_mismatch(errors, coordination_dict, expectations)


def _extract_status_before_recent_task(
    errors: list[str],
    recent_tasks: Any,
) -> dict[str, Any] | None:
    if not isinstance(recent_tasks, list) or not recent_tasks:
        errors.append(
            "mvp-wrapper-service-reconcile-status-before-json missing recent task"
        )
        return None

    recent_task = recent_tasks[0]
    if not isinstance(recent_task, dict):
        errors.append(
            "mvp-wrapper-service-reconcile-status-before-json missing recent task task-wrapper-service-reconcile-json"
        )
        return None

    return recent_task


def _validate_status_before_recent_task(
    errors: list[str],
    recent_task: dict[str, Any],
) -> bool:
    expectations = (
        (
            "task_id",
            _TASK_ID,
            "mvp-wrapper-service-reconcile-status-before-json missing recent task task-wrapper-service-reconcile-json",
        ),
        (
            "next_action",
            "inspect",
            "mvp-wrapper-service-reconcile-status-before-json missing next_action=inspect",
        ),
        (
            "next_reason",
            _NEXT_REASON,
            "mvp-wrapper-service-reconcile-status-before-json missing next_reason=executed_assumed_requires_reconcile",
        ),
        (
            "next_blocker",
            "scope_quarantine",
            "mvp-wrapper-service-reconcile-status-before-json missing next_blocker=scope_quarantine",
        ),
        (
            "next_task_id",
            _TASK_ID,
            "mvp-wrapper-service-reconcile-status-before-json missing next_task_id=task-wrapper-service-reconcile-json",
        ),
    )
    return _append_first_mismatch(errors, recent_task, expectations)


def _validate_status_before_reconcile_commands(
    errors: list[str],
    recent_task: dict[str, Any],
) -> None:
    reconcile_commands = recent_task.get("reconcile_commands")
    if not isinstance(reconcile_commands, dict):
        errors.append(
            "mvp-wrapper-service-reconcile-status-before-json missing reconcile_commands object"
        )
        return

    _append_first_mismatch(
        errors,
        reconcile_commands,
        (
            (
                "executed",
                _EXECUTED_COMMAND,
                "mvp-wrapper-service-reconcile-status-before-json missing reconcile_commands.executed",
            ),
            (
                "not_executed",
                _NOT_EXECUTED_COMMAND,
                "mvp-wrapper-service-reconcile-status-before-json missing reconcile_commands.not_executed",
            ),
        ),
    )


def _append_first_mismatch(
    errors: list[str],
    payload: dict[str, Any],
    expectations: tuple[tuple[str, Any, str], ...],
) -> bool:
    for key, expected, message in expectations:
        if payload.get(key) != expected:
            errors.append(message)
            return False
    return True


def _append_cmd_service_reconcile_json_errors(
    errors: list[str],
    ctx: ServiceReconcileSuccessContext,
) -> None:
    result = ctx.assert_command_json_result(
        _cmd_command(
            "service-reconcile",
            "--db",
            _DB_PATH,
            "--task-id",
            _TASK_ID,
            "--decision",
            "executed",
            "--limit",
            "1",
            "--report",
            "--json",
        ),
        errors,
        _CMD_LABEL,
        "service-reconcile",
    )
    ctx.assert_service_reconcile_json_result(
        result,
        errors,
        _CMD_LABEL,
        expected_db=_EXPECTED_DB,
        expected_db_source="flag",
        expected_task_id=_TASK_ID,
        expected_limit=1,
        expected_decision="executed",
        expected_steps=["reconcile", "service-status", "report"],
        expect_report_payload=True,
    )


def _append_ps1_service_reconcile_json_errors(
    errors: list[str],
    ctx: ServiceReconcileSuccessContext,
) -> None:
    result = ctx.assert_command_json_result(
        _ps1_command(
            "service-reconcile",
            "--db",
            _DB_PATH,
            "--task-id",
            _TASK_ID,
            "--decision",
            "executed",
            "--limit",
            "1",
            "--json",
        ),
        errors,
        _PS1_LABEL,
        "service-reconcile",
    )
    ctx.assert_service_reconcile_json_result(
        result,
        errors,
        _PS1_LABEL,
        expected_db=_EXPECTED_DB,
        expected_db_source="flag",
        expected_task_id=_TASK_ID,
        expected_limit=1,
        expected_decision="executed",
    )


def append_wrapper_service_reconcile_success_errors(
    errors: list[str],
    *,
    repo_root: Path,
    python_executable: str,
    subprocess_module: Any,
    assert_command_json_result: JsonCallable,
    assert_run_json_result: AssertionCallable,
    assert_service_reconcile_json_result: AssertionCallable,
) -> None:
    ctx = ServiceReconcileSuccessContext(
        repo_root=repo_root,
        python_executable=python_executable,
        subprocess_module=subprocess_module,
        assert_command_json_result=assert_command_json_result,
        assert_run_json_result=assert_run_json_result,
        assert_service_reconcile_json_result=assert_service_reconcile_json_result,
    )
    _append_seed_json_errors(errors, ctx, label=_SEED_LABEL)
    _append_status_before_text_errors(errors, ctx)
    _append_status_before_json_errors(errors, ctx)
    _append_cmd_service_reconcile_json_errors(errors, ctx)
    _append_restore_seed_errors(errors, label=_PS1_SEED_LABEL)
    _append_ps1_service_reconcile_json_errors(errors, ctx)
