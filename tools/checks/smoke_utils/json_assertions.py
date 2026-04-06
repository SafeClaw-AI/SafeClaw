"""JSON assertion utilities for smoke tests."""

from __future__ import annotations

import json
import subprocess


def load_json_payload(
    completed: subprocess.CompletedProcess[str],
    errors: list[str],
    name: str,
    expected_exit: int,
) -> dict[str, object] | None:
    """Load and validate JSON payload from subprocess output."""
    if completed.returncode != expected_exit:
        errors.append(f"{name} 执行失败: exit={completed.returncode}")
        return None

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        errors.append(f"{name} 输出不是合法 JSON: {error}")
        return None

    if not isinstance(payload, dict):
        errors.append(f"{name} 输出不是对象 JSON")
        return None

    return payload


def extract_json_error(
    payload: dict[str, object],
    errors: list[str],
    name: str,
    action: str,
) -> tuple[dict[str, object] | None, dict[str, object] | None]:
    """Extract error and details from JSON error response."""
    error = payload.get("error") or {}
    details = error.get("details") or {}

    if payload.get("ok") is not False or payload.get("action") != action:
        errors.append(f"{name} 输出缺少统一错误信封")
        return None, None

    return (
        error if isinstance(error, dict) else None,
        details if isinstance(details, dict) else None,
    )


def extract_json_result(
    payload: dict[str, object],
    errors: list[str],
    name: str,
    action: str,
) -> dict[str, object] | None:
    """Extract result from JSON success response."""
    result = payload.get("result") or {}

    if payload.get("ok") is not True or payload.get("action") != action:
        errors.append(f"{name} 输出缺少统一信封")
        return None

    if not isinstance(result, dict):
        errors.append(f"{name} result 不是对象")
        return None

    return result


def assert_verify_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
) -> None:
    """Assert verify command JSON result structure."""
    if result is None:
        return

    if result.get("exit_code") != 0:
        errors.append(f"{name} missing exit_code=0")
    elif result.get("script") != "tools/checks/check_mvp_operator_flow.py":
        errors.append(f"{name} missing verify script path")
    elif not result.get("python"):
        errors.append(f"{name} missing python path")
    elif "MVP operator flow check passed." not in str(
        result.get("captured_output", "")
    ):
        errors.append(f"{name} missing verify success output")


def assert_doctor_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    expected_db_path: str,
    expected_output_path: str,
    expected_db_source: str = "flag",
) -> None:
    """Assert doctor command JSON result structure."""
    if result is None:
        return

    if result.get("db_path") != expected_db_path:
        errors.append(f"{name} db_path 不匹配")
    if result.get("output_path") != expected_output_path:
        errors.append(f"{name} output_path 不匹配")
    if result.get("db_source") != expected_db_source:
        errors.append(f"{name} db_source 不匹配")


# Placeholder for additional assertion functions
# These will be added in subsequent commits to keep file size manageable
