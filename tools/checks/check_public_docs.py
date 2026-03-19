from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
README_FILE = REPO_ROOT / "README.md"
SCOPE_FILE = REPO_ROOT / "docs" / "V1_SCOPE.md"
TRIAGE_FILE = REPO_ROOT / "docs" / "V1_TASK_TRIAGE.md"
DEVLOG_FILE = REPO_ROOT / "docs" / "DEVLOG.md"
VERSION_FILE = REPO_ROOT / "VERSION"

REQUIRED_MARKERS = {
    README_FILE: [
        "specs/",
        "tests/contracts/",
        "tools/checks/",
        "0.1.1",
        "OpenClaw",
        "English Summary",
    ],
    SCOPE_FILE: [
        "Phase 0",
        "specs/",
        "tests/contracts/",
        "tools/checks/",
        "tools/lint/",
    ],
    TRIAGE_FILE: [
        "specs/",
        "CI",
        "codegen",
        "Frozen",
    ],
    DEVLOG_FILE: [
        "README.md",
        "specs/",
        "Phase 0",
    ],
}


def collect_errors() -> list[str]:
    repo_version = VERSION_FILE.read_text(encoding="utf-8").strip()
    errors: list[str] = []

    for path, markers in REQUIRED_MARKERS.items():
        if not path.exists():
            errors.append(f"缺少公开文档: {path.relative_to(REPO_ROOT).as_posix()}")
            continue
        text = path.read_text(encoding="utf-8")
        for marker in markers:
            current_marker = repo_version if marker == "0.1.1" else marker
            if current_marker not in text:
                errors.append(
                    f"公开文档缺少关键标记: {path.relative_to(REPO_ROOT).as_posix()} -> {current_marker}"
                )

    return errors


def main() -> int:
    errors = collect_errors()
    if errors:
        print("Public docs alignment check failed:")
        for item in errors:
            print(f"- {item}")
        return 1

    print("Public docs alignment check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
