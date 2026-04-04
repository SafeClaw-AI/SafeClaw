from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON = sys.executable
LEDGER_POLICY_CHECKS: list[tuple[str, str]] = [
    ("Ledger index manifest", "tools/checks/ledger_index_manifest.py"),
    ("Ledger alignment", "tools/checks/check_ledger_alignment.py"),
    ("Cross-file consistency", "tools/checks/check_consistency.py"),
    ("Version consistency", "tools/checks/check_versions.py"),
    ("Structure completeness", "tools/checks/check_structure.py"),
    ("Scaffold layout", "tools/checks/check_scaffold.py"),
    ("Public docs alignment", "tools/checks/check_public_docs.py"),
]
CONTRACT_TESTS_CHECK_NAME = "Contract tests"
CONTRACT_TESTS_COMMAND = [
    PYTHON,
    "-W",
    "ignore::DeprecationWarning",
    "-u",
    "-m",
    "unittest",
    "discover",
    "-s",
    "tests/contracts",
    "-p",
    "test_*.py",
]
TOOLING_SMOKE_CHECK_NAME = "Tooling smoke"
MVP_OPERATOR_FLOW_CHECK_NAME = "MVP operator flow"
TOOLING_SMOKE_COVERED_CHECKS: dict[str, tuple[str, ...]] = {
    TOOLING_SMOKE_CHECK_NAME: (MVP_OPERATOR_FLOW_CHECK_NAME,),
}
ASYNC_TAIL_START_CHECK_NAME = TOOLING_SMOKE_CHECK_NAME
SEQUENTIAL_CHECKS: list[tuple[str, list[str]]] = [
    *[(name, [PYTHON, "-u", script_path]) for name, script_path in LEDGER_POLICY_CHECKS],
    (
        "Reference redlines",
        [PYTHON, "-u", "tools/checks/check_reference_redlines.py"],
    ),
    (
        "Naming lint",
        [PYTHON, "-u", "tools/lint/check_naming.py"],
    ),
    (
        CONTRACT_TESTS_CHECK_NAME,
        CONTRACT_TESTS_COMMAND,
    ),
    (
        TOOLING_SMOKE_CHECK_NAME,
        [PYTHON, "-u", "tools/checks/check_tooling_smoke.py"],
    ),
]
ASYNC_TAIL_CHECKS: list[tuple[str, list[str]]] = [
    (
        "Example smoke",
        [PYTHON, "-u", "tools/checks/check_examples_smoke.py"],
    ),
    (
        "Generated sync",
        [PYTHON, "-u", "tools/checks/check_generated_sync.py"],
    ),
]
CHECKS: list[tuple[str, list[str]]] = [*SEQUENTIAL_CHECKS, *ASYNC_TAIL_CHECKS]
SUBPROCESS_ENV_OVERRIDES: dict[str, str] = {
    "PYTHONWARNINGS": "ignore::DeprecationWarning",
}


@dataclass
class RunningCheck:
    name: str
    command: list[str]
    process: subprocess.Popen[str]
    started_at: float


def build_check_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(SUBPROCESS_ENV_OVERRIDES)
    return env


def _format_duration(seconds: float) -> str:
    return f"{seconds:.2f}s"


def _emit_completed_check(
    name: str,
    completed: subprocess.CompletedProcess[str],
    duration_seconds: float,
) -> int:
    output = ((completed.stdout or "") + (completed.stderr or "")).rstrip()
    if output:
        print(output, flush=True)
    status = "OK" if completed.returncode == 0 else "FAIL"
    print(f"[{status} {_format_duration(duration_seconds)}] {name}", flush=True)
    return completed.returncode


def _run_check(name: str, command: list[str]) -> int:
    started_at = time.monotonic()
    print(f"==> {name}", flush=True)
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=build_check_env(),
    )
    duration_seconds = time.monotonic() - started_at
    return _emit_completed_check(name, completed, duration_seconds)


def _start_async_check(name: str, command: list[str]) -> RunningCheck:
    print(f"==> {name} (parallel tail)", flush=True)
    process = subprocess.Popen(
        command,
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=build_check_env(),
    )
    return RunningCheck(
        name=name,
        command=command,
        process=process,
        started_at=time.monotonic(),
    )


def _finish_async_check(running_check: RunningCheck) -> int:
    stdout, stderr = running_check.process.communicate()
    completed = subprocess.CompletedProcess(
        args=running_check.command,
        returncode=running_check.process.returncode or 0,
        stdout=stdout,
        stderr=stderr,
    )
    duration_seconds = time.monotonic() - running_check.started_at
    return _emit_completed_check(running_check.name, completed, duration_seconds)


def _terminate_async_checks(running_checks: list[RunningCheck]) -> None:
    for running_check in running_checks:
        if running_check.process.poll() is not None:
            continue
        running_check.process.terminate()
        try:
            running_check.process.wait(timeout=5)
        except subprocess.TimeoutExpired as error:
            print(
                f"[selfcheck] graceful terminate timed out for {running_check.name}: {error}",
                file=sys.stderr,
                flush=True,
            )
            running_check.process.kill()
            running_check.process.wait()


def main() -> int:
    running_async_checks: list[RunningCheck] = []
    try:
        for name, command in SEQUENTIAL_CHECKS:
            if name == ASYNC_TAIL_START_CHECK_NAME and not running_async_checks:
                running_async_checks = [
                    _start_async_check(async_name, async_command)
                    for async_name, async_command in ASYNC_TAIL_CHECKS
                ]
            exit_code = _run_check(name, command)
            if exit_code != 0:
                _terminate_async_checks(running_async_checks)
                return exit_code

        for running_check in running_async_checks:
            exit_code = _finish_async_check(running_check)
            if exit_code != 0:
                return exit_code
    finally:
        _terminate_async_checks(running_async_checks)

    print("All protocol checks passed.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
