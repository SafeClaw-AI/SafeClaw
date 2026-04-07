from __future__ import annotations

import ast
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

REFERENCE_STANDARD_FILE = REPO_ROOT / "docs" / "reference" / "01-反屎山工程规范.md"
STRUCTURAL_DEBT_LEDGER_FILE = REPO_ROOT / "docs" / "reference" / "02-结构性债务台账.md"

FILE_NONEMPTY_LINES_RULE = "file_nonempty_lines"
FUNCTION_NONEMPTY_LINES_RULE = "function_nonempty_lines"
COMPLEXITY_RULE = "cyclomatic_complexity"

RULE_KEY_TO_LABEL = {
    FILE_NONEMPTY_LINES_RULE: "单文件非空行",
    FUNCTION_NONEMPTY_LINES_RULE: "单函数非空行",
    COMPLEXITY_RULE: "圈复杂度",
}
RULE_LABEL_TO_KEY = {
    "单文件非空行": FILE_NONEMPTY_LINES_RULE,
    "测试文件非空行": FILE_NONEMPTY_LINES_RULE,
    "单函数非空行": FUNCTION_NONEMPTY_LINES_RULE,
    "圈复杂度": COMPLEXITY_RULE,
    "单函数圈复杂度": COMPLEXITY_RULE,
}

STRUCTURAL_DEBT_LEDGER_CORE_PATHS_HEADING = "核心业务路径"
STRUCTURAL_DEBT_LEDGER_SECTION_HEADING = "结构性债务白名单"

GOVERNED_TEXT_SUFFIXES = {".py", ".rs", ".ps1", ".cmd"}
IGNORED_DIR_NAMES = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".serena",
    "__pycache__",
    "target",
    "tmp",
}
PYTHON_SCAN_SUFFIXES = {".py"}
COMPLEXITY_BRANCH_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.ExceptHandler,
    ast.BoolOp,
    ast.IfExp,
    ast.Match,
    ast.comprehension,
)

FUNCTION_NONEMPTY_LIMIT_PATTERN = re.compile(
    r"\|\s*单函数非空行\s*\|\s*≤[0-9,]+\s*\|\s*≤(?P<value>[0-9,]+)\s*\|"
)
FILE_NONEMPTY_LIMIT_PATTERN = re.compile(
    r"\|\s*单文件非空行\s*\|\s*≤[0-9,]+\s*\|\s*≤(?P<value>[0-9,]+)\s*\|"
)
TEST_FILE_NONEMPTY_LIMIT_PATTERN = re.compile(
    r"\|\s*测试文件非空行\s*\|\s*≤[0-9,]+\s*\|\s*≤(?P<value>[0-9,]+)\s*\|"
)
COMPLEXITY_LIMIT_PATTERN = re.compile(
    r"单函数圈复杂度\s*≤(?P<default>[0-9,]+)\s*\(核心业务\s*≤(?P<core>[0-9,]+)\)"
)


@dataclass(frozen=True)
class GovernanceThresholds:
    function_nonempty_lines_limit: int
    file_nonempty_lines_limit: int
    test_file_nonempty_lines_limit: int
    cyclomatic_complexity_limit: int
    core_business_cyclomatic_complexity_limit: int


@dataclass(frozen=True)
class StructuralDebtEntry:
    object_id: str
    rule_key: str
    current_value: str
    target_value: str
    owner: str
    due_date: date
    can_split: str
    reason: str


@dataclass(frozen=True)
class StructuralDebtLedger:
    core_business_paths: tuple[str, ...]
    entries: tuple[StructuralDebtEntry, ...]


class StructuralViolation(NamedTuple):
    object_id: str
    rule_key: str
    current_value: str
    target_value: str


def _extract_threshold_value(
    markdown_text: str,
    pattern: re.Pattern[str],
    group_name: str,
    display_name: str,
) -> int:
    match = pattern.search(markdown_text)
    if match is None:
        raise ValueError(f"无法从规范真源解析 {display_name}")
    return int(match.group(group_name).replace(",", ""))


def load_reference_governance_thresholds(
    path: Path = REFERENCE_STANDARD_FILE,
) -> GovernanceThresholds:
    if not path.exists():
        raise FileNotFoundError(f"缺少规范真源: {path.relative_to(REPO_ROOT).as_posix()}")

    markdown_text = path.read_text(encoding="utf-8")
    return GovernanceThresholds(
        function_nonempty_lines_limit=_extract_threshold_value(
            markdown_text,
            FUNCTION_NONEMPTY_LIMIT_PATTERN,
            "value",
            "单函数非空行上限",
        ),
        file_nonempty_lines_limit=_extract_threshold_value(
            markdown_text,
            FILE_NONEMPTY_LIMIT_PATTERN,
            "value",
            "单文件非空行上限",
        ),
        test_file_nonempty_lines_limit=_extract_threshold_value(
            markdown_text,
            TEST_FILE_NONEMPTY_LIMIT_PATTERN,
            "value",
            "测试文件非空行上限",
        ),
        cyclomatic_complexity_limit=_extract_threshold_value(
            markdown_text,
            COMPLEXITY_LIMIT_PATTERN,
            "default",
            "默认圈复杂度上限",
        ),
        core_business_cyclomatic_complexity_limit=_extract_threshold_value(
            markdown_text,
            COMPLEXITY_LIMIT_PATTERN,
            "core",
            "核心业务圈复杂度上限",
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


def _normalize_rule_key(rule_label: str) -> str:
    normalized_label = _strip_code_span(rule_label)
    try:
        return RULE_LABEL_TO_KEY[normalized_label]
    except KeyError as error:
        raise ValueError(f"未知结构性债务规则: {normalized_label}") from error


def _normalize_core_business_path_prefix(raw_prefix: str) -> str:
    normalized = _strip_code_span(raw_prefix).replace("\\", "/")
    if not normalized:
        raise ValueError("核心业务路径不能为空")
    return normalized if normalized.endswith("/") else f"{normalized}/"


def _normalize_object_id(raw_object_id: str) -> str:
    normalized = _strip_code_span(raw_object_id).replace("\\", "/")
    if not normalized:
        raise ValueError("对象标识不能为空")
    return normalized


def _parse_markdown_table(section_body: str) -> list[dict[str, str]]:
    table_lines = [line.strip() for line in section_body.splitlines() if line.strip().startswith("|")]
    if len(table_lines) < 2:
        return []

    headers = [_strip_code_span(cell) for cell in table_lines[0].split("|")[1:-1]]
    rows: list[dict[str, str]] = []
    for raw_line in table_lines[2:]:
        cells = [_strip_code_span(cell) for cell in raw_line.split("|")[1:-1]]
        if len(cells) != len(headers):
            raise ValueError(f"结构性债务台账表格列数不一致: {raw_line}")
        rows.append(dict(zip(headers, cells, strict=True)))
    return rows


def load_structural_debt_ledger(
    path: Path = STRUCTURAL_DEBT_LEDGER_FILE,
) -> StructuralDebtLedger:
    if not path.exists():
        raise FileNotFoundError(f"缺少结构性债务台账: {path.relative_to(REPO_ROOT).as_posix()}")

    markdown_text = path.read_text(encoding="utf-8")
    core_paths_body = extract_markdown_section_body(
        markdown_text,
        STRUCTURAL_DEBT_LEDGER_CORE_PATHS_HEADING,
    )
    if core_paths_body is None:
        raise ValueError(f"结构性债务台账缺少章节: {STRUCTURAL_DEBT_LEDGER_CORE_PATHS_HEADING}")

    debt_entries_body = extract_markdown_section_body(
        markdown_text,
        STRUCTURAL_DEBT_LEDGER_SECTION_HEADING,
    )
    if debt_entries_body is None:
        raise ValueError(f"结构性债务台账缺少章节: {STRUCTURAL_DEBT_LEDGER_SECTION_HEADING}")

    core_business_paths = tuple(
        _normalize_core_business_path_prefix(item)
        for item in re.findall(r"`([^`]+)`", core_paths_body)
    )

    entries: list[StructuralDebtEntry] = []
    seen_keys: set[tuple[str, str]] = set()
    for row in _parse_markdown_table(debt_entries_body):
        object_id = _normalize_object_id(row["对象标识"])
        rule_key = _normalize_rule_key(row["违规项"])
        key = (object_id, rule_key)
        if key in seen_keys:
            raise ValueError(f"结构性债务台账存在重复条目: {object_id} -> {RULE_KEY_TO_LABEL[rule_key]}")
        seen_keys.add(key)

        entries.append(
            StructuralDebtEntry(
                object_id=object_id,
                rule_key=rule_key,
                current_value=_strip_code_span(row["当前值"]),
                target_value=_strip_code_span(row["目标值"]),
                owner=_strip_code_span(row["责任人"]),
                due_date=date.fromisoformat(_strip_code_span(row["到期日"])),
                can_split=_strip_code_span(row.get("可拆", "")),
                reason=_strip_code_span(row["原因"]),
            )
        )

    return StructuralDebtLedger(
        core_business_paths=core_business_paths,
        entries=tuple(entries),
    )


def _iter_governed_files(repo_root: Path, suffixes: set[str]) -> list[Path]:
    paths: list[Path] = []
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(repo_root).parts
        if any(part in IGNORED_DIR_NAMES for part in rel_parts):
            continue
        if path.suffix.lower() not in suffixes:
            continue
        paths.append(path)
    return sorted(paths)


def _count_nonempty_lines(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip())


def _serialize_file_nonempty_current_value(nonempty: int, limit: int) -> str:
    return f"nonempty={nonempty}; limit={limit}"


def _serialize_function_nonempty_current_value(
    count: int,
    max_nonempty: int,
    max_symbol: str,
    max_line: int,
) -> str:
    return f"count={count}; max={max_nonempty}; symbol={max_symbol}; line={max_line}"


def _serialize_complexity_current_value(
    count: int,
    max_complexity: int,
    max_symbol: str,
    max_line: int,
    limit: int,
) -> str:
    return (
        f"count={count}; max={max_complexity}; symbol={max_symbol}; "
        f"line={max_line}; limit={limit}"
    )


def _is_test_file(relpath: str) -> bool:
    parts = relpath.split("/")
    return "tests" in parts or Path(relpath).name.startswith("test_")


def _is_core_business_path(relpath: str, core_business_paths: tuple[str, ...]) -> bool:
    return any(relpath.startswith(prefix) for prefix in core_business_paths)


def _python_function_complexity(node: ast.AST) -> int:
    score = 1
    for child in ast.walk(node):
        if isinstance(child, COMPLEXITY_BRANCH_NODES):
            if isinstance(child, ast.BoolOp):
                score += max(len(child.values) - 1, 1)
            else:
                score += 1
    return score


def collect_observed_structural_violations(
    repo_root: Path,
    thresholds: GovernanceThresholds,
    core_business_paths: tuple[str, ...],
) -> tuple[dict[tuple[str, str], StructuralViolation], list[str]]:
    violations: dict[tuple[str, str], StructuralViolation] = {}
    errors: list[str] = []

    for path in _iter_governed_files(repo_root, GOVERNED_TEXT_SUFFIXES):
        relpath = path.relative_to(repo_root).as_posix()
        text = path.read_text(encoding="utf-8", errors="ignore")
        nonempty = _count_nonempty_lines(text)
        file_limit = (
            thresholds.test_file_nonempty_lines_limit
            if _is_test_file(relpath)
            else thresholds.file_nonempty_lines_limit
        )
        if nonempty > file_limit:
            rule_key = FILE_NONEMPTY_LINES_RULE
            current_value = _serialize_file_nonempty_current_value(nonempty, file_limit)
            target_value = f"≤{file_limit}"
            violations[(relpath, rule_key)] = StructuralViolation(
                object_id=relpath,
                rule_key=rule_key,
                current_value=current_value,
                target_value=target_value,
            )

    function_stats: dict[str, dict[str, int | str]] = defaultdict(
        lambda: {"count": 0, "max_nonempty": 0, "max_symbol": "", "max_line": 0}
    )
    complexity_stats: dict[str, dict[str, int | str]] = defaultdict(
        lambda: {"count": 0, "max_complexity": 0, "max_symbol": "", "max_line": 0, "limit": 0}
    )

    for path in _iter_governed_files(repo_root, PYTHON_SCAN_SUFFIXES):
        relpath = path.relative_to(repo_root).as_posix()
        text = path.read_text(encoding="utf-8", errors="ignore")
        try:
            tree = ast.parse(text, filename=relpath)
        except SyntaxError as error:
            errors.append(f"无法解析 Python 文件: {relpath}:{error.lineno} -> {error.msg}")
            continue

        lines = text.splitlines()
        complexity_limit = (
            thresholds.core_business_cyclomatic_complexity_limit
            if _is_core_business_path(relpath, core_business_paths)
            else thresholds.cyclomatic_complexity_limit
        )

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            function_lines = lines[node.lineno - 1 : getattr(node, "end_lineno", node.lineno)]
            nonempty = sum(
                1 for line in function_lines if line.strip() and not line.strip().startswith("#")
            )
            if nonempty > thresholds.function_nonempty_lines_limit:
                entry = function_stats[relpath]
                entry["count"] = int(entry["count"]) + 1
                if nonempty > int(entry["max_nonempty"]):
                    entry["max_nonempty"] = nonempty
                    entry["max_symbol"] = node.name
                    entry["max_line"] = node.lineno

            complexity = _python_function_complexity(node)
            if complexity > complexity_limit:
                entry = complexity_stats[relpath]
                entry["count"] = int(entry["count"]) + 1
                entry["limit"] = complexity_limit
                if complexity > int(entry["max_complexity"]):
                    entry["max_complexity"] = complexity
                    entry["max_symbol"] = node.name
                    entry["max_line"] = node.lineno

    for relpath, entry in sorted(function_stats.items()):
        rule_key = FUNCTION_NONEMPTY_LINES_RULE
        violations[(relpath, rule_key)] = StructuralViolation(
            object_id=relpath,
            rule_key=rule_key,
            current_value=_serialize_function_nonempty_current_value(
                int(entry["count"]),
                int(entry["max_nonempty"]),
                str(entry["max_symbol"]),
                int(entry["max_line"]),
            ),
            target_value=f"≤{thresholds.function_nonempty_lines_limit}",
        )

    for relpath, entry in sorted(complexity_stats.items()):
        rule_key = COMPLEXITY_RULE
        violations[(relpath, rule_key)] = StructuralViolation(
            object_id=relpath,
            rule_key=rule_key,
            current_value=_serialize_complexity_current_value(
                int(entry["count"]),
                int(entry["max_complexity"]),
                str(entry["max_symbol"]),
                int(entry["max_line"]),
                int(entry["limit"]),
            ),
            target_value=f"≤{int(entry['limit'])}",
        )

    return violations, errors


def collect_structural_governance_errors(
    repo_root: Path = REPO_ROOT,
    thresholds: GovernanceThresholds | None = None,
    structural_debt_ledger: StructuralDebtLedger | None = None,
    today: date | None = None,
) -> list[str]:
    errors: list[str] = []

    try:
        active_thresholds = (
            thresholds if thresholds is not None else load_reference_governance_thresholds()
        )
        active_ledger = (
            structural_debt_ledger
            if structural_debt_ledger is not None
            else load_structural_debt_ledger()
        )
    except (FileNotFoundError, ValueError) as error:
        return [f"治理真源解析失败: {error}"]

    observed_violations, scan_errors = collect_observed_structural_violations(
        repo_root=repo_root,
        thresholds=active_thresholds,
        core_business_paths=active_ledger.core_business_paths,
    )
    errors.extend(scan_errors)

    entry_map = {
        (entry.object_id, entry.rule_key): entry for entry in active_ledger.entries
    }
    current_day = today or date.today()

    for key in sorted(observed_violations):
        violation = observed_violations[key]
        entry = entry_map.get(key)
        rule_label = RULE_KEY_TO_LABEL[violation.rule_key]
        if entry is None:
            errors.append(
                f"结构性债务未入账: {violation.object_id} -> {rule_label} "
                f"({violation.current_value}，目标 {violation.target_value})"
            )
            continue

        if entry.current_value != violation.current_value:
            errors.append(
                f"结构性债务台账漂移: {violation.object_id} -> {rule_label} "
                f"({entry.current_value} != {violation.current_value})"
            )

        if entry.target_value != violation.target_value:
            errors.append(
                f"结构性债务台账目标漂移: {violation.object_id} -> {rule_label} "
                f"({entry.target_value} != {violation.target_value})"
            )

        if entry.due_date < current_day:
            errors.append(
                f"结构性债务已逾期: {violation.object_id} -> {rule_label} "
                f"(due {entry.due_date.isoformat()})"
            )

    for key in sorted(entry_map):
        entry = entry_map[key]
        if key in observed_violations:
            continue
        errors.append(
            f"结构性债务台账未清零: {entry.object_id} -> {RULE_KEY_TO_LABEL[entry.rule_key]}"
        )

    return errors
