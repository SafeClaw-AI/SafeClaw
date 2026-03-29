from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

TODO_METADATA_REQUIREMENTS = ("owner", "due", "req")
TODO_METADATA_PATTERNS = {
    "owner": re.compile(r"(?:\bowner\s*=\s*[A-Za-z0-9_.-]+)|(?:责任人\s*[:=]\s*[^,，\s]+)", re.IGNORECASE),
    "due": re.compile(r"(?:\bdue\s*=\s*\d{4}-\d{2}-\d{2})|(?:截止(?:日期)?\s*[:=]\s*\d{4}-\d{2}-\d{2})", re.IGNORECASE),
    "req": re.compile(r"(?:\breq\s*=\s*[A-Za-z0-9_.-]+)|(?:需求(?:ID)?\s*[:=]\s*[A-Za-z0-9_.-]+)", re.IGNORECASE),
}
TODO_LINE_PATTERN = re.compile(r"^\s*(?:(?:#|//|/\*+|\*|;|REM\b)\s*)?TODO\b", re.IGNORECASE)
PYTHON_SCAN_SUFFIXES = {".py"}
POWERSHELL_SCAN_SUFFIXES = {".ps1"}
TODO_SCAN_SUFFIXES = {".py", ".ps1", ".cmd", ".rs"}
REFERENCE_REDLINE_SCAN_DIRS = (
    "tools",
    "tests",
    "safeclaw-core",
    "safeclaw-sqlite",
    "modules",
)
REFERENCE_REDLINE_SCAN_FILES = (
    "safeclaw.ps1",
    "safeclaw.cmd",
)
IGNORED_DIR_NAMES = {".git", ".pytest_cache", "__pycache__", "target"}
POWERSHELL_EMPTY_CATCH_PATTERN = re.compile(r"catch\s*\{(?P<body>.*?)\}", re.IGNORECASE | re.DOTALL)


def iter_reference_redline_files() -> list[Path]:
    paths: list[Path] = []

    for relpath in REFERENCE_REDLINE_SCAN_FILES:
        path = REPO_ROOT / relpath
        if path.exists() and path.is_file():
            paths.append(path)

    for relpath in REFERENCE_REDLINE_SCAN_DIRS:
        root = REPO_ROOT / relpath
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel_parts = path.relative_to(REPO_ROOT).parts
            if any(part in IGNORED_DIR_NAMES for part in rel_parts):
                continue
            if path.suffix.lower() not in (TODO_SCAN_SUFFIXES | PYTHON_SCAN_SUFFIXES | POWERSHELL_SCAN_SUFFIXES):
                continue
            paths.append(path)

    deduped: dict[str, Path] = {}
    for path in paths:
        deduped[path.relative_to(REPO_ROOT).as_posix()] = path
    return [deduped[key] for key in sorted(deduped)]


def collect_todo_metadata_errors_for_text(path: Path, text: str) -> list[str]:
    errors: list[str] = []
    relpath = path.as_posix()
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not TODO_LINE_PATTERN.match(line):
            continue
        if all(pattern.search(line) for pattern in TODO_METADATA_PATTERNS.values()):
            continue
        errors.append(
            f"TODO 缺少责任元数据: {relpath}:{line_number} -> 需要同时包含 owner / due / req"
        )
    return errors


def _is_empty_python_except_body(body: list[ast.stmt]) -> bool:
    significant_statements: list[ast.stmt] = []
    for statement in body:
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant):
            if isinstance(statement.value.value, str):
                continue
            if statement.value.value is Ellipsis:
                significant_statements.append(statement)
                continue
        significant_statements.append(statement)

    if not significant_statements:
        return True

    for statement in significant_statements:
        if isinstance(statement, ast.Pass):
            continue
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant) and statement.value.value is Ellipsis:
            continue
        return False
    return True


def collect_empty_exception_errors_for_python_text(path: Path, text: str) -> list[str]:
    relpath = path.as_posix()
    try:
        tree = ast.parse(text, filename=relpath)
    except SyntaxError as error:
        return [f"无法解析 Python 文件: {relpath}:{error.lineno} -> {error.msg}"]

    errors: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        for handler in node.handlers:
            if _is_empty_python_except_body(handler.body):
                errors.append(
                    f"空异常处理违规: {relpath}:{handler.lineno} -> except 块不能只写 pass/省略号"
                )
    return errors


def collect_empty_exception_errors_for_powershell_text(path: Path, text: str) -> list[str]:
    errors: list[str] = []
    relpath = path.as_posix()
    for match in POWERSHELL_EMPTY_CATCH_PATTERN.finditer(text):
        body = match.group("body")
        meaningful_lines = []
        for raw_line in body.splitlines():
            stripped = raw_line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                continue
            meaningful_lines.append(stripped)
        if meaningful_lines:
            continue
        line_number = text.count("\n", 0, match.start()) + 1
        errors.append(f"空异常处理违规: {relpath}:{line_number} -> catch 块不能为空或只含注释")
    return errors


def collect_todo_metadata_errors() -> list[str]:
    errors: list[str] = []
    for path in iter_reference_redline_files():
        if path.suffix.lower() not in TODO_SCAN_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8")
        errors.extend(collect_todo_metadata_errors_for_text(path.relative_to(REPO_ROOT), text))
    return errors


def collect_empty_exception_errors() -> list[str]:
    errors: list[str] = []
    for path in iter_reference_redline_files():
        suffix = path.suffix.lower()
        if suffix not in (PYTHON_SCAN_SUFFIXES | POWERSHELL_SCAN_SUFFIXES):
            continue
        text = path.read_text(encoding="utf-8")
        relpath = path.relative_to(REPO_ROOT)
        if suffix in PYTHON_SCAN_SUFFIXES:
            errors.extend(collect_empty_exception_errors_for_python_text(relpath, text))
        if suffix in POWERSHELL_SCAN_SUFFIXES:
            errors.extend(collect_empty_exception_errors_for_powershell_text(relpath, text))
    return errors


def collect_errors() -> list[str]:
    errors: list[str] = []
    errors.extend(collect_todo_metadata_errors())
    errors.extend(collect_empty_exception_errors())
    return errors


def main() -> int:
    errors = collect_errors()
    if errors:
        print("Reference redlines check failed:")
        for item in errors:
            print(f"- {item}")
        return 1

    print("Reference redlines check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
