from __future__ import annotations

import subprocess
from collections import OrderedDict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BOUNDARY_GOVERNANCE_GROUP = "边界治理"
SELFCHECK_GOVERNANCE_GROUP = "自检治理"
PERSONAL_DEPLOY_GROUP = "个人部署链"
UNCLASSIFIED_GROUP = "未归类"
GROUP_RULES: "OrderedDict[str, dict[str, tuple[str, ...]]]" = OrderedDict(
    [
        (
            BOUNDARY_GOVERNANCE_GROUP,
            {
                "exact": (
                    "开发计划.md",
                    "MVP_PROGRESS.md",
                    "PUSH_LOG.md",
                    "docs/README.md",
                    "docs/30-方案/02-V4-目录锁定清单.md",
                    "docs/reference/02-仓库卫生与命名规范.md",
                    "tools/checks/check_public_docs.py",
                    "tools/mvp/chancellor_panel.py",
                    "tests/contracts/test_chancellor_panel.py",
                    "tests/contracts/test_public_docs_check.py",
                ),
                "prefix": ("docs/chancellor-mode/v2/",),
            },
        ),
        (
            SELFCHECK_GOVERNANCE_GROUP,
            {
                "exact": (
                    ".gitattributes",
                    "tools/checks/README.md",
                    "tools/checks/check_scaffold.py",
                    "tools/checks/selfcheck.py",
                    "tests/contracts/test_scaffold_check.py",
                    "tests/contracts/test_selfcheck.py",
                    "tools/checks/worktree_groups.py",
                    "tests/contracts/test_worktree_groups.py",
                ),
                "prefix": (),
            },
        ),
        (
            PERSONAL_DEPLOY_GROUP,
            {
                "exact": (
                    "tools/mvp/safeclaw_personal_deploy.py",
                    "tests/contracts/test_safeclaw_personal_deploy.py",
                ),
                "prefix": ("temp/parked-root/round-log-",),
            },
        ),
    ]
)


def normalize_relpath(relpath: str) -> str:
    normalized = relpath.strip()
    if normalized.startswith('"') and normalized.endswith('"'):
        normalized = normalized[1:-1]
    return normalized.replace("\\", "/")


def parse_status_line(line: str) -> tuple[str, str]:
    status = line[:2].strip() or line[:2]
    relpath = line[3:].strip()
    if " -> " in relpath:
        relpath = relpath.split(" -> ", 1)[1]
    return status, normalize_relpath(relpath)


def classify_path(relpath: str) -> str:
    normalized = normalize_relpath(relpath)
    for group_name, rules in GROUP_RULES.items():
        if normalized in rules["exact"]:
            return group_name
        if any(normalized.startswith(prefix) for prefix in rules["prefix"]):
            return group_name
    return UNCLASSIFIED_GROUP


def collect_dirty_worktree_entries() -> list[tuple[str, str]]:
    completed = subprocess.run(
        ["git", "-c", "core.quotepath=false", "status", "--short"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "git status failed").strip())
    entries: list[tuple[str, str]] = []
    for line in completed.stdout.splitlines():
        if not line.strip():
            continue
        entries.append(parse_status_line(line))
    return entries


def group_dirty_worktree_entries(
    entries: list[tuple[str, str]],
) -> "OrderedDict[str, list[tuple[str, str]]]":
    grouped: "OrderedDict[str, list[tuple[str, str]]]" = OrderedDict(
        (group_name, []) for group_name in [*GROUP_RULES.keys(), UNCLASSIFIED_GROUP]
    )
    for status, relpath in entries:
        grouped[classify_path(relpath)].append((status, relpath))
    return grouped


def render_grouped_entries(grouped: "OrderedDict[str, list[tuple[str, str]]]") -> str:
    non_empty_groups = [(name, items) for name, items in grouped.items() if items]
    if not non_empty_groups:
        return "工作区干净：当前没有未提交改动。"

    total_entries = sum(len(items) for _, items in non_empty_groups)
    group_summary = "，".join(f"{group_name} {len(items)}" for group_name, items in non_empty_groups)
    unclassified_count = len(grouped[UNCLASSIFIED_GROUP])
    if unclassified_count:
        unclassified_summary = f"有 {unclassified_count} 项，收口前需要继续处理。"
    else:
        unclassified_summary = "0 项，当前没有超出既定治理范围的改动。"

    lines = [
        "当前脏工作区摘要：",
        f"- 总改动：{total_entries}",
        f"- 分组：{group_summary}",
        f"- 未归类：{unclassified_summary}",
        "- 收口判断：改动已按治理分组归拢，可按分组逐项验证。",
        "",
        "详细清单：",
    ]
    for group_name, items in non_empty_groups:
        lines.append(f"- {group_name}（{len(items)}）")
        for status, relpath in items:
            lines.append(f"  {status} {relpath}")
    return "\n".join(lines)


def main() -> int:
    entries = collect_dirty_worktree_entries()
    grouped = group_dirty_worktree_entries(entries)
    print(render_grouped_entries(grouped))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
