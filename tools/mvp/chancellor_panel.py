from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEV_PLAN_FILE = REPO_ROOT / "开发计划.md"
CHANCELLOR_STATUS_COMMAND = "丞相状态"


def normalize_markdown_inline_code(text: str) -> str:
    return re.sub(r"`([^`]+)`", r"\1", text).strip()


def extract_markdown_labeled_value(markdown_text: str, label: str) -> str:
    prefix = f"{label}："
    for line in markdown_text.splitlines():
        if line.startswith(prefix):
            return normalize_markdown_inline_code(line.split(prefix, 1)[1].strip())
    raise ValueError(f"missing labeled value: {label}")


def derive_chancellor_stability(stage_text: str) -> str:
    if any(token in stage_text for token in ("阻塞", "失败", "未通过", "卡住")):
        return "存在阻塞"
    if any(token in stage_text for token in ("已毕业", "全绿", "已完成")):
        return "稳态"
    if any(token in stage_text for token in ("收口", "尾段")):
        return "收口中"
    return "推进中"


def extract_chancellor_next_step(stage_text: str, mode_text: str) -> str:
    if "下一步" not in stage_text:
        return f"继续推进 {mode_text}"
    next_step_text = stage_text.split("下一步", 1)[1].lstrip("：:，,；; ").strip()
    if not next_step_text:
        return f"继续推进 {mode_text}"
    return next_step_text


def build_chancellor_status_snapshot(dev_plan_text: str | None = None) -> dict[str, str]:
    if dev_plan_text is None:
        dev_plan_text = DEV_PLAN_FILE.read_text(encoding="utf-8")
    mode_text = extract_markdown_labeled_value(dev_plan_text, "当前主线")
    stage_text = extract_markdown_labeled_value(dev_plan_text, "当前阶段")
    stability = derive_chancellor_stability(stage_text)
    next_step = extract_chancellor_next_step(stage_text, mode_text)
    return {
        "mode": mode_text,
        "stability": stability,
        "next_step": next_step,
        "summary": f"当前处于 {mode_text}；状态{stability}；下一步{next_step}",
    }


def normalize_chancellor_panel_command_text(command_text: str) -> str:
    return command_text.strip()


def build_chancellor_panel_command_payload(
    command_text: str,
    dev_plan_text: str | None = None,
) -> dict[str, str]:
    normalized_command_text = normalize_chancellor_panel_command_text(command_text)
    if normalized_command_text != CHANCELLOR_STATUS_COMMAND:
        raise ValueError(f"unsupported chancellor panel command: {normalized_command_text or '<empty>'}")
    snapshot = build_chancellor_status_snapshot(dev_plan_text=dev_plan_text)
    return {
        "command": CHANCELLOR_STATUS_COMMAND,
        "summary": snapshot["summary"],
        "mode": snapshot["mode"],
        "stability": snapshot["stability"],
        "next_step": snapshot["next_step"],
    }


def main(argv: list[str]) -> int:
    payload = (
        build_chancellor_panel_command_payload(" ".join(argv[1:]))
        if len(argv) > 1
        else build_chancellor_status_snapshot()
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
