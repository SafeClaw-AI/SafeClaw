from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.checks.spec_index import build_spec_index

SPEC_FILE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*\.json$")
SPEC_DIR_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
STATE_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
STATE_ID_PATTERN = re.compile(r"^ST_[A-Z0-9_]+$")
EVENT_ID_PATTERN = re.compile(r"^EV_[A-Z0-9_]+$")
TIER_KEY_PATTERN = re.compile(r"^tier_[0-9]+$")
TIER_ID_PATTERN = re.compile(r"^TIER_[0-9]+$")
REV_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
REV_ID_PATTERN = re.compile(r"^REV_[A-Z0-9_]+$")
ERROR_CODE_PATTERN = re.compile(r"^E_[A-Z0-9_]+$")
SPI_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
ACTION_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def collect_errors() -> list[str]:
    index = build_spec_index()
    errors: list[str] = []

    for doc in index.documents:
        spec_path = Path(doc.relpath)
        if not SPEC_FILE_PATTERN.fullmatch(spec_path.name):
            errors.append(f"spec 文件名不符合规范: {doc.relpath}")
        for part in spec_path.parts[:-1]:
            if part == "specs":
                continue
            if not SPEC_DIR_PATTERN.fullmatch(part):
                errors.append(f"spec 目录名不符合规范: {doc.relpath} -> {part}")

    worker = index.require("specs/state-machines/worker_lifecycle.json").data
    for state_name, state_data in worker.get("states", {}).items():
        if not STATE_NAME_PATTERN.fullmatch(state_name):
            errors.append(f"state 名称不符合规范: {state_name}")
        state_id = state_data.get("state_id")
        if not isinstance(state_id, str) or not STATE_ID_PATTERN.fullmatch(state_id):
            errors.append(f"state_id 不符合规范: {state_name} -> {state_id}")

    for transition in worker.get("transitions", []):
        event_id = transition.get("event_id")
        if not isinstance(event_id, str) or not EVENT_ID_PATTERN.fullmatch(event_id):
            errors.append(f"event_id 不符合规范: {event_id}")

    action_tiers = index.require("specs/schemas/action_tiers.json").data
    for tier_key, tier_data in action_tiers.get("tiers", {}).items():
        if not TIER_KEY_PATTERN.fullmatch(tier_key):
            errors.append(f"tier key 不符合规范: {tier_key}")
        tier_id = tier_data.get("tier_id")
        if not isinstance(tier_id, str) or not TIER_ID_PATTERN.fullmatch(tier_id):
            errors.append(f"tier_id 不符合规范: {tier_key} -> {tier_id}")

    for rev_key, rev_data in action_tiers.get("reversibility", {}).items():
        if not REV_KEY_PATTERN.fullmatch(rev_key):
            errors.append(f"reversibility key 不符合规范: {rev_key}")
        rev_id = rev_data.get("rev_id")
        if not isinstance(rev_id, str) or not REV_ID_PATTERN.fullmatch(rev_id):
            errors.append(f"rev_id 不符合规范: {rev_key} -> {rev_id}")

    sys_errors = index.require("specs/error-codes/sys_errors.json").data
    for error_code in sys_errors.get("errors", {}):
        if not ERROR_CODE_PATTERN.fullmatch(error_code):
            errors.append(f"error code 不符合规范: {error_code}")

    effect = index.require("specs/schemas/effect_ledger.json").data
    action_enum = effect.get("properties", {}).get("action", {}).get("enum", [])
    for action_name in action_enum:
        if not isinstance(action_name, str) or not ACTION_NAME_PATTERN.fullmatch(action_name):
            errors.append(f"effect action 名称不符合规范: {action_name}")

    spi = index.require("specs/spi/base_fields.json").data
    for item in spi.get("registry", []):
        spi_name = item.get("spi_name")
        if not isinstance(spi_name, str) or not SPI_NAME_PATTERN.fullmatch(spi_name):
            errors.append(f"spi_name 不符合规范: {spi_name}")

    return errors


def main() -> int:
    errors = collect_errors()
    if errors:
        print("Naming lint failed:")
        for item in errors:
            print(f"- {item}")
        return 1

    print("Naming lint passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
