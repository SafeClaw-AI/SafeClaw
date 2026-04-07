from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


JsonCallable = Callable[..., Any]

_DEMO_TASK_ID = "task-wrapper-demo-json"


@dataclass(frozen=True)
class WrapperDemoInvalidArgumentContext:
    python_executable: str
    assert_command_json_error: JsonCallable


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


def _py_command(python_executable: str, *args: str) -> list[str]:
    return [python_executable, "tools/mvp/safeclaw_mvp.py", *args]


def append_wrapper_demo_invalid_argument_errors(
    errors: list[str],
    *,
    python_executable: str,
    assert_command_json_error: JsonCallable,
) -> None:
    ctx = WrapperDemoInvalidArgumentContext(
        python_executable=python_executable,
        assert_command_json_error=assert_command_json_error,
    )

    ctx.assert_command_json_error(
        _cmd_command("demo", "--bogus", "--json"),
        errors,
        "mvp-wrapper-cmd-demo-fail-json",
        "demo",
        expected_failed_step="run",
        expected_code="invalid-argument",
        expected_details_message_substring="unknown argument",
        details_message_label="mvp-wrapper-cmd-demo-fail-json missing unknown argument",
        expected_remembered_session_task_id=_DEMO_TASK_ID,
        remembered_session_label="mvp-wrapper-cmd-demo-fail-json missing task-wrapper-demo-json",
        reject_legacy_session=True,
        legacy_session_label="mvp-wrapper-cmd-demo-fail-json should not keep legacy session",
    )

    ctx.assert_command_json_error(
        _ps1_command("demo", "--bogus", "--json"),
        errors,
        "mvp-wrapper-ps1-demo-fail-json",
        "demo",
        expected_failed_step="run",
        expected_code="invalid-argument",
        expected_details_message_substring="unknown argument",
        details_message_label="mvp-wrapper-ps1-demo-fail-json missing unknown argument",
        expected_remembered_session_task_id=_DEMO_TASK_ID,
        remembered_session_label="mvp-wrapper-ps1-demo-fail-json missing task-wrapper-demo-json",
        reject_legacy_session=True,
        legacy_session_label="mvp-wrapper-ps1-demo-fail-json should not keep legacy session",
    )

    ctx.assert_command_json_error(
        _py_command(ctx.python_executable, "demo", "--bogus", "--json"),
        errors,
        "mvp-wrapper-demo-fail-json",
        "demo",
        expected_failed_step="run",
        expected_code="invalid-argument",
        expected_details_message_substring="unknown argument",
        details_message_label="mvp-wrapper-demo-fail-json 缺少 wrapper 级 unknown argument",
        expected_remembered_session_task_id=_DEMO_TASK_ID,
        remembered_session_label="mvp-wrapper-demo-fail-json remembered_session 缺少 task-wrapper-demo-json",
        reject_legacy_session=True,
        legacy_session_label="mvp-wrapper-demo-fail-json 不应继续返回旧 session 字段",
    )
