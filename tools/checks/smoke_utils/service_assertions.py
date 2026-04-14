"""Service-related assertion utilities for smoke tests."""

from __future__ import annotations

from .json_assertions import assert_matching_session_alias, assert_step_source_hints
from .service_status_assertions import (
    assert_service_status_json_result as _assert_service_status_json_result,
)


def assert_service_demo_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
) -> None:
    """Assert service-demo command JSON result structure."""
    if result is None:
        return

    resolved_run = result.get("resolved_run") or {}
    resolved_governance = result.get("resolved_governance") or {}
    confirmation_governance = result.get("confirmation_governance") or {}
    resolved_tasks = result.get("resolved_tasks") or []
    confirmation_tasks = result.get("confirmation_tasks") or []
    captured_output = str(result.get("captured_output") or "")
    for checker in (
        _check_service_demo_base_fields(result, resolved_run, name),
        _check_service_demo_governance_fields(
            resolved_governance,
            confirmation_governance,
            name,
        ),
        _check_service_demo_task_fields(
            resolved_tasks,
            confirmation_tasks,
            name,
        ),
        _check_service_demo_output_fields(result, captured_output, name),
    ):
        if checker is not None:
            errors.append(checker)
            return


def _check_service_demo_base_fields(
    result: dict[str, object],
    resolved_run: object,
    name: str,
) -> str | None:
    return _first_default_service_status_error(
        (
            (
                result.get("example") != "worker_service_governance_demo",
                f"{name} missing example name",
            ),
            (
                not isinstance(resolved_run, dict) or resolved_run.get("executed") != 2,
                f"{name} missing resolved_run.executed=2",
            ),
            (resolved_run.get("parked") != 0, f"{name} missing resolved_run.parked=0"),
        )
    )


def _check_service_demo_governance_fields(
    resolved_governance: object,
    confirmation_governance: object,
    name: str,
) -> str | None:
    return _first_default_service_status_error(
        (
            (
                not isinstance(resolved_governance, dict)
                or resolved_governance.get("resolved") != 2,
                f"{name} missing resolved_governance.resolved=2",
            ),
            (
                resolved_governance.get("confirmation") != 0,
                f"{name} missing resolved_governance.confirmation=0",
            ),
            (
                not isinstance(confirmation_governance, dict)
                or confirmation_governance.get("confirmation") != 1,
                f"{name} missing confirmation_governance.confirmation=1",
            ),
            (
                confirmation_governance.get("manual_review") != 0,
                f"{name} missing confirmation_governance.manual_review=0",
            ),
        )
    )


def _check_service_demo_task_fields(
    resolved_tasks: object,
    confirmation_tasks: object,
    name: str,
) -> str | None:
    return _first_default_service_status_error(
        (
            (
                not isinstance(resolved_tasks, list)
                or "task-worker-service-governance-a" not in resolved_tasks,
                f"{name} missing resolved task a",
            ),
            (
                "task-worker-service-governance-b" not in resolved_tasks,
                f"{name} missing resolved task b",
            ),
            (
                not isinstance(confirmation_tasks, list)
                or "task-worker-service-governance-confirmation" not in confirmation_tasks,
                f"{name} missing confirmation task",
            ),
        )
    )


def _check_service_demo_output_fields(
    result: dict[str, object],
    captured_output: str,
    name: str,
) -> str | None:
    return _first_default_service_status_error(
        (
            (
                not str(result.get("db_path") or "").lower().endswith(".db"),
                f"{name} missing db_path",
            ),
            (
                "[demo] service governance resolved => total=2 resolved=2 confirmation=0 manual_review=0"
                not in captured_output,
                f"{name} missing resolved governance output",
            ),
            (
                "[demo] service governance confirmation => total=1 resolved=0 confirmation=1 manual_review=0"
                not in captured_output,
                f"{name} missing confirmation governance output",
            ),
        )
    )


def assert_service_status_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    expected_db: str,
    expected_db_source: str,
    expected_task_id: str,
    expected_limit: int = 5,
    expected_target_scope: str | None = None,
    expected_requires_write: bool | None = None,
    expected_doctor_bypass: bool | None = None,
    expected_permission_tier: str | None = None,
    expected_permission_policy: str | None = None,
    expected_permission_reason: str | None = None,
    expected_lease_state: str | None = None,
    expected_lease_freshness: str | None = None,
    expected_lease_owner_id: str | None = None,
    expected_lease_fencing_token: int | None = None,
    expected_heartbeat_freshness: str | None = None,
    expected_heartbeat_status: str | None = None,
    expected_heartbeat_interval_ms: int | None = None,
    expected_heartbeat_event_driven: bool | None = None,
    expected_heartbeat_reason: str | None = None,
    expect_heartbeat_latest_updated_at_present: bool = False,
    expect_heartbeat_latest_updated_at_absent: bool = False,
    expect_heartbeat_latest_age_ms_present: bool = False,
    expect_heartbeat_latest_age_ms_absent: bool = False,
    expected_next_action: str | None = None,
    expected_next_command: str | None = None,
    expected_next_reason: str | None = None,
    expected_next_blocker: str | None = None,
    expected_next_summary: str | None = None,
    expected_coordination_status: str | None = None,
    expected_coordination_reason: str | None = None,
    expected_coordination_summary: str | None = None,
    expected_service_coordination_status: str | None = None,
    expected_service_coordination_reason: str | None = None,
    expected_service_coordination_summary: str | None = None,
) -> None:
    _assert_service_status_json_result(
        result,
        errors,
        name,
        expected_db=expected_db,
        expected_db_source=expected_db_source,
        expected_task_id=expected_task_id,
        expected_limit=expected_limit,
        expected_target_scope=expected_target_scope,
        expected_requires_write=expected_requires_write,
        expected_doctor_bypass=expected_doctor_bypass,
        expected_permission_tier=expected_permission_tier,
        expected_permission_policy=expected_permission_policy,
        expected_permission_reason=expected_permission_reason,
        expected_lease_state=expected_lease_state,
        expected_lease_freshness=expected_lease_freshness,
        expected_lease_owner_id=expected_lease_owner_id,
        expected_lease_fencing_token=expected_lease_fencing_token,
        expected_heartbeat_freshness=expected_heartbeat_freshness,
        expected_heartbeat_status=expected_heartbeat_status,
        expected_heartbeat_interval_ms=expected_heartbeat_interval_ms,
        expected_heartbeat_event_driven=expected_heartbeat_event_driven,
        expected_heartbeat_reason=expected_heartbeat_reason,
        expect_heartbeat_latest_updated_at_present=expect_heartbeat_latest_updated_at_present,
        expect_heartbeat_latest_updated_at_absent=expect_heartbeat_latest_updated_at_absent,
        expect_heartbeat_latest_age_ms_present=expect_heartbeat_latest_age_ms_present,
        expect_heartbeat_latest_age_ms_absent=expect_heartbeat_latest_age_ms_absent,
        expected_next_action=expected_next_action,
        expected_next_command=expected_next_command,
        expected_next_reason=expected_next_reason,
        expected_next_blocker=expected_next_blocker,
        expected_next_summary=expected_next_summary,
        expected_coordination_status=expected_coordination_status,
        expected_coordination_reason=expected_coordination_reason,
        expected_coordination_summary=expected_coordination_summary,
        expected_service_coordination_status=expected_service_coordination_status,
        expected_service_coordination_reason=expected_service_coordination_reason,
        expected_service_coordination_summary=expected_service_coordination_summary,
    )


def _assert_combo_result_common(
    result: dict[str, object],
    errors: list[str],
    name: str,
    *,
    expected_task_id: str,
    expected_steps: list[str],
) -> list[dict[str, object]] | None:
    steps = result.get("steps") or []
    remembered_session = result.get("remembered_session") or {}
    session = result.get("session") or {}

    if not _assert_combo_step_sequence(steps, errors, name, expected_steps=expected_steps):
        return None

    if not _assert_combo_session_aliases(
        remembered_session,
        session,
        errors,
        name,
        expected_task_id=expected_task_id,
    ):
        return None

    assert_matching_session_alias(result, errors, name)
    return steps


def _assert_combo_step_sequence(
    steps: object,
    errors: list[str],
    name: str,
    *,
    expected_steps: list[str],
) -> bool:
    if not isinstance(steps, list) or [step.get("action") for step in steps] != expected_steps:
        errors.append(f"{name} step sequence is incorrect")
        return False
    return True


def _assert_combo_session_aliases(
    remembered_session: object,
    session: object,
    errors: list[str],
    name: str,
    *,
    expected_task_id: str,
) -> bool:
    if (
        not isinstance(remembered_session, dict)
        or remembered_session.get("task_id") != expected_task_id
    ):
        errors.append(f"{name} missing remembered_session {expected_task_id}")
        return False

    if not isinstance(session, dict) or session.get("task_id") != expected_task_id:
        errors.append(f"{name} missing session alias {expected_task_id}")
        return False

    return True


def _assert_nested_combo_payload(
    payload: object,
    errors: list[str],
    name: str,
    *,
    payload_name: str,
    prepared_action: str,
    expected_task_id: str,
    expected_saved_session_task_id: str | None,
    expected_decision: str | None = None,
) -> bool:
    if not isinstance(payload, dict):
        errors.append(f"{name} missing nested {payload_name} payload")
        return False

    return all(
        (
            _check_nested_combo_prepared(
                payload,
                errors,
                name,
                payload_name=payload_name,
                prepared_action=prepared_action,
                expected_decision=expected_decision,
            ),
            _check_nested_combo_saved_session(
                payload,
                errors,
                name,
                payload_name=payload_name,
                expected_saved_session_task_id=expected_saved_session_task_id,
            ),
            _check_nested_combo_remembered_session(
                payload,
                errors,
                name,
                payload_name=payload_name,
                expected_task_id=expected_task_id,
            ),
        )
    )


def _check_nested_combo_prepared(
    payload: dict[str, object],
    errors: list[str],
    name: str,
    *,
    payload_name: str,
    prepared_action: str,
    expected_decision: str | None,
) -> bool:
    prepared = payload.get("prepared") or []

    if not isinstance(prepared, list) or not prepared or prepared[0] != prepared_action:
        errors.append(f"{name} nested {payload_name} missing prepared {prepared_action}")
        return False

    if expected_decision is None:
        return True

    if "--decision" not in prepared:
        errors.append(f"{name} nested {payload_name} missing --decision")
        return False

    decision_index = prepared.index("--decision") + 1
    if decision_index >= len(prepared) or prepared[decision_index] != expected_decision:
        errors.append(
            f"{name} nested {payload_name} missing --decision {expected_decision}"
        )
        return False

    return True


def _check_nested_combo_saved_session(
    payload: dict[str, object],
    errors: list[str],
    name: str,
    *,
    payload_name: str,
    expected_saved_session_task_id: str | None,
) -> bool:
    saved_session = payload.get("saved_session") or {}

    if expected_saved_session_task_id is None:
        if payload.get("saved_session") is None:
            return True
        errors.append(f"{name} nested {payload_name} should not save session")
        return False

    if (
        not isinstance(saved_session, dict)
        or saved_session.get("task_id") != expected_saved_session_task_id
    ):
        errors.append(
            f"{name} nested {payload_name} missing saved_session {expected_saved_session_task_id}"
        )
        return False

    return True


def _check_nested_combo_remembered_session(
    payload: dict[str, object],
    errors: list[str],
    name: str,
    *,
    payload_name: str,
    expected_task_id: str,
) -> bool:
    nested_remembered_session = payload.get("remembered_session") or {}

    if (
        not isinstance(nested_remembered_session, dict)
        or nested_remembered_session.get("task_id") != expected_task_id
    ):
        errors.append(
            f"{name} nested {payload_name} missing remembered_session {expected_task_id}"
        )
        return False

    return True


def _assert_nested_report_payload(
    result: dict[str, object],
    errors: list[str],
    name: str,
    *,
    expected_task_id: str,
) -> None:
    report_payload = result.get("report") or {}
    nested_report_session = report_payload.get("remembered_session") or {}
    prepared_report = report_payload.get("prepared") or []

    if not isinstance(report_payload, dict):
        errors.append(f"{name} missing nested report payload")
        return

    if (
        not isinstance(prepared_report, list)
        or not prepared_report
        or prepared_report[0] != "report"
    ):
        errors.append(f"{name} nested report missing prepared report")
        return

    if (
        not isinstance(nested_report_session, dict)
        or nested_report_session.get("task_id") != expected_task_id
    ):
        errors.append(
            f"{name} nested report missing remembered_session {expected_task_id}"
        )


def _assert_service_status_payload(
    result: dict[str, object],
    errors: list[str],
    name: str,
    *,
    expected_db: str,
    expected_db_source: str,
    expected_task_id: str,
    expected_limit: int,
) -> None:
    service_status = result.get("service_status")

    if not isinstance(service_status, dict):
        errors.append(f"{name} missing service_status payload")
        return

    assert_service_status_json_result(
        service_status,
        errors,
        f"{name} service_status",
        expected_db=expected_db,
        expected_db_source=expected_db_source,
        expected_task_id=expected_task_id,
        expected_limit=expected_limit,
    )


def _assert_service_combo_json_result(
    result: dict[str, object],
    errors: list[str],
    name: str,
    *,
    payload_name: str,
    prepared_action: str,
    expected_task_id: str,
    expected_steps: list[str],
    expected_step_hints: list[tuple[str, dict[str, str]]],
    expected_saved_session_task_id: str | None,
    expect_report_payload: bool,
    expected_db: str,
    expected_db_source: str,
    expected_limit: int,
    expected_decision: str | None = None,
) -> None:
    steps = _assert_combo_result_common(
        result,
        errors,
        name,
        expected_task_id=expected_task_id,
        expected_steps=expected_steps,
    )
    if steps is None:
        return

    payload_ok = _assert_nested_combo_payload(
        result.get(payload_name) or {},
        errors,
        name,
        payload_name=payload_name,
        prepared_action=prepared_action,
        expected_task_id=expected_task_id,
        expected_saved_session_task_id=expected_saved_session_task_id,
        expected_decision=expected_decision,
    )
    if not payload_ok:
        return
    assert_step_source_hints(
        steps[: len(expected_step_hints)],
        errors,
        name,
        expected_step_hints,
    )

    if expect_report_payload:
        _assert_nested_report_payload(
            result,
            errors,
            name,
            expected_task_id=expected_task_id,
        )

    _assert_service_status_payload(
        result,
        errors,
        name,
        expected_db=expected_db,
        expected_db_source=expected_db_source,
        expected_task_id=expected_task_id,
        expected_limit=expected_limit,
    )


def _first_default_service_status_error(
    checks: tuple[tuple[bool, str], ...],
) -> str | None:
    for failed, message in checks:
        if failed:
            return message
    return None


def _check_default_service_status_base_fields(
    result: dict[str, object],
    name: str,
    *,
    expected_db: str,
    expected_db_source: str,
    expected_limit: int,
) -> str | None:
    actual_db = str(result.get("db") or "").replace("\\", "/")
    return _first_default_service_status_error(
        (
            (actual_db != expected_db.replace("\\", "/"), f"{name} missing db={expected_db}"),
            (
                result.get("db_source") != expected_db_source,
                f"{name} missing db_source={expected_db_source}",
            ),
            (result.get("limit") != expected_limit, f"{name} missing limit={expected_limit}"),
            (result.get("current_session") is not None, f"{name} unexpected current_session"),
            (result.get("current_db") is not False, f"{name} missing current_db=false"),
        )
    )


def _check_default_service_status_runtime_fields(
    result: dict[str, object],
    name: str,
) -> str | None:
    runtime_profile = result.get("runtime_profile") or {}
    model_provider = result.get("model_provider") or {}
    sidecar = result.get("sidecar") or {}
    offline_gate = result.get("offline_gate") or {}
    return _first_default_service_status_error(
        (
            (
                not isinstance(runtime_profile, dict)
                or runtime_profile.get("mode") != "local_mvp",
                f"{name} missing runtime_profile.mode=local_mvp",
            ),
            (
                runtime_profile.get("offline_ready") is not True,
                f"{name} missing runtime_profile.offline_ready=true",
            ),
            (
                not isinstance(model_provider, dict)
                or model_provider.get("status") != "not-configured",
                f"{name} missing model_provider.status=not-configured",
            ),
            (
                model_provider.get("degradation_mode") != "local_only_ok",
                f"{name} missing model_provider.degradation_mode=local_only_ok",
            ),
            (
                not isinstance(sidecar, dict)
                or sidecar.get("status") != "not-configured",
                f"{name} missing sidecar.status=not-configured",
            ),
            (
                not isinstance(offline_gate, dict)
                or offline_gate.get("status") != "blocked",
                f"{name} missing offline_gate.status=blocked",
            ),
            (
                offline_gate.get("reason") != "ERR_AI_PROVIDER_UNAVAILABLE",
                f"{name} missing offline_gate.reason=ERR_AI_PROVIDER_UNAVAILABLE",
            ),
            (
                offline_gate.get("summary") != "ai_actions_require_provider",
                f"{name} missing offline_gate.summary=ai_actions_require_provider",
            ),
            (
                offline_gate.get("requested_action") != "ai-reason",
                f"{name} missing offline_gate.requested_action=ai-reason",
            ),
            (
                offline_gate.get("requires_model") is not True,
                f"{name} missing offline_gate.requires_model=true",
            ),
            (
                offline_gate.get("requires_sidecar") is not True,
                f"{name} missing offline_gate.requires_sidecar=true",
            ),
            (
                offline_gate.get("error_code") != "ERR_AI_PROVIDER_UNAVAILABLE",
                f"{name} missing offline_gate.error_code=ERR_AI_PROVIDER_UNAVAILABLE",
            ),
            (
                offline_gate.get("next_command") != "safeclaw.cmd preflight --action ai-reason",
                f"{name} missing offline_gate.next_command",
            ),
        )
    )


def assert_service_run_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    expected_db: str,
    expected_db_source: str,
    expected_task_id: str,
    expected_limit: int,
    expected_steps: list[str] | None = None,
    expect_report_payload: bool = False,
    expected_run_db_source: str = "flag",
    expected_run_task_context_source: str = "flag",
    expected_preflight_context_source: str | None = None,
) -> None:
    """Assert service-run command JSON result structure."""
    if result is None:
        return

    expected_steps = expected_steps or ["run", "service-status"]

    expected_step_hints: list[tuple[str, dict[str, str]]] = []

    if expected_steps and expected_steps[0] == "preflight":
        expected_step_hints.append(
            (
                "preflight",
                {"permission_context": expected_preflight_context_source or "none"},
            )
        )
        expected_step_hints.append(
            (
                "run",
                {
                    "db": expected_run_db_source,
                    "task_context": expected_run_task_context_source,
                },
            )
        )
        expected_step_hints.append(
            ("service-status", {"db": expected_db_source, "task_context": "session"})
        )
    else:
        expected_step_hints.append(
            (
                "run",
                {
                    "db": expected_run_db_source,
                    "task_context": expected_run_task_context_source,
                },
            )
        )
        expected_step_hints.append(
            ("service-status", {"db": expected_db_source, "task_context": "session"})
        )

    _assert_service_combo_json_result(
        result,
        errors,
        name,
        payload_name="run",
        prepared_action="run",
        expected_task_id=expected_task_id,
        expected_steps=expected_steps,
        expected_step_hints=expected_step_hints,
        expected_saved_session_task_id=expected_task_id,
        expect_report_payload=expect_report_payload,
        expected_db=expected_db,
        expected_db_source=expected_db_source,
        expected_limit=expected_limit,
    )


def assert_service_retry_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    expected_db: str,
    expected_db_source: str,
    expected_task_id: str,
    expected_limit: int,
    expected_steps: list[str] | None = None,
    expect_report_payload: bool = False,
) -> None:
    """Assert service-retry command JSON result structure."""
    if result is None:
        return

    expected_steps = expected_steps or ["retry", "service-status"]
    _assert_service_combo_json_result(
        result,
        errors,
        name,
        payload_name="retry",
        prepared_action="retry",
        expected_task_id=expected_task_id,
        expected_steps=expected_steps,
        expected_step_hints=[
            ("retry", {"db": expected_db_source, "task_context": "flag"}),
            ("service-status", {"db": expected_db_source, "task_context": "session"}),
        ],
        expected_saved_session_task_id=None,
        expect_report_payload=expect_report_payload,
        expected_db=expected_db,
        expected_db_source=expected_db_source,
        expected_limit=expected_limit,
    )


def assert_service_recover_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    expected_db: str,
    expected_db_source: str,
    expected_task_id: str,
    expected_limit: int,
    expected_steps: list[str] | None = None,
    expect_report_payload: bool = False,
) -> None:
    """Assert service-recover command JSON result structure."""
    if result is None:
        return

    expected_steps = expected_steps or ["recover", "service-status"]
    _assert_service_combo_json_result(
        result,
        errors,
        name,
        payload_name="recover",
        prepared_action="recover",
        expected_task_id=expected_task_id,
        expected_steps=expected_steps,
        expected_step_hints=[
            ("recover", {"db": expected_db_source, "task_context": "flag"}),
            ("service-status", {"db": expected_db_source, "task_context": "session"}),
        ],
        expected_saved_session_task_id=None,
        expect_report_payload=expect_report_payload,
        expected_db=expected_db,
        expected_db_source=expected_db_source,
        expected_limit=expected_limit,
    )


def assert_service_resume_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    expected_db: str,
    expected_db_source: str,
    expected_task_id: str,
    expected_limit: int,
    expected_steps: list[str] | None = None,
    expect_report_payload: bool = False,
) -> None:
    """Assert service-resume command JSON result structure."""
    if result is None:
        return

    expected_steps = expected_steps or ["resume", "service-status"]
    _assert_service_combo_json_result(
        result,
        errors,
        name,
        payload_name="resume",
        prepared_action="resume",
        expected_task_id=expected_task_id,
        expected_steps=expected_steps,
        expected_step_hints=[
            ("resume", {"db": expected_db_source, "task_context": "flag"}),
            ("service-status", {"db": expected_db_source, "task_context": "session"}),
        ],
        expected_saved_session_task_id=None,
        expect_report_payload=expect_report_payload,
        expected_db=expected_db,
        expected_db_source=expected_db_source,
        expected_limit=expected_limit,
    )


def assert_service_reconcile_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    expected_db: str,
    expected_db_source: str,
    expected_task_id: str,
    expected_limit: int,
    expected_decision: str,
    expected_steps: list[str] | None = None,
    expect_report_payload: bool = False,
) -> None:
    """Assert service-reconcile command JSON result structure."""
    if result is None:
        return

    expected_steps = expected_steps or ["reconcile", "service-status"]
    _assert_service_combo_json_result(
        result,
        errors,
        name,
        payload_name="reconcile",
        prepared_action="reconcile",
        expected_task_id=expected_task_id,
        expected_steps=expected_steps,
        expected_step_hints=[
            ("reconcile", {"db": expected_db_source, "task_context": "flag"}),
            ("service-status", {"db": expected_db_source, "task_context": "session"}),
        ],
        expected_saved_session_task_id=None,
        expect_report_payload=expect_report_payload,
        expected_db=expected_db,
        expected_db_source=expected_db_source,
        expected_limit=expected_limit,
        expected_decision=expected_decision,
    )

def assert_default_service_status_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    expected_db: str,
    expected_db_source: str = "default",
    expected_limit: int = 5,
) -> None:
    if result is None:
        return
    for checker in (
        _check_default_service_status_base_fields(
            result,
            name,
            expected_db=expected_db,
            expected_db_source=expected_db_source,
            expected_limit=expected_limit,
        ),
        _check_default_service_status_runtime_fields(result, name),
    ):
        if checker is not None:
            errors.append(checker)
            return


