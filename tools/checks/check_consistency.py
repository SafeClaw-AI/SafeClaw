from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.checks.ledger_index_manifest import load_ledger_index_manifest
from tools.checks.spec_index import build_spec_index

LEDGER_COMPAT_SPEC_FILE = REPO_ROOT / "docs" / "30-方案" / "06-V4-ledger-compat-index-spec.md"


def collect_ledger_manifest_doc_errors() -> list[str]:
    manifest = load_ledger_index_manifest()
    spec_text = LEDGER_COMPAT_SPEC_FILE.read_text(encoding="utf-8")
    errors: list[str] = []

    for entry in manifest.ledgers:
        mapping_line = f"- `{entry.logical_id}`：`{entry.legacy_path}` -> `{entry.target_path}`"
        if mapping_line not in spec_text:
            errors.append(f"台账映射未写入兼容索引方案: {mapping_line}")

        if entry.cutover_state == "legacy-only":
            if "### Phase A：当前阶段" not in spec_text:
                errors.append("兼容索引方案缺少 Phase A：当前阶段")
            if "- 只读旧路径" not in spec_text:
                errors.append("兼容索引方案缺少 legacy-only 只读旧路径说明")

    return errors


def collect_errors() -> list[str]:
    index = build_spec_index()
    errors: list[str] = []

    action_tiers = index.require("specs/schemas/action_tiers.json").data
    effect_ledger = index.require("specs/schemas/effect_ledger.json").data
    worker = index.require("specs/state-machines/worker_lifecycle.json").data
    preflight = index.require("specs/config/preflight.json").data
    sys_errors = index.require("specs/error-codes/sys_errors.json").data

    tier_ids = {
        entry["tier_id"]
        for entry in action_tiers.get("tiers", {}).values()
        if isinstance(entry, dict) and "tier_id" in entry
    }
    rev_ids = {
        entry["rev_id"]
        for entry in action_tiers.get("reversibility", {}).values()
        if isinstance(entry, dict) and "rev_id" in entry
    }

    effect_props = effect_ledger.get("properties", {})
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

    matrix = action_tiers.get("orthogonal_matrix", [])
    for index_no, row in enumerate(matrix, start=1):
        tier = row.get("tier")
        reversibility = row.get("reversibility")
        if tier not in tier_ids:
            errors.append(f"orthogonal_matrix[{index_no}] tier 未定义: {tier}")
        if reversibility not in rev_ids:
            errors.append(f"orthogonal_matrix[{index_no}] reversibility 未定义: {reversibility}")

    preflight_rules = action_tiers.get("preflight_rules", {})
    default_tier = preflight_rules.get("unknown_action_default_tier")
    if default_tier not in tier_ids:
        errors.append(f"preflight_rules.unknown_action_default_tier 未定义: {default_tier}")

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

    error_categories = set(sys_errors.get("categories", []))
    for key, value in sys_errors.get("errors", {}).items():
        category = value.get("category")
        if category not in error_categories:
            errors.append(f"{key} category 未在 categories 中注册: {category}")

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
