from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


JsonCallable = Callable[..., Any]
AssertionCallable = Callable[..., Any]

_TEXT_TASK_ID = "task-wrapper-demo-preflight"
_JSON_TASK_ID = "task-wrapper-demo-json"
_TEXT_LABEL = "mvp-wrapper-demo-preflight"
_JSON_LABEL = "mvp-wrapper-demo-preflight-json"
_TEXT_OUTPUT_PATH = "target/mvp/demo-preflight.txt"
_JSON_OUTPUT_PATH = "target/mvp/demo-preflight-json.txt"
_JSON_PREFLIGHT_LABEL = "mvp-wrapper-demo-preflight-json preflight"
_MISSING_REMEMBERED_SESSION_ERROR = (
    "mvp-wrapper-demo-preflight-json 缺少 remembered_session task-wrapper-demo-json"
)
_MISSING_SESSION_ALIAS_ERROR = (
    "mvp-wrapper-demo-preflight-json 缺少兼容 session task-wrapper-demo-json"
)
_TEXT_PREFLIGHT_SUMMARY = (
    "[mvp-wrapper] preflight => action=demo known=true class=local-action "
    "tier=TIER_1 writes_state=true target_scope=scope:target/mvp/demo-preflight.txt "
    "requires_write=true doctor_bypass=false perm_ctx=true "
    "perm_ctx_src=prepared-action enforce_perm=false perm=confirm perm_tier=TIER_1 "
    "perm_reason=write_scope_requires_confirmation decision=allow allowed=true "
    "offline_ready=true requires_model=false requires_sidecar=false "
    "degradation=local_only_ok reason=current_mvp_action_is_local_only"
)
_JSON_SOURCE_HINTS = [
    ("preflight", {"permission_context": "prepared-action"}),
    (
        "run",
        {
            "db": "default",
            "output": "flag",
            "owner_id": "default",
            "task_context": "flag",
        },
    ),
    (
        "status",
        {
            "db": "session",
            "output": "flag",
            "owner_id": "session",
            "task_context": "flag",
        },
    ),
    (
        "report",
        {
            "db": "session",
            "output": "flag",
            "owner_id": "session",
            "task_context": "flag",
        },
    ),
]


@dataclass(frozen=True)
class WrapperDemoPreflightSuccessContext:
    repo_root: Path
    python_executable: str
    subprocess_module: Any
    assert_command_json_result: JsonCallable
    assert_matching_session_alias: AssertionCallable
    assert_step_source_hints: AssertionCallable
    assert_preflight_json_result: AssertionCallable


def _py_command(python_executable: str, *args: str) -> list[str]:
    return [python_executable, "tools/mvp/safeclaw_mvp.py", *args]


def _append_demo_preflight_text_errors(
    errors: list[str],
    ctx: WrapperDemoPreflightSuccessContext,
) -> None:
    wrapper_demo_preflight = ctx.subprocess_module.run(
        _py_command(
            ctx.python_executable,
            "demo",
            "--task-id",
            _TEXT_TASK_ID,
            "--output",
            _TEXT_OUTPUT_PATH,
            "--preflight",
        ),
        cwd=ctx.repo_root,
        capture_output=True,
        text=True,
    )
    output = (wrapper_demo_preflight.stdout or "") + (wrapper_demo_preflight.stderr or "")
    if wrapper_demo_preflight.returncode != 0:
        errors.append(f"{_TEXT_LABEL} failed: exit={wrapper_demo_preflight.returncode}")
        return
    if "[mvp-wrapper] demo => preflight" not in output:
        errors.append("mvp-wrapper-demo-preflight missing preflight step marker")
        return
    if _TEXT_PREFLIGHT_SUMMARY not in output:
        errors.append("mvp-wrapper-demo-preflight missing preflight summary")
        return
    if "[mvp-wrapper] demo => run" not in output:
        errors.append("mvp-wrapper-demo-preflight missing run step marker")
        return
    if "[mvp-wrapper] demo => status" not in output:
        errors.append("mvp-wrapper-demo-preflight missing status step marker")
        return
    if "[mvp-wrapper] demo => report" not in output:
        errors.append("mvp-wrapper-demo-preflight missing report step marker")


def _append_demo_preflight_json_errors(
    errors: list[str],
    ctx: WrapperDemoPreflightSuccessContext,
) -> None:
    result = ctx.assert_command_json_result(
        _py_command(
            ctx.python_executable,
            "demo",
            "--task-id",
            _JSON_TASK_ID,
            "--output",
            _JSON_OUTPUT_PATH,
            "--preflight",
            "--json",
        ),
        errors,
        _JSON_LABEL,
        "demo",
    )
    if result is None:
        return
    steps = result.get("steps") or []
    session = result.get("session") or {}
    remembered_session = result.get("remembered_session") or {}
    if [step.get("action") for step in steps] != ["preflight", "run", "status", "report"]:
        errors.append("mvp-wrapper-demo-preflight-json step sequence is incorrect")
    elif remembered_session.get("task_id") != _JSON_TASK_ID:
        errors.append(_MISSING_REMEMBERED_SESSION_ERROR)
    elif session.get("task_id") != _JSON_TASK_ID:
        errors.append(_MISSING_SESSION_ALIAS_ERROR)
    else:
        ctx.assert_matching_session_alias(result, errors, _JSON_LABEL)
        ctx.assert_step_source_hints(steps, errors, _JSON_LABEL, _JSON_SOURCE_HINTS)

    ctx.assert_preflight_json_result(
        result.get("preflight"),
        errors,
        _JSON_PREFLIGHT_LABEL,
        expected_requested_action="demo",
        expected_known=True,
        expected_action_class="local-action",
        expected_tier="TIER_1",
        expected_writes_state=True,
        expected_permission_context_source="prepared-action",
        expected_target_scope="scope:target/mvp/demo-preflight-json.txt",
        expected_requires_write=True,
        expected_doctor_bypass=False,
        expected_permission_context_applied=True,
        expected_permission_tier="TIER_1",
        expected_permission_policy="confirm",
        expected_permission_reason="write_scope_requires_confirmation",
        expected_permission_enforced=False,
        expected_action_allowed=True,
        expected_action_decision="allow",
        expected_action_reason="current_mvp_action_is_local_only",
        expected_allowed=True,
        expected_decision="allow",
        expected_offline_ready=True,
        expected_degradation_mode="local_only_ok",
        expected_reason="current_mvp_action_is_local_only",
    )


def append_wrapper_demo_preflight_success_errors(
    errors: list[str],
    *,
    repo_root: Path,
    python_executable: str,
    subprocess_module: Any,
    assert_command_json_result: JsonCallable,
    assert_matching_session_alias: AssertionCallable,
    assert_step_source_hints: AssertionCallable,
    assert_preflight_json_result: AssertionCallable,
) -> None:
    ctx = WrapperDemoPreflightSuccessContext(
        repo_root=repo_root,
        python_executable=python_executable,
        subprocess_module=subprocess_module,
        assert_command_json_result=assert_command_json_result,
        assert_matching_session_alias=assert_matching_session_alias,
        assert_step_source_hints=assert_step_source_hints,
        assert_preflight_json_result=assert_preflight_json_result,
    )
    _append_demo_preflight_text_errors(errors, ctx)
    _append_demo_preflight_json_errors(errors, ctx)
