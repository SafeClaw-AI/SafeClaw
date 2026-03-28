from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.checks.ledger_index_manifest import load_ledger_index_manifest
from tools.checks.spec_index import build_spec_index

VERSION_FILE = REPO_ROOT / "VERSION"
README_FILE = REPO_ROOT / "README.md"
SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
LEDGER_SLICE_A_PHASE = "slice-a-baseline"


def read_repo_version() -> str:
    return VERSION_FILE.read_text(encoding="utf-8").strip()


def collect_ledger_version_errors() -> list[str]:
    manifest = load_ledger_index_manifest()
    errors: list[str] = []

    if not SEMVER_PATTERN.fullmatch(manifest.manifest_version):
        errors.append(f"ledger manifest_version 不是 x.y.z 语义版本: {manifest.manifest_version}")

    all_legacy_only = all(entry.cutover_state == "legacy-only" for entry in manifest.ledgers)
    if all_legacy_only and manifest.phase != LEDGER_SLICE_A_PHASE:
        errors.append(
            f"所有台账仍为 legacy-only 时，phase 必须为 {LEDGER_SLICE_A_PHASE}: {manifest.phase}"
        )

    if manifest.phase == LEDGER_SLICE_A_PHASE and not all_legacy_only:
        errors.append(
            f"phase={LEDGER_SLICE_A_PHASE} 时不应出现非 legacy-only 台账"
        )

    return errors


def collect_errors() -> list[str]:
    repo_version = read_repo_version()
    errors: list[str] = []

    if not repo_version:
        errors.append("VERSION 文件为空")
        return errors

    if not SEMVER_PATTERN.fullmatch(repo_version):
        errors.append(f"VERSION 不是 x.y.z 语义版本: {repo_version}")

    index = build_spec_index()
    for doc in index.documents:
        if doc.version is None:
            errors.append(f"spec 缺少 version: {doc.relpath}")
            continue
        if doc.version != repo_version:
            errors.append(
                f"spec version 与 VERSION 不一致: {doc.relpath} -> {doc.version} != {repo_version}"
            )

    readme_text = README_FILE.read_text(encoding="utf-8")
    if repo_version not in readme_text:
        errors.append(f"README.md 未包含当前版本号: {repo_version}")

    errors.extend(collect_ledger_version_errors())
    return errors


def main() -> int:
    errors = collect_errors()
    if errors:
        print("Version consistency check failed:")
        for item in errors:
            print(f"- {item}")
        return 1

    print(f"Version consistency check passed: {read_repo_version()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
