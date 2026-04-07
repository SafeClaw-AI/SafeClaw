from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


JsonCallable = Callable[..., Any]
_REPORT_STEPS = ("run", "service-status", "report")
_REPORT_TASK_ID = "task-wrapper-service-run-report-json"
_REPORT_DB_PATH = r"target\mvp\service-run-report-json.db"
_REPORT_OUTPUT_PATH = "target/mvp/service-run-report-json.txt"


@dataclass(frozen=True)
class ServiceRunReportCase:
    command_kind: str
    name: str


@dataclass(frozen=True)
class ServiceRunReportContext:
    repo_root: Path
    python_executable: str
    subprocess_module: Any
    assert_command_json_result: JsonCallable
    assert_service_run_json_result: JsonCallable


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


def _append_service_run_report_text_errors(
    errors: list[str],
    ctx: ServiceRunReportContext,
) -> None:
    result = ctx.subprocess_module.run(
        [
            ctx.python_executable,
            "tools/mvp/safeclaw_mvp.py",
            "service-run",
            "--reset",
            "--task-id",
            "task-wrapper-service-run-report",
            "--db",
            "target/mvp/service-run-report.db",
            "--output",
            "target/mvp/service-run-report.txt",
            "--limit",
            "1",
            "--report",
        ],
        cwd=ctx.repo_root,
        capture_output=True,
        text=True,
    )
    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        errors.append(
            f"mvp-wrapper-service-run-report failed: exit={result.returncode}"
        )
    elif "[mvp-wrapper] service-run => run" not in output:
        errors.append("mvp-wrapper-service-run-report missing run step marker")
    elif "[mvp-wrapper] service-run => service-status" not in output:
        errors.append(
            "mvp-wrapper-service-run-report missing service-status step marker"
        )
    elif "[mvp-wrapper] service-run => report" not in output:
        errors.append("mvp-wrapper-service-run-report missing report step marker")
    elif (
        "[mvp] report target => task=task-wrapper-service-run-report "
        "effect=effect-task-wrapper-service-run-report"
        not in output
    ):
        errors.append("mvp-wrapper-service-run-report missing report output")


def _append_service_run_report_json_case(
    errors: list[str],
    ctx: ServiceRunReportContext,
    *,
    case: ServiceRunReportCase,
) -> None:
    if case.command_kind == "cmd":
        command = _cmd_command(
            "service-run",
            "--reset",
            "--task-id",
            _REPORT_TASK_ID,
            "--db",
            _REPORT_DB_PATH.replace("\\", "/"),
            "--output",
            _REPORT_OUTPUT_PATH,
            "--limit",
            "1",
            "--report",
            "--json",
        )
    else:
        command = _ps1_command(
            "service-run",
            "--reset",
            "--task-id",
            _REPORT_TASK_ID,
            "--db",
            _REPORT_DB_PATH.replace("\\", "/"),
            "--output",
            _REPORT_OUTPUT_PATH,
            "--limit",
            "1",
            "--report",
            "--json",
        )
    result = ctx.assert_command_json_result(
        command,
        errors,
        case.name,
        "service-run",
    )
    ctx.assert_service_run_json_result(
        result,
        errors,
        case.name,
        expected_db=_REPORT_DB_PATH,
        expected_db_source="flag",
        expected_task_id=_REPORT_TASK_ID,
        expected_limit=1,
        expected_steps=list(_REPORT_STEPS),
        expect_report_payload=True,
    )


_SERVICE_RUN_REPORT_JSON_CASES = (
    ServiceRunReportCase(
        command_kind="cmd",
        name="mvp-wrapper-cmd-service-run-report-json",
    ),
    ServiceRunReportCase(
        command_kind="ps1",
        name="mvp-wrapper-ps1-service-run-report-json",
    ),
)


def append_wrapper_service_run_report_errors(
    errors: list[str],
    *,
    repo_root: Path,
    python_executable: str,
    subprocess_module: Any,
    assert_command_json_result: JsonCallable,
    assert_service_run_json_result: JsonCallable,
) -> None:
    ctx = ServiceRunReportContext(
        repo_root=repo_root,
        python_executable=python_executable,
        subprocess_module=subprocess_module,
        assert_command_json_result=assert_command_json_result,
        assert_service_run_json_result=assert_service_run_json_result,
    )
    _append_service_run_report_text_errors(errors, ctx)
    for case in _SERVICE_RUN_REPORT_JSON_CASES:
        _append_service_run_report_json_case(errors, ctx, case=case)
