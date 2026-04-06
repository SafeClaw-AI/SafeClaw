"""Output validation and substring checking utilities for smoke tests."""

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def append_expected_substring_errors(
    output: str,
    errors: list[str],
    expectations: list[tuple[str, str]],
    grouped_expectations: list[tuple[tuple[str, ...], str]] | None = None,
) -> None:
    for needle, message in expectations:
        if needle not in output:
            errors.append(message)
            return
    for needles, message in grouped_expectations or []:
        if any(needle not in output for needle in needles):
            errors.append(message)
            return


def load_help_output(
    command: list[str],
    errors: list[str],
    name: str,
    *,
    failure_verb: str,
) -> str | None:
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        errors.append(f"{name} {failure_verb}: exit={completed.returncode}")
        return None
    return (completed.stdout or "") + (completed.stderr or "")


def append_help_usage_error(
    errors: list[str],
    name: str,
    command: list[str],
    expected_usage: str,
    missing_message: str,
    *,
    failure_verb: str,
) -> None:
    output = load_help_output(command, errors, name, failure_verb=failure_verb)
    if output is not None and expected_usage not in output:
        errors.append(missing_message)
