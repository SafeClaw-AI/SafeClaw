from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


JsonCallable = Callable[..., Any]
FailureCallable = Callable[..., Any]

_PASSTHROUGH_FAIL_SUBSTRING = "[mvp-wrapper] cargo => failed action=not-real-action exit=1"
_DEMO_FAIL_SUBSTRING = "[mvp-wrapper] demo => failed step=run exit=2"


@dataclass(frozen=True)
class WrapperFailurePathContext:
    repo_root: Path
    python_executable: str
    subprocess_module: Any
    assert_command_json_error: JsonCallable
    assert_command_failure_output: FailureCallable


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


def _collect_output(result: Any) -> str:
    return (result.stdout or "") + (result.stderr or "")


def _append_invalid_sessions_json_case(
    errors: list[str],
    ctx: WrapperFailurePathContext,
) -> None:
    ctx.assert_command_json_error(
        _py_command(ctx.python_executable, "sessions", "--limit", "bad", "--json"),
        errors,
        "mvp-wrapper-invalid-sessions-json",
        "sessions",
        expected_error_message_substring="invalid --limit",
    )


def _append_passthrough_fail_cases(
    errors: list[str],
    ctx: WrapperFailurePathContext,
) -> None:
    ctx.assert_command_failure_output(
        _cmd_command("not-real-action"),
        errors,
        "mvp-wrapper-cmd-passthrough-fail",
        expected_substring=_PASSTHROUGH_FAIL_SUBSTRING,
        missing_output_label="mvp-wrapper-cmd-passthrough-fail missing failed action marker",
    )

    wrapper_passthrough_fail = ctx.subprocess_module.run(
        _py_command(ctx.python_executable, "not-real-action"),
        cwd=ctx.repo_root,
        capture_output=True,
        text=True,
    )
    output = _collect_output(wrapper_passthrough_fail)
    if wrapper_passthrough_fail.returncode == 0:
        errors.append("mvp-wrapper-passthrough-fail 未按预期返回非 0")
    elif _PASSTHROUGH_FAIL_SUBSTRING not in output:
        errors.append("mvp-wrapper-passthrough-fail 输出缺少透传失败承接提示")


def _append_demo_fail_cases(
    errors: list[str],
    ctx: WrapperFailurePathContext,
) -> None:
    ctx.assert_command_failure_output(
        _ps1_command("demo", "--bogus"),
        errors,
        "mvp-wrapper-ps1-demo-fail",
        expected_exit=2,
        expected_substring=_DEMO_FAIL_SUBSTRING,
        missing_output_label="mvp-wrapper-ps1-demo-fail missing failed step marker",
    )

    wrapper_demo_fail = ctx.subprocess_module.run(
        _py_command(ctx.python_executable, "demo", "--bogus"),
        cwd=ctx.repo_root,
        capture_output=True,
        text=True,
    )
    output = _collect_output(wrapper_demo_fail)
    if wrapper_demo_fail.returncode != 2:
        errors.append(
            f"mvp-wrapper-demo-fail 执行失败: exit={wrapper_demo_fail.returncode}"
        )
    elif _DEMO_FAIL_SUBSTRING not in output:
        errors.append("mvp-wrapper-demo-fail 输出缺少组合动作失败承接提示")


def append_wrapper_failure_path_errors(
    errors: list[str],
    *,
    repo_root: Path,
    python_executable: str,
    subprocess_module: Any,
    assert_command_json_error: JsonCallable,
    assert_command_failure_output: FailureCallable,
) -> None:
    ctx = WrapperFailurePathContext(
        repo_root=repo_root,
        python_executable=python_executable,
        subprocess_module=subprocess_module,
        assert_command_json_error=assert_command_json_error,
        assert_command_failure_output=assert_command_failure_output,
    )
    _append_invalid_sessions_json_case(errors, ctx)
    _append_passthrough_fail_cases(errors, ctx)
    _append_demo_fail_cases(errors, ctx)
