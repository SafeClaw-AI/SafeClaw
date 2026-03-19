from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_DIRS = [
    "config/trusted_plugins",
    "generated/rust",
    "generated/python",
    "generated/ts",
    "modules/adapters",
    "modules/memory",
    "modules/plugins",
    "modules/repair_plans",
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
    "tests/fixtures/README.md",
    "tools/schema_diff/README.md",
    "tools/codegen/README.md",
    "tools/checks/README.md",
    "tools/lint/README.md",
]


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
