from __future__ import annotations

from typing import Any, Callable


JsonCallable = Callable[..., Any]


def _py_command(python_executable: str, *args: str) -> list[str]:
    return [python_executable, "tools/mvp/safeclaw_mvp.py", *args]


def append_wrapper_service_demo_invalid_json_errors(
    errors: list[str],
    *,
    python_executable: str,
    assert_command_json_error: JsonCallable,
) -> None:
    details = assert_command_json_error(
        _py_command(python_executable, "service-demo", "--bogus", "--json"),
        errors,
        "mvp-wrapper-service-demo-invalid-json",
        "service-demo",
        expected_error_message_substring="unknown argument: --bogus",
        expect_no_remembered_session=True,
    )

    if details is not None and details.get("remembered_session") is not None:
        errors.append("mvp-wrapper-service-demo-invalid-json ???? remembered_session")
