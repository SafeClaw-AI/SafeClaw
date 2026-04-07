from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


JsonCallable = Callable[..., Any]
AssertionCallable = Callable[..., Any]

_RETRY_DEMO_TASK_ID = "task-wrapper-retry-demo-json"
_RETRY_DEMO_TEXT_TASK_ID = "task-wrapper-retry-demo"
_RETRY_DEMO_JSON_LABEL = "mvp-wrapper-retry-demo-json"
_RETRY_DEMO_TEXT_LABEL = "mvp-wrapper-retry-demo"
_RETRY_DEMO_MISSING_REMEMBERED_SESSION_ERROR = (
    "mvp-wrapper-retry-demo-json 缺少 remembered_session task-wrapper-retry-demo-json"
)
_RETRY_DEMO_MISSING_SESSION_ALIAS_ERROR = (
    "mvp-wrapper-retry-demo-json 缺少兼容 session task-wrapper-retry-demo-json"
)
_RETRY_DEMO_SOURCE_HINTS = [
    (
        "seed-failed",
        {
            "db": "default",
            "output": "default",
            "owner_id": "default",
            "task_context": "flag",
        },
    ),
    (
        "retry",
        {
            "db": "session",
            "output": "session",
            "owner_id": "session",
            "task_context": "flag",
        },
    ),
    (
        "report",
        {
            "db": "session",
            "output": "session",
            "owner_id": "session",
            "task_context": "flag",
        },
    ),
]


@dataclass(frozen=True)
class WrapperRetryDemoSuccessContext:
    repo_root: Path
    python_executable: str
    subprocess_module: Any
    assert_command_json_result: JsonCallable
    assert_matching_session_alias: AssertionCallable
    assert_step_source_hints: AssertionCallable


def _py_command(python_executable: str, *args: str) -> list[str]:
    return [python_executable, "tools/mvp/safeclaw_mvp.py", *args]


def _append_retry_demo_text_errors(
    errors: list[str],
    ctx: WrapperRetryDemoSuccessContext,
) -> None:
    wrapper_retry_demo = ctx.subprocess_module.run(
        _py_command(
            ctx.python_executable,
            "retry-demo",
            "--task-id",
            _RETRY_DEMO_TEXT_TASK_ID,
        ),
        cwd=ctx.repo_root,
        capture_output=True,
        text=True,
    )
    output = (wrapper_retry_demo.stdout or "") + (wrapper_retry_demo.stderr or "")
    if wrapper_retry_demo.returncode != 0:
        errors.append(
            f"{_RETRY_DEMO_TEXT_LABEL} 执行失败: exit={wrapper_retry_demo.returncode}"
        )
        return
    if "[mvp-wrapper] retry-demo => seed-failed" not in output:
        errors.append("mvp-wrapper-retry-demo 输出缺少 seed-failed 标记")
        return
    if "[mvp-wrapper] retry-demo => retry" not in output:
        errors.append("mvp-wrapper-retry-demo 输出缺少 retry 标记")
        return
    if "[mvp-wrapper] retry-demo => report" not in output:
        errors.append("mvp-wrapper-retry-demo 输出缺少 report 标记")
        return
    if (
        "[mvp] report target => task=task-wrapper-retry-demo "
        "effect=effect-task-wrapper-retry-demo"
        not in output
    ):
        errors.append("mvp-wrapper-retry-demo 输出缺少 task-wrapper-retry-demo report 目标")


def _append_retry_demo_json_errors(
    errors: list[str],
    ctx: WrapperRetryDemoSuccessContext,
) -> None:
    result = ctx.assert_command_json_result(
        _py_command(
            ctx.python_executable,
            "retry-demo",
            "--task-id",
            _RETRY_DEMO_TASK_ID,
            "--json",
        ),
        errors,
        _RETRY_DEMO_JSON_LABEL,
        "retry-demo",
    )
    if result is None:
        return
    steps = result.get("steps") or []
    session = result.get("session") or {}
    remembered_session = result.get("remembered_session") or {}
    if [step.get("action") for step in steps] != ["seed-failed", "retry", "report"]:
        errors.append("mvp-wrapper-retry-demo-json 步骤序列不正确")
        return
    if remembered_session.get("task_id") != _RETRY_DEMO_TASK_ID:
        errors.append(_RETRY_DEMO_MISSING_REMEMBERED_SESSION_ERROR)
        return
    if session.get("task_id") != _RETRY_DEMO_TASK_ID:
        errors.append(_RETRY_DEMO_MISSING_SESSION_ALIAS_ERROR)
        return
    ctx.assert_matching_session_alias(result, errors, _RETRY_DEMO_JSON_LABEL)
    ctx.assert_step_source_hints(
        steps,
        errors,
        _RETRY_DEMO_JSON_LABEL,
        _RETRY_DEMO_SOURCE_HINTS,
    )


def append_wrapper_retry_demo_success_errors(
    errors: list[str],
    *,
    repo_root: Path,
    python_executable: str,
    subprocess_module: Any,
    assert_command_json_result: JsonCallable,
    assert_matching_session_alias: AssertionCallable,
    assert_step_source_hints: AssertionCallable,
) -> None:
    ctx = WrapperRetryDemoSuccessContext(
        repo_root=repo_root,
        python_executable=python_executable,
        subprocess_module=subprocess_module,
        assert_command_json_result=assert_command_json_result,
        assert_matching_session_alias=assert_matching_session_alias,
        assert_step_source_hints=assert_step_source_hints,
    )
    _append_retry_demo_text_errors(errors, ctx)
    _append_retry_demo_json_errors(errors, ctx)
