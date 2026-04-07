from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


JsonCallable = Callable[..., Any]
AssertionCallable = Callable[..., Any]

_DEMO_TASK_ID = "task-wrapper-demo-json"
_DEMO_TEXT_TASK_ID = "task-wrapper-demo"
_DEMO_JSON_LABEL = "mvp-wrapper-demo-json"
_DEMO_TEXT_LABEL = "mvp-wrapper-demo"
_DEMO_MISSING_REMEMBERED_SESSION_ERROR = (
    "mvp-wrapper-demo-json 缺少 remembered_session task-wrapper-demo-json"
)
_DEMO_MISSING_SESSION_ALIAS_ERROR = (
    "mvp-wrapper-demo-json 缺少兼容 session task-wrapper-demo-json"
)
_DEMO_SOURCE_HINTS = [
    (
        "run",
        {
            "db": "default",
            "output": "default",
            "owner_id": "default",
            "task_context": "flag",
        },
    ),
    (
        "status",
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
class WrapperDemoSuccessContext:
    repo_root: Path
    python_executable: str
    subprocess_module: Any
    assert_command_json_result: JsonCallable
    assert_matching_session_alias: AssertionCallable
    assert_step_source_hints: AssertionCallable


def _py_command(python_executable: str, *args: str) -> list[str]:
    return [python_executable, "tools/mvp/safeclaw_mvp.py", *args]


def _append_demo_text_errors(
    errors: list[str],
    ctx: WrapperDemoSuccessContext,
) -> None:
    wrapper_demo = ctx.subprocess_module.run(
        _py_command(ctx.python_executable, "demo", "--task-id", _DEMO_TEXT_TASK_ID),
        cwd=ctx.repo_root,
        capture_output=True,
        text=True,
    )
    output = (wrapper_demo.stdout or "") + (wrapper_demo.stderr or "")
    if wrapper_demo.returncode != 0:
        errors.append(f"{_DEMO_TEXT_LABEL} 执行失败: exit={wrapper_demo.returncode}")
        return
    if "[mvp-wrapper] demo => run" not in output:
        errors.append("mvp-wrapper-demo 输出缺少 run 标记")
        return
    if "[mvp-wrapper] demo => status" not in output:
        errors.append("mvp-wrapper-demo 输出缺少 status 标记")
        return
    if "[mvp-wrapper] demo => report" not in output:
        errors.append("mvp-wrapper-demo 输出缺少 report 标记")
        return
    if (
        f"[mvp] report target => task={_DEMO_TEXT_TASK_ID} effect=effect-{_DEMO_TEXT_TASK_ID}"
        not in output
    ):
        errors.append("mvp-wrapper-demo 输出缺少 task-wrapper-demo report 目标")


def _append_demo_json_errors(
    errors: list[str],
    ctx: WrapperDemoSuccessContext,
) -> None:
    result = ctx.assert_command_json_result(
        _py_command(ctx.python_executable, "demo", "--task-id", _DEMO_TASK_ID, "--json"),
        errors,
        _DEMO_JSON_LABEL,
        "demo",
    )
    if result is None:
        return
    steps = result.get("steps") or []
    session = result.get("session") or {}
    remembered_session = result.get("remembered_session") or {}
    if [step.get("action") for step in steps] != ["run", "status", "report"]:
        errors.append("mvp-wrapper-demo-json 步骤序列不正确")
        return
    if remembered_session.get("task_id") != _DEMO_TASK_ID:
        errors.append(_DEMO_MISSING_REMEMBERED_SESSION_ERROR)
        return
    if session.get("task_id") != _DEMO_TASK_ID:
        errors.append(_DEMO_MISSING_SESSION_ALIAS_ERROR)
        return
    ctx.assert_matching_session_alias(result, errors, _DEMO_JSON_LABEL)
    ctx.assert_step_source_hints(steps, errors, _DEMO_JSON_LABEL, _DEMO_SOURCE_HINTS)


def append_wrapper_demo_success_errors(
    errors: list[str],
    *,
    repo_root: Path,
    python_executable: str,
    subprocess_module: Any,
    assert_command_json_result: JsonCallable,
    assert_matching_session_alias: AssertionCallable,
    assert_step_source_hints: AssertionCallable,
) -> None:
    ctx = WrapperDemoSuccessContext(
        repo_root=repo_root,
        python_executable=python_executable,
        subprocess_module=subprocess_module,
        assert_command_json_result=assert_command_json_result,
        assert_matching_session_alias=assert_matching_session_alias,
        assert_step_source_hints=assert_step_source_hints,
    )
    _append_demo_text_errors(errors, ctx)
    _append_demo_json_errors(errors, ctx)
