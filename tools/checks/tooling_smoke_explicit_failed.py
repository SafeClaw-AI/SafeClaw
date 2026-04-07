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
class ExplicitFailedContext:
    python_executable: str
    assert_command_json_result: JsonCallable
    assert_run_json_result: JsonCallable


@dataclass(frozen=True)
class ExplicitFailedScenario:
    seed_name: str
    command_name: str
    action: str
    task_id: str
    db_path: str
    output_path: str
    wrapper: str


_EXPLICIT_FAILED_SCENARIOS = (
    ExplicitFailedScenario(
        seed_name="mvp-wrapper-status-explicit-failed-seed-json",
        command_name="mvp-wrapper-ps1-status-explicit-failed-json",
        action="status",
        task_id="task-wrapper-status-explicit-failed",
        db_path="target/mvp/status-explicit-failed.db",
        output_path="target/mvp/status-explicit-failed.txt",
        wrapper="ps1",
    ),
    ExplicitFailedScenario(
        seed_name="mvp-wrapper-report-explicit-failed-seed-json",
        command_name="mvp-wrapper-ps1-report-explicit-failed-json",
        action="report",
        task_id="task-wrapper-report-explicit-failed",
        db_path="target/mvp/report-explicit-failed.db",
        output_path="target/mvp/report-explicit-failed.txt",
        wrapper="ps1",
    ),
    ExplicitFailedScenario(
        seed_name="mvp-wrapper-cmd-status-explicit-failed-seed-json",
        command_name="mvp-wrapper-cmd-status-explicit-failed-json",
        action="status",
        task_id="task-wrapper-cmd-status-explicit-failed",
        db_path="target/mvp/cmd-status-explicit-failed.db",
        output_path="target/mvp/cmd-status-explicit-failed.txt",
        wrapper="cmd",
    ),
    ExplicitFailedScenario(
        seed_name="mvp-wrapper-cmd-report-explicit-failed-seed-json",
        command_name="mvp-wrapper-cmd-report-explicit-failed-json",
        action="report",
        task_id="task-wrapper-cmd-report-explicit-failed",
        db_path="target/mvp/cmd-report-explicit-failed.db",
        output_path="target/mvp/cmd-report-explicit-failed.txt",
        wrapper="cmd",
    ),
)


def _build_ps1_command(scenario: ExplicitFailedScenario) -> list[str]:
    return [
        "powershell.exe",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        r"tools\mvp\safeclaw_mvp.ps1",
        scenario.action,
        "--db",
        scenario.db_path,
        "--task-id",
        scenario.task_id,
        "--json",
    ]


def _build_cmd_command(scenario: ExplicitFailedScenario) -> list[str]:
    return [
        "cmd",
        "/c",
        r"tools\mvp\safeclaw_mvp.cmd",
        scenario.action,
        "--db",
        scenario.db_path,
        "--task-id",
        scenario.task_id,
        "--json",
    ]


def _build_command(scenario: ExplicitFailedScenario) -> list[str]:
    if scenario.wrapper == "ps1":
        return _build_ps1_command(scenario)
    return _build_cmd_command(scenario)


def _append_seed_failed_json_errors(
    errors: list[str],
    ctx: ExplicitFailedContext,
    *,
    scenario: ExplicitFailedScenario,
) -> None:
    result = ctx.assert_command_json_result(
        [
            ctx.python_executable,
            "tools/mvp/safeclaw_mvp.py",
            "seed-failed",
            "--reset",
            "--task-id",
            scenario.task_id,
            "--db",
            scenario.db_path,
            "--output",
            scenario.output_path,
            "--json",
        ],
        errors,
        scenario.seed_name,
        "seed-failed",
    )
    ctx.assert_run_json_result(
        result,
        errors,
        scenario.seed_name,
        expected_task_id=scenario.task_id,
        expected_db_path=scenario.db_path,
        expected_output_path=scenario.output_path,
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
) -> None:
    if not isinstance(source_hints, dict) or source_hints.get("db") != "flag":
        errors.append(f"{name} missing source_hints.db=flag")
    elif source_hints.get("output") != "session":
        errors.append(f"{name} missing source_hints.output=session")
    elif source_hints.get("owner_id") != "session":
        errors.append(f"{name} missing source_hints.owner_id=session")
    elif source_hints.get("task_context") != "flag":
        errors.append(f"{name} missing source_hints.task_context=flag")


def _append_command_output_errors(
    errors: list[str],
    ctx: ExplicitFailedContext,
    *,
    scenario: ExplicitFailedScenario,
) -> None:
    result = ctx.assert_command_json_result(
        _build_command(scenario),
        errors,
        scenario.command_name,
        scenario.action,
    )
    if result is None:
        return

    prepared = result.get("prepared") or []
    remembered_session = result.get("remembered_session") or {}
    source_hints = result.get("source_hints") or {}
    captured_output = str(result.get("captured_output") or "")
    if _append_prepared_action_error(
        errors,
        name=scenario.command_name,
        action=scenario.action,
        prepared=prepared,
    ):
        return
    if _append_captured_task_error(
        errors,
        name=scenario.command_name,
        task_id=scenario.task_id,
        captured_output=captured_output,
    ):
        return
    if _append_required_output_fragment_error(
        errors,
        name=scenario.command_name,
        captured_output=captured_output,
    ):
        return
    if _append_remembered_session_error(
        errors,
        name=scenario.command_name,
        task_id=scenario.task_id,
        remembered_session=remembered_session,
    ):
        return
    _append_source_hints_error(
        errors,
        name=scenario.command_name,
        source_hints=source_hints,
    )


def append_wrapper_explicit_failed_errors(
    errors: list[str],
    *,
    python_executable: str,
    assert_command_json_result: JsonCallable,
    assert_run_json_result: JsonCallable,
) -> None:
    ctx = ExplicitFailedContext(
        python_executable=python_executable,
        assert_command_json_result=assert_command_json_result,
        assert_run_json_result=assert_run_json_result,
    )
    for scenario in _EXPLICIT_FAILED_SCENARIOS:
        _append_seed_failed_json_errors(errors, ctx, scenario=scenario)
        _append_command_output_errors(errors, ctx, scenario=scenario)
