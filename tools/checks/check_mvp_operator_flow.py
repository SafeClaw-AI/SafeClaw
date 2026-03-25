from __future__ import annotations

import json
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
    except json.JSONDecodeError:
        return completed.returncode, output, None
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
) -> None:
    if payload is None:
        return

    expect_equal(errors, label, "action", payload.get("action"), combo_action)
    result = payload.get("result") or {}
    steps = result.get("steps") or []
    expect_equal(errors, label, "steps.actions", [step.get("action") for step in steps], [primary_action, "service-status"])
    if len(steps) == 2:
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

    status = result.get("service_status") or {}
    expect_equal(errors, label, "service_status.db", status.get("db"), db)
    expect_equal(errors, label, "service_status.db_source", status.get("db_source"), "flag")
    expect_equal(errors, label, "service_status.limit", status.get("limit"), 1)
    expect_equal(errors, label, "service_status.queue.completed", ((status.get("queue") or {}).get("completed")), 1)
    expect_equal(errors, label, "service_status.workers.succeeded", ((status.get("workers") or {}).get("succeeded")), 1)
    expect_equal(errors, label, "service_status.effects.executed", ((status.get("effects") or {}).get("executed")), 1)
    expect_equal(errors, label, "service_status.heartbeat.interval_ms", ((status.get("heartbeat") or {}).get("interval_ms")), 10000)
    expect_equal(errors, label, "service_status.heartbeat.event_driven", ((status.get("heartbeat") or {}).get("event_driven")), True)
    expect_equal(errors, label, "service_status.heartbeat.latest_freshness", ((status.get("heartbeat") or {}).get("latest_freshness")), "lost")
    expect_equal(errors, label, "service_status.heartbeat.status", ((status.get("heartbeat") or {}).get("status")), "failed")
    expect_equal(errors, label, "service_status.heartbeat.reason", ((status.get("heartbeat") or {}).get("reason")), "recent_task_update_exceeded_grace_window")
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
    if not (status.get("heartbeat") or {}).get("latest_updated_at"):
        append_error(errors, label, "service_status.heartbeat.latest_updated_at missing")
    if not isinstance((status.get("heartbeat") or {}).get("latest_age_ms"), int):
        append_error(errors, label, "service_status.heartbeat.latest_age_ms missing int")
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
