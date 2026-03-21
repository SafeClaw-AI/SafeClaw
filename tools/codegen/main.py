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


def write_text_if_changed(path: Path, content: str) -> None:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.write_text(content, encoding="utf-8")


def to_repo_posix(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


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


def build_root_readme() -> str:
    return """# generated/

本目录用于承接由 `specs/` 自动生成的产物。

当前阶段保留最小稳定索引与目标子目录，供 contracts-gate 与后续 codegen 演进使用。

## 目标子目录

- `generated/rust/`：Rust 类型与契约映射
- `generated/python/`：Python 类型与运行时辅助对象
- `generated/ts/`：TypeScript 类型与前端契约映射

## 规则

- 本目录内容由工具生成，不手写维护
- 当前最小稳定索引为 `generated/index.json`、各目标下的 `manifest.json` 与 `stable_ids.json`
- 更完整的类型与运行时代码生成将在 M1 继续扩展
"""


def build_target_readme(target: str) -> str:
    labels = {
        "rust": "Rust 类型与契约映射",
        "python": "Python 类型与辅助运行时对象",
        "ts": "TypeScript 类型与前端契约映射",
    }
    label = labels[target]
    return f"""# generated/{target}/

当前包含由 `tools/codegen/` 生成的最小稳定索引：

- `manifest.json`
- `stable_ids.json`

后续将继续扩展为 {label}。
"""


def ensure_target_outputs(target: str, out_root: Path, repo_version: str, index: Any) -> dict[str, str]:
    target_dir = out_root / target
    target_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = target_dir / "manifest.json"
    stable_ids_path = target_dir / "stable_ids.json"
    target_readme_path = target_dir / "README.md"
    write_json_if_changed(manifest_path, build_manifest(target, repo_version, index))
    write_json_if_changed(stable_ids_path, build_stable_ids(index))
    write_text_if_changed(target_readme_path, build_target_readme(target))
    return {
        "target": target,
        "target_dir": to_repo_posix(target_dir),
        "manifest": to_repo_posix(manifest_path),
        "stable_ids": to_repo_posix(stable_ids_path),
    }


def build_generated_index(repo_version: str, outputs: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "protocol_version": repo_version,
        "targets": outputs,
    }


def build_targets_index(outputs: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "targets": outputs,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="SafeClaw codegen 入口（生成最小稳定索引）",
    )
    parser.add_argument(
        "--target",
        choices=SUPPORTED_TARGETS,
        required=True,
        help="生成目标子目录下的最小契约索引。",
    )
    parser.add_argument(
        "--out-dir",
        default="generated",
        help="输出目录，默认生成到仓库内的 generated/。",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    index = build_spec_index()
    repo_version = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    out_dir = Path(args.out_dir)
    out_root = out_dir if out_dir.is_absolute() else REPO_ROOT / out_dir
    out_root.mkdir(parents=True, exist_ok=True)
    output = ensure_target_outputs(args.target, out_root, repo_version, index)
    root_index_path = out_root / "index.json"
    root_index_alias_path = out_root / "root_index.json"
    targets_index_path = out_root / "targets.json"
    root_readme_path = out_root / "README.md"
    payload = build_generated_index(repo_version, [output])
    write_json_if_changed(root_index_path, payload)
    write_json_if_changed(root_index_alias_path, payload)
    write_json_if_changed(targets_index_path, build_targets_index([output]))
    write_text_if_changed(root_readme_path, build_root_readme())

    print("SafeClaw codegen stub ready.")
    print(f"- target: {args.target}")
    print(f"- out_dir: {to_repo_posix(out_root)}")
    print(f"- target_dir: {output['target_dir']}")
    print(f"- manifest: {output['manifest']}")
    print(f"- stable_ids: {output['stable_ids']}")
    print(f"- root_index: {to_repo_posix(root_index_path)}")
    print(f"- specs_loaded: {len(index.documents)}")
    print("- status: Phase 0 协议层已接入，已生成最小稳定索引，代码生成将在 M1 继续扩展。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
