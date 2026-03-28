from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
LEDGER_INDEX_MANIFEST_FILE = REPO_ROOT / "docs" / "30-方案" / "08-V4-ledger-index-manifest.json"
_ALLOWED_READ_ORDER_VALUES = {"legacy_path", "target_path"}
_ALLOWED_WRITE_MODES = {"legacy-only", "target-primary"}
_ALLOWED_CUTOVER_STATES = {"legacy-only", "dual-readable", "target-primary", "legacy-retired"}


@dataclass(frozen=True)
class LedgerEntry:
    logical_id: str
    legacy_path: str
    target_path: str
    read_order: tuple[str, ...]
    write_mode: str
    cutover_state: str


@dataclass(frozen=True)
class LedgerIndexManifest:
    manifest_version: str
    manifest_id: str
    phase: str
    description: str
    ledgers: tuple[LedgerEntry, ...]
    conflict_policy: dict[str, str]

    @property
    def by_logical_id(self) -> dict[str, LedgerEntry]:
        return {entry.logical_id: entry for entry in self.ledgers}

    def require(self, logical_id: str) -> LedgerEntry:
        try:
            return self.by_logical_id[logical_id]
        except KeyError as exc:
            raise KeyError(f"缺少台账索引项: {logical_id}") from exc


def _require_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"字段必须是非空字符串: {key}")
    return value


def _load_ledger_entry(payload: dict[str, Any]) -> LedgerEntry:
    logical_id = _require_string(payload, "logical_id")
    legacy_path = _require_string(payload, "legacy_path")
    target_path = _require_string(payload, "target_path")
    read_order = payload.get("read_order")
    if not isinstance(read_order, list) or not read_order:
        raise TypeError(f"read_order 必须是非空数组: {logical_id}")
    read_order_values = tuple(str(item) for item in read_order)
    if any(item not in _ALLOWED_READ_ORDER_VALUES for item in read_order_values):
        raise ValueError(f"read_order 含非法值: {logical_id}")
    write_mode = _require_string(payload, "write_mode")
    if write_mode not in _ALLOWED_WRITE_MODES:
        raise ValueError(f"write_mode 非法: {logical_id}")
    cutover_state = _require_string(payload, "cutover_state")
    if cutover_state not in _ALLOWED_CUTOVER_STATES:
        raise ValueError(f"cutover_state 非法: {logical_id}")
    return LedgerEntry(
        logical_id=logical_id,
        legacy_path=legacy_path,
        target_path=target_path,
        read_order=read_order_values,
        write_mode=write_mode,
        cutover_state=cutover_state,
    )


def load_ledger_index_manifest(path: Path = LEDGER_INDEX_MANIFEST_FILE) -> LedgerIndexManifest:
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        raise TypeError("ledger index manifest 顶层必须是 object")

    manifest_version = _require_string(payload, "manifest_version")
    manifest_id = _require_string(payload, "manifest_id")
    phase = _require_string(payload, "phase")
    description = _require_string(payload, "description")

    ledgers_payload = payload.get("ledgers")
    if not isinstance(ledgers_payload, list) or not ledgers_payload:
        raise TypeError("ledgers 必须是非空数组")
    ledgers = tuple(_load_ledger_entry(item) for item in ledgers_payload)
    logical_ids = [entry.logical_id for entry in ledgers]
    if len(logical_ids) != len(set(logical_ids)):
        raise ValueError("logical_id 不可重复")

    conflict_policy = payload.get("conflict_policy")
    if not isinstance(conflict_policy, dict):
        raise TypeError("conflict_policy 必须是 object")
    normalized_conflict_policy = {str(key): str(value) for key, value in conflict_policy.items()}
    for required_key in (
        "on_divergence",
        "on_missing_target_when_legacy_only",
        "on_missing_target_when_target_primary",
    ):
        if required_key not in normalized_conflict_policy:
            raise KeyError(f"conflict_policy 缺少字段: {required_key}")

    return LedgerIndexManifest(
        manifest_version=manifest_version,
        manifest_id=manifest_id,
        phase=phase,
        description=description,
        ledgers=ledgers,
        conflict_policy=normalized_conflict_policy,
    )


def main() -> int:
    manifest = load_ledger_index_manifest()
    print(
        f"Loaded {len(manifest.ledgers)} ledger entries from "
        f"{LEDGER_INDEX_MANIFEST_FILE.relative_to(REPO_ROOT).as_posix()}"
    )
    for entry in manifest.ledgers:
        print(
            f"- {entry.logical_id}: {entry.legacy_path} -> {entry.target_path} "
            f"[{entry.cutover_state}]"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
