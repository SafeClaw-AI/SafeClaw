"""Service-related assertion utilities for smoke tests."""

from __future__ import annotations


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

    if result.get("example") != "worker_service_governance_demo":
        errors.append(f"{name} missing example name")
    elif not isinstance(resolved_run, dict) or resolved_run.get("executed") != 2:
        errors.append(f"{name} missing resolved_run.executed=2")
    elif resolved_run.get("parked") != 0:
        errors.append(f"{name} missing resolved_run.parked=0")
    elif (
        not isinstance(resolved_governance, dict)
        or resolved_governance.get("resolved") != 2
    ):
        errors.append(f"{name} missing resolved_governance.resolved=2")
    elif resolved_governance.get("confirmation") != 0:
        errors.append(f"{name} missing resolved_governance.confirmation=0")
    elif (
        not isinstance(confirmation_governance, dict)
        or confirmation_governance.get("confirmation") != 1
    ):
        errors.append(f"{name} missing confirmation_governance.confirmation=1")
    elif confirmation_governance.get("manual_review") != 0:
        errors.append(f"{name} missing confirmation_governance.manual_review=0")
    elif (
        not isinstance(resolved_tasks, list)
        or "task-worker-service-governance-a" not in resolved_tasks
    ):
        errors.append(f"{name} missing resolved task a")
    elif "task-worker-service-governance-b" not in resolved_tasks:
        errors.append(f"{name} missing resolved task b")
    elif (
        not isinstance(confirmation_tasks, list)
        or "task-worker-service-governance-confirmation" not in confirmation_tasks
    ):
        errors.append(f"{name} missing confirmation task")
    elif not str(result.get("db_path") or "").lower().endswith(".db"):
        errors.append(f"{name} missing db_path")
    elif (
        "[demo] service governance resolved => total=2 resolved=2 confirmation=0 manual_review=0"
        not in captured_output
    ):
        errors.append(f"{name} missing resolved governance output")
    elif (
        "[demo] service governance confirmation => total=1 resolved=0 confirmation=1 manual_review=0"
        not in captured_output
    ):
        errors.append(f"{name} missing confirmation governance output")


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
    """Assert service-status command JSON result structure."""
    if result is None:
        return

    queue = result.get("queue") or {}
    workers = result.get("workers") or {}
    effects = result.get("effects") or {}
    probes = result.get("probes") or {}
    heartbeat = result.get("heartbeat") or {}
    coordination = result.get("coordination") or {}
    recent_tasks = result.get("recent_tasks") or []
    current_session = result.get("current_session") or {}
    runtime_profile = result.get("runtime_profile") or {}
    model_provider = result.get("model_provider") or {}
    sidecar = result.get("sidecar") or {}
    offline_gate = result.get("offline_gate") or {}

    actual_db = str(result.get("db") or "").replace("\\", "/")
    normalized_expected_db = expected_db.replace("\\", "/")

    worker_succeeded = (
        None
        if not isinstance(workers, dict)
        else (
            workers.get("succeeded")
            if "succeeded" in workers
            else workers.get("Succeeded")
        )
    )

    effect_executed = (
        None
        if not isinstance(effects, dict)
        else (
            effects.get("executed")
            if "executed" in effects
            else effects.get("Executed")
        )
    )

    if actual_db != normalized_expected_db:
        errors.append(f"{name} missing db={expected_db}")
    elif result.get("db_source") != expected_db_source:
        errors.append(f"{name} missing db_source={expected_db_source}")
    elif result.get("limit") != expected_limit:
        errors.append(f"{name} missing limit={expected_limit}")
    elif result.get("current_db") is not True:
        errors.append(f"{name} missing current_db=true")
    elif (
        not isinstance(current_session, dict)
        or current_session.get("task_id") != expected_task_id
    ):
        errors.append(f"{name} missing current_session {expected_task_id}")
    elif not isinstance(queue, dict) or queue.get("queued") != 0:
        errors.append(f"{name} missing queue.queued=0")
    elif queue.get("active") != 0:
        errors.append(f"{name} missing queue.active=0")
    elif queue.get("expired") != 0:
        errors.append(f"{name} missing queue.expired=0")
    elif queue.get("completed") != 1:
        errors.append(f"{name} missing queue.completed=1")
    elif worker_succeeded != 1:
        errors.append(f"{name} missing workers.succeeded=1")
    elif effect_executed != 1:
        errors.append(f"{name} missing effects.executed=1")
    elif not isinstance(probes, dict) or probes.get("none") != 1:
        errors.append(f"{name} missing probes.none=1")
    elif (
        expected_heartbeat_freshness is not None
        and heartbeat.get("latest_freshness") != expected_heartbeat_freshness
    ):
        errors.append(
            f"{name} missing heartbeat.latest_freshness={expected_heartbeat_freshness}"
        )
    elif (
        expected_heartbeat_status is not None
        and heartbeat.get("status") != expected_heartbeat_status
    ):
        errors.append(f"{name} missing heartbeat.status={expected_heartbeat_status}")
    elif (
        expected_heartbeat_interval_ms is not None
        and heartbeat.get("interval_ms") != expected_heartbeat_interval_ms
    ):
        errors.append(
            f"{name} missing heartbeat.interval_ms={expected_heartbeat_interval_ms}"
        )
    elif (
        expected_heartbeat_event_driven is not None
        and heartbeat.get("event_driven") is not expected_heartbeat_event_driven
    ):
        errors.append(
            f"{name} missing heartbeat.event_driven={expected_heartbeat_event_driven}"
        )
    elif (
        expected_heartbeat_reason is not None
        and heartbeat.get("reason") != expected_heartbeat_reason
    ):
        errors.append(f"{name} missing heartbeat.reason={expected_heartbeat_reason}")
    elif expect_heartbeat_latest_updated_at_present and not heartbeat.get(
        "latest_updated_at"
    ):
        errors.append(f"{name} missing heartbeat.latest_updated_at")
    elif (
        expect_heartbeat_latest_updated_at_absent
        and heartbeat.get("latest_updated_at") is not None
    ):
        errors.append(f"{name} expected heartbeat.latest_updated_at=None")
    elif expect_heartbeat_latest_age_ms_present and not isinstance(
        heartbeat.get("latest_age_ms"), int
    ):
        errors.append(f"{name} missing heartbeat.latest_age_ms int")
    elif (
        expect_heartbeat_latest_age_ms_absent
        and heartbeat.get("latest_age_ms") is not None
    ):
        errors.append(f"{name} expected heartbeat.latest_age_ms=None")
    elif (
        expected_service_coordination_status is not None
        and coordination.get("status") != expected_service_coordination_status
    ):
        errors.append(
            f"{name} missing coordination.status={expected_service_coordination_status}"
        )
    elif (
        expected_service_coordination_reason is not None
        and coordination.get("reason") != expected_service_coordination_reason
    ):
        errors.append(
            f"{name} missing coordination.reason={expected_service_coordination_reason}"
        )
    elif (
        expected_service_coordination_summary is not None
        and coordination.get("summary") != expected_service_coordination_summary
    ):
        errors.append(
            f"{name} missing coordination.summary={expected_service_coordination_summary}"
        )
    elif (
        not isinstance(runtime_profile, dict)
        or runtime_profile.get("mode") != "local_mvp"
    ):
        errors.append(f"{name} missing runtime_profile.mode=local_mvp")
    elif runtime_profile.get("offline_ready") is not True:
        errors.append(f"{name} missing runtime_profile.offline_ready=true")
    elif runtime_profile.get("llm_required") is not False:
        errors.append(f"{name} missing runtime_profile.llm_required=false")
    elif runtime_profile.get("sidecar_required") is not False:
        errors.append(f"{name} missing runtime_profile.sidecar_required=false")
    elif not runtime_profile.get("detail"):
        errors.append(f"{name} missing runtime_profile.detail")
    elif (
        not isinstance(model_provider, dict)
        or model_provider.get("status") != "not-configured"
    ):
        errors.append(f"{name} missing model_provider.status=not-configured")
    elif model_provider.get("required") is not False:
        errors.append(f"{name} missing model_provider.required=false")
    elif model_provider.get("configured") is not False:
        errors.append(f"{name} missing model_provider.configured=false")
    elif model_provider.get("degradation_mode") != "local_only_ok":
        errors.append(f"{name} missing model_provider.degradation_mode=local_only_ok")
    elif not model_provider.get("detail"):
        errors.append(f"{name} missing model_provider.detail")
    elif not isinstance(sidecar, dict) or sidecar.get("status") != "not-configured":
        errors.append(f"{name} missing sidecar.status=not-configured")
    elif sidecar.get("required") is not False:
        errors.append(f"{name} missing sidecar.required=false")
    elif sidecar.get("configured") is not False:
        errors.append(f"{name} missing sidecar.configured=false")
    elif not sidecar.get("detail"):
        errors.append(f"{name} missing sidecar.detail")
    elif not isinstance(offline_gate, dict) or offline_gate.get("status") != "blocked":
        errors.append(f"{name} missing offline_gate.status=blocked")
    elif offline_gate.get("reason") != "ERR_AI_PROVIDER_UNAVAILABLE":
        errors.append(f"{name} missing offline_gate.reason=ERR_AI_PROVIDER_UNAVAILABLE")
    elif offline_gate.get("summary") != "ai_actions_require_provider":
        errors.append(
            f"{name} missing offline_gate.summary=ai_actions_require_provider"
        )
    elif offline_gate.get("requested_action") != "ai-reason":
        errors.append(f"{name} missing offline_gate.requested_action=ai-reason")
    elif offline_gate.get("requires_model") is not True:
        errors.append(f"{name} missing offline_gate.requires_model=true")
    elif offline_gate.get("requires_sidecar") is not True:
        errors.append(f"{name} missing offline_gate.requires_sidecar=true")
    elif (
        offline_gate.get("next_command") != "safeclaw.cmd preflight --action ai-reason"
    ):
        errors.append(
            f"{name} missing offline_gate.next_command=safeclaw.cmd preflight --action ai-reason"
        )
    elif offline_gate.get("error_code") != "ERR_AI_PROVIDER_UNAVAILABLE":
        errors.append(
            f"{name} missing offline_gate.error_code=ERR_AI_PROVIDER_UNAVAILABLE"
        )
    elif "budget" in result:
        errors.append(f"{name} unexpectedly exposed budget without runtime source")
    elif (
        not isinstance(recent_tasks, list)
        or not recent_tasks
        or recent_tasks[0].get("task_id") != expected_task_id
    ):
        errors.append(f"{name} missing recent task {expected_task_id}")
    elif recent_tasks[0].get("current") is not True:
        errors.append(f"{name} missing recent current=true")
    elif (
        expected_target_scope is not None
        and recent_tasks[0].get("target_scope") != expected_target_scope
    ):
        errors.append(f"{name} missing recent target_scope={expected_target_scope}")
    elif (
        expected_requires_write is not None
        and recent_tasks[0].get("requires_write") != expected_requires_write
    ):
        errors.append(f"{name} missing recent requires_write={expected_requires_write}")
    elif (
        expected_doctor_bypass is not None
        and recent_tasks[0].get("doctor_bypass") != expected_doctor_bypass
    ):
        errors.append(f"{name} missing recent doctor_bypass={expected_doctor_bypass}")
    elif (
        expected_permission_tier is not None
        and recent_tasks[0].get("permission_tier") != expected_permission_tier
    ):
        errors.append(
            f"{name} missing recent permission_tier={expected_permission_tier}"
        )
    elif (
        expected_permission_policy is not None
        and recent_tasks[0].get("permission_policy") != expected_permission_policy
    ):
        errors.append(
            f"{name} missing recent permission_policy={expected_permission_policy}"
        )
    elif (
        expected_permission_reason is not None
        and recent_tasks[0].get("permission_reason") != expected_permission_reason
    ):
        errors.append(
            f"{name} missing recent permission_reason={expected_permission_reason}"
        )
    elif (
        expected_lease_state is not None
        and recent_tasks[0].get("lease_state") != expected_lease_state
    ):
        errors.append(f"{name} missing recent lease_state={expected_lease_state}")
    elif (
        expected_lease_freshness is not None
        and recent_tasks[0].get("lease_freshness") != expected_lease_freshness
    ):
        errors.append(
            f"{name} missing recent lease_freshness={expected_lease_freshness}"
        )
    elif (
        expected_lease_owner_id is not None
        and recent_tasks[0].get("lease_owner_id") != expected_lease_owner_id
    ):
        errors.append(f"{name} missing recent lease_owner_id={expected_lease_owner_id}")
    elif (
        expected_lease_fencing_token is not None
        and recent_tasks[0].get("lease_fencing_token") != expected_lease_fencing_token
    ):
        errors.append(
            f"{name} missing recent lease_fencing_token={expected_lease_fencing_token}"
        )
    elif (
        expected_next_action is not None
        and recent_tasks[0].get("next_action") != expected_next_action
    ):
        errors.append(f"{name} missing recent next_action={expected_next_action}")
    elif (
        expected_next_command is not None
        and recent_tasks[0].get("next_command") != expected_next_command
    ):
        errors.append(f"{name} missing recent next_command={expected_next_command}")
    elif (
        expected_next_reason is not None
        and recent_tasks[0].get("next_reason") != expected_next_reason
    ):
        errors.append(f"{name} missing recent next_reason={expected_next_reason}")
    elif (
        expected_next_blocker is not None
        and recent_tasks[0].get("next_blocker") != expected_next_blocker
    ):
        errors.append(f"{name} missing recent next_blocker={expected_next_blocker}")
    elif (
        expected_next_summary is not None
        and recent_tasks[0].get("next_summary") != expected_next_summary
    ):
        errors.append(f"{name} missing recent next_summary={expected_next_summary}")
    elif (
        expected_coordination_status is not None
        and recent_tasks[0].get("coordination_status") != expected_coordination_status
    ):
        errors.append(
            f"{name} missing recent coordination_status={expected_coordination_status}"
        )
    elif (
        expected_coordination_reason is not None
        and recent_tasks[0].get("coordination_reason") != expected_coordination_reason
    ):
        errors.append(
            f"{name} missing recent coordination_reason={expected_coordination_reason}"
        )
    elif (
        expected_coordination_summary is not None
        and recent_tasks[0].get("coordination_summary") != expected_coordination_summary
    ):
        errors.append(
            f"{name} missing recent coordination_summary={expected_coordination_summary}"
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

    steps = result.get("steps") or []
    remembered_session = result.get("remembered_session") or {}
    session = result.get("session") or {}
    run_payload = result.get("run") or {}

    if (
        not isinstance(steps, list)
        or [step.get("action") for step in steps] != expected_steps
    ):
        errors.append(f"{name} step sequence is incorrect")
        return

    if (
        not isinstance(remembered_session, dict)
        or remembered_session.get("task_id") != expected_task_id
    ):
        errors.append(f"{name} missing remembered_session {expected_task_id}")
        return

    if not isinstance(session, dict) or session.get("task_id") != expected_task_id:
        errors.append(f"{name} missing session alias {expected_task_id}")
        return

    from .json_assertions import assert_matching_session_alias, assert_step_source_hints

    assert_matching_session_alias(result, errors, name)

    if not isinstance(run_payload, dict):
        errors.append(f"{name} missing nested run payload")
        return

    saved_session = run_payload.get("saved_session") or {}
    nested_remembered_session = run_payload.get("remembered_session") or {}

    if (
        not isinstance(saved_session, dict)
        or saved_session.get("task_id") != expected_task_id
    ):
        errors.append(f"{name} nested run missing saved_session {expected_task_id}")
        return

    if (
        not isinstance(nested_remembered_session, dict)
        or nested_remembered_session.get("task_id") != expected_task_id
    ):
        errors.append(
            f"{name} nested run missing remembered_session {expected_task_id}"
        )
        return

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

    assert_step_source_hints(
        steps[: len(expected_step_hints)],
        errors,
        name,
        expected_step_hints,
    )

    if expect_report_payload:
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
            return

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

    steps = result.get("steps") or []
    remembered_session = result.get("remembered_session") or {}
    session = result.get("session") or {}
    retry_payload = result.get("retry") or {}

    if (
        not isinstance(steps, list)
        or [step.get("action") for step in steps] != expected_steps
    ):
        errors.append(f"{name} step sequence is incorrect")
        return

    if (
        not isinstance(remembered_session, dict)
        or remembered_session.get("task_id") != expected_task_id
    ):
        errors.append(f"{name} missing remembered_session {expected_task_id}")
        return

    if not isinstance(session, dict) or session.get("task_id") != expected_task_id:
        errors.append(f"{name} missing session alias {expected_task_id}")
        return

    from .json_assertions import assert_matching_session_alias, assert_step_source_hints

    assert_matching_session_alias(result, errors, name)

    if not isinstance(retry_payload, dict):
        errors.append(f"{name} missing nested retry payload")
        return

    prepared = retry_payload.get("prepared") or []
    nested_remembered_session = retry_payload.get("remembered_session") or {}

    if not isinstance(prepared, list) or not prepared or prepared[0] != "retry":
        errors.append(f"{name} nested retry missing prepared retry")
        return

    if retry_payload.get("saved_session") is not None:
        errors.append(f"{name} nested retry should not save session")
        return

    if (
        not isinstance(nested_remembered_session, dict)
        or nested_remembered_session.get("task_id") != expected_task_id
    ):
        errors.append(
            f"{name} nested retry missing remembered_session {expected_task_id}"
        )
        return

    assert_step_source_hints(
        steps[:2],
        errors,
        name,
        [
            ("retry", {"db": expected_db_source, "task_context": "flag"}),
            ("service-status", {"db": expected_db_source, "task_context": "session"}),
        ],
    )

    if expect_report_payload:
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
            return

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

    steps = result.get("steps") or []
    remembered_session = result.get("remembered_session") or {}
    session = result.get("session") or {}
    recover_payload = result.get("recover") or {}

    if (
        not isinstance(steps, list)
        or [step.get("action") for step in steps] != expected_steps
    ):
        errors.append(f"{name} step sequence is incorrect")
        return

    if (
        not isinstance(remembered_session, dict)
        or remembered_session.get("task_id") != expected_task_id
    ):
        errors.append(f"{name} missing remembered_session {expected_task_id}")
        return

    if not isinstance(session, dict) or session.get("task_id") != expected_task_id:
        errors.append(f"{name} missing session alias {expected_task_id}")
        return

    from .json_assertions import assert_matching_session_alias, assert_step_source_hints

    assert_matching_session_alias(result, errors, name)

    if not isinstance(recover_payload, dict):
        errors.append(f"{name} missing nested recover payload")
        return

    prepared = recover_payload.get("prepared") or []
    nested_remembered_session = recover_payload.get("remembered_session") or {}

    if not isinstance(prepared, list) or not prepared or prepared[0] != "recover":
        errors.append(f"{name} nested recover missing prepared recover")
        return

    if recover_payload.get("saved_session") is not None:
        errors.append(f"{name} nested recover should not save session")
        return

    if (
        not isinstance(nested_remembered_session, dict)
        or nested_remembered_session.get("task_id") != expected_task_id
    ):
        errors.append(
            f"{name} nested recover missing remembered_session {expected_task_id}"
        )
        return

    assert_step_source_hints(
        steps[:2],
        errors,
        name,
        [
            ("recover", {"db": expected_db_source, "task_context": "flag"}),
            ("service-status", {"db": expected_db_source, "task_context": "session"}),
        ],
    )

    if expect_report_payload:
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
            return

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

    steps = result.get("steps") or []
    remembered_session = result.get("remembered_session") or {}
    session = result.get("session") or {}
    resume_payload = result.get("resume") or {}

    if (
        not isinstance(steps, list)
        or [step.get("action") for step in steps] != expected_steps
    ):
        errors.append(f"{name} step sequence is incorrect")
        return

    if (
        not isinstance(remembered_session, dict)
        or remembered_session.get("task_id") != expected_task_id
    ):
        errors.append(f"{name} missing remembered_session {expected_task_id}")
        return

    if not isinstance(session, dict) or session.get("task_id") != expected_task_id:
        errors.append(f"{name} missing session alias {expected_task_id}")
        return

    from .json_assertions import assert_matching_session_alias, assert_step_source_hints

    assert_matching_session_alias(result, errors, name)

    if not isinstance(resume_payload, dict):
        errors.append(f"{name} missing nested resume payload")
        return

    prepared = resume_payload.get("prepared") or []
    nested_remembered_session = resume_payload.get("remembered_session") or {}

    if not isinstance(prepared, list) or not prepared or prepared[0] != "resume":
        errors.append(f"{name} nested resume missing prepared resume")
        return

    if resume_payload.get("saved_session") is not None:
        errors.append(f"{name} nested resume should not save session")
        return

    if (
        not isinstance(nested_remembered_session, dict)
        or nested_remembered_session.get("task_id") != expected_task_id
    ):
        errors.append(
            f"{name} nested resume missing remembered_session {expected_task_id}"
        )
        return

    assert_step_source_hints(
        steps[:2],
        errors,
        name,
        [
            ("resume", {"db": expected_db_source, "task_context": "flag"}),
            ("service-status", {"db": expected_db_source, "task_context": "session"}),
        ],
    )

    if expect_report_payload:
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
            return

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

    steps = result.get("steps") or []
    remembered_session = result.get("remembered_session") or {}
    session = result.get("session") or {}
    reconcile_payload = result.get("reconcile") or {}

    if (
        not isinstance(steps, list)
        or [step.get("action") for step in steps] != expected_steps
    ):
        errors.append(f"{name} step sequence is incorrect")
        return

    if (
        not isinstance(remembered_session, dict)
        or remembered_session.get("task_id") != expected_task_id
    ):
        errors.append(f"{name} missing remembered_session {expected_task_id}")
        return

    if not isinstance(session, dict) or session.get("task_id") != expected_task_id:
        errors.append(f"{name} missing session alias {expected_task_id}")
        return

    from .json_assertions import assert_matching_session_alias, assert_step_source_hints

    assert_matching_session_alias(result, errors, name)

    if not isinstance(reconcile_payload, dict):
        errors.append(f"{name} missing nested reconcile payload")
        return

    prepared = reconcile_payload.get("prepared") or []
    nested_remembered_session = reconcile_payload.get("remembered_session") or {}

    if not isinstance(prepared, list) or not prepared or prepared[0] != "reconcile":
        errors.append(f"{name} nested reconcile missing prepared reconcile")
        return

    if "--decision" not in prepared:
        errors.append(f"{name} nested reconcile missing --decision")
        return

    if prepared[prepared.index("--decision") + 1] != expected_decision:
        errors.append(f"{name} nested reconcile missing --decision {expected_decision}")
        return

    if reconcile_payload.get("saved_session") is not None:
        errors.append(f"{name} nested reconcile should not save session")
        return

    if (
        not isinstance(nested_remembered_session, dict)
        or nested_remembered_session.get("task_id") != expected_task_id
    ):
        errors.append(
            f"{name} nested reconcile missing remembered_session {expected_task_id}"
        )
        return

    assert_step_source_hints(
        steps[:2],
        errors,
        name,
        [
            ("reconcile", {"db": expected_db_source, "task_context": "flag"}),
            ("service-status", {"db": expected_db_source, "task_context": "session"}),
        ],
    )

    if expect_report_payload:
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
            return

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

