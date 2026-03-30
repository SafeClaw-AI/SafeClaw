from __future__ import annotations

import ast
import re
import sys
from collections.abc import Mapping
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
SILENT_FALLBACK_SUFFIX = "\u4e0d\u80fd\u76f4\u63a5\u9759\u9ed8\u964d\u7ea7\u4e3a None/False/\u7a7a\u5b57\u7b26\u4e32/\u7a7a\u5b57\u8282\u4e32/\u7a7a\u5bb9\u5668"
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

def _is_silent_fallback_constructor_call(node: ast.expr | None) -> bool:
    if not isinstance(node, ast.Call):
        return False
    if node.args or node.keywords:
        return False
    if not isinstance(node.func, ast.Name):
        return False
    return node.func.id in {"bool", "str", "bytes", "bytearray", "list", "dict", "tuple", "set", "frozenset"}



_STATIC_VALUE_NOT_AVAILABLE = object()
_ZERO_ARG_SILENT_FALLBACK_CONSTRUCTOR_VALUES = {
    "bool": False,
    "str": "",
    "bytes": b"",
    "bytearray": bytearray(),
    "list": [],
    "dict": {},
    "tuple": (),
    "set": set(),
    "frozenset": frozenset(),
}
_SINGLE_ARG_SILENT_FALLBACK_CONSTRUCTORS = {
    "bool": bool,
    "str": str,
    "bytes": bytes,
    "bytearray": bytearray,
    "list": list,
    "dict": dict,
    "tuple": tuple,
    "set": set,
    "frozenset": frozenset,
}
_SINGLE_KEYWORD_SILENT_FALLBACK_CONSTRUCTORS = {
    "str": {"object": str},
    "bytes": {"source": bytes},
    "bytearray": {"source": bytearray},
}
_STATIC_EMPTY_ITERATOR_VALUE = object()
_EMPTY_ITERATOR_CONSUMING_CONSTRUCTOR_VALUES = {
    "bytes": b"",
    "bytearray": bytearray(),
    "list": [],
    "dict": {},
    "tuple": (),
    "set": set(),
    "frozenset": frozenset(),
}
_ZERO_ARG_SILENT_FALLBACK_METHOD_OWNERS = {
    "copy": (list, dict, set, frozenset),
    "strip": (str, bytes, bytearray),
    "lstrip": (str, bytes, bytearray),
    "rstrip": (str, bytes, bytearray),
    "lower": (str, bytes, bytearray),
    "upper": (str, bytes, bytearray),
    "casefold": (str,),
    "split": (str, bytes, bytearray),
    "splitlines": (str, bytes, bytearray),
    "isalnum": (str, bytes, bytearray),
    "isalpha": (str, bytes, bytearray),
    "isdecimal": (str,),
    "isdigit": (str, bytes, bytearray),
    "isidentifier": (str,),
    "islower": (str, bytes, bytearray),
    "isnumeric": (str,),
    "isspace": (str, bytes, bytearray),
    "istitle": (str, bytes, bytearray),
    "isupper": (str, bytes, bytearray),
    "capitalize": (str, bytes, bytearray),
    "swapcase": (str, bytes, bytearray),
    "title": (str, bytes, bytearray),
    "expandtabs": (str, bytes, bytearray),
    "encode": (str,),
    "decode": (bytes, bytearray),
    "rsplit": (str, bytes, bytearray),
    "clear": (list, dict, set, bytearray),
    "reverse": (list, bytearray),
    "sort": (list,),
    "difference": (set, frozenset),
    "intersection": (set, frozenset),
    "union": (set, frozenset),
    "update": (dict, set),
    "difference_update": (set,),
    "intersection_update": (set,),
    "format": (str,),
    "hex": (bytes, bytearray),
}


def _runtime_value_is_silent_fallback(value: object) -> bool:
    if value is None or value is False:
        return True
    if isinstance(value, (str, bytes, bytearray)):
        return len(value) == 0
    if isinstance(value, (list, tuple, dict, set, frozenset, range)):
        return len(value) == 0
    return False



def _runtime_value_is_statically_empty_iterable(value: object) -> bool:
    if value is _STATIC_EMPTY_ITERATOR_VALUE:
        return True
    if isinstance(value, (str, bytes, bytearray, list, tuple, dict, set, frozenset, range)):
        return len(value) == 0
    return False



def _runtime_value_is_trackable_silent_fallback_assignment_value(value: object) -> bool:
    return _runtime_value_is_silent_fallback(value) or value is _STATIC_EMPTY_ITERATOR_VALUE



def _runtime_value_is_statically_empty_reversible(value: object) -> bool:
    return isinstance(value, (str, bytes, bytearray, list, tuple, dict, range)) and len(value) == 0



def _try_evaluate_statically_empty_zip_call_value(node: ast.Call, resolve_value) -> object:
    if not isinstance(node.func, ast.Name) or node.func.id != "zip" or node.keywords:
        return _STATIC_VALUE_NOT_AVAILABLE
    if not node.args:
        return _STATIC_EMPTY_ITERATOR_VALUE
    saw_unavailable = False
    for argument_node in node.args:
        argument_value = resolve_value(argument_node)
        if argument_value is _STATIC_VALUE_NOT_AVAILABLE:
            saw_unavailable = True
            continue
        if _runtime_value_is_statically_empty_iterable(argument_value):
            return _STATIC_EMPTY_ITERATOR_VALUE
    if saw_unavailable:
        return _STATIC_VALUE_NOT_AVAILABLE
    return _STATIC_VALUE_NOT_AVAILABLE



def _try_evaluate_statically_empty_iter_call_value(node: ast.Call, resolve_value) -> object:
    if not isinstance(node.func, ast.Name) or node.func.id != "iter" or node.keywords or len(node.args) != 1:
        return _STATIC_VALUE_NOT_AVAILABLE
    argument_value = resolve_value(node.args[0])
    if argument_value is _STATIC_VALUE_NOT_AVAILABLE:
        return _STATIC_VALUE_NOT_AVAILABLE
    if _runtime_value_is_statically_empty_iterable(argument_value):
        return _STATIC_EMPTY_ITERATOR_VALUE
    return _STATIC_VALUE_NOT_AVAILABLE



def _try_evaluate_statically_empty_reversed_call_value(node: ast.Call, resolve_value) -> object:
    if not isinstance(node.func, ast.Name) or node.func.id != "reversed" or node.keywords or len(node.args) != 1:
        return _STATIC_VALUE_NOT_AVAILABLE
    argument_value = resolve_value(node.args[0])
    if argument_value is _STATIC_VALUE_NOT_AVAILABLE:
        return _STATIC_VALUE_NOT_AVAILABLE
    if _runtime_value_is_statically_empty_reversible(argument_value):
        return _STATIC_EMPTY_ITERATOR_VALUE
    return _STATIC_VALUE_NOT_AVAILABLE



def _try_evaluate_statically_empty_enumerate_call_value(node: ast.Call, resolve_value) -> object:
    if not isinstance(node.func, ast.Name) or node.func.id != "enumerate":
        return _STATIC_VALUE_NOT_AVAILABLE
    iterable_node: ast.expr | None = None
    start_node: ast.expr | None = None
    if not node.keywords and len(node.args) in (1, 2):
        iterable_node = node.args[0]
        if len(node.args) == 2:
            start_node = node.args[1]
    elif len(node.args) == 1 and len(node.keywords) == 1 and node.keywords[0].arg == "start":
        iterable_node = node.args[0]
        start_node = node.keywords[0].value
    else:
        return _STATIC_VALUE_NOT_AVAILABLE
    iterable_value = resolve_value(iterable_node)
    if iterable_value is _STATIC_VALUE_NOT_AVAILABLE:
        return _STATIC_VALUE_NOT_AVAILABLE
    if start_node is not None:
        start_value = resolve_value(start_node)
        if start_value is _STATIC_VALUE_NOT_AVAILABLE or not isinstance(start_value, int):
            return _STATIC_VALUE_NOT_AVAILABLE
    if _runtime_value_is_statically_empty_iterable(iterable_value):
        return _STATIC_EMPTY_ITERATOR_VALUE
    return _STATIC_VALUE_NOT_AVAILABLE



def _try_evaluate_statically_empty_map_call_value(node: ast.Call, resolve_value) -> object:
    if not isinstance(node.func, ast.Name) or node.func.id != "map" or node.keywords or len(node.args) < 2:
        return _STATIC_VALUE_NOT_AVAILABLE
    saw_unavailable = False
    for iterable_node in node.args[1:]:
        iterable_value = resolve_value(iterable_node)
        if iterable_value is _STATIC_VALUE_NOT_AVAILABLE:
            saw_unavailable = True
            continue
        if _runtime_value_is_statically_empty_iterable(iterable_value):
            return _STATIC_EMPTY_ITERATOR_VALUE
    if saw_unavailable:
        return _STATIC_VALUE_NOT_AVAILABLE
    return _STATIC_VALUE_NOT_AVAILABLE



def _try_evaluate_statically_empty_filter_call_value(node: ast.Call, resolve_value) -> object:
    if not isinstance(node.func, ast.Name) or node.func.id != "filter" or node.keywords or len(node.args) != 2:
        return _STATIC_VALUE_NOT_AVAILABLE
    iterable_value = resolve_value(node.args[1])
    if iterable_value is _STATIC_VALUE_NOT_AVAILABLE:
        return _STATIC_VALUE_NOT_AVAILABLE
    if _runtime_value_is_statically_empty_iterable(iterable_value):
        return _STATIC_EMPTY_ITERATOR_VALUE
    return _STATIC_VALUE_NOT_AVAILABLE



def _try_evaluate_statically_empty_next_call_value(node: ast.Call, resolve_value) -> object:
    if not isinstance(node.func, ast.Name) or node.func.id != "next" or node.keywords or len(node.args) not in (1, 2):
        return _STATIC_VALUE_NOT_AVAILABLE
    iterator_value = resolve_value(node.args[0])
    if iterator_value is _STATIC_VALUE_NOT_AVAILABLE:
        return _STATIC_VALUE_NOT_AVAILABLE
    if not _runtime_value_is_statically_empty_iterable(iterator_value):
        return _STATIC_VALUE_NOT_AVAILABLE
    if len(node.args) == 1:
        return _STATIC_VALUE_NOT_AVAILABLE
    default_value = resolve_value(node.args[1])
    if default_value is _STATIC_VALUE_NOT_AVAILABLE:
        return _STATIC_VALUE_NOT_AVAILABLE
    return default_value



def _try_evaluate_statically_empty_sorted_call_value(node: ast.Call, resolve_value) -> object:
    if not isinstance(node.func, ast.Name) or node.func.id != "sorted" or node.keywords or len(node.args) != 1:
        return _STATIC_VALUE_NOT_AVAILABLE
    iterable_value = resolve_value(node.args[0])
    if iterable_value is _STATIC_VALUE_NOT_AVAILABLE:
        return _STATIC_VALUE_NOT_AVAILABLE
    if _runtime_value_is_statically_empty_iterable(iterable_value):
        return []
    return _STATIC_VALUE_NOT_AVAILABLE



def _try_evaluate_statically_empty_join_method_value(node: ast.Call, resolve_value) -> object:
    if (
        not isinstance(node.func, ast.Attribute)
        or node.func.attr != "join"
        or node.keywords
        or len(node.args) != 1
    ):
        return _STATIC_VALUE_NOT_AVAILABLE
    separator_value = resolve_value(node.func.value)
    if separator_value is _STATIC_VALUE_NOT_AVAILABLE:
        return _STATIC_VALUE_NOT_AVAILABLE
    if not isinstance(separator_value, (str, bytes, bytearray)):
        return _STATIC_VALUE_NOT_AVAILABLE
    iterable_value = resolve_value(node.args[0])
    if iterable_value is _STATIC_VALUE_NOT_AVAILABLE:
        return _STATIC_VALUE_NOT_AVAILABLE
    if not _runtime_value_is_statically_empty_iterable(iterable_value):
        return _STATIC_VALUE_NOT_AVAILABLE
    return separator_value[:0]



def _try_evaluate_statically_empty_dict_fromkeys_call_value(node: ast.Call, resolve_value) -> object:
    if (
        not isinstance(node.func, ast.Attribute)
        or node.func.attr != "fromkeys"
        or not isinstance(node.func.value, ast.Name)
        or node.func.value.id != "dict"
    ):
        return _STATIC_VALUE_NOT_AVAILABLE
    iterable_node: ast.expr | None = None
    if not node.keywords and len(node.args) in (1, 2):
        iterable_node = node.args[0]
    elif len(node.args) == 1 and len(node.keywords) == 1 and node.keywords[0].arg == "value":
        iterable_node = node.args[0]
    else:
        return _STATIC_VALUE_NOT_AVAILABLE
    iterable_value = resolve_value(iterable_node)
    if iterable_value is _STATIC_VALUE_NOT_AVAILABLE:
        return _STATIC_VALUE_NOT_AVAILABLE
    if _runtime_value_is_statically_empty_iterable(iterable_value):
        return {}
    return _STATIC_VALUE_NOT_AVAILABLE



def _try_evaluate_statically_empty_range_call_value(node: ast.Call, resolve_value) -> object:
    if not isinstance(node.func, ast.Name) or node.func.id != "range" or node.keywords or not (1 <= len(node.args) <= 3):
        return _STATIC_VALUE_NOT_AVAILABLE
    arguments: list[int] = []
    for argument_node in node.args:
        argument_value = resolve_value(argument_node)
        if argument_value is _STATIC_VALUE_NOT_AVAILABLE or not isinstance(argument_value, int):
            return _STATIC_VALUE_NOT_AVAILABLE
        arguments.append(argument_value)
    try:
        range_value = range(*arguments)
    except (TypeError, ValueError) as error:
        if isinstance(error, (TypeError, ValueError)):
            return _STATIC_VALUE_NOT_AVAILABLE
        raise AssertionError("unreachable range evaluation branch")
    if len(range_value) == 0:
        return range_value
    return _STATIC_VALUE_NOT_AVAILABLE



def _try_evaluate_statically_empty_dict_view_method_value(node: ast.Call, resolve_value) -> object:
    if (
        not isinstance(node.func, ast.Attribute)
        or node.func.attr not in {"keys", "values", "items"}
        or node.args
        or node.keywords
    ):
        return _STATIC_VALUE_NOT_AVAILABLE
    base_value = resolve_value(node.func.value)
    if base_value is _STATIC_VALUE_NOT_AVAILABLE:
        return _STATIC_VALUE_NOT_AVAILABLE
    if isinstance(base_value, dict) and len(base_value) == 0:
        return _STATIC_EMPTY_ITERATOR_VALUE
    return _STATIC_VALUE_NOT_AVAILABLE



def _try_evaluate_statically_empty_dict_default_method_value(node: ast.Call, resolve_value) -> object:
    if (
        not isinstance(node.func, ast.Attribute)
        or node.func.attr not in {"get", "pop", "setdefault"}
        or node.keywords
    ):
        return _STATIC_VALUE_NOT_AVAILABLE
    if node.func.attr == "pop":
        if len(node.args) != 2:
            return _STATIC_VALUE_NOT_AVAILABLE
    elif len(node.args) not in (1, 2):
        return _STATIC_VALUE_NOT_AVAILABLE
    base_value = resolve_value(node.func.value)
    if base_value is _STATIC_VALUE_NOT_AVAILABLE or not isinstance(base_value, dict) or len(base_value) != 0:
        return _STATIC_VALUE_NOT_AVAILABLE
    key_value = resolve_value(node.args[0])
    if key_value is _STATIC_VALUE_NOT_AVAILABLE:
        return _STATIC_VALUE_NOT_AVAILABLE
    try:
        hash(key_value)
    except TypeError as error:
        if isinstance(error, TypeError):
            return _STATIC_VALUE_NOT_AVAILABLE
        raise AssertionError("unreachable dict default-method key hashability branch")
    if len(node.args) == 1:
        if node.func.attr in {"get", "setdefault"}:
            return None
        return _STATIC_VALUE_NOT_AVAILABLE
    default_value = resolve_value(node.args[1])
    if default_value is _STATIC_VALUE_NOT_AVAILABLE:
        return _STATIC_VALUE_NOT_AVAILABLE
    return default_value



def _try_evaluate_statically_empty_dict_get_method_value(node: ast.Call, resolve_value) -> object:
    return _try_evaluate_statically_empty_dict_default_method_value(node, resolve_value)



def _try_evaluate_statically_empty_dict_pop_method_value(node: ast.Call, resolve_value) -> object:
    return _try_evaluate_statically_empty_dict_default_method_value(node, resolve_value)



def _try_evaluate_statically_empty_dict_setdefault_method_value(node: ast.Call, resolve_value) -> object:
    return _try_evaluate_statically_empty_dict_default_method_value(node, resolve_value)



def _try_evaluate_statically_empty_comprehension_value(
    node: ast.ListComp | ast.SetComp | ast.DictComp,
    resolve_value,
) -> object:
    for generator in node.generators:
        iterable_value = resolve_value(generator.iter)
        if iterable_value is _STATIC_VALUE_NOT_AVAILABLE:
            continue
        if _runtime_value_is_statically_empty_iterable(iterable_value):
            if isinstance(node, ast.ListComp):
                return []
            if isinstance(node, ast.SetComp):
                return set()
            return {}
    return _STATIC_VALUE_NOT_AVAILABLE



def _try_evaluate_statically_empty_generator_expression_value(
    node: ast.GeneratorExp,
    resolve_value,
) -> object:
    for generator in node.generators:
        iterable_value = resolve_value(generator.iter)
        if iterable_value is _STATIC_VALUE_NOT_AVAILABLE:
            continue
        if _runtime_value_is_statically_empty_iterable(iterable_value):
            return _STATIC_EMPTY_ITERATOR_VALUE
    return _STATIC_VALUE_NOT_AVAILABLE



def _try_resolve_empty_iterator_consuming_constructor_value(
    constructor_name: str,
    argument_value: object,
) -> object:
    if argument_value is not _STATIC_EMPTY_ITERATOR_VALUE:
        return _STATIC_VALUE_NOT_AVAILABLE
    return _EMPTY_ITERATOR_CONSUMING_CONSTRUCTOR_VALUES.get(
        constructor_name,
        _STATIC_VALUE_NOT_AVAILABLE,
    )



def _try_evaluate_joined_string_value(node: ast.JoinedStr, resolve_value) -> object:
    values: list[str] = []
    for value_node in node.values:
        if isinstance(value_node, ast.Constant):
            if not isinstance(value_node.value, str):
                return _STATIC_VALUE_NOT_AVAILABLE
            values.append(value_node.value)
            continue
        if not isinstance(value_node, ast.FormattedValue):
            return _STATIC_VALUE_NOT_AVAILABLE
        if value_node.format_spec is not None:
            return _STATIC_VALUE_NOT_AVAILABLE
        resolved_value = resolve_value(value_node.value)
        if resolved_value is _STATIC_VALUE_NOT_AVAILABLE:
            return _STATIC_VALUE_NOT_AVAILABLE
        if value_node.conversion in (-1, 115):
            values.append(str(resolved_value))
            continue
        if value_node.conversion == 114:
            values.append(repr(resolved_value))
            continue
        if value_node.conversion == 97:
            values.append(ascii(resolved_value))
            continue
        return _STATIC_VALUE_NOT_AVAILABLE
    return "".join(values)



def _copy_runtime_value_for_zero_arg_method_evaluation(value: object) -> object:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, set):
        return set(value)
    if isinstance(value, frozenset):
        return frozenset(value)
    if isinstance(value, tuple):
        return tuple(value)
    if isinstance(value, bytearray):
        return bytearray(value)
    return value



def _try_call_zero_arg_silent_fallback_method(base_value: object, method_name: str) -> object:
    owner_types = _ZERO_ARG_SILENT_FALLBACK_METHOD_OWNERS.get(method_name)
    if owner_types is None or not isinstance(base_value, owner_types):
        return _STATIC_VALUE_NOT_AVAILABLE
    evaluation_base_value = _copy_runtime_value_for_zero_arg_method_evaluation(base_value)
    method = getattr(evaluation_base_value, method_name, None)
    if method is None:
        return _STATIC_VALUE_NOT_AVAILABLE
    try:
        return method()
    except (TypeError, ValueError, AttributeError) as error:
        if isinstance(error, (TypeError, ValueError, AttributeError)):
            return _STATIC_VALUE_NOT_AVAILABLE
        raise AssertionError("unreachable zero-arg method evaluation branch")



def _try_unpack_runtime_sequence_values(value: object) -> object:
    try:
        return list(value)
    except TypeError as error:
        if isinstance(error, TypeError):
            return _STATIC_VALUE_NOT_AVAILABLE
        raise AssertionError("unreachable sequence unpack evaluation branch")



def _try_collect_sequence_literal_values(elements: list[ast.expr], resolve_value) -> object:
    values: list[object] = []
    for element in elements:
        if isinstance(element, ast.Starred):
            unpacked_value = resolve_value(element.value)
            if unpacked_value is _STATIC_VALUE_NOT_AVAILABLE:
                return _STATIC_VALUE_NOT_AVAILABLE
            unpacked_values = _try_unpack_runtime_sequence_values(unpacked_value)
            if unpacked_values is _STATIC_VALUE_NOT_AVAILABLE:
                return _STATIC_VALUE_NOT_AVAILABLE
            values.extend(unpacked_values)
            continue
        value = resolve_value(element)
        if value is _STATIC_VALUE_NOT_AVAILABLE:
            return _STATIC_VALUE_NOT_AVAILABLE
        values.append(value)
    return values



def _try_collect_dict_literal_mapping_value(
    key_nodes: list[ast.expr | None],
    value_nodes: list[ast.expr],
    resolve_value,
) -> object:
    mapping: dict[object, object] = {}
    for key_node, value_node in zip(key_nodes, value_nodes):
        value = resolve_value(value_node)
        if value is _STATIC_VALUE_NOT_AVAILABLE:
            return _STATIC_VALUE_NOT_AVAILABLE
        if key_node is None:
            if not isinstance(value, Mapping):
                return _STATIC_VALUE_NOT_AVAILABLE
            try:
                mapping.update(value)
            except (TypeError, ValueError) as error:
                if isinstance(error, (TypeError, ValueError)):
                    return _STATIC_VALUE_NOT_AVAILABLE
                raise AssertionError("unreachable dict unpack evaluation branch")
            continue
        key = resolve_value(key_node)
        if key is _STATIC_VALUE_NOT_AVAILABLE:
            return _STATIC_VALUE_NOT_AVAILABLE
        try:
            mapping[key] = value
        except TypeError as error:
            if isinstance(error, TypeError):
                return _STATIC_VALUE_NOT_AVAILABLE
            raise AssertionError("unreachable dict literal key evaluation branch")
    return mapping


def _try_evaluate_static_expression_value(node: ast.expr | None) -> object:
    if node is None:
        return None
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return _try_evaluate_joined_string_value(
            node,
            _try_evaluate_static_expression_value,
        )
    if isinstance(node, ast.NamedExpr):
        return _try_evaluate_static_expression_value(node.value)
    if isinstance(node, ast.IfExp):
        test_value = _try_evaluate_static_expression_value(node.test)
        if test_value is _STATIC_VALUE_NOT_AVAILABLE:
            return _STATIC_VALUE_NOT_AVAILABLE
        selected_branch = node.body if bool(test_value) else node.orelse
        return _try_evaluate_static_expression_value(selected_branch)
    if isinstance(node, ast.BoolOp):
        if not node.values:
            return _STATIC_VALUE_NOT_AVAILABLE
        result = _STATIC_VALUE_NOT_AVAILABLE
        for value_node in node.values:
            result = _try_evaluate_static_expression_value(value_node)
            if result is _STATIC_VALUE_NOT_AVAILABLE:
                return _STATIC_VALUE_NOT_AVAILABLE
            if isinstance(node.op, ast.And) and not bool(result):
                return result
            if isinstance(node.op, ast.Or) and bool(result):
                return result
        return result
    if isinstance(node, ast.UnaryOp):
        operand_value = _try_evaluate_static_expression_value(node.operand)
        if operand_value is _STATIC_VALUE_NOT_AVAILABLE:
            return _STATIC_VALUE_NOT_AVAILABLE
        if isinstance(node.op, ast.Not):
            return not bool(operand_value)
        return _STATIC_VALUE_NOT_AVAILABLE
    if isinstance(node, ast.Compare):
        left_value = _try_evaluate_static_expression_value(node.left)
        if left_value is _STATIC_VALUE_NOT_AVAILABLE:
            return _STATIC_VALUE_NOT_AVAILABLE
        current_left = left_value
        for operator_node, comparator_node in zip(node.ops, node.comparators):
            right_value = _try_evaluate_static_expression_value(comparator_node)
            if right_value is _STATIC_VALUE_NOT_AVAILABLE:
                return _STATIC_VALUE_NOT_AVAILABLE
            if isinstance(operator_node, ast.Eq):
                comparison_result = current_left == right_value
            elif isinstance(operator_node, ast.NotEq):
                comparison_result = current_left != right_value
            elif isinstance(operator_node, ast.Is):
                comparison_result = current_left is right_value
            elif isinstance(operator_node, ast.IsNot):
                comparison_result = current_left is not right_value
            elif isinstance(operator_node, ast.Lt):
                comparison_result = current_left < right_value
            elif isinstance(operator_node, ast.LtE):
                comparison_result = current_left <= right_value
            elif isinstance(operator_node, ast.Gt):
                comparison_result = current_left > right_value
            elif isinstance(operator_node, ast.GtE):
                comparison_result = current_left >= right_value
            elif isinstance(operator_node, ast.In):
                comparison_result = current_left in right_value
            elif isinstance(operator_node, ast.NotIn):
                comparison_result = current_left not in right_value
            else:
                return _STATIC_VALUE_NOT_AVAILABLE
            if not comparison_result:
                return False
            current_left = right_value
        return True
    if isinstance(node, ast.BinOp):
        left_value = _try_evaluate_static_expression_value(node.left)
        right_value = _try_evaluate_static_expression_value(node.right)
        if left_value is _STATIC_VALUE_NOT_AVAILABLE or right_value is _STATIC_VALUE_NOT_AVAILABLE:
            return _STATIC_VALUE_NOT_AVAILABLE
        try:
            if isinstance(node.op, ast.Add):
                return left_value + right_value
            if isinstance(node.op, ast.Mult):
                return left_value * right_value
            if isinstance(node.op, ast.BitOr):
                return left_value | right_value
        except (TypeError, ValueError) as error:
            if isinstance(error, (TypeError, ValueError)):
                return _STATIC_VALUE_NOT_AVAILABLE
            raise AssertionError("unreachable binary evaluation branch")
        return _STATIC_VALUE_NOT_AVAILABLE
    if isinstance(node, ast.List):
        values = _try_collect_sequence_literal_values(
            node.elts,
            _try_evaluate_static_expression_value,
        )
        if values is _STATIC_VALUE_NOT_AVAILABLE:
            return _STATIC_VALUE_NOT_AVAILABLE
        return values
    if isinstance(node, ast.Tuple):
        values = _try_collect_sequence_literal_values(
            node.elts,
            _try_evaluate_static_expression_value,
        )
        if values is _STATIC_VALUE_NOT_AVAILABLE:
            return _STATIC_VALUE_NOT_AVAILABLE
        return tuple(values)
    if isinstance(node, ast.Set):
        values = _try_collect_sequence_literal_values(
            node.elts,
            _try_evaluate_static_expression_value,
        )
        if values is _STATIC_VALUE_NOT_AVAILABLE:
            return _STATIC_VALUE_NOT_AVAILABLE
        try:
            return set(values)
        except TypeError:
            return _STATIC_VALUE_NOT_AVAILABLE
    if isinstance(node, ast.Dict):
        return _try_collect_dict_literal_mapping_value(
            node.keys,
            node.values,
            _try_evaluate_static_expression_value,
        )
    if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp)):
        return _try_evaluate_statically_empty_comprehension_value(
            node,
            _try_evaluate_static_expression_value,
        )
    if isinstance(node, ast.GeneratorExp):
        return _try_evaluate_statically_empty_generator_expression_value(
            node,
            _try_evaluate_static_expression_value,
        )
    if isinstance(node, ast.Subscript):
        base_value = _try_evaluate_static_expression_value(node.value)
        if base_value is _STATIC_VALUE_NOT_AVAILABLE:
            return _STATIC_VALUE_NOT_AVAILABLE
        subscript_key_value = _try_evaluate_static_subscript_key_value(node.slice)
        if subscript_key_value is _STATIC_VALUE_NOT_AVAILABLE:
            return _STATIC_VALUE_NOT_AVAILABLE
        return _try_apply_subscript_to_runtime_value(base_value, subscript_key_value)
    if not isinstance(node, ast.Call):
        return _STATIC_VALUE_NOT_AVAILABLE
    empty_zip_value = _try_evaluate_statically_empty_zip_call_value(
        node,
        _try_evaluate_static_expression_value,
    )
    if empty_zip_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_zip_value
    empty_iter_value = _try_evaluate_statically_empty_iter_call_value(
        node,
        _try_evaluate_static_expression_value,
    )
    if empty_iter_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_iter_value
    empty_reversed_value = _try_evaluate_statically_empty_reversed_call_value(
        node,
        _try_evaluate_static_expression_value,
    )
    if empty_reversed_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_reversed_value
    empty_enumerate_value = _try_evaluate_statically_empty_enumerate_call_value(
        node,
        _try_evaluate_static_expression_value,
    )
    if empty_enumerate_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_enumerate_value
    empty_map_value = _try_evaluate_statically_empty_map_call_value(
        node,
        _try_evaluate_static_expression_value,
    )
    if empty_map_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_map_value
    empty_filter_value = _try_evaluate_statically_empty_filter_call_value(
        node,
        _try_evaluate_static_expression_value,
    )
    if empty_filter_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_filter_value
    empty_next_value = _try_evaluate_statically_empty_next_call_value(
        node,
        _try_evaluate_static_expression_value,
    )
    if empty_next_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_next_value
    empty_sorted_value = _try_evaluate_statically_empty_sorted_call_value(
        node,
        _try_evaluate_static_expression_value,
    )
    if empty_sorted_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_sorted_value
    empty_join_value = _try_evaluate_statically_empty_join_method_value(
        node,
        _try_evaluate_static_expression_value,
    )
    if empty_join_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_join_value
    empty_dict_fromkeys_value = _try_evaluate_statically_empty_dict_fromkeys_call_value(
        node,
        _try_evaluate_static_expression_value,
    )
    if empty_dict_fromkeys_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_dict_fromkeys_value
    empty_range_value = _try_evaluate_statically_empty_range_call_value(
        node,
        _try_evaluate_static_expression_value,
    )
    if empty_range_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_range_value
    empty_dict_view_value = _try_evaluate_statically_empty_dict_view_method_value(
        node,
        _try_evaluate_static_expression_value,
    )
    if empty_dict_view_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_dict_view_value
    empty_dict_get_value = _try_evaluate_statically_empty_dict_get_method_value(
        node,
        _try_evaluate_static_expression_value,
    )
    if empty_dict_get_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_dict_get_value
    empty_dict_pop_value = _try_evaluate_statically_empty_dict_pop_method_value(
        node,
        _try_evaluate_static_expression_value,
    )
    if empty_dict_pop_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_dict_pop_value
    empty_dict_setdefault_value = _try_evaluate_statically_empty_dict_setdefault_method_value(
        node,
        _try_evaluate_static_expression_value,
    )
    if empty_dict_setdefault_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_dict_setdefault_value
    if isinstance(node.func, ast.Attribute) and not node.args and not node.keywords:
        base_value = _try_evaluate_static_expression_value(node.func.value)
        if base_value is _STATIC_VALUE_NOT_AVAILABLE:
            return _STATIC_VALUE_NOT_AVAILABLE
        return _try_call_zero_arg_silent_fallback_method(base_value, node.func.attr)
    if not isinstance(node.func, ast.Name):
        return _STATIC_VALUE_NOT_AVAILABLE
    if not node.keywords and not node.args and node.func.id in _ZERO_ARG_SILENT_FALLBACK_CONSTRUCTOR_VALUES:
        return _ZERO_ARG_SILENT_FALLBACK_CONSTRUCTOR_VALUES[node.func.id]
    if len(node.keywords) == 1 and not node.args:
        keyword = node.keywords[0]
        if keyword.arg is None:
            return _STATIC_VALUE_NOT_AVAILABLE
        constructor_map = _SINGLE_KEYWORD_SILENT_FALLBACK_CONSTRUCTORS.get(node.func.id)
        if constructor_map is None:
            return _STATIC_VALUE_NOT_AVAILABLE
        constructor = constructor_map.get(keyword.arg)
        if constructor is None:
            return _STATIC_VALUE_NOT_AVAILABLE
        argument_value = _try_evaluate_static_expression_value(keyword.value)
        generator_expression_value = _try_resolve_empty_iterator_consuming_constructor_value(
            node.func.id,
            argument_value,
        )
        if generator_expression_value is not _STATIC_VALUE_NOT_AVAILABLE:
            return generator_expression_value
        if (
            argument_value is _STATIC_VALUE_NOT_AVAILABLE
            or argument_value is _STATIC_EMPTY_ITERATOR_VALUE
        ):
            return _STATIC_VALUE_NOT_AVAILABLE
        try:
            return constructor(argument_value)
        except (TypeError, ValueError) as error:
            if isinstance(error, (TypeError, ValueError)):
                return _STATIC_VALUE_NOT_AVAILABLE
            raise AssertionError("unreachable keyword constructor evaluation branch")
    if node.keywords or len(node.args) != 1:
        return _STATIC_VALUE_NOT_AVAILABLE
    constructor = _SINGLE_ARG_SILENT_FALLBACK_CONSTRUCTORS.get(node.func.id)
    if constructor is None:
        return _STATIC_VALUE_NOT_AVAILABLE
    argument_value = _try_evaluate_static_expression_value(node.args[0])
    generator_expression_value = _try_resolve_empty_iterator_consuming_constructor_value(
        node.func.id,
        argument_value,
    )
    if generator_expression_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return generator_expression_value
    if (
        argument_value is _STATIC_VALUE_NOT_AVAILABLE
        or argument_value is _STATIC_EMPTY_ITERATOR_VALUE
    ):
        return _STATIC_VALUE_NOT_AVAILABLE
    try:
        return constructor(argument_value)
    except (TypeError, ValueError) as error:
        if isinstance(error, (TypeError, ValueError)):
            return _STATIC_VALUE_NOT_AVAILABLE
        raise AssertionError("unreachable constructor evaluation branch")



def _try_evaluate_static_subscript_key_value(node: ast.expr) -> object:
    if isinstance(node, ast.Slice):
        lower_value = _try_evaluate_static_expression_value(node.lower)
        upper_value = _try_evaluate_static_expression_value(node.upper)
        step_value = _try_evaluate_static_expression_value(node.step)
        if (
            lower_value is _STATIC_VALUE_NOT_AVAILABLE
            or upper_value is _STATIC_VALUE_NOT_AVAILABLE
            or step_value is _STATIC_VALUE_NOT_AVAILABLE
        ):
            return _STATIC_VALUE_NOT_AVAILABLE
        return slice(lower_value, upper_value, step_value)
    return _try_evaluate_static_expression_value(node)



def _try_apply_subscript_to_runtime_value(base_value: object, subscript_key_value: object) -> object:
    try:
        return base_value[subscript_key_value]
    except (TypeError, ValueError, IndexError, KeyError) as error:
        if isinstance(error, (TypeError, ValueError, IndexError, KeyError)):
            return _STATIC_VALUE_NOT_AVAILABLE
        raise AssertionError("unreachable subscript evaluation branch")



def _try_resolve_known_name_subscript_key_value(
    node: ast.expr,
    known_name_values: dict[str, object],
) -> object:
    if isinstance(node, ast.Slice):
        lower_value = _try_resolve_known_name_silent_fallback_runtime_value(
            node.lower,
            known_name_values,
        )
        upper_value = _try_resolve_known_name_silent_fallback_runtime_value(
            node.upper,
            known_name_values,
        )
        step_value = _try_resolve_known_name_silent_fallback_runtime_value(
            node.step,
            known_name_values,
        )
        if (
            lower_value is _STATIC_VALUE_NOT_AVAILABLE
            or upper_value is _STATIC_VALUE_NOT_AVAILABLE
            or step_value is _STATIC_VALUE_NOT_AVAILABLE
        ):
            return _STATIC_VALUE_NOT_AVAILABLE
        return slice(lower_value, upper_value, step_value)
    return _try_resolve_known_name_silent_fallback_runtime_value(node, known_name_values)



def _is_direct_silent_fallback_return_value(node: ast.expr | None) -> bool:
    return _runtime_value_is_silent_fallback(_try_evaluate_static_expression_value(node))



def _extract_simple_name_assignment_target_names_and_value(statement: ast.stmt) -> tuple[list[str], ast.expr | None] | None:
    if isinstance(statement, ast.Assign):
        target_names: list[str] = []
        for target in statement.targets:
            if not isinstance(target, ast.Name):
                return None
            target_names.append(target.id)
        if target_names:
            return target_names, statement.value
    elif isinstance(statement, ast.AnnAssign):
        if isinstance(statement.target, ast.Name) and statement.value is not None:
            return [statement.target.id], statement.value
    return None



def _try_resolve_known_name_silent_fallback_runtime_value(
    node: ast.expr | None,
    known_name_values: dict[str, object],
) -> object:
    static_value = _try_evaluate_static_expression_value(node)
    if static_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return static_value
    if isinstance(node, ast.Name):
        return known_name_values.get(node.id, _STATIC_VALUE_NOT_AVAILABLE)
    if isinstance(node, ast.JoinedStr):
        return _try_evaluate_joined_string_value(
            node,
            lambda expression: _try_resolve_known_name_silent_fallback_runtime_value(
                expression,
                known_name_values,
            ),
        )
    if isinstance(node, ast.NamedExpr):
        return _try_resolve_known_name_silent_fallback_runtime_value(
            node.value,
            known_name_values,
        )
    if isinstance(node, ast.List):
        values = _try_collect_sequence_literal_values(
            node.elts,
            lambda expression: _try_resolve_known_name_silent_fallback_runtime_value(
                expression,
                known_name_values,
            ),
        )
        if values is _STATIC_VALUE_NOT_AVAILABLE:
            return _STATIC_VALUE_NOT_AVAILABLE
        return values
    if isinstance(node, ast.Tuple):
        values = _try_collect_sequence_literal_values(
            node.elts,
            lambda expression: _try_resolve_known_name_silent_fallback_runtime_value(
                expression,
                known_name_values,
            ),
        )
        if values is _STATIC_VALUE_NOT_AVAILABLE:
            return _STATIC_VALUE_NOT_AVAILABLE
        return tuple(values)
    if isinstance(node, ast.Set):
        values = _try_collect_sequence_literal_values(
            node.elts,
            lambda expression: _try_resolve_known_name_silent_fallback_runtime_value(
                expression,
                known_name_values,
            ),
        )
        if values is _STATIC_VALUE_NOT_AVAILABLE:
            return _STATIC_VALUE_NOT_AVAILABLE
        try:
            return set(values)
        except TypeError:
            return _STATIC_VALUE_NOT_AVAILABLE
    if isinstance(node, ast.Dict):
        return _try_collect_dict_literal_mapping_value(
            node.keys,
            node.values,
            lambda expression: _try_resolve_known_name_silent_fallback_runtime_value(
                expression,
                known_name_values,
            ),
        )
    if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp)):
        return _try_evaluate_statically_empty_comprehension_value(
            node,
            lambda expression: _try_resolve_known_name_silent_fallback_runtime_value(
                expression,
                known_name_values,
            ),
        )
    if isinstance(node, ast.GeneratorExp):
        return _try_evaluate_statically_empty_generator_expression_value(
            node,
            lambda expression: _try_resolve_known_name_silent_fallback_runtime_value(
                expression,
                known_name_values,
            ),
        )
    if isinstance(node, ast.IfExp):
        test_value = _try_resolve_known_name_silent_fallback_runtime_value(
            node.test,
            known_name_values,
        )
        if test_value is _STATIC_VALUE_NOT_AVAILABLE:
            return _STATIC_VALUE_NOT_AVAILABLE
        selected_branch = node.body if bool(test_value) else node.orelse
        return _try_resolve_known_name_silent_fallback_runtime_value(
            selected_branch,
            known_name_values,
        )
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.Or):
            resolved_value: object = _STATIC_VALUE_NOT_AVAILABLE
            for value_node in node.values:
                resolved_value = _try_resolve_known_name_silent_fallback_runtime_value(
                    value_node,
                    known_name_values,
                )
                if resolved_value is _STATIC_VALUE_NOT_AVAILABLE:
                    return _STATIC_VALUE_NOT_AVAILABLE
                if bool(resolved_value):
                    return resolved_value
            return resolved_value
        if isinstance(node.op, ast.And):
            resolved_value: object = _STATIC_VALUE_NOT_AVAILABLE
            for value_node in node.values:
                resolved_value = _try_resolve_known_name_silent_fallback_runtime_value(
                    value_node,
                    known_name_values,
                )
                if resolved_value is _STATIC_VALUE_NOT_AVAILABLE:
                    return _STATIC_VALUE_NOT_AVAILABLE
                if not bool(resolved_value):
                    return resolved_value
            return resolved_value
        return _STATIC_VALUE_NOT_AVAILABLE
    if isinstance(node, ast.UnaryOp):
        operand_value = _try_resolve_known_name_silent_fallback_runtime_value(
            node.operand,
            known_name_values,
        )
        if operand_value is _STATIC_VALUE_NOT_AVAILABLE:
            return _STATIC_VALUE_NOT_AVAILABLE
        if isinstance(node.op, ast.Not):
            return not bool(operand_value)
        return _STATIC_VALUE_NOT_AVAILABLE
    if isinstance(node, ast.Compare):
        left_value = _try_resolve_known_name_silent_fallback_runtime_value(
            node.left,
            known_name_values,
        )
        if left_value is _STATIC_VALUE_NOT_AVAILABLE:
            return _STATIC_VALUE_NOT_AVAILABLE
        current_left = left_value
        for operator_node, comparator_node in zip(node.ops, node.comparators):
            right_value = _try_resolve_known_name_silent_fallback_runtime_value(
                comparator_node,
                known_name_values,
            )
            if right_value is _STATIC_VALUE_NOT_AVAILABLE:
                return _STATIC_VALUE_NOT_AVAILABLE
            try:
                if isinstance(operator_node, ast.Eq):
                    comparison_result = current_left == right_value
                elif isinstance(operator_node, ast.NotEq):
                    comparison_result = current_left != right_value
                elif isinstance(operator_node, ast.Is):
                    comparison_result = current_left is right_value
                elif isinstance(operator_node, ast.IsNot):
                    comparison_result = current_left is not right_value
                elif isinstance(operator_node, ast.Lt):
                    comparison_result = current_left < right_value
                elif isinstance(operator_node, ast.LtE):
                    comparison_result = current_left <= right_value
                elif isinstance(operator_node, ast.Gt):
                    comparison_result = current_left > right_value
                elif isinstance(operator_node, ast.GtE):
                    comparison_result = current_left >= right_value
                elif isinstance(operator_node, ast.In):
                    comparison_result = current_left in right_value
                elif isinstance(operator_node, ast.NotIn):
                    comparison_result = current_left not in right_value
                else:
                    return _STATIC_VALUE_NOT_AVAILABLE
            except TypeError as error:
                if isinstance(error, TypeError):
                    return _STATIC_VALUE_NOT_AVAILABLE
                raise AssertionError("unreachable known-name compare evaluation branch")
            if not comparison_result:
                return False
            current_left = right_value
        return True
    if isinstance(node, ast.BinOp):
        left_value = _try_resolve_known_name_silent_fallback_runtime_value(
            node.left,
            known_name_values,
        )
        right_value = _try_resolve_known_name_silent_fallback_runtime_value(
            node.right,
            known_name_values,
        )
        if left_value is _STATIC_VALUE_NOT_AVAILABLE or right_value is _STATIC_VALUE_NOT_AVAILABLE:
            return _STATIC_VALUE_NOT_AVAILABLE
        try:
            if isinstance(node.op, ast.Add):
                return left_value + right_value
            if isinstance(node.op, ast.Mult):
                return left_value * right_value
            if isinstance(node.op, ast.BitOr):
                return left_value | right_value
        except (TypeError, ValueError) as error:
            if isinstance(error, (TypeError, ValueError)):
                return _STATIC_VALUE_NOT_AVAILABLE
            raise AssertionError("unreachable known-name binop evaluation branch")
        return _STATIC_VALUE_NOT_AVAILABLE
    if isinstance(node, ast.Subscript):
        base_value = _try_resolve_known_name_silent_fallback_runtime_value(
            node.value,
            known_name_values,
        )
        if base_value is _STATIC_VALUE_NOT_AVAILABLE:
            return _STATIC_VALUE_NOT_AVAILABLE
        subscript_key_value = _try_resolve_known_name_subscript_key_value(
            node.slice,
            known_name_values,
        )
        if subscript_key_value is _STATIC_VALUE_NOT_AVAILABLE:
            return _STATIC_VALUE_NOT_AVAILABLE
        return _try_apply_subscript_to_runtime_value(base_value, subscript_key_value)
    if not isinstance(node, ast.Call):
        return _STATIC_VALUE_NOT_AVAILABLE
    empty_zip_value = _try_evaluate_statically_empty_zip_call_value(
        node,
        lambda expression: _try_resolve_known_name_silent_fallback_runtime_value(
            expression,
            known_name_values,
        ),
    )
    if empty_zip_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_zip_value
    empty_iter_value = _try_evaluate_statically_empty_iter_call_value(
        node,
        lambda expression: _try_resolve_known_name_silent_fallback_runtime_value(
            expression,
            known_name_values,
        ),
    )
    if empty_iter_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_iter_value
    empty_reversed_value = _try_evaluate_statically_empty_reversed_call_value(
        node,
        lambda expression: _try_resolve_known_name_silent_fallback_runtime_value(
            expression,
            known_name_values,
        ),
    )
    if empty_reversed_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_reversed_value
    empty_enumerate_value = _try_evaluate_statically_empty_enumerate_call_value(
        node,
        lambda expression: _try_resolve_known_name_silent_fallback_runtime_value(
            expression,
            known_name_values,
        ),
    )
    if empty_enumerate_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_enumerate_value
    empty_map_value = _try_evaluate_statically_empty_map_call_value(
        node,
        lambda expression: _try_resolve_known_name_silent_fallback_runtime_value(
            expression,
            known_name_values,
        ),
    )
    if empty_map_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_map_value
    empty_filter_value = _try_evaluate_statically_empty_filter_call_value(
        node,
        lambda expression: _try_resolve_known_name_silent_fallback_runtime_value(
            expression,
            known_name_values,
        ),
    )
    if empty_filter_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_filter_value
    empty_next_value = _try_evaluate_statically_empty_next_call_value(
        node,
        lambda expression: _try_resolve_known_name_silent_fallback_runtime_value(
            expression,
            known_name_values,
        ),
    )
    if empty_next_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_next_value
    empty_sorted_value = _try_evaluate_statically_empty_sorted_call_value(
        node,
        lambda expression: _try_resolve_known_name_silent_fallback_runtime_value(
            expression,
            known_name_values,
        ),
    )
    if empty_sorted_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_sorted_value
    empty_join_value = _try_evaluate_statically_empty_join_method_value(
        node,
        lambda expression: _try_resolve_known_name_silent_fallback_runtime_value(
            expression,
            known_name_values,
        ),
    )
    if empty_join_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_join_value
    empty_dict_fromkeys_value = _try_evaluate_statically_empty_dict_fromkeys_call_value(
        node,
        lambda expression: _try_resolve_known_name_silent_fallback_runtime_value(
            expression,
            known_name_values,
        ),
    )
    if empty_dict_fromkeys_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_dict_fromkeys_value
    empty_range_value = _try_evaluate_statically_empty_range_call_value(
        node,
        lambda expression: _try_resolve_known_name_silent_fallback_runtime_value(
            expression,
            known_name_values,
        ),
    )
    if empty_range_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_range_value
    empty_dict_view_value = _try_evaluate_statically_empty_dict_view_method_value(
        node,
        lambda expression: _try_resolve_known_name_silent_fallback_runtime_value(
            expression,
            known_name_values,
        ),
    )
    if empty_dict_view_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_dict_view_value
    empty_dict_get_value = _try_evaluate_statically_empty_dict_get_method_value(
        node,
        lambda expression: _try_resolve_known_name_silent_fallback_runtime_value(
            expression,
            known_name_values,
        ),
    )
    if empty_dict_get_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_dict_get_value
    empty_dict_pop_value = _try_evaluate_statically_empty_dict_pop_method_value(
        node,
        lambda expression: _try_resolve_known_name_silent_fallback_runtime_value(
            expression,
            known_name_values,
        ),
    )
    if empty_dict_pop_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_dict_pop_value
    empty_dict_setdefault_value = _try_evaluate_statically_empty_dict_setdefault_method_value(
        node,
        lambda expression: _try_resolve_known_name_silent_fallback_runtime_value(
            expression,
            known_name_values,
        ),
    )
    if empty_dict_setdefault_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_dict_setdefault_value
    if isinstance(node.func, ast.Attribute) and not node.args and not node.keywords:
        base_value = _try_resolve_known_name_silent_fallback_runtime_value(
            node.func.value,
            known_name_values,
        )
        if base_value is _STATIC_VALUE_NOT_AVAILABLE:
            return _STATIC_VALUE_NOT_AVAILABLE
        return _try_call_zero_arg_silent_fallback_method(base_value, node.func.attr)
    if not isinstance(node.func, ast.Name):
        return _STATIC_VALUE_NOT_AVAILABLE
    if len(node.keywords) == 1 and not node.args:
        keyword = node.keywords[0]
        if keyword.arg is None:
            return _STATIC_VALUE_NOT_AVAILABLE
        constructor_map = _SINGLE_KEYWORD_SILENT_FALLBACK_CONSTRUCTORS.get(node.func.id)
        if constructor_map is None:
            return _STATIC_VALUE_NOT_AVAILABLE
        constructor = constructor_map.get(keyword.arg)
        if constructor is None:
            return _STATIC_VALUE_NOT_AVAILABLE
        argument_value = _try_resolve_known_name_silent_fallback_runtime_value(
            keyword.value,
            known_name_values,
        )
        generator_expression_value = _try_resolve_empty_iterator_consuming_constructor_value(
            node.func.id,
            argument_value,
        )
        if generator_expression_value is not _STATIC_VALUE_NOT_AVAILABLE:
            return generator_expression_value
        if (
            argument_value is _STATIC_VALUE_NOT_AVAILABLE
            or argument_value is _STATIC_EMPTY_ITERATOR_VALUE
        ):
            return _STATIC_VALUE_NOT_AVAILABLE
        try:
            return constructor(argument_value)
        except (TypeError, ValueError) as error:
            if isinstance(error, (TypeError, ValueError)):
                return _STATIC_VALUE_NOT_AVAILABLE
            raise AssertionError("unreachable known-name keyword constructor evaluation branch")
    if node.keywords or len(node.args) != 1:
        return _STATIC_VALUE_NOT_AVAILABLE
    argument_value = _try_resolve_known_name_silent_fallback_runtime_value(
        node.args[0],
        known_name_values,
    )
    generator_expression_value = _try_resolve_empty_iterator_consuming_constructor_value(
        node.func.id,
        argument_value,
    )
    if generator_expression_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return generator_expression_value
    if (
        argument_value is _STATIC_VALUE_NOT_AVAILABLE
        or argument_value is _STATIC_EMPTY_ITERATOR_VALUE
    ):
        return _STATIC_VALUE_NOT_AVAILABLE
    constructor = _SINGLE_ARG_SILENT_FALLBACK_CONSTRUCTORS.get(node.func.id)
    if constructor is None:
        return _STATIC_VALUE_NOT_AVAILABLE
    try:
        return constructor(argument_value)
    except (TypeError, ValueError) as error:
        if isinstance(error, (TypeError, ValueError)):
            return _STATIC_VALUE_NOT_AVAILABLE
        raise AssertionError("unreachable known-name constructor evaluation branch")



def _is_assignment_then_same_name_return_silent_fallback(body: list[ast.stmt]) -> bool:
    if len(body) < 2:
        return False
    return_statement = body[-1]
    if not isinstance(return_statement, ast.Return):
        return False
    known_name_values: dict[str, object] = {}
    for statement in body[:-1]:
        assignment_info = _extract_simple_name_assignment_target_names_and_value(statement)
        if assignment_info is None:
            return False
        assignment_target_names, assignment_value = assignment_info
        runtime_value = _try_resolve_known_name_silent_fallback_runtime_value(
            assignment_value,
            known_name_values,
        )
        if not _runtime_value_is_trackable_silent_fallback_assignment_value(runtime_value):
            return False
        for assignment_target_name in assignment_target_names:
            known_name_values[assignment_target_name] = runtime_value
    return _runtime_value_is_silent_fallback(
        _try_resolve_known_name_silent_fallback_runtime_value(
            return_statement.value,
            known_name_values,
        )
    )



def _is_direct_silent_fallback_return_handler(handler: ast.ExceptHandler) -> bool:
    if len(handler.body) == 1:
        statement = handler.body[0]
        if not isinstance(statement, ast.Return):
            return False
        return _is_direct_silent_fallback_return_value(statement.value)
    return _is_assignment_then_same_name_return_silent_fallback(handler.body)


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
