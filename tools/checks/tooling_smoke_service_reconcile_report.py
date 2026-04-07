from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


JsonCallable = Callable[..., Any]
_RECONCILE_REPORT_TASK_ID = "task-wrapper-service-reconcile-report-json"
_RECONCILE_REPORT_DB_PATH = "target/mvp/service-reconcile-report-json.db"
_RECONCILE_REPORT_OUTPUT_PATH = "target/mvp/service-reconcile-report-json.txt"
_RECONCILE_REPORT_EXPECTED_DB = r"target\mvp\service-reconcile-report-json.db"
_RECONCILE_REPORT_STEPS = ("reconcile", "service-status", "report")


@dataclass(frozen=True)
class ServiceReconcileReportOperation:
    operation_kind: str
    name: str


@dataclass(frozen=True)
class ServiceReconcileReportContext:
    python_executable: str
    assert_command_json_result: JsonCallable
    assert_run_json_result: JsonCallable
    assert_service_reconcile_json_result: JsonCallable


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
    ctx: ServiceReconcileReportContext,
    *,
    operation: ServiceReconcileReportOperation,
) -> None:
    result = ctx.assert_command_json_result(
        [
            ctx.python_executable,
            "tools/mvp/safeclaw_mvp.py",
            "seed-crash",
            "--reset",
            "--probe-mode",
            "none",
            "--task-id",
            _RECONCILE_REPORT_TASK_ID,
            "--db",
            _RECONCILE_REPORT_DB_PATH,
            "--output",
            _RECONCILE_REPORT_OUTPUT_PATH,
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
        expected_task_id=_RECONCILE_REPORT_TASK_ID,
        expected_db_path=_RECONCILE_REPORT_DB_PATH,
        expected_output_path=_RECONCILE_REPORT_OUTPUT_PATH,
        expected_db_source="flag",
        expected_output_source="flag",
    )


def _append_ps1_service_reconcile_report_json_case(
    errors: list[str],
    ctx: ServiceReconcileReportContext,
    *,
    operation: ServiceReconcileReportOperation,
) -> None:
    result = ctx.assert_command_json_result(
        _ps1_command(
            "service-reconcile",
            "--db",
            _RECONCILE_REPORT_DB_PATH,
            "--task-id",
            _RECONCILE_REPORT_TASK_ID,
            "--decision",
            "executed",
            "--limit",
            "1",
            "--report",
            "--json",
        ),
        errors,
        operation.name,
        "service-reconcile",
    )
    ctx.assert_service_reconcile_json_result(
        result,
        errors,
        operation.name,
        expected_db=_RECONCILE_REPORT_EXPECTED_DB,
        expected_db_source="flag",
        expected_task_id=_RECONCILE_REPORT_TASK_ID,
        expected_limit=1,
        expected_decision="executed",
        expected_steps=list(_RECONCILE_REPORT_STEPS),
        expect_report_payload=True,
    )


_SERVICE_RECONCILE_REPORT_OPERATIONS = (
    ServiceReconcileReportOperation(
        operation_kind="seed",
        name="mvp-wrapper-service-reconcile-report-json-seed-crash-ps1-json",
    ),
    ServiceReconcileReportOperation(
        operation_kind="ps1",
        name="mvp-wrapper-ps1-service-reconcile-report-json",
    ),
)


def append_wrapper_service_reconcile_report_errors(
    errors: list[str],
    *,
    python_executable: str,
    assert_command_json_result: JsonCallable,
    assert_run_json_result: JsonCallable,
    assert_service_reconcile_json_result: JsonCallable,
) -> None:
    ctx = ServiceReconcileReportContext(
        python_executable=python_executable,
        assert_command_json_result=assert_command_json_result,
        assert_run_json_result=assert_run_json_result,
        assert_service_reconcile_json_result=assert_service_reconcile_json_result,
    )
    for operation in _SERVICE_RECONCILE_REPORT_OPERATIONS:
        if operation.operation_kind == "seed":
            _append_seed_crash_json_case(errors, ctx, operation=operation)
        else:
            _append_ps1_service_reconcile_report_json_case(
                errors,
                ctx,
                operation=operation,
            )
