from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
README_FILE = REPO_ROOT / "README.md"
SCOPE_FILE = REPO_ROOT / "docs" / "V1_SCOPE.md"
TRIAGE_FILE = REPO_ROOT / "docs" / "V1_TASK_TRIAGE.md"
DEVLOG_FILE = REPO_ROOT / "docs" / "DEVLOG.md"
SPECS_README_FILE = REPO_ROOT / "specs" / "README.md"
CONTRACTS_README_FILE = REPO_ROOT / "tests" / "contracts" / "README.md"
CODEGEN_README_FILE = REPO_ROOT / "tools" / "codegen" / "README.md"
SCHEMA_DIFF_README_FILE = REPO_ROOT / "tools" / "schema_diff" / "README.md"
DOCS_README_FILE = REPO_ROOT / "docs" / "README.md"
DIRECTORY_LOCK_FILE = REPO_ROOT / "docs" / "30-方案" / "02-V4-目录锁定清单.md"
TOOLS_README_FILE = REPO_ROOT / "tools" / "README.md"
TESTS_README_FILE = REPO_ROOT / "tests" / "README.md"
MVP_PROGRESS_FILE = REPO_ROOT / "MVP_PROGRESS.md"
PUSH_LOG_FILE = REPO_ROOT / "PUSH_LOG.md"
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
    SPECS_README_FILE: [
        "specs/",
        "generated/index.json",
        "plugin_runner.template.jsonc",
    ],
    CONTRACTS_README_FILE: [
        "specs/",
        "tools/checks/",
        "generated/",
    ],
    CODEGEN_README_FILE: [
        "regenerate_all.py",
        "generated/index.json",
        "stable_ids.json",
    ],
    SCHEMA_DIFF_README_FILE: [
        "--json-out",
        "--fail-on-diff",
        "schema",
    ],
    DOCS_README_FILE: [
        "DEVLOG.md",
        "V1_SCOPE.md",
        "V1_TASK_TRIAGE.md",
        "02-V4-目录锁定清单.md",
        "04-V4-repo-hygiene-migration-plan.md",
        "06-V4-ledger-compat-index-spec.md",
    ],
    DIRECTORY_LOCK_FILE: [
        "当前仓库的目录锁定依据",
        "迁移前临时保留",
        "docs/round_logs/",
        "specs/spi/keystore/",
        "04-V4-repo-hygiene-migration-plan.md",
        "06-V4-ledger-compat-index-spec.md",
    ],
    TOOLS_README_FILE: [
        "tools/checks/",
        "tools/codegen/",
        "selfcheck.py",
    ],
    TESTS_README_FILE: [
        "tests/contracts/",
        "tests/fixtures/",
        "合同测试",
    ],
    MVP_PROGRESS_FILE: [
        "整体计划实现进展表",
        "当前阶段",
        "当前预估",
        "## 进展",
    ],
    PUSH_LOG_FILE: [
        "提交推送流水账",
        "## 记录规则",
        "## 流水",
    ],
}

QUESTION_MARK_FORBIDDEN = {
    MVP_PROGRESS_FILE: True,
    PUSH_LOG_FILE: True,
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

        if QUESTION_MARK_FORBIDDEN.get(path) and ("?" in text or "�" in text):
            errors.append(
                f"公开文档疑似编码损坏: {path.relative_to(REPO_ROOT).as_posix()} 含有意外占位符"
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
