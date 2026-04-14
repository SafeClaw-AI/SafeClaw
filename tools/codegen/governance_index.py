from __future__ import annotations

import ast
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.checks.spec_index import SpecIndex, build_spec_index
from tools.codegen.main import (
    SUPPORTED_TARGETS,
    to_repo_posix,
    write_json_if_changed,
    write_text_if_changed,
)

DOC_FILE_SUFFIXES = {".json", ".md", ".toml"}
ROOT_SCAN_DIRS = (
    "specs",
    "docs",
    "tests",
    "tools",
    "modules",
    "config",
    "safeclaw-core",
    "safeclaw-sqlite",
    "generated",
)
ROOT_SSOT_FILES = (
    "README.md",
    "STATUS.md",
    "CHANGELOG.md",
    "DECISIONS.md",
    "ARCHITECTURE.md",
)
LEGACY_ROOT_RECORDS = (
    "开发计划.md",
    "MVP_PROGRESS.md",
    "PUSH_LOG.md",
)
L0_EXPLICIT_KINDS = {
    "VERSION": "protocol-version",
    "docs/30-方案/02-V4-目录锁定清单.md": "directory-lock",
    "docs/30-方案/08-V4-ledger-index-manifest.json": "ledger-index-manifest",
}
L3_PREFIXES = (
    "docs/records/",
    "docs/chancellor-mode/v2/",
)
L3_DOC_NAME_MARKERS = ("recheck", "rebaseline", "snapshot", "handoff", "progress")
TRACKED_PATH_PREFIXES = (
    "specs/",
    "generated/",
    "docs/",
    "config/",
    "modules/",
    "safeclaw-core/",
    "safeclaw-sqlite/",
    "tests/",
    "tools/",
)
TRACKED_SCENARIO_SUFFIXES = (".md", ".json", ".toml")
GOVERNANCE_GATE_KEYWORDS = (
    "selfcheck",
    "structure",
    "scaffold",
    "consistency",
    "ledger",
    "version",
    "reference",
)
RUNTIME_CONTRACT_KEYWORDS = (
    "probe",
    "effect",
    "fencing",
    "reconcile",
    "protocol",
    "worker",
    "task_queue",
    "mvp",
    "tooling",
    "personal",
    "code_agent",
    "skill",
    "claude_provider",
)
CONTRACTS_ROOT = REPO_ROOT / "tests" / "contracts"
IMPLEMENTATION_ROOTS = (
    REPO_ROOT / "safeclaw-core" / "src",
    REPO_ROOT / "safeclaw-sqlite" / "src",
    REPO_ROOT / "tools" / "mvp",
)
GOVERNANCE_ROOT = REPO_ROOT / "generated" / "governance"
DOC_INDEX_PATH = GOVERNANCE_ROOT / "doc_index.json"
SPEC_MAP_PATH = GOVERNANCE_ROOT / "spec_map.json"
TEST_MATRIX_PATH = GOVERNANCE_ROOT / "test_matrix.json"
README_STATUS_PATH = GOVERNANCE_ROOT / "README.md"
GOVERNANCE_OUTPUTS = (
    DOC_INDEX_PATH,
    SPEC_MAP_PATH,
    TEST_MATRIX_PATH,
    README_STATUS_PATH,
)
BASELINE_SPEC_TESTS = {
    "tests/contracts/test_specs_contracts.py",
    "tests/contracts/test_generated_indexes.py",
    "tests/contracts/test_governance_indexes.py",
    "tests/contracts/test_structure_check.py",
    "tests/contracts/test_version_check.py",
}


def _is_repo_doc_candidate(path: Path) -> bool:
    relpath = to_repo_posix(path)
    if relpath.startswith(("target/", "tmp/", "temp/", "assets/")):
        return False
    if any(part in {"__pycache__", ".pytest_cache", ".ruff_cache"} for part in path.parts):
        return False
    return path.is_file() and (path.suffix in DOC_FILE_SUFFIXES or path.name in {"README.md", "ARCHITECTURE.md"})


def iter_doc_candidate_paths() -> list[Path]:
    candidates: set[Path] = {REPO_ROOT / "VERSION", *GOVERNANCE_OUTPUTS}

    for relpath in ROOT_SSOT_FILES + LEGACY_ROOT_RECORDS:
        path = REPO_ROOT / relpath
        if path.exists():
            candidates.add(path)

    for root_name in ROOT_SCAN_DIRS:
        root = REPO_ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if _is_repo_doc_candidate(path):
                candidates.add(path)

    return sorted(candidates, key=to_repo_posix)


def _classify_l0(relpath: str, path: Path) -> dict[str, str] | None:
    if relpath in L0_EXPLICIT_KINDS:
        return {
            "layer": "L0",
            "kind": L0_EXPLICIT_KINDS[relpath],
            "group": "governance-truth",
            "rule": "explicit-truth",
        }
    if relpath.startswith("specs/") and path.suffix == ".json":
        family = path.parts[1] if len(path.parts) > 1 else "specs"
        return {
            "layer": "L0",
            "kind": f"spec-{family}",
            "group": family,
            "rule": "spec-json",
        }
    if relpath.startswith("docs/reference/"):
        return {
            "layer": "L0",
            "kind": "governance-reference",
            "group": "reference",
            "rule": "reference-doc",
        }
    if relpath.startswith("config/") and path.suffix == ".toml":
        return {
            "layer": "L0",
            "kind": "config-template",
            "group": "config",
            "rule": "config-template",
        }
    return None


def _classify_l1(relpath: str, path: Path) -> dict[str, str] | None:
    if relpath.startswith("generated/"):
        name = path.name
        if relpath.startswith("generated/governance/"):
            kind = "governance-readme" if name == "README.md" else "governance-index"
            group = "generated/governance"
        else:
            kind = "generated-readme" if name == "README.md" else "generated-index"
            group = relpath.split("/", 2)[1] if "/" in relpath else "generated"
        return {
            "layer": "L1",
            "kind": kind,
            "group": group,
            "rule": "generated-artifact",
        }
    return None


def _is_archive_doc(relpath: str, lowered_name: str) -> bool:
    if relpath in LEGACY_ROOT_RECORDS:
        return True
    if relpath.startswith(L3_PREFIXES):
        return True
    if relpath.startswith("docs/30-方案/") and relpath not in L0_EXPLICIT_KINDS:
        return True
    return relpath.startswith("docs/") and any(
        marker in lowered_name for marker in L3_DOC_NAME_MARKERS
    )


def _classify_l3(relpath: str, path: Path) -> dict[str, str] | None:
    lowered_name = path.name.lower()
    if not _is_archive_doc(relpath, lowered_name):
        return None
    return {
        "layer": "L3",
        "kind": "archive-record" if path.name.endswith(".md") else "archive-data",
        "group": path.parts[0] if path.parts else "archive",
        "rule": "archive-path",
    }


def _classify_l2(path: Path) -> dict[str, str]:
    name = path.name
    kind_by_name = {
        "STATUS.md": "status-board",
        "CHANGELOG.md": "changelog",
        "DECISIONS.md": "decision-log",
        "ARCHITECTURE.md": "architecture-guide",
        "README.md": "readme",
    }
    kind = kind_by_name.get(name, "guide")
    group = path.parts[0] if path.parts else "root"
    return {
        "layer": "L2",
        "kind": kind,
        "group": group,
        "rule": "active-doc",
    }


def classify_doc_path(relpath: str) -> dict[str, str]:
    path = Path(relpath)

    for classifier in (_classify_l0, _classify_l1, _classify_l3):
        classified = classifier(relpath, path)
        if classified is not None:
            return classified

    return _classify_l2(path)

def build_doc_index(repo_version: str) -> dict[str, Any]:
    entries = []
    for path in iter_doc_candidate_paths():
        relpath = to_repo_posix(path)
        classification = classify_doc_path(relpath)
        entry = {
            "path": relpath,
            "layer": classification["layer"],
            "kind": classification["kind"],
            "group": classification["group"],
            "rule": classification["rule"],
        }
        entries.append(entry)

    layer_counts = Counter(entry["layer"] for entry in entries)
    group_counts = Counter(entry["group"] for entry in entries)
    return {
        "protocol_version": repo_version,
        "entries": entries,
        "summary": {
            "layers": {layer: layer_counts.get(layer, 0) for layer in ("L0", "L1", "L2", "L3")},
            "groups": dict(sorted(group_counts.items())),
            "entry_count": len(entries),
        },
    }


def _normalize_path_constant(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.replace("\\", "/").strip()
    if normalized in {"VERSION", *ROOT_SSOT_FILES, *LEGACY_ROOT_RECORDS}:
        return normalized
    if normalized.endswith("/") and normalized.startswith(TRACKED_PATH_PREFIXES):
        return normalized
    if normalized.startswith(TRACKED_PATH_PREFIXES) and normalized.endswith(TRACKED_SCENARIO_SUFFIXES):
        return normalized
    return None


def _collect_import_refs(tree: ast.AST) -> list[str]:
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module:
                imports.add(module)
            for alias in node.names:
                qualified = f"{module}.{alias.name}".strip(".")
                if qualified:
                    imports.add(qualified)
    return sorted(imports)


def _collect_path_refs(tree: ast.AST) -> list[str]:
    refs: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant):
            normalized = _normalize_path_constant(node.value)
            if normalized is not None:
                refs.add(normalized)
    return sorted(refs)


def _is_truth_source_test(imports: list[str], path_refs: list[str]) -> bool:
    return any(ref == "VERSION" or ref.startswith("specs/") for ref in path_refs) or any(
        "spec_index" in item for item in imports
    )


def _is_derived_artifact_test(imports: list[str], path_refs: list[str]) -> bool:
    return any(ref.startswith("generated/") for ref in path_refs) or any(
        "tools.codegen" in item for item in imports
    )


def _is_documentation_governance_test(name: str, imports: list[str]) -> bool:
    return "public_docs" in name or any("check_public_docs" in item for item in imports)


def _contains_keyword(name: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in name for keyword in keywords)


def _classify_test_domains(relpath: str, imports: list[str], path_refs: list[str]) -> list[str]:
    name = Path(relpath).stem.lower()
    domains: set[str] = set()

    if _is_truth_source_test(imports, path_refs):
        domains.add("truth-source")

    if _is_derived_artifact_test(imports, path_refs):
        domains.add("derived-artifacts")

    if _is_documentation_governance_test(name, imports):
        domains.add("documentation-governance")

    if _contains_keyword(name, GOVERNANCE_GATE_KEYWORDS):
        domains.add("governance-gates")

    if _contains_keyword(name, RUNTIME_CONTRACT_KEYWORDS):
        domains.add("runtime-contracts")

    if not domains:
        domains.add("contract-suite")

    return sorted(domains)


def _classify_test_layers(path_refs: list[str], domains: list[str]) -> list[str]:
    layers = {
        classify_doc_path(ref)["layer"]
        for ref in path_refs
        if ref == "VERSION" or ref.endswith(TRACKED_SCENARIO_SUFFIXES)
    }
    if "truth-source" in domains:
        layers.add("L0")
    if "derived-artifacts" in domains:
        layers.add("L1")
    if "documentation-governance" in domains:
        layers.update({"L2", "L3"})
    return sorted(layers)


def iter_contract_test_paths() -> list[Path]:
    return sorted(CONTRACTS_ROOT.glob("test_*.py"), key=to_repo_posix)


def build_test_matrix(repo_version: str) -> dict[str, Any]:
    entries = []
    domain_counts: Counter[str] = Counter()
    for path in iter_contract_test_paths():
        relpath = to_repo_posix(path)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = _collect_import_refs(tree)
        path_refs = _collect_path_refs(tree)
        domains = _classify_test_domains(relpath, imports, path_refs)
        layers = _classify_test_layers(path_refs, domains)
        domain_counts.update(domains)
        entries.append(
            {
                "path": relpath,
                "domains": domains,
                "layers": layers,
                "imports": imports,
                "path_refs": path_refs,
            }
        )

    return {
        "protocol_version": repo_version,
        "tests": entries,
        "summary": {
            "test_count": len(entries),
            "domains": dict(sorted(domain_counts.items())),
        },
    }


def _collect_implementation_candidates(spec_relpath: str) -> list[str]:
    stem = Path(spec_relpath).stem.lower()
    tokens = [token for token in stem.split("_") if len(token) > 2]
    matches: set[str] = set()

    for path in _iter_implementation_files():
        if _matches_implementation_candidate(path, stem, tokens):
            matches.add(to_repo_posix(path))

    return sorted(matches)


def _iter_implementation_files() -> list[Path]:
    paths: list[Path] = []
    for root in IMPLEMENTATION_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in {".rs", ".py", ".pyw", ".ps1", ".cmd"}:
                paths.append(path)
    return paths


def _matches_implementation_candidate(path: Path, stem: str, tokens: list[str]) -> bool:
    file_stem = path.stem.lower()
    if file_stem == stem or stem in file_stem or file_stem in stem:
        return True
    return bool(tokens) and all(token in file_stem for token in tokens)


def _matches_schema_test(test_name: str, stem: str) -> bool:
    return (
        stem in test_name
        or "protocol" in test_name
        or any(token in test_name for token in ("effect", "task_queue", "worker_pool"))
    )


def _matches_family_test(family: str, stem: str, test_name: str) -> bool:
    family_rules = {
        "probes": lambda current_name: "probe" in current_name,
        "state-machines": lambda current_name: any(
            token in current_name for token in ("worker", "protocol", "reconcile")
        ),
        "schemas": lambda current_name: _matches_schema_test(current_name, stem),
        "config": lambda current_name: any(
            token in current_name for token in ("protocol", "mvp_state_guard", "mvp_operator_flow")
        ),
        "error-codes": lambda current_name: any(
            token in current_name for token in ("protocol", "specs", "version")
        ),
        "spi": lambda current_name: any(
            token in current_name for token in ("specs", "protocol", "skill")
        ),
    }
    rule = family_rules.get(family)
    return rule(test_name) if rule is not None else False


def _select_contract_tests_for_spec(spec_relpath: str, test_entries: list[dict[str, Any]]) -> list[str]:
    family = Path(spec_relpath).parts[1] if len(Path(spec_relpath).parts) > 1 else "specs"
    stem = Path(spec_relpath).stem.lower()
    related = set(BASELINE_SPEC_TESTS)

    for entry in test_entries:
        test_path = str(entry["path"])
        test_name = Path(test_path).stem.lower()
        path_refs = set(entry["path_refs"])

        if spec_relpath in path_refs:
            related.add(test_path)
            continue

        if _matches_family_test(family, stem, test_name):
            related.add(test_path)

    return sorted(related)


def build_spec_map(repo_version: str, index: SpecIndex, test_matrix: dict[str, Any]) -> dict[str, Any]:
    family_counts: Counter[str] = Counter()
    test_entries = test_matrix["tests"]
    entries = []
    for doc in index.documents:
        family = Path(doc.relpath).parts[1] if len(Path(doc.relpath).parts) > 1 else "specs"
        family_counts[family] += 1
        entries.append(
            {
                "relpath": doc.relpath,
                "layer": "L0",
                "family": family,
                "title": doc.title,
                "version": doc.version,
                "generated_targets": list(SUPPORTED_TARGETS),
                "generated_manifests": [f"generated/{target}/manifest.json" for target in SUPPORTED_TARGETS],
                "contract_tests": _select_contract_tests_for_spec(doc.relpath, test_entries),
                "implementation_candidates": _collect_implementation_candidates(doc.relpath),
            }
        )

    return {
        "protocol_version": repo_version,
        "spec_count": len(entries),
        "families": dict(sorted(family_counts.items())),
        "specs": entries,
    }


def build_governance_readme(
    doc_index: dict[str, Any],
    spec_map: dict[str, Any],
    test_matrix: dict[str, Any],
) -> str:
    layer_counts = doc_index["summary"]["layers"]
    family_counts = spec_map["families"]
    domain_counts = test_matrix["summary"]["domains"]

    family_summary = ", ".join(f"{name}={count}" for name, count in family_counts.items())
    domain_summary = ", ".join(f"{name}={count}" for name, count in domain_counts.items())

    return "\n".join(
        [
            "---",
            "slice: structured-governance-v100",
            "status: active",
            "generator: tools/codegen/governance_index.py",
            "outputs:",
            "  - generated/governance/doc_index.json",
            "  - generated/governance/spec_map.json",
            "  - generated/governance/test_matrix.json",
            "gate:",
            "  - tools/checks/check_governance_indexes.py",
            "contracts:",
            "  - tests/contracts/test_governance_indexes.py",
            "---",
            "",
            "# generated/governance/",
            "",
            "本目录由结构化治理生成链自动渲染，不手写维护。",
            "",
            "## Layer Summary",
            f"- L0: {layer_counts['L0']}",
            f"- L1: {layer_counts['L1']}",
            f"- L2: {layer_counts['L2']}",
            f"- L3: {layer_counts['L3']}",
            "",
            "## Outputs",
            "- `doc_index.json`: L0/L1/L2/L3 分层索引",
            "- `spec_map.json`: specs -> generated -> tests -> implementation 候选映射",
            "- `test_matrix.json`: contracts 结构化覆盖矩阵",
            "",
            "## Spec Summary",
            f"- spec_count: {spec_map['spec_count']}",
            f"- families: {family_summary}",
            "",
            "## Contract Summary",
            f"- test_count: {test_matrix['summary']['test_count']}",
            f"- domains: {domain_summary}",
            "",
            "## Gate",
            "- `python tools/checks/check_governance_indexes.py`",
            "- `python tools/checks/selfcheck.py`",
            "",
        ]
    )


def ensure_governance_outputs(out_root: Path, repo_version: str, index: SpecIndex) -> dict[str, str]:
    governance_root = out_root / "governance"
    governance_root.mkdir(parents=True, exist_ok=True)

    doc_index = build_doc_index(repo_version)
    test_matrix = build_test_matrix(repo_version)
    spec_map = build_spec_map(repo_version, index, test_matrix)
    readme = build_governance_readme(doc_index, spec_map, test_matrix)

    doc_index_path = governance_root / "doc_index.json"
    spec_map_path = governance_root / "spec_map.json"
    test_matrix_path = governance_root / "test_matrix.json"
    readme_path = governance_root / "README.md"

    write_json_if_changed(doc_index_path, doc_index)
    write_json_if_changed(spec_map_path, spec_map)
    write_json_if_changed(test_matrix_path, test_matrix)
    write_text_if_changed(readme_path, readme)

    return {
        "governance_dir": to_repo_posix(governance_root),
        "doc_index": to_repo_posix(doc_index_path),
        "spec_map": to_repo_posix(spec_map_path),
        "test_matrix": to_repo_posix(test_matrix_path),
        "readme": to_repo_posix(readme_path),
    }


def main() -> int:
    repo_version = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    index = build_spec_index()
    outputs = ensure_governance_outputs(REPO_ROOT / "generated", repo_version, index)
    print("SafeClaw governance indexes ready.")
    print(f"- governance_dir: {outputs['governance_dir']}")
    print(f"- doc_index: {outputs['doc_index']}")
    print(f"- spec_map: {outputs['spec_map']}")
    print(f"- test_matrix: {outputs['test_matrix']}")
    print(f"- readme: {outputs['readme']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
