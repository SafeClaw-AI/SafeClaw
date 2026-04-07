from __future__ import annotations

from typing import Any

OWNER_ID = "safeclaw-mvp"
Expectation = tuple[str, Any, Any]


def _append_error(errors: list[str], label: str, message: str) -> None:
    errors.append(f"{label}: {message}")


def _expect_equal(errors: list[str], label: str, field: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        _append_error(errors, label, f"{field} expected {expected!r}, got {actual!r}")


def _expect_true(errors: list[str], label: str, field: str, value: Any) -> None:
    if value is not True:
        _append_error(errors, label, f"{field} expected True, got {value!r}")


def _expect_positive_int(errors: list[str], label: str, field: str, value: Any) -> None:
    if not isinstance(value, int) or value <= 0:
        _append_error(errors, label, f"{field} expected positive int, got {value!r}")


def _expect_prefix(errors: list[str], label: str, field: str, value: Any, prefix: str) -> None:
    if not isinstance(value, str) or not value.startswith(prefix):
        _append_error(errors, label, f"{field} missing prefix {prefix!r}: {value!r}")


def _expect_contains(errors: list[str], label: str, field: str, value: Any, fragment: str) -> None:
    if not isinstance(value, str) or fragment not in value:
        _append_error(errors, label, f"{field} missing fragment {fragment!r}: {value!r}")


def _assert_pairs(errors: list[str], label: str, expectations: list[Expectation]) -> None:
    for field, actual, expected in expectations:
        _expect_equal(errors, label, field, actual, expected)


def _result(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    result = payload.get("result")
    return result if isinstance(result, dict) else {}


def _status_parts(
    payload: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], list[Any], dict[str, Any]]:
    result = _result(payload)
    coordination = result.get("coordination") or {}
    recent_tasks = result.get("recent_tasks") or []
    current_session = result.get("current_session") or {}
    return result, coordination, recent_tasks, current_session


def _first_recent_task(
    recent_tasks: list[Any],
    errors: list[str],
    label: str,
    message: str = "recent task missing",
) -> dict[str, Any] | None:
    if not recent_tasks:
        _append_error(errors, label, message)
        return None
    task = recent_tasks[0]
    return task if isinstance(task, dict) else {}


def _assert_session_fields(
    payload: dict[str, Any] | None,
    errors: list[str],
    label: str,
    field: str,
    task_id: str,
    db: str,
    output: str,
    *,
    owner_id: str = OWNER_ID,
) -> None:
    if payload is None:
        _append_error(errors, label, f"{field} missing")
        return
    _assert_pairs(
        errors,
        label,
        [
            (f"{field}.task_id", payload.get("task_id"), task_id),
            (f"{field}.effect_id", payload.get("effect_id"), f"effect-{task_id}"),
            (f"{field}.db", payload.get("db"), db),
            (f"{field}.output", payload.get("output"), output),
            (f"{field}.owner_id", payload.get("owner_id"), owner_id),
        ],
    )


def assert_workspace_clear_result(payload: dict[str, Any] | None, errors: list[str], label: str) -> None:
    if payload is None:
        return
    _assert_pairs(errors, label, [("action", payload.get("action"), "workspace")])
    clear_result = _result(payload)
    clear_state = (clear_result.get("cleared"), clear_result.get("reason"))
    if clear_result.get("path") != r"target\mvp\workspace.json":
        _append_error(errors, label, "missing workspace path")
    elif clear_state not in {(True, "removed"), (False, "none")}:
        _append_error(errors, label, f"unexpected clear state {clear_state!r}")


def assert_forget_result(payload: dict[str, Any] | None, errors: list[str], label: str) -> None:
    if payload is None:
        return
    _assert_pairs(errors, label, [("action", payload.get("action"), "forget")])
    forget_result = _result(payload)
    forgot = forget_result.get("forgot")
    forget_reason = forget_result.get("reason")
    if (forgot, forget_reason) not in {(True, "removed"), (True, "already-absent"), (False, "none")}:
        _append_error(errors, label, f"unexpected forget state forgot={forgot!r} reason={forget_reason!r}")


def assert_forget_after_result(payload: dict[str, Any] | None, errors: list[str], label: str) -> None:
    if payload is None:
        return
    _assert_pairs(errors, label, [("action", payload.get("action"), "forget")])
    _expect_true(errors, label, "result.forgot", _result(payload).get("forgot"))


def assert_doctor_result(payload: dict[str, Any] | None, errors: list[str], label: str) -> None:
    if payload is None:
        return
    result = _result(payload)
    _assert_pairs(
        errors,
        label,
        [
            ("action", payload.get("action"), "doctor"),
            ("result.status", result.get("status"), "ready"),
            ("result.session", result.get("session"), None),
            ("result.db.source", (result.get("db") or {}).get("source"), "default"),
            ("result.output.source", (result.get("output") or {}).get("source"), "default"),
        ],
    )
    _expect_true(errors, label, "entrypoints.cmd.exists", (((result.get("entrypoints") or {}).get("cmd") or {}).get("exists")))
    _expect_true(errors, label, "entrypoints.ps1.exists", (((result.get("entrypoints") or {}).get("ps1") or {}).get("exists")))
    _expect_true(errors, label, "entrypoints.py.exists", (((result.get("entrypoints") or {}).get("py") or {}).get("exists")))


def assert_report_result(
    payload: dict[str, Any] | None,
    errors: list[str],
    label: str,
    task_id: str,
    db: str,
    output: str,
) -> None:
    if payload is None:
        return
    result = _result(payload)
    _assert_pairs(errors, label, [("action", payload.get("action"), "report")])
    _assert_session_fields(result.get("remembered_session"), errors, label, "remembered_session", task_id, db, output)
    _assert_pairs(
        errors,
        label,
        [
            ("source_hints.db", (result.get("source_hints") or {}).get("db"), "session"),
            ("source_hints.output", (result.get("source_hints") or {}).get("output"), "session"),
            ("source_hints.owner_id", (result.get("source_hints") or {}).get("owner_id"), "session"),
            ("source_hints.task_context", (result.get("source_hints") or {}).get("task_context"), "session"),
        ],
    )


def assert_seed_result(
    payload: dict[str, Any] | None,
    errors: list[str],
    label: str,
    action: str,
    task_id: str,
    db: str,
    output: str,
    *,
    owner_id: str = OWNER_ID,
) -> None:
    if payload is None:
        return
    _assert_pairs(errors, label, [("action", payload.get("action"), action)])
    _assert_session_fields(_result(payload).get("remembered_session"), errors, label, "remembered_session", task_id, db, output, owner_id=owner_id)


def assert_use_result(
    payload: dict[str, Any] | None,
    errors: list[str],
    label: str,
    task_id: str,
    db: str,
    output: str,
    *,
    output_source: str = "task_scope",
    owner_id: str | None = None,
    owner_id_source: str | None = None,
) -> None:
    if payload is None:
        return
    result = _result(payload)
    _assert_pairs(
        errors,
        label,
        [
            ("action", payload.get("action"), "use"),
            ("result.task_id", result.get("task_id"), task_id),
            ("result.db", result.get("db"), db),
            ("result.output", result.get("output"), output),
            ("result.output_source", result.get("output_source"), output_source),
        ],
    )
    if owner_id is not None:
        _expect_equal(errors, label, "result.owner_id", result.get("owner_id"), owner_id)
    if owner_id_source is not None:
        _expect_equal(errors, label, "result.owner_id_source", result.get("owner_id_source"), owner_id_source)


def assert_hibernated_status(
    payload: dict[str, Any] | None,
    errors: list[str],
    label: str,
    task_id: str,
    db: str,
    output: str,
) -> None:
    if payload is None:
        return
    result, coordination, recent_tasks, current_session = _status_parts(payload)
    _assert_pairs(
        errors,
        label,
        [
            ("result.db", result.get("db"), db),
            ("result.db_source", result.get("db_source"), "flag"),
            ("result.limit", result.get("limit"), 1),
            ("current_session.task_id", current_session.get("task_id"), task_id),
            ("workers.hibernated", (result.get("workers") or {}).get("hibernated"), 1),
            ("coordination.status", coordination.get("status"), "hibernated"),
            ("coordination.reason", coordination.get("reason"), "hibernated_waiting_for_resume"),
            ("coordination.summary", coordination.get("summary"), "inspect_and_resume_or_expire"),
            ("coordination.task_id", coordination.get("task_id"), task_id),
            ("coordination.target_scope", coordination.get("target_scope"), f"scope:{output}"),
            ("coordination.next_action", coordination.get("next_action"), "inspect"),
            ("coordination.next_task_id", coordination.get("next_task_id"), task_id),
            ("coordination.next_blocker", coordination.get("next_blocker"), "manual_review_needed"),
            ("coordination.scope_peer_count", coordination.get("scope_peer_count"), 0),
            ("coordination.scope_active_peer_count", coordination.get("scope_active_peer_count"), 0),
            ("coordination.scope_active_peer_task_id", coordination.get("scope_active_peer_task_id"), ""),
            ("coordination.scope_quarantine_active", coordination.get("scope_quarantine_active"), False),
            ("coordination.scope_quarantine_source", coordination.get("scope_quarantine_source"), "none"),
            ("coordination.scope_quarantine_task_id", coordination.get("scope_quarantine_task_id"), ""),
            ("coordination.scope_quarantine_count", coordination.get("scope_quarantine_count"), 0),
        ],
    )
    task = _first_recent_task(recent_tasks, errors, label)
    if task is None:
        return
    _assert_pairs(
        errors,
        label,
        [
            ("recent.task_id", task.get("task_id"), task_id),
            ("recent.current", task.get("current"), True),
            ("recent.worker_state", task.get("worker_state"), "hibernated"),
            ("recent.lease_state", task.get("lease_state"), "expired"),
            ("recent.next_action", task.get("next_action"), "inspect"),
            ("recent.next_reason", task.get("next_reason"), "hibernated_waiting_for_resume"),
            ("recent.next_blocker", task.get("next_blocker"), "manual_review_needed"),
            ("recent.next_summary", task.get("next_summary"), "blocked:action=inspect,blocker=manual_review_needed,reason=hibernated_waiting_for_resume"),
            ("recent.next_task_id", task.get("next_task_id"), task_id),
            ("recent.next_command", task.get("next_command"), f'safeclaw.cmd service-resume --db "{db}" --task-id "{task_id}" --limit 1 --report'),
            ("recent.coordination_status", task.get("coordination_status"), "hibernated"),
            ("recent.coordination_reason", task.get("coordination_reason"), "hibernated_waiting_for_resume"),
            ("recent.coordination_summary", task.get("coordination_summary"), "inspect_and_resume_or_expire"),
            ("recent.scope_peer_count", task.get("scope_peer_count"), 0),
            ("recent.scope_active_peer_count", task.get("scope_active_peer_count"), 0),
            ("recent.scope_active_peer_task_id", task.get("scope_active_peer_task_id"), ""),
            ("recent.scope_quarantine_active", task.get("scope_quarantine_active"), False),
            ("recent.scope_quarantine_source", task.get("scope_quarantine_source"), "none"),
            ("recent.scope_quarantine_task_id", task.get("scope_quarantine_task_id"), ""),
            ("recent.scope_quarantine_count", task.get("scope_quarantine_count"), 0),
        ],
    )


def assert_stalled_status(
    payload: dict[str, Any] | None,
    errors: list[str],
    label: str,
    task_id: str,
    db: str,
    output: str,
) -> None:
    if payload is None:
        return
    result, coordination, recent_tasks, current_session = _status_parts(payload)
    _assert_pairs(
        errors,
        label,
        [
            ("result.db", result.get("db"), db),
            ("result.db_source", result.get("db_source"), "flag"),
            ("result.limit", result.get("limit"), 1),
            ("current_session.task_id", current_session.get("task_id"), task_id),
            ("coordination.status", coordination.get("status"), "stalled"),
            ("coordination.reason", coordination.get("reason"), "active_lease_without_recent_heartbeat"),
            ("coordination.summary", coordination.get("summary"), "inspect_owner_or_wait_for_lease_expiry"),
            ("coordination.task_id", coordination.get("task_id"), task_id),
            ("coordination.target_scope", coordination.get("target_scope"), f"scope:{output}"),
            ("coordination.next_action", coordination.get("next_action"), "inspect"),
            ("coordination.next_task_id", coordination.get("next_task_id"), task_id),
            ("coordination.next_blocker", coordination.get("next_blocker"), "active_lease"),
            ("coordination.scope_peer_count", coordination.get("scope_peer_count"), 0),
            ("coordination.scope_active_peer_count", coordination.get("scope_active_peer_count"), 0),
            ("coordination.scope_active_peer_task_id", coordination.get("scope_active_peer_task_id"), ""),
            ("coordination.scope_quarantine_active", coordination.get("scope_quarantine_active"), False),
            ("coordination.scope_quarantine_source", coordination.get("scope_quarantine_source"), "none"),
            ("coordination.scope_quarantine_task_id", coordination.get("scope_quarantine_task_id"), ""),
            ("coordination.scope_quarantine_count", coordination.get("scope_quarantine_count"), 0),
        ],
    )
    task = _first_recent_task(recent_tasks, errors, label)
    if task is None:
        return
    _assert_pairs(
        errors,
        label,
        [
            ("recent.task_id", task.get("task_id"), task_id),
            ("recent.current", task.get("current"), True),
            ("recent.effect_status", task.get("effect_status"), "prepared"),
            ("recent.lease_state", task.get("lease_state"), "active"),
            ("recent.lease_owner_id", task.get("lease_owner_id"), OWNER_ID),
            ("recent.lease_fencing_token", task.get("lease_fencing_token"), 1),
            ("recent.lease_freshness", task.get("lease_freshness"), "lost"),
            ("recent.next_action", task.get("next_action"), "inspect"),
            ("recent.next_reason", task.get("next_reason"), "lease_still_active"),
            ("recent.next_blocker", task.get("next_blocker"), "active_lease"),
            ("recent.next_task_id", task.get("next_task_id"), task_id),
            ("recent.next_command", task.get("next_command"), f'safeclaw.cmd report --db "{db}" --task-id "{task_id}"'),
            ("recent.coordination_status", task.get("coordination_status"), "stalled"),
            ("recent.coordination_reason", task.get("coordination_reason"), "active_lease_without_recent_heartbeat"),
            ("recent.coordination_summary", task.get("coordination_summary"), "inspect_owner_or_wait_for_lease_expiry"),
            ("recent.scope_peer_count", task.get("scope_peer_count"), 0),
            ("recent.scope_active_peer_count", task.get("scope_active_peer_count"), 0),
            ("recent.scope_active_peer_task_id", task.get("scope_active_peer_task_id"), ""),
            ("recent.scope_quarantine_active", task.get("scope_quarantine_active"), False),
            ("recent.scope_quarantine_source", task.get("scope_quarantine_source"), "none"),
            ("recent.scope_quarantine_task_id", task.get("scope_quarantine_task_id"), ""),
            ("recent.scope_quarantine_count", task.get("scope_quarantine_count"), 0),
        ],
    )
    _expect_positive_int(errors, label, "recent.lease_remaining_ms", task.get("lease_remaining_ms"))
    next_summary = task.get("next_summary")
    _expect_prefix(errors, label, "recent.next_summary", next_summary, "wait:remaining_ms=")
    _expect_contains(errors, label, "recent.next_summary", next_summary, ",blocker=active_lease,reason=lease_still_active")


def assert_contended_status(
    payload: dict[str, Any] | None,
    errors: list[str],
    label: str,
    current_task_id: str,
    active_peer_task_id: str,
    db: str,
    scope: str,
) -> None:
    if payload is None:
        return
    result, coordination, recent_tasks, current_session = _status_parts(payload)
    _assert_pairs(
        errors,
        label,
        [
            ("result.db", result.get("db"), db),
            ("result.db_source", result.get("db_source"), "flag"),
            ("result.limit", result.get("limit"), 2),
            ("current_session.task_id", current_session.get("task_id"), current_task_id),
            ("coordination.status", coordination.get("status"), "contended"),
            ("coordination.reason", coordination.get("reason"), "same_scope_peer_active"),
            ("coordination.summary", coordination.get("summary"), "wait_for_scope_peer_release"),
            ("coordination.task_id", coordination.get("task_id"), current_task_id),
            ("coordination.target_scope", coordination.get("target_scope"), scope),
            ("coordination.next_action", coordination.get("next_action"), "retry"),
            ("coordination.next_task_id", coordination.get("next_task_id"), current_task_id),
            ("coordination.next_blocker", coordination.get("next_blocker"), "none"),
            ("coordination.scope_peer_count", coordination.get("scope_peer_count"), 1),
            ("coordination.scope_active_peer_count", coordination.get("scope_active_peer_count"), 1),
            ("coordination.scope_active_peer_task_id", coordination.get("scope_active_peer_task_id"), active_peer_task_id),
            ("coordination.scope_quarantine_active", coordination.get("scope_quarantine_active"), False),
            ("coordination.scope_quarantine_source", coordination.get("scope_quarantine_source"), "none"),
            ("coordination.scope_quarantine_task_id", coordination.get("scope_quarantine_task_id"), ""),
            ("coordination.scope_quarantine_count", coordination.get("scope_quarantine_count"), 0),
        ],
    )
    task = _first_recent_task(recent_tasks, errors, label)
    if task is None:
        return
    _assert_pairs(
        errors,
        label,
        [
            ("recent.task_id", task.get("task_id"), current_task_id),
            ("recent.current", task.get("current"), True),
            ("recent.effect_status", task.get("effect_status"), "prepared"),
            ("recent.lease_state", task.get("lease_state"), "expired"),
            ("recent.next_action", task.get("next_action"), "retry"),
            ("recent.next_reason", task.get("next_reason"), "failed_state_ready_for_retry"),
            ("recent.next_blocker", task.get("next_blocker"), "none"),
            ("recent.next_summary", task.get("next_summary"), "ready_now:action=retry,reason=failed_state_ready_for_retry"),
            ("recent.next_task_id", task.get("next_task_id"), current_task_id),
            ("recent.next_command", task.get("next_command"), f'safeclaw.cmd service-retry --db "{db}" --task-id "{current_task_id}" --limit 1 --report'),
            ("recent.coordination_status", task.get("coordination_status"), "contended"),
            ("recent.coordination_reason", task.get("coordination_reason"), "same_scope_peer_active"),
            ("recent.coordination_summary", task.get("coordination_summary"), "wait_for_scope_peer_release"),
            ("recent.scope_peer_count", task.get("scope_peer_count"), 1),
            ("recent.scope_active_peer_count", task.get("scope_active_peer_count"), 1),
            ("recent.scope_active_peer_task_id", task.get("scope_active_peer_task_id"), active_peer_task_id),
        ],
    )


def assert_quarantine_status(
    payload: dict[str, Any] | None,
    errors: list[str],
    label: str,
    current_task_id: str,
    quarantine_task_id: str,
    db: str,
    scope: str,
) -> None:
    if payload is None:
        return
    result, coordination, recent_tasks, current_session = _status_parts(payload)
    _assert_pairs(
        errors,
        label,
        [
            ("result.db", result.get("db"), db),
            ("result.db_source", result.get("db_source"), "flag"),
            ("result.limit", result.get("limit"), 2),
            ("current_session.task_id", current_session.get("task_id"), current_task_id),
            ("coordination.status", coordination.get("status"), "quarantined"),
            ("coordination.reason", coordination.get("reason"), "peer_executed_assumed_scope_quarantine"),
            ("coordination.summary", coordination.get("summary"), "wait_for_scope_reconcile"),
            ("coordination.task_id", coordination.get("task_id"), current_task_id),
            ("coordination.target_scope", coordination.get("target_scope"), scope),
            ("coordination.next_action", coordination.get("next_action"), "inspect"),
            ("coordination.next_task_id", coordination.get("next_task_id"), quarantine_task_id),
            ("coordination.next_blocker", coordination.get("next_blocker"), "scope_quarantine"),
            ("coordination.scope_peer_count", coordination.get("scope_peer_count"), 1),
            ("coordination.scope_active_peer_count", coordination.get("scope_active_peer_count"), 0),
            ("coordination.scope_active_peer_task_id", coordination.get("scope_active_peer_task_id"), ""),
            ("coordination.scope_quarantine_active", coordination.get("scope_quarantine_active"), True),
            ("coordination.scope_quarantine_source", coordination.get("scope_quarantine_source"), "peer"),
            ("coordination.scope_quarantine_task_id", coordination.get("scope_quarantine_task_id"), quarantine_task_id),
            ("coordination.scope_quarantine_count", coordination.get("scope_quarantine_count"), 1),
        ],
    )
    task = _first_recent_task(recent_tasks, errors, label)
    if task is None:
        return
    _assert_pairs(
        errors,
        label,
        [
            ("recent.task_id", task.get("task_id"), current_task_id),
            ("recent.current", task.get("current"), True),
            ("recent.effect_status", task.get("effect_status"), "prepared"),
            ("recent.lease_state", task.get("lease_state"), "expired"),
            ("recent.next_action", task.get("next_action"), "inspect"),
            ("recent.next_reason", task.get("next_reason"), "scope_quarantined_by_peer"),
            ("recent.next_blocker", task.get("next_blocker"), "scope_quarantine"),
            ("recent.next_summary", task.get("next_summary"), "blocked:action=inspect,blocker=scope_quarantine,reason=scope_quarantined_by_peer"),
            ("recent.next_task_id", task.get("next_task_id"), quarantine_task_id),
            ("recent.next_command", task.get("next_command"), f'safeclaw.cmd report --db "{db}" --task-id "{quarantine_task_id}"'),
            ("recent.coordination_status", task.get("coordination_status"), "quarantined"),
            ("recent.coordination_reason", task.get("coordination_reason"), "peer_executed_assumed_scope_quarantine"),
            ("recent.coordination_summary", task.get("coordination_summary"), "wait_for_scope_reconcile"),
            ("recent.scope_quarantine_active", task.get("scope_quarantine_active"), True),
            ("recent.scope_quarantine_source", task.get("scope_quarantine_source"), "peer"),
            ("recent.scope_quarantine_task_id", task.get("scope_quarantine_task_id"), quarantine_task_id),
            ("recent.scope_quarantine_count", task.get("scope_quarantine_count"), 1),
        ],
    )


def assert_reconcile_status_before(
    payload: dict[str, Any] | None,
    errors: list[str],
    label: str,
    task_id: str,
    db: str,
    output: str,
) -> None:
    if payload is None:
        return
    result, coordination, recent_tasks, current_session = _status_parts(payload)
    _assert_pairs(
        errors,
        label,
        [
            ("result.db", result.get("db"), db),
            ("result.db_source", result.get("db_source"), "flag"),
            ("result.limit", result.get("limit"), 1),
            ("current_session.task_id", current_session.get("task_id"), task_id),
            ("coordination.status", coordination.get("status"), "quarantined"),
            ("coordination.reason", coordination.get("reason"), "self_executed_assumed_scope_quarantine"),
            ("coordination.summary", coordination.get("summary"), "reconcile_self_before_scope_write"),
            ("coordination.task_id", coordination.get("task_id"), task_id),
            ("coordination.target_scope", coordination.get("target_scope"), f"scope:{output}"),
            ("coordination.next_action", coordination.get("next_action"), "inspect"),
            ("coordination.next_task_id", coordination.get("next_task_id"), task_id),
            ("coordination.next_blocker", coordination.get("next_blocker"), "scope_quarantine"),
            ("coordination.scope_peer_count", coordination.get("scope_peer_count"), 0),
            ("coordination.scope_active_peer_count", coordination.get("scope_active_peer_count"), 0),
            ("coordination.scope_active_peer_task_id", coordination.get("scope_active_peer_task_id"), ""),
            ("coordination.scope_quarantine_active", coordination.get("scope_quarantine_active"), True),
            ("coordination.scope_quarantine_source", coordination.get("scope_quarantine_source"), "self"),
            ("coordination.scope_quarantine_task_id", coordination.get("scope_quarantine_task_id"), task_id),
            ("coordination.scope_quarantine_count", coordination.get("scope_quarantine_count"), 1),
        ],
    )
    task = _first_recent_task(recent_tasks, errors, label)
    if task is None:
        return
    _assert_pairs(
        errors,
        label,
        [
            ("recent.task_id", task.get("task_id"), task_id),
            ("recent.current", task.get("current"), True),
            ("recent.effect_status", task.get("effect_status"), "executed_assumed"),
            ("recent.lease_state", task.get("lease_state"), "expired"),
            ("recent.next_action", task.get("next_action"), "inspect"),
            ("recent.next_reason", task.get("next_reason"), "executed_assumed_requires_reconcile"),
            ("recent.next_blocker", task.get("next_blocker"), "scope_quarantine"),
            ("recent.next_summary", task.get("next_summary"), "blocked:action=inspect,blocker=scope_quarantine,reason=executed_assumed_requires_reconcile"),
            ("recent.next_task_id", task.get("next_task_id"), task_id),
            ("recent.next_command", task.get("next_command"), f'safeclaw.cmd report --db "{db}" --task-id "{task_id}"'),
            ("recent.coordination_status", task.get("coordination_status"), "quarantined"),
            ("recent.coordination_reason", task.get("coordination_reason"), "self_executed_assumed_scope_quarantine"),
            ("recent.coordination_summary", task.get("coordination_summary"), "reconcile_self_before_scope_write"),
            ("recent.scope_peer_count", task.get("scope_peer_count"), 0),
            ("recent.scope_active_peer_count", task.get("scope_active_peer_count"), 0),
            ("recent.scope_active_peer_task_id", task.get("scope_active_peer_task_id"), ""),
            ("recent.scope_quarantine_active", task.get("scope_quarantine_active"), True),
            ("recent.scope_quarantine_source", task.get("scope_quarantine_source"), "self"),
            ("recent.scope_quarantine_task_id", task.get("scope_quarantine_task_id"), task_id),
            ("recent.scope_quarantine_count", task.get("scope_quarantine_count"), 1),
        ],
    )
    reconcile_commands = task.get("reconcile_commands") or {}
    _assert_pairs(
        errors,
        label,
        [
            ("recent.reconcile_commands.executed", reconcile_commands.get("executed"), f'safeclaw.cmd service-reconcile --db "{db}" --task-id "{task_id}" --decision executed --limit 1 --report'),
            ("recent.reconcile_commands.not_executed", reconcile_commands.get("not_executed"), f'safeclaw.cmd service-reconcile --db "{db}" --task-id "{task_id}" --decision not-executed --limit 1 --report'),
        ],
    )


def assert_session_priority_status(
    payload: dict[str, Any] | None,
    errors: list[str],
    label: str,
    current_task_id: str,
    peer_task_id: str,
    db: str,
    output: str,
) -> None:
    if payload is None:
        return
    result, coordination, recent_tasks, current_session = _status_parts(payload)
    _assert_pairs(
        errors,
        label,
        [
            ("result.db", result.get("db"), db),
            ("result.db_source", result.get("db_source"), "flag"),
            ("result.limit", result.get("limit"), 2),
            ("current_session.task_id", current_session.get("task_id"), current_task_id),
            ("current_session.output", current_session.get("output"), output),
            ("coordination.status", coordination.get("status"), "ready"),
            ("coordination.reason", coordination.get("reason"), "uncertain_state_ready_for_recover"),
            ("coordination.summary", coordination.get("summary"), "recover_now"),
            ("coordination.task_id", coordination.get("task_id"), current_task_id),
            ("coordination.target_scope", coordination.get("target_scope"), f"scope:{output}"),
            ("coordination.next_action", coordination.get("next_action"), "recover"),
            ("coordination.next_task_id", coordination.get("next_task_id"), current_task_id),
            ("coordination.next_blocker", coordination.get("next_blocker"), "none"),
            ("coordination.scope_peer_count", coordination.get("scope_peer_count"), 0),
            ("coordination.scope_active_peer_count", coordination.get("scope_active_peer_count"), 0),
            ("coordination.scope_active_peer_task_id", coordination.get("scope_active_peer_task_id"), ""),
            ("coordination.scope_quarantine_active", coordination.get("scope_quarantine_active"), False),
            ("coordination.scope_quarantine_source", coordination.get("scope_quarantine_source"), "none"),
            ("coordination.scope_quarantine_task_id", coordination.get("scope_quarantine_task_id"), ""),
            ("coordination.scope_quarantine_count", coordination.get("scope_quarantine_count"), 0),
        ],
    )
    if len(recent_tasks) < 2:
        _append_error(errors, label, f"expected at least 2 recent tasks, got {len(recent_tasks)!r}")
        return
    newer = recent_tasks[0] if isinstance(recent_tasks[0], dict) else {}
    current = recent_tasks[1] if isinstance(recent_tasks[1], dict) else {}
    _assert_pairs(
        errors,
        label,
        [
            ("recent[0].task_id", newer.get("task_id"), peer_task_id),
            ("recent[0].current", newer.get("current"), False),
            ("recent[0].next_action", newer.get("next_action"), "retry"),
            ("recent[0].coordination_summary", newer.get("coordination_summary"), "retry_now"),
            ("recent[1].task_id", current.get("task_id"), current_task_id),
            ("recent[1].current", current.get("current"), True),
            ("recent[1].next_action", current.get("next_action"), "recover"),
            ("recent[1].coordination_summary", current.get("coordination_summary"), "recover_now"),
        ],
    )


def assert_owner_alignment_status(
    payload: dict[str, Any] | None,
    errors: list[str],
    label: str,
    task_id: str,
    db: str,
    output: str,
    owner_id: str,
) -> None:
    if payload is None:
        return
    result, _, _, current_session = _status_parts(payload)
    _assert_pairs(
        errors,
        label,
        [
            ("result.db", result.get("db"), db),
            ("current_session.task_id", current_session.get("task_id"), task_id),
            ("current_session.output", current_session.get("output"), output),
            ("current_session.owner_id", current_session.get("owner_id"), owner_id),
        ],
    )
