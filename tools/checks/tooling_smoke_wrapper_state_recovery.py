from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


JsonCallable = Callable[..., Any]

_CRASH_TASK_ID = "task-wrapper-seed-crash-json"
_FAILED_TASK_ID = "task-wrapper-seed-failed-json"
_CMD_CRASH_TASK_ID = "task-wrapper-cmd-seed-crash-json"
_CMD_FAILED_TASK_ID = "task-wrapper-cmd-seed-failed-json"
_CMD_CRASH_DB_PATH = "target/mvp/cmd-seed-crash-json.db"
_CMD_FAILED_DB_PATH = "target/mvp/cmd-seed-failed-json.db"
_CMD_CRASH_OUTPUT_PATH = "target/mvp/cmd-seed-crash-json.txt"
_CMD_FAILED_OUTPUT_PATH = "target/mvp/cmd-seed-failed-json.txt"
_RECOVER_REMEMBERED_SESSION_ERROR = (
    "mvp-wrapper-recover-json 缺少 remembered session task-wrapper-seed-crash-json"
)
_RETRY_REMEMBERED_SESSION_ERROR = (
    "mvp-wrapper-retry-json 缺少 remembered session task-wrapper-seed-failed-json"
)


@dataclass(frozen=True)
class WrapperStateRecoveryContext:
    repo_root: Path
    python_executable: str
    subprocess_module: Any
    load_json_payload: JsonCallable
    extract_json_result: JsonCallable
    assert_command_json_result: JsonCallable
    assert_run_json_result: JsonCallable


def _cmd_command(*args: str) -> list[str]:
    return ["cmd", "/c", r"tools\mvp\safeclaw_mvp.cmd", *args]


def _py_command(python_executable: str, *args: str) -> list[str]:
    return [python_executable, "tools/mvp/safeclaw_mvp.py", *args]


def _append_python_seed_crash_json(
    errors: list[str],
    ctx: WrapperStateRecoveryContext,
) -> None:
    wrapper_seed_crash_json = ctx.subprocess_module.run(
        _py_command(
            ctx.python_executable,
            "seed-crash",
            "--reset",
            "--task-id",
            _CRASH_TASK_ID,
            "--json",
        ),
        cwd=ctx.repo_root,
        capture_output=True,
        text=True,
    )
    payload = ctx.load_json_payload(
        wrapper_seed_crash_json,
        errors,
        "mvp-wrapper-seed-crash-json",
        expected_exit=0,
    )
    if payload is not None:
        result = ctx.extract_json_result(
            payload,
            errors,
            "mvp-wrapper-seed-crash-json",
            "seed-crash",
        )
        if result is not None:
            prepared = result.get("prepared") or []
            session = result.get("saved_session") or {}
            if not prepared or prepared[0] != "seed-crash":
                errors.append("mvp-wrapper-seed-crash-json 缺少 prepared seed-crash")
            elif session.get("task_id") != _CRASH_TASK_ID:
                errors.append(
                    "mvp-wrapper-seed-crash-json 缺少保存后的 task-wrapper-seed-crash-json 会话"
                )
            elif _CRASH_TASK_ID not in (result.get("captured_output") or ""):
                errors.append(
                    "mvp-wrapper-seed-crash-json 缺少 task-wrapper-seed-crash-json 输出"
                )


def _extract_python_session_recovery_result(
    errors: list[str],
    ctx: WrapperStateRecoveryContext,
    *,
    command_name: str,
    label: str,
) -> Any | None:
    completed = ctx.subprocess_module.run(
        _py_command(ctx.python_executable, command_name, "--json"),
        cwd=ctx.repo_root,
        capture_output=True,
        text=True,
    )
    payload = ctx.load_json_payload(
        completed,
        errors,
        label,
        expected_exit=0,
    )
    if payload is None:
        return None
    return ctx.extract_json_result(
        payload,
        errors,
        label,
        command_name,
    )


def _append_missing_prepared_error(
    errors: list[str],
    *,
    result: dict[str, Any],
    label: str,
    command_name: str,
) -> bool:
    prepared = result.get("prepared") or []
    if prepared and prepared[0] == command_name:
        return False
    errors.append(f"{label} 缺少 prepared {command_name}")
    return True


def _append_missing_session_output_error(
    errors: list[str],
    *,
    result: dict[str, Any],
    label: str,
    expected_task_id: str,
) -> bool:
    if expected_task_id in (result.get("captured_output") or ""):
        return False
    errors.append(f"{label} 缺少当前会话 {expected_task_id} 输出")
    return True


def _append_missing_remembered_session_error(
    errors: list[str],
    *,
    result: dict[str, Any],
    expected_task_id: str,
    error_message: str,
) -> bool:
    remembered = result.get("remembered_session") or {}
    if remembered.get("task_id") == expected_task_id:
        return False
    errors.append(error_message)
    return True


def _append_missing_task_context_error(
    errors: list[str],
    *,
    result: dict[str, Any],
    label: str,
) -> None:
    source_hints = result.get("source_hints") or {}
    if source_hints.get("task_context") != "session":
        errors.append(f"{label} 缺少 task_context=session")


def _append_python_session_recovery_json(
    errors: list[str],
    ctx: WrapperStateRecoveryContext,
    *,
    command_name: str,
    label: str,
    expected_task_id: str,
    missing_remembered_session_error: str,
) -> None:
    result = _extract_python_session_recovery_result(
        errors,
        ctx,
        command_name=command_name,
        label=label,
    )
    if result is None:
        return
    if _append_missing_prepared_error(
        errors,
        result=result,
        label=label,
        command_name=command_name,
    ):
        return
    if _append_missing_session_output_error(
        errors,
        result=result,
        label=label,
        expected_task_id=expected_task_id,
    ):
        return
    if _append_missing_remembered_session_error(
        errors,
        result=result,
        expected_task_id=expected_task_id,
        error_message=missing_remembered_session_error,
    ):
        return
    _append_missing_task_context_error(
        errors,
        result=result,
        label=label,
    )


def _append_python_recover_json(
    errors: list[str],
    ctx: WrapperStateRecoveryContext,
) -> None:
    _append_python_session_recovery_json(
        errors,
        ctx,
        command_name="recover",
        label="mvp-wrapper-recover-json",
        expected_task_id=_CRASH_TASK_ID,
        missing_remembered_session_error=_RECOVER_REMEMBERED_SESSION_ERROR,
    )


def _append_cmd_seed_crash_json(
    errors: list[str],
    ctx: WrapperStateRecoveryContext,
) -> None:
    result = ctx.assert_command_json_result(
        _cmd_command(
            "seed-crash",
            "--reset",
            "--task-id",
            _CMD_CRASH_TASK_ID,
            "--db",
            _CMD_CRASH_DB_PATH,
            "--output",
            _CMD_CRASH_OUTPUT_PATH,
            "--json",
        ),
        errors,
        "mvp-wrapper-cmd-seed-crash-json",
        "seed-crash",
    )
    ctx.assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-cmd-seed-crash-json",
        expected_task_id=_CMD_CRASH_TASK_ID,
        expected_db_path=_CMD_CRASH_DB_PATH,
        expected_output_path=_CMD_CRASH_OUTPUT_PATH,
        expected_db_source="flag",
        expected_output_source="flag",
    )


def _append_python_seed_failed_json(
    errors: list[str],
    ctx: WrapperStateRecoveryContext,
) -> None:
    wrapper_seed_failed_json = ctx.subprocess_module.run(
        _py_command(
            ctx.python_executable,
            "seed-failed",
            "--reset",
            "--task-id",
            _FAILED_TASK_ID,
            "--json",
        ),
        cwd=ctx.repo_root,
        capture_output=True,
        text=True,
    )
    payload = ctx.load_json_payload(
        wrapper_seed_failed_json,
        errors,
        "mvp-wrapper-seed-failed-json",
        expected_exit=0,
    )
    if payload is not None:
        result = ctx.extract_json_result(
            payload,
            errors,
            "mvp-wrapper-seed-failed-json",
            "seed-failed",
        )
        if result is not None:
            prepared = result.get("prepared") or []
            session = result.get("saved_session") or {}
            if not prepared or prepared[0] != "seed-failed":
                errors.append("mvp-wrapper-seed-failed-json 缺少 prepared seed-failed")
            elif session.get("task_id") != _FAILED_TASK_ID:
                errors.append(
                    "mvp-wrapper-seed-failed-json 缺少保存后的 task-wrapper-seed-failed-json 会话"
                )
            elif _FAILED_TASK_ID not in (result.get("captured_output") or ""):
                errors.append(
                    "mvp-wrapper-seed-failed-json 缺少 task-wrapper-seed-failed-json 输出"
                )

def _append_python_retry_json(
    errors: list[str],
    ctx: WrapperStateRecoveryContext,
) -> None:
    _append_python_session_recovery_json(
        errors,
        ctx,
        command_name="retry",
        label="mvp-wrapper-retry-json",
        expected_task_id=_FAILED_TASK_ID,
        missing_remembered_session_error=_RETRY_REMEMBERED_SESSION_ERROR,
    )


def _append_cmd_seed_failed_json(
    errors: list[str],
    ctx: WrapperStateRecoveryContext,
) -> None:
    result = ctx.assert_command_json_result(
        _cmd_command(
            "seed-failed",
            "--reset",
            "--task-id",
            _CMD_FAILED_TASK_ID,
            "--db",
            _CMD_FAILED_DB_PATH,
            "--output",
            _CMD_FAILED_OUTPUT_PATH,
            "--json",
        ),
        errors,
        "mvp-wrapper-cmd-seed-failed-json",
        "seed-failed",
    )
    ctx.assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-cmd-seed-failed-json",
        expected_task_id=_CMD_FAILED_TASK_ID,
        expected_db_path=_CMD_FAILED_DB_PATH,
        expected_output_path=_CMD_FAILED_OUTPUT_PATH,
        expected_db_source="flag",
        expected_output_source="flag",
    )


def append_wrapper_state_recovery_errors(
    errors: list[str],
    *,
    repo_root: Path,
    python_executable: str,
    subprocess_module: Any,
    load_json_payload: JsonCallable,
    extract_json_result: JsonCallable,
    assert_command_json_result: JsonCallable,
    assert_run_json_result: JsonCallable,
) -> None:
    ctx = WrapperStateRecoveryContext(
        repo_root=repo_root,
        python_executable=python_executable,
        subprocess_module=subprocess_module,
        load_json_payload=load_json_payload,
        extract_json_result=extract_json_result,
        assert_command_json_result=assert_command_json_result,
        assert_run_json_result=assert_run_json_result,
    )
    _append_python_seed_crash_json(errors, ctx)
    _append_python_recover_json(errors, ctx)
    _append_cmd_seed_crash_json(errors, ctx)
    _append_python_seed_failed_json(errors, ctx)
    _append_python_retry_json(errors, ctx)
    _append_cmd_seed_failed_json(errors, ctx)
