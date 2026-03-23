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
LOCAL_ACTIONS = {"session", "sessions"}


def main(argv: list[str]) -> int:
    raw_args = argv[1:]
    if not raw_args or raw_args[0] in {"-h", "--help"}:
        return run_cargo(["--help"])

    action = raw_args[0]
    if action == "session":
        return print_session()
    if action == "sessions":
        return print_sessions(raw_args[1:])
    if action not in SESSION_ACTIONS:
        return run_cargo(raw_args)

    session = load_session()
    prepared = prepare_args(action, raw_args, session)
    exit_code = run_cargo(prepared)
    if exit_code == 0 and action in WRITES_SESSION:
        save_session(build_session(prepared))
    return exit_code


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


def print_session() -> int:
    session = load_session()
    if session is None:
        print("[mvp-wrapper] session => none")
        return 0
    print(
        "[mvp-wrapper] session => "
        f"task={session['task_id']} effect={session['effect_id']} db={session['db']} "
        f"output={session['output']} owner={session['owner_id']}"
    )
    return 0


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
    print(f"[mvp-wrapper] sessions => db={db} limit={limit}")
    if session is not None:
        current = "true" if session.get("db") == db else "false"
        print(
            "[mvp-wrapper] current => "
            f"task={session['task_id']} effect={session['effect_id']} current_db={current}"
        )

    rows = load_recent_tasks(db_path, limit)
    if not rows:
        print("[mvp-wrapper] recent => empty")
        return 0

    for index, row in enumerate(rows):
        current = (
            session is not None
            and session.get("db") == db
            and session.get("task_id") == row["task_id"]
        )
        print(
            f"[mvp-wrapper] recent[{index}] => "
            f"task={row['task_id']} effect={row['effect_id']} worker={row['worker_state']} "
            f"effect_status={row['effect_status']} updated_at={row['updated_at']} current={str(current).lower()}"
        )
    return 0


def load_session() -> dict[str, str] | None:
    if not SESSION_FILE.exists():
        return None
    return json.loads(SESSION_FILE.read_text(encoding="utf-8"))


def save_session(session: dict[str, str]) -> None:
    STATE_ROOT.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(json.dumps(session, indent=2, ensure_ascii=False), encoding="utf-8")


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


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
