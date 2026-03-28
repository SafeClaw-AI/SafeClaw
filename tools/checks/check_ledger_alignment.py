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
