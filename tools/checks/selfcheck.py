from __future__ import annotations

import subprocess
import sys
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
    "-u",
    "-m",
    "unittest",
    "discover",
    "-s",
    "tests/contracts",
    "-p",
    "test_*.py",
    "-v",
]
CHECKS: list[tuple[str, list[str]]] = [
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
        "Tooling smoke",
        [PYTHON, "-u", "tools/checks/check_tooling_smoke.py"],
    ),
    (
        "MVP operator flow",
        [PYTHON, "-u", "tools/checks/check_mvp_operator_flow.py"],
    ),
    (
        "Example smoke",
        [PYTHON, "-u", "tools/checks/check_examples_smoke.py"],
    ),
    (
        "Generated sync",
        [PYTHON, "-u", "tools/checks/check_generated_sync.py"],
    ),
]


def main() -> int:
    for name, command in CHECKS:
        print(f"==> {name}", flush=True)
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        output = ((completed.stdout or "") + (completed.stderr or "")).rstrip()
        if output:
            print(output, flush=True)
        if completed.returncode != 0:
            print(f"[FAIL] {name}", flush=True)
            return completed.returncode
        print(f"[OK] {name}", flush=True)

    print("All protocol checks passed.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())