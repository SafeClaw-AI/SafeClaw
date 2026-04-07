from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


JsonCallable = Callable[..., Any]
PathCallable = Callable[[Path], Any]


@dataclass(frozen=True)
class WrapperVerifyInvalidCase:
    command_kind: str
    name: str


@dataclass(frozen=True)
class WrapperVerifyContext:
    repo_root: Path
    python_executable: str
    subprocess_module: Any
    build_smoke_pythonpath_env: PathCallable
    write_smoke_verify_sitecustomize: PathCallable
    load_json_payload: JsonCallable
    extract_json_result: JsonCallable
    assert_verify_json_result: JsonCallable
    assert_command_json_result: JsonCallable
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


def _build_command(
    python_executable: str,
    case: WrapperVerifyInvalidCase,
) -> list[str]:
    if case.command_kind == "cmd":
        return _cmd_command("verify", "--bogus", "--json")
    if case.command_kind == "ps1":
        return _ps1_command("verify", "--bogus", "--json")
    return _py_command(python_executable, "verify", "--bogus", "--json")


def _append_wrapper_cmd_verify_json_guard(
    errors: list[str],
    ctx: WrapperVerifyContext,
) -> None:
    with tempfile.TemporaryDirectory() as verify_mock_dir:
        ctx.write_smoke_verify_sitecustomize(Path(verify_mock_dir))
        wrapper_cmd_verify = ctx.subprocess_module.run(
            _cmd_command("verify", "--json"),
            env=ctx.build_smoke_pythonpath_env(Path(verify_mock_dir)),
            cwd=ctx.repo_root,
            capture_output=True,
            text=True,
        )
    payload = ctx.load_json_payload(
        wrapper_cmd_verify,
        errors,
        "mvp-wrapper-cmd-verify-json",
        0,
    )
    result = None
    if payload is not None:
        result = ctx.extract_json_result(
            payload,
            errors,
            "mvp-wrapper-cmd-verify-json",
            "verify",
        )
    ctx.assert_verify_json_result(result, errors, "mvp-wrapper-cmd-verify-json")


def _append_wrapper_verify_json_guard(
    errors: list[str],
    ctx: WrapperVerifyContext,
) -> None:
    result = ctx.assert_command_json_result(
        [
            ctx.python_executable,
            "-c",
            "import subprocess; from tools.mvp import safeclaw_mvp as m; "
            "m.subprocess.run = lambda *args, **kwargs: subprocess.CompletedProcess("
            "args=['python', 'tools/checks/check_mvp_operator_flow.py'], "
            "returncode=0, stdout='MVP operator flow check passed.\\n', stderr=''); "
            "raise SystemExit(m.run_verify(['--json']))",
        ],
        errors,
        "mvp-wrapper-verify-json",
        "verify",
    )
    ctx.assert_verify_json_result(result, errors, "mvp-wrapper-verify-json")


def _append_wrapper_verify_invalid_json_case(
    errors: list[str],
    ctx: WrapperVerifyContext,
    *,
    case: WrapperVerifyInvalidCase,
) -> None:
    ctx.assert_command_json_error(
        _build_command(ctx.python_executable, case),
        errors,
        case.name,
        "verify",
        expected_error_message_substring="unknown argument: --bogus",
    )


_VERIFY_INVALID_CASES = (
    WrapperVerifyInvalidCase(
        command_kind="cmd",
        name="mvp-wrapper-cmd-verify-invalid-json",
    ),
    WrapperVerifyInvalidCase(
        command_kind="ps1",
        name="mvp-wrapper-ps1-verify-invalid-json",
    ),
    WrapperVerifyInvalidCase(
        command_kind="py",
        name="mvp-wrapper-verify-invalid-json",
    ),
)


def append_wrapper_verify_errors(
    errors: list[str],
    *,
    repo_root: Path,
    python_executable: str,
    subprocess_module: Any,
    build_smoke_pythonpath_env: PathCallable,
    write_smoke_verify_sitecustomize: PathCallable,
    load_json_payload: JsonCallable,
    extract_json_result: JsonCallable,
    assert_verify_json_result: JsonCallable,
    assert_command_json_result: JsonCallable,
    assert_command_json_error: JsonCallable,
) -> None:
    ctx = WrapperVerifyContext(
        repo_root=repo_root,
        python_executable=python_executable,
        subprocess_module=subprocess_module,
        build_smoke_pythonpath_env=build_smoke_pythonpath_env,
        write_smoke_verify_sitecustomize=write_smoke_verify_sitecustomize,
        load_json_payload=load_json_payload,
        extract_json_result=extract_json_result,
        assert_verify_json_result=assert_verify_json_result,
        assert_command_json_result=assert_command_json_result,
        assert_command_json_error=assert_command_json_error,
    )
    _append_wrapper_cmd_verify_json_guard(errors, ctx)
    _append_wrapper_verify_json_guard(errors, ctx)
    for case in _VERIFY_INVALID_CASES:
        _append_wrapper_verify_invalid_json_case(errors, ctx, case=case)
