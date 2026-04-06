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


def assert_workspace_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    expected_active: bool,
    expected_name: str | None,
    expected_db_path: str,
    expected_output_path: str,
    expected_changed: bool | None = None,
) -> None:
    """Assert workspace command JSON result structure."""
    if result is None:
        return

    normalized_db = str(result.get("db") or "").replace("/", chr(92))
    normalized_output = str(result.get("output") or "").replace("/", chr(92))
    expected_db = expected_db_path.replace("/", chr(92))
    expected_output = expected_output_path.replace("/", chr(92))

    if result.get("active") is not expected_active:
        errors.append(f"{name} missing active={expected_active}")
    elif result.get("name") != expected_name:
        errors.append(f"{name} missing name={expected_name}")
    elif normalized_db != expected_db:
        errors.append(f"{name} missing db={expected_db_path}")
    elif normalized_output != expected_output:
        errors.append(f"{name} missing output={expected_output_path}")
    elif result.get("path") != "target\mvp\workspace.json":
        errors.append(f"{name} missing workspace path")
    elif expected_changed is not None and result.get("changed") is not expected_changed:
        errors.append(f"{name} missing changed={expected_changed}")


def assert_use_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    expected_task_id: str,
    expected_source: str,
) -> None:
    """Assert use command JSON result structure."""
    if result is None:
        return

    if (
        result.get("task_id") != expected_task_id
        or result.get("source") != expected_source
    ):
        errors.append(f"{name} missing task_id/source")
    elif result.get("db_source") != "session":
        errors.append(f"{name} missing db_source=session")
    elif result.get("output_source") != "task_scope":
        errors.append(f"{name} missing output_source=task_scope")
    elif result.get("owner_id_source") != "session":
        errors.append(f"{name} missing owner_id_source=session")


def assert_session_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    expected_task_id: str,
) -> None:
    """Assert session command JSON result structure."""
    if result is None:
        return

    expected_effect_id = f"effect-{expected_task_id}"

    if result.get("task_id") != expected_task_id:
        errors.append(f"{name} missing task_id={expected_task_id}")
    elif result.get("effect_id") != expected_effect_id:
        errors.append(f"{name} missing effect_id={expected_effect_id}")
    elif result.get("db") != "target\mvp\session.db":
        errors.append(f"{name} missing db=target\mvp\session.db")
    elif result.get("output") != "target\mvp\output.txt":
        errors.append(f"{name} missing output=target\mvp\output.txt")
    elif result.get("owner_id") != "safeclaw-mvp":
        errors.append(f"{name} missing owner_id=safeclaw-mvp")


def assert_sessions_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    expected_current_task_id: str,
    expected_previous_task_id: str,
) -> None:
    """Assert sessions command JSON result structure."""
    if result is None:
        return

    rows = result.get("rows") or []
    current_session = result.get("current_session") or {}

    if result.get("db") != "target\mvp\session.db":
        errors.append(f"{name} missing db=target\mvp\session.db")
    elif result.get("db_source") != "session":
        errors.append(f"{name} missing db_source=session")
    elif result.get("limit") != 5:
        errors.append(f"{name} missing limit=5")
    elif (
        not isinstance(current_session, dict)
        or current_session.get("task_id") != expected_current_task_id
    ):
        errors.append(f"{name} missing current_session {expected_current_task_id}")
    elif not rows or rows[0].get("task_id") != expected_current_task_id:
        errors.append(f"{name} missing recent[0] task={expected_current_task_id}")
    elif rows[0].get("current") is not True:
        errors.append(f"{name} missing recent[0] current=true")
    elif len(rows) < 2 or rows[1].get("task_id") != expected_previous_task_id:
        errors.append(f"{name} missing recent[1] task={expected_previous_task_id}")
    elif rows[1].get("current") is not False:
        errors.append(f"{name} missing recent[1] current=false")


def assert_json_null_result(
    payload: dict[str, object] | None,
    errors: list[str],
    name: str,
    action: str,
) -> None:
    """Assert JSON response with null result."""
    if payload is None:
        return

    if payload.get("ok") is not True or payload.get("action") != action:
        errors.append(f"{name} missing envelope")
    elif "result" not in payload or payload.get("result") is not None:
        errors.append(f"{name} missing result=null")


# Placeholder for additional assertion functions
# These will be added in subsequent commits to keep file size manageable
