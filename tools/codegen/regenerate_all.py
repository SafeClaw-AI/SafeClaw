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
    ensure_target_outputs,
    write_json_if_changed,
)


def main() -> int:
    index = build_spec_index()
    repo_version = (CODEGEN_REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    out_root = (CODEGEN_REPO_ROOT / "generated").resolve()
    outputs = [
        ensure_target_outputs(target, out_root, repo_version, index)
        for target in SUPPORTED_TARGETS
    ]
    root_index_path = out_root / "index.json"
    write_json_if_changed(root_index_path, build_generated_index(repo_version, outputs))

    print("SafeClaw codegen sync ready.")
    print(f"- out_root: {out_root}")
    print(f"- root_index: {root_index_path}")
    print(f"- targets: {', '.join(SUPPORTED_TARGETS)}")
    print(f"- specs_loaded: {len(index.documents)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
