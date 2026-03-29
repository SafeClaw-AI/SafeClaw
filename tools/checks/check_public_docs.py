from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.checks.check_ledger_alignment import collect_ledger_errors

README_FILE = REPO_ROOT / "README.md"
SCOPE_FILE = REPO_ROOT / "docs" / "V1_SCOPE.md"
TRIAGE_FILE = REPO_ROOT / "docs" / "V1_TASK_TRIAGE.md"
DEVLOG_FILE = REPO_ROOT / "docs" / "DEVLOG.md"
IMPLEMENTATION_STRATEGY_FILE = REPO_ROOT / "docs" / "IMPLEMENTATION_STRATEGY.md"
SPECS_README_FILE = REPO_ROOT / "specs" / "README.md"
CONTRACTS_README_FILE = REPO_ROOT / "tests" / "contracts" / "README.md"
CODEGEN_README_FILE = REPO_ROOT / "tools" / "codegen" / "README.md"
SCHEMA_DIFF_README_FILE = REPO_ROOT / "tools" / "schema_diff" / "README.md"
DOCS_README_FILE = REPO_ROOT / "docs" / "README.md"
DIRECTORY_LOCK_FILE = REPO_ROOT / "docs" / "30-方案" / "02-V4-目录锁定清单.md"
REFERENCE_REBASELINE_FILE = REPO_ROOT / "docs" / "30-方案" / "20-V4-reference-compliance-rebaseline-record-20260329_030242.md"
TOOLS_README_FILE = REPO_ROOT / "tools" / "README.md"
CHECKS_README_FILE = REPO_ROOT / "tools" / "checks" / "README.md"
TESTS_README_FILE = REPO_ROOT / "tests" / "README.md"
OPERATOR_PLAYBOOK_FILE = REPO_ROOT / "tools" / "mvp" / "OPERATOR_PLAYBOOK.md"
MVP_README_FILE = REPO_ROOT / "tools" / "mvp" / "README.md"
LINT_README_FILE = REPO_ROOT / "tools" / "lint" / "README.md"
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
        "selfcheck.py",
        "ledger_index_manifest.py",
        "check_ledger_alignment.py",
        "check_consistency.py",
        "check_versions.py",
        "check_structure.py",
        "check_scaffold.py",
        "check_public_docs.py",
        "Contract tests",
    ],
    TRIAGE_FILE: [
        "specs/",
        "CI",
        "codegen",
        "Frozen",
        "selfcheck.py",
        "ledger_index_manifest.py",
        "check_ledger_alignment.py",
        "check_consistency.py",
        "check_versions.py",
        "check_structure.py",
        "check_scaffold.py",
        "check_public_docs.py",
        "Contract tests",
    ],
    DEVLOG_FILE: [
        "README.md",
        "specs/",
        "Phase 0",
        "selfcheck.py",
        ".github/workflows/contracts.yml",
        "ledger_index_manifest.py",
        "check_ledger_alignment.py",
        "check_consistency.py",
        "check_versions.py",
        "check_structure.py",
        "check_scaffold.py",
        "check_public_docs.py",
        "Contract tests",
    ],
    IMPLEMENTATION_STRATEGY_FILE: [
        "README.md",
        "specs/",
        "tests/contracts/",
        "tools/checks/",
        "selfcheck.py",
        "ledger_index_manifest.py",
        "check_ledger_alignment.py",
        "check_consistency.py",
        "check_versions.py",
        "check_structure.py",
        "check_scaffold.py",
        "check_public_docs.py",
        "Contract tests",
    ],
    SPECS_README_FILE: [
        "specs/",
        "generated/index.json",
        "plugin_runner.template.jsonc",
        "ledger-first policy chain",
        "selfcheck.py",
        "ledger_index_manifest.py",
        "check_ledger_alignment.py",
        "check_consistency.py",
        "check_versions.py",
        "check_structure.py",
        "check_scaffold.py",
        "check_public_docs.py",
        "Contract tests",
    ],
    CONTRACTS_README_FILE: [
        "specs/",
        "tools/checks/",
        "generated/",
        "selfcheck.py",
        "ledger_index_manifest.py",
        "check_ledger_alignment.py",
        "check_consistency.py",
        "check_versions.py",
        "check_structure.py",
        "check_scaffold.py",
        "check_public_docs.py",
        "Contract tests",
    ],
    CODEGEN_README_FILE: [
        "regenerate_all.py",
        "generated/index.json",
        "stable_ids.json",
        "selfcheck.py",
        ".github/workflows/contracts.yml",
        "ledger_index_manifest.py",
        "check_ledger_alignment.py",
        "check_consistency.py",
        "check_versions.py",
        "check_structure.py",
        "check_scaffold.py",
        "check_public_docs.py",
        "Contract tests",
    ],
    SCHEMA_DIFF_README_FILE: [
        "--json-out",
        "--fail-on-diff",
        "schema",
        "selfcheck.py",
        ".github/workflows/contracts.yml",
        "ledger_index_manifest.py",
        "check_ledger_alignment.py",
        "check_consistency.py",
        "check_versions.py",
        "check_structure.py",
        "check_scaffold.py",
        "check_public_docs.py",
        "Contract tests",
    ],
    DOCS_README_FILE: [
        "DEVLOG.md",
        "V1_SCOPE.md",
        "V1_TASK_TRIAGE.md",
        "02-V4-目录锁定清单.md",
        "04-V4-repo-hygiene-migration-plan.md",
        "06-V4-ledger-compat-index-spec.md",
        "08-V4-ledger-index-manifest.json",
        "20-V4-reference-compliance-rebaseline-record-20260329_030242.md",
        "selfcheck.py",
        "ledger_index_manifest.py",
        "check_ledger_alignment.py",
        "check_consistency.py",
        "check_versions.py",
        "check_structure.py",
        "check_scaffold.py",
        "check_public_docs.py",
        "tests/contracts/",
    ],
    DIRECTORY_LOCK_FILE: [
        "当前仓库的目录锁定依据",
        "迁移前临时保留",
        "docs/round_logs/",
        "specs/spi/keystore/",
        "04-V4-repo-hygiene-migration-plan.md",
        "06-V4-ledger-compat-index-spec.md",
        "08-V4-ledger-index-manifest.json",
    ],
    TOOLS_README_FILE: [
        "tools/checks/",
        "tools/codegen/",
        "selfcheck.py",
        "Current selfcheck policy",
        "ledger_index_manifest.py",
        "check_ledger_alignment.py",
        "check_consistency.py",
        "check_versions.py",
        "check_structure.py",
        "check_scaffold.py",
        "check_public_docs.py",
        "Contract tests",
    ],
    CHECKS_README_FILE: [
        "迁移期优先链路",
        "ledger_index_manifest.py",
        "check_consistency.py",
        "check_versions.py",
        "check_structure.py",
        "check_scaffold.py",
        "check_public_docs.py",
        "Contract tests",
    ],
    TESTS_README_FILE: [
        "tests/contracts/",
        "tests/fixtures/",
        "合同测试",
        "selfcheck.py",
        "ledger_index_manifest.py",
        "check_ledger_alignment.py",
        "check_consistency.py",
        "check_versions.py",
        "check_structure.py",
        "check_scaffold.py",
        "check_public_docs.py",
    ],
    OPERATOR_PLAYBOOK_FILE: [
        "verify",
        "tools\\checks\\selfcheck.py",
        "ledger_index_manifest.py",
        "check_ledger_alignment.py",
        "check_consistency.py",
        "check_versions.py",
        "check_structure.py",
        "check_scaffold.py",
        "check_public_docs.py",
        "Contract tests",
    ],
    MVP_README_FILE: [
        "tools/mvp/README.md",
        ".github/workflows/contracts.yml",
        "ledger_index_manifest.py",
        "check_ledger_alignment.py",
        "check_consistency.py",
        "check_versions.py",
        "check_structure.py",
        "check_scaffold.py",
        "check_public_docs.py",
        "Contract tests",
    ],
    LINT_README_FILE: [
        "tools/lint/check_naming.py",
        ".github/workflows/contracts.yml",
        "ledger_index_manifest.py",
        "check_ledger_alignment.py",
        "check_consistency.py",
        "check_versions.py",
        "check_structure.py",
        "check_scaffold.py",
        "check_public_docs.py",
        "Contract tests",
    ],
}

def collect_reference_rebaseline_errors() -> list[str]:
    if not REFERENCE_REBASELINE_FILE.exists():
        return [f"缺少公开文档: {REFERENCE_REBASELINE_FILE.relative_to(REPO_ROOT).as_posix()}"]

    text = REFERENCE_REBASELINE_FILE.read_text(encoding="utf-8")
    errors: list[str] = []
    required_markers = [
        "已经过期的旧结论",
        "目录锁定清单",
        "公开文档门禁",
        "docs/round_logs/",
        "先止血、后迁移",
    ]
    for marker in required_markers:
        if marker not in text:
            errors.append(
                f"公开文档缺少关键标记: {REFERENCE_REBASELINE_FILE.relative_to(REPO_ROOT).as_posix()} -> {marker}"
            )

    return errors


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

    errors.extend(collect_reference_rebaseline_errors())
    errors.extend(collect_ledger_errors())

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
