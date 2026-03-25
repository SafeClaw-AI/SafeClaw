from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_ROOT = REPO_ROOT / "target" / "mvp"
SESSION_FILE = STATE_ROOT / "last_session.json"
WORKSPACE_FILE = STATE_ROOT / "workspace.json"
WORKSPACE_ROOT = STATE_ROOT / "workspaces"
DEFAULT_DB = STATE_ROOT / "session.db"
DEFAULT_OUTPUT = STATE_ROOT / "output.txt"
DEFAULT_OWNER_ID = "safeclaw-mvp"
DEFAULT_LIST_LIMIT = 5
DEFAULT_HEARTBEAT_INTERVAL_MS = 10_000
HEARTBEAT_CONFIG_FILE = REPO_ROOT / "specs" / "config" / "heartbeat.json"
TOOLCHAIN = "stable-x86_64-pc-windows-gnu"
LINKER = (
    r"C:\Users\tianduan999\AppData\Local\Microsoft\WinGet\Packages\BrechtSanders."
    r"WinLibs.POSIX.UCRT_Microsoft.Winget.Source_8wekyb3d8bbwe\mingw64\bin\x86_64-w64-mingw32-gcc.exe"
)
SESSION_ACTIONS = {"run", "report", "status", "seed-crash", "recover", "seed-failed", "retry", "reconcile"}
WRITES_SESSION = {"run", "seed-crash", "seed-failed"}
READS_SESSION = {"report", "status", "recover", "retry", "reconcile"}
TASK_CONTEXT_ACTIONS = {"report", "recover", "retry", "reconcile"}
LOCAL_ACTIONS = ("demo", "recover-demo", "retry-demo", "service-demo", "service-run", "service-retry", "service-recover", "service-reconcile", "service-status", "session", "sessions", "use", "forget", "workspace", "doctor", "preflight", "verify")
ENTRYPOINT_FILES = (
    ("cmd", REPO_ROOT / "tools" / "mvp" / "safeclaw_mvp.cmd"),
    ("ps1", REPO_ROOT / "tools" / "mvp" / "safeclaw_mvp.ps1"),
    ("py", REPO_ROOT / "tools" / "mvp" / "safeclaw_mvp.py"),
)
SESSION_FIELDS = ("task_id", "effect_id", "db", "output", "owner_id")
WORKSPACE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
PREFLIGHT_WRITE_ACTIONS = {
    "demo",
    "recover-demo",
    "retry-demo",
    "service-demo",
    "service-run",
    "service-retry",
    "service-recover",
    "service-reconcile",
    "workspace",
    "use",
    "forget",
    "run",
    "seed-crash",
    "recover",
    "seed-failed",
    "retry",
    "reconcile",
}
AI_REQUIRED_PREFLIGHT_ACTIONS = {"ai-reason"}
KNOWN_PREFLIGHT_ACTIONS = set(LOCAL_ACTIONS) | SESSION_ACTIONS | AI_REQUIRED_PREFLIGHT_ACTIONS
PREFLIGHT_TEMPLATE_ACTION_MAP = {
    "demo": "run",
    "recover-demo": "recover",
    "retry-demo": "retry",
    "service-run": "run",
    "service-retry": "retry",
    "service-recover": "recover",
    "service-reconcile": "reconcile",
    "service-status": "status",
    "run": "run",
    "report": "report",
    "status": "status",
    "seed-crash": "seed-crash",
    "recover": "recover",
    "seed-failed": "seed-failed",
    "retry": "retry",
    "reconcile": "reconcile",
}


def display_entry_command() -> str:
    return os.environ.get("SAFECLAW_MVP_DISPLAY_ENTRY") or "tools\\mvp\\safeclaw_mvp.cmd"
LOCAL_ACTION_FLAG_SPECS = {
    "session": {"value": set(), "boolean": {"--json"}},
    "sessions": {"value": {"--db", "--limit"}, "boolean": {"--json"}},
    "use": {
        "value": {"--db", "--task-id", "--index", "--output", "--owner-id", "--effect-id"},
        "boolean": {"--json"},
    },
    "forget": {"value": set(), "boolean": {"--json"}},
    "workspace": {"value": {"--name"}, "boolean": {"--json", "--clear"}},
    "service-demo": {"value": set(), "boolean": {"--json"}},
    "service-run": {
        "value": {"--db", "--output", "--content", "--task-id", "--owner-id", "--effect-id", "--limit", "--preflight-action"},
        "boolean": {"--json", "--reset", "--report", "--preflight", "--enforce-permission"},
    },
    "service-retry": {
        "value": {"--db", "--output", "--content", "--task-id", "--owner-id", "--effect-id", "--limit", "--preflight-action"},
        "boolean": {"--json", "--report", "--preflight", "--enforce-permission"},
    },
    "service-recover": {
        "value": {"--db", "--output", "--content", "--task-id", "--owner-id", "--effect-id", "--limit", "--preflight-action"},
        "boolean": {"--json", "--report", "--preflight", "--enforce-permission"},
    },
    "service-reconcile": {
        "value": {"--db", "--output", "--task-id", "--owner-id", "--effect-id", "--decision", "--limit", "--preflight-action"},
        "boolean": {"--json", "--report", "--preflight", "--enforce-permission"},
    },
    "service-status": {"value": {"--db", "--limit"}, "boolean": {"--json"}},
    "doctor": {"value": {"--db", "--output"}, "boolean": {"--json"}},
    "preflight": {"value": {"--action", "--scope"}, "boolean": {"--json", "--write", "--doctor-bypass", "--enforce-permission"}},
    "verify": {"value": set(), "boolean": {"--json"}},
}
SESSION_ACTION_FLAG_SPECS = {
    "run": {
        "value": {"--db", "--output", "--content", "--task-id", "--owner-id", "--effect-id"},
        "boolean": {"--reset"},
    },
    "report": {
        "value": {"--db", "--task-id", "--output", "--owner-id", "--effect-id"},
        "boolean": set(),
    },
    "status": {
        "value": {"--db", "--task-id", "--output", "--owner-id", "--effect-id"},
        "boolean": set(),
    },
    "seed-crash": {
        "value": {"--db", "--output", "--content", "--task-id", "--owner-id", "--effect-id", "--probe-mode"},
        "boolean": {"--reset"},
    },
    "recover": {
        "value": {"--db", "--task-id", "--output", "--content", "--owner-id", "--effect-id"},
        "boolean": set(),
    },
    "seed-failed": {
        "value": {"--db", "--output", "--content", "--task-id", "--owner-id", "--effect-id"},
        "boolean": {"--reset"},
    },
    "retry": {
        "value": {"--db", "--task-id", "--output", "--content", "--owner-id", "--effect-id"},
        "boolean": set(),
    },
    "reconcile": {
        "value": {"--db", "--task-id", "--output", "--owner-id", "--effect-id", "--decision"},
        "boolean": set(),
    },
}


def resolve_executable_candidate(candidate: str) -> str | None:
    path = Path(candidate).expanduser()
    if path.exists():
        return str(path)
    resolved = shutil.which(candidate)
    if resolved is not None:
        return resolved
    return None


def cargo_home_candidates(binary: str) -> list[Path]:
    filenames = [binary]
    if os.name == "nt":
        filenames = [f"{binary}.exe", f"{binary}.bat", binary]

    roots: list[Path] = []
    cargo_home = os.environ.get("CARGO_HOME")
    if cargo_home:
        roots.append(Path(cargo_home).expanduser())
    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        roots.append(Path(user_profile) / ".cargo")
    roots.append(Path.home() / ".cargo")

    candidates: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root)
        if key in seen:
            continue
        seen.add(key)
        for filename in filenames:
            candidates.append(root / "bin" / filename)
    return candidates


def resolve_executable(binary: str, *env_keys: str) -> str | None:
    for env_key in env_keys:
        candidate = os.environ.get(env_key)
        if candidate:
            resolved = resolve_executable_candidate(candidate)
            if resolved is not None:
                return resolved

    resolved = shutil.which(binary)
    if resolved is not None:
        return resolved

    for candidate in cargo_home_candidates(binary):
        if candidate.exists():
            return str(candidate)
    return None


def prepend_env_path(env: dict[str, str], *entries: str | None) -> None:
    path_entries = [item for item in env.get("PATH", "").split(os.pathsep) if item]
    seen = {os.path.normcase(os.path.normpath(item)) for item in path_entries}
    prepend: list[str] = []
    for entry in entries:
        if not entry:
            continue
        normalized = os.path.normcase(os.path.normpath(entry))
        if normalized in seen:
            continue
        seen.add(normalized)
        prepend.append(entry)
    if prepend:
        env["PATH"] = os.pathsep.join([*prepend, *path_entries])


def build_rust_env() -> tuple[dict[str, str], str | None, str | None]:
    env = os.environ.copy()
    cargo_exe = resolve_executable("cargo", "SAFECLAW_CARGO", "CARGO_EXE")
    rustc_exe = resolve_executable("rustc", "SAFECLAW_RUSTC", "RUSTC")

    tool_dir = None
    if cargo_exe is not None:
        tool_dir = str(Path(cargo_exe).resolve().parent)
    elif rustc_exe is not None:
        tool_dir = str(Path(rustc_exe).resolve().parent)

    linker_path = Path(LINKER)
    prepend_env_path(
        env,
        tool_dir,
        str(linker_path.parent) if linker_path.exists() else None,
    )

    env["RUSTUP_TOOLCHAIN"] = TOOLCHAIN
    env["CARGO_TARGET_X86_64_PC_WINDOWS_GNU_LINKER"] = LINKER
    return env, cargo_exe, rustc_exe



def main(argv: list[str]) -> int:
    raw_args = argv[1:]
    if not raw_args:
        return print_help()

    action = raw_args[0]
    if action in {"-h", "--help", "help"}:
        return print_help()
    if action == "session":
        return dispatch_local_action("session", raw_args[1:], print_session)
    if action == "sessions":
        return dispatch_local_action("sessions", raw_args[1:], print_sessions)
    if action == "use":
        return dispatch_local_action("use", raw_args[1:], activate_session)
    if action == "forget":
        return dispatch_local_action("forget", raw_args[1:], forget_session)
    if action == "workspace":
        return dispatch_local_action("workspace", raw_args[1:], run_workspace)
    if action == "doctor":
        return dispatch_local_action("doctor", raw_args[1:], run_doctor)
    if action == "preflight":
        return dispatch_local_action("preflight", raw_args[1:], run_preflight)
    if action == "verify":
        return dispatch_local_action("verify", raw_args[1:], run_verify)
    if action == "demo":
        return run_demo(raw_args[1:])
    if action == "recover-demo":
        return run_recover_demo(raw_args[1:])
    if action == "retry-demo":
        return run_retry_demo(raw_args[1:])
    if action == "service-demo":
        return dispatch_local_action("service-demo", raw_args[1:], run_service_demo)
    if action == "service-run":
        return dispatch_local_action("service-run", raw_args[1:], run_service_run)
    if action == "service-retry":
        return dispatch_local_action("service-retry", raw_args[1:], run_service_retry)
    if action == "service-recover":
        return dispatch_local_action("service-recover", raw_args[1:], run_service_recover)
    if action == "service-reconcile":
        return dispatch_local_action("service-reconcile", raw_args[1:], run_service_reconcile)
    if action == "service-status":
        return dispatch_local_action("service-status", raw_args[1:], run_service_status)
    if action not in SESSION_ACTIONS:
        return run_cargo(raw_args, action=action)

    if has_flag(raw_args[1:], "--json"):
        return execute_session_action_json(raw_args)
    return execute_session_action(raw_args)


def execute_session_action(args: list[str]) -> int:
    action = args[0]
    session = load_session()
    try:
        prepared = prepare_args(action, args, session)
    except ValueError as error:
        print(f"[mvp-wrapper] {action} => error {error}", file=sys.stderr)
        return 2
    exit_code = run_cargo(prepared, action=action)
    if exit_code == 0 and action in WRITES_SESSION:
        save_session(build_session(prepared))
    return exit_code


def dispatch_local_action(action: str, args: list[str], handler) -> int:
    validation_error = validate_local_action_args(action, args)
    if validation_error is not None:
        return emit_local_action_error(action, args, validation_error, exit_code=2)
    return handler(args)


def execute_session_action_json(args: list[str]) -> int:
    action = args[0]
    clean_args = [action, *[item for item in args[1:] if item != "--json"]]
    try:
        result = execute_session_action_capture(clean_args)
    except ValueError as error:
        details = build_remembered_session_details()
        if str(error).startswith("missing task context"):
            details["code"] = "missing-task-context"
        else:
            details["code"] = "invalid-argument"
        return emit_json_error(action, str(error), exit_code=2, details=details)
    except Exception as error:
        return emit_json_error(action, f"failed to prepare action: {error}", exit_code=1)

    payload = build_session_action_result_payload(result)
    if result["exit_code"] != 0:
        return emit_json_error(
            action,
            "underlying action failed",
            exit_code=int(result["exit_code"]),
            details=payload,
        )
    return emit_json_result(action, payload)


def execute_session_action_capture(args: list[str]) -> dict[str, object]:
    action = args[0]
    session = load_session()
    prepared = prepare_args(action, args, session)
    exit_code, output = run_cargo_capture(prepared, action=action)
    saved_session = None
    if exit_code == 0 and action in WRITES_SESSION:
        saved_session = build_session(prepared)
        save_session(saved_session)
    return {
        "action": action,
        "prepared": prepared,
        "exit_code": exit_code,
        "output": output,
        "saved_session": saved_session,
        "source_hints": describe_prepared_sources(action, args, session, prepared),
    }


def strip_local_combo_only_args(args: list[str]) -> list[str]:
    prepared: list[str] = []
    index = 0
    while index < len(args):
        token = args[index]
        if token in {"--reset", "--json", "--preflight", "--enforce-permission"}:
            index += 1
            continue
        if token == "--preflight-action":
            index += 2
            continue
        prepared.append(token)
        index += 1
    return prepared


def resolve_combo_preflight_action(local_action: str, args: list[str]) -> str:
    requested_action = str(get_flag(args, "--preflight-action") or local_action).strip()
    return requested_action or local_action


def run_demo(args: list[str]) -> int:
    json_mode = has_flag(args, "--json")
    preflight_requested = has_flag(args, "--preflight") or has_flag(args, "--enforce-permission")
    permission_enforced = has_flag(args, "--enforce-permission")
    shared_args = strip_local_combo_only_args(args)
    steps = [
        ["run", "--reset", *shared_args],
        ["status", *shared_args],
        ["report", *shared_args],
    ]
    return run_sequence(
        "demo",
        steps,
        json_mode=json_mode,
        preflight_payload=(
            build_sequence_preflight_payload(
                "demo",
                steps[0],
                permission_enforced=permission_enforced,
                requested_action=resolve_combo_preflight_action("demo", args),
            )
            if preflight_requested
            else None
        ),
    )


def run_recover_demo(args: list[str]) -> int:
    json_mode = has_flag(args, "--json")
    preflight_requested = has_flag(args, "--preflight") or has_flag(args, "--enforce-permission")
    permission_enforced = has_flag(args, "--enforce-permission")
    shared_args = strip_local_combo_only_args(args)
    steps = [
        ["seed-crash", "--reset", *shared_args],
        ["recover", *shared_args],
        ["report", *shared_args],
    ]
    return run_sequence(
        "recover-demo",
        steps,
        json_mode=json_mode,
        preflight_payload=(
            build_sequence_preflight_payload(
                "recover-demo",
                steps[0],
                permission_enforced=permission_enforced,
                requested_action=resolve_combo_preflight_action("recover-demo", args),
            )
            if preflight_requested
            else None
        ),
    )


def run_retry_demo(args: list[str]) -> int:
    json_mode = has_flag(args, "--json")
    preflight_requested = has_flag(args, "--preflight") or has_flag(args, "--enforce-permission")
    permission_enforced = has_flag(args, "--enforce-permission")
    shared_args = strip_local_combo_only_args(args)
    steps = [
        ["seed-failed", "--reset", *shared_args],
        ["retry", *shared_args],
        ["report", *shared_args],
    ]
    return run_sequence(
        "retry-demo",
        steps,
        json_mode=json_mode,
        preflight_payload=(
            build_sequence_preflight_payload(
                "retry-demo",
                steps[0],
                permission_enforced=permission_enforced,
                requested_action=resolve_combo_preflight_action("retry-demo", args),
            )
            if preflight_requested
            else None
        ),
    )


def run_service_demo(args: list[str]) -> int:
    json_mode = has_flag(args, "--json")
    exit_code, output = run_sqlite_example_capture(
        "worker_service_governance_demo",
        action="service-demo",
        replay_output=not json_mode,
    )
    if exit_code != 0:
        if json_mode:
            return emit_json_error(
                "service-demo",
                "underlying action failed",
                exit_code=exit_code,
                details={"captured_output": output.strip()},
            )
        return exit_code

    try:
        payload = build_service_demo_result_payload(output)
    except ValueError as error:
        if json_mode:
            return emit_json_error(
                "service-demo",
                str(error),
                exit_code=1,
                details={"captured_output": output.strip()},
            )
        print(f"[mvp-wrapper] service-demo => error {error}", file=sys.stderr)
        return 1

    if json_mode:
        return emit_json_result("service-demo", payload)
    return 0


def parse_list_limit(args: list[str]) -> int:
    limit_raw = get_flag(args, "--limit") or str(DEFAULT_LIST_LIMIT)
    try:
        return max(1, int(limit_raw))
    except ValueError as error:
        raise ValueError(f"invalid --limit: {limit_raw}") from error


def render_cmd_arg(value: str) -> str:
    escaped = value.replace('"', '""')
    return f'"{escaped}"'



def resolve_service_status_next_task_id(row: dict[str, object]) -> str:
    task_id = str(row.get("task_id") or "")
    next_action = str(row.get("next_action") or "inspect")
    scope_quarantine_source = str(row.get("scope_quarantine_source") or "none")
    scope_quarantine_task_id = str(row.get("scope_quarantine_task_id") or "")
    if next_action == "inspect" and scope_quarantine_source == "peer" and scope_quarantine_task_id:
        return scope_quarantine_task_id
    return task_id



def build_service_status_next_command(db: str, row: dict[str, object]) -> str:
    task_id = str(row.get("next_task_id") or resolve_service_status_next_task_id(row) or "")
    next_action = str(row.get("next_action") or "inspect")
    db_arg = render_cmd_arg(db)
    task_arg = render_cmd_arg(task_id)
    if next_action == "retry":
        return f"safeclaw.cmd service-retry --db {db_arg} --task-id {task_arg} --limit 1 --report"
    if next_action == "recover":
        return f"safeclaw.cmd service-recover --db {db_arg} --task-id {task_arg} --limit 1 --report"
    return f"safeclaw.cmd report --db {db_arg} --task-id {task_arg}"



def build_service_status_reconcile_commands(db: str, row: dict[str, object]) -> dict[str, str]:
    next_reason = str(row.get("next_reason") or "")
    task_id = str(row.get("task_id") or "")
    if next_reason != "executed_assumed_requires_reconcile" or not task_id:
        return {}
    db_arg = render_cmd_arg(db)
    task_arg = render_cmd_arg(task_id)
    base = f"safeclaw.cmd service-reconcile --db {db_arg} --task-id {task_arg}"
    return {
        "executed": f"{base} --decision executed --limit 1 --report",
        "not_executed": f"{base} --decision not-executed --limit 1 --report",
    }



def build_service_status_next_summary(row: dict[str, object]) -> str:
    next_action = str(row.get("next_action") or "inspect")
    next_reason = str(row.get("next_reason") or "manual_inspection_required")
    next_blocker = str(row.get("next_blocker") or "none")
    if next_blocker == "active_lease":
        remaining_ms = row.get("lease_remaining_ms")
        remaining_text = str(remaining_ms) if remaining_ms is not None else "unknown"
        return f"wait:remaining_ms={remaining_text},blocker=active_lease,reason={next_reason}"
    if next_action in {"ok", "retry", "recover"} and next_blocker == "none":
        return f"ready_now:action={next_action},reason={next_reason}"
    return f"blocked:action={next_action},blocker={next_blocker},reason={next_reason}"


def build_service_status_coordination_payload(row: dict[str, object]) -> dict[str, str]:
    next_action = str(row.get("next_action") or "inspect")
    next_reason = str(row.get("next_reason") or "manual_inspection_required")
    next_blocker = str(row.get("next_blocker") or "none")
    lease_freshness = str(row.get("lease_freshness") or "unknown")
    requires_write = bool(row.get("requires_write"))
    doctor_bypass = bool(row.get("doctor_bypass"))
    scope_active_peer_count = int(row.get("scope_active_peer_count") or 0)
    scope_quarantine_active = bool(row.get("scope_quarantine_active"))
    scope_quarantine_source = str(row.get("scope_quarantine_source") or "none")
    if scope_quarantine_active and requires_write and not doctor_bypass:
        if scope_quarantine_source == "self":
            return {
                "coordination_status": "quarantined",
                "coordination_reason": "self_executed_assumed_scope_quarantine",
                "coordination_summary": "reconcile_self_before_scope_write",
            }
        return {
            "coordination_status": "quarantined",
            "coordination_reason": "peer_executed_assumed_scope_quarantine",
            "coordination_summary": "wait_for_scope_reconcile",
        }
    if next_blocker == "active_lease":
        if lease_freshness == "lost":
            return {
                "coordination_status": "stalled",
                "coordination_reason": "active_lease_without_recent_heartbeat",
                "coordination_summary": "inspect_owner_or_wait_for_lease_expiry",
            }
        return {
            "coordination_status": "busy",
            "coordination_reason": "active_lease_in_progress",
            "coordination_summary": "wait_for_current_owner",
        }
    if scope_active_peer_count > 0 and requires_write and not doctor_bypass:
        return {
            "coordination_status": "contended",
            "coordination_reason": "same_scope_peer_active",
            "coordination_summary": "wait_for_scope_peer_release",
        }
    if next_action == "retry" and next_blocker == "none":
        return {
            "coordination_status": "ready",
            "coordination_reason": next_reason,
            "coordination_summary": "retry_now",
        }
    if next_action == "recover" and next_blocker == "none":
        return {
            "coordination_status": "ready",
            "coordination_reason": next_reason,
            "coordination_summary": "recover_now",
        }
    if next_action == "ok" and next_blocker == "none":
        return {
            "coordination_status": "clear",
            "coordination_reason": next_reason,
            "coordination_summary": "no_followup_needed",
        }
    return {
        "coordination_status": "inspect",
        "coordination_reason": next_reason,
        "coordination_summary": "inspect_before_followup",
    }


def build_service_coordination_payload(rows: list[dict[str, object]]) -> dict[str, object]:
    if not rows:
        return {
            "status": "idle",
            "reason": "no_recent_tasks",
            "summary": "queue_idle",
            "task_id": "",
            "target_scope": "",
            "next_action": "inspect",
            "next_task_id": "",
            "next_blocker": "none",
            "scope_quarantine_active": False,
            "scope_quarantine_source": "none",
            "scope_quarantine_task_id": "",
            "scope_quarantine_count": 0,
        }
    row = rows[0]
    return {
        "status": str(row.get("coordination_status") or "inspect"),
        "reason": str(row.get("coordination_reason") or "manual_inspection_required"),
        "summary": str(row.get("coordination_summary") or "inspect_before_followup"),
        "task_id": str(row.get("task_id") or ""),
        "target_scope": str(row.get("target_scope") or ""),
        "next_action": str(row.get("next_action") or "inspect"),
        "next_task_id": str(row.get("next_task_id") or resolve_service_status_next_task_id(row) or ""),
        "next_blocker": str(row.get("next_blocker") or "none"),
        "scope_peer_count": int(row.get("scope_peer_count") or 0),
        "scope_active_peer_count": int(row.get("scope_active_peer_count") or 0),
        "scope_active_peer_task_id": str(row.get("scope_active_peer_task_id") or ""),
        "scope_quarantine_active": bool(row.get("scope_quarantine_active")),
        "scope_quarantine_source": str(row.get("scope_quarantine_source") or "none"),
        "scope_quarantine_task_id": str(row.get("scope_quarantine_task_id") or ""),
        "scope_quarantine_count": int(row.get("scope_quarantine_count") or 0),
    }


def load_recent_task_scope_peer_facts(
    connection: sqlite3.Connection,
    target_scope: str,
    task_id: str,
    effect_status: str,
    *,
    now_ms: int,
) -> dict[str, object]:
    normalized_scope = target_scope.strip()
    if not normalized_scope:
        return {
            "scope_peer_count": 0,
            "scope_active_peer_count": 0,
            "scope_active_peer_task_id": "",
            "scope_quarantine_active": False,
            "scope_quarantine_source": "none",
            "scope_quarantine_task_id": "",
            "scope_quarantine_count": 0,
        }

    rows = connection.execute(
        """
        SELECT
            task_snapshots.task_id,
            task_snapshots.effect_status,
            latest_lease.expires_at_ms,
            latest_lease.released_at_ms
        FROM task_snapshots
        LEFT JOIN orchestrator_tasks
          ON orchestrator_tasks.task_id = task_snapshots.task_id
        LEFT JOIN orchestrator_leases AS latest_lease
          ON latest_lease.lease_id = (
              SELECT lease_view.lease_id
              FROM orchestrator_leases AS lease_view
              WHERE lease_view.task_id = task_snapshots.task_id
              ORDER BY lease_view.fencing_token DESC, lease_view.rowid DESC
              LIMIT 1
          )
        WHERE COALESCE(orchestrator_tasks.target_scope, '') = ?1
          AND task_snapshots.task_id <> ?2
        ORDER BY task_snapshots.updated_at DESC, task_snapshots.task_id DESC
        """,
        (normalized_scope, task_id),
    ).fetchall()

    active_peer_task_id = ""
    active_peer_count = 0
    quarantine_peer_task_id = ""
    quarantine_peer_count = 0
    for row in rows:
        lease_state = classify_orchestrator_lease_state(
            None if row[2] is None else int(row[2]),
            None if row[3] is None else int(row[3]),
            now_ms,
        )
        if lease_state == "active":
            active_peer_count += 1
            if not active_peer_task_id:
                active_peer_task_id = str(row[0] or "")
        if str(row[1] or "") == "executed_assumed":
            quarantine_peer_count += 1
            if not quarantine_peer_task_id:
                quarantine_peer_task_id = str(row[0] or "")

    self_quarantine = effect_status == "executed_assumed"
    scope_quarantine_source = "none"
    scope_quarantine_task_id = ""
    if self_quarantine:
        scope_quarantine_source = "self"
        scope_quarantine_task_id = task_id
    elif quarantine_peer_count > 0:
        scope_quarantine_source = "peer"
        scope_quarantine_task_id = quarantine_peer_task_id

    return {
        "scope_peer_count": len(rows),
        "scope_active_peer_count": active_peer_count,
        "scope_active_peer_task_id": active_peer_task_id,
        "scope_quarantine_active": bool(self_quarantine or quarantine_peer_count > 0),
        "scope_quarantine_source": scope_quarantine_source,
        "scope_quarantine_task_id": scope_quarantine_task_id,
        "scope_quarantine_count": quarantine_peer_count + (1 if self_quarantine else 0),
    }


def load_heartbeat_config() -> dict[str, object]:
    try:
        payload = json.loads(HEARTBEAT_CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"interval_ms": DEFAULT_HEARTBEAT_INTERVAL_MS, "event_driven": True}

    interval_ms = payload.get("default_interval_ms")
    if not isinstance(interval_ms, int) or interval_ms <= 0:
        interval_ms = DEFAULT_HEARTBEAT_INTERVAL_MS
    return {
        "interval_ms": interval_ms,
        "event_driven": bool(payload.get("event_driven", True)),
    }



def parse_iso_timestamp_ms(value: object) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        timestamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return int(timestamp.timestamp() * 1000)



def compute_timestamp_age_ms(value: object, now_ms: int) -> int | None:
    parsed_ms = parse_iso_timestamp_ms(value)
    if parsed_ms is None:
        return None
    age_ms = now_ms - parsed_ms
    return age_ms if age_ms >= 0 else 0



def classify_heartbeat_freshness(age_ms: int | None, interval_ms: int) -> str:
    if age_ms is None:
        return "unknown"
    if age_ms <= interval_ms:
        return "fresh"
    if age_ms <= interval_ms * 2:
        return "slow"
    return "lost"



def describe_heartbeat_freshness(freshness: str) -> tuple[str, str]:
    if freshness == "fresh":
        return "healthy", "recent_task_update_within_interval"
    if freshness == "slow":
        return "degraded", "recent_task_update_exceeded_interval"
    if freshness == "lost":
        return "failed", "recent_task_update_exceeded_grace_window"
    if freshness == "none":
        return "idle", "no_recent_tasks"
    return "unknown", "recent_task_timestamp_unparseable"



def build_service_heartbeat_payload(
    rows: list[dict[str, object]],
    *,
    interval_ms: int,
    event_driven: bool,
) -> dict[str, object]:
    latest_updated_at = None if not rows else rows[0].get("updated_at")
    latest_age_ms = None if not rows else rows[0].get("lease_age_ms")
    freshness = "none" if not rows else str(rows[0].get("lease_freshness") or "unknown")
    status, reason = describe_heartbeat_freshness(freshness)
    return {
        "interval_ms": interval_ms,
        "event_driven": event_driven,
        "latest_updated_at": latest_updated_at,
        "latest_age_ms": latest_age_ms,
        "latest_freshness": freshness,
        "status": status,
        "reason": reason,
    }


def build_service_offline_gate_payload() -> dict[str, object]:
    preflight_payload = build_preflight_payload("ai-reason")
    requested_action = str(preflight_payload.get("requested_action") or "ai-reason")
    error_code = str(preflight_payload.get("error_code") or "")
    status = "ready" if bool(preflight_payload.get("allowed")) else "blocked"
    if status == "ready":
        summary = "ai_actions_ready"
    elif error_code == "ERR_AI_PROVIDER_UNAVAILABLE":
        summary = "ai_actions_require_provider"
    else:
        summary = "check_preflight_for_details"
    return {
        "status": status,
        "reason": str(preflight_payload.get("reason") or "none"),
        "summary": summary,
        "requested_action": requested_action,
        "requires_model": bool(preflight_payload.get("requires_model")),
        "requires_sidecar": bool(preflight_payload.get("requires_sidecar")),
        "next_command": f"safeclaw.cmd preflight --action {requested_action}",
        "error_code": error_code,
        "detail": str(preflight_payload.get("detail") or ""),
    }


def render_service_offline_gate_summary(payload: dict[str, object]) -> str:
    return (
        f"status={payload['status']} reason={payload['reason']} summary={payload['summary']} "
        f"action={payload['requested_action']} requires_model={str(bool(payload['requires_model'])).lower()} "
        f"requires_sidecar={str(bool(payload['requires_sidecar'])).lower()} "
        f"next={payload['next_command']} error_code={payload['error_code'] or 'none'}"
    )



def build_service_status_payload(
    args: list[str],
    session: dict[str, str] | None,
    *,
    limit: int,
) -> dict[str, object]:
    db, db_source = resolve_db_selection(args, session)
    db_path = resolve_repo_path(db)
    queue = load_service_queue_counts(db_path)
    workers = load_task_snapshot_counts(db_path, "worker_state")
    effects = load_task_snapshot_counts(db_path, "effect_status")
    probes = load_task_snapshot_counts(db_path, "probe_state")
    heartbeat_config = load_heartbeat_config()
    runtime_profile = build_runtime_profile_payload()
    model_provider = build_model_provider_payload()
    sidecar = build_sidecar_payload()
    offline_gate = build_service_offline_gate_payload()
    rows = load_recent_tasks(db_path, limit, heartbeat_interval_ms=int(heartbeat_config["interval_ms"]))
    current_db = matches_session_db(session, db)
    rows_with_current = [
        {
            **row,
            "current": current_db and session is not None and session.get("task_id") == row["task_id"],
            **build_service_status_coordination_payload(row),
            "next_summary": build_service_status_next_summary(row),
            "next_task_id": resolve_service_status_next_task_id(row),
            "next_command": build_service_status_next_command(db, row),
            "reconcile_commands": build_service_status_reconcile_commands(db, row),
        }
        for row in rows
    ]
    return {
        "db": db,
        "db_source": db_source,
        "limit": limit,
        "current_session": session,
        "current_db": current_db,
        "runtime_profile": runtime_profile,
        "model_provider": model_provider,
        "sidecar": sidecar,
        "offline_gate": offline_gate,
        "queue": queue,
        "workers": workers,
        "effects": effects,
        "probes": probes,
        "heartbeat": build_service_heartbeat_payload(
            rows_with_current,
            interval_ms=int(heartbeat_config["interval_ms"]),
            event_driven=bool(heartbeat_config["event_driven"]),
        ),
        "coordination": build_service_coordination_payload(rows_with_current),
        "recent_tasks": rows_with_current,
    }


def build_service_session_action_args(session_action: str, args: list[str]) -> list[str]:
    spec = SESSION_ACTION_FLAG_SPECS[session_action]
    prepared = [session_action]
    index = 0
    while index < len(args):
        token = args[index]
        if token == "--json":
            index += 1
            continue
        if token == "--limit":
            index += 2
            continue
        if token in spec["boolean"]:
            prepared.append(token)
            index += 1
            continue
        if token in spec["value"]:
            prepared.extend([token, args[index + 1]])
            index += 2
            continue
        index += 1
    return prepared


def build_service_report_args(args: list[str]) -> list[str]:
    return build_service_session_action_args("report", args)


def build_service_status_args(args: list[str], limit: int) -> list[str]:
    status_args: list[str] = []
    db = get_flag(args, "--db")
    if db is not None:
        status_args.extend(["--db", db])
    status_args.extend(["--limit", str(limit)])
    return status_args


def build_service_status_step_result(payload: dict[str, object]) -> dict[str, object]:
    return {
        "action": "service-status",
        "ok": True,
        "exit_code": 0,
        "source_hints": {
            "db": str(payload.get("db_source") or "default"),
            "task_context": "session" if bool(payload.get("current_db")) else "none",
        },
    }


def render_preflight_summary(payload: dict[str, object]) -> str:
    summary = (
        f"action={payload['requested_action']} known={str(bool(payload['known'])).lower()} "
        f"class={payload['action_class']} tier={payload['tier']} "
        f"writes_state={str(bool(payload['writes_state'])).lower()} "
        f"target_scope={payload['target_scope'] or 'none'} "
        f"requires_write={str(bool(payload['requires_write'])).lower()} "
        f"doctor_bypass={str(bool(payload['doctor_bypass'])).lower()} "
        f"perm_ctx={str(bool(payload['permission_context_applied'])).lower()} "
        f"perm_ctx_src={payload['permission_context_source']} "
        f"enforce_perm={str(bool(payload['permission_enforced'])).lower()} "
        f"perm={payload['permission_policy']} perm_tier={payload['permission_tier']} "
        f"perm_reason={payload['permission_reason']} "
        f"decision={payload['decision']} allowed={str(bool(payload['allowed'])).lower()} "
        f"offline_ready={str(bool(payload['offline_ready'])).lower()} "
        f"requires_model={str(bool(payload['requires_model'])).lower()} "
        f"requires_sidecar={str(bool(payload['requires_sidecar'])).lower()} "
        f"degradation={payload['degradation_mode']} reason={payload['reason']}"
    )
    error_code = str(payload.get("error_code") or "").strip()
    if error_code:
        summary = f"{summary} error_code={error_code}"
    return summary


def build_preflight_step_result(payload: dict[str, object]) -> dict[str, object]:
    return {
        "action": "preflight",
        "ok": bool(payload.get("allowed")),
        "exit_code": 0 if bool(payload.get("allowed")) else 1,
        "source_hints": {
            "permission_context": str(payload.get("permission_context_source") or "none"),
        },
    }


def build_service_preflight_payload(
    local_action: str,
    session_args: list[str],
    *,
    permission_enforced: bool,
    requested_action: str | None = None,
) -> dict[str, object]:
    output = get_flag(session_args, "--output") or ""
    return build_preflight_payload(
        requested_action or local_action,
        target_scope=build_scope_value(output) if output else "",
        requires_write=local_action in PREFLIGHT_WRITE_ACTIONS,
        doctor_bypass=local_action == "service-reconcile",
        permission_enforced=permission_enforced,
        permission_context_source_hint="prepared-action",
    )


def build_sequence_preflight_payload(
    local_action: str,
    first_step: list[str],
    *,
    permission_enforced: bool,
    requested_action: str | None = None,
) -> dict[str, object]:
    output = get_flag(first_step, "--output") or ""
    return build_preflight_payload(
        requested_action or local_action,
        target_scope=build_scope_value(output) if output else "",
        requires_write=local_action in PREFLIGHT_WRITE_ACTIONS,
        doctor_bypass=False,
        permission_enforced=permission_enforced,
        permission_context_source_hint="prepared-action",
    )


def run_service_session_combo(local_action: str, session_action: str, args: list[str]) -> int:
    try:
        limit = parse_list_limit(args)
    except ValueError as error:
        return emit_local_action_error(
            local_action,
            args,
            str(error),
            exit_code=2,
            text_message=f"[mvp-wrapper] {error}",
        )

    include_report = has_flag(args, "--report")
    preflight_requested = has_flag(args, "--preflight") or has_flag(args, "--enforce-permission")
    permission_enforced = has_flag(args, "--enforce-permission")
    session_args = build_service_session_action_args(session_action, args)
    status_args = build_service_status_args(args, limit)
    report_args = build_service_report_args(args)
    nested_result_key = session_action.replace("-", "_")
    preflight_payload = (
        build_service_preflight_payload(
            local_action,
            session_args,
            permission_enforced=permission_enforced,
            requested_action=resolve_combo_preflight_action(local_action, args),
        )
        if preflight_requested
        else None
    )

    if has_flag(args, "--json"):
        step_results: list[dict[str, object]] = []
        if preflight_payload is not None:
            step_results.append(build_preflight_step_result(preflight_payload))
            if not bool(preflight_payload.get("allowed")):
                details = build_preflight_blocked_details(preflight_payload, step_results)
                return emit_json_error(local_action, "failed step=preflight", exit_code=1, code="preflight-blocked", details=details)
        try:
            action_result = execute_session_action_capture(session_args)
        except ValueError as error:
            step_results.append({"action": session_action, "ok": False, "exit_code": 2})
            details = build_remembered_session_details(
                failed_step=session_action,
                steps=step_results,
                error_message=str(error),
            )
            details["code"] = "missing-task-context" if str(error).startswith("missing task context") else "invalid-argument"
            return emit_json_error(local_action, f"failed step={session_action}", exit_code=2, details=details)

        step_results.append(
            {
                "action": str(action_result["action"]),
                "ok": action_result["exit_code"] == 0,
                "exit_code": int(action_result["exit_code"]),
                "source_hints": action_result["source_hints"],
            }
        )
        if action_result["exit_code"] != 0:
            return emit_json_error(
                local_action,
                f"failed step={session_action}",
                exit_code=int(action_result["exit_code"]),
                details=build_remembered_session_details(
                    failed_step=session_action,
                    steps=step_results,
                    captured_output=str(action_result["output"]).strip(),
                ),
            )

        status_payload = build_service_status_payload(status_args, load_session(), limit=limit)
        step_results.append(build_service_status_step_result(status_payload))
        payload = build_combo_result_payload(step_results)
        if preflight_payload is not None:
            payload["preflight"] = preflight_payload
        payload[nested_result_key] = build_session_action_result_payload(action_result)
        payload["service_status"] = status_payload

        if include_report:
            try:
                report_result = execute_session_action_capture(report_args)
            except ValueError as error:
                step_results.append({"action": "report", "ok": False, "exit_code": 2})
                details = build_remembered_session_details(
                    failed_step="report",
                    steps=step_results,
                    error_message=str(error),
                )
                details["code"] = "missing-task-context" if str(error).startswith("missing task context") else "invalid-argument"
                return emit_json_error(local_action, "failed step=report", exit_code=2, details=details)

            step_results.append(
                {
                    "action": "report",
                    "ok": report_result["exit_code"] == 0,
                    "exit_code": int(report_result["exit_code"]),
                    "source_hints": report_result["source_hints"],
                }
            )
            if report_result["exit_code"] != 0:
                return emit_json_error(
                    local_action,
                    "failed step=report",
                    exit_code=int(report_result["exit_code"]),
                    details=build_remembered_session_details(
                        failed_step="report",
                        steps=step_results,
                        captured_output=str(report_result["output"]).strip(),
                    ),
                )
            payload = build_combo_result_payload(step_results)
            if preflight_payload is not None:
                payload["preflight"] = preflight_payload
            payload[nested_result_key] = build_session_action_result_payload(action_result)
            payload["service_status"] = status_payload
            payload["report"] = build_session_action_result_payload(report_result)

        return emit_json_result(local_action, payload)

    if preflight_payload is not None:
        print(f"[mvp-wrapper] {local_action} => preflight")
        print(f"[mvp-wrapper] preflight => {render_preflight_summary(preflight_payload)}")
        if not bool(preflight_payload.get("allowed")):
            print(f"[mvp-wrapper] {local_action} => failed step=preflight exit=1", file=sys.stderr)
            return 1

    print(f"[mvp-wrapper] {local_action} => {session_action}")
    exit_code = execute_session_action(session_args)
    if exit_code != 0:
        print(f"[mvp-wrapper] {local_action} => failed step={session_action} exit={exit_code}", file=sys.stderr)
        return exit_code

    print(f"[mvp-wrapper] {local_action} => service-status")
    exit_code = run_service_status(status_args)
    if exit_code != 0:
        print(f"[mvp-wrapper] {local_action} => failed step=service-status exit={exit_code}", file=sys.stderr)
        return exit_code

    if include_report:
        print(f"[mvp-wrapper] {local_action} => report")
        exit_code = execute_session_action(report_args)
        if exit_code != 0:
            print(f"[mvp-wrapper] {local_action} => failed step=report exit={exit_code}", file=sys.stderr)
            return exit_code
    return 0



def run_service_run(args: list[str]) -> int:
    return run_service_session_combo("service-run", "run", args)


def run_service_retry(args: list[str]) -> int:
    return run_service_session_combo("service-retry", "retry", args)


def run_service_recover(args: list[str]) -> int:
    return run_service_session_combo("service-recover", "recover", args)


def run_service_reconcile(args: list[str]) -> int:
    return run_service_session_combo("service-reconcile", "reconcile", args)


def run_preflight(args: list[str]) -> int:
    requested_action = get_flag(args, "--action")
    if requested_action is None:
        return emit_local_action_error(
            "preflight",
            args,
            "preflight requires --action <name>",
            exit_code=2,
            text_message="[mvp-wrapper] preflight requires --action <name>",
        )
    payload = build_preflight_payload(
        requested_action,
        target_scope=get_flag(args, "--scope") or "",
        requires_write=has_flag(args, "--write"),
        doctor_bypass=has_flag(args, "--doctor-bypass"),
        permission_enforced=has_flag(args, "--enforce-permission"),
    )
    exit_code = 0 if bool(payload.get("allowed")) else 1
    if has_flag(args, "--json"):
        return emit_json_result("preflight", payload, exit_code=exit_code)
    print(f"[mvp-wrapper] preflight => {render_preflight_summary(payload)}")
    return exit_code


def run_verify(args: list[str]) -> int:
    command = [sys.executable, "tools/checks/check_mvp_operator_flow.py"]
    completed = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True)
    output = ((completed.stdout or "") + (completed.stderr or "")).strip()
    payload = {
        "python": sys.executable,
        "script": "tools/checks/check_mvp_operator_flow.py",
        "exit_code": completed.returncode,
        "captured_output": output,
    }
    if has_flag(args, "--json"):
        if completed.returncode != 0:
            return emit_json_error("verify", "operator flow check failed", exit_code=completed.returncode, details=payload)
        return emit_json_result("verify", payload)

    if output:
        print(output)
    if completed.returncode != 0:
        print(f"[mvp-wrapper] verify => failed exit={completed.returncode}", file=sys.stderr)
        return completed.returncode
    print("[mvp-wrapper] verify => passed")
    return 0


def run_service_status(args: list[str]) -> int:
    try:
        limit = parse_list_limit(args)
    except ValueError as error:
        return emit_local_action_error(
            "service-status",
            args,
            str(error),
            exit_code=2,
            text_message=f"[mvp-wrapper] {error}",
        )

    session = load_session()
    payload = build_service_status_payload(args, session, limit=limit)
    if has_flag(args, "--json"):
        return emit_json_result("service-status", payload)

    db = str(payload["db"])
    db_source = str(payload["db_source"])
    queue = payload["queue"]
    workers = payload["workers"]
    effects = payload["effects"]
    probes = payload["probes"]
    heartbeat = payload["heartbeat"]
    runtime_profile = payload["runtime_profile"]
    model_provider = payload["model_provider"]
    sidecar = payload["sidecar"]
    offline_gate = payload["offline_gate"]
    coordination = payload["coordination"]
    rows_with_current = payload["recent_tasks"]

    print(f"[mvp-wrapper] service-status => db={db} limit={limit} source={db_source}")
    print(
        "[mvp-wrapper] service queue => "
        f"queued={queue['queued']} active={queue['active']} expired={queue['expired']} completed={queue['completed']}"
    )
    print(f"[mvp-wrapper] service workers => {render_count_summary(workers)}")
    print(f"[mvp-wrapper] service effects => {render_count_summary(effects)}")
    print(f"[mvp-wrapper] service probes => {render_count_summary(probes)}")
    print(
        "[mvp-wrapper] service heartbeat => "
        f"interval_ms={heartbeat['interval_ms']} event_driven={str(bool(heartbeat['event_driven'])).lower()} "
        f"latest_updated_at={heartbeat['latest_updated_at'] or 'none'} "
        f"age_ms={heartbeat['latest_age_ms'] if heartbeat['latest_age_ms'] is not None else 'none'} "
        f"freshness={heartbeat['latest_freshness']} status={heartbeat['status']} reason={heartbeat['reason']}"
    )
    print(
        "[mvp-wrapper] service runtime => "
        f"mode={runtime_profile['mode']} offline_ready={str(runtime_profile['offline_ready']).lower()} "
        f"llm_required={str(runtime_profile['llm_required']).lower()} "
        f"sidecar_required={str(runtime_profile['sidecar_required']).lower()}"
    )
    print(
        "[mvp-wrapper] service model => "
        f"status={model_provider['status']} required={str(model_provider['required']).lower()} "
        f"configured={str(model_provider['configured']).lower()} degradation={model_provider['degradation_mode']}"
    )
    print(
        "[mvp-wrapper] service sidecar => "
        f"status={sidecar['status']} required={str(sidecar['required']).lower()} "
        f"configured={str(sidecar['configured']).lower()}"
    )
    print(f"[mvp-wrapper] service offline => {render_service_offline_gate_summary(offline_gate)}")
    print(
        "[mvp-wrapper] service coordination => "
        f"status={coordination['status']} reason={coordination['reason']} summary={coordination['summary']} "
        f"task={coordination['task_id'] or 'none'} scope={coordination['target_scope'] or 'none'} "
        f"next={coordination['next_action']} blocker={coordination['next_blocker']} "
        f"scope_peers={coordination['scope_peer_count']} scope_active_peers={coordination['scope_active_peer_count']} "
        f"scope_active_task={coordination['scope_active_peer_task_id'] or 'none'} "
        f"scope_quarantine={str(bool(coordination['scope_quarantine_active'])).lower()} "
        f"quarantine_source={coordination['scope_quarantine_source']} "
        f"quarantine_task={coordination['scope_quarantine_task_id'] or 'none'} "
        f"quarantine_count={coordination['scope_quarantine_count']} "
        f"next_task={coordination['next_task_id'] or 'none'}"
    )
    if session is not None:
        current = "true" if bool(payload["current_db"]) else "false"
        print(
            "[mvp-wrapper] service current => "
            f"task={session['task_id']} effect={session['effect_id']} current_db={current}"
        )
    if not rows_with_current:
        print("[mvp-wrapper] service recent => empty")
        return 0
    for index, row in enumerate(rows_with_current):
        print(
            f"[mvp-wrapper] service recent[{index}] => "
            f"task={row['task_id']} effect={row['effect_id']} worker={row['worker_state']} "
            f"effect_status={row['effect_status']} scope={row['target_scope']} "
            f"write={str(bool(row['requires_write'])).lower()} "
            f"doctor_bypass={str(bool(row['doctor_bypass'])).lower()} "
            f"perm={row['permission_policy']} perm_tier={row['permission_tier']} "
            f"perm_reason={row['permission_reason']} "
            f"lease={row['lease_state']} lease_owner={row['lease_owner_id'] or 'none'} "
            f"lease_fence={row['lease_fencing_token'] if row['lease_fencing_token'] is not None else 'none'} "
            f"lease_age_ms={row['lease_age_ms'] if row['lease_age_ms'] is not None else 'none'} "
            f"lease_freshness={row['lease_freshness']} "
            f"wait_ms={row['lease_remaining_ms'] if row['lease_remaining_ms'] is not None else 'none'} "
            f"next={row['next_action']} next_reason={row['next_reason']} blocker={row['next_blocker']} "
            f"coordination={row['coordination_status']} coordination_reason={row['coordination_reason']} "
            f"coordination_summary={row['coordination_summary']} "
            f"next_summary={row['next_summary']} next_cmd={row['next_command']} "
            f"next_task={row['next_task_id'] or 'none'} "
            f"scope_peers={row['scope_peer_count']} scope_active_peers={row['scope_active_peer_count']} "
            f"scope_active_task={row['scope_active_peer_task_id'] or 'none'} "
            f"scope_quarantine={str(bool(row['scope_quarantine_active'])).lower()} "
            f"quarantine_source={row['scope_quarantine_source']} "
            f"quarantine_task={row['scope_quarantine_task_id'] or 'none'} "
            f"quarantine_count={row['scope_quarantine_count']} "
            f"updated_at={row['updated_at']} current={str(row['current']).lower()}"
        )
        reconcile_commands = row.get("reconcile_commands") or {}
        if isinstance(reconcile_commands, dict) and reconcile_commands:
            print(
                f"[mvp-wrapper] service recent[{index}] reconcile => "
                f"executed={reconcile_commands.get('executed', 'none')} "
                f"not_executed={reconcile_commands.get('not_executed', 'none')}"
            )
    return 0
def run_sequence(
    name: str,
    steps: list[list[str]],
    json_mode: bool = False,
    preflight_payload: dict[str, object] | None = None,
) -> int:
    if json_mode:
        return run_sequence_json(name, steps, preflight_payload=preflight_payload)
    if preflight_payload is not None:
        print(f"[mvp-wrapper] {name} => preflight")
        print(f"[mvp-wrapper] preflight => {render_preflight_summary(preflight_payload)}")
        if not bool(preflight_payload.get("allowed")):
            print(f"[mvp-wrapper] {name} => failed step=preflight exit=1", file=sys.stderr)
            return 1
    for step in steps:
        print(f"[mvp-wrapper] {name} => {step[0]}")
        exit_code = execute_session_action(step)
        if exit_code != 0:
            print(f"[mvp-wrapper] {name} => failed step={step[0]} exit={exit_code}", file=sys.stderr)
            return exit_code
    return 0


def prepare_args(action: str, args: list[str], session: dict[str, str] | None) -> list[str]:
    prepared = list(args)
    workspace = load_workspace()
    validation_error = validate_session_action_args(action, prepared[1:])
    if validation_error is not None:
        raise ValueError(validation_error)
    if action in WRITES_SESSION:
        db = get_flag(prepared, "--db") or (workspace["db"] if workspace is not None else render_repo_path(DEFAULT_DB))
        ensure_flag(prepared, "--db", db)
        default_output = get_flag(prepared, "--output") or (
            workspace["output"] if matches_workspace_db(workspace, db) else default_output_for_db(db)
        )
        ensure_flag(prepared, "--output", default_output)
        task_id = get_flag(prepared, "--task-id") or f"task-safeclaw-mvp-{int(time.time() * 1000)}"
        ensure_flag(prepared, "--task-id", task_id)
        ensure_flag(prepared, "--effect-id", get_flag(prepared, "--effect-id") or f"effect-{task_id}")
        ensure_flag(prepared, "--owner-id", get_flag(prepared, "--owner-id") or DEFAULT_OWNER_ID)
        return prepared

    db = get_flag(prepared, "--db") or (
        session["db"] if session is not None else (workspace["db"] if workspace is not None else render_repo_path(DEFAULT_DB))
    )
    ensure_flag(prepared, "--db", db)

    session_matches_db = matches_session_db(session, db)
    workspace_matches_db = matches_workspace_db(workspace, db)
    default_output = (
        session["output"] if session_matches_db else (workspace["output"] if workspace_matches_db else default_output_for_db(db))
    )
    ensure_flag(prepared, "--output", get_flag(prepared, "--output") or default_output)
    owner_id, _ = resolve_owner_id_selection(prepared, session, db)
    ensure_flag(prepared, "--owner-id", owner_id)

    task_id = get_flag(prepared, "--task-id")
    if task_id is None and session_matches_db:
        task_id = session["task_id"]
        ensure_flag(prepared, "--task-id", task_id)
    if task_id is None and action in TASK_CONTEXT_ACTIONS:
        raise ValueError(
            f"missing task context for {action}: pass --task-id or activate a remembered session"
        )

    effect_id = get_flag(prepared, "--effect-id")
    if effect_id is None and task_id is not None:
        resolved_effect = lookup_latest_effect_id(resolve_repo_path(db), task_id)
        if resolved_effect is None and session_matches_db and session["task_id"] == task_id:
            resolved_effect = session["effect_id"]
        ensure_flag(prepared, "--effect-id", resolved_effect or f"effect-{task_id}")

    return prepared


def describe_prepared_sources(
    action: str,
    original_args: list[str],
    session: dict[str, str] | None,
    prepared: list[str],
) -> dict[str, str]:
    workspace = load_workspace()
    prepared_db = get_flag(prepared, "--db") or render_repo_path(DEFAULT_DB)
    session_matches_db = matches_session_db(session, prepared_db)
    workspace_matches_db = matches_workspace_db(workspace, prepared_db)

    db_source = resolve_source_hint(
        get_flag(original_args, "--db") is not None,
        is_write_action=action in WRITES_SESSION,
        session_available=session is not None,
        workspace_available=workspace is not None,
    )

    output_source = resolve_source_hint(
        get_flag(original_args, "--output") is not None,
        is_write_action=action in WRITES_SESSION,
        session_available=session_matches_db,
        workspace_available=workspace_matches_db,
    )

    owner_id_source = resolve_source_hint(
        get_flag(original_args, "--owner-id") is not None,
        is_write_action=action in WRITES_SESSION,
        session_available=session_matches_db,
        workspace_available=False,
    )

    if get_flag(original_args, "--task-id") is not None:
        task_context_source = "flag"
    elif action in WRITES_SESSION:
        task_context_source = "generated"
    elif action in TASK_CONTEXT_ACTIONS and session_matches_db:
        task_context_source = "session"
    elif action in TASK_CONTEXT_ACTIONS:
        task_context_source = "missing"
    elif action == "status" and session_matches_db and get_flag(prepared, "--task-id") is not None:
        task_context_source = "session"
    elif action == "status":
        task_context_source = "latest"
    else:
        task_context_source = "none"

    return {
        "db": db_source,
        "output": output_source,
        "owner_id": owner_id_source,
        "task_context": task_context_source,
    }


def build_session(args: list[str]) -> dict[str, str]:
    task_id = require_flag(args, "--task-id")
    return {
        "task_id": task_id,
        "effect_id": get_flag(args, "--effect-id") or f"effect-{task_id}",
        "db": require_flag(args, "--db"),
        "output": require_flag(args, "--output"),
        "owner_id": get_flag(args, "--owner-id") or DEFAULT_OWNER_ID,
    }


def build_remembered_session_details(**extra: object) -> dict[str, object]:
    details: dict[str, object] = dict(extra)
    details["remembered_session"] = load_session()
    return details


def build_preflight_blocked_details(
    preflight_payload: dict[str, object],
    steps: list[dict[str, object]],
) -> dict[str, object]:
    details = build_remembered_session_details(
        failed_step="preflight",
        steps=steps,
        preflight=preflight_payload,
        code="preflight-blocked",
        preflight_requested_action=str(preflight_payload.get("requested_action") or ""),
        preflight_reason=str(preflight_payload.get("reason") or ""),
        preflight_summary=render_preflight_summary(preflight_payload),
    )
    error_code = str(preflight_payload.get("error_code") or "").strip()
    if error_code:
        details["preflight_error_code"] = error_code
    return details


def build_runtime_profile_payload() -> dict[str, object]:
    return {
        "mode": "local_mvp",
        "offline_ready": True,
        "llm_required": False,
        "sidecar_required": False,
        "detail": "current MVP path runs local SQLite demo flows and does not require an external model provider",
    }


def build_model_provider_payload() -> dict[str, object]:
    return {
        "configured": False,
        "required": False,
        "status": "not-configured",
        "degradation_mode": "local_only_ok",
        "detail": "current MVP wrapper is local-only; model-backed flows are not wired into this entry yet",
    }


def build_sidecar_payload() -> dict[str, object]:
    return {
        "configured": False,
        "required": False,
        "status": "not-configured",
        "detail": "sidecar lifecycle is specified for later phases; current local MVP wrapper does not depend on it",
    }


def build_permission_decision_payload(
    target_scope: str,
    requires_write: bool,
    doctor_bypass: bool,
    *,
    context_available: bool = True,
) -> dict[str, object]:
    normalized_scope = target_scope.strip()
    if not context_available:
        return {
            "target_scope": normalized_scope,
            "requires_write": requires_write,
            "doctor_bypass": doctor_bypass,
            "permission_tier": suggest_recent_task_permission_tier(requires_write),
            "permission_policy": "not_evaluated",
            "permission_reason": "permission_context_not_provided",
        }
    return {
        "target_scope": normalized_scope,
        "requires_write": requires_write,
        "doctor_bypass": doctor_bypass,
        "permission_tier": suggest_recent_task_permission_tier(requires_write),
        "permission_policy": suggest_recent_task_permission_policy(normalized_scope, requires_write, doctor_bypass),
        "permission_reason": suggest_recent_task_permission_reason(normalized_scope, requires_write, doctor_bypass),
    }


def build_scope_value(value: str) -> str:
    normalized = value.strip().replace("\\", "/")
    if not normalized:
        return ""
    if normalized.startswith("scope:"):
        return normalized
    return f"scope:{normalized}"


def infer_preflight_permission_context(requested_action: str) -> dict[str, object] | None:
    mapped_action = PREFLIGHT_TEMPLATE_ACTION_MAP.get(requested_action.strip())
    if mapped_action is None:
        return None
    try:
        prepared = prepare_args(mapped_action, [mapped_action], load_session())
    except ValueError:
        return None
    output = get_flag(prepared, "--output")
    if output is None:
        return None
    return {
        "target_scope": build_scope_value(output),
        "requires_write": requested_action.strip() in PREFLIGHT_WRITE_ACTIONS,
        "doctor_bypass": mapped_action == "reconcile",
        "permission_context_source": "action-template",
    }


def resolve_preflight_permission_context(
    requested_action: str,
    target_scope: str,
    requires_write: bool,
    doctor_bypass: bool,
    *,
    permission_context_source_hint: str | None = None,
) -> dict[str, object]:
    normalized_scope = target_scope.strip()
    if normalized_scope or requires_write or doctor_bypass:
        return {
            "target_scope": normalized_scope,
            "requires_write": requires_write,
            "doctor_bypass": doctor_bypass,
            "permission_context_source": permission_context_source_hint or "explicit",
        }
    inferred = infer_preflight_permission_context(requested_action)
    if inferred is not None:
        return inferred
    return {
        "target_scope": normalized_scope,
        "requires_write": requires_write,
        "doctor_bypass": doctor_bypass,
        "permission_context_source": "none",
    }


def build_preflight_gate_payload(
    *,
    action_allowed: bool,
    action_decision: str,
    action_reason: str,
    permission_enforced: bool,
    permission_context_applied: bool,
    permission_policy: str,
    permission_reason: str,
) -> dict[str, object]:
    if not action_allowed:
        return {
            "permission_enforced": permission_enforced,
            "action_allowed": action_allowed,
            "action_decision": action_decision,
            "action_reason": action_reason,
            "allowed": False,
            "decision": action_decision,
            "reason": action_reason,
        }
    if not permission_enforced:
        return {
            "permission_enforced": False,
            "action_allowed": action_allowed,
            "action_decision": action_decision,
            "action_reason": action_reason,
            "allowed": True,
            "decision": action_decision,
            "reason": action_reason,
        }
    if not permission_context_applied:
        return {
            "permission_enforced": True,
            "action_allowed": action_allowed,
            "action_decision": action_decision,
            "action_reason": action_reason,
            "allowed": False,
            "decision": "deny",
            "reason": "permission_context_required_for_enforcement",
        }
    if permission_policy == "allow":
        return {
            "permission_enforced": True,
            "action_allowed": action_allowed,
            "action_decision": action_decision,
            "action_reason": action_reason,
            "allowed": True,
            "decision": "allow",
            "reason": permission_reason,
        }
    if permission_policy == "confirm":
        return {
            "permission_enforced": True,
            "action_allowed": action_allowed,
            "action_decision": action_decision,
            "action_reason": action_reason,
            "allowed": False,
            "decision": "confirm",
            "reason": permission_reason,
        }
    return {
        "permission_enforced": True,
        "action_allowed": action_allowed,
        "action_decision": action_decision,
        "action_reason": action_reason,
        "allowed": False,
        "decision": "deny",
        "reason": permission_reason,
    }


def build_preflight_payload(
    requested_action: str,
    *,
    target_scope: str = "",
    requires_write: bool = False,
    doctor_bypass: bool = False,
    permission_enforced: bool = False,
    permission_context_source_hint: str | None = None,
) -> dict[str, object]:
    action = requested_action.strip()
    runtime_profile = build_runtime_profile_payload()
    model_provider = build_model_provider_payload()
    sidecar = build_sidecar_payload()
    writes_state = action in PREFLIGHT_WRITE_ACTIONS
    resolved_context = resolve_preflight_permission_context(
        action,
        target_scope,
        requires_write,
        doctor_bypass,
        permission_context_source_hint=permission_context_source_hint,
    )
    resolved_target_scope = str(resolved_context["target_scope"])
    resolved_requires_write = writes_state or bool(resolved_context["requires_write"])
    resolved_doctor_bypass = bool(resolved_context["doctor_bypass"])
    permission_context_source = str(resolved_context["permission_context_source"])
    permission_context_applied = permission_context_source != "none"
    permission_payload = build_permission_decision_payload(
        resolved_target_scope,
        resolved_requires_write,
        resolved_doctor_bypass,
        context_available=permission_context_applied,
    )
    if action in AI_REQUIRED_PREFLIGHT_ACTIONS:
        gate_payload = build_preflight_gate_payload(
            action_allowed=False,
            action_decision="deny",
            action_reason="ERR_AI_PROVIDER_UNAVAILABLE",
            permission_enforced=permission_enforced,
            permission_context_applied=permission_context_applied,
            permission_policy=str(permission_payload["permission_policy"]),
            permission_reason=str(permission_payload["permission_reason"]),
        )
        return {
            "requested_action": action,
            "known": True,
            "action_class": "ai-action",
            "tier": "TIER_2",
            "writes_state": False,
            "permission_context_source": permission_context_source,
            "permission_context_applied": permission_context_applied,
            **permission_payload,
            **gate_payload,
            "offline_ready": False,
            "requires_model": True,
            "requires_sidecar": True,
            "degradation_mode": "provider_unavailable",
            "error_code": "ERR_AI_PROVIDER_UNAVAILABLE",
            "detail": "ai reasoning actions stay blocked in the current local-only MVP because no model provider or sidecar is configured",
            "runtime_profile": runtime_profile,
            "model_provider": model_provider,
            "sidecar": sidecar,
        }

    action_allowed = action in KNOWN_PREFLIGHT_ACTIONS
    action_decision = "allow" if action_allowed else "deny"
    action_reason = (
        "current_mvp_action_is_local_only"
        if action_allowed
        else "unknown_action_defaults_to_strict_deny"
    )
    gate_payload = build_preflight_gate_payload(
        action_allowed=action_allowed,
        action_decision=action_decision,
        action_reason=action_reason,
        permission_enforced=permission_enforced,
        permission_context_applied=permission_context_applied,
        permission_policy=str(permission_payload["permission_policy"]),
        permission_reason=str(permission_payload["permission_reason"]),
    )
    if not action_allowed:
        return {
            "requested_action": action,
            "known": False,
            "action_class": "unknown",
            "tier": "TIER_2",
            "writes_state": False,
            "permission_context_source": permission_context_source,
            "permission_context_applied": permission_context_applied,
            **permission_payload,
            **gate_payload,
            "offline_ready": False,
            "requires_model": False,
            "requires_sidecar": False,
            "degradation_mode": "deny_unknown",
            "detail": "preflight only allows known local MVP wrapper, session actions, or documented ai preflight placeholders in the current offline entry",
            "runtime_profile": runtime_profile,
            "model_provider": model_provider,
            "sidecar": sidecar,
        }

    return {
        "requested_action": action,
        "known": True,
        "action_class": "local-action" if action in LOCAL_ACTIONS else "session-action",
        "tier": "TIER_1" if writes_state else "TIER_0",
        "writes_state": writes_state,
        "permission_context_source": permission_context_source,
        "permission_context_applied": permission_context_applied,
        **permission_payload,
        **gate_payload,
        "offline_ready": True,
        "requires_model": False,
        "requires_sidecar": False,
        "degradation_mode": "local_only_ok",
        "detail": "current MVP wrapper action stays available without an external model provider or sidecar",
        "runtime_profile": runtime_profile,
        "model_provider": model_provider,
        "sidecar": sidecar,
    }



def build_session_action_result_payload(result: dict[str, object]) -> dict[str, object]:
    return {
        "prepared": result["prepared"],
        "captured_output": str(result["output"]),
        "saved_session": result["saved_session"],
        "remembered_session": load_session(),
        "source_hints": result["source_hints"],
    }


def resolve_db_selection(args: list[str], session: dict[str, str] | None) -> tuple[str, str]:
    workspace = load_workspace()
    db_flag = get_flag(args, "--db")
    if db_flag is not None:
        return db_flag, "flag"
    if session is not None:
        return session["db"], "session"
    if workspace is not None:
        return workspace["db"], "workspace"
    return render_repo_path(DEFAULT_DB), "default"


def resolve_output_selection(
    args: list[str],
    session: dict[str, str] | None,
    db: str,
) -> tuple[str, str]:
    workspace = load_workspace()
    output_flag = get_flag(args, "--output")
    if output_flag is not None:
        return output_flag, "flag"
    if matches_session_db(session, db):
        return session["output"], "session"
    if matches_workspace_db(workspace, db):
        return workspace["output"], "workspace"
    return default_output_for_db(db), "default"


def resolve_owner_id_selection(
    args: list[str],
    session: dict[str, str] | None,
    db: str,
) -> tuple[str, str]:
    owner_id_flag = get_flag(args, "--owner-id")
    if owner_id_flag is not None:
        return owner_id_flag, "flag"
    if matches_session_db(session, db):
        return session["owner_id"], "session"
    return DEFAULT_OWNER_ID, "default"


def resolve_source_hint(
    flag_present: bool,
    *,
    is_write_action: bool,
    session_available: bool,
    workspace_available: bool,
) -> str:
    if flag_present:
        return "flag"
    if is_write_action:
        return "workspace" if workspace_available else "default"
    if session_available:
        return "session"
    if workspace_available:
        return "workspace"
    return "default"


def matches_session_db(session: dict[str, str] | None, db: str) -> bool:
    return session is not None and session.get("db") == db


def build_combo_result_payload(steps: list[dict[str, object]]) -> dict[str, object]:
    remembered_session = load_session()
    return {
        "steps": steps,
        "remembered_session": remembered_session,
        "session": remembered_session,
    }


def print_help() -> int:
    print(f"[mvp-wrapper] usage => {display_entry_command()} <action> [flags]")
    print(f"[mvp-wrapper] local actions => {', '.join(LOCAL_ACTIONS)}")
    print(f"[mvp-wrapper] passthrough actions => {', '.join(sorted(SESSION_ACTIONS))}")
    print(
        "[mvp-wrapper] defaults => write actions auto-fill --db/--output/--task-id/--effect-id/--owner-id, "
        "read actions reuse the remembered session when possible"
    )
    print(
        "[mvp-wrapper] examples => "
        "demo | recover-demo | retry-demo | service-demo | service-run --reset --limit 1 | service-run --reset --limit 1 --report | service-retry --task-id task-demo --limit 1 --report | service-recover --task-id task-demo --limit 1 --report | service-reconcile --task-id task-demo --decision executed --limit 1 --report | service-status --limit 5 | session | sessions --limit 5 | use --index 0 | use --task-id task-demo | status --task-id task-demo | report --task-id task-demo | reconcile --task-id task-demo --decision executed | forget | workspace | workspace --name demo | workspace --clear | doctor | preflight --action service-run --enforce-permission | verify"
    )
    print(
        "[mvp-wrapper] demo flows => demo=run->status->report; recover-demo=seed-crash->recover->report; "
        "retry-demo=seed-failed->retry->report; service-demo=worker-service-governance; service-run=run->service-status; service-retry=retry->service-status; service-recover=recover->service-status; service-reconcile=reconcile->service-status"
    )
    print(
        "[mvp-wrapper] failure flows => run 直接执行到完成；seed-crash/recover 演示 uncertain 恢复；"
        "seed-failed/retry 演示失败态重试"
    )
    print(
        "[mvp-wrapper] json => demo/recover-demo/retry-demo/service-demo/service-run/service-retry/service-recover/service-reconcile/service-status/run/report/status/"
        "seed-crash/recover/seed-failed/retry/reconcile/session/sessions/use/forget/workspace/doctor/preflight/verify 支持 --json，"
        "统一返回 {ok, action, schema_version, result|error} 信封"
    )
    print(
        "[mvp-wrapper] errors => invalid-argument / missing-task-context；"
        "组合动作 JSON 失败会额外附带 failed_step / code / error_message"
    )
    print(
        "[mvp-wrapper] error hints => invalid-argument 多为未知参数或 flag 缺值；"
        "missing-task-context 时请传 --task-id，或先 use/run/seed-crash/seed-failed 建立上下文"
    )
    print(
        "[mvp-wrapper] error message => error.message 是稳定的 wrapper 级消息；"
        "脚本无需解析底层 cargo 文案"
    )
    print(
        "[mvp-wrapper] error session => 包装层错误 JSON 若当前存在 remembered session；"
        "会在 error.details.remembered_session 附带它"
    )
    print(
        "[mvp-wrapper] session => session 显示当前记忆的最近成功会话；sessions/use/forget 管理 remembered session；"
        "status/report/recover/retry/doctor 会尽量复用它"
    )
    print(
        "[mvp-wrapper] status/report => status 默认查看当前 remembered session，也可显式传 --task-id；"
        "report 查看指定 task/effect 的治理视图"
    )
    print(
        "[mvp-wrapper] service demo => service-demo shows worker service governance summary for resolved / confirmation queues; "
        "--json returns structured summary and raw output"
    )
    print(
        "[mvp-wrapper] service run => service-run executes run then service-status with one command; "
        "supports write flags plus --limit / --preflight / --enforce-permission / --json"
    )
    print(
        "[mvp-wrapper] service retry => service-retry executes retry then service-status for a failed task; "
        "supports retry flags plus --limit / --preflight / --enforce-permission / --json"
    )
    print(
        "[mvp-wrapper] service recover => service-recover executes recover then service-status for an uncertain task; "
        "supports recover flags plus --limit / --preflight / --enforce-permission / --json"
    )
    print(
        "[mvp-wrapper] service reconcile => service-reconcile executes reconcile then service-status for an executed_assumed task; "
        "requires --decision executed|not-executed and supports reconcile flags plus --limit / --report / --preflight / --enforce-permission / --json"
    )
    print(
        "[mvp-wrapper] service status => service-status shows queue / worker / effect / probe / heartbeat summary / runtime / model-provider / sidecar snapshots / offline gate summary / coordination summary / recent task summary, plus scope, same-scope peer / scope-quarantine visibility, permission decisions, lease freshness, active-lease wait timing, next action hints, suggested commands, short reasons, blockers, coordination hints, and one-line summaries; "
        "supports --db / --limit / --json"
    )
    print(
        "[mvp-wrapper] doctor => 文本模式会检查包装入口、cargo/toolchain/linker、remembered session 路径，并给出 db/output 来源；"
        "--json 会额外返回 status 与 failing_checks"
    )
    print(
        "[mvp-wrapper] preflight => preflight checks whether an action stays allowed in the current local-only MVP entry; "
        "common wrapper/session actions auto-infer permission context from remembered session/workspace/default output, preflight-only ai-reason returns ERR_AI_PROVIDER_UNAVAILABLE when no provider/sidecar is configured, explicit --scope / --write / --doctor-bypass override permission context, and --enforce-permission fails closed on confirm / deny; supports --action <name> / --scope <value> / --json"
    )
    print(
        "[mvp-wrapper] combo preflight override => demo/recover-demo/retry-demo/service-run/service-retry/service-recover/service-reconcile accept --preflight-action <name>; blocked combo JSON keeps full error.details.preflight, mirrors preflight-blocked at top-level error.code, and mirrors preflight_requested_action / preflight_reason / preflight_summary / optional preflight_error_code at the error.details top level"
    )
    print(
        "[mvp-wrapper] verify => verify runs the practical MVP operator flow gate; "
        "supports --json and reuses the current Python interpreter"
    )
    print(
        "[mvp-wrapper] workspace => workspace shows or activates the current named workspace; "
        "--name selects it, --clear resets to default db/output"
    )
    print(
        "[mvp-wrapper] workspace defaults => when active, write actions default to workspace db/output; "
        "read actions fall back to workspace when no remembered session applies"
    )
    print(
        "[mvp-wrapper] service report => add --report to service-run / service-retry / service-recover / service-reconcile to append report after service-status"
    )
    print(
        "[mvp-wrapper] combo preflight => demo/recover-demo/retry-demo/service-run/service-retry/service-recover/service-reconcile support --preflight / --enforce-permission; "
        "JSON success returns result.preflight, blocked runs fail at step=preflight"
    )
    print(
        "[mvp-wrapper] source hints => status/report/recover/retry/reconcile --json 会额外返回 result.source_hints；"
        "可直接看到 db/output/owner_id/task_context 来源"
    )
    print(
        "[mvp-wrapper] combo source hints => demo/recover-demo/retry-demo/service-run/service-retry/service-recover/service-reconcile --json result.steps[*] and error.details.steps[*] include source_hints"
    )
    print(
        "[mvp-wrapper] combo session => demo/recover-demo/retry-demo/service-run/service-retry/service-recover/service-reconcile --json returns result.remembered_session; "
        "result.session stays as a compatibility alias; scripts should prefer remembered_session"
    )
    print(
        "[mvp-wrapper] session list => sessions 会列出当前 db 的最近任务快照；"
        "use 可按 --index / --task-id 激活其中一条"
    )
    print(
        "[mvp-wrapper] session selectors => status 可显式传 --task-id；"
        "use 支持 --index / --task-id 选择历史会话"
    )
    print(
        "[mvp-wrapper] session sources => sessions 默认优先复用 remembered session 的 db，文本/JSON 都会标 source；"
        "use 文本/JSON 都会标选择来源与 db/output/owner 来源，--json 会返回 source/db_source/output_source/owner_id_source"
    )
    print(
        "[mvp-wrapper] session paths => session 文本输出会带 remembered session 文件路径；"
        "forget 文本/JSON 会显式给出 reason/path，且不删除 db/output 文件"
    )
    print(
        "[mvp-wrapper] session repair => remembered session 文件损坏时会自动丢弃并回退为 session => none"
    )
    return 0


def print_session(args: list[str]) -> int:
    session = load_session()
    session_path = render_repo_path(SESSION_FILE)
    if has_flag(args, "--json"):
        return emit_json_result("session", session)
    if session is None:
        print(f"[mvp-wrapper] session => none path={session_path}")
        return 0
    print(
        "[mvp-wrapper] session => "
        f"task={session['task_id']} effect={session['effect_id']} db={session['db']} "
        f"output={session['output']} owner={session['owner_id']} path={session_path}"
    )
    return 0


def forget_session(args: list[str]) -> int:
    session_path = render_repo_path(SESSION_FILE)
    if not SESSION_FILE.exists():
        if has_flag(args, "--json"):
            return emit_json_result("forget", {"forgot": False, "path": session_path, "reason": "none"})
        print(f"[mvp-wrapper] forgot => reason=none path={session_path}")
        return 0
    try:
        SESSION_FILE.unlink()
    except OSError as error:
        return emit_local_action_error(
            "forget",
            args,
            f"failed to delete remembered session: {error}",
            exit_code=1,
            text_message=f"[mvp-wrapper] forgot => error {error}",
        )
    if has_flag(args, "--json"):
        return emit_json_result("forget", {"forgot": True, "path": session_path, "reason": "removed"})
    print(f"[mvp-wrapper] forgot => reason=removed path={session_path}")
    return 0




def workspace_db_for_name(name: str) -> str:
    return render_repo_path(WORKSPACE_ROOT / name / "session.db")


def workspace_output_for_name(name: str) -> str:
    return render_repo_path(WORKSPACE_ROOT / name / "output.txt")


def validate_workspace_name(name: str) -> str | None:
    if not name:
        return "workspace name must not be empty"
    if WORKSPACE_NAME_PATTERN.fullmatch(name) is None:
        return "invalid workspace name: use letters, digits, dot, underscore, or dash"
    return None


def matches_workspace_db(workspace: dict[str, str] | None, db: str) -> bool:
    return workspace is not None and workspace.get("db") == db


def load_workspace() -> dict[str, str] | None:
    if not WORKSPACE_FILE.exists():
        return None
    try:
        payload = json.loads(WORKSPACE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        repair_invalid_workspace(str(error))
        return None
    if not isinstance(payload, dict):
        repair_invalid_workspace("expected object payload")
        return None
    name = payload.get("name")
    if not isinstance(name, str):
        repair_invalid_workspace("missing workspace name")
        return None
    validation_error = validate_workspace_name(name)
    if validation_error is not None:
        repair_invalid_workspace(validation_error)
        return None
    return {
        "name": name,
        "db": workspace_db_for_name(name),
        "output": workspace_output_for_name(name),
    }


def save_workspace(name: str) -> None:
    STATE_ROOT.mkdir(parents=True, exist_ok=True)
    WORKSPACE_FILE.write_text(json.dumps({"name": name}, indent=2, ensure_ascii=False), encoding="utf-8")


def repair_invalid_workspace(reason: str) -> None:
    try:
        WORKSPACE_FILE.unlink(missing_ok=True)
    except OSError as error:
        print(
            "[mvp-wrapper] workspace repair => "
            f"failed to drop invalid {render_repo_path(WORKSPACE_FILE)} reason={reason} error={error}",
            file=sys.stderr,
        )
        return
    print(
        "[mvp-wrapper] workspace repair => "
        f"dropped invalid {render_repo_path(WORKSPACE_FILE)} reason={reason}",
        file=sys.stderr,
    )


def build_workspace_status_payload(workspace: dict[str, str] | None) -> dict[str, object]:
    if workspace is None:
        return {
            "active": False,
            "name": None,
            "db": render_repo_path(DEFAULT_DB),
            "output": render_repo_path(DEFAULT_OUTPUT),
            "path": render_repo_path(WORKSPACE_FILE),
        }
    return {
        "active": True,
        "name": workspace["name"],
        "db": workspace["db"],
        "output": workspace["output"],
        "path": render_repo_path(WORKSPACE_FILE),
    }


def run_workspace(args: list[str]) -> int:
    workspace_path = render_repo_path(WORKSPACE_FILE)
    name = get_flag(args, "--name")
    clear = has_flag(args, "--clear")
    if name is not None and clear:
        return emit_local_action_error(
            "workspace",
            args,
            "workspace accepts either --name or --clear, not both",
            exit_code=2,
            text_message="[mvp-wrapper] workspace accepts either --name or --clear, not both",
        )
    if name is not None:
        validation_error = validate_workspace_name(name)
        if validation_error is not None:
            return emit_local_action_error(
                "workspace",
                args,
                validation_error,
                exit_code=2,
                text_message=f"[mvp-wrapper] {validation_error}",
            )
        save_workspace(name)
        payload = build_workspace_status_payload(load_workspace())
        payload["changed"] = True
        if has_flag(args, "--json"):
            return emit_json_result("workspace", payload)
        print(
            "[mvp-wrapper] workspace => "
            f"activated name={payload['name']} db={payload['db']} output={payload['output']} path={workspace_path}"
        )
        return 0
    if clear:
        if not WORKSPACE_FILE.exists():
            payload = {"cleared": False, "path": workspace_path, "reason": "none"}
            if has_flag(args, "--json"):
                return emit_json_result("workspace", payload)
            print(f"[mvp-wrapper] workspace => reason=none path={workspace_path}")
            return 0
        try:
            WORKSPACE_FILE.unlink()
        except OSError as error:
            return emit_local_action_error(
                "workspace",
                args,
                f"failed to delete workspace file: {error}",
                exit_code=1,
                text_message=f"[mvp-wrapper] workspace => error {error}",
            )
        payload = {"cleared": True, "path": workspace_path, "reason": "removed"}
        if has_flag(args, "--json"):
            return emit_json_result("workspace", payload)
        print(f"[mvp-wrapper] workspace => reason=removed path={workspace_path}")
        return 0

    payload = build_workspace_status_payload(load_workspace())
    if has_flag(args, "--json"):
        return emit_json_result("workspace", payload)
    if payload["active"] is not True:
        print(
            "[mvp-wrapper] workspace => "
            f"none path={workspace_path} db={payload['db']} output={payload['output']}"
        )
        return 0
    print(
        "[mvp-wrapper] workspace => "
        f"name={payload['name']} db={payload['db']} output={payload['output']} path={workspace_path}"
    )
    return 0

def run_doctor(args: list[str]) -> int:
    session = load_session()
    workspace = load_workspace()
    db, db_source = resolve_db_selection(args, session)
    output, output_source = resolve_output_selection(args, session, db)

    rust_env, cargo_exe, rustc_exe = build_rust_env()
    cargo_ok, cargo_detail = probe_command(
        None if cargo_exe is None else [cargo_exe, "--version"],
        env=rust_env,
        missing_detail="cargo executable not found; checked PATH and ~/.cargo/bin",
    )
    toolchain_command = None
    if rustc_exe is not None:
        toolchain_command = [rustc_exe, f"+{TOOLCHAIN}", "--version"]
    elif cargo_exe is not None:
        toolchain_command = [cargo_exe, f"+{TOOLCHAIN}", "rustc", "--version"]
    toolchain_ok, toolchain_detail = probe_command(
        toolchain_command,
        env=rust_env,
        missing_detail="rust toolchain executable not found; checked PATH and ~/.cargo/bin",
    )
    linker_path = Path(LINKER)
    linker_ok = linker_path.exists()
    entrypoints = {
        name: {"path": render_repo_path(path), "exists": path.exists()}
        for name, path in ENTRYPOINT_FILES
    }
    entry_ok = all(item["exists"] for item in entrypoints.values())
    db_path = resolve_repo_path(db)
    output_path = resolve_repo_path(output)
    failing_checks = [
        name
        for name, ok in (("entry", entry_ok), ("cargo", cargo_ok), ("toolchain", toolchain_ok), ("linker", linker_ok))
        if not ok
    ]
    doctor_status = "ready" if not failing_checks else "degraded"

    runtime_profile = build_runtime_profile_payload()
    model_provider = build_model_provider_payload()
    sidecar = build_sidecar_payload()

    payload = {
        "repo": str(REPO_ROOT),
        "status": doctor_status,
        "failing_checks": failing_checks,
        "python": {"ok": True, "detail": sys.executable},
        "entrypoints": entrypoints,
        "cargo": {"ok": cargo_ok, "detail": cargo_detail},
        "toolchain": {"ok": toolchain_ok, "detail": toolchain_detail},
        "linker": {"ok": linker_ok, "detail": render_repo_path(linker_path)},
        "runtime_profile": runtime_profile,
        "model_provider": model_provider,
        "sidecar": sidecar,
        "session": session,
        "session_path": render_repo_path(SESSION_FILE),
        "workspace": build_workspace_status_payload(workspace),
        "db": {"path": render_repo_path(db_path), "exists": db_path.exists(), "source": db_source},
        "output": {"path": render_repo_path(output_path), "exists": output_path.exists(), "source": output_source},
    }
    if has_flag(args, "--json"):
        return emit_json_result(
            "doctor",
            payload,
            exit_code=0 if doctor_status == "ready" else 1,
        )

    print(f"[mvp-wrapper] doctor repo => {REPO_ROOT}")
    print(f"[mvp-wrapper] doctor python => ok {sys.executable}")
    entry_names = " ".join(f"{name}={entrypoints[name]['path']}" for name, _ in ENTRYPOINT_FILES)
    if not entry_ok:
        missing_entries = ",".join(name for name, _ in ENTRYPOINT_FILES if not entrypoints[name]["exists"])
        entry_names = f"{entry_names} missing={missing_entries}"
    print(f"[mvp-wrapper] doctor entry => {'ok' if entry_ok else 'error'} {entry_names}")
    print(f"[mvp-wrapper] doctor cargo => {'ok' if cargo_ok else 'error'} {cargo_detail}")
    print(f"[mvp-wrapper] doctor toolchain => {'ok' if toolchain_ok else 'error'} {toolchain_detail}")
    print(
        f"[mvp-wrapper] doctor linker => {'ok' if linker_ok else 'error'} {render_repo_path(linker_path)}"
    )
    print(f"[mvp-wrapper] doctor session_path => {render_repo_path(SESSION_FILE)}")
    if workspace is None:
        print(
            "[mvp-wrapper] doctor workspace => "
            f"none path={render_repo_path(WORKSPACE_FILE)} db={render_repo_path(DEFAULT_DB)} output={render_repo_path(DEFAULT_OUTPUT)}"
        )
    else:
        print(
            "[mvp-wrapper] doctor workspace => "
            f"name={workspace['name']} path={render_repo_path(WORKSPACE_FILE)} db={workspace['db']} output={workspace['output']}"
        )
    if session is None:
        print("[mvp-wrapper] doctor session => none")
    else:
        print(
            "[mvp-wrapper] doctor session => "
            f"task={session['task_id']} effect={session['effect_id']} db={session['db']} "
            f"output={session['output']} owner={session['owner_id']}"
        )
    print(
        f"[mvp-wrapper] doctor db => {'present' if db_path.exists() else 'missing'} {render_repo_path(db_path)}"
    )
    print(
        f"[mvp-wrapper] doctor output => {'present' if output_path.exists() else 'missing'} {render_repo_path(output_path)}"
    )
    print(f"[mvp-wrapper] doctor source => db={db_source} output={output_source}")
    print(
        "[mvp-wrapper] doctor runtime => "
        f"mode={runtime_profile['mode']} offline_ready={str(runtime_profile['offline_ready']).lower()} "
        f"llm_required={str(runtime_profile['llm_required']).lower()} "
        f"sidecar_required={str(runtime_profile['sidecar_required']).lower()}"
    )
    print(
        "[mvp-wrapper] doctor model => "
        f"status={model_provider['status']} required={str(model_provider['required']).lower()} "
        f"configured={str(model_provider['configured']).lower()} degradation={model_provider['degradation_mode']}"
    )
    print(
        "[mvp-wrapper] doctor sidecar => "
        f"status={sidecar['status']} required={str(sidecar['required']).lower()} "
        f"configured={str(sidecar['configured']).lower()}"
    )
    print(
        f"[mvp-wrapper] doctor summary => {doctor_status}"
        + ("" if not failing_checks else f" failing={','.join(failing_checks)}")
    )
    return 0 if doctor_status == "ready" else 1


def print_sessions(args: list[str]) -> int:
    session = load_session()
    db, db_source = resolve_db_selection(args, session)
    limit_raw = get_flag(args, "--limit") or str(DEFAULT_LIST_LIMIT)
    try:
        limit = max(1, int(limit_raw))
    except ValueError:
        return emit_local_action_error(
            "sessions",
            args,
            f"invalid --limit: {limit_raw}",
            exit_code=2,
            text_message=f"[mvp-wrapper] invalid --limit: {limit_raw}",
        )

    db_path = resolve_repo_path(db)
    rows = load_recent_tasks(db_path, limit, heartbeat_interval_ms=int(load_heartbeat_config()["interval_ms"]))
    rows_with_current = [
        {
            **row,
            "current": matches_session_db(session, db) and session.get("task_id") == row["task_id"],
        }
        for row in rows
    ]
    if has_flag(args, "--json"):
        return emit_json_result(
            "sessions",
            {
                "db": db,
                "db_source": db_source,
                "limit": limit,
                "current_session": session,
                "rows": rows_with_current,
            },
        )

    print(f"[mvp-wrapper] sessions => db={db} limit={limit} source={db_source}")
    if session is not None:
        current = "true" if matches_session_db(session, db) else "false"
        print(
            "[mvp-wrapper] current => "
            f"task={session['task_id']} effect={session['effect_id']} current_db={current}"
        )

    if not rows_with_current:
        print("[mvp-wrapper] recent => empty")
        return 0

    for index, row in enumerate(rows_with_current):
        print(
            f"[mvp-wrapper] recent[{index}] => "
            f"task={row['task_id']} effect={row['effect_id']} worker={row['worker_state']} "
            f"effect_status={row['effect_status']} updated_at={row['updated_at']} current={str(row['current']).lower()}"
        )
    return 0


def activate_session(args: list[str]) -> int:
    session = load_session()
    db, db_source = resolve_db_selection(args, session)
    db_path = resolve_repo_path(db)

    task_id = get_flag(args, "--task-id")
    index_raw = get_flag(args, "--index")
    if task_id is not None and index_raw is not None:
        return emit_local_action_error(
            "use",
            args,
            "use requires either --task-id or --index, not both",
            exit_code=2,
            text_message="[mvp-wrapper] use requires either --task-id or --index, not both",
        )

    if task_id is None:
        index_raw = index_raw or "0"
        try:
            index = int(index_raw)
        except ValueError:
            return emit_local_action_error(
                "use",
                args,
                f"invalid --index: {index_raw}",
                exit_code=2,
                text_message=f"[mvp-wrapper] invalid --index: {index_raw}",
            )
        if index < 0:
            return emit_local_action_error(
                "use",
                args,
                f"invalid --index: {index_raw}",
                exit_code=2,
                text_message=f"[mvp-wrapper] invalid --index: {index_raw}",
            )
        rows = load_recent_tasks(db_path, max(index + 1, DEFAULT_LIST_LIMIT), heartbeat_interval_ms=int(load_heartbeat_config()["interval_ms"]))
        if index >= len(rows):
            return emit_local_action_error(
                "use",
                args,
                f"no recent task at index {index} for db={db}",
                exit_code=2,
                text_message=f"[mvp-wrapper] no recent task at index {index} for db={db}",
            )
        target = rows[index]
        source = f"index:{index}"
    else:
        target = lookup_task_entry(db_path, task_id)
        if target is None:
            return emit_local_action_error(
                "use",
                args,
                f"missing task snapshot for task={task_id} db={db}",
                exit_code=2,
                text_message=f"[mvp-wrapper] missing task snapshot for task={task_id} db={db}",
            )
        source = f"task:{task_id}"

    output, output_source = resolve_output_selection(args, session, db)

    owner_id, owner_id_source = resolve_owner_id_selection(args, session, db)

    selected_session = {
        "task_id": target["task_id"],
        "effect_id": get_flag(args, "--effect-id") or target["effect_id"],
        "db": db,
        "db_source": db_source,
        "output": output,
        "output_source": output_source,
        "owner_id": owner_id,
        "owner_id_source": owner_id_source,
        "source": source,
    }
    save_session({key: selected_session[key] for key in SESSION_FIELDS})
    if has_flag(args, "--json"):
        return emit_json_result("use", selected_session)
    print(
        "[mvp-wrapper] activated => "
        f"task={selected_session['task_id']} effect={selected_session['effect_id']} db={selected_session['db']} "
        f"output={selected_session['output']} owner={selected_session['owner_id']} source={source} "
        f"db_source={db_source} output_source={output_source} owner_source={owner_id_source}"
    )
    return 0


def load_session() -> dict[str, str] | None:
    if not SESSION_FILE.exists():
        return None
    try:
        payload = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        repair_invalid_session(str(error))
        return None
    if not isinstance(payload, dict):
        repair_invalid_session("expected object payload")
        return None
    session = {key: payload.get(key) for key in SESSION_FIELDS}
    if any(not isinstance(value, str) or value == "" for value in session.values()):
        repair_invalid_session("missing required string fields")
        return None
    return session


def save_session(session: dict[str, str]) -> None:
    STATE_ROOT.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(json.dumps(session, indent=2, ensure_ascii=False), encoding="utf-8")


def repair_invalid_session(reason: str) -> None:
    try:
        SESSION_FILE.unlink(missing_ok=True)
    except OSError as error:
        print(
            "[mvp-wrapper] session repair => "
            f"failed to drop invalid {render_repo_path(SESSION_FILE)} reason={reason} error={error}",
            file=sys.stderr,
        )
        return
    print(
        "[mvp-wrapper] session repair => "
        f"dropped invalid {render_repo_path(SESSION_FILE)} reason={reason}",
        file=sys.stderr,
    )


def classify_orchestrator_lease_state(
    expires_at_ms: int | None,
    released_at_ms: int | None,
    now_ms: int,
) -> str:
    if expires_at_ms is None:
        return "none"
    if released_at_ms is not None:
        return "released"
    if expires_at_ms > now_ms:
        return "active"
    return "expired"



def compute_orchestrator_lease_remaining_ms(
    expires_at_ms: int | None,
    released_at_ms: int | None,
    now_ms: int,
) -> int | None:
    if expires_at_ms is None or released_at_ms is not None:
        return None
    remaining_ms = int(expires_at_ms) - now_ms
    return remaining_ms if remaining_ms > 0 else None



def suggest_recent_task_next_action(
    worker_state: str,
    effect_status: str,
    lease_state: str,
    *,
    scope_quarantine_blocked: bool,
) -> str:
    if worker_state == "succeeded" and effect_status == "executed":
        return "ok"
    if effect_status == "executed_assumed":
        return "inspect"
    if scope_quarantine_blocked:
        return "inspect"
    if lease_state == "active":
        return "inspect"
    if worker_state == "failed":
        return "retry"
    if worker_state == "uncertain" or effect_status == "uncertain":
        return "recover"
    return "inspect"



def suggest_recent_task_next_reason(
    worker_state: str,
    effect_status: str,
    lease_state: str,
    *,
    scope_quarantine_blocked: bool,
    scope_quarantine_source: str,
) -> str:
    if worker_state == "succeeded" and effect_status == "executed":
        return "execution_already_confirmed"
    if effect_status == "executed_assumed":
        return "executed_assumed_requires_reconcile"
    if scope_quarantine_blocked:
        return (
            "scope_quarantined_by_peer"
            if scope_quarantine_source == "peer"
            else "scope_quarantined"
        )
    if lease_state == "active":
        return "lease_still_active"
    if worker_state == "failed":
        return "failed_state_ready_for_retry"
    if worker_state == "uncertain" or effect_status == "uncertain":
        return "uncertain_state_ready_for_recover"
    return "manual_inspection_required"



def suggest_recent_task_next_blocker(
    next_action: str,
    next_reason: str,
) -> str:
    if next_reason == "lease_still_active":
        return "active_lease"
    if next_reason in {"executed_assumed_requires_reconcile", "scope_quarantined_by_peer", "scope_quarantined"}:
        return "scope_quarantine"
    if next_action == "inspect":
        return "manual_review_needed"
    return "none"



def suggest_recent_task_permission_tier(requires_write: bool) -> str:
    return "TIER_1" if requires_write else "TIER_0"



def suggest_recent_task_permission_policy(
    target_scope: str,
    requires_write: bool,
    doctor_bypass: bool,
) -> str:
    if doctor_bypass:
        return "allow"
    if not target_scope:
        return "deny"
    if requires_write:
        return "confirm"
    return "allow"



def suggest_recent_task_permission_reason(
    target_scope: str,
    requires_write: bool,
    doctor_bypass: bool,
) -> str:
    if doctor_bypass:
        return "doctor_bypass_privileged_context"
    if not target_scope:
        return "missing_scope_defaults_deny"
    if requires_write:
        return "write_scope_requires_confirmation"
    return "read_scope_allowed"



def load_recent_tasks(db_path: Path, limit: int, *, heartbeat_interval_ms: int) -> list[dict[str, object]]:
    if not db_path.exists():
        return []

    now_ms = int(time.time() * 1000)
    items: list[dict[str, object]] = []
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT
                task_snapshots.task_id,
                task_snapshots.worker_state,
                task_snapshots.effect_status,
                task_snapshots.updated_at,
                COALESCE(
                    (
                        SELECT effect_id
                        FROM effects effect_view
                        WHERE effect_view.task_id = task_snapshots.task_id
                        ORDER BY rowid DESC
                        LIMIT 1
                    ),
                    ''
                ) AS effect_id,
                COALESCE(orchestrator_tasks.target_scope, '') AS target_scope,
                COALESCE(orchestrator_tasks.requires_write, 0) AS requires_write,
                COALESCE(orchestrator_tasks.doctor_bypass, 0) AS doctor_bypass,
                COALESCE(latest_lease.owner_id, '') AS lease_owner_id,
                latest_lease.fencing_token AS lease_fencing_token,
                latest_lease.expires_at_ms AS lease_expires_at_ms,
                latest_lease.released_at_ms AS lease_released_at_ms
            FROM task_snapshots
            LEFT JOIN orchestrator_tasks
              ON orchestrator_tasks.task_id = task_snapshots.task_id
            LEFT JOIN orchestrator_leases AS latest_lease
              ON latest_lease.lease_id = (
                  SELECT lease_view.lease_id
                  FROM orchestrator_leases AS lease_view
                  WHERE lease_view.task_id = task_snapshots.task_id
                  ORDER BY lease_view.fencing_token DESC, lease_view.rowid DESC
                  LIMIT 1
              )
            ORDER BY task_snapshots.updated_at DESC, task_snapshots.task_id DESC
            LIMIT ?1
            """,
            (limit,),
        ).fetchall()

        for row in rows:
            lease_state = classify_orchestrator_lease_state(
                None if row[10] is None else int(row[10]),
                None if row[11] is None else int(row[11]),
                now_ms,
            )
            lease_expires_at_ms = None if row[10] is None else int(row[10])
            lease_released_at_ms = None if row[11] is None else int(row[11])
            target_scope = str(row[5] or '')
            requires_write = bool(row[6])
            doctor_bypass = bool(row[7])
            lease_age_ms = compute_timestamp_age_ms(row[3], now_ms)
            lease_freshness = (
                "none"
                if lease_state == "none"
                else classify_heartbeat_freshness(lease_age_ms, heartbeat_interval_ms)
            )
            item = {
                "task_id": row[0],
                "worker_state": row[1],
                "effect_status": row[2],
                "updated_at": row[3],
                "effect_id": row[4] or f"effect-{row[0]}",
                **build_permission_decision_payload(target_scope, requires_write, doctor_bypass),
                "lease_owner_id": row[8] or '',
                "lease_fencing_token": None if row[9] is None else int(row[9]),
                "lease_expires_at_ms": lease_expires_at_ms,
                "lease_released_at_ms": lease_released_at_ms,
                "lease_state": lease_state,
                "lease_age_ms": lease_age_ms,
                "lease_freshness": lease_freshness,
                "lease_remaining_ms": compute_orchestrator_lease_remaining_ms(
                    lease_expires_at_ms,
                    lease_released_at_ms,
                    now_ms,
                ),
                **load_recent_task_scope_peer_facts(
                    connection,
                    target_scope,
                    str(row[0] or ''),
                    str(row[2] or ''),
                    now_ms=now_ms,
                ),
            }
            scope_quarantine_blocked = bool(
                item["scope_quarantine_active"] and requires_write and not doctor_bypass
            )
            next_action = suggest_recent_task_next_action(
                str(row[1]),
                str(row[2]),
                lease_state,
                scope_quarantine_blocked=scope_quarantine_blocked,
            )
            next_reason = suggest_recent_task_next_reason(
                str(row[1]),
                str(row[2]),
                lease_state,
                scope_quarantine_blocked=scope_quarantine_blocked,
                scope_quarantine_source=str(item["scope_quarantine_source"]),
            )
            item.update(
                {
                    "next_action": next_action,
                    "next_reason": next_reason,
                    "next_blocker": suggest_recent_task_next_blocker(next_action, next_reason),
                }
            )
            item.update(build_service_status_coordination_payload(item))
            items.append(item)
    return items


def load_service_queue_counts(db_path: Path) -> dict[str, int]:
    counts = {"queued": 0, "active": 0, "expired": 0, "completed": 0}
    if not db_path.exists():
        return counts

    now_ms = int(time.time() * 1000)
    with sqlite3.connect(db_path) as connection:
        counts["queued"] = int(
            connection.execute(
                """
                SELECT COUNT(*)
                FROM orchestrator_tasks task_view
                WHERE task_view.is_completed = 0
                  AND NOT EXISTS (
                      SELECT 1
                      FROM orchestrator_leases lease_view
                      WHERE lease_view.task_id = task_view.task_id
                        AND lease_view.released_at_ms IS NULL
                  )
                """
            ).fetchone()[0]
        )
        counts["active"] = int(
            connection.execute(
                """
                SELECT COUNT(DISTINCT task_id)
                FROM orchestrator_leases
                WHERE released_at_ms IS NULL
                  AND expires_at_ms > ?1
                """,
                (now_ms,),
            ).fetchone()[0]
        )
        counts["expired"] = int(
            connection.execute(
                """
                SELECT COUNT(DISTINCT task_id)
                FROM orchestrator_leases
                WHERE released_at_ms IS NULL
                  AND expires_at_ms <= ?1
                """,
                (now_ms,),
            ).fetchone()[0]
        )
        counts["completed"] = int(
            connection.execute(
                "SELECT COUNT(*) FROM orchestrator_tasks WHERE is_completed = 1"
            ).fetchone()[0]
        )
    return counts



def load_task_snapshot_counts(db_path: Path, field: str) -> dict[str, int]:
    if not db_path.exists():
        return {}

    select_field = field
    if field == "probe_state":
        select_field = "COALESCE(probe_state, 'none')"

    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            f"SELECT {select_field} AS label, COUNT(*) FROM task_snapshots GROUP BY label ORDER BY label",
        ).fetchall()
    return {str(row[0]): int(row[1]) for row in rows if row[0] is not None}



def render_count_summary(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in counts.items())


def lookup_task_entry(db_path: Path, task_id: str) -> dict[str, str] | None:
    if not db_path.exists():
        return None

    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT
                task_id,
                worker_state,
                effect_status,
                updated_at,
                COALESCE(
                    (
                        SELECT effect_id
                        FROM effects effect_view
                        WHERE effect_view.task_id = task_snapshots.task_id
                        ORDER BY rowid DESC
                        LIMIT 1
                    ),
                    ''
                ) AS effect_id
            FROM task_snapshots
            WHERE task_id = ?1
            LIMIT 1
            """,
            (task_id,),
        ).fetchone()
    if row is None:
        return None
    return {
        "task_id": row[0],
        "worker_state": row[1],
        "effect_status": row[2],
        "updated_at": row[3],
        "effect_id": row[4] or f"effect-{row[0]}",
    }


def lookup_latest_effect_id(db_path: Path, task_id: str) -> str | None:
    if not db_path.exists():
        return None

    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT effect_id FROM effects WHERE task_id = ?1 ORDER BY rowid DESC LIMIT 1",
            (task_id,),
        ).fetchone()
    return None if row is None else str(row[0])


def find_output_line(output: str, prefix: str) -> str:
    for line in output.splitlines():
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    raise ValueError(f"missing expected output line: {prefix}")



def parse_counter_fields(raw: str) -> dict[str, int]:
    parsed: dict[str, int] = {}
    for token in raw.split():
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        parsed[key] = int(value.rstrip(","))
    if not parsed:
        raise ValueError(f"missing counter fields: {raw}")
    return parsed



def parse_task_csv(raw: str) -> list[str]:
    return [item for item in raw.split(",") if item]



def build_service_demo_result_payload(output: str) -> dict[str, object]:
    captured_output = output.strip()
    return {
        "example": "worker_service_governance_demo",
        "resolved_run": parse_counter_fields(
            find_output_line(output, "[demo] service run resolved => ")
        ),
        "resolved_governance": parse_counter_fields(
            find_output_line(output, "[demo] service governance resolved => ")
        ),
        "resolved_tasks": parse_task_csv(
            find_output_line(output, "[demo] service governance resolved tasks => ")
        ),
        "resolved_snapshot": parse_counter_fields(
            find_output_line(output, "[demo] snapshot after-resolved => ")
        ),
        "confirmation_run": parse_counter_fields(
            find_output_line(output, "[demo] service run confirmation => ")
        ),
        "confirmation_governance": parse_counter_fields(
            find_output_line(output, "[demo] service governance confirmation => ")
        ),
        "confirmation_tasks": parse_task_csv(
            find_output_line(output, "[demo] service governance confirmation tasks => ")
        ),
        "confirmation_snapshot": parse_counter_fields(
            find_output_line(output, "[demo] snapshot after-confirmation => ")
        ),
        "db_path": find_output_line(output, "[demo] db: "),
        "captured_output": captured_output,
    }



def run_sqlite_example_capture(
    example: str,
    example_args: list[str] | None = None,
    action: str | None = None,
    replay_output: bool = False,
) -> tuple[int, str]:
    env, cargo_exe, _ = build_rust_env()
    action_name = action or example
    if cargo_exe is None:
        message = "cargo executable not found; checked PATH and ~/.cargo/bin"
        if replay_output:
            print(f"[mvp-wrapper] cargo => error action={action_name} error={message}", file=sys.stderr)
        return 1, message

    command = [
        cargo_exe,
        f"+{TOOLCHAIN}",
        "run",
        "-p",
        "safeclaw-sqlite",
        "--example",
        example,
        "--quiet",
    ]
    if example_args:
        command.extend(["--", *example_args])

    try:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        message = str(error)
        if replay_output:
            print(f"[mvp-wrapper] cargo => error action={action_name} error={message}", file=sys.stderr)
        return 1, message

    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    combined_output = stdout + stderr
    if replay_output:
        if stdout:
            print(stdout, end="")
        if stderr:
            print(stderr, end="", file=sys.stderr)
        if completed.returncode != 0:
            print(f"[mvp-wrapper] cargo => failed action={action_name} exit={completed.returncode}", file=sys.stderr)
    return completed.returncode, combined_output


def run_cargo(args: list[str], action: str | None = None) -> int:
    exit_code, _ = run_cargo_capture(args, action=action, replay_output=True)
    return exit_code


def run_cargo_capture(
    args: list[str],
    action: str | None = None,
    replay_output: bool = False,
) -> tuple[int, str]:
    return run_sqlite_example_capture(
        "safeclaw_mvp_entry",
        example_args=args,
        action=action or (args[0] if args else "unknown"),
        replay_output=replay_output,
    )


def probe_command(
    command: list[str] | None,
    env: dict[str, str] | None = None,
    missing_detail: str | None = None,
) -> tuple[bool, str]:
    if not command:
        return False, missing_detail or "missing command"
    try:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, str(error)

    combined = ((completed.stdout or "") + (completed.stderr or "")).strip()
    detail = combined.splitlines()[0] if combined else f"exit={completed.returncode}"
    return completed.returncode == 0, detail


def resolve_repo_path(path_str: str) -> Path:
    path = Path(path_str)
    return path if path.is_absolute() else REPO_ROOT / path


def render_repo_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def default_output_for_db(db_arg: str) -> str:
    return render_repo_path(resolve_repo_path(db_arg).parent / "output.txt")


def get_flag(args: list[str], flag: str) -> str | None:
    try:
        index = args.index(flag)
    except ValueError:
        return None
    if index + 1 >= len(args):
        return None
    return args[index + 1]


def require_flag(args: list[str], flag: str) -> str:
    value = get_flag(args, flag)
    if value is None:
        raise ValueError(f"missing required flag after preparation: {flag}")
    return value


def ensure_flag(args: list[str], flag: str, value: str) -> None:
    if get_flag(args, flag) is None:
        args.extend([flag, value])


def has_flag(args: list[str], flag: str) -> bool:
    return flag in args


def validate_local_action_args(action: str, args: list[str]) -> str | None:
    return validate_flag_args(args, LOCAL_ACTION_FLAG_SPECS[action])


def validate_session_action_args(action: str, args: list[str]) -> str | None:
    return validate_flag_args(args, SESSION_ACTION_FLAG_SPECS[action])


def validate_flag_args(args: list[str], spec: dict[str, set[str]]) -> str | None:
    index = 0
    while index < len(args):
        token = args[index]
        if token in spec["boolean"]:
            index += 1
            continue
        if token in spec["value"]:
            if index + 1 >= len(args) or looks_like_flag(args[index + 1]):
                return f"missing value after {token}"
            index += 2
            continue
        return f"unknown argument: {token}"
    return None


def looks_like_flag(token: str) -> bool:
    return token.startswith("--")


def emit_local_action_error(
    action: str,
    args: list[str],
    message: str,
    exit_code: int = 1,
    text_message: str | None = None,
) -> int:
    if has_flag(args, "--json"):
        return emit_json_error(action, message, exit_code=exit_code)
    print(text_message or f"[mvp-wrapper] {action} => error {message}", file=sys.stderr)
    return exit_code


def run_sequence_json(
    name: str,
    steps: list[list[str]],
    preflight_payload: dict[str, object] | None = None,
) -> int:
    step_results: list[dict[str, object]] = []
    if preflight_payload is not None:
        step_results.append(build_preflight_step_result(preflight_payload))
        if not bool(preflight_payload.get("allowed")):
            details = build_preflight_blocked_details(preflight_payload, step_results)
            return emit_json_error(name, "failed step=preflight", exit_code=1, code="preflight-blocked", details=details)
    for step in steps:
        try:
            result = execute_session_action_capture(step)
        except ValueError as error:
            step_results.append({"action": step[0], "ok": False, "exit_code": 2})
            details = build_remembered_session_details(
                failed_step=step[0],
                steps=step_results,
                error_message=str(error),
            )
            if str(error).startswith("missing task context"):
                details["code"] = "missing-task-context"
            else:
                details["code"] = "invalid-argument"
            return emit_json_error(name, f"failed step={step[0]}", exit_code=2, details=details)
        step_results.append(
            {
                "action": result["action"],
                "ok": result["exit_code"] == 0,
                "exit_code": result["exit_code"],
                "source_hints": result["source_hints"],
            }
        )
        if result["exit_code"] != 0:
            return emit_json_error(
                name,
                f"failed step={result['action']}",
                exit_code=int(result["exit_code"]),
                details=build_remembered_session_details(
                    failed_step=result["action"],
                    steps=step_results,
                    captured_output=str(result["output"]).strip(),
                ),
            )
    payload = build_combo_result_payload(step_results)
    if preflight_payload is not None:
        payload["preflight"] = preflight_payload
    return emit_json_result(name, payload)


def emit_json_result(action: str, result: object, exit_code: int = 0) -> int:
    payload = {
        "ok": exit_code == 0,
        "action": action,
        "schema_version": "mvp-wrapper.v1",
        "result": result,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return exit_code


def emit_json_error(
    action: str,
    message: str,
    exit_code: int = 1,
    details: object | None = None,
    code: str | None = None,
) -> int:
    error_payload: dict[str, object] = {"message": message, "exit_code": exit_code}
    error_code = str(code or "").strip()
    if error_code:
        error_payload["code"] = error_code
    if details is not None:
        error_payload["details"] = details
    payload = {
        "ok": False,
        "action": action,
        "schema_version": "mvp-wrapper.v1",
        "error": error_payload,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
