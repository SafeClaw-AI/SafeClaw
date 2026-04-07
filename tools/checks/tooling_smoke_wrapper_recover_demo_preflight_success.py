from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


JsonCallable = Callable[..., Any]
AssertionCallable = Callable[..., Any]

_RECOVER_DEMO_TASK_ID = "task-wrapper-recover-demo-json"
_RECOVER_DEMO_JSON_LABEL = "mvp-wrapper-recover-demo-preflight-json"
_RECOVER_DEMO_PREFLIGHT_LABEL = "mvp-wrapper-recover-demo-preflight-json preflight"
_RECOVER_DEMO_PREVIEW_OUTPUT = "target/mvp/recover-demo-preflight-json.txt"
_RECOVER_DEMO_MISSING_REMEMBERED_SESSION_ERROR = (
    "mvp-wrapper-recover-demo-preflight-json missing remembered_session task-wrapper-recover-demo-json"
)
_RECOVER_DEMO_MISSING_SESSION_ALIAS_ERROR = (
    "mvp-wrapper-recover-demo-preflight-json missing session alias task-wrapper-recover-demo-json"
)
_RECOVER_DEMO_SOURCE_HINTS = [
    ("preflight", {"permission_context": "prepared-action"}),
    (
        "seed-crash",
        {
            "db": "default",
            "output": "flag",
            "owner_id": "default",
            "task_context": "flag",
        },
    ),
    (
        "recover",
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
class WrapperRecoverDemoPreflightSuccessContext:
    python_executable: str
    assert_command_json_result: JsonCallable
    assert_matching_session_alias: AssertionCallable
    assert_step_source_hints: AssertionCallable
    assert_preflight_json_result: AssertionCallable


def _py_command(python_executable: str, *args: str) -> list[str]:
    return [python_executable, "tools/mvp/safeclaw_mvp.py", *args]


def _append_recover_demo_preflight_json_errors(
    errors: list[str],
    ctx: WrapperRecoverDemoPreflightSuccessContext,
) -> None:
    result = ctx.assert_command_json_result(
        _py_command(
            ctx.python_executable,
            "recover-demo",
            "--task-id",
            _RECOVER_DEMO_TASK_ID,
            "--output",
            _RECOVER_DEMO_PREVIEW_OUTPUT,
            "--preflight",
            "--json",
        ),
        errors,
        _RECOVER_DEMO_JSON_LABEL,
        "recover-demo",
    )
    if result is None:
        return

    steps = result.get("steps") or []
    session = result.get("session") or {}
    remembered_session = result.get("remembered_session") or {}
    if [step.get("action") for step in steps] != [
        "preflight",
        "seed-crash",
        "recover",
        "report",
    ]:
        errors.append("mvp-wrapper-recover-demo-preflight-json step sequence is incorrect")
    elif remembered_session.get("task_id") != _RECOVER_DEMO_TASK_ID:
        errors.append(_RECOVER_DEMO_MISSING_REMEMBERED_SESSION_ERROR)
    elif session.get("task_id") != _RECOVER_DEMO_TASK_ID:
        errors.append(_RECOVER_DEMO_MISSING_SESSION_ALIAS_ERROR)
    else:
        ctx.assert_matching_session_alias(result, errors, _RECOVER_DEMO_JSON_LABEL)
        ctx.assert_step_source_hints(
            steps,
            errors,
            _RECOVER_DEMO_JSON_LABEL,
            _RECOVER_DEMO_SOURCE_HINTS,
        )

    ctx.assert_preflight_json_result(
        result.get("preflight"),
        errors,
        _RECOVER_DEMO_PREFLIGHT_LABEL,
        expected_requested_action="recover-demo",
        expected_known=True,
        expected_action_class="local-action",
        expected_tier="TIER_1",
        expected_writes_state=True,
        expected_permission_context_source="prepared-action",
        expected_target_scope="scope:target/mvp/recover-demo-preflight-json.txt",
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


def append_wrapper_recover_demo_preflight_success_errors(
    errors: list[str],
    *,
    python_executable: str,
    assert_command_json_result: JsonCallable,
    assert_matching_session_alias: AssertionCallable,
    assert_step_source_hints: AssertionCallable,
    assert_preflight_json_result: AssertionCallable,
) -> None:
    ctx = WrapperRecoverDemoPreflightSuccessContext(
        python_executable=python_executable,
        assert_command_json_result=assert_command_json_result,
        assert_matching_session_alias=assert_matching_session_alias,
        assert_step_source_hints=assert_step_source_hints,
        assert_preflight_json_result=assert_preflight_json_result,
    )
    _append_recover_demo_preflight_json_errors(errors, ctx)
