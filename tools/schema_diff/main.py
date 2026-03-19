from __future__ import annotations

import argparse
import json
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="SafeClaw schema diff 入口（Phase 0 空壳）",
    )
    parser.add_argument("old", help="旧 schema 文件或目录")
    parser.add_argument("new", help="新 schema 文件或目录")
    return parser


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise TypeError(f"顶层必须是 object: {path}")
    return data


def load_dir(root: Path) -> dict[str, dict]:
    return {
        item.relative_to(root).as_posix(): load_json(item)
        for item in sorted(root.rglob("*.json"))
    }


def diff_directories(old_root: Path, new_root: Path) -> int:
    old_docs = load_dir(old_root)
    new_docs = load_dir(new_root)
    old_paths = set(old_docs)
    new_paths = set(new_docs)
    added = sorted(new_paths - old_paths)
    removed = sorted(old_paths - new_paths)
    changed = sorted(path for path in old_paths & new_paths if old_docs[path] != new_docs[path])

    print("SafeClaw schema diff stub ready.")
    print(f"- mode: directory")
    print(f"- old_root: {old_root}")
    print(f"- new_root: {new_root}")
    print(f"- added_files: {len(added)}")
    print(f"- removed_files: {len(removed)}")
    print(f"- changed_files: {len(changed)}")

    for path in added:
        print(f"  + {path}")
    for path in removed:
        print(f"  - {path}")
    for path in changed:
        old_version = old_docs[path].get("version", "<missing>")
        new_version = new_docs[path].get("version", "<missing>")
        print(f"  * {path} :: {old_version} -> {new_version}")

    return 0


def diff_files(old_path: Path, new_path: Path) -> int:
    old_doc = load_json(old_path)
    new_doc = load_json(new_path)
    old_keys = set(old_doc)
    new_keys = set(new_doc)
    added_keys = sorted(new_keys - old_keys)
    removed_keys = sorted(old_keys - new_keys)
    common_changed = sorted(
        key for key in old_keys & new_keys if old_doc[key] != new_doc[key]
    )

    print("SafeClaw schema diff stub ready.")
    print("- mode: file")
    print(f"- old_file: {old_path}")
    print(f"- new_file: {new_path}")
    print(f"- added_keys: {len(added_keys)}")
    print(f"- removed_keys: {len(removed_keys)}")
    print(f"- changed_keys: {len(common_changed)}")

    for key in added_keys:
        print(f"  + {key}")
    for key in removed_keys:
        print(f"  - {key}")
    for key in common_changed:
        print(f"  * {key}")

    return 0


def main() -> int:
    args = build_parser().parse_args()
    old_path = Path(args.old).resolve()
    new_path = Path(args.new).resolve()

    if not old_path.exists():
        raise FileNotFoundError(f"旧路径不存在: {old_path}")
    if not new_path.exists():
        raise FileNotFoundError(f"新路径不存在: {new_path}")

    if old_path.is_dir() and new_path.is_dir():
        return diff_directories(old_path, new_path)
    if old_path.is_file() and new_path.is_file():
        return diff_files(old_path, new_path)

    raise ValueError("old/new 必须同为目录或同为文件")


if __name__ == "__main__":
    raise SystemExit(main())
