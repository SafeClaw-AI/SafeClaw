from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON = sys.executable
CHECKS: list[tuple[str, list[str]]] = [
    (
        "Contract tests",
        [PYTHON, "-u", "-m", "unittest", "discover", "-s", "tests/contracts", "-p", "test_*.py", "-v"],
    ),
    (
        "Cross-file consistency",
        [PYTHON, "-u", "tools/checks/check_consistency.py"],
    ),
    (
        "Version consistency",
        [PYTHON, "-u", "tools/checks/check_versions.py"],
    ),
    (
        "Structure completeness",
        [PYTHON, "-u", "tools/checks/check_structure.py"],
    ),
    (
        "Naming lint",
        [PYTHON, "-u", "tools/lint/check_naming.py"],
    ),
    (
        "Public docs alignment",
        [PYTHON, "-u", "tools/checks/check_public_docs.py"],
    ),
    (
        "Scaffold layout",
        [PYTHON, "-u", "tools/checks/check_scaffold.py"],
    ),
    (
        "Tooling smoke",
        [PYTHON, "-u", "tools/checks/check_tooling_smoke.py"],
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
