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
LOCAL_ACTIONS = ("demo", "recover-demo", "retry-demo", "session", "sessions", "use", "forget", "doctor")
SESSION_FIELDS = ("task_id", "effect_id", "db", "output", "owner_id")


def main(argv: list[str]) -> int:
    raw_args = argv[1:]
    if not raw_args:
        return print_help()

    action = raw_args[0]
    if action in {"-h", "--help", "help"}:
        return print_help()
    if action == "session":
        return print_session(raw_args[1:])
    if action == "sessions":
        return print_sessions(raw_args[1:])
    if action == "use":
        return activate_session(raw_args[1:])
    if action == "forget":
        return forget_session(raw_args[1:])
    if action == "doctor":
        return run_doctor(raw_args[1:])
    if action == "demo":
        return run_demo(raw_args[1:])
    if action == "recover-demo":
        return run_recover_demo(raw_args[1:])
    if action == "retry-demo":
        return run_retry_demo(raw_args[1:])
    if action not in SESSION_ACTIONS:
        return run_cargo(raw_args)

    return execute_session_action(raw_args)


def execute_session_action(args: list[str]) -> int:
    action = args[0]
    session = load_session()
    prepared = prepare_args(action, args, session)
    exit_code = run_cargo(prepared)
    if exit_code == 0 and action in WRITES_SESSION:
        save_session(build_session(prepared))
    return exit_code


def run_demo(args: list[str]) -> int:
    shared_args = [item for item in args if item != "--reset"]
    return run_sequence(
        "demo",
        [
            ["run", "--reset", *shared_args],
            ["status", *shared_args],
            ["report", *shared_args],
        ],
    )


def run_recover_demo(args: list[str]) -> int:
    shared_args = [item for item in args if item != "--reset"]
    return run_sequence(
        "recover-demo",
        [
            ["seed-crash", "--reset", *shared_args],
            ["recover", *shared_args],
            ["report", *shared_args],
        ],
    )


def run_retry_demo(args: list[str]) -> int:
    shared_args = [item for item in args if item != "--reset"]
    return run_sequence(
        "retry-demo",
        [
            ["seed-failed", "--reset", *shared_args],
            ["retry", *shared_args],
            ["report", *shared_args],
        ],
    )


def run_sequence(name: str, steps: list[list[str]]) -> int:
    for step in steps:
        print(f"[mvp-wrapper] {name} => {step[0]}")
        exit_code = execute_session_action(step)
        if exit_code != 0:
            return exit_code
    return 0


def prepare_args(action: str, args: list[str], session: dict[str, str] | None) -> list[str]:
    prepared = list(args)
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

    session_matches_db = session is not None and session.get("db") == db
    default_output = session["output"] if session_matches_db else default_output_for_db(db)
    ensure_flag(prepared, "--output", get_flag(prepared, "--output") or default_output)
    ensure_flag(
        prepared,
        "--owner-id",
        get_flag(prepared, "--owner-id") or (session["owner_id"] if session_matches_db else DEFAULT_OWNER_ID),
    )

    task_id = get_flag(prepared, "--task-id")
    if task_id is None and session_matches_db:
        task_id = session["task_id"]
        ensure_flag(prepared, "--task-id", task_id)

    effect_id = get_flag(prepared, "--effect-id")
    if effect_id is None and task_id is not None:
        resolved_effect = lookup_latest_effect_id(resolve_repo_path(db), task_id)
        if resolved_effect is None and session_matches_db and session["task_id"] == task_id:
            resolved_effect = session["effect_id"]
        ensure_flag(prepared, "--effect-id", resolved_effect or f"effect-{task_id}")

    return prepared


def build_session(args: list[str]) -> dict[str, str]:
    task_id = require_flag(args, "--task-id")
    return {
        "task_id": task_id,
        "effect_id": get_flag(args, "--effect-id") or f"effect-{task_id}",
        "db": require_flag(args, "--db"),
        "output": require_flag(args, "--output"),
        "owner_id": get_flag(args, "--owner-id") or DEFAULT_OWNER_ID,
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
    print("[mvp-wrapper] json => session/sessions/use/forget/doctor 支持 --json")
    return 0


def print_session(args: list[str]) -> int:
    session = load_session()
    if has_flag(args, "--json"):
        return emit_json(session)
    if session is None:
        print("[mvp-wrapper] session => none")
        return 0
    print(
        "[mvp-wrapper] session => "
        f"task={session['task_id']} effect={session['effect_id']} db={session['db']} "
        f"output={session['output']} owner={session['owner_id']}"
    )
    return 0


def forget_session(args: list[str]) -> int:
    if not SESSION_FILE.exists():
        if has_flag(args, "--json"):
            return emit_json({"forgot": False, "path": render_repo_path(SESSION_FILE), "reason": "none"})
        print("[mvp-wrapper] forgot => none")
        return 0
    try:
        SESSION_FILE.unlink()
    except OSError as error:
        print(f"[mvp-wrapper] forgot => error {error}", file=sys.stderr)
        return 1
    if has_flag(args, "--json"):
        return emit_json({"forgot": True, "path": render_repo_path(SESSION_FILE), "reason": "removed"})
    print(f"[mvp-wrapper] forgot => {render_repo_path(SESSION_FILE)}")
    return 0


def run_doctor(args: list[str]) -> int:
    session = load_session()
    db = get_flag(args, "--db") or (session["db"] if session is not None else render_repo_path(DEFAULT_DB))
    output = get_flag(args, "--output")
    if output is None:
        if session is not None and session.get("db") == db:
            output = session["output"]
        else:
            output = default_output_for_db(db)

    cargo_ok, cargo_detail = probe_command(["cargo", "--version"])
    toolchain_ok, toolchain_detail = probe_command(["rustc", f"+{TOOLCHAIN}", "--version"])
    linker_path = Path(LINKER)
    linker_ok = linker_path.exists()
    db_path = resolve_repo_path(db)
    output_path = resolve_repo_path(output)

    payload = {
        "repo": str(REPO_ROOT),
        "python": {"ok": True, "detail": sys.executable},
        "cargo": {"ok": cargo_ok, "detail": cargo_detail},
        "toolchain": {"ok": toolchain_ok, "detail": toolchain_detail},
        "linker": {"ok": linker_ok, "detail": render_repo_path(linker_path)},
        "session": session,
        "db": {"path": render_repo_path(db_path), "exists": db_path.exists()},
        "output": {"path": render_repo_path(output_path), "exists": output_path.exists()},
    }
    if has_flag(args, "--json"):
        return emit_json(payload, exit_code=0 if cargo_ok and toolchain_ok and linker_ok else 1)

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
    return 0 if cargo_ok and toolchain_ok and linker_ok else 1


def print_sessions(args: list[str]) -> int:
    db = get_flag(args, "--db") or (load_session() or {}).get("db") or render_repo_path(DEFAULT_DB)
    limit_raw = get_flag(args, "--limit") or str(DEFAULT_LIST_LIMIT)
    try:
        limit = max(1, int(limit_raw))
    except ValueError:
        print(f"[mvp-wrapper] invalid --limit: {limit_raw}", file=sys.stderr)
        return 2

    db_path = resolve_repo_path(db)
    session = load_session()
    rows = load_recent_tasks(db_path, limit)
    rows_with_current = [
        {
            **row,
            "current": (
                session is not None
                and session.get("db") == db
                and session.get("task_id") == row["task_id"]
            ),
        }
        for row in rows
    ]
    if has_flag(args, "--json"):
        return emit_json({"db": db, "limit": limit, "current_session": session, "rows": rows_with_current})

    print(f"[mvp-wrapper] sessions => db={db} limit={limit}")
    if session is not None:
        current = "true" if session.get("db") == db else "false"
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
    db = get_flag(args, "--db") or (session or {}).get("db") or render_repo_path(DEFAULT_DB)
    db_path = resolve_repo_path(db)

    task_id = get_flag(args, "--task-id")
    index_raw = get_flag(args, "--index")
    if task_id is not None and index_raw is not None:
        print("[mvp-wrapper] use requires either --task-id or --index, not both", file=sys.stderr)
        return 2

    if task_id is None:
        index_raw = index_raw or "0"
        try:
            index = int(index_raw)
        except ValueError:
            print(f"[mvp-wrapper] invalid --index: {index_raw}", file=sys.stderr)
            return 2
        if index < 0:
            print(f"[mvp-wrapper] invalid --index: {index_raw}", file=sys.stderr)
            return 2
        rows = load_recent_tasks(db_path, max(index + 1, DEFAULT_LIST_LIMIT))
        if index >= len(rows):
            print(f"[mvp-wrapper] no recent task at index {index} for db={db}", file=sys.stderr)
            return 2
        target = rows[index]
        source = f"index:{index}"
    else:
        target = lookup_task_entry(db_path, task_id)
        if target is None:
            print(f"[mvp-wrapper] missing task snapshot for task={task_id} db={db}", file=sys.stderr)
            return 2
        source = f"task:{task_id}"

    output = get_flag(args, "--output")
    if output is None:
        if session is not None and session.get("db") == db:
            output = session["output"]
        else:
            output = default_output_for_db(db)

    owner_id = get_flag(args, "--owner-id")
    if owner_id is None:
        if session is not None and session.get("db") == db:
            owner_id = session["owner_id"]
        else:
            owner_id = DEFAULT_OWNER_ID

    selected_session = {
        "task_id": target["task_id"],
        "effect_id": get_flag(args, "--effect-id") or target["effect_id"],
        "db": db,
        "output": output,
        "owner_id": owner_id,
        "source": source,
    }
    save_session({key: selected_session[key] for key in SESSION_FIELDS})
    if has_flag(args, "--json"):
        return emit_json(selected_session)
    print(
        "[mvp-wrapper] activated => "
        f"task={selected_session['task_id']} effect={selected_session['effect_id']} db={selected_session['db']} "
        f"output={selected_session['output']} owner={selected_session['owner_id']} source={source}"
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


def run_cargo(args: list[str]) -> int:
    env = os.environ.copy()
    env["RUSTUP_TOOLCHAIN"] = TOOLCHAIN
    env["CARGO_TARGET_X86_64_PC_WINDOWS_GNU_LINKER"] = LINKER
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
    )
    return completed.returncode


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


def emit_json(payload: object, exit_code: int = 0) -> int:
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
