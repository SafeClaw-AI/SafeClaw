"""JSON assertion utilities for smoke tests."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


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


def load_json_file_payload(
    path: Path, errors: list[str], name: str
) -> dict[str, object] | None:
    """Load and validate JSON payload from file."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        errors.append(f"{name} 读取失败: {exc}")
        return None
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


def assert_session_passthrough_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    action: str,
    expected_task_id: str,
) -> None:
    """Assert session passthrough command JSON result structure."""
    if result is None:
        return

    prepared = result.get("prepared") or []
    remembered_session = result.get("remembered_session") or {}
    source_hints = result.get("source_hints") or {}
    captured_output = str(result.get("captured_output") or "")

    if not prepared or prepared[0] != action:
        errors.append(f"{name} missing prepared {action}")
    elif expected_task_id not in captured_output:
        errors.append(f"{name} missing captured task {expected_task_id}")
    elif (
        not isinstance(remembered_session, dict)
        or remembered_session.get("task_id") != expected_task_id
    ):
        errors.append(f"{name} missing remembered session {expected_task_id}")
    elif not isinstance(source_hints, dict) or source_hints.get("db") != "session":
        errors.append(f"{name} missing source_hints.db=session")
    elif source_hints.get("output") != "session":
        errors.append(f"{name} missing source_hints.output=session")
    elif source_hints.get("owner_id") != "session":
        errors.append(f"{name} missing source_hints.owner_id=session")
    elif source_hints.get("task_context") != "session":
        errors.append(f"{name} missing source_hints.task_context=session")


def assert_run_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    expected_task_id: str,
    expected_db_path: str | None = None,
    expected_output_path: str | None = None,
    expected_db_source: str,
    expected_output_source: str,
    expected_owner_source: str = "default",
    expected_task_context_source: str = "flag",
) -> None:
    """Assert run command JSON result structure."""
    if result is None:
        return

    saved_session = result.get("saved_session") or {}
    remembered_session = result.get("remembered_session") or {}
    source_hints = result.get("source_hints") or {}
    captured_output = str(result.get("captured_output") or "").replace("/", chr(92))
    normalized_saved_db = str(saved_session.get("db") or "").replace("/", chr(92))
    normalized_saved_output = str(saved_session.get("output") or "").replace("/", chr(92))
    normalized_expected_db = (
        None if expected_db_path is None else expected_db_path.replace("/", chr(92))
    )
    normalized_expected_output = (
        None if expected_output_path is None else expected_output_path.replace("/", chr(92))
    )

    if (
        not isinstance(saved_session, dict)
        or saved_session.get("task_id") != expected_task_id
    ):
        errors.append(f"{name} missing saved_session task_id={expected_task_id}")
    elif (
        normalized_expected_db is not None
        and normalized_saved_db != normalized_expected_db
    ):
        errors.append(f"{name} missing saved_session db={expected_db_path}")
    elif (
        normalized_expected_output is not None
        and normalized_saved_output != normalized_expected_output
    ):
        errors.append(f"{name} missing saved_session output={expected_output_path}")
    elif (
        not isinstance(remembered_session, dict) or remembered_session != saved_session
    ):
        errors.append(f"{name} missing remembered_session mirror")
    elif (
        not isinstance(source_hints, dict)
        or source_hints.get("db") != expected_db_source
    ):
        errors.append(f"{name} missing source_hints.db={expected_db_source}")
    elif source_hints.get("output") != expected_output_source:
        errors.append(f"{name} missing source_hints.output={expected_output_source}")
    elif source_hints.get("owner_id") != expected_owner_source:
        errors.append(f"{name} missing source_hints.owner_id={expected_owner_source}")
    elif source_hints.get("task_context") != expected_task_context_source:
        errors.append(
            f"{name} missing source_hints.task_context={expected_task_context_source}"
        )
    elif (
        normalized_expected_db is not None
        and normalized_expected_db not in captured_output
    ):
        errors.append(f"{name} missing captured db path")
    elif (
        normalized_expected_output is not None
        and normalized_expected_output not in captured_output
    ):
        errors.append(f"{name} missing captured output path")


def assert_step_source_hints(
    steps: object,
    errors: list[str],
    name: str,
    expected: list[tuple[str, dict[str, str]]],
) -> None:
    """Assert step source hints in multi-step commands."""
    if not isinstance(steps, list):
        errors.append(f"{name} steps 不是列表")
        return

    for index, (expected_action, expected_hints) in enumerate(expected):
        if index >= len(steps) or not isinstance(steps[index], dict):
            errors.append(f"{name} 缺少步骤 {expected_action}")
            return

        step = steps[index]

        if step.get("action") != expected_action:
            errors.append(f"{name} 步骤 {index} 不是 {expected_action}")
            return

        source_hints = step.get("source_hints") or {}

        if not isinstance(source_hints, dict):
            errors.append(f"{name} 步骤 {expected_action} 缺少 source_hints")
            return

        for field, expected_value in expected_hints.items():
            if source_hints.get(field) != expected_value:
                errors.append(
                    f"{name} 步骤 {expected_action} source_hints.{field} != {expected_value}"
                )
                return


def assert_matching_session_alias(
    payload: dict[str, object] | None,
    errors: list[str],
    name: str,
) -> None:
    """Assert that session alias matches remembered_session."""
    if payload is None:
        return

    remembered_session = payload.get("remembered_session") or {}
    session = payload.get("session") or {}

    if not isinstance(remembered_session, dict):
        errors.append(f"{name} remembered_session 不是对象")
        return

    if not isinstance(session, dict):
        errors.append(f"{name} session 兼容别名不是对象")
        return

    if session != remembered_session:
        errors.append(f"{name} session 兼容别名与 remembered_session 不一致")


def assert_workspace_seed_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    expected_action: str,
    expected_task_id: str,
) -> None:
    """Assert workspace seed command JSON result structure."""
    if result is None:
        return

    prepared = result.get("prepared") or []
    session = result.get("saved_session") or {}
    source_hints = result.get("source_hints") or {}

    if not prepared or prepared[0] != expected_action:
        errors.append(f"{name} missing prepared {expected_action}")
    elif session.get("task_id") != expected_task_id:
        errors.append(f"{name} missing saved session task")
    elif source_hints.get("db") != "workspace":
        errors.append(f"{name} missing workspace db source")


def assert_json_error_fields(
    error: dict[str, object] | None,
    details: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    expected_error_message_substring: str | None = None,
    error_message_label: str | None = None,
    expected_top_level_error_code: str | None = None,
    expected_top_level_error_reason: str | None = None,
    expected_top_level_error_error_code: str | None = None,
    expect_top_level_error_error_code_absent: bool = False,
    expected_top_level_error_degradation_mode: str | None = None,
    expected_top_level_error_requires_model: bool | None = None,
    expected_top_level_error_requires_sidecar: bool | None = None,
    expected_top_level_error_requested_action: str | None = None,
    expected_code: str | None = None,
    expected_failed_step: str | None = None,
    expected_details_message_substring: str | None = None,
    details_message_field: str = "error_message",
    details_message_label: str | None = None,
    expected_remembered_session_task_id: str | None = None,
    remembered_session_label: str | None = None,
    expect_no_remembered_session: bool = False,
    expected_preflight_requested_action: str | None = None,
    expected_preflight_reason: str | None = None,
    expected_preflight_error_code: str | None = None,
    expect_preflight_error_code_absent: bool = False,
    expected_preflight_summary_substring: str | None = None,
    expect_top_level_error_summary_matches_preflight: bool = False,
) -> None:
    """Assert JSON error fields with comprehensive validation."""
    if error is None:
        return

    if expected_error_message_substring is not None:
        if expected_error_message_substring not in str(error.get("message", "")):
            errors.append(error_message_label or f"{name} 输出缺少错误信息")
            return

    if expected_top_level_error_code is not None:
        if error.get("code") != expected_top_level_error_code:
            errors.append(f"{name} missing error.code={expected_top_level_error_code}")
            return

    if expected_top_level_error_reason is not None:
        if error.get("reason") != expected_top_level_error_reason:
            errors.append(
                f"{name} missing error.reason={expected_top_level_error_reason}"
            )
            return

    if expected_top_level_error_error_code is not None:
        if error.get("error_code") != expected_top_level_error_error_code:
            errors.append(
                f"{name} missing error.error_code={expected_top_level_error_error_code}"
            )
            return

    if expect_top_level_error_error_code_absent:
        if error.get("error_code") is not None:
            errors.append(f"{name} expected no error.error_code")
            return

    if expected_top_level_error_degradation_mode is not None:
        if error.get("degradation_mode") != expected_top_level_error_degradation_mode:
            errors.append(
                f"{name} missing error.degradation_mode={expected_top_level_error_degradation_mode}"
            )
            return

    if expected_top_level_error_requires_model is not None:
        if error.get("requires_model") is not expected_top_level_error_requires_model:
            errors.append(
                f"{name} missing error.requires_model={expected_top_level_error_requires_model}"
            )
            return

    if expected_top_level_error_requires_sidecar is not None:
        if (
            error.get("requires_sidecar")
            is not expected_top_level_error_requires_sidecar
        ):
            errors.append(
                f"{name} missing error.requires_sidecar={expected_top_level_error_requires_sidecar}"
            )
            return

    if expected_top_level_error_requested_action is not None:
        if error.get("requested_action") != expected_top_level_error_requested_action:
            errors.append(
                f"{name} missing error.requested_action={expected_top_level_error_requested_action}"
            )
            return

    if details is None:
        return

    if expected_failed_step is not None:
        if details.get("failed_step") != expected_failed_step:
            errors.append(f"{name} 缺少失败步骤 {expected_failed_step}")
            return

    if expected_code is not None:
        if details.get("code") != expected_code:
            errors.append(f"{name} 缺少错误代码 {expected_code}")
            return

    if expected_details_message_substring is not None:
        if expected_details_message_substring not in str(
            details.get(details_message_field, "")
        ):
            errors.append(details_message_label or f"{name} 缺少错误明细")
            return

    if expect_no_remembered_session:
        if details.get("remembered_session") is not None:
            errors.append(f"{name} remembered_session 预期为空")
            return

    if expected_remembered_session_task_id is not None:
        remembered_session = details.get("remembered_session") or {}

        if (
            not isinstance(remembered_session, dict)
            or remembered_session.get("task_id") != expected_remembered_session_task_id
        ):
            errors.append(
                remembered_session_label
                or f"{name} remembered_session 缺少 {expected_remembered_session_task_id}"
            )
            return

    if expected_preflight_requested_action is not None:
        if (
            details.get("preflight_requested_action")
            != expected_preflight_requested_action
        ):
            errors.append(
                f"{name} missing preflight_requested_action={expected_preflight_requested_action}"
            )
            return

    if expected_preflight_reason is not None:
        if details.get("preflight_reason") != expected_preflight_reason:
            errors.append(
                f"{name} missing preflight_reason={expected_preflight_reason}"
            )
            return

    if expected_preflight_error_code is not None:
        if details.get("preflight_error_code") != expected_preflight_error_code:
            errors.append(
                f"{name} missing preflight_error_code={expected_preflight_error_code}"
            )
            return

    if expect_preflight_error_code_absent:
        if details.get("preflight_error_code") is not None:
            errors.append(f"{name} expected no preflight_error_code")
            return

    if expected_preflight_summary_substring is not None:
        if expected_preflight_summary_substring not in str(
            details.get("preflight_summary", "")
        ):
            errors.append(
                f"{name} missing preflight_summary substring {expected_preflight_summary_substring}"
            )
            return

    if expect_top_level_error_summary_matches_preflight:
        if error.get("summary") != details.get("preflight_summary"):
            errors.append(
                f"{name} missing mirrored error.summary from preflight_summary"
            )

def assert_run_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    expected_task_id: str,
    expected_db_path: str | None = None,
    expected_output_path: str | None = None,
    expected_db_source: str,
    expected_output_source: str,
    expected_owner_source: str = "default",
    expected_task_context_source: str = "flag",
) -> None:
    if result is None:
        return

    saved_session = result.get("saved_session") or {}

    remembered_session = result.get("remembered_session") or {}

    source_hints = result.get("source_hints") or {}

    captured_output = str(result.get("captured_output") or "").replace("/", chr(92))

    normalized_saved_db = str(saved_session.get("db") or "").replace("/", chr(92))

    normalized_saved_output = str(saved_session.get("output") or "").replace(
        "/", chr(92)
    )

    normalized_expected_db = (
        None if expected_db_path is None else expected_db_path.replace("/", chr(92))
    )

    normalized_expected_output = (
        None
        if expected_output_path is None
        else expected_output_path.replace("/", chr(92))
    )

    if (
        not isinstance(saved_session, dict)
        or saved_session.get("task_id") != expected_task_id
    ):
        errors.append(f"{name} missing saved_session task_id={expected_task_id}")

    elif (
        normalized_expected_db is not None
        and normalized_saved_db != normalized_expected_db
    ):
        errors.append(f"{name} missing saved_session db={expected_db_path}")

    elif (
        normalized_expected_output is not None
        and normalized_saved_output != normalized_expected_output
    ):
        errors.append(f"{name} missing saved_session output={expected_output_path}")

    elif (
        not isinstance(remembered_session, dict) or remembered_session != saved_session
    ):
        errors.append(f"{name} missing remembered_session mirror")

    elif (
        not isinstance(source_hints, dict)
        or source_hints.get("db") != expected_db_source
    ):
        errors.append(f"{name} missing source_hints.db={expected_db_source}")

    elif source_hints.get("output") != expected_output_source:
        errors.append(f"{name} missing source_hints.output={expected_output_source}")

    elif source_hints.get("owner_id") != expected_owner_source:
        errors.append(f"{name} missing source_hints.owner_id={expected_owner_source}")

    elif source_hints.get("task_context") != expected_task_context_source:
        errors.append(
            f"{name} missing source_hints.task_context={expected_task_context_source}"
        )

    elif (
        normalized_expected_db is not None
        and normalized_expected_db not in captured_output
    ):
        errors.append(f"{name} missing captured db path")

    elif (
        normalized_expected_output is not None
        and normalized_expected_output not in captured_output
    ):
        errors.append(f"{name} missing captured output path")

def assert_use_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    expected_task_id: str,
    expected_source: str,
) -> None:
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

def assert_session_passthrough_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    action: str,
    expected_task_id: str,
) -> None:
    if result is None:
        return

    prepared = result.get("prepared") or []

    remembered_session = result.get("remembered_session") or {}

    source_hints = result.get("source_hints") or {}

    captured_output = str(result.get("captured_output") or "")

    if not prepared or prepared[0] != action:
        errors.append(f"{name} missing prepared {action}")

    elif expected_task_id not in captured_output:
        errors.append(f"{name} missing captured task {expected_task_id}")

    elif (
        not isinstance(remembered_session, dict)
        or remembered_session.get("task_id") != expected_task_id
    ):
        errors.append(f"{name} missing remembered session {expected_task_id}")

    elif not isinstance(source_hints, dict) or source_hints.get("db") != "session":
        errors.append(f"{name} missing source_hints.db=session")

    elif source_hints.get("output") != "session":
        errors.append(f"{name} missing source_hints.output=session")

    elif source_hints.get("owner_id") != "session":
        errors.append(f"{name} missing source_hints.owner_id=session")

    elif source_hints.get("task_context") != "session":
        errors.append(f"{name} missing source_hints.task_context=session")

def assert_session_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    expected_task_id: str,
) -> None:
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
    if payload is None:
        return

    if payload.get("ok") is not True or payload.get("action") != action:
        errors.append(f"{name} missing envelope")

    elif "result" not in payload or payload.get("result") is not None:
        errors.append(f"{name} missing result=null")

