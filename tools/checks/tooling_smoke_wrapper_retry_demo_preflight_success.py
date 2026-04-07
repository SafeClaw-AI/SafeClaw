from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


JsonCallable = Callable[..., Any]
AssertionCallable = Callable[..., Any]

_RETRY_DEMO_TASK_ID = "task-wrapper-retry-demo-json"
_RETRY_DEMO_JSON_LABEL = "mvp-wrapper-retry-demo-preflight-json"
_RETRY_DEMO_PREFLIGHT_LABEL = "mvp-wrapper-retry-demo-preflight-json preflight"
_RETRY_DEMO_PREVIEW_OUTPUT = "target/mvp/retry-demo-preflight-json.txt"
_RETRY_DEMO_MISSING_REMEMBERED_SESSION_ERROR = (
    "mvp-wrapper-retry-demo-preflight-json missing remembered_session task-wrapper-retry-demo-json"
)
_RETRY_DEMO_MISSING_SESSION_ALIAS_ERROR = (
    "mvp-wrapper-retry-demo-preflight-json missing session alias task-wrapper-retry-demo-json"
)
_RETRY_DEMO_SOURCE_HINTS = [
    ("preflight", {"permission_context": "prepared-action"}),
    (
        "seed-failed",
        {
            "db": "default",
            "output": "flag",
            "owner_id": "default",
            "task_context": "flag",
        },
    ),
    (
        "retry",
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
class WrapperRetryDemoPreflightSuccessContext:
    python_executable: str
    assert_command_json_result: JsonCallable
    assert_matching_session_alias: AssertionCallable
    assert_step_source_hints: AssertionCallable
    assert_preflight_json_result: AssertionCallable


def _py_command(python_executable: str, *args: str) -> list[str]:
    return [python_executable, "tools/mvp/safeclaw_mvp.py", *args]


def _append_retry_demo_preflight_json_errors(
    errors: list[str],
    ctx: WrapperRetryDemoPreflightSuccessContext,
) -> None:
    result = ctx.assert_command_json_result(
        _py_command(
            ctx.python_executable,
            "retry-demo",
            "--task-id",
            _RETRY_DEMO_TASK_ID,
            "--output",
            _RETRY_DEMO_PREVIEW_OUTPUT,
            "--preflight",
            "--json",
        ),
        errors,
        _RETRY_DEMO_JSON_LABEL,
        "retry-demo",
    )
    if result is None:
        return

    steps = result.get("steps") or []
    session = result.get("session") or {}
    remembered_session = result.get("remembered_session") or {}
    if [step.get("action") for step in steps] != [
        "preflight",
        "seed-failed",
        "retry",
        "report",
    ]:
        errors.append("mvp-wrapper-retry-demo-preflight-json step sequence is incorrect")
    elif remembered_session.get("task_id") != _RETRY_DEMO_TASK_ID:
        errors.append(_RETRY_DEMO_MISSING_REMEMBERED_SESSION_ERROR)
    elif session.get("task_id") != _RETRY_DEMO_TASK_ID:
        errors.append(_RETRY_DEMO_MISSING_SESSION_ALIAS_ERROR)
    else:
        ctx.assert_matching_session_alias(result, errors, _RETRY_DEMO_JSON_LABEL)
        ctx.assert_step_source_hints(
            steps,
            errors,
            _RETRY_DEMO_JSON_LABEL,
            _RETRY_DEMO_SOURCE_HINTS,
        )

    ctx.assert_preflight_json_result(
        result.get("preflight"),
        errors,
        _RETRY_DEMO_PREFLIGHT_LABEL,
        expected_requested_action="retry-demo",
        expected_known=True,
        expected_action_class="local-action",
        expected_tier="TIER_1",
        expected_writes_state=True,
        expected_permission_context_source="prepared-action",
        expected_target_scope="scope:target/mvp/retry-demo-preflight-json.txt",
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


def append_wrapper_retry_demo_preflight_success_errors(
    errors: list[str],
    *,
    python_executable: str,
    assert_command_json_result: JsonCallable,
    assert_matching_session_alias: AssertionCallable,
    assert_step_source_hints: AssertionCallable,
    assert_preflight_json_result: AssertionCallable,
) -> None:
    ctx = WrapperRetryDemoPreflightSuccessContext(
        python_executable=python_executable,
        assert_command_json_result=assert_command_json_result,
        assert_matching_session_alias=assert_matching_session_alias,
        assert_step_source_hints=assert_step_source_hints,
        assert_preflight_json_result=assert_preflight_json_result,
    )
    _append_retry_demo_preflight_json_errors(errors, ctx)
