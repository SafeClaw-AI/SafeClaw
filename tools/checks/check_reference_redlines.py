from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from typing import NamedTuple

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
BROAD_EXCEPTION_TYPE_NAMES = {"BaseException", "Exception"}
SILENT_FALLBACK_EXCEPTION_TYPE_ORDER = (
    "FileExistsError",
    "KeyError",
    "OSError",
    "RuntimeError",
    "SyntaxError",
    "SystemError",
    "json.JSONDecodeError",
    "subprocess.TimeoutExpired",
)
HIGH_RISK_EXCEPTION_TYPES = set(SILENT_FALLBACK_EXCEPTION_TYPE_ORDER)
SILENT_FALLBACK_EXCEPTION_TYPES = HIGH_RISK_EXCEPTION_TYPES
CONTEXT_REQUIRED_EXCEPTION_TYPES = HIGH_RISK_EXCEPTION_TYPES
CONTEXT_REQUIRED_SUFFIX = "\u5fc5\u987b\u7ed1\u5b9a `as error` \u4ee5\u4fdd\u7559\u4e0a\u4e0b\u6587"
SILENT_FALLBACK_SUFFIX = "\u4e0d\u80fd\u76f4\u63a5\u9759\u9ed8\u964d\u7ea7\u4e3a None/False"
BARE_CONTEXT_REQUIRED_MESSAGE = "\u88f8 except \u4e0d\u5141\u8bb8\uff1b\u5fc5\u987b\u663e\u5f0f\u6355\u83b7\u5f02\u5e38\u7c7b\u578b\u5e76\u7ed1\u5b9a `as error`"
BROAD_CONTEXT_REQUIRED_MESSAGE = f"broad except {CONTEXT_REQUIRED_SUFFIX}"
MULTI_CONTEXT_REQUIRED_MESSAGE = f"\u591a\u5f02\u5e38 except {CONTEXT_REQUIRED_SUFFIX}"
BARE_SILENT_FALLBACK_MESSAGE = f"\u88f8 except {SILENT_FALLBACK_SUFFIX}"
BROAD_SILENT_FALLBACK_MESSAGE = f"broad except {SILENT_FALLBACK_SUFFIX}"
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


def _handler_requires_bound_error(handler: ast.ExceptHandler) -> bool:
    profile = _build_handler_exception_gate_profile(handler)
    if profile.is_bare_handler:
        return True
    if profile.uses_multi_exception_family:
        return True
    if profile.uses_broad_exception_family:
        return True
    return profile.uses_high_risk_exception_family


def _ordered_high_risk_exception_names(caught_types: set[str]) -> list[str]:
    return [name for name in SILENT_FALLBACK_EXCEPTION_TYPE_ORDER if name in caught_types]


def _caught_types_include_broad_exception(caught_types: set[str]) -> bool:
    return bool(caught_types & BROAD_EXCEPTION_TYPE_NAMES)


def _handler_caught_types(handler: ast.ExceptHandler) -> set[str]:
    return set(_collect_exception_type_names(handler.type))


class HandlerExceptionGateProfile(NamedTuple):
    caught_types: set[str]
    ordered_high_risk_exception_names: tuple[str, ...]
    is_bare_handler: bool
    uses_high_risk_exception_family: bool
    uses_multi_exception_family: bool
    uses_broad_exception_family: bool


def _build_handler_exception_gate_profile(handler: ast.ExceptHandler) -> HandlerExceptionGateProfile:
    caught_types = _handler_caught_types(handler)
    ordered_high_risk_exception_names = tuple(_ordered_high_risk_exception_names(caught_types))
    is_bare_handler = handler.type is None
    uses_high_risk_exception_family = bool(caught_types & HIGH_RISK_EXCEPTION_TYPES)
    uses_multi_exception_family = isinstance(handler.type, ast.Tuple)
    uses_broad_exception_family = (
        not is_bare_handler and _caught_types_include_broad_exception(caught_types)
    )
    return HandlerExceptionGateProfile(
        caught_types=caught_types,
        ordered_high_risk_exception_names=ordered_high_risk_exception_names,
        is_bare_handler=is_bare_handler,
        uses_high_risk_exception_family=uses_high_risk_exception_family,
        uses_multi_exception_family=uses_multi_exception_family,
        uses_broad_exception_family=uses_broad_exception_family,
    )


def _handler_uses_broad_exception_family(handler: ast.ExceptHandler) -> bool:
    return _build_handler_exception_gate_profile(handler).uses_broad_exception_family


def _handler_context_requirement(handler: ast.ExceptHandler) -> str:
    profile = _build_handler_exception_gate_profile(handler)
    if profile.is_bare_handler:
        return BARE_CONTEXT_REQUIRED_MESSAGE
    if profile.uses_broad_exception_family:
        return BROAD_CONTEXT_REQUIRED_MESSAGE
    if profile.uses_multi_exception_family:
        return MULTI_CONTEXT_REQUIRED_MESSAGE
    protected_types = list(profile.ordered_high_risk_exception_names)
    if protected_types:
        return f"{protected_types[0]} {CONTEXT_REQUIRED_SUFFIX}"
    return BROAD_CONTEXT_REQUIRED_MESSAGE


def _collect_exception_type_names(node: ast.expr | None) -> list[str]:
    if node is None:
        return ["<bare>"]
    if isinstance(node, ast.Tuple):
        names: list[str] = []
        for element in node.elts:
            names.extend(_collect_exception_type_names(element))
        return names
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, ast.Attribute):
        parent_names = _collect_exception_type_names(node.value)
        if len(parent_names) == 1:
            return [f"{parent_names[0]}.{node.attr}"]
        return [node.attr]
    return []

def _is_direct_none_false_return_handler(handler: ast.ExceptHandler) -> bool:
    if len(handler.body) != 1:
        return False
    statement = handler.body[0]
    if not isinstance(statement, ast.Return):
        return False
    if not isinstance(statement.value, ast.Constant):
        return False
    return statement.value.value in (None, False)


def _is_direct_silent_fallback_handler(handler: ast.ExceptHandler) -> bool:
    if not _is_direct_none_false_return_handler(handler):
        return False
    profile = _build_handler_exception_gate_profile(handler)
    if profile.is_bare_handler:
        return True
    if profile.uses_broad_exception_family:
        return True
    return profile.uses_high_risk_exception_family


def _silent_fallback_requirement(handler: ast.ExceptHandler) -> str:
    profile = _build_handler_exception_gate_profile(handler)
    if profile.is_bare_handler:
        return BARE_SILENT_FALLBACK_MESSAGE
    if profile.uses_broad_exception_family:
        return BROAD_SILENT_FALLBACK_MESSAGE
    protected_types = list(profile.ordered_high_risk_exception_names)
    protected_text = " / ".join(protected_types or sorted(profile.caught_types))
    return f"{protected_text} {SILENT_FALLBACK_SUFFIX}"


def collect_uncontextualized_exception_errors_for_python_text(path: Path, text: str) -> list[str]:
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
            if not _handler_requires_bound_error(handler):
                continue
            if handler.name is not None:
                continue
            errors.append(
                f"异常处理缺少上下文: {relpath}:{handler.lineno} -> {_handler_context_requirement(handler)}"
            )
    return errors


def _is_placeholder_error_assignment(statement: ast.stmt, error_name: str) -> bool:
    if not isinstance(statement, ast.Assign):
        return False
    if len(statement.targets) != 1:
        return False
    target = statement.targets[0]
    if not isinstance(target, ast.Name) or target.id != "_":
        return False
    return isinstance(statement.value, ast.Name) and statement.value.id == error_name


def _collect_meaningful_error_usage_count(body: list[ast.stmt], error_name: str) -> int:
    count = 0
    for statement in body:
        if _is_placeholder_error_assignment(statement, error_name):
            continue
        for node in ast.walk(statement):
            if isinstance(node, ast.Name) and node.id == error_name and isinstance(node.ctx, ast.Load):
                count += 1
    return count


def collect_unused_bound_exception_context_errors_for_python_text(path: Path, text: str) -> list[str]:
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
            if not _handler_requires_bound_error(handler):
                continue
            if handler.name is None:
                continue
            if _collect_meaningful_error_usage_count(handler.body, handler.name) > 0:
                continue
            errors.append(
                f"异常上下文未真正使用: {relpath}:{handler.lineno} -> 绑定了 `as error` 后，异常上下文不能只做占位赋值"
            )
    return errors


def collect_silent_fallback_exception_errors_for_python_text(path: Path, text: str) -> list[str]:
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
            if not _is_direct_silent_fallback_handler(handler):
                continue
            errors.append(
                f"异常降级缺少上下文: {relpath}:{handler.lineno} -> {_silent_fallback_requirement(handler)}"
            )
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


def collect_uncontextualized_exception_errors() -> list[str]:
    errors: list[str] = []
    for path in iter_reference_redline_files():
        if path.suffix.lower() not in PYTHON_SCAN_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8")
        errors.extend(
            collect_uncontextualized_exception_errors_for_python_text(path.relative_to(REPO_ROOT), text)
        )
    return errors


def collect_unused_bound_exception_context_errors() -> list[str]:
    errors: list[str] = []
    for path in iter_reference_redline_files():
        if path.suffix.lower() not in PYTHON_SCAN_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8")
        errors.extend(
            collect_unused_bound_exception_context_errors_for_python_text(path.relative_to(REPO_ROOT), text)
        )
    return errors


def collect_silent_fallback_exception_errors() -> list[str]:
    errors: list[str] = []
    for path in iter_reference_redline_files():
        if path.suffix.lower() not in PYTHON_SCAN_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8")
        errors.extend(
            collect_silent_fallback_exception_errors_for_python_text(path.relative_to(REPO_ROOT), text)
        )
    return errors


def collect_errors() -> list[str]:
    errors: list[str] = []
    errors.extend(collect_todo_metadata_errors())
    errors.extend(collect_empty_exception_errors())
    errors.extend(collect_uncontextualized_exception_errors())
    errors.extend(collect_unused_bound_exception_context_errors())
    errors.extend(collect_silent_fallback_exception_errors())
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
