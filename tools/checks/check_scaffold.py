from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.checks.ledger_index_manifest import load_ledger_index_manifest

REQUIRED_DIRS = [
    "config/trusted_plugins",
    "generated/rust",
    "generated/python",
    "generated/ts",
    "modules/adapters",
    "modules/memory",
    "modules/plugins",
    "modules/repair_plans",
    "safeclaw-core/src",
    "safeclaw-core/tests",
    "tests/fixtures",
]
REQUIRED_FILES = [
    "config/README.md",
    "docs/README.md",
    "tests/README.md",
    "tools/README.md",
    "config/default_config.toml",
    "config/default_permissions.toml",
    "config/trusted_plugins/README.md",
    "generated/README.md",
    "generated/rust/README.md",
    "generated/python/README.md",
    "generated/ts/README.md",
    "modules/README.md",
    "modules/adapters/README.md",
    "modules/memory/README.md",
    "modules/plugins/README.md",
    "modules/repair_plans/README.md",
    "safeclaw-core/ARCHITECTURE.md",
    "safeclaw-core/Cargo.toml",
    "safeclaw-core/README.md",
    "safeclaw-core/src/lib.rs",
    "safeclaw-core/src/protocol.rs",
    "safeclaw-core/src/effect_ledger.rs",
    "safeclaw-core/src/task_concurrency.rs",
    "safeclaw-core/src/worker_lifecycle.rs",
    "safeclaw-core/src/spec_map.rs",
    "safeclaw-core/tests/protocol_contracts.rs",
    "tests/fixtures/README.md",
    "tools/schema_diff/README.md",
    "tools/codegen/README.md",
    "tools/checks/README.md",
    "tools/lint/README.md",
]
LEGACY_REQUIRED_STATES = {"legacy-only", "dual-readable"}
DIRECTORY_LOCK_FILE = REPO_ROOT / "docs" / "30-方案" / "02-V4-目录锁定清单.md"
REFERENCE_REQUIRED_FILES = [
    REPO_ROOT / "docs" / "reference" / "01-反屎山AI研发执行总纲（Codex专用浓缩对照版）.md",
    REPO_ROOT / "docs" / "reference" / "02-仓库卫生与命名规范.md",
]
ROOT_TEXT_POLICY_FILES = [
    REPO_ROOT / ".gitattributes",
]
ROOT_DIRECTORY_SECTION_TITLES = (
    "一、长期保留的根目录",
    "二、迁移前临时保留的根目录",
)
ROOT_FILE_SECTION_TITLES = (
    "三、长期保留的根文件",
    "四、迁移前临时保留的根文件",
)
DIRECTORY_LOCK_REQUIRED_MARKERS = (
    "docs/reference/02-仓库卫生与命名规范.md",
    "docs/reference/",
    "高优先级参考规范",
)
FORBIDDEN_NAME_TOKENS = ("最终版", "临时版", "new2", "test1")
ALLOWED_HIDDEN_ROOT_ENTRIES = {".github", ".gitattributes", ".gitignore"}
IGNORED_RUNTIME_DIR_NAMES = {"__pycache__"}
TMP_DISALLOWED_PREFIXES = ("round-log-",)


def normalize_locked_entry(entry: str) -> str:
    return entry.rstrip("/")


def extract_markdown_section_body(markdown_text: str, heading: str) -> str | None:
    pattern = re.compile(
        rf"^### {re.escape(heading)}\s*$\r?\n(?P<body>.*?)(?=^### |^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(markdown_text)
    if match is None:
        return None
    return match.group("body")


def extract_locked_entries(markdown_text: str, headings: tuple[str, ...]) -> set[str]:
    entries: set[str] = set()
    for heading in headings:
        body = extract_markdown_section_body(markdown_text, heading)
        if body is None:
            continue
        for entry in re.findall(r"`([^`]+)`", body):
            entries.add(normalize_locked_entry(entry))
    return entries


def load_locked_root_entries() -> tuple[set[str], set[str]]:
    if not DIRECTORY_LOCK_FILE.exists():
        return set(), set()

    markdown_text = DIRECTORY_LOCK_FILE.read_text(encoding="utf-8")
    root_dirs = extract_locked_entries(markdown_text, ROOT_DIRECTORY_SECTION_TITLES)
    root_files = extract_locked_entries(markdown_text, ROOT_FILE_SECTION_TITLES)
    return root_dirs, root_files


def iter_governed_root_entries() -> list[Path]:
    entries: list[Path] = []
    for path in REPO_ROOT.iterdir():
        if path.name in IGNORED_RUNTIME_DIR_NAMES:
            continue
        if path.name.startswith("."):
            if path.name in ALLOWED_HIDDEN_ROOT_ENTRIES:
                continue
            continue
        entries.append(path)
    return entries


def iter_governed_repo_paths() -> list[Path]:
    paths: list[Path] = []
    for path in REPO_ROOT.rglob("*"):
        rel_parts = path.relative_to(REPO_ROOT).parts
        if any(part in IGNORED_RUNTIME_DIR_NAMES for part in rel_parts):
            continue
        hidden_parts = [
            part
            for part in rel_parts
            if part.startswith(".") and part not in ALLOWED_HIDDEN_ROOT_ENTRIES
        ]
        if hidden_parts:
            continue
        paths.append(path)
    return paths


def collect_reference_file_errors() -> list[str]:
    errors: list[str] = []
    for path in REFERENCE_REQUIRED_FILES:
        if not path.exists():
            errors.append(f"缺少 reference 真源文件: {path.relative_to(REPO_ROOT).as_posix()}")
    return errors


def collect_root_text_policy_errors() -> list[str]:
    errors: list[str] = []
    for path in ROOT_TEXT_POLICY_FILES:
        if not path.exists():
            errors.append(f"缺少根级文本行尾策略文件: {path.relative_to(REPO_ROOT).as_posix()}")
    return errors


def collect_directory_lock_errors() -> list[str]:
    if not DIRECTORY_LOCK_FILE.exists():
        return [f"缺少目录锁定清单: {DIRECTORY_LOCK_FILE.relative_to(REPO_ROOT).as_posix()}"]

    text = DIRECTORY_LOCK_FILE.read_text(encoding="utf-8")
    errors: list[str] = []
    for marker in DIRECTORY_LOCK_REQUIRED_MARKERS:
        if marker not in text:
            errors.append(f"目录锁定清单缺少关键标记: {DIRECTORY_LOCK_FILE.relative_to(REPO_ROOT).as_posix()} -> {marker}")
    return errors


def collect_root_layout_errors() -> list[str]:
    locked_root_dirs, locked_root_files = load_locked_root_entries()
    errors: list[str] = []

    if not locked_root_dirs:
        errors.append("目录锁定清单未声明根目录白名单")
    if not locked_root_files:
        errors.append("目录锁定清单未声明根文件白名单")

    for path in iter_governed_root_entries():
        display_name = f"{path.name}/" if path.is_dir() else path.name
        if path.is_dir() and path.name not in locked_root_dirs:
            errors.append(f"根目录存在未锁定目录: {display_name}")
        if path.is_file() and path.name not in locked_root_files:
            errors.append(f"根目录存在未锁定文件: {display_name}")

    return errors


def collect_forbidden_name_errors() -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()

    for path in iter_governed_repo_paths():
        relpath = path.relative_to(REPO_ROOT).as_posix()
        for part in path.relative_to(REPO_ROOT).parts:
            lowered_part = part.lower()
            matched_token = next(
                (token for token in FORBIDDEN_NAME_TOKENS if token.lower() in lowered_part),
                None,
            )
            if matched_token is None:
                continue
            message = f"路径命名触发 reference 禁词: {relpath} -> {matched_token}"
            if message not in seen:
                seen.add(message)
                errors.append(message)
            break

    return errors


def collect_tmp_hygiene_errors() -> list[str]:
    tmp_root = REPO_ROOT / "tmp"
    if not tmp_root.exists():
        return []

    errors: list[str] = []
    for path in tmp_root.rglob("*"):
        if not path.is_file():
            continue
        if path.name.startswith(TMP_DISALLOWED_PREFIXES):
            errors.append(
                f"tmp 目录存在误放长期留痕: {path.relative_to(REPO_ROOT).as_posix()}"
            )
    return errors


def collect_reference_guardrail_errors() -> list[str]:
    errors: list[str] = []
    errors.extend(collect_reference_file_errors())
    errors.extend(collect_root_text_policy_errors())
    errors.extend(collect_directory_lock_errors())
    errors.extend(collect_root_layout_errors())
    errors.extend(collect_forbidden_name_errors())
    errors.extend(collect_tmp_hygiene_errors())
    return errors


def collect_ledger_scaffold_errors() -> list[str]:
    manifest = load_ledger_index_manifest()
    errors: list[str] = []

    for entry in manifest.ledgers:
        legacy_path = REPO_ROOT / entry.legacy_path
        if entry.cutover_state in LEGACY_REQUIRED_STATES:
            if legacy_path.parent != REPO_ROOT:
                errors.append(f"legacy 阶段台账必须保留在根目录: {entry.logical_id} -> {entry.legacy_path}")
            elif not legacy_path.exists():
                errors.append(f"legacy 阶段缺少根台账文件: {entry.logical_id} -> {entry.legacy_path}")
            elif not legacy_path.is_file():
                errors.append(f"legacy 阶段台账路径不是文件: {entry.logical_id} -> {entry.legacy_path}")

    return errors


def collect_errors() -> list[str]:
    errors: list[str] = []
    errors.extend(collect_reference_guardrail_errors())

    for relpath in REQUIRED_DIRS:
        path = REPO_ROOT / relpath
        if not path.exists():
            errors.append(f"缺少骨架目录: {relpath}")
        elif not path.is_dir():
            errors.append(f"骨架路径不是目录: {relpath}")

    for relpath in REQUIRED_FILES:
        path = REPO_ROOT / relpath
        if not path.exists():
            errors.append(f"缺少骨架文件: {relpath}")
        elif not path.is_file():
            errors.append(f"骨架路径不是文件: {relpath}")

    errors.extend(collect_ledger_scaffold_errors())
    return errors


def main() -> int:
    errors = collect_errors()
    if errors:
        print("Scaffold check failed:")
        for item in errors:
            print(f"- {item}")
        return 1

    print("Scaffold check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
