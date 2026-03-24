from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_ROOT = REPO_ROOT / "target" / "mvp"
SESSION_FILE = STATE_ROOT / "last_session.json"
DEFAULT_DB = STATE_ROOT / "session.db"
DEFAULT_OUTPUT = STATE_ROOT / "output.txt"
DEFAULT_OWNER_ID = "safeclaw-mvp"
DEFAULT_LIST_LIMIT = 5
TOOLCHAIN = "stable-x86_64-pc-windows-gnu"
LINKER = (
    r"C:\Users\tianduan999\AppData\Local\Microsoft\WinGet\Packages\BrechtSanders."
    r"WinLibs.POSIX.UCRT_Microsoft.Winget.Source_8wekyb3d8bbwe\mingw64\bin\x86_64-w64-mingw32-gcc.exe"
)
SESSION_ACTIONS = {"run", "report", "status", "seed-crash", "recover", "seed-failed", "retry"}
WRITES_SESSION = {"run", "seed-crash", "seed-failed"}
READS_SESSION = {"report", "status", "recover", "retry"}
TASK_CONTEXT_ACTIONS = {"report", "recover", "retry"}
LOCAL_ACTIONS = ("demo", "recover-demo", "retry-demo", "session", "sessions", "use", "forget", "doctor")
SESSION_FIELDS = ("task_id", "effect_id", "db", "output", "owner_id")
LOCAL_ACTION_FLAG_SPECS = {
    "session": {"value": set(), "boolean": {"--json"}},
    "sessions": {"value": {"--db", "--limit"}, "boolean": {"--json"}},
    "use": {
        "value": {"--db", "--task-id", "--index", "--output", "--owner-id", "--effect-id"},
        "boolean": {"--json"},
    },
    "forget": {"value": set(), "boolean": {"--json"}},
    "doctor": {"value": {"--db", "--output"}, "boolean": {"--json"}},
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
        "value": {"--db", "--output", "--content", "--task-id", "--owner-id", "--effect-id"},
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
}


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
    if action == "doctor":
        return dispatch_local_action("doctor", raw_args[1:], run_doctor)
    if action == "demo":
        return run_demo(raw_args[1:])
    if action == "recover-demo":
        return run_recover_demo(raw_args[1:])
    if action == "retry-demo":
        return run_retry_demo(raw_args[1:])
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


def run_demo(args: list[str]) -> int:
    json_mode = has_flag(args, "--json")
    shared_args = [item for item in args if item not in {"--reset", "--json"}]
    return run_sequence(
        "demo",
        [
            ["run", "--reset", *shared_args],
            ["status", *shared_args],
            ["report", *shared_args],
        ],
        json_mode=json_mode,
    )


def run_recover_demo(args: list[str]) -> int:
    json_mode = has_flag(args, "--json")
    shared_args = [item for item in args if item not in {"--reset", "--json"}]
    return run_sequence(
        "recover-demo",
        [
            ["seed-crash", "--reset", *shared_args],
            ["recover", *shared_args],
            ["report", *shared_args],
        ],
        json_mode=json_mode,
    )


def run_retry_demo(args: list[str]) -> int:
    json_mode = has_flag(args, "--json")
    shared_args = [item for item in args if item not in {"--reset", "--json"}]
    return run_sequence(
        "retry-demo",
        [
            ["seed-failed", "--reset", *shared_args],
            ["retry", *shared_args],
            ["report", *shared_args],
        ],
        json_mode=json_mode,
    )


def run_sequence(name: str, steps: list[list[str]], json_mode: bool = False) -> int:
    if json_mode:
        return run_sequence_json(name, steps)
    for step in steps:
        print(f"[mvp-wrapper] {name} => {step[0]}")
        exit_code = execute_session_action(step)
        if exit_code != 0:
            print(f"[mvp-wrapper] {name} => failed step={step[0]} exit={exit_code}", file=sys.stderr)
            return exit_code
    return 0


def prepare_args(action: str, args: list[str], session: dict[str, str] | None) -> list[str]:
    prepared = list(args)
    validation_error = validate_session_action_args(action, prepared[1:])
    if validation_error is not None:
        raise ValueError(validation_error)
    if action in WRITES_SESSION:
        db = get_flag(prepared, "--db") or render_repo_path(DEFAULT_DB)
        ensure_flag(prepared, "--db", db)
        ensure_flag(prepared, "--output", get_flag(prepared, "--output") or default_output_for_db(db))
        task_id = get_flag(prepared, "--task-id") or f"task-safeclaw-mvp-{int(time.time() * 1000)}"
        ensure_flag(prepared, "--task-id", task_id)
        ensure_flag(prepared, "--effect-id", get_flag(prepared, "--effect-id") or f"effect-{task_id}")
        ensure_flag(prepared, "--owner-id", get_flag(prepared, "--owner-id") or DEFAULT_OWNER_ID)
        return prepared

    db = get_flag(prepared, "--db") or (session["db"] if session is not None else render_repo_path(DEFAULT_DB))
    ensure_flag(prepared, "--db", db)

    session_matches_db = matches_session_db(session, db)
    default_output = session["output"] if session_matches_db else default_output_for_db(db)
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
    prepared_db = get_flag(prepared, "--db") or render_repo_path(DEFAULT_DB)
    session_matches_db = matches_session_db(session, prepared_db)

    db_source = resolve_source_hint(
        get_flag(original_args, "--db") is not None,
        is_write_action=action in WRITES_SESSION,
        session_available=session is not None,
    )

    output_source = resolve_source_hint(
        get_flag(original_args, "--output") is not None,
        is_write_action=action in WRITES_SESSION,
        session_available=session_matches_db,
    )

    owner_id_source = resolve_source_hint(
        get_flag(original_args, "--owner-id") is not None,
        is_write_action=action in WRITES_SESSION,
        session_available=session_matches_db,
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


def build_session_action_result_payload(result: dict[str, object]) -> dict[str, object]:
    return {
        "prepared": result["prepared"],
        "captured_output": str(result["output"]),
        "saved_session": result["saved_session"],
        "remembered_session": load_session(),
        "source_hints": result["source_hints"],
    }


def resolve_db_selection(args: list[str], session: dict[str, str] | None) -> tuple[str, str]:
    db_flag = get_flag(args, "--db")
    if db_flag is not None:
        return db_flag, "flag"
    if session is not None:
        return session["db"], "session"
    return render_repo_path(DEFAULT_DB), "default"


def resolve_output_selection(
    args: list[str],
    session: dict[str, str] | None,
    db: str,
) -> tuple[str, str]:
    output_flag = get_flag(args, "--output")
    if output_flag is not None:
        return output_flag, "flag"
    if matches_session_db(session, db):
        return session["output"], "session"
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
) -> str:
    if flag_present:
        return "flag"
    if is_write_action:
        return "default"
    if session_available:
        return "session"
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
    print("[mvp-wrapper] usage => tools\\mvp\\safeclaw_mvp.cmd <action> [flags]")
    print(f"[mvp-wrapper] local actions => {', '.join(LOCAL_ACTIONS)}")
    print(f"[mvp-wrapper] passthrough actions => {', '.join(sorted(SESSION_ACTIONS))}")
    print(
        "[mvp-wrapper] defaults => write actions auto-fill --db/--output/--task-id/--effect-id/--owner-id, "
        "read actions reuse the remembered session when possible"
    )
    print(
        "[mvp-wrapper] examples => "
        "demo | recover-demo | retry-demo | session | sessions --limit 5 | use --index 0 | forget | doctor"
    )
    print(
        "[mvp-wrapper] json => demo/recover-demo/retry-demo/run/report/status/"
        "seed-crash/recover/seed-failed/retry/session/sessions/use/forget/doctor 支持 --json，"
        "统一返回 {ok, action, schema_version, result|error} 信封"
    )
    print(
        "[mvp-wrapper] errors => invalid-argument / missing-task-context；"
        "组合动作 JSON 失败会额外附带 failed_step 与 error_message"
    )
    print(
        "[mvp-wrapper] session => session/sessions/use/forget 管理 remembered session；"
        "status/report/recover/retry/doctor 会尽量复用它"
    )
    print(
        "[mvp-wrapper] doctor => 文本模式给出 summary 与 db/output 来源；"
        "--json 会额外返回 status 与 failing_checks"
    )
    print(
        "[mvp-wrapper] source hints => status/report/recover/retry --json 会额外返回 result.source_hints；"
        "可直接看到 db/output/owner_id/task_context 来源"
    )
    print(
        "[mvp-wrapper] combo source hints => demo/recover-demo/retry-demo --json 的 result.steps[*] / error.details.steps[*] 也会带 source_hints"
    )
    print(
        "[mvp-wrapper] combo session => demo/recover-demo/retry-demo --json 会返回 result.remembered_session；"
        "result.session 仅作兼容别名，脚本应优先读取 remembered_session"
    )
    print(
        "[mvp-wrapper] session selectors => status 可显式传 --task-id；"
        "use 支持 --index / --task-id 选择历史会话"
    )
    print(
        "[mvp-wrapper] session sources => sessions --json 会返回 current_session/db_source；"
        "use --json 会返回 source/db_source/output_source/owner_id_source"
    )
    print(
        "[mvp-wrapper] session paths => session 文本输出会带 remembered session 文件路径；"
        "forget 文本/JSON 会显式给出 reason/path"
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


def run_doctor(args: list[str]) -> int:
    session = load_session()
    db, db_source = resolve_db_selection(args, session)
    output, output_source = resolve_output_selection(args, session, db)

    cargo_ok, cargo_detail = probe_command(["cargo", "--version"])
    toolchain_ok, toolchain_detail = probe_command(["rustc", f"+{TOOLCHAIN}", "--version"])
    linker_path = Path(LINKER)
    linker_ok = linker_path.exists()
    db_path = resolve_repo_path(db)
    output_path = resolve_repo_path(output)
    failing_checks = [
        name
        for name, ok in (("cargo", cargo_ok), ("toolchain", toolchain_ok), ("linker", linker_ok))
        if not ok
    ]
    doctor_status = "ready" if not failing_checks else "degraded"

    payload = {
        "repo": str(REPO_ROOT),
        "status": doctor_status,
        "failing_checks": failing_checks,
        "python": {"ok": True, "detail": sys.executable},
        "cargo": {"ok": cargo_ok, "detail": cargo_detail},
        "toolchain": {"ok": toolchain_ok, "detail": toolchain_detail},
        "linker": {"ok": linker_ok, "detail": render_repo_path(linker_path)},
        "session": session,
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
    print(f"[mvp-wrapper] doctor cargo => {'ok' if cargo_ok else 'error'} {cargo_detail}")
    print(f"[mvp-wrapper] doctor toolchain => {'ok' if toolchain_ok else 'error'} {toolchain_detail}")
    print(
        f"[mvp-wrapper] doctor linker => {'ok' if linker_ok else 'error'} {render_repo_path(linker_path)}"
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
    rows = load_recent_tasks(db_path, limit)
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
        rows = load_recent_tasks(db_path, max(index + 1, DEFAULT_LIST_LIMIT))
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


def load_recent_tasks(db_path: Path, limit: int) -> list[dict[str, str]]:
    if not db_path.exists():
        return []

    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
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
            ORDER BY updated_at DESC, task_id DESC
            LIMIT ?1
            """,
            (limit,),
        ).fetchall()

    return [
        {
            "task_id": row[0],
            "worker_state": row[1],
            "effect_status": row[2],
            "updated_at": row[3],
            "effect_id": row[4] or f"effect-{row[0]}",
        }
        for row in rows
    ]


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


def run_cargo(args: list[str], action: str | None = None) -> int:
    exit_code, _ = run_cargo_capture(args, action=action, replay_output=True)
    return exit_code


def run_cargo_capture(
    args: list[str],
    action: str | None = None,
    replay_output: bool = False,
) -> tuple[int, str]:
    env = os.environ.copy()
    env["RUSTUP_TOOLCHAIN"] = TOOLCHAIN
    env["CARGO_TARGET_X86_64_PC_WINDOWS_GNU_LINKER"] = LINKER
    action_name = action or (args[0] if args else "unknown")
    try:
        completed = subprocess.run(
            [
                "cargo",
                f"+{TOOLCHAIN}",
                "run",
                "-p",
                "safeclaw-sqlite",
                "--example",
                "safeclaw_mvp_entry",
                "--quiet",
                "--",
                *args,
            ],
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


def probe_command(command: list[str]) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
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


def run_sequence_json(name: str, steps: list[list[str]]) -> int:
    step_results: list[dict[str, object]] = []
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
    return emit_json_result(name, build_combo_result_payload(step_results))


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
) -> int:
    error_payload: dict[str, object] = {"message": message, "exit_code": exit_code}
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









