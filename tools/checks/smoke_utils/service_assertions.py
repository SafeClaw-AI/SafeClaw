"""Service-related assertion utilities for smoke tests."""

from __future__ import annotations


def assert_service_demo_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
) -> None:
    """Assert service-demo command JSON result structure."""
    if result is None:
        return

    resolved_run = result.get("resolved_run") or {}
    resolved_governance = result.get("resolved_governance") or {}
    confirmation_governance = result.get("confirmation_governance") or {}
    resolved_tasks = result.get("resolved_tasks") or []
    confirmation_tasks = result.get("confirmation_tasks") or []
    captured_output = str(result.get("captured_output") or "")

    if result.get("example") != "worker_service_governance_demo":
        errors.append(f"{name} missing example name")
    elif not isinstance(resolved_run, dict) or resolved_run.get("executed") != 2:
        errors.append(f"{name} missing resolved_run.executed=2")
    elif resolved_run.get("parked") != 0:
        errors.append(f"{name} missing resolved_run.parked=0")
    elif (
        not isinstance(resolved_governance, dict)
        or resolved_governance.get("resolved") != 2
    ):
        errors.append(f"{name} missing resolved_governance.resolved=2")
    elif resolved_governance.get("confirmation") != 0:
        errors.append(f"{name} missing resolved_governance.confirmation=0")
    elif (
        not isinstance(confirmation_governance, dict)
        or confirmation_governance.get("confirmation") != 1
    ):
        errors.append(f"{name} missing confirmation_governance.confirmation=1")
    elif confirmation_governance.get("manual_review") != 0:
        errors.append(f"{name} missing confirmation_governance.manual_review=0")
    elif (
        not isinstance(resolved_tasks, list)
        or "task-worker-service-governance-a" not in resolved_tasks
    ):
        errors.append(f"{name} missing resolved task a")
    elif "task-worker-service-governance-b" not in resolved_tasks:
        errors.append(f"{name} missing resolved task b")
    elif (
        not isinstance(confirmation_tasks, list)
        or "task-worker-service-governance-confirmation" not in confirmation_tasks
    ):
        errors.append(f"{name} missing confirmation task")
    elif not str(result.get("db_path") or "").lower().endswith(".db"):
        errors.append(f"{name} missing db_path")
    elif (
        "[demo] service governance resolved => total=2 resolved=2 confirmation=0 manual_review=0"
        not in captured_output
    ):
        errors.append(f"{name} missing resolved governance output")
    elif (
        "[demo] service governance confirmation => total=1 resolved=0 confirmation=1 manual_review=0"
        not in captured_output
    ):
        errors.append(f"{name} missing confirmation governance output")


# Placeholder for more service assertion functions
# Will be added incrementally to keep commits manageable
