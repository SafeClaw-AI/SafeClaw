from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


JsonCallable = Callable[..., Any]
AssertionCallable = Callable[..., Any]

_LABEL = "mvp-wrapper-service-demo-no-tool-path-json"


@dataclass(frozen=True)
class ServiceDemoNoToolPathJsonContext:
    repo_root: Path
    python_executable: str
    subprocess_module: Any
    load_json_payload: JsonCallable
    extract_json_result: JsonCallable
    assert_service_demo_json_result: AssertionCallable


def _py_command(python_executable: str, *args: str) -> list[str]:
    return [python_executable, "tools/mvp/safeclaw_mvp.py", *args]


def append_wrapper_service_demo_no_tool_path_json_errors(
    errors: list[str],
    *,
    repo_root: Path,
    python_executable: str,
    subprocess_module: Any,
    load_json_payload: JsonCallable,
    extract_json_result: JsonCallable,
    assert_service_demo_json_result: AssertionCallable,
) -> None:
    ctx = ServiceDemoNoToolPathJsonContext(
        repo_root=repo_root,
        python_executable=python_executable,
        subprocess_module=subprocess_module,
        load_json_payload=load_json_payload,
        extract_json_result=extract_json_result,
        assert_service_demo_json_result=assert_service_demo_json_result,
    )
    wrapper_service_env = os.environ.copy()
    wrapper_service_env["PATH"] = os.pathsep.join(
        entry
        for entry in wrapper_service_env.get("PATH", "").split(os.pathsep)
        if ".cargo" not in entry.lower() and "mingw64" not in entry.lower()
    )

    service_demo_without_tool_path = ctx.subprocess_module.run(
        _py_command(ctx.python_executable, "service-demo", "--json"),
        cwd=ctx.repo_root,
        capture_output=True,
        text=True,
        env=wrapper_service_env,
    )
    payload = ctx.load_json_payload(
        service_demo_without_tool_path,
        errors,
        _LABEL,
        0,
    )
    result = (
        None
        if payload is None
        else ctx.extract_json_result(payload, errors, _LABEL, "service-demo")
    )
    ctx.assert_service_demo_json_result(result, errors, _LABEL)
