from __future__ import annotations

from typing import Any, Callable


JsonCallable = Callable[..., Any]
AssertionCallable = Callable[..., Any]

_COMMAND = [
    "cmd",
    "/c",
    r"tools\mvp\safeclaw_mvp.cmd",
    "run",
    "--reset",
    "--task-id",
    "task-wrapper-cmd-space",
    "--db",
    "target/mvp/space wrapper/run wrapper cmd.db",
    "--output",
    "target/mvp/space wrapper/run wrapper cmd.txt",
    "--json",
]
_LABEL = "mvp-wrapper-cmd-run-json"


def append_wrapper_cmd_run_json_errors(
    errors: list[str],
    *,
    assert_command_json_result: JsonCallable,
    assert_run_json_result: AssertionCallable,
) -> None:
    result = assert_command_json_result(_COMMAND, errors, _LABEL, "run")
    assert_run_json_result(
        result,
        errors,
        _LABEL,
        expected_task_id="task-wrapper-cmd-space",
        expected_db_path="target/mvp/space wrapper/run wrapper cmd.db",
        expected_output_path="target/mvp/space wrapper/run wrapper cmd.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )
