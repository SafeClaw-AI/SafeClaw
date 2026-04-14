from __future__ import annotations

import importlib.util
import io
import json
import sqlite3
import shutil
import sys
import time
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

import mvp_operator_flow_helpers as flow_helpers
from mvp_state_guard import acquire_mvp_state_lock

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "mvp-wrapper.v1"
OWNER_ID = "safeclaw-mvp"
_OPERATOR_FLOW_STEP_COUNTER = 0
_OPERATOR_FLOW_STARTED_AT = 0.0
_SAFECLAW_MVP_MODULE: Any | None = None

RUN_TASK, RUN_DB, RUN_OUTPUT = "task-operator-flow-run", "target/mvp/operator-flow-run.db", "target/mvp/operator-flow-run.txt"
RETRY_TASK, RETRY_DB, RETRY_OUTPUT = "task-operator-flow-retry", "target/mvp/operator-flow-retry.db", "target/mvp/operator-flow-retry.txt"
RECOVER_TASK, RECOVER_DB, RECOVER_OUTPUT = "task-operator-flow-recover", "target/mvp/operator-flow-recover.db", "target/mvp/operator-flow-recover.txt"
RECONCILE_TASK, RECONCILE_DB, RECONCILE_OUTPUT = "task-operator-flow-reconcile", "target/mvp/operator-flow-reconcile.db", "target/mvp/operator-flow-reconcile.txt"
STALLED_TASK, STALLED_DB, STALLED_OUTPUT = "task-operator-flow-stalled", "target/mvp/operator-flow-stalled.db", "target/mvp/operator-flow-stalled.txt"
CONTENDED_A_TASK, CONTENDED_B_TASK, CONTENDED_DB = "task-operator-flow-contended-a", "task-operator-flow-contended-b", "target/mvp/operator-flow-contended.db"
CONTENDED_A_OUTPUT, CONTENDED_B_OUTPUT, CONTENDED_SHARED_OUTPUT = "target/mvp/operator-flow-contended-a.txt", "target/mvp/operator-flow-contended-b.txt", "target/mvp/operator-flow-contended-shared.txt"
QUARANTINE_A_TASK, QUARANTINE_B_TASK, QUARANTINE_DB = "task-operator-flow-quarantine-a", "task-operator-flow-quarantine-b", "target/mvp/operator-flow-quarantine.db"
QUARANTINE_A_OUTPUT, QUARANTINE_B_OUTPUT, QUARANTINE_SHARED_OUTPUT = "target/mvp/operator-flow-quarantine-a.txt", "target/mvp/operator-flow-quarantine-b.txt", "target/mvp/operator-flow-quarantine-shared.txt"
HIBERNATED_TASK, HIBERNATED_DB, HIBERNATED_OUTPUT = "task-operator-flow-hibernated", "target/mvp/operator-flow-hibernated.db", "target/mvp/operator-flow-hibernated.txt"
SESSION_PRIORITY_A_TASK, SESSION_PRIORITY_B_TASK, SESSION_PRIORITY_DB = "task-operator-flow-session-priority-a", "task-operator-flow-session-priority-b", "target/mvp/operator-flow-session-priority.db"
SESSION_PRIORITY_A_OUTPUT, SESSION_PRIORITY_B_OUTPUT = "target/mvp/operator-flow-session-priority-a.txt", "target/mvp/operator-flow-session-priority-b.txt"
OWNER_ALIGNMENT_A_TASK, OWNER_ALIGNMENT_B_TASK, OWNER_ALIGNMENT_DB = "task-operator-flow-owner-alignment-a", "task-operator-flow-owner-alignment-b", "target/mvp/operator-flow-owner-alignment.db"
OWNER_ALIGNMENT_A_OUTPUT, OWNER_ALIGNMENT_B_OUTPUT = "target/mvp/operator-flow-owner-alignment-a.txt", "target/mvp/operator-flow-owner-alignment-b.txt"
OWNER_ALIGNMENT_A_OWNER, OWNER_ALIGNMENT_B_OWNER = "safeclaw-owner-a", "safeclaw-owner-b"


def format_operator_flow_args(args: list[str]) -> str:
    preview = " ".join(args[:8])
    if len(args) > 8:
        preview = f"{preview} ..."
    return preview


def reset_operator_flow_progress() -> None:
    global _OPERATOR_FLOW_STEP_COUNTER, _OPERATOR_FLOW_STARTED_AT
    _OPERATOR_FLOW_STEP_COUNTER = 0
    _OPERATOR_FLOW_STARTED_AT = time.monotonic()


def start_operator_flow_step(label: str, detail: str) -> tuple[int, float]:
    global _OPERATOR_FLOW_STEP_COUNTER
    _OPERATOR_FLOW_STEP_COUNTER += 1
    sequence = _OPERATOR_FLOW_STEP_COUNTER
    started_at = time.monotonic()
    elapsed = started_at - _OPERATOR_FLOW_STARTED_AT if _OPERATOR_FLOW_STARTED_AT > 0 else 0.0
    print(
        f"[operator-flow {sequence:03d}] start +{elapsed:.1f}s => {label} :: {detail}",
        flush=True,
    )
    return sequence, started_at


def finish_operator_flow_step(sequence: int, started_at: float, *, exit_code: int, status: str) -> None:
    duration = time.monotonic() - started_at
    print(
        f"[operator-flow {sequence:03d}] done exit={exit_code} status={status} duration={duration:.1f}s",
        flush=True,
    )


def reset_operator_flow_state() -> None:
    state_root = REPO_ROOT / "target" / "mvp"
    for relative_path in [
        "last_session.json",
        "workspace.json",
        "operator-flow-run.db",
        "operator-flow-run.db-shm",
        "operator-flow-run.db-wal",
        "operator-flow-run.txt",
        "operator-flow-retry.db",
        "operator-flow-retry.db-shm",
        "operator-flow-retry.db-wal",
        "operator-flow-retry.txt",
        "operator-flow-recover.db",
        "operator-flow-recover.db-shm",
        "operator-flow-recover.db-wal",
        "operator-flow-recover.txt",
        "operator-flow-reconcile.db",
        "operator-flow-reconcile.db-shm",
        "operator-flow-reconcile.db-wal",
        "operator-flow-reconcile.txt",
        "operator-flow-stalled.db",
        "operator-flow-stalled.db-shm",
        "operator-flow-stalled.db-wal",
        "operator-flow-stalled.txt",
        "operator-flow-contended.db",
        "operator-flow-contended.db-shm",
        "operator-flow-contended.db-wal",
        "operator-flow-contended-a.txt",
        "operator-flow-contended-b.txt",
        "operator-flow-quarantine.db",
        "operator-flow-quarantine.db-shm",
        "operator-flow-quarantine.db-wal",
        "operator-flow-quarantine-a.txt",
        "operator-flow-quarantine-b.txt",
        "operator-flow-hibernated.db",
        "operator-flow-hibernated.db-shm",
        "operator-flow-hibernated.db-wal",
        "operator-flow-hibernated.txt",
        "operator-flow-session-priority.db",
        "operator-flow-session-priority.db-shm",
        "operator-flow-session-priority.db-wal",
        "operator-flow-session-priority-a.txt",
        "operator-flow-session-priority-b.txt",
        "operator-flow-owner-alignment.db",
        "operator-flow-owner-alignment.db-shm",
        "operator-flow-owner-alignment.db-wal",
        "operator-flow-owner-alignment-a.txt",
        "operator-flow-owner-alignment-b.txt",
    ]:
        path = state_root / relative_path
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)


append_error = flow_helpers._append_error
expect_equal = flow_helpers._expect_equal
expect_true = flow_helpers._expect_true
assert_session_fields = flow_helpers._assert_session_fields



def load_safeclaw_mvp_module() -> Any:
    global _SAFECLAW_MVP_MODULE
    if _SAFECLAW_MVP_MODULE is not None:
        return _SAFECLAW_MVP_MODULE
    module_path = REPO_ROOT / "tools" / "mvp" / "safeclaw_mvp.py"
    spec = importlib.util.spec_from_file_location("safeclaw_mvp_operator_flow", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load wrapper module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _SAFECLAW_MVP_MODULE = module
    return module


def _invoke_json_module(module: Any, args: list[str]) -> tuple[int, str]:
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    try:
        with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
            exit_code = int(module.main(["safeclaw_mvp.py", *args, "--json"]) or 0)
    except SystemExit as error:
        exit_code = int(error.code or 0)
    except Exception as error:
        traceback.print_exception(error, file=stderr_buffer)
        exit_code = 1
    return exit_code, (stdout_buffer.getvalue() + stderr_buffer.getvalue()).strip()


def _decode_json_output(exit_code: int, output: str) -> tuple[int, str, dict[str, Any] | None]:
    if exit_code != 0:
        return exit_code, output, None
    try:
        payload = json.loads(output)
    except json.JSONDecodeError as error:
        detail = f"invalid json: {error}"
        return exit_code, f"{output}\n{detail}".strip(), None
    if not isinstance(payload, dict):
        return exit_code, output, None
    return exit_code, output, payload


def load_json(args: list[str]) -> tuple[int, str, dict[str, Any] | None]:
    module = load_safeclaw_mvp_module()
    exit_code, output = _invoke_json_module(module, args)
    return _decode_json_output(exit_code, output)


def _extract_session_result(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if payload is None or payload.get("ok") is not True or payload.get("action") != "session":
        return None
    result = payload.get("result")
    return result if isinstance(result, dict) else None


def _matches_session(
    result: dict[str, Any],
    task_id: str,
    db: str,
    output: str,
    owner_id: str | None,
) -> bool:
    return (
        result.get("task_id") == task_id
        and result.get("db") == db
        and result.get("output") == output
        and (owner_id is None or result.get("owner_id") == owner_id)
    )


def wait_for_session(
    task_id: str,
    db: str,
    output: str,
    errors: list[str],
    label: str,
    *,
    owner_id: str | None = None,
) -> None:
    sequence, started_at = start_operator_flow_step(label, f"wait-session task={task_id}")
    exit_code = 1
    status = "timeout tries=0"
    last_observed: dict[str, Any] | None = None
    try:
        for attempt in range(1, 13):
            exit_code, _, payload = load_json(["session"])
            result = _extract_session_result(payload if exit_code == 0 else None)
            if result is not None:
                last_observed = result
                if _matches_session(result, task_id, db, output, owner_id):
                    status = f"matched tries={attempt}"
                    exit_code = 0
                    return
            status = f"waiting tries={attempt}"
            time.sleep(0.1)
        append_error(errors, label, f"session did not converge to {task_id!r}; last={last_observed!r}")
        status = "timeout tries=12"
    finally:
        finish_operator_flow_step(sequence, started_at, exit_code=exit_code, status=status)

def run_json(args: list[str], label: str, errors: list[str]) -> dict[str, Any] | None:
    sequence, started_at = start_operator_flow_step(label, format_operator_flow_args([*args, "--json"]))
    status = "ok"
    exit_code = 0
    try:
        exit_code, output, payload = load_json(args)
        if exit_code != 0:
            status = "failed"
            append_error(errors, label, f"exit={exit_code} output={output!r}")
            return None

        if payload is None:
            status = "invalid-json"
            append_error(errors, label, f"invalid json output={output!r}")
            return None

        expect_true(errors, label, "ok", payload.get("ok"))
        expect_equal(errors, label, "schema_version", payload.get("schema_version"), SCHEMA_VERSION)
        return payload
    finally:
        finish_operator_flow_step(sequence, started_at, exit_code=exit_code, status=status)



def _mapping(payload: dict[str, Any], field: str) -> dict[str, Any]:
    value = payload.get(field)
    return value if isinstance(value, dict) else {}


def _items(payload: dict[str, Any], field: str) -> list[Any]:
    value = payload.get(field)
    return value if isinstance(value, list) else []


def _assert_service_combo_steps(
    result: dict[str, Any],
    errors: list[str],
    label: str,
    *,
    expected_steps: list[str],
) -> None:
    steps = result.get("steps") or []
    expect_equal(errors, label, "steps.actions", [step.get("action") for step in steps], expected_steps)
    if len(steps) >= 2:
        expect_true(errors, label, "steps[0].ok", steps[0].get("ok"))
        expect_true(errors, label, "steps[1].ok", steps[1].get("ok"))
        expect_equal(errors, label, "steps[0].source_hints.db", (steps[0].get("source_hints") or {}).get("db"), "flag")
        expect_equal(errors, label, "steps[1].source_hints.db", (steps[1].get("source_hints") or {}).get("db"), "flag")
        expect_equal(
            errors,
            label,
            "steps[1].source_hints.task_context",
            (steps[1].get("source_hints") or {}).get("task_context"),
            "session",
        )
    if len(steps) >= 3:
        expect_true(errors, label, "steps[2].ok", steps[2].get("ok"))


def _assert_service_combo_primary_payload(
    result: dict[str, Any],
    errors: list[str],
    label: str,
    *,
    primary_action: str,
    task_id: str,
    db: str,
    output: str,
    expected_output_source: str,
    expected_owner_source: str,
) -> None:
    primary = result.get(primary_action) or {}
    expect_equal(errors, label, f"{primary_action}.prepared[0]", (primary.get("prepared") or [None])[0], primary_action)
    expect_equal(errors, label, f"{primary_action}.source_hints.db", (primary.get("source_hints") or {}).get("db"), "flag")
    expect_equal(
        errors,
        label,
        f"{primary_action}.source_hints.output",
        (primary.get("source_hints") or {}).get("output"),
        expected_output_source,
    )
    expect_equal(
        errors,
        label,
        f"{primary_action}.source_hints.owner_id",
        (primary.get("source_hints") or {}).get("owner_id"),
        expected_owner_source,
    )
    expect_equal(errors, label, f"{primary_action}.source_hints.task_context", (primary.get("source_hints") or {}).get("task_context"), "flag")
    assert_session_fields(primary.get("remembered_session"), errors, label, f"{primary_action}.remembered_session", task_id, db, output)


def _assert_service_combo_report_payload(
    result: dict[str, Any],
    errors: list[str],
    label: str,
    *,
    task_id: str,
    db: str,
    output: str,
) -> None:
    report = result.get("report") or {}
    expect_equal(errors, label, "report.prepared[0]", (report.get("prepared") or [None])[0], "report")
    expect_equal(errors, label, "report.saved_session", report.get("saved_session"), None)
    assert_session_fields(report.get("remembered_session"), errors, label, "report.remembered_session", task_id, db, output)


def _assert_service_combo_runtime_status(
    status: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    _assert_service_combo_runtime_profile(status, errors, label)
    _assert_service_combo_provider_status(status, errors, label)
    _assert_service_combo_offline_gate(status, errors, label)
    _assert_service_combo_runtime_details(status, errors, label)


def _assert_service_combo_runtime_profile(
    status: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    expect_equal(errors, label, "service_status.runtime_profile.mode", ((status.get("runtime_profile") or {}).get("mode")), "local_mvp")
    expect_equal(errors, label, "service_status.runtime_profile.offline_ready", ((status.get("runtime_profile") or {}).get("offline_ready")), True)
    expect_equal(errors, label, "service_status.runtime_profile.llm_required", ((status.get("runtime_profile") or {}).get("llm_required")), False)
    expect_equal(errors, label, "service_status.runtime_profile.sidecar_required", ((status.get("runtime_profile") or {}).get("sidecar_required")), False)
    expect_equal(errors, label, "service_status.heartbeat.latest_updated_at", ((status.get("heartbeat") or {}).get("latest_updated_at")), None)
    expect_equal(errors, label, "service_status.heartbeat.latest_age_ms", ((status.get("heartbeat") or {}).get("latest_age_ms")), None)


def _assert_service_combo_provider_status(
    status: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    expect_equal(errors, label, "service_status.model_provider.status", ((status.get("model_provider") or {}).get("status")), "not-configured")
    expect_equal(errors, label, "service_status.model_provider.required", ((status.get("model_provider") or {}).get("required")), False)
    expect_equal(errors, label, "service_status.model_provider.configured", ((status.get("model_provider") or {}).get("configured")), False)
    expect_equal(errors, label, "service_status.model_provider.degradation_mode", ((status.get("model_provider") or {}).get("degradation_mode")), "local_only_ok")
    expect_equal(errors, label, "service_status.sidecar.status", ((status.get("sidecar") or {}).get("status")), "not-configured")
    expect_equal(errors, label, "service_status.sidecar.required", ((status.get("sidecar") or {}).get("required")), False)
    expect_equal(errors, label, "service_status.sidecar.configured", ((status.get("sidecar") or {}).get("configured")), False)


def _assert_service_combo_offline_gate(
    status: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    expect_equal(errors, label, "service_status.offline_gate.status", ((status.get("offline_gate") or {}).get("status")), "blocked")
    expect_equal(errors, label, "service_status.offline_gate.reason", ((status.get("offline_gate") or {}).get("reason")), "ERR_AI_PROVIDER_UNAVAILABLE")
    expect_equal(errors, label, "service_status.offline_gate.summary", ((status.get("offline_gate") or {}).get("summary")), "ai_actions_require_provider")
    expect_equal(errors, label, "service_status.offline_gate.requested_action", ((status.get("offline_gate") or {}).get("requested_action")), "ai-reason")
    expect_equal(errors, label, "service_status.offline_gate.requires_model", ((status.get("offline_gate") or {}).get("requires_model")), True)
    expect_equal(errors, label, "service_status.offline_gate.requires_sidecar", ((status.get("offline_gate") or {}).get("requires_sidecar")), True)
    expect_equal(errors, label, "service_status.offline_gate.next_command", ((status.get("offline_gate") or {}).get("next_command")), "safeclaw.cmd preflight --action ai-reason")
    expect_equal(errors, label, "service_status.offline_gate.error_code", ((status.get("offline_gate") or {}).get("error_code")), "ERR_AI_PROVIDER_UNAVAILABLE")


def _assert_service_combo_runtime_details(
    status: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if not (status.get("runtime_profile") or {}).get("detail"):
        append_error(errors, label, "service_status.runtime_profile.detail missing")
    if not (status.get("model_provider") or {}).get("detail"):
        append_error(errors, label, "service_status.model_provider.detail missing")
    if not (status.get("sidecar") or {}).get("detail"):
        append_error(errors, label, "service_status.sidecar.detail missing")


def _assert_service_combo_coordination(
    coordination: dict[str, Any],
    errors: list[str],
    label: str,
    *,
    task_id: str,
    output: str,
) -> None:
    expect_equal(errors, label, "service_status.coordination.status", coordination.get("status"), "clear")
    expect_equal(errors, label, "service_status.coordination.reason", coordination.get("reason"), "execution_already_confirmed")
    expect_equal(errors, label, "service_status.coordination.summary", coordination.get("summary"), "no_followup_needed")
    expect_equal(errors, label, "service_status.coordination.task_id", coordination.get("task_id"), task_id)
    expect_equal(errors, label, "service_status.coordination.target_scope", coordination.get("target_scope"), f"scope:{output}")
    expect_equal(errors, label, "service_status.coordination.next_action", coordination.get("next_action"), "ok")
    expect_equal(errors, label, "service_status.coordination.next_task_id", coordination.get("next_task_id"), task_id)
    expect_equal(errors, label, "service_status.coordination.next_blocker", coordination.get("next_blocker"), "none")
    expect_equal(errors, label, "service_status.coordination.scope_peer_count", coordination.get("scope_peer_count"), 0)
    expect_equal(errors, label, "service_status.coordination.scope_active_peer_count", coordination.get("scope_active_peer_count"), 0)
    expect_equal(errors, label, "service_status.coordination.scope_active_peer_task_id", coordination.get("scope_active_peer_task_id"), "")
    expect_equal(errors, label, "service_status.coordination.scope_quarantine_active", coordination.get("scope_quarantine_active"), False)
    expect_equal(errors, label, "service_status.coordination.scope_quarantine_source", coordination.get("scope_quarantine_source"), "none")
    expect_equal(errors, label, "service_status.coordination.scope_quarantine_task_id", coordination.get("scope_quarantine_task_id"), "")
    expect_equal(errors, label, "service_status.coordination.scope_quarantine_count", coordination.get("scope_quarantine_count"), 0)


def _assert_service_combo_recent_tasks(
    recent_tasks: list[dict[str, Any]],
    errors: list[str],
    label: str,
    *,
    task_id: str,
) -> None:
    if not recent_tasks:
        append_error(errors, label, "service_status.recent_tasks missing")
        return
    expect_equal(errors, label, "service_status.recent_tasks[0].task_id", recent_tasks[0].get("task_id"), task_id)
    expect_true(errors, label, "service_status.recent_tasks[0].current", recent_tasks[0].get("current"))
    expect_equal(errors, label, "service_status.recent_tasks[0].next_action", recent_tasks[0].get("next_action"), "ok")
    expect_equal(errors, label, "service_status.recent_tasks[0].next_reason", recent_tasks[0].get("next_reason"), "execution_already_confirmed")
    expect_equal(errors, label, "service_status.recent_tasks[0].next_blocker", recent_tasks[0].get("next_blocker"), "none")
    expect_equal(errors, label, "service_status.recent_tasks[0].coordination_status", recent_tasks[0].get("coordination_status"), "clear")
    expect_equal(errors, label, "service_status.recent_tasks[0].coordination_reason", recent_tasks[0].get("coordination_reason"), "execution_already_confirmed")
    expect_equal(errors, label, "service_status.recent_tasks[0].coordination_summary", recent_tasks[0].get("coordination_summary"), "no_followup_needed")
    expect_equal(errors, label, "service_status.recent_tasks[0].next_task_id", recent_tasks[0].get("next_task_id"), task_id)
    expect_equal(errors, label, "service_status.recent_tasks[0].scope_peer_count", recent_tasks[0].get("scope_peer_count"), 0)
    expect_equal(errors, label, "service_status.recent_tasks[0].scope_active_peer_count", recent_tasks[0].get("scope_active_peer_count"), 0)
    expect_equal(errors, label, "service_status.recent_tasks[0].scope_active_peer_task_id", recent_tasks[0].get("scope_active_peer_task_id"), "")
    expect_equal(errors, label, "service_status.recent_tasks[0].scope_quarantine_active", recent_tasks[0].get("scope_quarantine_active"), False)
    expect_equal(errors, label, "service_status.recent_tasks[0].scope_quarantine_source", recent_tasks[0].get("scope_quarantine_source"), "none")
    expect_equal(errors, label, "service_status.recent_tasks[0].scope_quarantine_task_id", recent_tasks[0].get("scope_quarantine_task_id"), "")
    expect_equal(errors, label, "service_status.recent_tasks[0].scope_quarantine_count", recent_tasks[0].get("scope_quarantine_count"), 0)


def _assert_service_combo_status(
    result: dict[str, Any],
    errors: list[str],
    label: str,
    *,
    task_id: str,
    db: str,
    output: str,
) -> None:
    status = _mapping(result, "service_status")
    coordination = _mapping(status, "coordination")
    recent_tasks = _items(status, "recent_tasks")
    queue = _mapping(status, "queue")
    workers = _mapping(status, "workers")
    effects = _mapping(status, "effects")
    heartbeat = _mapping(status, "heartbeat")
    expect_equal(errors, label, "service_status.db", status.get("db"), db)
    expect_equal(errors, label, "service_status.db_source", status.get("db_source"), "flag")
    expect_equal(errors, label, "service_status.limit", status.get("limit"), 1)
    expect_equal(errors, label, "service_status.queue.completed", queue.get("completed"), 1)
    expect_equal(errors, label, "service_status.workers.succeeded", workers.get("succeeded"), 1)
    expect_equal(errors, label, "service_status.effects.executed", effects.get("executed"), 1)
    expect_equal(errors, label, "service_status.heartbeat.interval_ms", heartbeat.get("interval_ms"), 10000)
    expect_equal(errors, label, "service_status.heartbeat.event_driven", heartbeat.get("event_driven"), True)
    expect_equal(errors, label, "service_status.heartbeat.latest_freshness", heartbeat.get("latest_freshness"), "none")
    expect_equal(errors, label, "service_status.heartbeat.status", heartbeat.get("status"), "idle")
    expect_equal(errors, label, "service_status.heartbeat.reason", heartbeat.get("reason"), "no_active_lease_heartbeat")
    _assert_service_combo_runtime_status(status, errors, label)
    _assert_service_combo_coordination(coordination, errors, label, task_id=task_id, output=output)
    _assert_service_combo_recent_tasks(recent_tasks, errors, label, task_id=task_id)


def assert_service_combo(
    payload: dict[str, Any] | None,
    errors: list[str],
    label: str,
    combo_action: str,
    primary_action: str,
    task_id: str,
    db: str,
    output: str,
    expected_output_source: str,
    expected_owner_source: str,
    expected_steps: list[str] | None = None,
    expect_report_payload: bool = False,
) -> None:
    if payload is None:
        return

    expect_equal(errors, label, "action", payload.get("action"), combo_action)
    result = payload.get("result") or {}
    expected_steps = expected_steps or [primary_action, "service-status"]
    _assert_service_combo_steps(result, errors, label, expected_steps=expected_steps)
    assert_session_fields(result.get("remembered_session"), errors, label, "remembered_session", task_id, db, output)
    assert_session_fields(result.get("session"), errors, label, "session", task_id, db, output)
    _assert_service_combo_primary_payload(
        result,
        errors,
        label,
        primary_action=primary_action,
        task_id=task_id,
        db=db,
        output=output,
        expected_output_source=expected_output_source,
        expected_owner_source=expected_owner_source,
    )

    if expect_report_payload:
        _assert_service_combo_report_payload(result, errors, label, task_id=task_id, db=db, output=output)
    _assert_service_combo_status(result, errors, label, task_id=task_id, db=db, output=output)



def _run_operator_flow_prelude(errors: list[str]) -> None:
    workspace_clear_before = run_json(["workspace", "--clear"], "operator-flow/workspace-clear-before", errors)
    flow_helpers.assert_workspace_clear_result(workspace_clear_before, errors, "operator-flow/workspace-clear-before")
    forget_before = run_json(["forget"], "operator-flow/forget-before", errors)
    flow_helpers.assert_forget_result(forget_before, errors, "operator-flow/forget-before")
    doctor = run_json(["doctor"], "operator-flow/doctor", errors)
    flow_helpers.assert_doctor_result(doctor, errors, "operator-flow/doctor")
    service_run = run_json(["service-run", "--task-id", RUN_TASK, "--db", RUN_DB, "--output", RUN_OUTPUT, "--limit", "1"], "operator-flow/service-run", errors)
    assert_service_combo(service_run, errors, "operator-flow/service-run", combo_action="service-run", primary_action="run", task_id=RUN_TASK, db=RUN_DB, output=RUN_OUTPUT, expected_output_source="flag", expected_owner_source="default")
    wait_for_session(RUN_TASK, RUN_DB, RUN_OUTPUT, errors, "operator-flow/service-run")
    report = run_json(["report"], "operator-flow/report", errors)
    flow_helpers.assert_report_result(report, errors, "operator-flow/report", RUN_TASK, RUN_DB, RUN_OUTPUT)


def _run_retry_and_recover_flow(errors: list[str]) -> None:
    seed_failed = run_json(["seed-failed", "--task-id", RETRY_TASK, "--db", RETRY_DB, "--output", RETRY_OUTPUT], "operator-flow/seed-failed", errors)
    flow_helpers.assert_seed_result(seed_failed, errors, "operator-flow/seed-failed", "seed-failed", RETRY_TASK, RETRY_DB, RETRY_OUTPUT)
    wait_for_session(RETRY_TASK, RETRY_DB, RETRY_OUTPUT, errors, "operator-flow/seed-failed")
    service_retry = run_json(["service-retry", "--db", RETRY_DB, "--task-id", RETRY_TASK, "--limit", "1"], "operator-flow/service-retry", errors)
    assert_service_combo(service_retry, errors, "operator-flow/service-retry", combo_action="service-retry", primary_action="retry", task_id=RETRY_TASK, db=RETRY_DB, output=RETRY_OUTPUT, expected_output_source="session", expected_owner_source="session")
    seed_crash = run_json(["seed-crash", "--task-id", RECOVER_TASK, "--db", RECOVER_DB, "--output", RECOVER_OUTPUT], "operator-flow/seed-crash", errors)
    flow_helpers.assert_seed_result(seed_crash, errors, "operator-flow/seed-crash", "seed-crash", RECOVER_TASK, RECOVER_DB, RECOVER_OUTPUT)
    wait_for_session(RECOVER_TASK, RECOVER_DB, RECOVER_OUTPUT, errors, "operator-flow/seed-crash")
    service_recover = run_json(["service-recover", "--db", RECOVER_DB, "--task-id", RECOVER_TASK, "--limit", "1"], "operator-flow/service-recover", errors)
    assert_service_combo(service_recover, errors, "operator-flow/service-recover", combo_action="service-recover", primary_action="recover", task_id=RECOVER_TASK, db=RECOVER_DB, output=RECOVER_OUTPUT, expected_output_source="session", expected_owner_source="session")


def _run_hibernated_and_stalled_flow(errors: list[str]) -> None:
    seed_hibernated = run_json(["seed-hibernated", "--task-id", HIBERNATED_TASK, "--db", HIBERNATED_DB, "--output", HIBERNATED_OUTPUT], "operator-flow/seed-hibernated", errors)
    flow_helpers.assert_seed_result(seed_hibernated, errors, "operator-flow/seed-hibernated", "seed-hibernated", HIBERNATED_TASK, HIBERNATED_DB, HIBERNATED_OUTPUT)
    wait_for_session(HIBERNATED_TASK, HIBERNATED_DB, HIBERNATED_OUTPUT, errors, "operator-flow/seed-hibernated")
    hibernated_status = run_json(["service-status", "--db", HIBERNATED_DB, "--limit", "1"], "operator-flow/service-status-hibernated", errors)
    flow_helpers.assert_hibernated_status(hibernated_status, errors, "operator-flow/service-status-hibernated", HIBERNATED_TASK, HIBERNATED_DB, HIBERNATED_OUTPUT)
    service_resume = run_json(["service-resume", "--db", HIBERNATED_DB, "--task-id", HIBERNATED_TASK, "--limit", "1"], "operator-flow/service-resume", errors)
    assert_service_combo(service_resume, errors, "operator-flow/service-resume", combo_action="service-resume", primary_action="resume", task_id=HIBERNATED_TASK, db=HIBERNATED_DB, output=HIBERNATED_OUTPUT, expected_output_source="session", expected_owner_source="session")
    seed_failed_stalled = run_json(["seed-failed", "--task-id", STALLED_TASK, "--db", STALLED_DB, "--output", STALLED_OUTPUT], "operator-flow/seed-failed-stalled", errors)
    flow_helpers.assert_seed_result(seed_failed_stalled, errors, "operator-flow/seed-failed-stalled", "seed-failed", STALLED_TASK, STALLED_DB, STALLED_OUTPUT)
    with sqlite3.connect(REPO_ROOT / STALLED_DB) as connection:
        connection.execute(
            """
            UPDATE orchestrator_leases
            SET expires_at_ms = ?1,
                released_at_ms = NULL
            WHERE task_id = ?2
            """,
            (int(time.time() * 1000) + 45_000, STALLED_TASK),
        )
        connection.commit()
    stalled_status = run_json(["service-status", "--db", STALLED_DB, "--limit", "1"], "operator-flow/service-status-stalled", errors)
    flow_helpers.assert_stalled_status(stalled_status, errors, "operator-flow/service-status-stalled", STALLED_TASK, STALLED_DB, STALLED_OUTPUT)


def _run_contended_flow(errors: list[str]) -> None:
    seed_failed_contended_a = run_json(["seed-failed", "--task-id", CONTENDED_A_TASK, "--db", CONTENDED_DB, "--output", CONTENDED_A_OUTPUT], "operator-flow/seed-failed-contended-a", errors)
    flow_helpers.assert_seed_result(seed_failed_contended_a, errors, "operator-flow/seed-failed-contended-a", "seed-failed", CONTENDED_A_TASK, CONTENDED_DB, CONTENDED_A_OUTPUT)
    seed_failed_contended_b = run_json(["seed-failed", "--task-id", CONTENDED_B_TASK, "--db", CONTENDED_DB, "--output", CONTENDED_B_OUTPUT], "operator-flow/seed-failed-contended-b", errors)
    flow_helpers.assert_seed_result(seed_failed_contended_b, errors, "operator-flow/seed-failed-contended-b", "seed-failed", CONTENDED_B_TASK, CONTENDED_DB, CONTENDED_B_OUTPUT)
    contended_scope = f"scope:{CONTENDED_SHARED_OUTPUT}"
    with sqlite3.connect(REPO_ROOT / CONTENDED_DB) as connection:
        connection.execute("UPDATE orchestrator_tasks SET target_scope = ?1 WHERE task_id IN (?2, ?3)", (contended_scope, CONTENDED_A_TASK, CONTENDED_B_TASK))
        connection.execute("UPDATE orchestrator_leases SET expires_at_ms = ?1, released_at_ms = NULL WHERE task_id = ?2", (int(time.time() * 1000) - 1_000, CONTENDED_A_TASK))
        connection.execute("UPDATE orchestrator_leases SET expires_at_ms = ?1, released_at_ms = NULL WHERE task_id = ?2", (int(time.time() * 1000) + 45_000, CONTENDED_B_TASK))
        connection.execute("UPDATE task_snapshots SET updated_at = ?1 WHERE task_id = ?2", (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 5)), CONTENDED_A_TASK))
        connection.commit()
    use_contended = run_json(["use", "--db", CONTENDED_DB, "--task-id", CONTENDED_A_TASK], "operator-flow/use-contended", errors)
    flow_helpers.assert_use_result(use_contended, errors, "operator-flow/use-contended", CONTENDED_A_TASK, CONTENDED_DB, CONTENDED_SHARED_OUTPUT)
    contended_status = run_json(["service-status", "--db", CONTENDED_DB, "--limit", "2"], "operator-flow/service-status-contended", errors)
    flow_helpers.assert_contended_status(contended_status, errors, "operator-flow/service-status-contended", CONTENDED_A_TASK, CONTENDED_B_TASK, CONTENDED_DB, contended_scope)


def _run_quarantine_flow(errors: list[str]) -> None:
    seed_failed_quarantine_a = run_json(["seed-failed", "--task-id", QUARANTINE_A_TASK, "--db", QUARANTINE_DB, "--output", QUARANTINE_A_OUTPUT], "operator-flow/seed-failed-quarantine-a", errors)
    flow_helpers.assert_seed_result(seed_failed_quarantine_a, errors, "operator-flow/seed-failed-quarantine-a", "seed-failed", QUARANTINE_A_TASK, QUARANTINE_DB, QUARANTINE_A_OUTPUT)
    seed_failed_quarantine_b = run_json(["seed-failed", "--task-id", QUARANTINE_B_TASK, "--db", QUARANTINE_DB, "--output", QUARANTINE_B_OUTPUT], "operator-flow/seed-failed-quarantine-b", errors)
    flow_helpers.assert_seed_result(seed_failed_quarantine_b, errors, "operator-flow/seed-failed-quarantine-b", "seed-failed", QUARANTINE_B_TASK, QUARANTINE_DB, QUARANTINE_B_OUTPUT)
    with sqlite3.connect(REPO_ROOT / QUARANTINE_DB) as connection:
        connection.execute("UPDATE orchestrator_tasks SET target_scope = ?1 WHERE task_id IN (?2, ?3)", (f"scope:{QUARANTINE_SHARED_OUTPUT}", QUARANTINE_A_TASK, QUARANTINE_B_TASK))
        connection.execute("UPDATE task_snapshots SET effect_status = ?1 WHERE task_id = ?2", ("executed_assumed", QUARANTINE_A_TASK))
        connection.execute("UPDATE task_snapshots SET updated_at = ?1 WHERE task_id = ?2", (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 5)), QUARANTINE_B_TASK))
        connection.execute("UPDATE orchestrator_leases SET expires_at_ms = ?1, released_at_ms = NULL WHERE task_id = ?2", (int(time.time() * 1000) - 1_000, QUARANTINE_A_TASK))
        connection.execute("UPDATE orchestrator_leases SET expires_at_ms = ?1, released_at_ms = NULL WHERE task_id = ?2", (int(time.time() * 1000) - 1_000, QUARANTINE_B_TASK))
        connection.commit()
    use_quarantine = run_json(["use", "--db", QUARANTINE_DB, "--task-id", QUARANTINE_B_TASK], "operator-flow/use-quarantine", errors)
    flow_helpers.assert_use_result(use_quarantine, errors, "operator-flow/use-quarantine", QUARANTINE_B_TASK, QUARANTINE_DB, QUARANTINE_SHARED_OUTPUT)
    quarantine_status = run_json(["service-status", "--db", QUARANTINE_DB, "--limit", "2"], "operator-flow/service-status-quarantine", errors)
    flow_helpers.assert_quarantine_status(quarantine_status, errors, "operator-flow/service-status-quarantine", QUARANTINE_B_TASK, QUARANTINE_A_TASK, QUARANTINE_DB, f"scope:{QUARANTINE_SHARED_OUTPUT}")


def _run_reconcile_session_priority_flow(errors: list[str]) -> None:
    seed_crash_reconcile = run_json(["seed-crash", "--probe-mode", "none", "--task-id", RECONCILE_TASK, "--db", RECONCILE_DB, "--output", RECONCILE_OUTPUT], "operator-flow/seed-crash-reconcile", errors)
    flow_helpers.assert_seed_result(seed_crash_reconcile, errors, "operator-flow/seed-crash-reconcile", "seed-crash", RECONCILE_TASK, RECONCILE_DB, RECONCILE_OUTPUT)
    reconcile_status_before = run_json(["service-status", "--db", RECONCILE_DB, "--limit", "1"], "operator-flow/service-reconcile-status-before", errors)
    flow_helpers.assert_reconcile_status_before(reconcile_status_before, errors, "operator-flow/service-reconcile-status-before", RECONCILE_TASK, RECONCILE_DB, RECONCILE_OUTPUT)
    service_reconcile = run_json(["service-reconcile", "--db", RECONCILE_DB, "--task-id", RECONCILE_TASK, "--decision", "executed", "--limit", "1"], "operator-flow/service-reconcile", errors)
    assert_service_combo(service_reconcile, errors, "operator-flow/service-reconcile", combo_action="service-reconcile", primary_action="reconcile", task_id=RECONCILE_TASK, db=RECONCILE_DB, output=RECONCILE_OUTPUT, expected_output_source="session", expected_owner_source="session")
    seed_crash_session_priority_a = run_json(["seed-crash", "--task-id", SESSION_PRIORITY_A_TASK, "--db", SESSION_PRIORITY_DB, "--output", SESSION_PRIORITY_A_OUTPUT], "operator-flow/seed-crash-session-priority-a", errors)
    flow_helpers.assert_seed_result(seed_crash_session_priority_a, errors, "operator-flow/seed-crash-session-priority-a", "seed-crash", SESSION_PRIORITY_A_TASK, SESSION_PRIORITY_DB, SESSION_PRIORITY_A_OUTPUT)
    seed_failed_session_priority_b = run_json(["seed-failed", "--task-id", SESSION_PRIORITY_B_TASK, "--db", SESSION_PRIORITY_DB, "--output", SESSION_PRIORITY_B_OUTPUT], "operator-flow/seed-failed-session-priority-b", errors)
    flow_helpers.assert_seed_result(seed_failed_session_priority_b, errors, "operator-flow/seed-failed-session-priority-b", "seed-failed", SESSION_PRIORITY_B_TASK, SESSION_PRIORITY_DB, SESSION_PRIORITY_B_OUTPUT)
    with sqlite3.connect(REPO_ROOT / SESSION_PRIORITY_DB) as connection:
        connection.execute("UPDATE task_snapshots SET updated_at = ?1 WHERE task_id = ?2", (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 5)), SESSION_PRIORITY_B_TASK))
        connection.commit()
    use_session_priority_a = run_json(["use", "--db", SESSION_PRIORITY_DB, "--task-id", SESSION_PRIORITY_A_TASK], "operator-flow/use-session-priority-a", errors)
    flow_helpers.assert_use_result(use_session_priority_a, errors, "operator-flow/use-session-priority-a", SESSION_PRIORITY_A_TASK, SESSION_PRIORITY_DB, SESSION_PRIORITY_A_OUTPUT)
    session_priority_status = run_json(["service-status", "--db", SESSION_PRIORITY_DB, "--limit", "2"], "operator-flow/service-status-session-priority", errors)
    flow_helpers.assert_session_priority_status(session_priority_status, errors, "operator-flow/service-status-session-priority", SESSION_PRIORITY_A_TASK, SESSION_PRIORITY_B_TASK, SESSION_PRIORITY_DB, SESSION_PRIORITY_A_OUTPUT)


def _run_owner_alignment_closeout(errors: list[str]) -> None:
    seed_crash_owner_alignment_a = run_json(["seed-crash", "--task-id", OWNER_ALIGNMENT_A_TASK, "--db", OWNER_ALIGNMENT_DB, "--output", OWNER_ALIGNMENT_A_OUTPUT, "--owner-id", OWNER_ALIGNMENT_A_OWNER], "operator-flow/seed-crash-owner-alignment-a", errors)
    flow_helpers.assert_seed_result(seed_crash_owner_alignment_a, errors, "operator-flow/seed-crash-owner-alignment-a", "seed-crash", OWNER_ALIGNMENT_A_TASK, OWNER_ALIGNMENT_DB, OWNER_ALIGNMENT_A_OUTPUT, owner_id=OWNER_ALIGNMENT_A_OWNER)
    seed_failed_owner_alignment_b = run_json(["seed-failed", "--task-id", OWNER_ALIGNMENT_B_TASK, "--db", OWNER_ALIGNMENT_DB, "--output", OWNER_ALIGNMENT_B_OUTPUT, "--owner-id", OWNER_ALIGNMENT_B_OWNER], "operator-flow/seed-failed-owner-alignment-b", errors)
    flow_helpers.assert_seed_result(seed_failed_owner_alignment_b, errors, "operator-flow/seed-failed-owner-alignment-b", "seed-failed", OWNER_ALIGNMENT_B_TASK, OWNER_ALIGNMENT_DB, OWNER_ALIGNMENT_B_OUTPUT, owner_id=OWNER_ALIGNMENT_B_OWNER)
    use_owner_alignment_a = run_json(["use", "--db", OWNER_ALIGNMENT_DB, "--task-id", OWNER_ALIGNMENT_A_TASK], "operator-flow/use-owner-alignment-a", errors)
    flow_helpers.assert_use_result(use_owner_alignment_a, errors, "operator-flow/use-owner-alignment-a", OWNER_ALIGNMENT_A_TASK, OWNER_ALIGNMENT_DB, OWNER_ALIGNMENT_A_OUTPUT, owner_id=OWNER_ALIGNMENT_A_OWNER, owner_id_source="task_owner")
    owner_alignment_status = run_json(["service-status", "--db", OWNER_ALIGNMENT_DB, "--limit", "2"], "operator-flow/service-status-owner-alignment", errors)
    flow_helpers.assert_owner_alignment_status(owner_alignment_status, errors, "operator-flow/service-status-owner-alignment", OWNER_ALIGNMENT_A_TASK, OWNER_ALIGNMENT_DB, OWNER_ALIGNMENT_A_OUTPUT, OWNER_ALIGNMENT_A_OWNER)
    forget_after = run_json(["forget"], "operator-flow/forget-after", errors)
    flow_helpers.assert_forget_after_result(forget_after, errors, "operator-flow/forget-after")
    workspace_clear_after = run_json(["workspace", "--clear"], "operator-flow/workspace-clear-after", errors)
    flow_helpers.assert_workspace_clear_result(workspace_clear_after, errors, "operator-flow/workspace-clear-after")


def _main() -> int:
    errors: list[str] = []

    reset_operator_flow_progress()
    sequence, started_at = start_operator_flow_step("operator-flow/reset-state", "reset-state")
    try:
        reset_operator_flow_state()
    finally:
        finish_operator_flow_step(sequence, started_at, exit_code=0, status="ok")



    _run_operator_flow_prelude(errors)
    _run_retry_and_recover_flow(errors)
    _run_hibernated_and_stalled_flow(errors)
    _run_contended_flow(errors)
    _run_quarantine_flow(errors)
    _run_reconcile_session_priority_flow(errors)
    _run_owner_alignment_closeout(errors)

    if errors:
        print("MVP operator flow check failed.", flush=True)
        for item in errors:
            print(f"- {item}", flush=True)
        return 1

    print("MVP operator flow check passed.", flush=True)
    return 0


def main() -> int:
    try:
        with acquire_mvp_state_lock("check_mvp_operator_flow"):
            return _main()
    except RuntimeError as error:
        print(f"MVP operator flow check failed: {error}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
