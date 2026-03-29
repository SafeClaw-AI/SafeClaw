from __future__ import annotations

import os
import re
import sys
from contextlib import contextmanager
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_ROOT = REPO_ROOT / "target" / "mvp"
LOCK_FILE = STATE_ROOT / ".wrapper-check.lock"
LOCK_ENV = "SAFECLAW_MVP_CHECK_LOCK_HELD"
PID_PATTERN = re.compile(r"pid=(\d+)")


def _holder_pid(holder: str) -> int | None:
    match = PID_PATTERN.search(holder)
    if match is None:
        return None
    return int(match.group(1))


def _process_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


@contextmanager
def acquire_mvp_state_lock(check_name: str):
    if os.environ.get(LOCK_ENV):
        yield
        return
    STATE_ROOT.mkdir(parents=True, exist_ok=True)
    fd: int | None = None
    previous_env = os.environ.get(LOCK_ENV)
    while True:
        try:
            fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            holder = "unknown"
            holder_pid: int | None = None
            try:
                holder = LOCK_FILE.read_text(encoding="utf-8").strip() or holder
                holder_pid = _holder_pid(holder)
            except OSError as error:
                holder = f"{holder} unreadable={error.__class__.__name__}"
                holder_pid = None
            if holder_pid is not None and not _process_is_running(holder_pid):
                try:
                    LOCK_FILE.unlink(missing_ok=True)
                    continue
                except OSError as error:
                    raise RuntimeError(
                        f"failed to remove stale MVP state lock: {LOCK_FILE.relative_to(REPO_ROOT).as_posix()} error={error}"
                    ) from error
            raise RuntimeError(
                f"another MVP state check is already running; lock={LOCK_FILE.relative_to(REPO_ROOT).as_posix()} holder={holder}"
            )
    try:
        os.environ[LOCK_ENV] = check_name
        os.write(fd, f"{check_name} pid={os.getpid()}".encode("utf-8", errors="replace"))
        yield
    finally:
        if previous_env is None:
            os.environ.pop(LOCK_ENV, None)
        else:
            os.environ[LOCK_ENV] = previous_env
        if fd is not None:
            os.close(fd)
        try:
            LOCK_FILE.unlink(missing_ok=True)
        except OSError as error:
            print(
                f"[mvp-state-guard] failed to release lock {LOCK_FILE.relative_to(REPO_ROOT).as_posix()}: {error}",
                file=sys.stderr,
            )
