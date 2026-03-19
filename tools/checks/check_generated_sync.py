from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.checks.spec_index import build_spec_index
from tools.codegen.main import SUPPORTED_TARGETS, build_manifest, build_stable_ids

VERSION_FILE = REPO_ROOT / "VERSION"
GENERATED_ROOT = REPO_ROOT / "generated"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise TypeError(f"JSON 顶层必须是 object: {path}")
    return data


def collect_errors() -> list[str]:
    repo_version = VERSION_FILE.read_text(encoding="utf-8").strip()
    index = build_spec_index()
    errors: list[str] = []

    expected_stable_ids = build_stable_ids(index)

    for target in SUPPORTED_TARGETS:
        target_dir = GENERATED_ROOT / target
        manifest_path = target_dir / "manifest.json"
        stable_ids_path = target_dir / "stable_ids.json"

        if not manifest_path.exists():
            errors.append(f"缺少生成产物: {manifest_path.relative_to(REPO_ROOT).as_posix()}")
            continue
        if not stable_ids_path.exists():
            errors.append(f"缺少生成产物: {stable_ids_path.relative_to(REPO_ROOT).as_posix()}")
            continue

        expected_manifest = build_manifest(target, repo_version, index)
        actual_manifest = load_json(manifest_path)
        actual_stable_ids = load_json(stable_ids_path)

        if actual_manifest != expected_manifest:
            errors.append(f"manifest 与当前 specs 不一致: {manifest_path.relative_to(REPO_ROOT).as_posix()}")
        if actual_stable_ids != expected_stable_ids:
            errors.append(f"stable_ids 与当前 specs 不一致: {stable_ids_path.relative_to(REPO_ROOT).as_posix()}")

    return errors


def main() -> int:
    errors = collect_errors()
    if errors:
        print("Generated sync check failed:")
        for item in errors:
            print(f"- {item}")
        return 1

    print("Generated sync check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
