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
CONTEXT_REQUIRED_EXCEPTION_TYPE_ORDER = (
    "FileExistsError",
    "KeyError",
    "OSError",
    "RuntimeError",
    "SyntaxError",
    "SystemError",
    "json.JSONDecodeError",
    "subprocess.TimeoutExpired",
)
SILENT_FALLBACK_EXCEPTION_TYPE_ORDER = CONTEXT_REQUIRED_EXCEPTION_TYPE_ORDER + (
    "ValueError",
    "TypeError",
)
HIGH_RISK_EXCEPTION_TYPES = set(CONTEXT_REQUIRED_EXCEPTION_TYPE_ORDER)
CONTEXT_REQUIRED_EXCEPTION_TYPES = HIGH_RISK_EXCEPTION_TYPES
SILENT_FALLBACK_EXCEPTION_TYPES = set(SILENT_FALLBACK_EXCEPTION_TYPE_ORDER)
CONTEXT_REQUIRED_SUFFIX = "\u5fc5\u987b\u7ed1\u5b9a `as error` \u4ee5\u4fdd\u7559\u4e0a\u4e0b\u6587"
SILENT_FALLBACK_SUFFIX = "\u4e0d\u80fd\u76f4\u63a5\u9759\u9ed8\u964d\u7ea7\u4e3a None/False/\u7a7a\u5b57\u7b26\u4e32/\u7a7a\u5bb9\u5668"
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


def _parse_python_text_for_reference_check(path: Path, text: str) -> PythonTextParseResult:
    relpath = path.as_posix()
    try:
        tree = ast.parse(text, filename=relpath)
    except SyntaxError as error:
        return PythonTextParseResult(
            relpath=relpath,
            tree=None,
            syntax_error_message=f"无法解析 Python 文件: {relpath}:{error.lineno} -> {error.msg}",
        )
    return PythonTextParseResult(relpath=relpath, tree=tree, syntax_error_message=None)


def collect_empty_exception_errors_for_python_text(path: Path, text: str) -> list[str]:
    parsed = _parse_python_text_for_reference_check(path, text)
    if parsed.syntax_error_message is not None:
        return [parsed.syntax_error_message]

    relpath = parsed.relpath
    tree = parsed.tree
    assert tree is not None

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
    return _build_handler_exception_gate_profile(handler).requires_bound_error


def _ordered_high_risk_exception_names(caught_types: set[str]) -> list[str]:
    return [name for name in CONTEXT_REQUIRED_EXCEPTION_TYPE_ORDER if name in caught_types]


def _ordered_silent_fallback_exception_names(caught_types: set[str]) -> list[str]:
    return [name for name in SILENT_FALLBACK_EXCEPTION_TYPE_ORDER if name in caught_types]


def _caught_types_include_broad_exception(caught_types: set[str]) -> bool:
    return bool(caught_types & BROAD_EXCEPTION_TYPE_NAMES)


def _handler_caught_types(handler: ast.ExceptHandler) -> set[str]:
    return set(_collect_exception_type_names(handler.type))


class PythonTextParseResult(NamedTuple):
    relpath: str
    tree: ast.Module | None
    syntax_error_message: str | None


class ReferenceRedlineScanText(NamedTuple):
    relpath: Path
    suffix: str
    text: str


class HandlerExceptionGateProfile(NamedTuple):
    caught_types: set[str]
    ordered_high_risk_exception_names: tuple[str, ...]
    context_requirement_message: str
    silent_fallback_requirement_message: str
    requires_bound_error: bool
    is_direct_silent_fallback: bool
    is_bare_handler: bool
    uses_high_risk_exception_family: bool
    uses_multi_exception_family: bool
    uses_broad_exception_family: bool


def _build_handler_exception_gate_profile(handler: ast.ExceptHandler) -> HandlerExceptionGateProfile:
    caught_types = _handler_caught_types(handler)
    ordered_high_risk_exception_names = tuple(_ordered_high_risk_exception_names(caught_types))
    ordered_silent_fallback_exception_names = tuple(
        _ordered_silent_fallback_exception_names(caught_types)
    )
    is_bare_handler = handler.type is None
    uses_high_risk_exception_family = bool(caught_types & HIGH_RISK_EXCEPTION_TYPES)
    uses_silent_fallback_exception_family = bool(
        caught_types & SILENT_FALLBACK_EXCEPTION_TYPES
    )
    uses_multi_exception_family = isinstance(handler.type, ast.Tuple)
    uses_broad_exception_family = (
        not is_bare_handler and _caught_types_include_broad_exception(caught_types)
    )
    requires_bound_error = (
        is_bare_handler
        or uses_multi_exception_family
        or uses_broad_exception_family
        or uses_high_risk_exception_family
    )

    if is_bare_handler:
        context_requirement_message = BARE_CONTEXT_REQUIRED_MESSAGE
        silent_fallback_requirement_message = BARE_SILENT_FALLBACK_MESSAGE
    elif uses_broad_exception_family:
        context_requirement_message = BROAD_CONTEXT_REQUIRED_MESSAGE
        silent_fallback_requirement_message = BROAD_SILENT_FALLBACK_MESSAGE
    elif uses_multi_exception_family:
        context_requirement_message = MULTI_CONTEXT_REQUIRED_MESSAGE
        protected_text = " / ".join(
            ordered_silent_fallback_exception_names or sorted(caught_types)
        )
        silent_fallback_requirement_message = f"{protected_text} {SILENT_FALLBACK_SUFFIX}"
    else:
        primary_high_risk_exception_name = next(iter(ordered_high_risk_exception_names), None)
        context_requirement_message = (
            f"{primary_high_risk_exception_name} {CONTEXT_REQUIRED_SUFFIX}"
            if primary_high_risk_exception_name
            else BROAD_CONTEXT_REQUIRED_MESSAGE
        )
        protected_text = " / ".join(
            ordered_silent_fallback_exception_names or sorted(caught_types)
        )
        silent_fallback_requirement_message = f"{protected_text} {SILENT_FALLBACK_SUFFIX}"

    is_direct_silent_fallback = False
    if _is_direct_silent_fallback_return_handler(handler):
        is_direct_silent_fallback = (
            is_bare_handler
            or uses_broad_exception_family
            or uses_silent_fallback_exception_family
        )

    return HandlerExceptionGateProfile(
        caught_types=caught_types,
        ordered_high_risk_exception_names=ordered_high_risk_exception_names,
        context_requirement_message=context_requirement_message,
        silent_fallback_requirement_message=silent_fallback_requirement_message,
        requires_bound_error=requires_bound_error,
        is_direct_silent_fallback=is_direct_silent_fallback,
        is_bare_handler=is_bare_handler,
        uses_high_risk_exception_family=uses_high_risk_exception_family,
        uses_multi_exception_family=uses_multi_exception_family,
        uses_broad_exception_family=uses_broad_exception_family,
    )


def _handler_uses_broad_exception_family(handler: ast.ExceptHandler) -> bool:
    return _build_handler_exception_gate_profile(handler).uses_broad_exception_family


def _iter_exception_handler_gate_profiles(tree: ast.AST):
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        for handler in node.handlers:
            yield handler, _build_handler_exception_gate_profile(handler)


def _handler_context_requirement(handler: ast.ExceptHandler) -> str:
    return _build_handler_exception_gate_profile(handler).context_requirement_message


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

def _is_empty_fallback_constructor_call(node: ast.expr | None) -> bool:
    if not isinstance(node, ast.Call):
        return False
    if node.args or node.keywords:
        return False
    if not isinstance(node.func, ast.Name):
        return False
    return node.func.id in {"str", "list", "dict", "tuple", "set", "frozenset"}



def _is_direct_silent_fallback_return_value(node: ast.expr | None) -> bool:
    if node is None:
        return True
    if isinstance(node, ast.Constant):
        return node.value in (None, False, "")
    if isinstance(node, ast.List):
        return not node.elts
    if isinstance(node, ast.Dict):
        return not node.keys
    if isinstance(node, ast.Tuple):
        return not node.elts
    if _is_empty_fallback_constructor_call(node):
        return True
    return False


def _is_direct_silent_fallback_return_handler(handler: ast.ExceptHandler) -> bool:
    if len(handler.body) != 1:
        return False
    statement = handler.body[0]
    if not isinstance(statement, ast.Return):
        return False
    return _is_direct_silent_fallback_return_value(statement.value)


def _is_direct_silent_fallback_handler(handler: ast.ExceptHandler) -> bool:
    return _build_handler_exception_gate_profile(handler).is_direct_silent_fallback


def _silent_fallback_requirement(handler: ast.ExceptHandler) -> str:
    return _build_handler_exception_gate_profile(handler).silent_fallback_requirement_message


def collect_uncontextualized_exception_errors_for_python_text(path: Path, text: str) -> list[str]:
    parsed = _parse_python_text_for_reference_check(path, text)
    if parsed.syntax_error_message is not None:
        return [parsed.syntax_error_message]

    relpath = parsed.relpath
    tree = parsed.tree
    assert tree is not None

    errors: list[str] = []
    for handler, profile in _iter_exception_handler_gate_profiles(tree):
        if not profile.requires_bound_error:
            continue
        if handler.name is not None:
            continue
        errors.append(
            f"异常处理缺少上下文: {relpath}:{handler.lineno} -> {profile.context_requirement_message}"
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
    parsed = _parse_python_text_for_reference_check(path, text)
    if parsed.syntax_error_message is not None:
        return [parsed.syntax_error_message]

    relpath = parsed.relpath
    tree = parsed.tree
    assert tree is not None

    errors: list[str] = []
    for handler, profile in _iter_exception_handler_gate_profiles(tree):
        if not profile.requires_bound_error:
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
    parsed = _parse_python_text_for_reference_check(path, text)
    if parsed.syntax_error_message is not None:
        return [parsed.syntax_error_message]

    relpath = parsed.relpath
    tree = parsed.tree
    assert tree is not None

    errors: list[str] = []
    for handler, profile in _iter_exception_handler_gate_profiles(tree):
        if not profile.is_direct_silent_fallback:
            continue
        errors.append(
            f"异常降级缺少上下文: {relpath}:{handler.lineno} -> {profile.silent_fallback_requirement_message}"
        )
    return errors


def _iter_reference_redline_scan_texts(scan_suffixes: set[str]) -> list[ReferenceRedlineScanText]:
    scan_texts: list[ReferenceRedlineScanText] = []
    for path in iter_reference_redline_files():
        suffix = path.suffix.lower()
        if suffix not in scan_suffixes:
            continue
        scan_texts.append(
            ReferenceRedlineScanText(
                relpath=path.relative_to(REPO_ROOT),
                suffix=suffix,
                text=path.read_text(encoding="utf-8"),
            )
        )
    return scan_texts


def collect_todo_metadata_errors() -> list[str]:
    errors: list[str] = []
    for scan_text in _iter_reference_redline_scan_texts(TODO_SCAN_SUFFIXES):
        errors.extend(collect_todo_metadata_errors_for_text(scan_text.relpath, scan_text.text))
    return errors


def _collect_python_reference_redline_errors(collector) -> list[str]:
    errors: list[str] = []
    for scan_text in _iter_reference_redline_scan_texts(PYTHON_SCAN_SUFFIXES):
        errors.extend(collector(scan_text.relpath, scan_text.text))
    return errors


def collect_empty_exception_errors() -> list[str]:
    errors: list[str] = []
    for scan_text in _iter_reference_redline_scan_texts(
        PYTHON_SCAN_SUFFIXES | POWERSHELL_SCAN_SUFFIXES
    ):
        if scan_text.suffix in PYTHON_SCAN_SUFFIXES:
            errors.extend(
                collect_empty_exception_errors_for_python_text(
                    scan_text.relpath,
                    scan_text.text,
                )
            )
        if scan_text.suffix in POWERSHELL_SCAN_SUFFIXES:
            errors.extend(
                collect_empty_exception_errors_for_powershell_text(
                    scan_text.relpath,
                    scan_text.text,
                )
            )
    return errors


def collect_uncontextualized_exception_errors() -> list[str]:
    return _collect_python_reference_redline_errors(
        collect_uncontextualized_exception_errors_for_python_text
    )


def collect_unused_bound_exception_context_errors() -> list[str]:
    return _collect_python_reference_redline_errors(
        collect_unused_bound_exception_context_errors_for_python_text
    )


def collect_silent_fallback_exception_errors() -> list[str]:
    return _collect_python_reference_redline_errors(
        collect_silent_fallback_exception_errors_for_python_text
    )


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
