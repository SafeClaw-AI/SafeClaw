from __future__ import annotations

import json
import os
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
TOOLCHAIN = "stable-x86_64-pc-windows-gnu"
LINKER = (
    r"C:\Users\tianduan999\AppData\Local\Microsoft\WinGet\Packages\BrechtSanders."
    r"WinLibs.POSIX.UCRT_Microsoft.Winget.Source_8wekyb3d8bbwe\mingw64\bin\x86_64-w64-mingw32-gcc.exe"
)
SESSION_ACTIONS = {"run", "report", "status", "seed-crash", "recover", "seed-failed", "retry"}
WRITES_SESSION = {"run", "seed-crash", "seed-failed"}
READS_SESSION = {"report", "status", "recover", "retry"}


def main(argv: list[str]) -> int:
    raw_args = argv[1:]
    if not raw_args or raw_args[0] in {"-h", "--help"}:
        return run_cargo(["--help"])

    action = raw_args[0]
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
        ensure_flag(prepared, "--db", render_repo_path(DEFAULT_DB))
        ensure_flag(prepared, "--output", render_repo_path(DEFAULT_OUTPUT))
        task_id = get_flag(prepared, "--task-id") or f"task-safeclaw-mvp-{int(time.time() * 1000)}"
        ensure_flag(prepared, "--task-id", task_id)
        ensure_flag(prepared, "--effect-id", f"effect-{task_id}")
        ensure_flag(prepared, "--owner-id", DEFAULT_OWNER_ID)
        return prepared

    if action in READS_SESSION and session is not None:
        if action != "status":
            ensure_flag(prepared, "--task-id", session["task_id"])
        ensure_flag(prepared, "--db", session["db"])
        ensure_flag(prepared, "--output", session["output"])
        ensure_flag(prepared, "--effect-id", session["effect_id"])
        ensure_flag(prepared, "--owner-id", session["owner_id"])

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


def load_session() -> dict[str, str] | None:
    if not SESSION_FILE.exists():
        return None
    return json.loads(SESSION_FILE.read_text(encoding="utf-8"))


def save_session(session: dict[str, str]) -> None:
    STATE_ROOT.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(json.dumps(session, indent=2, ensure_ascii=False), encoding="utf-8")


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


def render_repo_path(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


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
