from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.checks.spec_index import build_spec_index
from tools.codegen.governance_index import (
    DOC_INDEX_PATH,
    README_STATUS_PATH,
    SPEC_MAP_PATH,
    TEST_MATRIX_PATH,
    build_doc_index,
    build_governance_readme,
    build_spec_map,
    build_test_matrix,
)

REQUIRED_LAYER_PATHS = {
    "L0": "VERSION",
    "L1": "generated/governance/doc_index.json",
    "L2": "README.md",
    "L3": "docs/records/开发计划.md",
}


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise TypeError(f"JSON 顶层必须是 object: {path}")
    return data


def _build_expected_payloads() -> tuple[dict, dict, dict, str]:
    repo_version = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    index = build_spec_index()
    expected_doc_index = build_doc_index(repo_version)
    expected_test_matrix = build_test_matrix(repo_version)
    expected_spec_map = build_spec_map(repo_version, index, expected_test_matrix)
    expected_readme = build_governance_readme(
        expected_doc_index,
        expected_spec_map,
        expected_test_matrix,
    )
    return expected_doc_index, expected_test_matrix, expected_spec_map, expected_readme


def _collect_payload_errors(
    expected_doc_index: dict,
    expected_test_matrix: dict,
    expected_spec_map: dict,
    expected_readme: str,
) -> list[str]:
    errors: list[str] = []

    expected_json_files = {
        DOC_INDEX_PATH: expected_doc_index,
        SPEC_MAP_PATH: expected_spec_map,
        TEST_MATRIX_PATH: expected_test_matrix,
    }
    for path, expected_payload in expected_json_files.items():
        if not path.exists():
            errors.append(f"缺少治理索引: {path.relative_to(REPO_ROOT).as_posix()}")
            continue
        actual_payload = load_json(path)
        if actual_payload != expected_payload:
            errors.append(f"治理索引与当前仓结构不一致: {path.relative_to(REPO_ROOT).as_posix()}")

    if not README_STATUS_PATH.exists():
        errors.append(f"缺少治理 README: {README_STATUS_PATH.relative_to(REPO_ROOT).as_posix()}")
    else:
        actual_readme = README_STATUS_PATH.read_text(encoding="utf-8")
        if actual_readme != expected_readme:
            errors.append("治理 README 与当前仓结构不一致: generated/governance/README.md")
    return errors


def _collect_structure_errors(expected_doc_index: dict) -> list[str]:
    errors: list[str] = []
    doc_entries = {
        entry["path"]: entry["layer"]
        for entry in expected_doc_index.get("entries", [])
    }
    for layer, relpath in REQUIRED_LAYER_PATHS.items():
        if doc_entries.get(relpath) != layer:
            errors.append(f"治理索引缺少关键分层: {relpath} -> {layer}")

    layer_counts = expected_doc_index.get("summary", {}).get("layers", {})
    for layer in ("L0", "L1", "L2", "L3"):
        if layer_counts.get(layer, 0) <= 0:
            errors.append(f"治理索引分层为空: {layer}")
    return errors


def collect_errors() -> list[str]:
    expected_doc_index, expected_test_matrix, expected_spec_map, expected_readme = _build_expected_payloads()
    errors = _collect_payload_errors(
        expected_doc_index,
        expected_test_matrix,
        expected_spec_map,
        expected_readme,
    )
    errors.extend(_collect_structure_errors(expected_doc_index))
    return errors


def main() -> int:
    errors = collect_errors()
    if errors:
        print("Governance indexes check failed:")
        for item in errors:
            print(f"- {item}")
        return 1

    print("Governance indexes check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
