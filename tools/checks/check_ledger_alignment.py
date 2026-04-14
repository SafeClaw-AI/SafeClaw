from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.checks.ledger_index_manifest import load_ledger_index_manifest

QUESTION_MARK_FORBIDDEN = {
    "mvp-progress": True,
    "push-log": True,
}

ROOT_COMPAT_STUB_REQUIRED_MARKERS = {
    "dev-plan": [
        "# 开发计划（兼容入口）",
        "当前计划台账真源已迁至 `docs/records/开发计划.md`。",
        "当前根文件只保留兼容跳转说明，不再作为更新真源。",
        "- `logical_id`: `dev-plan`",
        "- `target_path`: `docs/records/开发计划.md`",
        "- `write_mode`: `target-primary`",
        "- `cutover_state`: `legacy-retired`",
        "1. `docs/30-方案/08-V4-ledger-index-manifest.json`",
        "2. `docs/records/开发计划.md`",
        "如需继续推进 README V14 主线，请在 `docs/records/开发计划.md` 上更新，而不是回写本根文件。",
    ],
    "mvp-progress": [
        "# 整体计划实现进展表（兼容入口）",
        "当前进展台账真源已迁至 `docs/records/MVP_PROGRESS.md`。",
        "当前根文件只保留兼容跳转说明，不再作为更新真源。",
        "- `logical_id`: `mvp-progress`",
        "- `target_path`: `docs/records/MVP_PROGRESS.md`",
        "- `write_mode`: `target-primary`",
        "- `cutover_state`: `legacy-retired`",
        "1. `docs/30-方案/08-V4-ledger-index-manifest.json`",
        "2. `docs/records/MVP_PROGRESS.md`",
        "如需继续推进 README V14 主线，请在 `docs/records/MVP_PROGRESS.md` 上更新，而不是回写本根文件。",
    ],
    "push-log": [
        "# 提交推送流水账（兼容入口）",
        "当前推送流水真源已迁至 `docs/records/PUSH_LOG.md`。",
        "当前根文件只保留兼容跳转说明，不再作为更新真源。",
        "- `logical_id`: `push-log`",
        "- `target_path`: `docs/records/PUSH_LOG.md`",
        "- `write_mode`: `target-primary`",
        "- `cutover_state`: `legacy-retired`",
        "1. `docs/30-方案/08-V4-ledger-index-manifest.json`",
        "2. `docs/records/PUSH_LOG.md`",
        "如需继续推进 README V14 主线，请在 `docs/records/PUSH_LOG.md` 上更新，而不是回写本根文件。",
    ],
}

ROOT_COMPAT_STUB_FORBIDDEN_MARKERS = (
    "## 一、当前已知稳定事实",
    "## 二、当前状态",
    "## 进展",
    "## 流水",
    "当前边界说明（2026-04-04）",
    "当前提交执行摘要（2026-04-04）",
    "当前收口总览（2026-04-04）",
)

LEDGER_REQUIRED_MARKERS = {
    "dev-plan": [
        "# 开发计划",
        "当前主线",
        "## 三、下一候选",
        "## 五、执行约束",
    ],
    "mvp-progress": [
        "整体计划实现进展表",
        "当前阶段",
        "当前预估",
        "## 进展",
    ],
    "push-log": [
        "提交推送流水账",
        "## 记录规则",
        "## 流水",
    ],
}

EXPECTED_LEDGER_BASELINE = {
    "dev-plan": {
        "legacy_path": "开发计划.md",
        "target_path": "docs/records/开发计划.md",
        "write_mode": "target-primary",
        "cutover_state": "legacy-retired",
    },
    "mvp-progress": {
        "legacy_path": "MVP_PROGRESS.md",
        "target_path": "docs/records/MVP_PROGRESS.md",
        "write_mode": "target-primary",
        "cutover_state": "legacy-retired",
    },
    "push-log": {
        "legacy_path": "PUSH_LOG.md",
        "target_path": "docs/records/PUSH_LOG.md",
        "write_mode": "target-primary",
        "cutover_state": "legacy-retired",
    },
}


def collect_root_compat_stub_errors(manifest, repo_root: Path = REPO_ROOT) -> list[str]:
    errors: list[str] = []

    for logical_id, markers in ROOT_COMPAT_STUB_REQUIRED_MARKERS.items():
        entry = manifest.require(logical_id)
        legacy_path = repo_root / entry.legacy_path
        if not legacy_path.exists():
            errors.append(
                f"根兼容入口缺失: {entry.legacy_path}"
            )
            continue

        text = legacy_path.read_text(encoding="utf-8")
        legacy_display = legacy_path.relative_to(repo_root).as_posix()
        for marker in markers:
            if marker not in text:
                errors.append(
                    f"根兼容入口缺少关键标记: {legacy_display} -> {marker}"
                )
        for marker in ROOT_COMPAT_STUB_FORBIDDEN_MARKERS:
            if marker in text:
                errors.append(
                    f"根兼容入口出现旧正文标记: {legacy_display} -> {marker}"
                )

    return errors


def collect_ledger_errors() -> list[str]:
    manifest = load_ledger_index_manifest()
    errors: list[str] = []

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

    errors.extend(collect_root_compat_stub_errors(manifest, REPO_ROOT))

    for logical_id, markers in LEDGER_REQUIRED_MARKERS.items():
        resolved_path, text = manifest.read_resolved_text(logical_id)
        for marker in markers:
            if marker not in text:
                errors.append(
                    f"台账缺少关键标记: {resolved_path.relative_to(REPO_ROOT).as_posix()} -> {marker}"
                )
        if QUESTION_MARK_FORBIDDEN.get(logical_id) and ("?" in text or "�" in text):
            errors.append(
                f"台账疑似编码损坏: {resolved_path.relative_to(REPO_ROOT).as_posix()} 含有意外占位符"
            )

    return errors


def main() -> int:
    errors = collect_ledger_errors()
    if errors:
        print("Ledger alignment check failed:")
        for item in errors:
            print(f"- {item}")
        return 1

    print("Ledger alignment check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
