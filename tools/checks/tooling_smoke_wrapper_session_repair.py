from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


JsonCallable = Callable[..., Any]

_SESSION_FILE_RELATIVE_PATH = r"target\mvp\last_session.json"
_SESSION_REPAIR_NOTICE = (
    rf"[mvp-wrapper] session repair => dropped invalid {_SESSION_FILE_RELATIVE_PATH}"
)
_SESSION_NONE_NOTICE = rf"[mvp-wrapper] session => none path={_SESSION_FILE_RELATIVE_PATH}"


@dataclass(frozen=True)
class WrapperSessionRepairContext:
    repo_root: Path
    python_executable: str
    subprocess_module: Any
    load_json_payload: JsonCallable
    assert_json_null_result: JsonCallable


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


def _write_invalid_session_file(wrapper_session_file: Path) -> None:
    wrapper_session_file.parent.mkdir(parents=True, exist_ok=True)
    wrapper_session_file.write_text("{broken", encoding="utf-8")


def _append_python_session_after_corrupt(
    errors: list[str],
    ctx: WrapperSessionRepairContext,
    *,
    wrapper_session_file: Path,
) -> None:
    _write_invalid_session_file(wrapper_session_file)
    result = ctx.subprocess_module.run(
        _py_command(ctx.python_executable, "session"),
        cwd=ctx.repo_root,
        capture_output=True,
        text=True,
    )
    output = _collect_output(result)
    if result.returncode != 0:
        errors.append(
            f"mvp-wrapper-session-after-corrupt 执行失败: exit={result.returncode}"
        )
    elif _SESSION_REPAIR_NOTICE not in output:
        errors.append("mvp-wrapper-session-after-corrupt 输出缺少损坏会话修复提示")
    elif _SESSION_NONE_NOTICE not in output:
        errors.append("mvp-wrapper-session-after-corrupt 输出缺少 none/path")
    elif wrapper_session_file.exists():
        errors.append("mvp-wrapper-session-after-corrupt 未移除损坏会话文件")


def _append_ps1_session_after_corrupt_json(
    errors: list[str],
    ctx: WrapperSessionRepairContext,
    *,
    wrapper_session_file: Path,
) -> None:
    _write_invalid_session_file(wrapper_session_file)
    result = ctx.subprocess_module.run(
        _ps1_command("session", "--json"),
        cwd=ctx.repo_root,
        capture_output=True,
        text=True,
    )
    output = _collect_output(result)
    payload = ctx.load_json_payload(
        result,
        errors,
        "mvp-wrapper-ps1-session-after-corrupt-json",
        expected_exit=0,
    )
    ctx.assert_json_null_result(
        payload,
        errors,
        "mvp-wrapper-ps1-session-after-corrupt-json",
        "session",
    )
    if _SESSION_REPAIR_NOTICE not in output:
        errors.append("mvp-wrapper-ps1-session-after-corrupt-json missing repair notice")
    elif wrapper_session_file.exists():
        errors.append(
            "mvp-wrapper-ps1-session-after-corrupt-json did not remove invalid file"
        )


def _append_cmd_session_after_ps1_repair(
    errors: list[str],
    ctx: WrapperSessionRepairContext,
) -> None:
    result = ctx.subprocess_module.run(
        _cmd_command("session"),
        cwd=ctx.repo_root,
        capture_output=True,
        text=True,
    )
    output = _collect_output(result)
    if result.returncode != 0:
        errors.append(
            f"mvp-wrapper-cmd-session-after-ps1-repair failed: exit={result.returncode}"
        )
    elif _SESSION_NONE_NOTICE not in output:
        errors.append("mvp-wrapper-cmd-session-after-ps1-repair missing none/path")


def append_wrapper_session_repair_errors(
    errors: list[str],
    *,
    repo_root: Path,
    python_executable: str,
    subprocess_module: Any,
    load_json_payload: JsonCallable,
    assert_json_null_result: JsonCallable,
) -> None:
    ctx = WrapperSessionRepairContext(
        repo_root=repo_root,
        python_executable=python_executable,
        subprocess_module=subprocess_module,
        load_json_payload=load_json_payload,
        assert_json_null_result=assert_json_null_result,
    )
    wrapper_session_file = ctx.repo_root / "target" / "mvp" / "last_session.json"
    _append_python_session_after_corrupt(
        errors,
        ctx,
        wrapper_session_file=wrapper_session_file,
    )
    _append_ps1_session_after_corrupt_json(
        errors,
        ctx,
        wrapper_session_file=wrapper_session_file,
    )
    _append_cmd_session_after_ps1_repair(errors, ctx)
