"""Subprocess execution utilities for smoke tests."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from mvp_state_guard import _process_is_running

# Global state for smoke test progress tracking
_ORIGINAL_SUBPROCESS_MODULE = subprocess
_SMOKE_RUN_COUNTER = 0
_SMOKE_STARTED_AT = 0.0
_SMOKE_PARENT_PID = 0
_SMOKE_MONITOR_INTERVAL_SECONDS = 0.5


def reset_smoke_progress() -> None:
    """Reset smoke test progress counters."""
    global _SMOKE_PARENT_PID, _SMOKE_RUN_COUNTER, _SMOKE_STARTED_AT
    _SMOKE_RUN_COUNTER = 0
    _SMOKE_STARTED_AT = time.monotonic()
    _SMOKE_PARENT_PID = os.getppid()


def _smoke_parent_is_running() -> bool:
    """Check if the parent process is still running."""
    if _SMOKE_PARENT_PID <= 0:
        return True
    return _process_is_running(_SMOKE_PARENT_PID)


def _terminate_smoke_process(process: subprocess.Popen[str]) -> None:
    """Terminate a subprocess gracefully, then forcefully if needed."""
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=1.0)
    except _ORIGINAL_SUBPROCESS_MODULE.TimeoutExpired:
        process.kill()
        process.wait()


def format_smoke_command(command: object) -> str:
    """Format a command for display in smoke test output."""
    if not isinstance(command, (list, tuple)):
        return str(command)
    parts = [str(part) for part in command]
    return " ".join(parts)


def run_smoke_subprocess(
    command: object, *args: object, **kwargs: object
) -> subprocess.CompletedProcess[str]:
    """
    Run a subprocess with smoke test monitoring.

    This wrapper:
    - Tracks execution progress with sequence numbers
    - Monitors parent process liveness
    - Applies sitecustomize patches when needed
    - Logs start/completion with timing
    """
    global _SMOKE_RUN_COUNTER
    _SMOKE_RUN_COUNTER += 1
    sequence = _SMOKE_RUN_COUNTER
    started_at = time.monotonic()
    elapsed = started_at - _SMOKE_STARTED_AT if _SMOKE_STARTED_AT > 0 else 0.0

    popen_kwargs = dict(kwargs)

    # Import here to avoid circular dependency
    from smoke_utils.sitecustomize_factory import (
        should_use_smoke_demo_sitecustomize,
        should_use_smoke_wrapper_service_sitecustomize,
        should_use_smoke_wrapper_report_sitecustomize,
        should_use_smoke_wrapper_service_report_sitecustomize,
        should_use_smoke_root_ps1_service_report_sitecustomize,
        build_smoke_demo_pythonpath_env,
        build_smoke_report_pythonpath_env,
    )

    if should_use_smoke_demo_sitecustomize(
        command
    ) or should_use_smoke_wrapper_service_sitecustomize(command):
        popen_kwargs["env"] = build_smoke_demo_pythonpath_env(
            base_env=popen_kwargs.get("env"),
        )
    elif (
        should_use_smoke_wrapper_report_sitecustomize(command)
        or should_use_smoke_wrapper_service_report_sitecustomize(command)
        or should_use_smoke_root_ps1_service_report_sitecustomize(command)
    ):
        popen_kwargs["env"] = build_smoke_report_pythonpath_env(
            base_env=popen_kwargs.get("env"),
        )

    capture_output = bool(popen_kwargs.pop("capture_output", False))
    input_data = popen_kwargs.pop("input", None)
    check = bool(popen_kwargs.pop("check", False))
    timeout = popen_kwargs.pop("timeout", None)

    if capture_output:
        if "stdout" in popen_kwargs or "stderr" in popen_kwargs:
            raise ValueError(
                "stdout and stderr arguments may not be used with capture_output"
            )
        popen_kwargs["stdout"] = _ORIGINAL_SUBPROCESS_MODULE.PIPE
        popen_kwargs["stderr"] = _ORIGINAL_SUBPROCESS_MODULE.PIPE

    if input_data is not None:
        if "stdin" in popen_kwargs:
            raise ValueError("stdin and input arguments may not both be used.")
        popen_kwargs["stdin"] = _ORIGINAL_SUBPROCESS_MODULE.PIPE

    print(
        f"[tooling-smoke {sequence:03d}] start +{elapsed:.1f}s => {format_smoke_command(command)}",
        flush=True,
    )

    process = _ORIGINAL_SUBPROCESS_MODULE.Popen(command, *args, **popen_kwargs)
    deadline = None if timeout is None else started_at + float(timeout)
    stdout = None
    stderr = None

    try:
        while True:
            wait_timeout = _SMOKE_MONITOR_INTERVAL_SECONDS
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise _ORIGINAL_SUBPROCESS_MODULE.TimeoutExpired(command, timeout)
                wait_timeout = min(wait_timeout, remaining)
            try:
                stdout, stderr = process.communicate(
                    input=input_data, timeout=wait_timeout
                )
                input_data = None
                break
            except _ORIGINAL_SUBPROCESS_MODULE.TimeoutExpired:
                input_data = None
                if not _smoke_parent_is_running():
                    raise RuntimeError(
                        f"tooling smoke parent exited while running {format_smoke_command(command)}"
                    )
                continue
    except BaseException as error:
        _terminate_smoke_process(process)
        if isinstance(error, KeyboardInterrupt):
            raise
        raise

    completed = _ORIGINAL_SUBPROCESS_MODULE.CompletedProcess(
        args=command,
        returncode=process.returncode or 0,
        stdout=stdout,
        stderr=stderr,
    )

    duration = time.monotonic() - started_at
    print(
        f"[tooling-smoke {sequence:03d}] done exit={completed.returncode} duration={duration:.1f}s",
        flush=True,
    )

    if check and completed.returncode != 0:
        raise _ORIGINAL_SUBPROCESS_MODULE.CalledProcessError(
            completed.returncode,
            command,
            output=completed.stdout,
            stderr=completed.stderr,
        )

    return completed


class _TracingSubprocessModule:
    """Wrapper that intercepts subprocess.run() calls for smoke testing."""

    def __init__(self, delegate: object) -> None:
        self._delegate = delegate

    def run(
        self, command: object, *args: object, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        return run_smoke_subprocess(command, *args, **kwargs)

    def __getattr__(self, name: str) -> object:
        return getattr(self._delegate, name)


def get_tracing_subprocess_module() -> _TracingSubprocessModule:
    """Get a subprocess module wrapper that traces all run() calls."""
    return _TracingSubprocessModule(_ORIGINAL_SUBPROCESS_MODULE)
