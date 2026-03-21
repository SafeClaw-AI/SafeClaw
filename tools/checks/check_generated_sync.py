from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.checks.spec_index import build_spec_index
from tools.codegen.main import (
    SUPPORTED_TARGETS,
    build_generated_index,
    build_manifest,
    build_stable_ids,
    build_targets_index,
    to_repo_posix,
)

VERSION_FILE = REPO_ROOT / "VERSION"
GENERATED_ROOT = REPO_ROOT / "generated"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise TypeError(f"JSON 顶层必须是 object: {path}")
    return data


def is_relative_posix_path(value: object) -> bool:
    return (
        isinstance(value, str)
        and not value.startswith("/")
        and "\\" not in value
        and not (len(value) >= 2 and value[1] == ":" and value[0].isalpha())
    )


def validate_target_outputs(source: str, outputs: list[dict[str, object]], errors: list[str]) -> None:
    for item in outputs:
        target = item.get("target", "<unknown>")
        for key in ("target_dir", "manifest", "stable_ids"):
            value = item.get(key)
            if not is_relative_posix_path(value):
                errors.append(f"{source} 含非相对 POSIX 路径: target={target} field={key} value={value}")


def collect_errors() -> list[str]:
    repo_version = VERSION_FILE.read_text(encoding="utf-8").strip()
    index = build_spec_index()
    errors: list[str] = []

    expected_stable_ids = build_stable_ids(index)
    expected_outputs: list[dict[str, str]] = []

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
        expected_outputs.append(
            {
                "target": target,
                "target_dir": to_repo_posix(target_dir),
                "manifest": to_repo_posix(manifest_path),
                "stable_ids": to_repo_posix(stable_ids_path),
            }
        )
        actual_manifest = load_json(manifest_path)
        actual_stable_ids = load_json(stable_ids_path)

        if actual_manifest != expected_manifest:
            errors.append(f"manifest 与当前 specs 不一致: {manifest_path.relative_to(REPO_ROOT).as_posix()}")
        if actual_stable_ids != expected_stable_ids:
            errors.append(f"stable_ids 与当前 specs 不一致: {stable_ids_path.relative_to(REPO_ROOT).as_posix()}")

        for spec in actual_manifest.get("specs", []):
            relpath = spec.get("relpath")
            if not is_relative_posix_path(relpath):
                errors.append(
                    f"manifest 含非相对 POSIX relpath: {manifest_path.relative_to(REPO_ROOT).as_posix()} value={relpath}"
                )

    expected_root_index = build_generated_index(repo_version, expected_outputs)
    expected_targets_index = build_targets_index(expected_outputs)
    index_specs = [
        ("generated 根索引", GENERATED_ROOT / "index.json", expected_root_index),
        ("generated 根索引别名", GENERATED_ROOT / "root_index.json", expected_root_index),
        ("generated targets 索引", GENERATED_ROOT / "targets.json", expected_targets_index),
    ]

    for label, path, expected_payload in index_specs:
        if not path.exists():
            errors.append(f"缺少生成产物: {path.relative_to(REPO_ROOT).as_posix()}")
            continue

        actual_payload = load_json(path)
        if actual_payload != expected_payload:
            errors.append(f"{label}与当前 specs 不一致: {path.relative_to(REPO_ROOT).as_posix()}")

        targets = actual_payload.get("targets", [])
        if not isinstance(targets, list):
            errors.append(f"{label} 的 targets 字段不是数组: {path.relative_to(REPO_ROOT).as_posix()}")
            continue
        validate_target_outputs(label, targets, errors)

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
