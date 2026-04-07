from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


JsonCallable = Callable[..., Any]
_RECOVER_REPORT_TASK_ID = "task-wrapper-service-recover-report-json"
_RECOVER_REPORT_DB_PATH = "target/mvp/service-recover-report-json.db"
_RECOVER_REPORT_OUTPUT_PATH = "target/mvp/service-recover-report-json.txt"
_RECOVER_REPORT_EXPECTED_DB = r"target\mvp\service-recover-report-json.db"
_RECOVER_REPORT_STEPS = ("recover", "service-status", "report")


@dataclass(frozen=True)
class ServiceRecoverReportOperation:
    operation_kind: str
    name: str
    command_kind: str | None = None


@dataclass(frozen=True)
class ServiceRecoverReportContext:
    python_executable: str
    assert_command_json_result: JsonCallable
    assert_run_json_result: JsonCallable
    assert_service_recover_json_result: JsonCallable


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


def _append_seed_crash_json_case(
    errors: list[str],
    ctx: ServiceRecoverReportContext,
    *,
    operation: ServiceRecoverReportOperation,
) -> None:
    result = ctx.assert_command_json_result(
        [
            ctx.python_executable,
            "tools/mvp/safeclaw_mvp.py",
            "seed-crash",
            "--reset",
            "--task-id",
            _RECOVER_REPORT_TASK_ID,
            "--db",
            _RECOVER_REPORT_DB_PATH,
            "--output",
            _RECOVER_REPORT_OUTPUT_PATH,
            "--json",
        ],
        errors,
        operation.name,
        "seed-crash",
    )
    ctx.assert_run_json_result(
        result,
        errors,
        operation.name,
        expected_task_id=_RECOVER_REPORT_TASK_ID,
        expected_db_path=_RECOVER_REPORT_DB_PATH,
        expected_output_path=_RECOVER_REPORT_OUTPUT_PATH,
        expected_db_source="flag",
        expected_output_source="flag",
    )


def _append_service_recover_report_json_case(
    errors: list[str],
    ctx: ServiceRecoverReportContext,
    *,
    operation: ServiceRecoverReportOperation,
) -> None:
    if operation.command_kind == "cmd":
        command = _cmd_command(
            "service-recover",
            "--db",
            _RECOVER_REPORT_DB_PATH,
            "--task-id",
            _RECOVER_REPORT_TASK_ID,
            "--limit",
            "1",
            "--report",
            "--json",
        )
    else:
        command = _ps1_command(
            "service-recover",
            "--db",
            _RECOVER_REPORT_DB_PATH,
            "--task-id",
            _RECOVER_REPORT_TASK_ID,
            "--limit",
            "1",
            "--report",
            "--json",
        )
    result = ctx.assert_command_json_result(
        command,
        errors,
        operation.name,
        "service-recover",
    )
    ctx.assert_service_recover_json_result(
        result,
        errors,
        operation.name,
        expected_db=_RECOVER_REPORT_EXPECTED_DB,
        expected_db_source="flag",
        expected_task_id=_RECOVER_REPORT_TASK_ID,
        expected_limit=1,
        expected_steps=list(_RECOVER_REPORT_STEPS),
        expect_report_payload=True,
    )


_SERVICE_RECOVER_REPORT_OPERATIONS = (
    ServiceRecoverReportOperation(
        operation_kind="seed",
        name="mvp-wrapper-service-recover-report-json-seed-crash-json",
    ),
    ServiceRecoverReportOperation(
        operation_kind="command",
        command_kind="cmd",
        name="mvp-wrapper-cmd-service-recover-report-json",
    ),
    ServiceRecoverReportOperation(
        operation_kind="seed",
        name="mvp-wrapper-service-recover-report-json-seed-crash-ps1-json",
    ),
    ServiceRecoverReportOperation(
        operation_kind="command",
        command_kind="ps1",
        name="mvp-wrapper-ps1-service-recover-report-json",
    ),
)


def append_wrapper_service_recover_report_errors(
    errors: list[str],
    *,
    python_executable: str,
    assert_command_json_result: JsonCallable,
    assert_run_json_result: JsonCallable,
    assert_service_recover_json_result: JsonCallable,
) -> None:
    ctx = ServiceRecoverReportContext(
        python_executable=python_executable,
        assert_command_json_result=assert_command_json_result,
        assert_run_json_result=assert_run_json_result,
        assert_service_recover_json_result=assert_service_recover_json_result,
    )
    for operation in _SERVICE_RECOVER_REPORT_OPERATIONS:
        if operation.operation_kind == "seed":
            _append_seed_crash_json_case(errors, ctx, operation=operation)
        else:
            _append_service_recover_report_json_case(
                errors,
                ctx,
                operation=operation,
            )
