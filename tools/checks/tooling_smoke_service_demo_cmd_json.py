from __future__ import annotations

from typing import Any, Callable


JsonCallable = Callable[..., Any]
AssertionCallable = Callable[..., Any]

_COMMAND = ["cmd", "/c", r"tools\mvp\safeclaw_mvp.cmd", "service-demo", "--json"]
_LABEL = "mvp-wrapper-cmd-service-demo-json"


def append_wrapper_cmd_service_demo_json_errors(
    errors: list[str],
    *,
    assert_command_json_result: JsonCallable,
    assert_service_demo_json_result: AssertionCallable,
) -> None:
    result = assert_command_json_result(_COMMAND, errors, _LABEL, "service-demo")
    assert_service_demo_json_result(result, errors, _LABEL)
