from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


JsonPayloadCallable = Callable[..., Any]
JsonResultCallable = Callable[..., Any]

_TASK_A = "task-wrapper-a"
_TASK_B = "task-wrapper-b"
_USE_JSON_LABEL = "mvp-wrapper-use-json"
_REPORT_JSON_LABEL = "mvp-wrapper-report-json"
_RESTORE_A_FAILURE_LABEL = "mvp-wrapper-restore-after-ps1-retry-a failed"
_RESTORE_B_FAILURE_LABEL = "mvp-wrapper-restore-after-ps1-retry-b failed"


@dataclass(frozen=True)
class UseSessionSuccessContext:
    repo_root: Path
    python_executable: str
    subprocess_module: Any
    load_json_payload: JsonPayloadCallable
    extract_json_result: JsonResultCallable


def _py_command(python_executable: str, *args: str) -> list[str]:
    return [python_executable, "tools/mvp/safeclaw_mvp.py", *args]


def _restore_session(
    errors: list[str],
    ctx: UseSessionSuccessContext,
    *,
    task_id: str,
    label: str,
    reset: bool,
) -> None:
    command = ["run"]
    if reset:
        command.append("--reset")
    command.extend(["--task-id", task_id])
    result = ctx.subprocess_module.run(
        _py_command(ctx.python_executable, *command),
        cwd=ctx.repo_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        errors.append(f"{label}: exit={result.returncode}")


def _append_use_text_errors(
    errors: list[str],
    ctx: UseSessionSuccessContext,
) -> None:
    _restore_session(
        errors,
        ctx,
        task_id=_TASK_A,
        label=_RESTORE_A_FAILURE_LABEL,
        reset=True,
    )
    _restore_session(
        errors,
        ctx,
        task_id=_TASK_B,
        label=_RESTORE_B_FAILURE_LABEL,
        reset=False,
    )

    if not _append_use_activation_errors(errors, ctx):
        return
    if not _append_session_after_use_errors(errors, ctx):
        return
    _append_status_after_use_errors(errors, ctx)


def _append_use_activation_errors(
    errors: list[str],
    ctx: UseSessionSuccessContext,
) -> bool:
    wrapper_use = ctx.subprocess_module.run(
        _py_command(ctx.python_executable, "use", "--index", "1"),
        cwd=ctx.repo_root,
        capture_output=True,
        text=True,
    )
    wrapper_use_output = (wrapper_use.stdout or "") + (wrapper_use.stderr or "")
    if wrapper_use.returncode != 0:
        errors.append(f"mvp-wrapper-use 执行失败: exit={wrapper_use.returncode}")
        return False
    if (
        f"[mvp-wrapper] activated => task={_TASK_A} effect=effect-{_TASK_A}"
        not in wrapper_use_output
    ):
        errors.append("mvp-wrapper-use 输出缺少切回 task-wrapper-a")
        return False
    if (
        "source=index:1 db_source=session output_source=task_scope owner_source=session"
        not in wrapper_use_output
    ):
        errors.append("mvp-wrapper-use 输出缺少来源说明")
        return False
    return True


def _append_session_after_use_errors(
    errors: list[str],
    ctx: UseSessionSuccessContext,
) -> bool:
    wrapper_session_after_use = ctx.subprocess_module.run(
        _py_command(ctx.python_executable, "session"),
        cwd=ctx.repo_root,
        capture_output=True,
        text=True,
    )
    wrapper_session_after_use_output = (
        (wrapper_session_after_use.stdout or "") + (wrapper_session_after_use.stderr or "")
    )
    if wrapper_session_after_use.returncode != 0:
        errors.append(
            "mvp-wrapper-session-after-use 执行失败: "
            f"exit={wrapper_session_after_use.returncode}"
        )
        return False
    if (
        f"[mvp-wrapper] session => task={_TASK_A} effect=effect-{_TASK_A}"
        not in wrapper_session_after_use_output
    ):
        errors.append("mvp-wrapper-session-after-use 输出缺少已切换 task-wrapper-a")
        return False
    if "path=target\\mvp\\last_session.json" not in wrapper_session_after_use_output:
        errors.append("mvp-wrapper-session-after-use 输出缺少 remembered session 路径")
        return False
    return True


def _append_status_after_use_errors(
    errors: list[str],
    ctx: UseSessionSuccessContext,
) -> None:
    wrapper_status_after_use = ctx.subprocess_module.run(
        _py_command(ctx.python_executable, "status"),
        cwd=ctx.repo_root,
        capture_output=True,
        text=True,
    )
    wrapper_status_after_use_output = (
        (wrapper_status_after_use.stdout or "") + (wrapper_status_after_use.stderr or "")
    )
    if wrapper_status_after_use.returncode != 0:
        errors.append(
            f"mvp-wrapper-status-after-use 执行失败: exit={wrapper_status_after_use.returncode}"
        )
        return
    if (
        f"[mvp] status target => task={_TASK_A} effect=effect-{_TASK_A}"
        not in wrapper_status_after_use_output
    ):
        errors.append("mvp-wrapper-status-after-use 输出缺少已切换 task-wrapper-a")


def _append_use_json_errors(
    errors: list[str],
    ctx: UseSessionSuccessContext,
) -> None:
    wrapper_use_json = ctx.subprocess_module.run(
        _py_command(ctx.python_executable, "use", "--index", "0", "--json"),
        cwd=ctx.repo_root,
        capture_output=True,
        text=True,
    )
    payload = ctx.load_json_payload(
        wrapper_use_json,
        errors,
        _USE_JSON_LABEL,
        expected_exit=0,
    )
    if payload is None:
        return
    result = ctx.extract_json_result(payload, errors, _USE_JSON_LABEL, "use")
    if result is None:
        return
    if result.get("task_id") != _TASK_B or result.get("source") != "index:0":
        errors.append("mvp-wrapper-use-json 输出缺少切回 task-wrapper-b")
        return
    if result.get("db_source") != "session":
        errors.append("mvp-wrapper-use-json 输出缺少 db_source=session")
        return
    if result.get("output_source") != "task_scope":
        errors.append("mvp-wrapper-use-json 输出缺少 output_source=task_scope")
        return
    if result.get("owner_id_source") != "session":
        errors.append("mvp-wrapper-use-json 输出缺少 owner_id_source=session")


def _append_report_json_errors(
    errors: list[str],
    ctx: UseSessionSuccessContext,
) -> None:
    wrapper_report_json = ctx.subprocess_module.run(
        _py_command(ctx.python_executable, "report", "--json"),
        cwd=ctx.repo_root,
        capture_output=True,
        text=True,
    )
    payload = ctx.load_json_payload(
        wrapper_report_json,
        errors,
        _REPORT_JSON_LABEL,
        expected_exit=0,
    )
    if payload is None:
        return
    result = ctx.extract_json_result(payload, errors, _REPORT_JSON_LABEL, "report")
    if result is None:
        return
    _append_report_json_result_errors(errors, result)


def _append_report_json_result_errors(
    errors: list[str],
    result: Any,
) -> None:
    prepared = result.get("prepared") or []
    source_hints = result.get("source_hints") or {}
    if not prepared or prepared[0] != "report":
        errors.append("mvp-wrapper-report-json 缺少 prepared report")
        return
    if _TASK_B not in (result.get("captured_output") or ""):
        errors.append("mvp-wrapper-report-json 缺少当前会话 task-wrapper-b 输出")
        return
    if (result.get("remembered_session") or {}).get("task_id") != _TASK_B:
        errors.append("mvp-wrapper-report-json 缺少 remembered session task-wrapper-b")
        return
    if source_hints.get("task_context") != "session":
        errors.append("mvp-wrapper-report-json 缺少 task_context=session")


def append_wrapper_use_session_success_errors(
    errors: list[str],
    *,
    repo_root: Path,
    python_executable: str,
    subprocess_module: Any,
    load_json_payload: JsonPayloadCallable,
    extract_json_result: JsonResultCallable,
) -> None:
    ctx = UseSessionSuccessContext(
        repo_root=repo_root,
        python_executable=python_executable,
        subprocess_module=subprocess_module,
        load_json_payload=load_json_payload,
        extract_json_result=extract_json_result,
    )
    _append_use_text_errors(errors, ctx)
    _append_use_json_errors(errors, ctx)
    _append_report_json_errors(errors, ctx)
