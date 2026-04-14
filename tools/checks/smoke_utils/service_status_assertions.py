"""Shared assertions for service-status JSON payloads."""

from __future__ import annotations

from dataclasses import dataclass, fields


@dataclass(frozen=True)
class ServiceStatusExpectations:
    expected_limit: int = 5
    expected_target_scope: str | None = None
    expected_requires_write: bool | None = None
    expected_doctor_bypass: bool | None = None
    expected_permission_tier: str | None = None
    expected_permission_policy: str | None = None
    expected_permission_reason: str | None = None
    expected_lease_state: str | None = None
    expected_lease_freshness: str | None = None
    expected_lease_owner_id: str | None = None
    expected_lease_fencing_token: int | None = None
    expected_heartbeat_freshness: str | None = None
    expected_heartbeat_status: str | None = None
    expected_heartbeat_interval_ms: int | None = None
    expected_heartbeat_event_driven: bool | None = None
    expected_heartbeat_reason: str | None = None
    expect_heartbeat_latest_updated_at_present: bool = False
    expect_heartbeat_latest_updated_at_absent: bool = False
    expect_heartbeat_latest_age_ms_present: bool = False
    expect_heartbeat_latest_age_ms_absent: bool = False
    expected_next_action: str | None = None
    expected_next_command: str | None = None
    expected_next_reason: str | None = None
    expected_next_blocker: str | None = None
    expected_next_summary: str | None = None
    expected_coordination_status: str | None = None
    expected_coordination_reason: str | None = None
    expected_coordination_summary: str | None = None
    expected_service_coordination_status: str | None = None
    expected_service_coordination_reason: str | None = None
    expected_service_coordination_summary: str | None = None

    @classmethod
    def from_kwargs(
        cls,
        kwargs: dict[str, object],
    ) -> ServiceStatusExpectations:
        allowed = {field.name for field in fields(cls)}
        unexpected = sorted(set(kwargs) - allowed)
        if unexpected:
            names = ", ".join(unexpected)
            raise TypeError(f"unexpected service-status expectations: {names}")
        return cls(**kwargs)


def _first_service_status_error(
    checks: tuple[tuple[bool, str], ...],
) -> str | None:
    for failed, message in checks:
        if failed:
            return message
    return None


def _service_stat_value(payload: object, key: str) -> object | None:
    if not isinstance(payload, dict):
        return None
    if key in payload:
        return payload.get(key)
    return payload.get(key.capitalize())


def _check_service_status_identity_fields(
    *,
    result: dict[str, object],
    name: str,
    expected_db: str,
    expected_db_source: str,
    expected_task_id: str,
    expected_limit: int,
) -> str | None:
    queue = result.get("queue") or {}
    workers = result.get("workers") or {}
    effects = result.get("effects") or {}
    probes = result.get("probes") or {}
    current_session = result.get("current_session") or {}

    actual_db = str(result.get("db") or "").replace("\\", "/")
    normalized_expected_db = expected_db.replace("\\", "/")
    worker_succeeded = _service_stat_value(workers, "succeeded")
    effect_executed = _service_stat_value(effects, "executed")

    return _first_service_status_error(
        (
            (actual_db != normalized_expected_db, f"{name} missing db={expected_db}"),
            (
                result.get("db_source") != expected_db_source,
                f"{name} missing db_source={expected_db_source}",
            ),
            (result.get("limit") != expected_limit, f"{name} missing limit={expected_limit}"),
            (result.get("current_db") is not True, f"{name} missing current_db=true"),
            (
                not isinstance(current_session, dict)
                or current_session.get("task_id") != expected_task_id,
                f"{name} missing current_session {expected_task_id}",
            ),
            (
                not isinstance(queue, dict) or queue.get("queued") != 0,
                f"{name} missing queue.queued=0",
            ),
            (queue.get("active") != 0, f"{name} missing queue.active=0"),
            (queue.get("expired") != 0, f"{name} missing queue.expired=0"),
            (queue.get("completed") != 1, f"{name} missing queue.completed=1"),
            (worker_succeeded != 1, f"{name} missing workers.succeeded=1"),
            (effect_executed != 1, f"{name} missing effects.executed=1"),
            (
                not isinstance(probes, dict) or probes.get("none") != 1,
                f"{name} missing probes.none=1",
            ),
        )
    )


def _check_service_status_heartbeat_fields(
    *,
    result: dict[str, object],
    name: str,
    expected_heartbeat_freshness: str | None,
    expected_heartbeat_status: str | None,
    expected_heartbeat_interval_ms: int | None,
    expected_heartbeat_event_driven: bool | None,
    expected_heartbeat_reason: str | None,
    expect_heartbeat_latest_updated_at_present: bool,
    expect_heartbeat_latest_updated_at_absent: bool,
    expect_heartbeat_latest_age_ms_present: bool,
    expect_heartbeat_latest_age_ms_absent: bool,
) -> str | None:
    heartbeat = result.get("heartbeat") or {}
    for checker in (
        _check_service_status_heartbeat_value_fields(
            heartbeat=heartbeat,
            name=name,
            expected_heartbeat_freshness=expected_heartbeat_freshness,
            expected_heartbeat_status=expected_heartbeat_status,
            expected_heartbeat_interval_ms=expected_heartbeat_interval_ms,
            expected_heartbeat_event_driven=expected_heartbeat_event_driven,
            expected_heartbeat_reason=expected_heartbeat_reason,
        ),
        _check_service_status_heartbeat_timestamp_fields(
            heartbeat=heartbeat,
            name=name,
            expect_heartbeat_latest_updated_at_present=expect_heartbeat_latest_updated_at_present,
            expect_heartbeat_latest_updated_at_absent=expect_heartbeat_latest_updated_at_absent,
            expect_heartbeat_latest_age_ms_present=expect_heartbeat_latest_age_ms_present,
            expect_heartbeat_latest_age_ms_absent=expect_heartbeat_latest_age_ms_absent,
        ),
    ):
        if checker is not None:
            return checker
    return None


def _check_service_status_heartbeat_value_fields(
    *,
    heartbeat: object,
    name: str,
    expected_heartbeat_freshness: str | None,
    expected_heartbeat_status: str | None,
    expected_heartbeat_interval_ms: int | None,
    expected_heartbeat_event_driven: bool | None,
    expected_heartbeat_reason: str | None,
) -> str | None:
    return _first_service_status_error(
        (
            (
                expected_heartbeat_freshness is not None
                and heartbeat.get("latest_freshness") != expected_heartbeat_freshness,
                f"{name} missing heartbeat.latest_freshness={expected_heartbeat_freshness}",
            ),
            (
                expected_heartbeat_status is not None
                and heartbeat.get("status") != expected_heartbeat_status,
                f"{name} missing heartbeat.status={expected_heartbeat_status}",
            ),
            (
                expected_heartbeat_interval_ms is not None
                and heartbeat.get("interval_ms") != expected_heartbeat_interval_ms,
                f"{name} missing heartbeat.interval_ms={expected_heartbeat_interval_ms}",
            ),
            (
                expected_heartbeat_event_driven is not None
                and heartbeat.get("event_driven") is not expected_heartbeat_event_driven,
                f"{name} missing heartbeat.event_driven={expected_heartbeat_event_driven}",
            ),
            (
                expected_heartbeat_reason is not None
                and heartbeat.get("reason") != expected_heartbeat_reason,
                f"{name} missing heartbeat.reason={expected_heartbeat_reason}",
            ),
        )
    )


def _check_service_status_heartbeat_timestamp_fields(
    *,
    heartbeat: object,
    name: str,
    expect_heartbeat_latest_updated_at_present: bool,
    expect_heartbeat_latest_updated_at_absent: bool,
    expect_heartbeat_latest_age_ms_present: bool,
    expect_heartbeat_latest_age_ms_absent: bool,
) -> str | None:
    return _first_service_status_error(
        (
            (
                expect_heartbeat_latest_updated_at_present
                and not heartbeat.get("latest_updated_at"),
                f"{name} missing heartbeat.latest_updated_at",
            ),
            (
                expect_heartbeat_latest_updated_at_absent
                and heartbeat.get("latest_updated_at") is not None,
                f"{name} expected heartbeat.latest_updated_at=None",
            ),
            (
                expect_heartbeat_latest_age_ms_present
                and not isinstance(heartbeat.get("latest_age_ms"), int),
                f"{name} missing heartbeat.latest_age_ms int",
            ),
            (
                expect_heartbeat_latest_age_ms_absent
                and heartbeat.get("latest_age_ms") is not None,
                f"{name} expected heartbeat.latest_age_ms=None",
            ),
        )
    )


def _check_service_status_coordination_fields(
    *,
    result: dict[str, object],
    name: str,
    expected_service_coordination_status: str | None,
    expected_service_coordination_reason: str | None,
    expected_service_coordination_summary: str | None,
) -> str | None:
    coordination = result.get("coordination") or {}
    return _first_service_status_error(
        (
            (
                expected_service_coordination_status is not None
                and coordination.get("status") != expected_service_coordination_status,
                f"{name} missing coordination.status={expected_service_coordination_status}",
            ),
            (
                expected_service_coordination_reason is not None
                and coordination.get("reason") != expected_service_coordination_reason,
                f"{name} missing coordination.reason={expected_service_coordination_reason}",
            ),
            (
                expected_service_coordination_summary is not None
                and coordination.get("summary") != expected_service_coordination_summary,
                f"{name} missing coordination.summary={expected_service_coordination_summary}",
            ),
        )
    )


def _check_service_status_core_fields(
    *,
    result: dict[str, object],
    name: str,
    expected_db: str,
    expected_db_source: str,
    expected_task_id: str,
    expected_limit: int,
    expected_heartbeat_freshness: str | None,
    expected_heartbeat_status: str | None,
    expected_heartbeat_interval_ms: int | None,
    expected_heartbeat_event_driven: bool | None,
    expected_heartbeat_reason: str | None,
    expect_heartbeat_latest_updated_at_present: bool,
    expect_heartbeat_latest_updated_at_absent: bool,
    expect_heartbeat_latest_age_ms_present: bool,
    expect_heartbeat_latest_age_ms_absent: bool,
    expected_service_coordination_status: str | None,
    expected_service_coordination_reason: str | None,
    expected_service_coordination_summary: str | None,
) -> str | None:
    for checker in (
        _check_service_status_identity_fields(
            result=result,
            name=name,
            expected_db=expected_db,
            expected_db_source=expected_db_source,
            expected_task_id=expected_task_id,
            expected_limit=expected_limit,
        ),
        _check_service_status_heartbeat_fields(
            result=result,
            name=name,
            expected_heartbeat_freshness=expected_heartbeat_freshness,
            expected_heartbeat_status=expected_heartbeat_status,
            expected_heartbeat_interval_ms=expected_heartbeat_interval_ms,
            expected_heartbeat_event_driven=expected_heartbeat_event_driven,
            expected_heartbeat_reason=expected_heartbeat_reason,
            expect_heartbeat_latest_updated_at_present=expect_heartbeat_latest_updated_at_present,
            expect_heartbeat_latest_updated_at_absent=expect_heartbeat_latest_updated_at_absent,
            expect_heartbeat_latest_age_ms_present=expect_heartbeat_latest_age_ms_present,
            expect_heartbeat_latest_age_ms_absent=expect_heartbeat_latest_age_ms_absent,
        ),
        _check_service_status_coordination_fields(
            result=result,
            name=name,
            expected_service_coordination_status=expected_service_coordination_status,
            expected_service_coordination_reason=expected_service_coordination_reason,
            expected_service_coordination_summary=expected_service_coordination_summary,
        ),
    ):
        if checker is not None:
            return checker
    return None


def _check_service_status_runtime_fields(
    *,
    result: dict[str, object],
    name: str,
) -> str | None:
    runtime_profile = result.get("runtime_profile") or {}
    model_provider = result.get("model_provider") or {}
    sidecar = result.get("sidecar") or {}
    offline_gate = result.get("offline_gate") or {}

    for checker in (
        _check_runtime_profile_fields(runtime_profile=runtime_profile, name=name),
        _check_model_provider_fields(model_provider=model_provider, name=name),
        _check_sidecar_fields(sidecar=sidecar, name=name),
        _check_offline_gate_fields(offline_gate=offline_gate, name=name),
        _check_runtime_budget_absent(result=result, name=name),
    ):
        if checker is not None:
            return checker
    return None


def _check_runtime_profile_fields(
    *,
    runtime_profile: object,
    name: str,
) -> str | None:
    return _first_service_status_error(
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
                runtime_profile.get("llm_required") is not False,
                f"{name} missing runtime_profile.llm_required=false",
            ),
            (
                runtime_profile.get("sidecar_required") is not False,
                f"{name} missing runtime_profile.sidecar_required=false",
            ),
            (not runtime_profile.get("detail"), f"{name} missing runtime_profile.detail"),
        )
    )


def _check_model_provider_fields(
    *,
    model_provider: object,
    name: str,
) -> str | None:
    return _first_service_status_error(
        (
            (
                not isinstance(model_provider, dict)
                or model_provider.get("status") != "not-configured",
                f"{name} missing model_provider.status=not-configured",
            ),
            (
                model_provider.get("required") is not False,
                f"{name} missing model_provider.required=false",
            ),
            (
                model_provider.get("configured") is not False,
                f"{name} missing model_provider.configured=false",
            ),
            (
                model_provider.get("degradation_mode") != "local_only_ok",
                f"{name} missing model_provider.degradation_mode=local_only_ok",
            ),
            (not model_provider.get("detail"), f"{name} missing model_provider.detail"),
        )
    )


def _check_sidecar_fields(
    *,
    sidecar: object,
    name: str,
) -> str | None:
    return _first_service_status_error(
        (
            (
                not isinstance(sidecar, dict)
                or sidecar.get("status") != "not-configured",
                f"{name} missing sidecar.status=not-configured",
            ),
            (
                sidecar.get("required") is not False,
                f"{name} missing sidecar.required=false",
            ),
            (
                sidecar.get("configured") is not False,
                f"{name} missing sidecar.configured=false",
            ),
            (not sidecar.get("detail"), f"{name} missing sidecar.detail"),
        )
    )


def _check_offline_gate_fields(
    *,
    offline_gate: object,
    name: str,
) -> str | None:
    return _first_service_status_error(
        (
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
                offline_gate.get("next_command")
                != "safeclaw.cmd preflight --action ai-reason",
                f"{name} missing offline_gate.next_command=safeclaw.cmd preflight --action ai-reason",
            ),
            (
                offline_gate.get("error_code") != "ERR_AI_PROVIDER_UNAVAILABLE",
                f"{name} missing offline_gate.error_code=ERR_AI_PROVIDER_UNAVAILABLE",
            ),
        )
    )


def _check_runtime_budget_absent(
    *,
    result: dict[str, object],
    name: str,
) -> str | None:
    return _first_service_status_error(
        (
            ("budget" in result, f"{name} unexpectedly exposed budget without runtime source"),
        )
    )


def _check_recent_task_present(
    *,
    recent_tasks: object,
    name: str,
    expected_task_id: str,
) -> tuple[dict[str, object], str | None]:
    if (
        not isinstance(recent_tasks, list)
        or not recent_tasks
        or recent_tasks[0].get("task_id") != expected_task_id
    ):
        return {}, f"{name} missing recent task {expected_task_id}"
    return recent_tasks[0], None


def _check_recent_task_scope_fields(
    *,
    recent_task: dict[str, object],
    name: str,
    expected_target_scope: str | None,
    expected_requires_write: bool | None,
    expected_doctor_bypass: bool | None,
    expected_permission_tier: str | None,
    expected_permission_policy: str | None,
    expected_permission_reason: str | None,
) -> str | None:
    return _first_service_status_error(
        (
            (recent_task.get("current") is not True, f"{name} missing recent current=true"),
            (
                expected_target_scope is not None
                and recent_task.get("target_scope") != expected_target_scope,
                f"{name} missing recent target_scope={expected_target_scope}",
            ),
            (
                expected_requires_write is not None
                and recent_task.get("requires_write") != expected_requires_write,
                f"{name} missing recent requires_write={expected_requires_write}",
            ),
            (
                expected_doctor_bypass is not None
                and recent_task.get("doctor_bypass") != expected_doctor_bypass,
                f"{name} missing recent doctor_bypass={expected_doctor_bypass}",
            ),
            (
                expected_permission_tier is not None
                and recent_task.get("permission_tier") != expected_permission_tier,
                f"{name} missing recent permission_tier={expected_permission_tier}",
            ),
            (
                expected_permission_policy is not None
                and recent_task.get("permission_policy") != expected_permission_policy,
                f"{name} missing recent permission_policy={expected_permission_policy}",
            ),
            (
                expected_permission_reason is not None
                and recent_task.get("permission_reason") != expected_permission_reason,
                f"{name} missing recent permission_reason={expected_permission_reason}",
            ),
        )
    )


def _check_recent_task_lease_fields(
    *,
    recent_task: dict[str, object],
    name: str,
    expected_lease_state: str | None,
    expected_lease_freshness: str | None,
    expected_lease_owner_id: str | None,
    expected_lease_fencing_token: int | None,
) -> str | None:
    return _first_service_status_error(
        (
            (
                expected_lease_state is not None
                and recent_task.get("lease_state") != expected_lease_state,
                f"{name} missing recent lease_state={expected_lease_state}",
            ),
            (
                expected_lease_freshness is not None
                and recent_task.get("lease_freshness") != expected_lease_freshness,
                f"{name} missing recent lease_freshness={expected_lease_freshness}",
            ),
            (
                expected_lease_owner_id is not None
                and recent_task.get("lease_owner_id") != expected_lease_owner_id,
                f"{name} missing recent lease_owner_id={expected_lease_owner_id}",
            ),
            (
                expected_lease_fencing_token is not None
                and recent_task.get("lease_fencing_token") != expected_lease_fencing_token,
                f"{name} missing recent lease_fencing_token={expected_lease_fencing_token}",
            ),
        )
    )


def _check_recent_task_next_fields(
    *,
    recent_task: dict[str, object],
    name: str,
    expected_next_action: str | None,
    expected_next_command: str | None,
    expected_next_reason: str | None,
    expected_next_blocker: str | None,
    expected_next_summary: str | None,
) -> str | None:
    return _first_service_status_error(
        (
            (
                expected_next_action is not None
                and recent_task.get("next_action") != expected_next_action,
                f"{name} missing recent next_action={expected_next_action}",
            ),
            (
                expected_next_command is not None
                and recent_task.get("next_command") != expected_next_command,
                f"{name} missing recent next_command={expected_next_command}",
            ),
            (
                expected_next_reason is not None
                and recent_task.get("next_reason") != expected_next_reason,
                f"{name} missing recent next_reason={expected_next_reason}",
            ),
            (
                expected_next_blocker is not None
                and recent_task.get("next_blocker") != expected_next_blocker,
                f"{name} missing recent next_blocker={expected_next_blocker}",
            ),
            (
                expected_next_summary is not None
                and recent_task.get("next_summary") != expected_next_summary,
                f"{name} missing recent next_summary={expected_next_summary}",
            ),
        )
    )


def _check_recent_task_coordination_fields(
    *,
    recent_task: dict[str, object],
    name: str,
    expected_coordination_status: str | None,
    expected_coordination_reason: str | None,
    expected_coordination_summary: str | None,
) -> str | None:
    return _first_service_status_error(
        (
            (
                expected_coordination_status is not None
                and recent_task.get("coordination_status")
                != expected_coordination_status,
                f"{name} missing recent coordination_status={expected_coordination_status}",
            ),
            (
                expected_coordination_reason is not None
                and recent_task.get("coordination_reason") != expected_coordination_reason,
                f"{name} missing recent coordination_reason={expected_coordination_reason}",
            ),
            (
                expected_coordination_summary is not None
                and recent_task.get("coordination_summary")
                != expected_coordination_summary,
                f"{name} missing recent coordination_summary={expected_coordination_summary}",
            ),
        )
    )


def _check_service_status_recent_task_fields(
    *,
    recent_tasks: object,
    name: str,
    expected_task_id: str,
    expected_target_scope: str | None,
    expected_requires_write: bool | None,
    expected_doctor_bypass: bool | None,
    expected_permission_tier: str | None,
    expected_permission_policy: str | None,
    expected_permission_reason: str | None,
    expected_lease_state: str | None,
    expected_lease_freshness: str | None,
    expected_lease_owner_id: str | None,
    expected_lease_fencing_token: int | None,
    expected_next_action: str | None,
    expected_next_command: str | None,
    expected_next_reason: str | None,
    expected_next_blocker: str | None,
    expected_next_summary: str | None,
    expected_coordination_status: str | None,
    expected_coordination_reason: str | None,
    expected_coordination_summary: str | None,
) -> str | None:
    recent_task, presence_error = _check_recent_task_present(
        recent_tasks=recent_tasks,
        name=name,
        expected_task_id=expected_task_id,
    )
    if presence_error is not None:
        return presence_error

    for checker in (
        _check_recent_task_scope_fields(
            recent_task=recent_task,
            name=name,
            expected_target_scope=expected_target_scope,
            expected_requires_write=expected_requires_write,
            expected_doctor_bypass=expected_doctor_bypass,
            expected_permission_tier=expected_permission_tier,
            expected_permission_policy=expected_permission_policy,
            expected_permission_reason=expected_permission_reason,
        ),
        _check_recent_task_lease_fields(
            recent_task=recent_task,
            name=name,
            expected_lease_state=expected_lease_state,
            expected_lease_freshness=expected_lease_freshness,
            expected_lease_owner_id=expected_lease_owner_id,
            expected_lease_fencing_token=expected_lease_fencing_token,
        ),
        _check_recent_task_next_fields(
            recent_task=recent_task,
            name=name,
            expected_next_action=expected_next_action,
            expected_next_command=expected_next_command,
            expected_next_reason=expected_next_reason,
            expected_next_blocker=expected_next_blocker,
            expected_next_summary=expected_next_summary,
        ),
        _check_recent_task_coordination_fields(
            recent_task=recent_task,
            name=name,
            expected_coordination_status=expected_coordination_status,
            expected_coordination_reason=expected_coordination_reason,
            expected_coordination_summary=expected_coordination_summary,
        ),
    ):
        if checker is not None:
            return checker
    return None


def _collect_service_status_result_error(
    *,
    result: dict[str, object],
    name: str,
    expected_db: str,
    expected_db_source: str,
    expected_task_id: str,
    expectations: ServiceStatusExpectations,
) -> str | None:
    recent_tasks = result.get("recent_tasks") or []

    for checker in (
        _check_service_status_core_fields(
            result=result,
            name=name,
            expected_db=expected_db,
            expected_db_source=expected_db_source,
            expected_task_id=expected_task_id,
            expected_limit=expectations.expected_limit,
            expected_heartbeat_freshness=expectations.expected_heartbeat_freshness,
            expected_heartbeat_status=expectations.expected_heartbeat_status,
            expected_heartbeat_interval_ms=expectations.expected_heartbeat_interval_ms,
            expected_heartbeat_event_driven=expectations.expected_heartbeat_event_driven,
            expected_heartbeat_reason=expectations.expected_heartbeat_reason,
            expect_heartbeat_latest_updated_at_present=expectations.expect_heartbeat_latest_updated_at_present,
            expect_heartbeat_latest_updated_at_absent=expectations.expect_heartbeat_latest_updated_at_absent,
            expect_heartbeat_latest_age_ms_present=expectations.expect_heartbeat_latest_age_ms_present,
            expect_heartbeat_latest_age_ms_absent=expectations.expect_heartbeat_latest_age_ms_absent,
            expected_service_coordination_status=expectations.expected_service_coordination_status,
            expected_service_coordination_reason=expectations.expected_service_coordination_reason,
            expected_service_coordination_summary=expectations.expected_service_coordination_summary,
        ),
        _check_service_status_runtime_fields(result=result, name=name),
        _check_service_status_recent_task_fields(
            recent_tasks=recent_tasks,
            name=name,
            expected_task_id=expected_task_id,
            expected_target_scope=expectations.expected_target_scope,
            expected_requires_write=expectations.expected_requires_write,
            expected_doctor_bypass=expectations.expected_doctor_bypass,
            expected_permission_tier=expectations.expected_permission_tier,
            expected_permission_policy=expectations.expected_permission_policy,
            expected_permission_reason=expectations.expected_permission_reason,
            expected_lease_state=expectations.expected_lease_state,
            expected_lease_freshness=expectations.expected_lease_freshness,
            expected_lease_owner_id=expectations.expected_lease_owner_id,
            expected_lease_fencing_token=expectations.expected_lease_fencing_token,
            expected_next_action=expectations.expected_next_action,
            expected_next_command=expectations.expected_next_command,
            expected_next_reason=expectations.expected_next_reason,
            expected_next_blocker=expectations.expected_next_blocker,
            expected_next_summary=expectations.expected_next_summary,
            expected_coordination_status=expectations.expected_coordination_status,
            expected_coordination_reason=expectations.expected_coordination_reason,
            expected_coordination_summary=expectations.expected_coordination_summary,
        ),
    ):
        if checker is not None:
            return checker
    return None


def assert_service_status_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    expected_db: str,
    expected_db_source: str,
    expected_task_id: str,
    **expectation_kwargs: object,
) -> None:
    if result is None:
        return

    expectations = ServiceStatusExpectations.from_kwargs(expectation_kwargs)
    error = _collect_service_status_result_error(
        result=result,
        name=name,
        expected_db=expected_db,
        expected_db_source=expected_db_source,
        expected_task_id=expected_task_id,
        expectations=expectations,
    )
    if error is not None:
        errors.append(error)
