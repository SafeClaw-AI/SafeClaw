"""Constants and configuration for smoke tests."""

from __future__ import annotations

import sys
from pathlib import Path

# Repository root
REPO_ROOT = Path(__file__).resolve().parents[3]

# Python executable
PYTHON = sys.executable

# Smoke test stub configurations
SMOKE_DEMO_STUB_ACTIONS = {"demo", "recover-demo", "retry-demo", "service-demo"}

SMOKE_DEMO_STUB_TASK_IDS = {
    "task-wrapper-demo",
    "task-wrapper-demo-json",
    "task-wrapper-demo-preflight",
    "task-wrapper-recover-demo",
    "task-wrapper-recover-demo-json",
    "task-wrapper-retry-demo",
    "task-wrapper-retry-demo-json",
}

SMOKE_WRAPPER_SERVICE_STUB_ACTIONS = {"service-demo", "service-run"}

SMOKE_WRAPPER_SERVICE_STUB_TASK_IDS = {
    "task-wrapper-service-run-json",
    "task-wrapper-service-run-report-json",
}

SMOKE_WRAPPER_SERVICE_REPORT_STUB_ACTIONS = {
    "service-retry",
    "service-recover",
    "service-resume",
    "service-reconcile",
}

SMOKE_WRAPPER_SERVICE_REPORT_STUB_TASK_IDS = {
    "task-wrapper-service-retry-report-json",
    "task-wrapper-service-recover-report-json",
    "task-wrapper-service-resume-report-json",
    "task-wrapper-service-reconcile-report-json",
}

SMOKE_ROOT_PS1_SERVICE_REPORT_STUB_ACTIONS = {
    "service-run",
    "service-retry",
    "service-recover",
    "service-resume",
    "service-reconcile",
}

SMOKE_ROOT_PS1_SERVICE_REPORT_STUB_TASK_IDS = {
    "task-readme-root",
    "task-readme-root-failed-ps1",
    "task-readme-root-uncertain-ps1",
    "task-readme-root-hibernated-ps1",
    "task-readme-root-assumed-ps1",
}

SMOKE_WRAPPER_REPORT_STUB_TASK_OUTPUTS = {
    "task-wrapper-recover-json": ("", "", ""),
    "task-wrapper-report-explicit-crash": (
        "QueueForManualReview",
        "Uncertain",
        "Uncertain",
    ),
    "task-wrapper-session-explicit-crash": (
        "QueueForManualReview",
        "Uncertain",
        "Uncertain",
    ),
    "task-wrapper-report-session-crash": (
        "QueueForManualReview",
        "Uncertain",
        "Uncertain",
    ),
    "task-wrapper-recover-session-crash": (
        "QueueForManualReview",
        "Uncertain",
        "Uncertain",
    ),
}

# Codegen and schema-diff checks
CHECKS: list[tuple[str, list[str], str]] = [
    (
        "codegen-rust",
        [PYTHON, "tools/codegen/main.py", "--target", "rust"],
        "SafeClaw codegen stub ready.",
    ),
    (
        "codegen-python",
        [PYTHON, "tools/codegen/main.py", "--target", "python"],
        "SafeClaw codegen stub ready.",
    ),
    (
        "codegen-ts",
        [PYTHON, "tools/codegen/main.py", "--target", "ts"],
        "SafeClaw codegen stub ready.",
    ),
    (
        "codegen-regenerate-all",
        [PYTHON, "tools/codegen/regenerate_all.py"],
        "SafeClaw codegen sync ready.",
    ),
    (
        "schema-diff-dir",
        [PYTHON, "tools/schema_diff/main.py", "specs", "specs"],
        "SafeClaw schema diff ready.",
    ),
    (
        "schema-diff-file",
        [
            PYTHON,
            "tools/schema_diff/main.py",
            "specs/schemas/action_tiers.json",
            "specs/schemas/action_tiers.json",
        ],
        "SafeClaw schema diff ready.",
    ),
]
