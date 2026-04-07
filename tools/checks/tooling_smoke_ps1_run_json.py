from __future__ import annotations

from typing import Any, Callable


JsonCallable = Callable[..., Any]
AssertionCallable = Callable[..., Any]

_COMMAND = [
    "powershell.exe",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    r"tools\mvp\safeclaw_mvp.ps1",
    "run",
    "--reset",
    "--task-id",
    "task-wrapper-ps1-space",
    "--db",
    "target/mvp/space wrapper/run wrapper ps1.db",
    "--output",
    "target/mvp/space wrapper/run wrapper ps1.txt",
    "--json",
]
_LABEL = "mvp-wrapper-ps1-run-json"


def append_wrapper_ps1_run_json_errors(
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
        expected_task_id="task-wrapper-ps1-space",
        expected_db_path="target/mvp/space wrapper/run wrapper ps1.db",
        expected_output_path="target/mvp/space wrapper/run wrapper ps1.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )
