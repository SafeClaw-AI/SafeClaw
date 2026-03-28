from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.checks.ledger_index_manifest import load_ledger_index_manifest
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
        "08-V4-ledger-index-manifest.json",
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

EXPECTED_LEDGER_BASELINE = {
    "dev-plan": {
        "legacy_path": "开发计划.md",
        "target_path": "docs/records/开发计划.md",
        "write_mode": "legacy-only",
        "cutover_state": "legacy-only",
    },
    "mvp-progress": {
        "legacy_path": "MVP_PROGRESS.md",
        "target_path": "docs/records/MVP_PROGRESS.md",
        "write_mode": "legacy-only",
        "cutover_state": "legacy-only",
    },
    "push-log": {
        "legacy_path": "PUSH_LOG.md",
        "target_path": "docs/records/PUSH_LOG.md",
        "write_mode": "legacy-only",
        "cutover_state": "legacy-only",
    },
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

    manifest = load_ledger_index_manifest()
    if manifest.manifest_id != "safeclaw-ledger-index":
        errors.append(f"台账索引 manifest_id 异常: {manifest.manifest_id}")
    for logical_id, expected in EXPECTED_LEDGER_BASELINE.items():
        entry = manifest.require(logical_id)
        for key, expected_value in expected.items():
            actual_value = getattr(entry, key)
            if actual_value != expected_value:
                errors.append(
                    f"台账索引基线不一致: {logical_id}.{key} -> {actual_value} != {expected_value}"
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
