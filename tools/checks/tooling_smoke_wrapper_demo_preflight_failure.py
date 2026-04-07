from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


JsonCallable = Callable[..., Any]
AssertionCallable = Callable[..., Any]

_ENFORCED_TASK_ID = "task-wrapper-demo-enforced"
_ENFORCED_OUTPUT_PATH = "target/mvp/demo-enforced.txt"
_ENFORCED_LABEL = "mvp-wrapper-demo-enforced-json"
_ENFORCED_PREFLIGHT_LABEL = "mvp-wrapper-demo-enforced-json preflight"
_ENFORCED_MISSING_PREFLIGHT_PAYLOAD_ERROR = (
    "mvp-wrapper-demo-enforced-json missing preflight payload"
)
_ENFORCED_MISSING_ISOLATED_STEP_ERROR = (
    "mvp-wrapper-demo-enforced-json missing isolated preflight step"
)
_ENFORCED_MISSING_STEP_ACTION_ERROR = (
    "mvp-wrapper-demo-enforced-json missing preflight step action"
)
_AI_TASK_ID = "task-wrapper-demo-preflight-ai"
_AI_OUTPUT_PATH = "target/mvp/demo-preflight-ai.txt"
_AI_LABEL = "mvp-wrapper-demo-preflight-ai-json"
_AI_PREFLIGHT_LABEL = "mvp-wrapper-demo-preflight-ai-json preflight"
_AI_MISSING_PREFLIGHT_PAYLOAD_ERROR = (
    "mvp-wrapper-demo-preflight-ai-json missing preflight payload"
)
_AI_MISSING_ISOLATED_STEP_ERROR = (
    "mvp-wrapper-demo-preflight-ai-json missing isolated preflight step"
)
_AI_MISSING_STEP_ACTION_ERROR = (
    "mvp-wrapper-demo-preflight-ai-json missing preflight step action"
)


@dataclass(frozen=True)
class WrapperDemoPreflightFailureContext:
    python_executable: str
    assert_command_json_error: JsonCallable
    assert_preflight_json_result: AssertionCallable


def _py_command(python_executable: str, *args: str) -> list[str]:
    return [python_executable, "tools/mvp/safeclaw_mvp.py", *args]


def _assert_isolated_preflight_step(
    details: dict[str, object],
    errors: list[str],
    *,
    missing_step_error: str,
    missing_step_action_error: str,
) -> None:
    steps = details.get("steps") or []
    if not isinstance(steps, list) or len(steps) != 1 or not isinstance(steps[0], dict):
        errors.append(missing_step_error)
    elif steps[0].get("action") != "preflight":
        errors.append(missing_step_action_error)


def _append_demo_enforced_preflight_errors(
    errors: list[str],
    ctx: WrapperDemoPreflightFailureContext,
) -> None:
    details = ctx.assert_command_json_error(
        _py_command(
            ctx.python_executable,
            "demo",
            "--task-id",
            _ENFORCED_TASK_ID,
            "--output",
            _ENFORCED_OUTPUT_PATH,
            "--enforce-permission",
            "--json",
        ),
        errors,
        _ENFORCED_LABEL,
        "demo",
        expected_exit=1,
        expected_error_message_substring="failed step=preflight",
        expected_top_level_error_code="preflight-blocked",
        expected_top_level_error_reason="write_scope_requires_confirmation",
        expect_top_level_error_error_code_absent=True,
        expected_top_level_error_degradation_mode="local_only_ok",
        expected_top_level_error_requires_model=False,
        expected_top_level_error_requires_sidecar=False,
        expected_top_level_error_requested_action="demo",
        expected_code="preflight-blocked",
        expected_failed_step="preflight",
        expected_preflight_requested_action="demo",
        expected_preflight_reason="write_scope_requires_confirmation",
        expect_preflight_error_code_absent=True,
        expected_preflight_summary_substring="action=demo",
        expect_top_level_error_summary_matches_preflight=True,
    )
    if not isinstance(details, dict):
        return

    preflight_payload = details.get("preflight")
    if not isinstance(preflight_payload, dict):
        errors.append(_ENFORCED_MISSING_PREFLIGHT_PAYLOAD_ERROR)
    else:
        ctx.assert_preflight_json_result(
            preflight_payload,
            errors,
            _ENFORCED_PREFLIGHT_LABEL,
            expected_requested_action="demo",
            expected_known=True,
            expected_action_class="local-action",
            expected_tier="TIER_1",
            expected_writes_state=True,
            expected_permission_context_source="prepared-action",
            expected_target_scope="scope:target/mvp/demo-enforced.txt",
            expected_requires_write=True,
            expected_doctor_bypass=False,
            expected_permission_context_applied=True,
            expected_permission_tier="TIER_1",
            expected_permission_policy="confirm",
            expected_permission_reason="write_scope_requires_confirmation",
            expected_permission_enforced=True,
            expected_action_allowed=True,
            expected_action_decision="allow",
            expected_action_reason="current_mvp_action_is_local_only",
            expected_allowed=False,
            expected_decision="confirm",
            expected_offline_ready=True,
            expected_degradation_mode="local_only_ok",
            expected_reason="write_scope_requires_confirmation",
        )

    _assert_isolated_preflight_step(
        details,
        errors,
        missing_step_error=_ENFORCED_MISSING_ISOLATED_STEP_ERROR,
        missing_step_action_error=_ENFORCED_MISSING_STEP_ACTION_ERROR,
    )


def _append_demo_preflight_ai_errors(
    errors: list[str],
    ctx: WrapperDemoPreflightFailureContext,
) -> None:
    details = ctx.assert_command_json_error(
        _py_command(
            ctx.python_executable,
            "demo",
            "--task-id",
            _AI_TASK_ID,
            "--output",
            _AI_OUTPUT_PATH,
            "--preflight",
            "--preflight-action",
            "ai-reason",
            "--json",
        ),
        errors,
        _AI_LABEL,
        "demo",
        expected_exit=1,
        expected_error_message_substring="failed step=preflight",
        expected_top_level_error_code="preflight-blocked",
        expected_top_level_error_reason="ERR_AI_PROVIDER_UNAVAILABLE",
        expected_top_level_error_error_code="ERR_AI_PROVIDER_UNAVAILABLE",
        expected_top_level_error_degradation_mode="provider_unavailable",
        expected_top_level_error_requires_model=True,
        expected_top_level_error_requires_sidecar=True,
        expected_top_level_error_requested_action="ai-reason",
        expected_code="preflight-blocked",
        expected_failed_step="preflight",
        expected_preflight_requested_action="ai-reason",
        expected_preflight_reason="ERR_AI_PROVIDER_UNAVAILABLE",
        expected_preflight_error_code="ERR_AI_PROVIDER_UNAVAILABLE",
        expected_preflight_summary_substring="action=ai-reason",
        expect_top_level_error_summary_matches_preflight=True,
    )
    if not isinstance(details, dict):
        return

    preflight_payload = details.get("preflight")
    if not isinstance(preflight_payload, dict):
        errors.append(_AI_MISSING_PREFLIGHT_PAYLOAD_ERROR)
    else:
        ctx.assert_preflight_json_result(
            preflight_payload,
            errors,
            _AI_PREFLIGHT_LABEL,
            expected_requested_action="ai-reason",
            expected_known=True,
            expected_action_class="ai-action",
            expected_tier="TIER_2",
            expected_writes_state=False,
            expected_permission_context_source="prepared-action",
            expected_target_scope="scope:target/mvp/demo-preflight-ai.txt",
            expected_requires_write=True,
            expected_doctor_bypass=False,
            expected_permission_context_applied=True,
            expected_permission_tier="TIER_1",
            expected_permission_policy="confirm",
            expected_permission_reason="write_scope_requires_confirmation",
            expected_permission_enforced=False,
            expected_action_allowed=False,
            expected_action_decision="deny",
            expected_action_reason="ERR_AI_PROVIDER_UNAVAILABLE",
            expected_allowed=False,
            expected_decision="deny",
            expected_offline_ready=False,
            expected_degradation_mode="provider_unavailable",
            expected_reason="ERR_AI_PROVIDER_UNAVAILABLE",
            expected_requires_model=True,
            expected_requires_sidecar=True,
            expected_error_code="ERR_AI_PROVIDER_UNAVAILABLE",
        )

    _assert_isolated_preflight_step(
        details,
        errors,
        missing_step_error=_AI_MISSING_ISOLATED_STEP_ERROR,
        missing_step_action_error=_AI_MISSING_STEP_ACTION_ERROR,
    )


def append_wrapper_demo_preflight_failure_errors(
    errors: list[str],
    *,
    python_executable: str,
    assert_command_json_error: JsonCallable,
    assert_preflight_json_result: AssertionCallable,
) -> None:
    ctx = WrapperDemoPreflightFailureContext(
        python_executable=python_executable,
        assert_command_json_error=assert_command_json_error,
        assert_preflight_json_result=assert_preflight_json_result,
    )
    _append_demo_enforced_preflight_errors(errors, ctx)
    _append_demo_preflight_ai_errors(errors, ctx)
