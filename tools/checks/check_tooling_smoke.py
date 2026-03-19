from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON = sys.executable
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
        "schema-diff-dir",
        [PYTHON, "tools/schema_diff/main.py", "specs", "specs"],
        "SafeClaw schema diff stub ready.",
    ),
    (
        "schema-diff-file",
        [PYTHON, "tools/schema_diff/main.py", "specs/schemas/action_tiers.json", "specs/schemas/action_tiers.json"],
        "SafeClaw schema diff stub ready.",
    ),
]


def collect_errors() -> list[str]:
    errors: list[str] = []

    for name, command, expected in CHECKS:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        output = (completed.stdout or "") + (completed.stderr or "")
        if completed.returncode != 0:
            errors.append(f"{name} 执行失败: exit={completed.returncode}")
            continue
        if expected not in output:
            errors.append(f"{name} 输出缺少关键文本: {expected}")

    for target in ("rust", "python", "ts"):
        manifest_path = REPO_ROOT / "generated" / target / "manifest.json"
        stable_ids_path = REPO_ROOT / "generated" / target / "stable_ids.json"
        if not manifest_path.exists():
            errors.append(f"缺少 codegen 产物: {manifest_path.relative_to(REPO_ROOT).as_posix()}")
        if not stable_ids_path.exists():
            errors.append(f"缺少 codegen 产物: {stable_ids_path.relative_to(REPO_ROOT).as_posix()}")

    return errors


def main() -> int:
    errors = collect_errors()
    if errors:
        print("Tooling smoke check failed:")
        for item in errors:
            print(f"- {item}")
        return 1

    print("Tooling smoke check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
