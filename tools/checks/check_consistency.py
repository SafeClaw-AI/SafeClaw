from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.checks.ledger_index_manifest import load_ledger_index_manifest
from tools.checks.spec_index import build_spec_index

LEDGER_COMPAT_SPEC_FILE = REPO_ROOT / "docs" / "30-方案" / "06-V4-ledger-compat-index-spec.md"

LEDGER_DOC_REQUIREMENTS_BY_STATE = {
    "legacy-only": (
        ("### Phase A：当前阶段", "兼容索引方案缺少 Phase A：当前阶段"),
        ("- 只读旧路径", "兼容索引方案缺少 legacy-only 只读旧路径说明"),
    ),
    "dual-readable": (
        ("### Phase B：兼容阶段", "兼容索引方案缺少 Phase B：兼容阶段"),
        ("- 优先读新路径", "兼容索引方案缺少 dual-readable 优先读新路径说明"),
    ),
    "target-primary": (
        ("### Phase C：切换完成", "兼容索引方案缺少 Phase C：切换完成"),
        ("- 只读新路径", "兼容索引方案缺少 target-primary 只读新路径说明"),
        (
            "旧路径只允许保留跳转说明或迁移标记",
            "兼容索引方案缺少 legacy-retired 旧路径跳转说明",
        ),
    ),
    "legacy-retired": (
        ("### Phase C：切换完成", "兼容索引方案缺少 Phase C：切换完成"),
        ("- 只读新路径", "兼容索引方案缺少 target-primary 只读新路径说明"),
        (
            "旧路径只允许保留跳转说明或迁移标记",
            "兼容索引方案缺少 legacy-retired 旧路径跳转说明",
        ),
    ),
}


def _collect_missing_doc_errors(
    spec_text: str,
    requirements: tuple[tuple[str, str], ...],
) -> list[str]:
    errors: list[str] = []
    for marker, message in requirements:
        if marker not in spec_text:
            errors.append(message)
    return errors


def _collect_mapping_doc_errors(entry: object, spec_text: str) -> list[str]:
    mapping_line = f"- `{entry.logical_id}`：`{entry.legacy_path}` -> `{entry.target_path}`"
    if mapping_line in spec_text:
        return []
    return [f"台账映射未写入兼容索引方案: {mapping_line}"]


def _collect_cutover_state_doc_errors(cutover_state: str, spec_text: str) -> list[str]:
    requirements = LEDGER_DOC_REQUIREMENTS_BY_STATE.get(cutover_state, ())
    return _collect_missing_doc_errors(spec_text, requirements)


def collect_ledger_manifest_doc_errors() -> list[str]:
    manifest = load_ledger_index_manifest()
    spec_text = LEDGER_COMPAT_SPEC_FILE.read_text(encoding="utf-8")
    errors: list[str] = []

    for entry in manifest.ledgers:
        errors.extend(_collect_mapping_doc_errors(entry, spec_text))
        errors.extend(_collect_cutover_state_doc_errors(entry.cutover_state, spec_text))

    return errors


def _collect_registered_ids(entries: dict[str, object], field_name: str) -> set[str]:
    identifiers: set[str] = set()
    for entry in entries.values():
        if isinstance(entry, dict) and field_name in entry:
            identifiers.add(entry[field_name])
    return identifiers


def _collect_effect_enum_errors(
    effect_props: dict[str, object],
    tier_ids: set[str],
    rev_ids: set[str],
) -> list[str]:
    errors: list[str] = []
    effect_tiers = set(effect_props.get("tier", {}).get("enum", []))
    effect_revs = set(effect_props.get("reversibility", {}).get("enum", []))

    if effect_tiers != tier_ids:
        errors.append(
            f"effect_ledger tier enums 与 action_tiers tier_ids 不一致: {sorted(effect_tiers)} != {sorted(tier_ids)}"
        )
    if effect_revs != rev_ids:
        errors.append(
            f"effect_ledger reversibility enums 与 action_tiers rev_ids 不一致: {sorted(effect_revs)} != {sorted(rev_ids)}"
        )

    return errors


def _collect_orthogonal_matrix_errors(
    matrix: list[dict[str, object]],
    tier_ids: set[str],
    rev_ids: set[str],
) -> list[str]:
    errors: list[str] = []
    for index_no, row in enumerate(matrix, start=1):
        tier = row.get("tier")
        reversibility = row.get("reversibility")
        if tier not in tier_ids:
            errors.append(f"orthogonal_matrix[{index_no}] tier 未定义: {tier}")
        if reversibility not in rev_ids:
            errors.append(f"orthogonal_matrix[{index_no}] reversibility 未定义: {reversibility}")
    return errors


def _collect_unknown_action_default_tier_errors(
    preflight_rules: dict[str, object],
    tier_ids: set[str],
) -> list[str]:
    default_tier = preflight_rules.get("unknown_action_default_tier")
    if default_tier in tier_ids:
        return []
    return [f"preflight_rules.unknown_action_default_tier 未定义: {default_tier}"]


def collect_action_tier_alignment_errors(index: object) -> list[str]:
    action_tiers = index.require("specs/schemas/action_tiers.json").data
    effect_ledger = index.require("specs/schemas/effect_ledger.json").data
    tier_ids = _collect_registered_ids(action_tiers.get("tiers", {}), "tier_id")
    rev_ids = _collect_registered_ids(action_tiers.get("reversibility", {}), "rev_id")

    effect_props = effect_ledger.get("properties", {})
    matrix = action_tiers.get("orthogonal_matrix", [])
    preflight_rules = action_tiers.get("preflight_rules", {})
    errors: list[str] = []
    errors.extend(_collect_effect_enum_errors(effect_props, tier_ids, rev_ids))
    errors.extend(_collect_orthogonal_matrix_errors(matrix, tier_ids, rev_ids))
    errors.extend(_collect_unknown_action_default_tier_errors(preflight_rules, tier_ids))
    return errors


def collect_worker_lifecycle_alignment_errors(index: object) -> list[str]:
    worker = index.require("specs/state-machines/worker_lifecycle.json").data
    errors: list[str] = []

    states = worker.get("states", {})
    state_names = set(states.keys())
    state_ids = {state["state_id"] for state in states.values()}
    if len(state_names) != len(state_ids):
        errors.append("worker states 与 state_id 不是一一映射")

    terminal_names = set(worker.get("terminal_states", []))
    for name in terminal_names:
        if name not in state_names:
            errors.append(f"terminal state 未定义: {name}")
        elif not states[name].get("terminal"):
            errors.append(f"terminal state 未标记 terminal=true: {name}")

    for transition in worker.get("transitions", []):
        event_id = transition.get("event_id", "<missing>")
        from_state = transition.get("from")
        to_state = transition.get("to")
        if from_state not in state_names:
            errors.append(f"{event_id} from 未定义: {from_state}")
        if to_state not in state_names:
            errors.append(f"{event_id} to 未定义: {to_state}")

    return errors


def collect_sys_error_category_alignment_errors(index: object) -> list[str]:
    sys_errors = index.require("specs/error-codes/sys_errors.json").data
    errors: list[str] = []

    error_categories = set(sys_errors.get("categories", []))
    for key, value in sys_errors.get("errors", {}).items():
        category = value.get("category")
        if category not in error_categories:
            errors.append(f"{key} category 未在 categories 中注册: {category}")

    return errors


def collect_errors() -> list[str]:
    index = build_spec_index()
    errors: list[str] = []
    errors.extend(collect_action_tier_alignment_errors(index))
    errors.extend(collect_worker_lifecycle_alignment_errors(index))
    errors.extend(collect_sys_error_category_alignment_errors(index))
    errors.extend(collect_ledger_manifest_doc_errors())
    return errors


def main() -> int:
    errors = collect_errors()
    if errors:
        print("Cross-file consistency check failed:")
        for item in errors:
            print(f"- {item}")
        return 1

    print("Cross-file consistency check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
