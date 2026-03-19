from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.checks.spec_index import build_spec_index

SUPPORTED_TARGETS = ("rust", "python", "ts")


def write_json_if_changed(path: Path, payload: dict[str, Any]) -> None:
    content = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.write_text(content, encoding="utf-8")


def build_manifest(target: str, repo_version: str, index: Any) -> dict[str, Any]:
    return {
        "protocol_version": repo_version,
        "target": target,
        "spec_count": len(index.documents),
        "specs": [
            {
                "relpath": doc.relpath,
                "id": doc.data.get("$id"),
                "title": doc.title,
                "version": doc.version,
            }
            for doc in index.documents
        ],
    }


def build_stable_ids(index: Any) -> dict[str, Any]:
    worker = index.require("specs/state-machines/worker_lifecycle.json").data
    action_tiers = index.require("specs/schemas/action_tiers.json").data
    sys_errors = index.require("specs/error-codes/sys_errors.json").data
    spi = index.require("specs/spi/base_fields.json").data

    return {
        "worker": {
            "state_ids": {
                name: value["state_id"]
                for name, value in worker.get("states", {}).items()
            },
            "event_ids": [
                item["event_id"] for item in worker.get("transitions", [])
            ],
            "terminal_states": worker.get("terminal_states", []),
        },
        "tiers": {
            name: value["tier_id"]
            for name, value in action_tiers.get("tiers", {}).items()
        },
        "reversibility": {
            name: value["rev_id"]
            for name, value in action_tiers.get("reversibility", {}).items()
        },
        "error_codes": sorted(sys_errors.get("errors", {}).keys()),
        "spi_names": [item["spi_name"] for item in spi.get("registry", [])],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="SafeClaw codegen 入口（Phase 0 空壳）",
    )
    parser.add_argument(
        "--target",
        choices=SUPPORTED_TARGETS,
        required=True,
        help="预留生成目标，目前只做契约装载校验。",
    )
    parser.add_argument(
        "--out-dir",
        default="generated",
        help="预留输出目录，当前不写入任何文件。",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    index = build_spec_index()
    repo_version = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    out_root = (REPO_ROOT / args.out_dir).resolve()
    target_dir = out_root / args.target
    target_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = target_dir / "manifest.json"
    stable_ids_path = target_dir / "stable_ids.json"
    write_json_if_changed(manifest_path, build_manifest(args.target, repo_version, index))
    write_json_if_changed(stable_ids_path, build_stable_ids(index))

    print("SafeClaw codegen stub ready.")
    print(f"- target: {args.target}")
    print(f"- out_dir: {out_root}")
    print(f"- target_dir: {target_dir}")
    print(f"- manifest: {manifest_path}")
    print(f"- stable_ids: {stable_ids_path}")
    print(f"- specs_loaded: {len(index.documents)}")
    print("- status: Phase 0 协议层已接入，已生成最小稳定索引，代码生成将在 M1 继续扩展。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
