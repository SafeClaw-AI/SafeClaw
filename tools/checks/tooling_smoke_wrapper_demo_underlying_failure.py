from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


JsonCallable = Callable[..., Any]
AssertionCallable = Callable[..., Any]

_DEMO_TASK_ID = "task-wrapper-demo-json"
_UNDERLYING_FAIL_TASK_ID = "task-wrapper-demo-underlying-fail"
_UNDERLYING_FAIL_LABEL = "mvp-wrapper-demo-underlying-fail-json"
_UNDERLYING_FAIL_SOURCE_HINTS = [
    (
        "run",
        {
            "db": "default",
            "output": "flag",
            "owner_id": "default",
            "task_context": "flag",
        },
    )
]


@dataclass(frozen=True)
class WrapperDemoUnderlyingFailureContext:
    python_executable: str
    assert_command_json_error: JsonCallable
    assert_step_source_hints: AssertionCallable


def _py_command(python_executable: str, *args: str) -> list[str]:
    return [python_executable, "tools/mvp/safeclaw_mvp.py", *args]


def append_wrapper_demo_underlying_failure_errors(
    errors: list[str],
    *,
    python_executable: str,
    assert_command_json_error: JsonCallable,
    assert_step_source_hints: AssertionCallable,
) -> None:
    ctx = WrapperDemoUnderlyingFailureContext(
        python_executable=python_executable,
        assert_command_json_error=assert_command_json_error,
        assert_step_source_hints=assert_step_source_hints,
    )

    details = ctx.assert_command_json_error(
        _py_command(
            ctx.python_executable,
            "demo",
            "--task-id",
            _UNDERLYING_FAIL_TASK_ID,
            "--output",
            "target/mvp",
            "--json",
        ),
        errors,
        _UNDERLYING_FAIL_LABEL,
        "demo",
        expected_exit=1,
        expected_error_message_substring="failed step=run",
        error_message_label="mvp-wrapper-demo-underlying-fail-json 缺少组合动作失败消息",
        expected_failed_step="run",
        expected_remembered_session_task_id=_DEMO_TASK_ID,
        remembered_session_label="mvp-wrapper-demo-underlying-fail-json remembered_session 缺少 task-wrapper-demo-json",
        reject_legacy_session=True,
        legacy_session_label="mvp-wrapper-demo-underlying-fail-json 不应继续返回旧 session 字段",
    )
    if not isinstance(details, dict):
        return

    ctx.assert_step_source_hints(
        details.get("steps"),
        errors,
        _UNDERLYING_FAIL_LABEL,
        _UNDERLYING_FAIL_SOURCE_HINTS,
    )
