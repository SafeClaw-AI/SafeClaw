from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


JsonCallable = Callable[..., Any]
_RETRY_REPORT_TASK_ID = "task-wrapper-service-retry-report-json"
_RETRY_REPORT_DB_PATH = "target/mvp/service-retry-report-json.db"
_RETRY_REPORT_OUTPUT_PATH = "target/mvp/service-retry-report-json.txt"
_RETRY_REPORT_DB_SNAPSHOT_PATH = "target/mvp/service-retry-report-json.seed-snapshot.db"
_RETRY_REPORT_OUTPUT_SNAPSHOT_PATH = (
    "target/mvp/service-retry-report-json.seed-snapshot.txt"
)
_RETRY_REPORT_EXPECTED_DB = r"target\mvp\service-retry-report-json.db"
_RETRY_REPORT_STEPS = ("retry", "service-status", "report")


@dataclass(frozen=True)
class ServiceRetryReportOperation:
    operation_kind: str
    name: str
    command_kind: str | None = None


@dataclass(frozen=True)
class ServiceRetryReportContext:
    python_executable: str
    assert_command_json_result: JsonCallable
    assert_run_json_result: JsonCallable
    assert_service_retry_json_result: JsonCallable


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


def _capture_seed_snapshot(errors: list[str], *, operation_name: str) -> None:
    try:
        _copy_fixture_file(_RETRY_REPORT_DB_PATH, _RETRY_REPORT_DB_SNAPSHOT_PATH)
        output_path = Path(_RETRY_REPORT_OUTPUT_PATH)
        output_snapshot_path = Path(_RETRY_REPORT_OUTPUT_SNAPSHOT_PATH)
        if output_path.exists():
            _copy_fixture_file(
                _RETRY_REPORT_OUTPUT_PATH,
                _RETRY_REPORT_OUTPUT_SNAPSHOT_PATH,
            )
        elif output_snapshot_path.exists():
            output_snapshot_path.unlink()
    except FileNotFoundError as error:
        errors.append(
            f"{operation_name} missing seeded fixture for snapshot: {error}"
        )
    except OSError as error:
        errors.append(f"{operation_name} failed to snapshot seeded fixture: {error}")


def _restore_seed_snapshot(errors: list[str], *, operation_name: str) -> None:
    try:
        _copy_fixture_file(_RETRY_REPORT_DB_SNAPSHOT_PATH, _RETRY_REPORT_DB_PATH)
        output_path = Path(_RETRY_REPORT_OUTPUT_PATH)
        output_snapshot_path = Path(_RETRY_REPORT_OUTPUT_SNAPSHOT_PATH)
        if output_snapshot_path.exists():
            _copy_fixture_file(
                _RETRY_REPORT_OUTPUT_SNAPSHOT_PATH,
                _RETRY_REPORT_OUTPUT_PATH,
            )
        elif output_path.exists():
            output_path.unlink()
    except FileNotFoundError as error:
        errors.append(
            f"{operation_name} missing saved seed snapshot for restore: {error}"
        )
    except OSError as error:
        errors.append(f"{operation_name} failed to restore seed snapshot: {error}")


def _append_seed_failed_json_case(
    errors: list[str],
    ctx: ServiceRetryReportContext,
    *,
    operation: ServiceRetryReportOperation,
) -> None:
    result = ctx.assert_command_json_result(
        [
            ctx.python_executable,
            "tools/mvp/safeclaw_mvp.py",
            "seed-failed",
            "--reset",
            "--task-id",
            _RETRY_REPORT_TASK_ID,
            "--db",
            _RETRY_REPORT_DB_PATH,
            "--output",
            _RETRY_REPORT_OUTPUT_PATH,
            "--json",
        ],
        errors,
        operation.name,
        "seed-failed",
    )
    ctx.assert_run_json_result(
        result,
        errors,
        operation.name,
        expected_task_id=_RETRY_REPORT_TASK_ID,
        expected_db_path=_RETRY_REPORT_DB_PATH,
        expected_output_path=_RETRY_REPORT_OUTPUT_PATH,
        expected_db_source="flag",
        expected_output_source="flag",
    )
    if result is not None:
        _capture_seed_snapshot(errors, operation_name=operation.name)


def _append_restore_seed_failed_case(
    errors: list[str],
    *,
    operation: ServiceRetryReportOperation,
) -> None:
    # Reuse the seeded fixture before the slower PowerShell wrapper path.
    _restore_seed_snapshot(errors, operation_name=operation.name)


def _append_service_retry_report_json_case(
    errors: list[str],
    ctx: ServiceRetryReportContext,
    *,
    operation: ServiceRetryReportOperation,
) -> None:
    if operation.command_kind == "cmd":
        command = _cmd_command(
            "service-retry",
            "--db",
            _RETRY_REPORT_DB_PATH,
            "--task-id",
            _RETRY_REPORT_TASK_ID,
            "--limit",
            "1",
            "--report",
            "--json",
        )
    else:
        command = _ps1_command(
            "service-retry",
            "--db",
            _RETRY_REPORT_DB_PATH,
            "--task-id",
            _RETRY_REPORT_TASK_ID,
            "--limit",
            "1",
            "--report",
            "--json",
        )
    result = ctx.assert_command_json_result(
        command,
        errors,
        operation.name,
        "service-retry",
    )
    ctx.assert_service_retry_json_result(
        result,
        errors,
        operation.name,
        expected_db=_RETRY_REPORT_EXPECTED_DB,
        expected_db_source="flag",
        expected_task_id=_RETRY_REPORT_TASK_ID,
        expected_limit=1,
        expected_steps=list(_RETRY_REPORT_STEPS),
        expect_report_payload=True,
    )


_SERVICE_RETRY_REPORT_OPERATIONS = (
    ServiceRetryReportOperation(
        operation_kind="seed",
        name="mvp-wrapper-service-retry-report-json-seed-failed-json",
    ),
    ServiceRetryReportOperation(
        operation_kind="command",
        command_kind="cmd",
        name="mvp-wrapper-cmd-service-retry-report-json",
    ),
    ServiceRetryReportOperation(
        operation_kind="restore",
        name="mvp-wrapper-service-retry-report-json-seed-failed-ps1-json",
    ),
    ServiceRetryReportOperation(
        operation_kind="command",
        command_kind="ps1",
        name="mvp-wrapper-ps1-service-retry-report-json",
    ),
)


def append_wrapper_service_retry_report_errors(
    errors: list[str],
    *,
    python_executable: str,
    assert_command_json_result: JsonCallable,
    assert_run_json_result: JsonCallable,
    assert_service_retry_json_result: JsonCallable,
) -> None:
    ctx = ServiceRetryReportContext(
        python_executable=python_executable,
        assert_command_json_result=assert_command_json_result,
        assert_run_json_result=assert_run_json_result,
        assert_service_retry_json_result=assert_service_retry_json_result,
    )
    for operation in _SERVICE_RETRY_REPORT_OPERATIONS:
        if operation.operation_kind == "seed":
            _append_seed_failed_json_case(errors, ctx, operation=operation)
        elif operation.operation_kind == "restore":
            _append_restore_seed_failed_case(
                errors,
                operation=operation,
            )
        else:
            _append_service_retry_report_json_case(
                errors,
                ctx,
                operation=operation,
            )
