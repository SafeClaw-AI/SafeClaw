from __future__ import annotations

import json
import subprocess
import sys
import tempfile
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
        "SafeClaw schema diff ready.",
    ),
    (
        "schema-diff-file",
        [PYTHON, "tools/schema_diff/main.py", "specs/schemas/action_tiers.json", "specs/schemas/action_tiers.json"],
        "SafeClaw schema diff ready.",
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

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        old_path = temp_root / "old.json"
        new_path = temp_root / "new.json"
        json_out = temp_root / "diff.json"
        old_path.write_text(json.dumps({"version": "0.1.1", "a": 1}), encoding="utf-8")
        new_path.write_text(json.dumps({"version": "0.1.2", "a": 2, "b": 3}), encoding="utf-8")

        json_run = subprocess.run(
            [PYTHON, "tools/schema_diff/main.py", str(old_path), str(new_path), "--json-out", str(json_out)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        if json_run.returncode != 0:
            errors.append(f"schema-diff json 输出执行失败: exit={json_run.returncode}")
        elif not json_out.exists():
            errors.append("schema-diff 未生成 JSON 输出文件")

        fail_run = subprocess.run(
            [PYTHON, "tools/schema_diff/main.py", str(old_path), str(new_path), "--fail-on-diff"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        if fail_run.returncode == 0:
            errors.append("schema-diff 在存在差异时未按预期返回非 0")

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
