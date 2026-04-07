from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


JsonCallable = Callable[..., Any]
FailureCallable = Callable[..., Any]

_RECOVER_DEMO_TASK_ID = "task-wrapper-recover-demo-json"
_RECOVER_DEMO_TEXT_LABEL = "mvp-wrapper-recover-demo-fail"
_RECOVER_DEMO_FAIL_SUBSTRING = "[mvp-wrapper] recover-demo => failed step=seed-crash exit=2"
_RECOVER_DEMO_MISSING_OUTPUT_ERROR = (
    "mvp-wrapper-recover-demo-fail 输出缺少组合动作失败承接提示"
)


@dataclass(frozen=True)
class WrapperRecoverDemoFailureContext:
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


def _append_recover_demo_fail_text_errors(
    errors: list[str],
    ctx: WrapperRecoverDemoFailureContext,
) -> None:
    ctx.assert_command_failure_output(
        _ps1_command("recover-demo", "--bogus"),
        errors,
        "mvp-wrapper-ps1-recover-demo-fail",
        expected_exit=2,
        expected_substring=_RECOVER_DEMO_FAIL_SUBSTRING,
        missing_output_label="mvp-wrapper-ps1-recover-demo-fail missing failed step marker",
    )

    wrapper_recover_demo_fail = ctx.subprocess_module.run(
        _py_command(ctx.python_executable, "recover-demo", "--bogus"),
        cwd=ctx.repo_root,
        capture_output=True,
        text=True,
    )
    output = _collect_output(wrapper_recover_demo_fail)
    if wrapper_recover_demo_fail.returncode != 2:
        errors.append(
            f"{_RECOVER_DEMO_TEXT_LABEL} 执行失败: exit={wrapper_recover_demo_fail.returncode}"
        )
    elif _RECOVER_DEMO_FAIL_SUBSTRING not in output:
        errors.append(_RECOVER_DEMO_MISSING_OUTPUT_ERROR)


def _append_recover_demo_fail_json_errors(
    errors: list[str],
    ctx: WrapperRecoverDemoFailureContext,
) -> None:
    ctx.assert_command_json_error(
        _cmd_command("recover-demo", "--bogus", "--json"),
        errors,
        "mvp-wrapper-cmd-recover-demo-fail-json",
        "recover-demo",
        expected_failed_step="seed-crash",
        expected_code="invalid-argument",
        expected_details_message_substring="unknown argument",
        details_message_label="mvp-wrapper-cmd-recover-demo-fail-json missing unknown argument",
        expected_remembered_session_task_id=_RECOVER_DEMO_TASK_ID,
        remembered_session_label="mvp-wrapper-cmd-recover-demo-fail-json missing task-wrapper-recover-demo-json",
        reject_legacy_session=True,
        legacy_session_label="mvp-wrapper-cmd-recover-demo-fail-json should not keep legacy session",
    )

    ctx.assert_command_json_error(
        _ps1_command("recover-demo", "--bogus", "--json"),
        errors,
        "mvp-wrapper-ps1-recover-demo-fail-json",
        "recover-demo",
        expected_failed_step="seed-crash",
        expected_code="invalid-argument",
        expected_details_message_substring="unknown argument",
        details_message_label="mvp-wrapper-ps1-recover-demo-fail-json missing unknown argument",
        expected_remembered_session_task_id=_RECOVER_DEMO_TASK_ID,
        remembered_session_label="mvp-wrapper-ps1-recover-demo-fail-json missing task-wrapper-recover-demo-json",
        reject_legacy_session=True,
        legacy_session_label="mvp-wrapper-ps1-recover-demo-fail-json should not keep legacy session",
    )

    ctx.assert_command_json_error(
        _py_command(ctx.python_executable, "recover-demo", "--bogus", "--json"),
        errors,
        "mvp-wrapper-recover-demo-fail-json",
        "recover-demo",
        expected_failed_step="seed-crash",
        expected_code="invalid-argument",
        expected_details_message_substring="unknown argument",
        details_message_label="mvp-wrapper-recover-demo-fail-json 缺少 wrapper 级 unknown argument",
        expected_remembered_session_task_id=_RECOVER_DEMO_TASK_ID,
        remembered_session_label="mvp-wrapper-recover-demo-fail-json remembered_session 缺少 task-wrapper-recover-demo-json",
        reject_legacy_session=True,
        legacy_session_label="mvp-wrapper-recover-demo-fail-json 不应继续返回旧 session 字段",
    )


def append_wrapper_recover_demo_failure_errors(
    errors: list[str],
    *,
    repo_root: Path,
    python_executable: str,
    subprocess_module: Any,
    assert_command_json_error: JsonCallable,
    assert_command_failure_output: FailureCallable,
) -> None:
    ctx = WrapperRecoverDemoFailureContext(
        repo_root=repo_root,
        python_executable=python_executable,
        subprocess_module=subprocess_module,
        assert_command_json_error=assert_command_json_error,
        assert_command_failure_output=assert_command_failure_output,
    )
    _append_recover_demo_fail_text_errors(errors, ctx)
    _append_recover_demo_fail_json_errors(errors, ctx)
