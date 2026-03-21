from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.checks.spec_index import build_spec_index
from tools.codegen.main import (
    REPO_ROOT as CODEGEN_REPO_ROOT,
    SUPPORTED_TARGETS,
    build_generated_index,
    build_root_readme,
    build_targets_index,
    ensure_target_outputs,
    to_repo_posix,
    write_json_if_changed,
    write_text_if_changed,
)


def main() -> int:
    index = build_spec_index()
    repo_version = (CODEGEN_REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    out_root = CODEGEN_REPO_ROOT / "generated"
    out_root.mkdir(parents=True, exist_ok=True)
    outputs = [
        ensure_target_outputs(target, out_root, repo_version, index)
        for target in SUPPORTED_TARGETS
    ]
    root_index_path = out_root / "index.json"
    root_index_alias_path = out_root / "root_index.json"
    targets_index_path = out_root / "targets.json"
    root_readme_path = out_root / "README.md"
    payload = build_generated_index(repo_version, outputs)
    write_json_if_changed(root_index_path, payload)
    write_json_if_changed(root_index_alias_path, payload)
    write_json_if_changed(targets_index_path, build_targets_index(outputs))
    write_text_if_changed(root_readme_path, build_root_readme())

    print("SafeClaw codegen sync ready.")
    print(f"- out_root: {to_repo_posix(out_root)}")
    print(f"- root_index: {to_repo_posix(root_index_path)}")
    print(f"- targets: {', '.join(SUPPORTED_TARGETS)}")
    print(f"- specs_loaded: {len(index.documents)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
