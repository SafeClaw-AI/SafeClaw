from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.checks.ledger_index_manifest import load_ledger_index_manifest

REQUIRED_DIRS = [
    "config/trusted_plugins",
    "generated/rust",
    "generated/python",
    "generated/ts",
    "modules/adapters",
    "modules/memory",
    "modules/plugins",
    "modules/repair_plans",
    "safeclaw-core/src",
    "safeclaw-core/tests",
    "tests/fixtures",
]
REQUIRED_FILES = [
    "config/README.md",
    "docs/README.md",
    "tests/README.md",
    "tools/README.md",
    "config/default_config.toml",
    "config/default_permissions.toml",
    "config/trusted_plugins/README.md",
    "generated/README.md",
    "generated/rust/README.md",
    "generated/python/README.md",
    "generated/ts/README.md",
    "modules/README.md",
    "modules/adapters/README.md",
    "modules/memory/README.md",
    "modules/plugins/README.md",
    "modules/repair_plans/README.md",
    "safeclaw-core/ARCHITECTURE.md",
    "safeclaw-core/Cargo.toml",
    "safeclaw-core/README.md",
    "safeclaw-core/src/lib.rs",
    "safeclaw-core/src/protocol.rs",
    "safeclaw-core/src/effect_ledger.rs",
    "safeclaw-core/src/task_concurrency.rs",
    "safeclaw-core/src/worker_lifecycle.rs",
    "safeclaw-core/src/spec_map.rs",
    "safeclaw-core/tests/protocol_contracts.rs",
    "tests/fixtures/README.md",
    "tools/schema_diff/README.md",
    "tools/codegen/README.md",
    "tools/checks/README.md",
    "tools/lint/README.md",
]
LEGACY_REQUIRED_STATES = {"legacy-only", "dual-readable"}


def collect_ledger_scaffold_errors() -> list[str]:
    manifest = load_ledger_index_manifest()
    errors: list[str] = []

    for entry in manifest.ledgers:
        legacy_path = REPO_ROOT / entry.legacy_path
        if entry.cutover_state in LEGACY_REQUIRED_STATES:
            if legacy_path.parent != REPO_ROOT:
                errors.append(f"legacy 阶段台账必须保留在根目录: {entry.logical_id} -> {entry.legacy_path}")
            elif not legacy_path.exists():
                errors.append(f"legacy 阶段缺少根台账文件: {entry.logical_id} -> {entry.legacy_path}")
            elif not legacy_path.is_file():
                errors.append(f"legacy 阶段台账路径不是文件: {entry.logical_id} -> {entry.legacy_path}")

    return errors


def collect_errors() -> list[str]:
    errors: list[str] = []

    for relpath in REQUIRED_DIRS:
        path = REPO_ROOT / relpath
        if not path.exists():
            errors.append(f"缺少骨架目录: {relpath}")
        elif not path.is_dir():
            errors.append(f"骨架路径不是目录: {relpath}")

    for relpath in REQUIRED_FILES:
        path = REPO_ROOT / relpath
        if not path.exists():
            errors.append(f"缺少骨架文件: {relpath}")
        elif not path.is_file():
            errors.append(f"骨架路径不是文件: {relpath}")

    errors.extend(collect_ledger_scaffold_errors())
    return errors


def main() -> int:
    errors = collect_errors()
    if errors:
        print("Scaffold check failed:")
        for item in errors:
            print(f"- {item}")
        return 1

    print("Scaffold check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
