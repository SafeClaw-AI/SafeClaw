from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.checks.spec_index import build_spec_index

SPECS_ROOT = REPO_ROOT / "specs"
REQUIRED_DIRS = [
    "specs/config",
    "specs/error-codes",
    "specs/manifests",
    "specs/schemas",
    "specs/spi",
    "specs/state-machines",
]
REQUIRED_FILES = [
    "specs/README.md",
    "specs/config/preflight.json",
    "specs/error-codes/sys_errors.json",
    "specs/schemas/action_tiers.json",
    "specs/schemas/effect_ledger.json",
    "specs/spi/base_fields.json",
    "specs/state-machines/worker_lifecycle.json",
]
REQUIRED_FIELDS = {
    "specs/config/preflight.json": {"confidence_threshold", "degradation", "runtime", "metrics"},
    "specs/error-codes/sys_errors.json": {"errors", "severity_levels", "categories"},
    "specs/schemas/action_tiers.json": {"tiers", "reversibility", "orthogonal_matrix", "preflight_rules"},
    "specs/schemas/effect_ledger.json": {"type", "required", "properties", "commit_order"},
    "specs/spi/base_fields.json": {"type", "required", "properties", "registry"},
    "specs/state-machines/worker_lifecycle.json": {"states", "transitions", "terminal_states", "invariants", "system_budgets"},
}


def collect_errors() -> list[str]:
    errors: list[str] = []

    for relpath in REQUIRED_DIRS:
        path = REPO_ROOT / relpath
        if not path.exists():
            errors.append(f"缺少目录: {relpath}")
        elif not path.is_dir():
            errors.append(f"路径不是目录: {relpath}")

    for relpath in REQUIRED_FILES:
        path = REPO_ROOT / relpath
        if not path.exists():
            errors.append(f"缺少文件: {relpath}")
        elif not path.is_file():
            errors.append(f"路径不是文件: {relpath}")

    index = build_spec_index()
    for relpath, required_fields in REQUIRED_FIELDS.items():
        try:
            doc = index.require(relpath)
        except KeyError as exc:
            errors.append(str(exc))
            continue

        missing_fields = sorted(required_fields - set(doc.data.keys()))
        for field in missing_fields:
            errors.append(f"{relpath} 缺少根字段: {field}")

        expected_id = f"safeclaw://{relpath}"
        actual_id = doc.data.get("$id")
        if actual_id != expected_id:
            errors.append(f"{relpath} 的 $id 不匹配: {actual_id} != {expected_id}")

    return errors


def main() -> int:
    errors = collect_errors()
    if errors:
        print("Structure completeness check failed:")
        for item in errors:
            print(f"- {item}")
        return 1

    print(f"Structure completeness check passed for {SPECS_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
