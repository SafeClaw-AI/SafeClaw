from __future__ import annotations

from typing import Any, Callable


JsonCallable = Callable[..., Any]
AssertionCallable = Callable[..., Any]

_LABEL = "mvp-wrapper-run-json"


def append_wrapper_run_json_errors(
    errors: list[str],
    *,
    python_executable: str,
    assert_command_json_result: JsonCallable,
    assert_run_json_result: AssertionCallable,
) -> None:
    result = assert_command_json_result(
        [
            python_executable,
            "tools/mvp/safeclaw_mvp.py",
            "run",
            "--reset",
            "--task-id",
            "task-wrapper-json",
            "--json",
        ],
        errors,
        _LABEL,
        "run",
    )

    assert_run_json_result(
        result,
        errors,
        _LABEL,
        expected_task_id="task-wrapper-json",
        expected_db_source="default",
        expected_output_source="default",
    )
