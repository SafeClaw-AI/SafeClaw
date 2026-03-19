from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="SafeClaw schema diff 工具",
    )
    parser.add_argument("old", help="旧 schema 文件或目录")
    parser.add_argument("new", help="新 schema 文件或目录")
    parser.add_argument(
        "--json-out",
        help="可选：将 diff 结果写入 JSON 文件",
    )
    parser.add_argument(
        "--fail-on-diff",
        action="store_true",
        help="若检测到差异则返回非 0，用于自动化门禁。",
    )
    return parser


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise TypeError(f"顶层必须是 object: {path}")
    return data


def load_dir(root: Path) -> dict[str, dict[str, Any]]:
    return {
        item.relative_to(root).as_posix(): load_json(item)
        for item in sorted(root.rglob("*.json"))
    }


def summarize_directories(old_root: Path, new_root: Path) -> dict[str, Any]:
    old_docs = load_dir(old_root)
    new_docs = load_dir(new_root)
    old_paths = set(old_docs)
    new_paths = set(new_docs)
    added = sorted(new_paths - old_paths)
    removed = sorted(old_paths - new_paths)
    changed = sorted(path for path in old_paths & new_paths if old_docs[path] != new_docs[path])

    return {
        "mode": "directory",
        "old_root": str(old_root),
        "new_root": str(new_root),
        "added_files": added,
        "removed_files": removed,
        "changed_files": [
            {
                "path": path,
                "old_version": old_docs[path].get("version", "<missing>"),
                "new_version": new_docs[path].get("version", "<missing>"),
            }
            for path in changed
        ],
    }


def summarize_files(old_path: Path, new_path: Path) -> dict[str, Any]:
    old_doc = load_json(old_path)
    new_doc = load_json(new_path)
    old_keys = set(old_doc)
    new_keys = set(new_doc)
    added_keys = sorted(new_keys - old_keys)
    removed_keys = sorted(old_keys - new_keys)
    changed_keys = sorted(key for key in old_keys & new_keys if old_doc[key] != new_doc[key])

    return {
        "mode": "file",
        "old_file": str(old_path),
        "new_file": str(new_path),
        "added_keys": added_keys,
        "removed_keys": removed_keys,
        "changed_keys": changed_keys,
    }


def has_diff(summary: dict[str, Any]) -> bool:
    if summary.get("mode") == "directory":
        return bool(
            summary.get("added_files")
            or summary.get("removed_files")
            or summary.get("changed_files")
        )
    return bool(
        summary.get("added_keys")
        or summary.get("removed_keys")
        or summary.get("changed_keys")
    )


def print_summary(summary: dict[str, Any]) -> None:
    print("SafeClaw schema diff ready.")
    print(f"- mode: {summary['mode']}")
    if summary["mode"] == "directory":
        print(f"- old_root: {summary['old_root']}")
        print(f"- new_root: {summary['new_root']}")
        print(f"- added_files: {len(summary['added_files'])}")
        print(f"- removed_files: {len(summary['removed_files'])}")
        print(f"- changed_files: {len(summary['changed_files'])}")
        for path in summary["added_files"]:
            print(f"  + {path}")
        for path in summary["removed_files"]:
            print(f"  - {path}")
        for item in summary["changed_files"]:
            print(f"  * {item['path']} :: {item['old_version']} -> {item['new_version']}")
        return

    print(f"- old_file: {summary['old_file']}")
    print(f"- new_file: {summary['new_file']}")
    print(f"- added_keys: {len(summary['added_keys'])}")
    print(f"- removed_keys: {len(summary['removed_keys'])}")
    print(f"- changed_keys: {len(summary['changed_keys'])}")
    for key in summary["added_keys"]:
        print(f"  + {key}")
    for key in summary["removed_keys"]:
        print(f"  - {key}")
    for key in summary["changed_keys"]:
        print(f"  * {key}")


def write_json_output(path: Path, payload: dict[str, Any]) -> None:
    content = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.write_text(content, encoding="utf-8")


def main() -> int:
    args = build_parser().parse_args()
    old_path = Path(args.old).resolve()
    new_path = Path(args.new).resolve()

    if not old_path.exists():
        raise FileNotFoundError(f"旧路径不存在: {old_path}")
    if not new_path.exists():
        raise FileNotFoundError(f"新路径不存在: {new_path}")

    if old_path.is_dir() and new_path.is_dir():
        summary = summarize_directories(old_path, new_path)
    elif old_path.is_file() and new_path.is_file():
        summary = summarize_files(old_path, new_path)
    else:
        raise ValueError("old/new 必须同为目录或同为文件")

    print_summary(summary)

    if args.json_out:
        write_json_output(Path(args.json_out).resolve(), summary)

    if args.fail_on_diff and has_diff(summary):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
