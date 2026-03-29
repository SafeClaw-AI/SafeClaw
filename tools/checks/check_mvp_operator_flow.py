from __future__ import annotations

import json
import sqlite3
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from mvp_state_guard import acquire_mvp_state_lock

REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPER = ["cmd", "/c", r"tools\mvp\safeclaw_mvp.cmd"]
SCHEMA_VERSION = "mvp-wrapper.v1"
OWNER_ID = "safeclaw-mvp"

RUN_TASK = "task-operator-flow-run"
RUN_DB = "target/mvp/operator-flow-run.db"
RUN_OUTPUT = "target/mvp/operator-flow-run.txt"
RETRY_TASK = "task-operator-flow-retry"
RETRY_DB = "target/mvp/operator-flow-retry.db"
RETRY_OUTPUT = "target/mvp/operator-flow-retry.txt"
RECOVER_TASK = "task-operator-flow-recover"
RECOVER_DB = "target/mvp/operator-flow-recover.db"
RECOVER_OUTPUT = "target/mvp/operator-flow-recover.txt"
RECONCILE_TASK = "task-operator-flow-reconcile"
RECONCILE_DB = "target/mvp/operator-flow-reconcile.db"
RECONCILE_OUTPUT = "target/mvp/operator-flow-reconcile.txt"
STALLED_TASK = "task-operator-flow-stalled"
STALLED_DB = "target/mvp/operator-flow-stalled.db"
STALLED_OUTPUT = "target/mvp/operator-flow-stalled.txt"
CONTENDED_A_TASK = "task-operator-flow-contended-a"
CONTENDED_B_TASK = "task-operator-flow-contended-b"
CONTENDED_DB = "target/mvp/operator-flow-contended.db"
CONTENDED_A_OUTPUT = "target/mvp/operator-flow-contended-a.txt"
CONTENDED_B_OUTPUT = "target/mvp/operator-flow-contended-b.txt"
CONTENDED_SHARED_OUTPUT = "target/mvp/operator-flow-contended-shared.txt"
QUARANTINE_A_TASK = "task-operator-flow-quarantine-a"
QUARANTINE_B_TASK = "task-operator-flow-quarantine-b"
QUARANTINE_DB = "target/mvp/operator-flow-quarantine.db"
QUARANTINE_A_OUTPUT = "target/mvp/operator-flow-quarantine-a.txt"
QUARANTINE_B_OUTPUT = "target/mvp/operator-flow-quarantine-b.txt"
QUARANTINE_SHARED_OUTPUT = "target/mvp/operator-flow-quarantine-shared.txt"
HIBERNATED_TASK = "task-operator-flow-hibernated"
HIBERNATED_DB = "target/mvp/operator-flow-hibernated.db"
HIBERNATED_OUTPUT = "target/mvp/operator-flow-hibernated.txt"
SESSION_PRIORITY_A_TASK = "task-operator-flow-session-priority-a"
SESSION_PRIORITY_B_TASK = "task-operator-flow-session-priority-b"
SESSION_PRIORITY_DB = "target/mvp/operator-flow-session-priority.db"
SESSION_PRIORITY_A_OUTPUT = "target/mvp/operator-flow-session-priority-a.txt"
SESSION_PRIORITY_B_OUTPUT = "target/mvp/operator-flow-session-priority-b.txt"


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
    ]:
        path = state_root / relative_path
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)


def append_error(errors: list[str], label: str, message: str) -> None:
    errors.append(f"{label}: {message}")



def expect_equal(errors: list[str], label: str, field: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        append_error(errors, label, f"{field} expected {expected!r}, got {actual!r}")



def expect_true(errors: list[str], label: str, field: str, value: Any) -> None:
    if value is not True:
        append_error(errors, label, f"{field} expected True, got {value!r}")





def load_json(args: list[str]) -> tuple[int, str, dict[str, Any] | None]:
    completed = subprocess.run(
        [*WRAPPER, *args, "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    output = ((completed.stdout or "") + (completed.stderr or "")).strip()
    if completed.returncode != 0:
        return completed.returncode, output, None
    try:
        payload = json.loads(output)
    except json.JSONDecodeError as error:
        detail = f"invalid json: {error}"
        return completed.returncode, f"{output}\n{detail}".strip(), None
    if not isinstance(payload, dict):
        return completed.returncode, output, None
    return completed.returncode, output, payload


def wait_for_session(task_id: str, db: str, output: str, errors: list[str], label: str) -> None:
    last_observed: dict[str, Any] | None = None
    for _ in range(12):
        exit_code, raw_output, payload = load_json(["session"])
        if exit_code == 0 and payload is not None and payload.get("ok") is True and payload.get("action") == "session":
            result = payload.get("result")
            if isinstance(result, dict):
                last_observed = result
                if result.get("task_id") == task_id and result.get("db") == db and result.get("output") == output:
                    return
        time.sleep(0.1)
    append_error(errors, label, f"session did not converge to {task_id!r}; last={last_observed!r}")

def run_json(args: list[str], label: str, errors: list[str]) -> dict[str, Any] | None:
    completed = subprocess.run(
        [*WRAPPER, *args, "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    output = ((completed.stdout or "") + (completed.stderr or "")).strip()
    if completed.returncode != 0:
        append_error(errors, label, f"exit={completed.returncode} output={output!r}")
        return None

    try:
        payload = json.loads(output)
    except json.JSONDecodeError as exc:
        append_error(errors, label, f"invalid json: {exc} output={output!r}")
        return None

    expect_true(errors, label, "ok", payload.get("ok"))
    expect_equal(errors, label, "schema_version", payload.get("schema_version"), SCHEMA_VERSION)
    return payload



def assert_session_fields(
    payload: dict[str, Any] | None,
    errors: list[str],
    label: str,
    field: str,
    task_id: str,
    db: str,
    output: str,
) -> None:
    if payload is None:
        append_error(errors, label, f"{field} missing")
        return
    expect_equal(errors, label, f"{field}.task_id", payload.get("task_id"), task_id)
    expect_equal(errors, label, f"{field}.effect_id", payload.get("effect_id"), f"effect-{task_id}")
    expect_equal(errors, label, f"{field}.db", payload.get("db"), db)
    expect_equal(errors, label, f"{field}.output", payload.get("output"), output)
    expect_equal(errors, label, f"{field}.owner_id", payload.get("owner_id"), OWNER_ID)



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
    steps = result.get("steps") or []
    expected_steps = expected_steps or [primary_action, "service-status"]
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

    assert_session_fields(result.get("remembered_session"), errors, label, "remembered_session", task_id, db, output)
    assert_session_fields(result.get("session"), errors, label, "session", task_id, db, output)

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

    if expect_report_payload:
        report = result.get("report") or {}
        expect_equal(errors, label, "report.prepared[0]", (report.get("prepared") or [None])[0], "report")
        expect_equal(errors, label, "report.saved_session", report.get("saved_session"), None)
        assert_session_fields(report.get("remembered_session"), errors, label, "report.remembered_session", task_id, db, output)

    status = result.get("service_status") or {}
    expect_equal(errors, label, "service_status.db", status.get("db"), db)
    expect_equal(errors, label, "service_status.db_source", status.get("db_source"), "flag")
    expect_equal(errors, label, "service_status.limit", status.get("limit"), 1)
    expect_equal(errors, label, "service_status.queue.completed", ((status.get("queue") or {}).get("completed")), 1)
    expect_equal(errors, label, "service_status.workers.succeeded", ((status.get("workers") or {}).get("succeeded")), 1)
    expect_equal(errors, label, "service_status.effects.executed", ((status.get("effects") or {}).get("executed")), 1)
    expect_equal(errors, label, "service_status.heartbeat.interval_ms", ((status.get("heartbeat") or {}).get("interval_ms")), 10000)
    expect_equal(errors, label, "service_status.heartbeat.event_driven", ((status.get("heartbeat") or {}).get("event_driven")), True)
    expect_equal(errors, label, "service_status.heartbeat.latest_freshness", ((status.get("heartbeat") or {}).get("latest_freshness")), "none")
    expect_equal(errors, label, "service_status.heartbeat.status", ((status.get("heartbeat") or {}).get("status")), "idle")
    expect_equal(errors, label, "service_status.heartbeat.reason", ((status.get("heartbeat") or {}).get("reason")), "no_active_lease_heartbeat")
    expect_equal(errors, label, "service_status.runtime_profile.mode", ((status.get("runtime_profile") or {}).get("mode")), "local_mvp")
    expect_equal(errors, label, "service_status.runtime_profile.offline_ready", ((status.get("runtime_profile") or {}).get("offline_ready")), True)
    expect_equal(errors, label, "service_status.runtime_profile.llm_required", ((status.get("runtime_profile") or {}).get("llm_required")), False)
    expect_equal(errors, label, "service_status.runtime_profile.sidecar_required", ((status.get("runtime_profile") or {}).get("sidecar_required")), False)
    expect_equal(errors, label, "service_status.model_provider.status", ((status.get("model_provider") or {}).get("status")), "not-configured")
    expect_equal(errors, label, "service_status.model_provider.required", ((status.get("model_provider") or {}).get("required")), False)
    expect_equal(errors, label, "service_status.model_provider.configured", ((status.get("model_provider") or {}).get("configured")), False)
    expect_equal(errors, label, "service_status.model_provider.degradation_mode", ((status.get("model_provider") or {}).get("degradation_mode")), "local_only_ok")
    expect_equal(errors, label, "service_status.sidecar.status", ((status.get("sidecar") or {}).get("status")), "not-configured")
    expect_equal(errors, label, "service_status.sidecar.required", ((status.get("sidecar") or {}).get("required")), False)
    expect_equal(errors, label, "service_status.sidecar.configured", ((status.get("sidecar") or {}).get("configured")), False)
    expect_equal(errors, label, "service_status.offline_gate.status", ((status.get("offline_gate") or {}).get("status")), "blocked")
    expect_equal(errors, label, "service_status.offline_gate.reason", ((status.get("offline_gate") or {}).get("reason")), "ERR_AI_PROVIDER_UNAVAILABLE")
    expect_equal(errors, label, "service_status.offline_gate.summary", ((status.get("offline_gate") or {}).get("summary")), "ai_actions_require_provider")
    expect_equal(errors, label, "service_status.offline_gate.requested_action", ((status.get("offline_gate") or {}).get("requested_action")), "ai-reason")
    expect_equal(errors, label, "service_status.offline_gate.requires_model", ((status.get("offline_gate") or {}).get("requires_model")), True)
    expect_equal(errors, label, "service_status.offline_gate.requires_sidecar", ((status.get("offline_gate") or {}).get("requires_sidecar")), True)
    expect_equal(errors, label, "service_status.offline_gate.next_command", ((status.get("offline_gate") or {}).get("next_command")), "safeclaw.cmd preflight --action ai-reason")
    expect_equal(errors, label, "service_status.offline_gate.error_code", ((status.get("offline_gate") or {}).get("error_code")), "ERR_AI_PROVIDER_UNAVAILABLE")
    expect_equal(errors, label, "service_status.heartbeat.latest_updated_at", ((status.get("heartbeat") or {}).get("latest_updated_at")), None)
    expect_equal(errors, label, "service_status.heartbeat.latest_age_ms", ((status.get("heartbeat") or {}).get("latest_age_ms")), None)
    if not (status.get("runtime_profile") or {}).get("detail"):
        append_error(errors, label, "service_status.runtime_profile.detail missing")
    if not (status.get("model_provider") or {}).get("detail"):
        append_error(errors, label, "service_status.model_provider.detail missing")
    if not (status.get("sidecar") or {}).get("detail"):
        append_error(errors, label, "service_status.sidecar.detail missing")
    coordination = status.get("coordination") or {}
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
    recent_tasks = status.get("recent_tasks") or []
    if not recent_tasks:
        append_error(errors, label, "service_status.recent_tasks missing")
    else:
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



def _main() -> int:
    errors: list[str] = []

    reset_operator_flow_state()



    workspace_clear_before = run_json(["workspace", "--clear"], "operator-flow/workspace-clear-before", errors)
    if workspace_clear_before is not None:
        expect_equal(errors, "operator-flow/workspace-clear-before", "action", workspace_clear_before.get("action"), "workspace")
        clear_result = workspace_clear_before.get("result") or {}
        clear_state = (clear_result.get("cleared"), clear_result.get("reason"))
        if clear_result.get("path") != "target\mvp\workspace.json":
            append_error(errors, "operator-flow/workspace-clear-before", "missing workspace path")
        elif clear_state not in {(True, "removed"), (False, "none")}:
            append_error(errors, "operator-flow/workspace-clear-before", f"unexpected clear state {clear_state!r}")

    forget_before = run_json(["forget"], "operator-flow/forget-before", errors)
    if forget_before is not None:
        expect_equal(errors, "operator-flow/forget-before", "action", forget_before.get("action"), "forget")
        forget_result = forget_before.get("result") or {}
        forget_reason = forget_result.get("reason")
        forgot = forget_result.get("forgot")
        if (forgot, forget_reason) not in {(True, "removed"), (True, "already-absent"), (False, "none")}:
            append_error(errors, "operator-flow/forget-before", f"unexpected forget state forgot={forgot!r} reason={forget_reason!r}")

    doctor = run_json(["doctor"], "operator-flow/doctor", errors)
    if doctor is not None:
        expect_equal(errors, "operator-flow/doctor", "action", doctor.get("action"), "doctor")
        doctor_result = doctor.get("result") or {}
        expect_equal(errors, "operator-flow/doctor", "result.status", doctor_result.get("status"), "ready")
        expect_equal(errors, "operator-flow/doctor", "result.session", doctor_result.get("session"), None)
        expect_equal(errors, "operator-flow/doctor", "result.db.source", ((doctor_result.get("db") or {}).get("source")), "default")
        expect_equal(errors, "operator-flow/doctor", "result.output.source", ((doctor_result.get("output") or {}).get("source")), "default")
        expect_true(errors, "operator-flow/doctor", "entrypoints.cmd.exists", (((doctor_result.get("entrypoints") or {}).get("cmd") or {}).get("exists")))
        expect_true(errors, "operator-flow/doctor", "entrypoints.ps1.exists", (((doctor_result.get("entrypoints") or {}).get("ps1") or {}).get("exists")))
        expect_true(errors, "operator-flow/doctor", "entrypoints.py.exists", (((doctor_result.get("entrypoints") or {}).get("py") or {}).get("exists")))

    service_run = run_json(
        [
            "service-run",
            "--reset",
            "--task-id",
            RUN_TASK,
            "--db",
            RUN_DB,
            "--output",
            RUN_OUTPUT,
            "--limit",
            "1",
        ],
        "operator-flow/service-run",
        errors,
    )
    assert_service_combo(
        service_run,
        errors,
        "operator-flow/service-run",
        combo_action="service-run",
        primary_action="run",
        task_id=RUN_TASK,
        db=RUN_DB,
        output=RUN_OUTPUT,
        expected_output_source="flag",
        expected_owner_source="default",
    )
    wait_for_session(RUN_TASK, RUN_DB, RUN_OUTPUT, errors, "operator-flow/service-run")

    report = run_json(["report"], "operator-flow/report", errors)
    if report is not None:
        expect_equal(errors, "operator-flow/report", "action", report.get("action"), "report")
        report_result = report.get("result") or {}
        assert_session_fields(report_result.get("remembered_session"), errors, "operator-flow/report", "remembered_session", RUN_TASK, RUN_DB, RUN_OUTPUT)
        expect_equal(errors, "operator-flow/report", "source_hints.db", ((report_result.get("source_hints") or {}).get("db")), "session")
        expect_equal(errors, "operator-flow/report", "source_hints.output", ((report_result.get("source_hints") or {}).get("output")), "session")
        expect_equal(errors, "operator-flow/report", "source_hints.owner_id", ((report_result.get("source_hints") or {}).get("owner_id")), "session")
        expect_equal(errors, "operator-flow/report", "source_hints.task_context", ((report_result.get("source_hints") or {}).get("task_context")), "session")

    seed_failed = run_json(
        [
            "seed-failed",
            "--reset",
            "--task-id",
            RETRY_TASK,
            "--db",
            RETRY_DB,
            "--output",
            RETRY_OUTPUT,
        ],
        "operator-flow/seed-failed",
        errors,
    )
    if seed_failed is not None:
        expect_equal(errors, "operator-flow/seed-failed", "action", seed_failed.get("action"), "seed-failed")
        assert_session_fields((seed_failed.get("result") or {}).get("remembered_session"), errors, "operator-flow/seed-failed", "remembered_session", RETRY_TASK, RETRY_DB, RETRY_OUTPUT)
    wait_for_session(RETRY_TASK, RETRY_DB, RETRY_OUTPUT, errors, "operator-flow/seed-failed")

    service_retry = run_json(
        [
            "service-retry",
            "--db",
            RETRY_DB,
            "--task-id",
            RETRY_TASK,
            "--limit",
            "1",
        ],
        "operator-flow/service-retry",
        errors,
    )
    assert_service_combo(
        service_retry,
        errors,
        "operator-flow/service-retry",
        combo_action="service-retry",
        primary_action="retry",
        task_id=RETRY_TASK,
        db=RETRY_DB,
        output=RETRY_OUTPUT,
        expected_output_source="session",
        expected_owner_source="session",
    )

    seed_crash = run_json(
        [
            "seed-crash",
            "--reset",
            "--task-id",
            RECOVER_TASK,
            "--db",
            RECOVER_DB,
            "--output",
            RECOVER_OUTPUT,
        ],
        "operator-flow/seed-crash",
        errors,
    )
    if seed_crash is not None:
        expect_equal(errors, "operator-flow/seed-crash", "action", seed_crash.get("action"), "seed-crash")
        assert_session_fields((seed_crash.get("result") or {}).get("remembered_session"), errors, "operator-flow/seed-crash", "remembered_session", RECOVER_TASK, RECOVER_DB, RECOVER_OUTPUT)
    wait_for_session(RECOVER_TASK, RECOVER_DB, RECOVER_OUTPUT, errors, "operator-flow/seed-crash")

    service_recover = run_json(
        [
            "service-recover",
            "--db",
            RECOVER_DB,
            "--task-id",
            RECOVER_TASK,
            "--limit",
            "1",
        ],
        "operator-flow/service-recover",
        errors,
    )
    assert_service_combo(
        service_recover,
        errors,
        "operator-flow/service-recover",
        combo_action="service-recover",
        primary_action="recover",
        task_id=RECOVER_TASK,
        db=RECOVER_DB,
        output=RECOVER_OUTPUT,
        expected_output_source="session",
        expected_owner_source="session",
    )

    seed_hibernated = run_json(
        [
            "seed-hibernated",
            "--reset",
            "--task-id",
            HIBERNATED_TASK,
            "--db",
            HIBERNATED_DB,
            "--output",
            HIBERNATED_OUTPUT,
        ],
        "operator-flow/seed-hibernated",
        errors,
    )
    if seed_hibernated is not None:
        expect_equal(errors, "operator-flow/seed-hibernated", "action", seed_hibernated.get("action"), "seed-hibernated")
        assert_session_fields((seed_hibernated.get("result") or {}).get("remembered_session"), errors, "operator-flow/seed-hibernated", "remembered_session", HIBERNATED_TASK, HIBERNATED_DB, HIBERNATED_OUTPUT)
    wait_for_session(HIBERNATED_TASK, HIBERNATED_DB, HIBERNATED_OUTPUT, errors, "operator-flow/seed-hibernated")

    hibernated_status = run_json(
        [
            "service-status",
            "--db",
            HIBERNATED_DB,
            "--limit",
            "1",
        ],
        "operator-flow/service-status-hibernated",
        errors,
    )
    if hibernated_status is not None:
        result = hibernated_status.get("result") or {}
        coordination = result.get("coordination") or {}
        recent_tasks = result.get("recent_tasks") or []
        current_session = result.get("current_session") or {}
        expect_equal(errors, "operator-flow/service-status-hibernated", "result.db", result.get("db"), HIBERNATED_DB)
        expect_equal(errors, "operator-flow/service-status-hibernated", "result.db_source", result.get("db_source"), "flag")
        expect_equal(errors, "operator-flow/service-status-hibernated", "result.limit", result.get("limit"), 1)
        expect_equal(errors, "operator-flow/service-status-hibernated", "current_session.task_id", current_session.get("task_id"), HIBERNATED_TASK)
        expect_equal(errors, "operator-flow/service-status-hibernated", "workers.hibernated", ((result.get("workers") or {}).get("hibernated")), 1)
        expect_equal(errors, "operator-flow/service-status-hibernated", "coordination.status", coordination.get("status"), "hibernated")
        expect_equal(errors, "operator-flow/service-status-hibernated", "coordination.reason", coordination.get("reason"), "hibernated_waiting_for_resume")
        expect_equal(errors, "operator-flow/service-status-hibernated", "coordination.summary", coordination.get("summary"), "inspect_and_resume_or_expire")
        expect_equal(errors, "operator-flow/service-status-hibernated", "coordination.task_id", coordination.get("task_id"), HIBERNATED_TASK)
        expect_equal(errors, "operator-flow/service-status-hibernated", "coordination.target_scope", coordination.get("target_scope"), f"scope:{HIBERNATED_OUTPUT}")
        expect_equal(errors, "operator-flow/service-status-hibernated", "coordination.next_action", coordination.get("next_action"), "inspect")
        expect_equal(errors, "operator-flow/service-status-hibernated", "coordination.next_task_id", coordination.get("next_task_id"), HIBERNATED_TASK)
        expect_equal(errors, "operator-flow/service-status-hibernated", "coordination.next_blocker", coordination.get("next_blocker"), "manual_review_needed")
        expect_equal(errors, "operator-flow/service-status-hibernated", "coordination.scope_peer_count", coordination.get("scope_peer_count"), 0)
        expect_equal(errors, "operator-flow/service-status-hibernated", "coordination.scope_active_peer_count", coordination.get("scope_active_peer_count"), 0)
        expect_equal(errors, "operator-flow/service-status-hibernated", "coordination.scope_active_peer_task_id", coordination.get("scope_active_peer_task_id"), "")
        expect_equal(errors, "operator-flow/service-status-hibernated", "coordination.scope_quarantine_active", coordination.get("scope_quarantine_active"), False)
        expect_equal(errors, "operator-flow/service-status-hibernated", "coordination.scope_quarantine_source", coordination.get("scope_quarantine_source"), "none")
        expect_equal(errors, "operator-flow/service-status-hibernated", "coordination.scope_quarantine_task_id", coordination.get("scope_quarantine_task_id"), "")
        expect_equal(errors, "operator-flow/service-status-hibernated", "coordination.scope_quarantine_count", coordination.get("scope_quarantine_count"), 0)
        if not recent_tasks:
            append_error(errors, "operator-flow/service-status-hibernated", "recent task missing")
        else:
            task = recent_tasks[0]
            expect_equal(errors, "operator-flow/service-status-hibernated", "recent.task_id", task.get("task_id"), HIBERNATED_TASK)
            expect_true(errors, "operator-flow/service-status-hibernated", "recent.current", task.get("current"))
            expect_equal(errors, "operator-flow/service-status-hibernated", "recent.worker_state", task.get("worker_state"), "hibernated")
            expect_equal(errors, "operator-flow/service-status-hibernated", "recent.lease_state", task.get("lease_state"), "expired")
            expect_equal(errors, "operator-flow/service-status-hibernated", "recent.next_action", task.get("next_action"), "inspect")
            expect_equal(errors, "operator-flow/service-status-hibernated", "recent.next_reason", task.get("next_reason"), "hibernated_waiting_for_resume")
            expect_equal(errors, "operator-flow/service-status-hibernated", "recent.next_blocker", task.get("next_blocker"), "manual_review_needed")
            expect_equal(errors, "operator-flow/service-status-hibernated", "recent.next_summary", task.get("next_summary"), "blocked:action=inspect,blocker=manual_review_needed,reason=hibernated_waiting_for_resume")
            expect_equal(errors, "operator-flow/service-status-hibernated", "recent.next_task_id", task.get("next_task_id"), HIBERNATED_TASK)
            expect_equal(errors, "operator-flow/service-status-hibernated", "recent.next_command", task.get("next_command"), f'safeclaw.cmd service-resume --db "{HIBERNATED_DB}" --task-id "{HIBERNATED_TASK}" --limit 1 --report')
            expect_equal(errors, "operator-flow/service-status-hibernated", "recent.coordination_status", task.get("coordination_status"), "hibernated")
            expect_equal(errors, "operator-flow/service-status-hibernated", "recent.coordination_reason", task.get("coordination_reason"), "hibernated_waiting_for_resume")
            expect_equal(errors, "operator-flow/service-status-hibernated", "recent.coordination_summary", task.get("coordination_summary"), "inspect_and_resume_or_expire")
            expect_equal(errors, "operator-flow/service-status-hibernated", "recent.scope_peer_count", task.get("scope_peer_count"), 0)
            expect_equal(errors, "operator-flow/service-status-hibernated", "recent.scope_active_peer_count", task.get("scope_active_peer_count"), 0)
            expect_equal(errors, "operator-flow/service-status-hibernated", "recent.scope_active_peer_task_id", task.get("scope_active_peer_task_id"), "")
            expect_equal(errors, "operator-flow/service-status-hibernated", "recent.scope_quarantine_active", task.get("scope_quarantine_active"), False)
            expect_equal(errors, "operator-flow/service-status-hibernated", "recent.scope_quarantine_source", task.get("scope_quarantine_source"), "none")
            expect_equal(errors, "operator-flow/service-status-hibernated", "recent.scope_quarantine_task_id", task.get("scope_quarantine_task_id"), "")
            expect_equal(errors, "operator-flow/service-status-hibernated", "recent.scope_quarantine_count", task.get("scope_quarantine_count"), 0)

    service_resume = run_json(
        [
            "service-resume",
            "--db",
            HIBERNATED_DB,
            "--task-id",
            HIBERNATED_TASK,
            "--limit",
            "1",
            "--report",
        ],
        "operator-flow/service-resume",
        errors,
    )
    assert_service_combo(
        service_resume,
        errors,
        "operator-flow/service-resume",
        combo_action="service-resume",
        primary_action="resume",
        task_id=HIBERNATED_TASK,
        db=HIBERNATED_DB,
        output=HIBERNATED_OUTPUT,
        expected_output_source="session",
        expected_owner_source="session",
        expected_steps=["resume", "service-status", "report"],
        expect_report_payload=True,
    )

    seed_failed_stalled = run_json(
        [
            "seed-failed",
            "--reset",
            "--task-id",
            STALLED_TASK,
            "--db",
            STALLED_DB,
            "--output",
            STALLED_OUTPUT,
        ],
        "operator-flow/seed-failed-stalled",
        errors,
    )
    if seed_failed_stalled is not None:
        expect_equal(errors, "operator-flow/seed-failed-stalled", "action", seed_failed_stalled.get("action"), "seed-failed")
        assert_session_fields((seed_failed_stalled.get("result") or {}).get("remembered_session"), errors, "operator-flow/seed-failed-stalled", "remembered_session", STALLED_TASK, STALLED_DB, STALLED_OUTPUT)
    wait_for_session(STALLED_TASK, STALLED_DB, STALLED_OUTPUT, errors, "operator-flow/seed-failed-stalled")

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

    stalled_status = run_json(
        [
            "service-status",
            "--db",
            STALLED_DB,
            "--limit",
            "1",
        ],
        "operator-flow/service-status-stalled",
        errors,
    )
    if stalled_status is not None:
        result = stalled_status.get("result") or {}
        coordination = result.get("coordination") or {}
        recent_tasks = result.get("recent_tasks") or []
        current_session = result.get("current_session") or {}
        expect_equal(errors, "operator-flow/service-status-stalled", "result.db", result.get("db"), STALLED_DB)
        expect_equal(errors, "operator-flow/service-status-stalled", "result.db_source", result.get("db_source"), "flag")
        expect_equal(errors, "operator-flow/service-status-stalled", "result.limit", result.get("limit"), 1)
        expect_equal(errors, "operator-flow/service-status-stalled", "current_session.task_id", current_session.get("task_id"), STALLED_TASK)
        expect_equal(errors, "operator-flow/service-status-stalled", "coordination.status", coordination.get("status"), "stalled")
        expect_equal(errors, "operator-flow/service-status-stalled", "coordination.reason", coordination.get("reason"), "active_lease_without_recent_heartbeat")
        expect_equal(errors, "operator-flow/service-status-stalled", "coordination.summary", coordination.get("summary"), "inspect_owner_or_wait_for_lease_expiry")
        expect_equal(errors, "operator-flow/service-status-stalled", "coordination.task_id", coordination.get("task_id"), STALLED_TASK)
        expect_equal(errors, "operator-flow/service-status-stalled", "coordination.target_scope", coordination.get("target_scope"), f"scope:{STALLED_OUTPUT}")
        expect_equal(errors, "operator-flow/service-status-stalled", "coordination.next_action", coordination.get("next_action"), "inspect")
        expect_equal(errors, "operator-flow/service-status-stalled", "coordination.next_task_id", coordination.get("next_task_id"), STALLED_TASK)
        expect_equal(errors, "operator-flow/service-status-stalled", "coordination.next_blocker", coordination.get("next_blocker"), "active_lease")
        expect_equal(errors, "operator-flow/service-status-stalled", "coordination.scope_peer_count", coordination.get("scope_peer_count"), 0)
        expect_equal(errors, "operator-flow/service-status-stalled", "coordination.scope_active_peer_count", coordination.get("scope_active_peer_count"), 0)
        expect_equal(errors, "operator-flow/service-status-stalled", "coordination.scope_active_peer_task_id", coordination.get("scope_active_peer_task_id"), "")
        expect_equal(errors, "operator-flow/service-status-stalled", "coordination.scope_quarantine_active", coordination.get("scope_quarantine_active"), False)
        expect_equal(errors, "operator-flow/service-status-stalled", "coordination.scope_quarantine_source", coordination.get("scope_quarantine_source"), "none")
        expect_equal(errors, "operator-flow/service-status-stalled", "coordination.scope_quarantine_task_id", coordination.get("scope_quarantine_task_id"), "")
        expect_equal(errors, "operator-flow/service-status-stalled", "coordination.scope_quarantine_count", coordination.get("scope_quarantine_count"), 0)
        if not recent_tasks:
            append_error(errors, "operator-flow/service-status-stalled", "recent task missing")
        else:
            task = recent_tasks[0]
            expect_equal(errors, "operator-flow/service-status-stalled", "recent.task_id", task.get("task_id"), STALLED_TASK)
            expect_true(errors, "operator-flow/service-status-stalled", "recent.current", task.get("current"))
            expect_equal(errors, "operator-flow/service-status-stalled", "recent.effect_status", task.get("effect_status"), "prepared")
            expect_equal(errors, "operator-flow/service-status-stalled", "recent.lease_state", task.get("lease_state"), "active")
            expect_equal(errors, "operator-flow/service-status-stalled", "recent.lease_owner_id", task.get("lease_owner_id"), OWNER_ID)
            expect_equal(errors, "operator-flow/service-status-stalled", "recent.lease_fencing_token", task.get("lease_fencing_token"), 1)
            expect_equal(errors, "operator-flow/service-status-stalled", "recent.lease_freshness", task.get("lease_freshness"), "lost")
            expect_equal(errors, "operator-flow/service-status-stalled", "recent.next_action", task.get("next_action"), "inspect")
            expect_equal(errors, "operator-flow/service-status-stalled", "recent.next_reason", task.get("next_reason"), "lease_still_active")
            expect_equal(errors, "operator-flow/service-status-stalled", "recent.next_blocker", task.get("next_blocker"), "active_lease")
            expect_equal(errors, "operator-flow/service-status-stalled", "recent.next_task_id", task.get("next_task_id"), STALLED_TASK)
            expect_equal(errors, "operator-flow/service-status-stalled", "recent.next_command", task.get("next_command"), f'safeclaw.cmd report --db "{STALLED_DB}" --task-id "{STALLED_TASK}"')
            expect_equal(errors, "operator-flow/service-status-stalled", "recent.coordination_status", task.get("coordination_status"), "stalled")
            expect_equal(errors, "operator-flow/service-status-stalled", "recent.coordination_reason", task.get("coordination_reason"), "active_lease_without_recent_heartbeat")
            expect_equal(errors, "operator-flow/service-status-stalled", "recent.coordination_summary", task.get("coordination_summary"), "inspect_owner_or_wait_for_lease_expiry")
            expect_equal(errors, "operator-flow/service-status-stalled", "recent.scope_peer_count", task.get("scope_peer_count"), 0)
            expect_equal(errors, "operator-flow/service-status-stalled", "recent.scope_active_peer_count", task.get("scope_active_peer_count"), 0)
            expect_equal(errors, "operator-flow/service-status-stalled", "recent.scope_active_peer_task_id", task.get("scope_active_peer_task_id"), "")
            expect_equal(errors, "operator-flow/service-status-stalled", "recent.scope_quarantine_active", task.get("scope_quarantine_active"), False)
            expect_equal(errors, "operator-flow/service-status-stalled", "recent.scope_quarantine_source", task.get("scope_quarantine_source"), "none")
            expect_equal(errors, "operator-flow/service-status-stalled", "recent.scope_quarantine_task_id", task.get("scope_quarantine_task_id"), "")
            expect_equal(errors, "operator-flow/service-status-stalled", "recent.scope_quarantine_count", task.get("scope_quarantine_count"), 0)
            lease_remaining_ms = task.get("lease_remaining_ms")
            if not isinstance(lease_remaining_ms, int) or lease_remaining_ms <= 0:
                append_error(errors, "operator-flow/service-status-stalled", f"recent.lease_remaining_ms expected positive int, got {lease_remaining_ms!r}")
            next_summary = task.get("next_summary")
            if not isinstance(next_summary, str) or not next_summary.startswith("wait:remaining_ms="):
                append_error(errors, "operator-flow/service-status-stalled", f"recent.next_summary missing wait prefix: {next_summary!r}")
            elif ",blocker=active_lease,reason=lease_still_active" not in next_summary:
                append_error(errors, "operator-flow/service-status-stalled", f"recent.next_summary missing active-lease payload: {next_summary!r}")

    seed_failed_contended_a = run_json(
        [
            "seed-failed",
            "--reset",
            "--task-id",
            CONTENDED_A_TASK,
            "--db",
            CONTENDED_DB,
            "--output",
            CONTENDED_A_OUTPUT,
        ],
        "operator-flow/seed-failed-contended-a",
        errors,
    )
    if seed_failed_contended_a is not None:
        expect_equal(errors, "operator-flow/seed-failed-contended-a", "action", seed_failed_contended_a.get("action"), "seed-failed")
        assert_session_fields((seed_failed_contended_a.get("result") or {}).get("remembered_session"), errors, "operator-flow/seed-failed-contended-a", "remembered_session", CONTENDED_A_TASK, CONTENDED_DB, CONTENDED_A_OUTPUT)
    wait_for_session(CONTENDED_A_TASK, CONTENDED_DB, CONTENDED_A_OUTPUT, errors, "operator-flow/seed-failed-contended-a")

    seed_failed_contended_b = run_json(
        [
            "seed-failed",
            "--task-id",
            CONTENDED_B_TASK,
            "--db",
            CONTENDED_DB,
            "--output",
            CONTENDED_B_OUTPUT,
        ],
        "operator-flow/seed-failed-contended-b",
        errors,
    )
    if seed_failed_contended_b is not None:
        expect_equal(errors, "operator-flow/seed-failed-contended-b", "action", seed_failed_contended_b.get("action"), "seed-failed")
        assert_session_fields((seed_failed_contended_b.get("result") or {}).get("remembered_session"), errors, "operator-flow/seed-failed-contended-b", "remembered_session", CONTENDED_B_TASK, CONTENDED_DB, CONTENDED_B_OUTPUT)

    contended_scope = f"scope:{CONTENDED_SHARED_OUTPUT}"
    with sqlite3.connect(REPO_ROOT / CONTENDED_DB) as connection:
        connection.execute(
            "UPDATE orchestrator_tasks SET target_scope = ?1 WHERE task_id IN (?2, ?3)",
            (contended_scope, CONTENDED_A_TASK, CONTENDED_B_TASK),
        )
        connection.execute(
            """
            UPDATE orchestrator_leases
            SET expires_at_ms = ?1,
                released_at_ms = NULL
            WHERE task_id = ?2
            """,
            (int(time.time() * 1000) - 1_000, CONTENDED_A_TASK),
        )
        connection.execute(
            """
            UPDATE orchestrator_leases
            SET expires_at_ms = ?1,
                released_at_ms = NULL
            WHERE task_id = ?2
            """,
            (int(time.time() * 1000) + 45_000, CONTENDED_B_TASK),
        )
        connection.execute(
            "UPDATE task_snapshots SET updated_at = ?1 WHERE task_id = ?2",
            (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 5)), CONTENDED_A_TASK),
        )
        connection.commit()

    use_contended = run_json(
        [
            "use",
            "--db",
            CONTENDED_DB,
            "--task-id",
            CONTENDED_A_TASK,
        ],
        "operator-flow/use-contended",
        errors,
    )
    if use_contended is not None:
        expect_equal(errors, "operator-flow/use-contended", "action", use_contended.get("action"), "use")
        use_contended_result = use_contended.get("result") or {}
        expect_equal(errors, "operator-flow/use-contended", "result.task_id", use_contended_result.get("task_id"), CONTENDED_A_TASK)
        expect_equal(errors, "operator-flow/use-contended", "result.db", use_contended_result.get("db"), CONTENDED_DB)
        expect_equal(errors, "operator-flow/use-contended", "result.output", use_contended_result.get("output"), CONTENDED_SHARED_OUTPUT)
        expect_equal(errors, "operator-flow/use-contended", "result.output_source", use_contended_result.get("output_source"), "task_scope")
    wait_for_session(CONTENDED_A_TASK, CONTENDED_DB, CONTENDED_SHARED_OUTPUT, errors, "operator-flow/use-contended")

    contended_status = run_json(
        [
            "service-status",
            "--db",
            CONTENDED_DB,
            "--limit",
            "2",
        ],
        "operator-flow/service-status-contended",
        errors,
    )
    if contended_status is not None:
        result = contended_status.get("result") or {}
        coordination = result.get("coordination") or {}
        recent_tasks = result.get("recent_tasks") or []
        current_session = result.get("current_session") or {}
        expect_equal(errors, "operator-flow/service-status-contended", "result.db", result.get("db"), CONTENDED_DB)
        expect_equal(errors, "operator-flow/service-status-contended", "result.db_source", result.get("db_source"), "flag")
        expect_equal(errors, "operator-flow/service-status-contended", "result.limit", result.get("limit"), 2)
        expect_equal(errors, "operator-flow/service-status-contended", "current_session.task_id", current_session.get("task_id"), CONTENDED_A_TASK)
        expect_equal(errors, "operator-flow/service-status-contended", "coordination.status", coordination.get("status"), "contended")
        expect_equal(errors, "operator-flow/service-status-contended", "coordination.reason", coordination.get("reason"), "same_scope_peer_active")
        expect_equal(errors, "operator-flow/service-status-contended", "coordination.summary", coordination.get("summary"), "wait_for_scope_peer_release")
        expect_equal(errors, "operator-flow/service-status-contended", "coordination.task_id", coordination.get("task_id"), CONTENDED_A_TASK)
        expect_equal(errors, "operator-flow/service-status-contended", "coordination.target_scope", coordination.get("target_scope"), contended_scope)
        expect_equal(errors, "operator-flow/service-status-contended", "coordination.next_action", coordination.get("next_action"), "retry")
        expect_equal(errors, "operator-flow/service-status-contended", "coordination.next_task_id", coordination.get("next_task_id"), CONTENDED_A_TASK)
        expect_equal(errors, "operator-flow/service-status-contended", "coordination.next_blocker", coordination.get("next_blocker"), "none")
        expect_equal(errors, "operator-flow/service-status-contended", "coordination.scope_peer_count", coordination.get("scope_peer_count"), 1)
        expect_equal(errors, "operator-flow/service-status-contended", "coordination.scope_active_peer_count", coordination.get("scope_active_peer_count"), 1)
        expect_equal(errors, "operator-flow/service-status-contended", "coordination.scope_active_peer_task_id", coordination.get("scope_active_peer_task_id"), CONTENDED_B_TASK)
        expect_equal(errors, "operator-flow/service-status-contended", "coordination.scope_quarantine_active", coordination.get("scope_quarantine_active"), False)
        expect_equal(errors, "operator-flow/service-status-contended", "coordination.scope_quarantine_source", coordination.get("scope_quarantine_source"), "none")
        expect_equal(errors, "operator-flow/service-status-contended", "coordination.scope_quarantine_task_id", coordination.get("scope_quarantine_task_id"), "")
        expect_equal(errors, "operator-flow/service-status-contended", "coordination.scope_quarantine_count", coordination.get("scope_quarantine_count"), 0)
        if not recent_tasks:
            append_error(errors, "operator-flow/service-status-contended", "recent task missing")
        else:
            task = recent_tasks[0]
            expect_equal(errors, "operator-flow/service-status-contended", "recent.task_id", task.get("task_id"), CONTENDED_A_TASK)
            expect_true(errors, "operator-flow/service-status-contended", "recent.current", task.get("current"))
            expect_equal(errors, "operator-flow/service-status-contended", "recent.effect_status", task.get("effect_status"), "prepared")
            expect_equal(errors, "operator-flow/service-status-contended", "recent.lease_state", task.get("lease_state"), "expired")
            expect_equal(errors, "operator-flow/service-status-contended", "recent.next_action", task.get("next_action"), "retry")
            expect_equal(errors, "operator-flow/service-status-contended", "recent.next_reason", task.get("next_reason"), "failed_state_ready_for_retry")
            expect_equal(errors, "operator-flow/service-status-contended", "recent.next_blocker", task.get("next_blocker"), "none")
            expect_equal(errors, "operator-flow/service-status-contended", "recent.next_summary", task.get("next_summary"), "ready_now:action=retry,reason=failed_state_ready_for_retry")
            expect_equal(errors, "operator-flow/service-status-contended", "recent.next_task_id", task.get("next_task_id"), CONTENDED_A_TASK)
            expect_equal(errors, "operator-flow/service-status-contended", "recent.next_command", task.get("next_command"), f'safeclaw.cmd service-retry --db "{CONTENDED_DB}" --task-id "{CONTENDED_A_TASK}" --limit 1 --report')
            expect_equal(errors, "operator-flow/service-status-contended", "recent.coordination_status", task.get("coordination_status"), "contended")
            expect_equal(errors, "operator-flow/service-status-contended", "recent.coordination_reason", task.get("coordination_reason"), "same_scope_peer_active")
            expect_equal(errors, "operator-flow/service-status-contended", "recent.coordination_summary", task.get("coordination_summary"), "wait_for_scope_peer_release")
            expect_equal(errors, "operator-flow/service-status-contended", "recent.scope_peer_count", task.get("scope_peer_count"), 1)
            expect_equal(errors, "operator-flow/service-status-contended", "recent.scope_active_peer_count", task.get("scope_active_peer_count"), 1)
            expect_equal(errors, "operator-flow/service-status-contended", "recent.scope_active_peer_task_id", task.get("scope_active_peer_task_id"), CONTENDED_B_TASK)

    seed_failed_quarantine_a = run_json(
        [
            "seed-failed",
            "--reset",
            "--task-id",
            QUARANTINE_A_TASK,
            "--db",
            QUARANTINE_DB,
            "--output",
            QUARANTINE_A_OUTPUT,
        ],
        "operator-flow/seed-failed-quarantine-a",
        errors,
    )
    if seed_failed_quarantine_a is not None:
        expect_equal(errors, "operator-flow/seed-failed-quarantine-a", "action", seed_failed_quarantine_a.get("action"), "seed-failed")
        assert_session_fields((seed_failed_quarantine_a.get("result") or {}).get("remembered_session"), errors, "operator-flow/seed-failed-quarantine-a", "remembered_session", QUARANTINE_A_TASK, QUARANTINE_DB, QUARANTINE_A_OUTPUT)
    wait_for_session(QUARANTINE_A_TASK, QUARANTINE_DB, QUARANTINE_A_OUTPUT, errors, "operator-flow/seed-failed-quarantine-a")

    seed_failed_quarantine_b = run_json(
        [
            "seed-failed",
            "--task-id",
            QUARANTINE_B_TASK,
            "--db",
            QUARANTINE_DB,
            "--output",
            QUARANTINE_B_OUTPUT,
        ],
        "operator-flow/seed-failed-quarantine-b",
        errors,
    )
    if seed_failed_quarantine_b is not None:
        expect_equal(errors, "operator-flow/seed-failed-quarantine-b", "action", seed_failed_quarantine_b.get("action"), "seed-failed")
        assert_session_fields((seed_failed_quarantine_b.get("result") or {}).get("remembered_session"), errors, "operator-flow/seed-failed-quarantine-b", "remembered_session", QUARANTINE_B_TASK, QUARANTINE_DB, QUARANTINE_B_OUTPUT)

    with sqlite3.connect(REPO_ROOT / QUARANTINE_DB) as connection:
        connection.execute(
            "UPDATE orchestrator_tasks SET target_scope = ?1 WHERE task_id IN (?2, ?3)",
            (f"scope:{QUARANTINE_SHARED_OUTPUT}", QUARANTINE_A_TASK, QUARANTINE_B_TASK),
        )
        connection.execute(
            "UPDATE task_snapshots SET effect_status = ?1 WHERE task_id = ?2",
            ("executed_assumed", QUARANTINE_A_TASK),
        )
        connection.execute(
            "UPDATE task_snapshots SET updated_at = ?1 WHERE task_id = ?2",
            (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 5)), QUARANTINE_B_TASK),
        )
        connection.execute(
            "UPDATE orchestrator_leases SET expires_at_ms = ?1, released_at_ms = NULL WHERE task_id = ?2",
            (int(time.time() * 1000) - 1_000, QUARANTINE_A_TASK),
        )
        connection.execute(
            "UPDATE orchestrator_leases SET expires_at_ms = ?1, released_at_ms = NULL WHERE task_id = ?2",
            (int(time.time() * 1000) - 1_000, QUARANTINE_B_TASK),
        )
        connection.commit()

    use_quarantine = run_json(
        [
            "use",
            "--db",
            QUARANTINE_DB,
            "--task-id",
            QUARANTINE_B_TASK,
        ],
        "operator-flow/use-quarantine",
        errors,
    )
    if use_quarantine is not None:
        expect_equal(errors, "operator-flow/use-quarantine", "action", use_quarantine.get("action"), "use")
        use_quarantine_result = use_quarantine.get("result") or {}
        expect_equal(errors, "operator-flow/use-quarantine", "result.task_id", use_quarantine_result.get("task_id"), QUARANTINE_B_TASK)
        expect_equal(errors, "operator-flow/use-quarantine", "result.db", use_quarantine_result.get("db"), QUARANTINE_DB)
        expect_equal(errors, "operator-flow/use-quarantine", "result.output", use_quarantine_result.get("output"), QUARANTINE_SHARED_OUTPUT)
        expect_equal(errors, "operator-flow/use-quarantine", "result.output_source", use_quarantine_result.get("output_source"), "task_scope")
    wait_for_session(QUARANTINE_B_TASK, QUARANTINE_DB, QUARANTINE_SHARED_OUTPUT, errors, "operator-flow/use-quarantine")

    quarantine_status = run_json(
        [
            "service-status",
            "--db",
            QUARANTINE_DB,
            "--limit",
            "2",
        ],
        "operator-flow/service-status-quarantine",
        errors,
    )
    if quarantine_status is not None:
        result = quarantine_status.get("result") or {}
        coordination = result.get("coordination") or {}
        recent_tasks = result.get("recent_tasks") or []
        current_session = result.get("current_session") or {}
        expect_equal(errors, "operator-flow/service-status-quarantine", "result.db", result.get("db"), QUARANTINE_DB)
        expect_equal(errors, "operator-flow/service-status-quarantine", "result.db_source", result.get("db_source"), "flag")
        expect_equal(errors, "operator-flow/service-status-quarantine", "result.limit", result.get("limit"), 2)
        expect_equal(errors, "operator-flow/service-status-quarantine", "current_session.task_id", current_session.get("task_id"), QUARANTINE_B_TASK)
        expect_equal(errors, "operator-flow/service-status-quarantine", "coordination.status", coordination.get("status"), "quarantined")
        expect_equal(errors, "operator-flow/service-status-quarantine", "coordination.reason", coordination.get("reason"), "peer_executed_assumed_scope_quarantine")
        expect_equal(errors, "operator-flow/service-status-quarantine", "coordination.summary", coordination.get("summary"), "wait_for_scope_reconcile")
        expect_equal(errors, "operator-flow/service-status-quarantine", "coordination.task_id", coordination.get("task_id"), QUARANTINE_B_TASK)
        expect_equal(errors, "operator-flow/service-status-quarantine", "coordination.target_scope", coordination.get("target_scope"), f"scope:{QUARANTINE_SHARED_OUTPUT}")
        expect_equal(errors, "operator-flow/service-status-quarantine", "coordination.next_action", coordination.get("next_action"), "inspect")
        expect_equal(errors, "operator-flow/service-status-quarantine", "coordination.next_task_id", coordination.get("next_task_id"), QUARANTINE_A_TASK)
        expect_equal(errors, "operator-flow/service-status-quarantine", "coordination.next_blocker", coordination.get("next_blocker"), "scope_quarantine")
        expect_equal(errors, "operator-flow/service-status-quarantine", "coordination.scope_peer_count", coordination.get("scope_peer_count"), 1)
        expect_equal(errors, "operator-flow/service-status-quarantine", "coordination.scope_active_peer_count", coordination.get("scope_active_peer_count"), 0)
        expect_equal(errors, "operator-flow/service-status-quarantine", "coordination.scope_active_peer_task_id", coordination.get("scope_active_peer_task_id"), "")
        expect_equal(errors, "operator-flow/service-status-quarantine", "coordination.scope_quarantine_active", coordination.get("scope_quarantine_active"), True)
        expect_equal(errors, "operator-flow/service-status-quarantine", "coordination.scope_quarantine_source", coordination.get("scope_quarantine_source"), "peer")
        expect_equal(errors, "operator-flow/service-status-quarantine", "coordination.scope_quarantine_task_id", coordination.get("scope_quarantine_task_id"), QUARANTINE_A_TASK)
        expect_equal(errors, "operator-flow/service-status-quarantine", "coordination.scope_quarantine_count", coordination.get("scope_quarantine_count"), 1)
        if not recent_tasks:
            append_error(errors, "operator-flow/service-status-quarantine", "recent task missing")
        else:
            task = recent_tasks[0]
            expect_equal(errors, "operator-flow/service-status-quarantine", "recent.task_id", task.get("task_id"), QUARANTINE_B_TASK)
            expect_true(errors, "operator-flow/service-status-quarantine", "recent.current", task.get("current"))
            expect_equal(errors, "operator-flow/service-status-quarantine", "recent.effect_status", task.get("effect_status"), "prepared")
            expect_equal(errors, "operator-flow/service-status-quarantine", "recent.lease_state", task.get("lease_state"), "expired")
            expect_equal(errors, "operator-flow/service-status-quarantine", "recent.next_action", task.get("next_action"), "inspect")
            expect_equal(errors, "operator-flow/service-status-quarantine", "recent.next_reason", task.get("next_reason"), "scope_quarantined_by_peer")
            expect_equal(errors, "operator-flow/service-status-quarantine", "recent.next_blocker", task.get("next_blocker"), "scope_quarantine")
            expect_equal(errors, "operator-flow/service-status-quarantine", "recent.next_summary", task.get("next_summary"), "blocked:action=inspect,blocker=scope_quarantine,reason=scope_quarantined_by_peer")
            expect_equal(errors, "operator-flow/service-status-quarantine", "recent.next_task_id", task.get("next_task_id"), QUARANTINE_A_TASK)
            expect_equal(errors, "operator-flow/service-status-quarantine", "recent.next_command", task.get("next_command"), f'safeclaw.cmd report --db "{QUARANTINE_DB}" --task-id "{QUARANTINE_A_TASK}"')
            expect_equal(errors, "operator-flow/service-status-quarantine", "recent.coordination_status", task.get("coordination_status"), "quarantined")
            expect_equal(errors, "operator-flow/service-status-quarantine", "recent.coordination_reason", task.get("coordination_reason"), "peer_executed_assumed_scope_quarantine")
            expect_equal(errors, "operator-flow/service-status-quarantine", "recent.coordination_summary", task.get("coordination_summary"), "wait_for_scope_reconcile")
            expect_equal(errors, "operator-flow/service-status-quarantine", "recent.scope_quarantine_active", task.get("scope_quarantine_active"), True)
            expect_equal(errors, "operator-flow/service-status-quarantine", "recent.scope_quarantine_source", task.get("scope_quarantine_source"), "peer")
            expect_equal(errors, "operator-flow/service-status-quarantine", "recent.scope_quarantine_task_id", task.get("scope_quarantine_task_id"), QUARANTINE_A_TASK)
            expect_equal(errors, "operator-flow/service-status-quarantine", "recent.scope_quarantine_count", task.get("scope_quarantine_count"), 1)

    seed_crash_reconcile = run_json(
        [
            "seed-crash",
            "--reset",
            "--probe-mode",
            "none",
            "--task-id",
            RECONCILE_TASK,
            "--db",
            RECONCILE_DB,
            "--output",
            RECONCILE_OUTPUT,
        ],
        "operator-flow/seed-crash-reconcile",
        errors,
    )
    if seed_crash_reconcile is not None:
        expect_equal(errors, "operator-flow/seed-crash-reconcile", "action", seed_crash_reconcile.get("action"), "seed-crash")
        assert_session_fields((seed_crash_reconcile.get("result") or {}).get("remembered_session"), errors, "operator-flow/seed-crash-reconcile", "remembered_session", RECONCILE_TASK, RECONCILE_DB, RECONCILE_OUTPUT)
    wait_for_session(RECONCILE_TASK, RECONCILE_DB, RECONCILE_OUTPUT, errors, "operator-flow/seed-crash-reconcile")

    reconcile_status_before = run_json(
        [
            "service-status",
            "--db",
            RECONCILE_DB,
            "--limit",
            "1",
        ],
        "operator-flow/service-reconcile-status-before",
        errors,
    )
    if reconcile_status_before is not None:
        result = reconcile_status_before.get("result") or {}
        coordination = result.get("coordination") or {}
        recent_tasks = result.get("recent_tasks") or []
        current_session = result.get("current_session") or {}
        expect_equal(errors, "operator-flow/service-reconcile-status-before", "result.db", result.get("db"), RECONCILE_DB)
        expect_equal(errors, "operator-flow/service-reconcile-status-before", "result.db_source", result.get("db_source"), "flag")
        expect_equal(errors, "operator-flow/service-reconcile-status-before", "result.limit", result.get("limit"), 1)
        expect_equal(errors, "operator-flow/service-reconcile-status-before", "current_session.task_id", current_session.get("task_id"), RECONCILE_TASK)
        expect_equal(errors, "operator-flow/service-reconcile-status-before", "coordination.status", coordination.get("status"), "quarantined")
        expect_equal(errors, "operator-flow/service-reconcile-status-before", "coordination.reason", coordination.get("reason"), "self_executed_assumed_scope_quarantine")
        expect_equal(errors, "operator-flow/service-reconcile-status-before", "coordination.summary", coordination.get("summary"), "reconcile_self_before_scope_write")
        expect_equal(errors, "operator-flow/service-reconcile-status-before", "coordination.task_id", coordination.get("task_id"), RECONCILE_TASK)
        expect_equal(errors, "operator-flow/service-reconcile-status-before", "coordination.target_scope", coordination.get("target_scope"), f"scope:{RECONCILE_OUTPUT}")
        expect_equal(errors, "operator-flow/service-reconcile-status-before", "coordination.next_action", coordination.get("next_action"), "inspect")
        expect_equal(errors, "operator-flow/service-reconcile-status-before", "coordination.next_task_id", coordination.get("next_task_id"), RECONCILE_TASK)
        expect_equal(errors, "operator-flow/service-reconcile-status-before", "coordination.next_blocker", coordination.get("next_blocker"), "scope_quarantine")
        expect_equal(errors, "operator-flow/service-reconcile-status-before", "coordination.scope_peer_count", coordination.get("scope_peer_count"), 0)
        expect_equal(errors, "operator-flow/service-reconcile-status-before", "coordination.scope_active_peer_count", coordination.get("scope_active_peer_count"), 0)
        expect_equal(errors, "operator-flow/service-reconcile-status-before", "coordination.scope_active_peer_task_id", coordination.get("scope_active_peer_task_id"), "")
        expect_equal(errors, "operator-flow/service-reconcile-status-before", "coordination.scope_quarantine_active", coordination.get("scope_quarantine_active"), True)
        expect_equal(errors, "operator-flow/service-reconcile-status-before", "coordination.scope_quarantine_source", coordination.get("scope_quarantine_source"), "self")
        expect_equal(errors, "operator-flow/service-reconcile-status-before", "coordination.scope_quarantine_task_id", coordination.get("scope_quarantine_task_id"), RECONCILE_TASK)
        expect_equal(errors, "operator-flow/service-reconcile-status-before", "coordination.scope_quarantine_count", coordination.get("scope_quarantine_count"), 1)
        if not recent_tasks:
            append_error(errors, "operator-flow/service-reconcile-status-before", "recent task missing")
        else:
            task = recent_tasks[0]
            expect_equal(errors, "operator-flow/service-reconcile-status-before", "recent.task_id", task.get("task_id"), RECONCILE_TASK)
            expect_true(errors, "operator-flow/service-reconcile-status-before", "recent.current", task.get("current"))
            expect_equal(errors, "operator-flow/service-reconcile-status-before", "recent.effect_status", task.get("effect_status"), "executed_assumed")
            expect_equal(errors, "operator-flow/service-reconcile-status-before", "recent.lease_state", task.get("lease_state"), "expired")
            expect_equal(errors, "operator-flow/service-reconcile-status-before", "recent.next_action", task.get("next_action"), "inspect")
            expect_equal(errors, "operator-flow/service-reconcile-status-before", "recent.next_reason", task.get("next_reason"), "executed_assumed_requires_reconcile")
            expect_equal(errors, "operator-flow/service-reconcile-status-before", "recent.next_blocker", task.get("next_blocker"), "scope_quarantine")
            expect_equal(errors, "operator-flow/service-reconcile-status-before", "recent.next_summary", task.get("next_summary"), "blocked:action=inspect,blocker=scope_quarantine,reason=executed_assumed_requires_reconcile")
            expect_equal(errors, "operator-flow/service-reconcile-status-before", "recent.next_task_id", task.get("next_task_id"), RECONCILE_TASK)
            expect_equal(errors, "operator-flow/service-reconcile-status-before", "recent.next_command", task.get("next_command"), f'safeclaw.cmd report --db "{RECONCILE_DB}" --task-id "{RECONCILE_TASK}"')
            expect_equal(errors, "operator-flow/service-reconcile-status-before", "recent.coordination_status", task.get("coordination_status"), "quarantined")
            expect_equal(errors, "operator-flow/service-reconcile-status-before", "recent.coordination_reason", task.get("coordination_reason"), "self_executed_assumed_scope_quarantine")
            expect_equal(errors, "operator-flow/service-reconcile-status-before", "recent.coordination_summary", task.get("coordination_summary"), "reconcile_self_before_scope_write")
            expect_equal(errors, "operator-flow/service-reconcile-status-before", "recent.scope_peer_count", task.get("scope_peer_count"), 0)
            expect_equal(errors, "operator-flow/service-reconcile-status-before", "recent.scope_active_peer_count", task.get("scope_active_peer_count"), 0)
            expect_equal(errors, "operator-flow/service-reconcile-status-before", "recent.scope_active_peer_task_id", task.get("scope_active_peer_task_id"), "")
            expect_equal(errors, "operator-flow/service-reconcile-status-before", "recent.scope_quarantine_active", task.get("scope_quarantine_active"), True)
            expect_equal(errors, "operator-flow/service-reconcile-status-before", "recent.scope_quarantine_source", task.get("scope_quarantine_source"), "self")
            expect_equal(errors, "operator-flow/service-reconcile-status-before", "recent.scope_quarantine_task_id", task.get("scope_quarantine_task_id"), RECONCILE_TASK)
            expect_equal(errors, "operator-flow/service-reconcile-status-before", "recent.scope_quarantine_count", task.get("scope_quarantine_count"), 1)
            reconcile_commands = task.get("reconcile_commands") or {}
            expect_equal(errors, "operator-flow/service-reconcile-status-before", "recent.reconcile_commands.executed", reconcile_commands.get("executed"), f'safeclaw.cmd service-reconcile --db "{RECONCILE_DB}" --task-id "{RECONCILE_TASK}" --decision executed --limit 1 --report')
            expect_equal(errors, "operator-flow/service-reconcile-status-before", "recent.reconcile_commands.not_executed", reconcile_commands.get("not_executed"), f'safeclaw.cmd service-reconcile --db "{RECONCILE_DB}" --task-id "{RECONCILE_TASK}" --decision not-executed --limit 1 --report')

    service_reconcile = run_json(
        [
            "service-reconcile",
            "--db",
            RECONCILE_DB,
            "--task-id",
            RECONCILE_TASK,
            "--decision",
            "executed",
            "--limit",
            "1",
        ],
        "operator-flow/service-reconcile",
        errors,
    )
    assert_service_combo(
        service_reconcile,
        errors,
        "operator-flow/service-reconcile",
        combo_action="service-reconcile",
        primary_action="reconcile",
        task_id=RECONCILE_TASK,
        db=RECONCILE_DB,
        output=RECONCILE_OUTPUT,
        expected_output_source="session",
        expected_owner_source="session",
    )

    seed_crash_session_priority_a = run_json(
        [
            "seed-crash",
            "--reset",
            "--task-id",
            SESSION_PRIORITY_A_TASK,
            "--db",
            SESSION_PRIORITY_DB,
            "--output",
            SESSION_PRIORITY_A_OUTPUT,
        ],
        "operator-flow/seed-crash-session-priority-a",
        errors,
    )
    if seed_crash_session_priority_a is not None:
        expect_equal(errors, "operator-flow/seed-crash-session-priority-a", "action", seed_crash_session_priority_a.get("action"), "seed-crash")
        assert_session_fields((seed_crash_session_priority_a.get("result") or {}).get("remembered_session"), errors, "operator-flow/seed-crash-session-priority-a", "remembered_session", SESSION_PRIORITY_A_TASK, SESSION_PRIORITY_DB, SESSION_PRIORITY_A_OUTPUT)
    wait_for_session(SESSION_PRIORITY_A_TASK, SESSION_PRIORITY_DB, SESSION_PRIORITY_A_OUTPUT, errors, "operator-flow/seed-crash-session-priority-a")

    seed_failed_session_priority_b = run_json(
        [
            "seed-failed",
            "--task-id",
            SESSION_PRIORITY_B_TASK,
            "--db",
            SESSION_PRIORITY_DB,
            "--output",
            SESSION_PRIORITY_B_OUTPUT,
        ],
        "operator-flow/seed-failed-session-priority-b",
        errors,
    )
    if seed_failed_session_priority_b is not None:
        expect_equal(errors, "operator-flow/seed-failed-session-priority-b", "action", seed_failed_session_priority_b.get("action"), "seed-failed")
        assert_session_fields((seed_failed_session_priority_b.get("result") or {}).get("remembered_session"), errors, "operator-flow/seed-failed-session-priority-b", "remembered_session", SESSION_PRIORITY_B_TASK, SESSION_PRIORITY_DB, SESSION_PRIORITY_B_OUTPUT)

    with sqlite3.connect(REPO_ROOT / SESSION_PRIORITY_DB) as connection:
        connection.execute(
            "UPDATE task_snapshots SET updated_at = ?1 WHERE task_id = ?2",
            (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 5)), SESSION_PRIORITY_B_TASK),
        )
        connection.commit()

    use_session_priority_a = run_json(
        [
            "use",
            "--db",
            SESSION_PRIORITY_DB,
            "--task-id",
            SESSION_PRIORITY_A_TASK,
        ],
        "operator-flow/use-session-priority-a",
        errors,
    )
    if use_session_priority_a is not None:
        expect_equal(errors, "operator-flow/use-session-priority-a", "action", use_session_priority_a.get("action"), "use")
        use_session_priority_result = use_session_priority_a.get("result") or {}
        expect_equal(errors, "operator-flow/use-session-priority-a", "result.task_id", use_session_priority_result.get("task_id"), SESSION_PRIORITY_A_TASK)
        expect_equal(errors, "operator-flow/use-session-priority-a", "result.db", use_session_priority_result.get("db"), SESSION_PRIORITY_DB)
        expect_equal(errors, "operator-flow/use-session-priority-a", "result.output", use_session_priority_result.get("output"), SESSION_PRIORITY_A_OUTPUT)
        expect_equal(errors, "operator-flow/use-session-priority-a", "result.output_source", use_session_priority_result.get("output_source"), "task_scope")
    wait_for_session(SESSION_PRIORITY_A_TASK, SESSION_PRIORITY_DB, SESSION_PRIORITY_A_OUTPUT, errors, "operator-flow/use-session-priority-a")
    session_priority_status = run_json(
        [
            "service-status",
            "--db",
            SESSION_PRIORITY_DB,
            "--limit",
            "2",
        ],
        "operator-flow/service-status-session-priority",
        errors,
    )
    if session_priority_status is not None:
        result = session_priority_status.get("result") or {}
        coordination = result.get("coordination") or {}
        current_session = result.get("current_session") or {}
        recent_tasks = result.get("recent_tasks") or []
        expect_equal(errors, "operator-flow/service-status-session-priority", "result.db", result.get("db"), SESSION_PRIORITY_DB)
        expect_equal(errors, "operator-flow/service-status-session-priority", "result.db_source", result.get("db_source"), "flag")
        expect_equal(errors, "operator-flow/service-status-session-priority", "result.limit", result.get("limit"), 2)
        expect_equal(errors, "operator-flow/service-status-session-priority", "current_session.task_id", current_session.get("task_id"), SESSION_PRIORITY_A_TASK)
        expect_equal(errors, "operator-flow/service-status-session-priority", "current_session.output", current_session.get("output"), SESSION_PRIORITY_A_OUTPUT)
        expect_equal(errors, "operator-flow/service-status-session-priority", "coordination.status", coordination.get("status"), "ready")
        expect_equal(errors, "operator-flow/service-status-session-priority", "coordination.reason", coordination.get("reason"), "uncertain_state_ready_for_recover")
        expect_equal(errors, "operator-flow/service-status-session-priority", "coordination.summary", coordination.get("summary"), "recover_now")
        expect_equal(errors, "operator-flow/service-status-session-priority", "coordination.task_id", coordination.get("task_id"), SESSION_PRIORITY_A_TASK)
        expect_equal(errors, "operator-flow/service-status-session-priority", "coordination.target_scope", coordination.get("target_scope"), f"scope:{SESSION_PRIORITY_A_OUTPUT}")
        expect_equal(errors, "operator-flow/service-status-session-priority", "coordination.next_action", coordination.get("next_action"), "recover")
        expect_equal(errors, "operator-flow/service-status-session-priority", "coordination.next_task_id", coordination.get("next_task_id"), SESSION_PRIORITY_A_TASK)
        expect_equal(errors, "operator-flow/service-status-session-priority", "coordination.next_blocker", coordination.get("next_blocker"), "none")
        expect_equal(errors, "operator-flow/service-status-session-priority", "coordination.scope_peer_count", coordination.get("scope_peer_count"), 0)
        expect_equal(errors, "operator-flow/service-status-session-priority", "coordination.scope_active_peer_count", coordination.get("scope_active_peer_count"), 0)
        expect_equal(errors, "operator-flow/service-status-session-priority", "coordination.scope_active_peer_task_id", coordination.get("scope_active_peer_task_id"), "")
        expect_equal(errors, "operator-flow/service-status-session-priority", "coordination.scope_quarantine_active", coordination.get("scope_quarantine_active"), False)
        expect_equal(errors, "operator-flow/service-status-session-priority", "coordination.scope_quarantine_source", coordination.get("scope_quarantine_source"), "none")
        expect_equal(errors, "operator-flow/service-status-session-priority", "coordination.scope_quarantine_task_id", coordination.get("scope_quarantine_task_id"), "")
        expect_equal(errors, "operator-flow/service-status-session-priority", "coordination.scope_quarantine_count", coordination.get("scope_quarantine_count"), 0)
        if len(recent_tasks) < 2:
            append_error(errors, "operator-flow/service-status-session-priority", f"expected at least 2 recent tasks, got {len(recent_tasks)!r}")
        else:
            recent_newer = recent_tasks[0]
            recent_current = recent_tasks[1]
            expect_equal(errors, "operator-flow/service-status-session-priority", "recent[0].task_id", recent_newer.get("task_id"), SESSION_PRIORITY_B_TASK)
            expect_equal(errors, "operator-flow/service-status-session-priority", "recent[0].current", recent_newer.get("current"), False)
            expect_equal(errors, "operator-flow/service-status-session-priority", "recent[0].next_action", recent_newer.get("next_action"), "retry")
            expect_equal(errors, "operator-flow/service-status-session-priority", "recent[0].coordination_summary", recent_newer.get("coordination_summary"), "retry_now")
            expect_equal(errors, "operator-flow/service-status-session-priority", "recent[1].task_id", recent_current.get("task_id"), SESSION_PRIORITY_A_TASK)
            expect_equal(errors, "operator-flow/service-status-session-priority", "recent[1].current", recent_current.get("current"), True)
            expect_equal(errors, "operator-flow/service-status-session-priority", "recent[1].next_action", recent_current.get("next_action"), "recover")
            expect_equal(errors, "operator-flow/service-status-session-priority", "recent[1].coordination_summary", recent_current.get("coordination_summary"), "recover_now")

    forget_after = run_json(["forget"], "operator-flow/forget-after", errors)
    if forget_after is not None:
        expect_equal(errors, "operator-flow/forget-after", "action", forget_after.get("action"), "forget")
        expect_true(errors, "operator-flow/forget-after", "result.forgot", (forget_after.get("result") or {}).get("forgot"))



    workspace_clear_after = run_json(["workspace", "--clear"], "operator-flow/workspace-clear-after", errors)
    if workspace_clear_after is not None:
        expect_equal(errors, "operator-flow/workspace-clear-after", "action", workspace_clear_after.get("action"), "workspace")
        clear_result = workspace_clear_after.get("result") or {}
        clear_state = (clear_result.get("cleared"), clear_result.get("reason"))
        if clear_result.get("path") != "target\mvp\workspace.json":
            append_error(errors, "operator-flow/workspace-clear-after", "missing workspace path")
        elif clear_state not in {(True, "removed"), (False, "none")}:
            append_error(errors, "operator-flow/workspace-clear-after", f"unexpected clear state {clear_state!r}")

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
