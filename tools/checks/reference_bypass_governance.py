from __future__ import annotations

import io
import re
import tokenize
from dataclasses import dataclass
from pathlib import Path

from tools.checks.file_scan import iter_repo_files

REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_BYPASS_WHITELIST_FILE = REPO_ROOT / "docs" / "reference" / "03-绕过白名单.md"

NOQA_BYPASS = "noqa"
PRAGMA_NO_COVER_BYPASS = "pragma_no_cover"
TYPE_IGNORE_BYPASS = "type_ignore"
UNITTEST_SKIP_BYPASS = "unittest_skip"
PYTEST_SKIP_BYPASS = "pytest_skip"
NOLINT_BYPASS = "nolint"
WARNING_FILTER_BYPASS = "warning_filter"
PYTHON_COMMENT_ONLY_BYPASS_KEYS = frozenset(
    {
        NOQA_BYPASS,
        PRAGMA_NO_COVER_BYPASS,
        TYPE_IGNORE_BYPASS,
        NOLINT_BYPASS,
    }
)

BYPASS_KEY_TO_LABEL = {
    NOQA_BYPASS: "# noqa",
    PRAGMA_NO_COVER_BYPASS: "pragma: no cover",
    TYPE_IGNORE_BYPASS: "type: ignore",
    UNITTEST_SKIP_BYPASS: "unittest skip",
    PYTEST_SKIP_BYPASS: "pytest skip",
    NOLINT_BYPASS: "nolint",
    WARNING_FILTER_BYPASS: "warning filter",
}
BYPASS_LABEL_TO_KEY = {label: key for key, label in BYPASS_KEY_TO_LABEL.items()}

IGNORED_DIR_NAMES = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".serena",
    "__pycache__",
    "temp",
    "target",
    "tmp",
}
SCAN_SUFFIXES = {".py", ".ps1", ".cmd", ".rs", ".yml", ".yaml"}
WHITELIST_SECTION_HEADING = "绕过白名单"


@dataclass(frozen=True)
class BypassWhitelistEntry:
    object_id: str
    bypass_key: str
    token: str
    owner: str
    review_cycle: str
    reason: str


@dataclass(frozen=True)
class BypassOccurrence:
    object_id: str
    bypass_key: str
    token: str


@dataclass(frozen=True)
class BypassScanner:
    bypass_key: str
    pattern: re.Pattern[str]
    suffixes: frozenset[str]
    include_test_files: bool = True


BYPASS_SCANNERS = (
    BypassScanner(
        bypass_key=NOQA_BYPASS,
        pattern=re.compile(r"# noqa(?::\s*[A-Z0-9, ]+)?"),
        suffixes=frozenset({".py"}),
    ),
    BypassScanner(
        bypass_key=PRAGMA_NO_COVER_BYPASS,
        pattern=re.compile(r"pragma:\s*no cover"),
        suffixes=frozenset({".py"}),
    ),
    BypassScanner(
        bypass_key=TYPE_IGNORE_BYPASS,
        pattern=re.compile(r"type:\s*ignore(?:\[[^\]]+\])?"),
        suffixes=frozenset({".py"}),
    ),
    BypassScanner(
        bypass_key=UNITTEST_SKIP_BYPASS,
        pattern=re.compile(r"@unittest\.skip(?:If|Unless)?"),
        suffixes=frozenset({".py"}),
    ),
    BypassScanner(
        bypass_key=PYTEST_SKIP_BYPASS,
        pattern=re.compile(r"@pytest\.mark\.skip"),
        suffixes=frozenset({".py"}),
    ),
    BypassScanner(
        bypass_key=NOLINT_BYPASS,
        pattern=re.compile(r"\bnolint\b"),
        suffixes=frozenset(SCAN_SUFFIXES),
    ),
    BypassScanner(
        bypass_key=WARNING_FILTER_BYPASS,
        pattern=re.compile(r"ignore::[A-Za-z0-9_.]+Warning"),
        suffixes=frozenset({".py", ".yml", ".yaml"}),
        include_test_files=False,
    ),
)


def extract_markdown_section_body(markdown_text: str, heading: str) -> str | None:
    pattern = re.compile(
        rf"^##+\s+{re.escape(heading)}\s*$\r?\n(?P<body>.*?)(?=^##+\s+|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(markdown_text)
    if match is None:
        return None
    return match.group("body")


def _strip_code_span(raw_text: str) -> str:
    return raw_text.strip().strip("`").strip()


def _normalize_object_id(raw_object_id: str) -> str:
    normalized = _strip_code_span(raw_object_id).replace("\\", "/")
    if not normalized:
        raise ValueError("绕过白名单对象标识不能为空")
    return normalized


def _normalize_bypass_key(raw_label: str) -> str:
    normalized_label = _strip_code_span(raw_label)
    try:
        return BYPASS_LABEL_TO_KEY[normalized_label]
    except KeyError as error:
        raise ValueError(f"未知绕过类型: {normalized_label}") from error


def _parse_markdown_table(section_body: str) -> list[dict[str, str]]:
    table_lines = [line.strip() for line in section_body.splitlines() if line.strip().startswith("|")]
    if len(table_lines) < 2:
        return []

    headers = [_strip_code_span(cell) for cell in table_lines[0].split("|")[1:-1]]
    rows: list[dict[str, str]] = []
    for raw_line in table_lines[2:]:
        cells = [_strip_code_span(cell) for cell in raw_line.split("|")[1:-1]]
        if len(cells) != len(headers):
            raise ValueError(f"绕过白名单表格列数不一致: {raw_line}")
        rows.append(dict(zip(headers, cells, strict=True)))
    return rows


def load_bypass_whitelist(
    path: Path | None = None,
) -> tuple[BypassWhitelistEntry, ...]:
    active_path = path or REFERENCE_BYPASS_WHITELIST_FILE
    if not active_path.exists():
        raise FileNotFoundError(
            f"缺少绕过白名单: {active_path.relative_to(REPO_ROOT).as_posix()}"
        )

    markdown_text = active_path.read_text(encoding="utf-8")
    section_body = extract_markdown_section_body(markdown_text, WHITELIST_SECTION_HEADING)
    if section_body is None:
        raise ValueError(f"绕过白名单缺少章节: {WHITELIST_SECTION_HEADING}")

    entries: list[BypassWhitelistEntry] = []
    seen_keys: set[tuple[str, str]] = set()
    for row in _parse_markdown_table(section_body):
        object_id = _normalize_object_id(row["对象标识"])
        bypass_key = _normalize_bypass_key(row["绕过类型"])
        key = (object_id, bypass_key)
        if key in seen_keys:
            raise ValueError(f"绕过白名单存在重复条目: {object_id} -> {BYPASS_KEY_TO_LABEL[bypass_key]}")
        seen_keys.add(key)
        entries.append(
            BypassWhitelistEntry(
                object_id=object_id,
                bypass_key=bypass_key,
                token=_strip_code_span(row["标记"]),
                owner=_strip_code_span(row["责任人"]),
                review_cycle=_strip_code_span(row["复查周期"]),
                reason=_strip_code_span(row["原因"]),
            )
        )
    return tuple(entries)


def _iter_governed_files() -> list[Path]:
    return iter_repo_files(REPO_ROOT, SCAN_SUFFIXES, IGNORED_DIR_NAMES)


def _is_test_file(relpath: str) -> bool:
    parts = relpath.split("/")
    return "tests" in parts or Path(relpath).name.startswith("test_")


def _collect_python_comment_bypass_occurrences(
    relpath: str,
    text: str,
) -> tuple[BypassOccurrence, ...]:
    scanners = tuple(
        scanner
        for scanner in BYPASS_SCANNERS
        if scanner.bypass_key in PYTHON_COMMENT_ONLY_BYPASS_KEYS
        and (scanner.include_test_files or not _is_test_file(relpath))
    )
    if not scanners:
        return ()

    occurrences: list[BypassOccurrence] = []
    seen_keys: set[tuple[str, str]] = set()
    tokens = tokenize.generate_tokens(io.StringIO(text).readline)

    for token in tokens:
        if token.type != tokenize.COMMENT:
            continue
        for scanner in scanners:
            match = scanner.pattern.search(token.string)
            if match is None:
                continue
            object_id = f"{relpath}:{token.start[0]}"
            key = (object_id, scanner.bypass_key)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            occurrences.append(
                BypassOccurrence(
                    object_id=object_id,
                    bypass_key=scanner.bypass_key,
                    token=match.group(0),
                )
            )
    return tuple(occurrences)


def _append_occurrence_if_new(
    occurrences: list[BypassOccurrence],
    seen_keys: set[tuple[str, str]],
    occurrence: BypassOccurrence,
) -> None:
    key = (occurrence.object_id, occurrence.bypass_key)
    if key in seen_keys:
        return
    seen_keys.add(key)
    occurrences.append(occurrence)


def _iter_line_bypass_scanners(path: Path, relpath: str) -> tuple[BypassScanner, ...]:
    suffix = path.suffix.lower()
    is_test_file = _is_test_file(relpath)
    is_python_file = suffix == ".py"
    return tuple(
        scanner
        for scanner in BYPASS_SCANNERS
        if suffix in scanner.suffixes
        and not (is_python_file and scanner.bypass_key in PYTHON_COMMENT_ONLY_BYPASS_KEYS)
        and (scanner.include_test_files or not is_test_file)
    )


def _collect_line_bypass_occurrences(
    path: Path,
    relpath: str,
    lines: list[str],
) -> tuple[BypassOccurrence, ...]:
    occurrences: list[BypassOccurrence] = []
    seen_keys: set[tuple[str, str]] = set()
    for scanner in _iter_line_bypass_scanners(path, relpath):
        for line_number, line in enumerate(lines, start=1):
            match = scanner.pattern.search(line)
            if match is None:
                continue
            _append_occurrence_if_new(
                occurrences,
                seen_keys,
                BypassOccurrence(
                    object_id=f"{relpath}:{line_number}",
                    bypass_key=scanner.bypass_key,
                    token=match.group(0),
                ),
            )
    return tuple(occurrences)


def _collect_file_bypass_occurrences(path: Path) -> tuple[BypassOccurrence, ...]:
    relpath = path.relative_to(REPO_ROOT).as_posix()
    text = path.read_text(encoding="utf-8", errors="ignore")
    occurrences = list(_collect_line_bypass_occurrences(path, relpath, text.splitlines()))
    if path.suffix.lower() != ".py":
        return tuple(occurrences)
    return (
        *_collect_python_comment_bypass_occurrences(relpath, text),
        *occurrences,
    )


def collect_observed_bypass_occurrences() -> tuple[BypassOccurrence, ...]:
    occurrences: list[BypassOccurrence] = []
    seen_keys: set[tuple[str, str]] = set()

    for path in _iter_governed_files():
        for occurrence in _collect_file_bypass_occurrences(path):
            _append_occurrence_if_new(occurrences, seen_keys, occurrence)

    return tuple(sorted(occurrences, key=lambda item: (item.object_id, item.bypass_key)))


def collect_bypass_whitelist_errors() -> list[str]:
    try:
        whitelist_entries = load_bypass_whitelist()
    except (FileNotFoundError, ValueError) as error:
        return [f"绕过白名单解析失败: {error}"]

    observed_occurrences = collect_observed_bypass_occurrences()
    errors: list[str] = []
    entry_map = {
        (entry.object_id, entry.bypass_key): entry for entry in whitelist_entries
    }
    observed_map = {
        (occurrence.object_id, occurrence.bypass_key): occurrence for occurrence in observed_occurrences
    }

    for key in sorted(observed_map):
        occurrence = observed_map[key]
        entry = entry_map.get(key)
        label = BYPASS_KEY_TO_LABEL[occurrence.bypass_key]
        if entry is None:
            errors.append(f"绕过未登记: {occurrence.object_id} -> {label} ({occurrence.token})")
            continue
        if entry.token != occurrence.token:
            errors.append(
                f"绕过白名单标记漂移: {occurrence.object_id} -> {label} "
                f"({entry.token} != {occurrence.token})"
            )

    for key in sorted(entry_map):
        entry = entry_map[key]
        if key in observed_map:
            continue
        errors.append(
            f"绕过白名单未清零: {entry.object_id} -> {BYPASS_KEY_TO_LABEL[entry.bypass_key]}"
        )

    return errors
