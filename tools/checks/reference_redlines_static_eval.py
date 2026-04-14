from __future__ import annotations

import ast
from collections.abc import Mapping

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
_POSITIONAL_EMPTY_PADDING_METHOD_OWNERS = {
    "zfill": (str, bytes, bytearray),
    "center": (str, bytes, bytearray),
    "ljust": (str, bytes, bytearray),
    "rjust": (str, bytes, bytearray),
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



def _runtime_value_is_trackable_known_name_assignment_value(value: object) -> bool:
    return value is not _STATIC_VALUE_NOT_AVAILABLE



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



def _try_evaluate_statically_empty_any_call_value(node: ast.Call, resolve_value) -> object:
    if not isinstance(node.func, ast.Name) or node.func.id != "any" or node.keywords or len(node.args) != 1:
        return _STATIC_VALUE_NOT_AVAILABLE
    iterable_value = resolve_value(node.args[0])
    if iterable_value is _STATIC_VALUE_NOT_AVAILABLE:
        return _STATIC_VALUE_NOT_AVAILABLE
    if _runtime_value_is_statically_empty_iterable(iterable_value):
        return False
    return _STATIC_VALUE_NOT_AVAILABLE



def _try_evaluate_statically_empty_all_call_value(node: ast.Call, resolve_value) -> object:
    if not isinstance(node.func, ast.Name) or node.func.id != "all" or node.keywords or len(node.args) != 1:
        return _STATIC_VALUE_NOT_AVAILABLE
    iterable_value = resolve_value(node.args[0])
    if iterable_value is _STATIC_VALUE_NOT_AVAILABLE:
        return _STATIC_VALUE_NOT_AVAILABLE
    if _runtime_value_is_statically_empty_iterable(iterable_value):
        return True
    return _STATIC_VALUE_NOT_AVAILABLE



def _try_evaluate_statically_empty_len_call_value(node: ast.Call, resolve_value) -> object:
    if not isinstance(node.func, ast.Name) or node.func.id != "len" or node.keywords or len(node.args) != 1:
        return _STATIC_VALUE_NOT_AVAILABLE
    value = resolve_value(node.args[0])
    if value is _STATIC_VALUE_NOT_AVAILABLE:
        return _STATIC_VALUE_NOT_AVAILABLE
    if _runtime_value_is_statically_empty_iterable(value):
        return 0
    return _STATIC_VALUE_NOT_AVAILABLE



def _try_evaluate_statically_empty_sum_call_value(node: ast.Call, resolve_value) -> object:
    if not isinstance(node.func, ast.Name) or node.func.id != "sum" or node.keywords or len(node.args) != 1:
        return _STATIC_VALUE_NOT_AVAILABLE
    value = resolve_value(node.args[0])
    if value is _STATIC_VALUE_NOT_AVAILABLE:
        return _STATIC_VALUE_NOT_AVAILABLE
    if _runtime_value_is_statically_empty_iterable(value):
        return 0
    return _STATIC_VALUE_NOT_AVAILABLE



def _try_evaluate_statically_empty_count_method_value(node: ast.Call, resolve_value) -> object:
    if (
        not isinstance(node.func, ast.Attribute)
        or node.func.attr != "count"
        or node.keywords
        or len(node.args) != 1
    ):
        return _STATIC_VALUE_NOT_AVAILABLE
    base_value = resolve_value(node.func.value)
    if base_value is _STATIC_VALUE_NOT_AVAILABLE:
        return _STATIC_VALUE_NOT_AVAILABLE
    if isinstance(base_value, (str, bytes, bytearray, list, tuple, range)) and len(base_value) == 0:
        return 0
    return _STATIC_VALUE_NOT_AVAILABLE



def _try_evaluate_statically_empty_removal_method_value(node: ast.Call, resolve_value) -> object:
    if (
        not isinstance(node.func, ast.Attribute)
        or node.func.attr not in {"removeprefix", "removesuffix"}
        or node.keywords
        or len(node.args) != 1
    ):
        return _STATIC_VALUE_NOT_AVAILABLE
    base_value = resolve_value(node.func.value)
    if base_value is _STATIC_VALUE_NOT_AVAILABLE:
        return _STATIC_VALUE_NOT_AVAILABLE
    argument_value = resolve_value(node.args[0])
    if argument_value is _STATIC_VALUE_NOT_AVAILABLE:
        return _STATIC_VALUE_NOT_AVAILABLE
    if isinstance(base_value, str) and isinstance(argument_value, str) and len(base_value) == 0:
        return ""
    if isinstance(base_value, (bytes, bytearray)) and isinstance(argument_value, (bytes, bytearray)) and len(base_value) == 0:
        return base_value[:0]
    return _STATIC_VALUE_NOT_AVAILABLE



def _try_evaluate_statically_empty_strip_method_with_arg_value(node: ast.Call, resolve_value) -> object:
    if (
        not isinstance(node.func, ast.Attribute)
        or node.func.attr not in {"strip", "lstrip", "rstrip"}
        or node.keywords
        or len(node.args) != 1
    ):
        return _STATIC_VALUE_NOT_AVAILABLE
    base_value = resolve_value(node.func.value)
    if base_value is _STATIC_VALUE_NOT_AVAILABLE:
        return _STATIC_VALUE_NOT_AVAILABLE
    argument_value = resolve_value(node.args[0])
    if argument_value is _STATIC_VALUE_NOT_AVAILABLE:
        return _STATIC_VALUE_NOT_AVAILABLE
    if isinstance(base_value, str) and isinstance(argument_value, str) and len(base_value) == 0:
        return ""
    if isinstance(base_value, (bytes, bytearray)) and isinstance(argument_value, (bytes, bytearray)) and len(base_value) == 0:
        return base_value[:0]
    return _STATIC_VALUE_NOT_AVAILABLE



def _try_evaluate_statically_empty_replace_method_value(node: ast.Call, resolve_value) -> object:
    if (
        not isinstance(node.func, ast.Attribute)
        or node.func.attr != "replace"
        or len(node.args) not in {2, 3}
    ):
        return _STATIC_VALUE_NOT_AVAILABLE
    if len(node.keywords) > 1:
        return _STATIC_VALUE_NOT_AVAILABLE
    count_keyword = node.keywords[0] if node.keywords else None
    if count_keyword is not None and count_keyword.arg != "count":
        return _STATIC_VALUE_NOT_AVAILABLE
    if len(node.args) == 3 and count_keyword is not None:
        return _STATIC_VALUE_NOT_AVAILABLE
    base_value = resolve_value(node.func.value)
    if base_value is _STATIC_VALUE_NOT_AVAILABLE:
        return _STATIC_VALUE_NOT_AVAILABLE
    old_value = resolve_value(node.args[0])
    if old_value is _STATIC_VALUE_NOT_AVAILABLE:
        return _STATIC_VALUE_NOT_AVAILABLE
    new_value = resolve_value(node.args[1])
    if new_value is _STATIC_VALUE_NOT_AVAILABLE:
        return _STATIC_VALUE_NOT_AVAILABLE
    if len(node.args) == 3:
        count_value = resolve_value(node.args[2])
        if count_value is _STATIC_VALUE_NOT_AVAILABLE or not isinstance(count_value, int):
            return _STATIC_VALUE_NOT_AVAILABLE
    if count_keyword is not None:
        count_value = resolve_value(count_keyword.value)
        if count_value is _STATIC_VALUE_NOT_AVAILABLE or not isinstance(count_value, int):
            return _STATIC_VALUE_NOT_AVAILABLE
    if isinstance(base_value, str) and isinstance(old_value, str) and isinstance(new_value, str) and len(base_value) == 0:
        return ""
    if (
        isinstance(base_value, (bytes, bytearray))
        and isinstance(old_value, (bytes, bytearray))
        and isinstance(new_value, (bytes, bytearray))
        and len(base_value) == 0
    ):
        return base_value[:0]
    return _STATIC_VALUE_NOT_AVAILABLE



def _try_evaluate_statically_empty_translate_method_value(node: ast.Call, resolve_value) -> object:
    if (
        not isinstance(node.func, ast.Attribute)
        or node.func.attr != "translate"
        or node.keywords
        or len(node.args) != 1
    ):
        return _STATIC_VALUE_NOT_AVAILABLE
    base_value = resolve_value(node.func.value)
    if base_value is _STATIC_VALUE_NOT_AVAILABLE:
        return _STATIC_VALUE_NOT_AVAILABLE
    argument_value = resolve_value(node.args[0])
    if argument_value is _STATIC_VALUE_NOT_AVAILABLE:
        return _STATIC_VALUE_NOT_AVAILABLE
    if isinstance(base_value, str) and len(base_value) == 0:
        return ""
    if isinstance(base_value, (bytes, bytearray)) and argument_value is None and len(base_value) == 0:
        return base_value[:0]
    return _STATIC_VALUE_NOT_AVAILABLE



def _try_evaluate_statically_empty_codec_method_value(node: ast.Call, resolve_value) -> object:
    if (
        not isinstance(node.func, ast.Attribute)
        or node.func.attr not in {"encode", "decode"}
        or len(node.args) not in {0, 1, 2}
        or len(node.keywords) > 2
    ):
        return _STATIC_VALUE_NOT_AVAILABLE
    keyword_values: dict[str, str] = {}
    for keyword in node.keywords:
        if keyword.arg not in {"encoding", "errors"} or keyword.arg in keyword_values:
            return _STATIC_VALUE_NOT_AVAILABLE
        keyword_value = resolve_value(keyword.value)
        if keyword_value is _STATIC_VALUE_NOT_AVAILABLE or not isinstance(keyword_value, str):
            return _STATIC_VALUE_NOT_AVAILABLE
        keyword_values[keyword.arg] = keyword_value
    if len(node.args) == 0 and not keyword_values:
        return _STATIC_VALUE_NOT_AVAILABLE
    base_value = resolve_value(node.func.value)
    if base_value is _STATIC_VALUE_NOT_AVAILABLE:
        return _STATIC_VALUE_NOT_AVAILABLE
    if node.func.attr == "encode":
        if not isinstance(base_value, str) or len(base_value) != 0:
            return _STATIC_VALUE_NOT_AVAILABLE
    else:
        if not isinstance(base_value, (bytes, bytearray)) or len(base_value) != 0:
            return _STATIC_VALUE_NOT_AVAILABLE
    argument_values: list[str] = []
    for argument_node in node.args:
        argument_value = resolve_value(argument_node)
        if argument_value is _STATIC_VALUE_NOT_AVAILABLE or not isinstance(argument_value, str):
            return _STATIC_VALUE_NOT_AVAILABLE
        argument_values.append(argument_value)
    evaluation_base_value = _copy_runtime_value_for_zero_arg_method_evaluation(base_value)
    method = getattr(evaluation_base_value, node.func.attr, None)
    if method is None:
        return _STATIC_VALUE_NOT_AVAILABLE
    try:
        result = method(*argument_values, **keyword_values)
    except (LookupError, TypeError, ValueError, AttributeError) as error:
        if isinstance(error, (LookupError, TypeError, ValueError, AttributeError)):
            return _STATIC_VALUE_NOT_AVAILABLE
        raise AssertionError("unreachable codec method evaluation branch")
    if _runtime_value_is_silent_fallback(result):
        return result
    return _STATIC_VALUE_NOT_AVAILABLE



def _try_evaluate_statically_empty_format_method_value(node: ast.Call, resolve_value) -> object:
    if not isinstance(node.func, ast.Attribute) or node.func.attr != "format":
        return _STATIC_VALUE_NOT_AVAILABLE
    base_value = resolve_value(node.func.value)
    if base_value is _STATIC_VALUE_NOT_AVAILABLE or not isinstance(base_value, str) or len(base_value) != 0:
        return _STATIC_VALUE_NOT_AVAILABLE
    argument_values: list[object] = []
    for argument_node in node.args:
        argument_value = resolve_value(argument_node)
        if argument_value is _STATIC_VALUE_NOT_AVAILABLE:
            return _STATIC_VALUE_NOT_AVAILABLE
        argument_values.append(argument_value)
    keyword_values: dict[str, object] = {}
    for keyword in node.keywords:
        if keyword.arg is None:
            return _STATIC_VALUE_NOT_AVAILABLE
        keyword_value = resolve_value(keyword.value)
        if keyword_value is _STATIC_VALUE_NOT_AVAILABLE:
            return _STATIC_VALUE_NOT_AVAILABLE
        keyword_values[keyword.arg] = keyword_value
    try:
        return base_value.format(*argument_values, **keyword_values)
    except (IndexError, KeyError, TypeError, ValueError, AttributeError) as error:
        if isinstance(error, (IndexError, KeyError, TypeError, ValueError, AttributeError)):
            return _STATIC_VALUE_NOT_AVAILABLE
        raise AssertionError("unreachable format method evaluation branch")



def _try_evaluate_statically_empty_format_map_method_value(node: ast.Call, resolve_value) -> object:
    if (
        not isinstance(node.func, ast.Attribute)
        or node.func.attr != "format_map"
        or node.keywords
        or len(node.args) != 1
    ):
        return _STATIC_VALUE_NOT_AVAILABLE
    base_value = resolve_value(node.func.value)
    if base_value is _STATIC_VALUE_NOT_AVAILABLE or not isinstance(base_value, str) or len(base_value) != 0:
        return _STATIC_VALUE_NOT_AVAILABLE
    mapping_value = resolve_value(node.args[0])
    if mapping_value is _STATIC_VALUE_NOT_AVAILABLE or not isinstance(mapping_value, dict):
        return _STATIC_VALUE_NOT_AVAILABLE
    try:
        return base_value.format_map(mapping_value)
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        if isinstance(error, (KeyError, TypeError, ValueError, AttributeError)):
            return _STATIC_VALUE_NOT_AVAILABLE
        raise AssertionError("unreachable format_map method evaluation branch")



def _try_evaluate_statically_empty_padding_method_value(node: ast.Call, resolve_value) -> object:
    if not isinstance(node.func, ast.Attribute) or node.keywords:
        return _STATIC_VALUE_NOT_AVAILABLE
    owner_types = _POSITIONAL_EMPTY_PADDING_METHOD_OWNERS.get(node.func.attr)
    if owner_types is None:
        return _STATIC_VALUE_NOT_AVAILABLE
    if node.func.attr == "zfill":
        if len(node.args) != 1:
            return _STATIC_VALUE_NOT_AVAILABLE
    elif len(node.args) not in {1, 2}:
        return _STATIC_VALUE_NOT_AVAILABLE
    base_value = resolve_value(node.func.value)
    if (
        base_value is _STATIC_VALUE_NOT_AVAILABLE
        or not isinstance(base_value, owner_types)
        or len(base_value) != 0
    ):
        return _STATIC_VALUE_NOT_AVAILABLE
    argument_values: list[object] = []
    for argument_node in node.args:
        argument_value = resolve_value(argument_node)
        if argument_value is _STATIC_VALUE_NOT_AVAILABLE:
            return _STATIC_VALUE_NOT_AVAILABLE
        argument_values.append(argument_value)
    method = getattr(base_value, node.func.attr, None)
    if method is None:
        return _STATIC_VALUE_NOT_AVAILABLE
    try:
        result = method(*argument_values)
    except (TypeError, ValueError, AttributeError) as error:
        if isinstance(error, (TypeError, ValueError, AttributeError)):
            return _STATIC_VALUE_NOT_AVAILABLE
        raise AssertionError("unreachable padding method evaluation branch")
    if _runtime_value_is_silent_fallback(result):
        return result
    return _STATIC_VALUE_NOT_AVAILABLE



def _try_evaluate_statically_empty_fromhex_classmethod_value(node: ast.Call, resolve_value) -> object:
    if (
        not isinstance(node.func, ast.Attribute)
        or node.func.attr != "fromhex"
        or node.keywords
        or len(node.args) != 1
        or not isinstance(node.func.value, ast.Name)
        or node.func.value.id not in {"bytes", "bytearray"}
    ):
        return _STATIC_VALUE_NOT_AVAILABLE
    source_value = resolve_value(node.args[0])
    if source_value is _STATIC_VALUE_NOT_AVAILABLE or not isinstance(source_value, str):
        return _STATIC_VALUE_NOT_AVAILABLE
    if len(source_value) != 0:
        return _STATIC_VALUE_NOT_AVAILABLE
    if node.func.value.id == "bytes":
        return b""
    return bytearray()



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



def _try_evaluate_statically_empty_min_max_default_call_value(node: ast.Call, resolve_value) -> object:
    if not isinstance(node.func, ast.Name) or node.func.id not in {"min", "max"} or len(node.args) != 1:
        return _STATIC_VALUE_NOT_AVAILABLE
    if not node.keywords:
        return _STATIC_VALUE_NOT_AVAILABLE
    seen_keyword_names: set[str] = set()
    default_keyword: ast.keyword | None = None
    for keyword in node.keywords:
        if keyword.arg is None or keyword.arg not in {"default", "key"} or keyword.arg in seen_keyword_names:
            return _STATIC_VALUE_NOT_AVAILABLE
        seen_keyword_names.add(keyword.arg)
        if keyword.arg == "default":
            default_keyword = keyword
    if default_keyword is None:
        return _STATIC_VALUE_NOT_AVAILABLE
    iterable_value = resolve_value(node.args[0])
    if iterable_value is _STATIC_VALUE_NOT_AVAILABLE:
        return _STATIC_VALUE_NOT_AVAILABLE
    if not _runtime_value_is_statically_empty_iterable(iterable_value):
        return _STATIC_VALUE_NOT_AVAILABLE
    default_value = resolve_value(default_keyword.value)
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
    empty_any_value = _try_evaluate_statically_empty_any_call_value(
        node,
        _try_evaluate_static_expression_value,
    )
    if empty_any_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_any_value
    empty_all_value = _try_evaluate_statically_empty_all_call_value(
        node,
        _try_evaluate_static_expression_value,
    )
    if empty_all_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_all_value
    empty_len_value = _try_evaluate_statically_empty_len_call_value(
        node,
        _try_evaluate_static_expression_value,
    )
    if empty_len_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_len_value
    empty_sum_value = _try_evaluate_statically_empty_sum_call_value(
        node,
        _try_evaluate_static_expression_value,
    )
    if empty_sum_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_sum_value
    empty_count_value = _try_evaluate_statically_empty_count_method_value(
        node,
        _try_evaluate_static_expression_value,
    )
    if empty_count_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_count_value
    empty_removal_value = _try_evaluate_statically_empty_removal_method_value(
        node,
        _try_evaluate_static_expression_value,
    )
    if empty_removal_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_removal_value
    empty_strip_arg_value = _try_evaluate_statically_empty_strip_method_with_arg_value(
        node,
        _try_evaluate_static_expression_value,
    )
    if empty_strip_arg_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_strip_arg_value
    empty_replace_value = _try_evaluate_statically_empty_replace_method_value(
        node,
        _try_evaluate_static_expression_value,
    )
    if empty_replace_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_replace_value
    empty_translate_value = _try_evaluate_statically_empty_translate_method_value(
        node,
        _try_evaluate_static_expression_value,
    )
    if empty_translate_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_translate_value
    empty_codec_value = _try_evaluate_statically_empty_codec_method_value(
        node,
        _try_evaluate_static_expression_value,
    )
    if empty_codec_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_codec_value
    empty_format_value = _try_evaluate_statically_empty_format_method_value(
        node,
        _try_evaluate_static_expression_value,
    )
    if empty_format_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_format_value
    empty_format_map_value = _try_evaluate_statically_empty_format_map_method_value(
        node,
        _try_evaluate_static_expression_value,
    )
    if empty_format_map_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_format_map_value
    empty_padding_value = _try_evaluate_statically_empty_padding_method_value(
        node,
        _try_evaluate_static_expression_value,
    )
    if empty_padding_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_padding_value
    empty_fromhex_value = _try_evaluate_statically_empty_fromhex_classmethod_value(
        node,
        _try_evaluate_static_expression_value,
    )
    if empty_fromhex_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_fromhex_value
    empty_next_value = _try_evaluate_statically_empty_next_call_value(
        node,
        _try_evaluate_static_expression_value,
    )
    if empty_next_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_next_value
    empty_min_max_default_value = _try_evaluate_statically_empty_min_max_default_call_value(
        node,
        _try_evaluate_static_expression_value,
    )
    if empty_min_max_default_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_min_max_default_value
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
    empty_any_value = _try_evaluate_statically_empty_any_call_value(
        node,
        lambda expression: _try_resolve_known_name_silent_fallback_runtime_value(
            expression,
            known_name_values,
        ),
    )
    if empty_any_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_any_value
    empty_all_value = _try_evaluate_statically_empty_all_call_value(
        node,
        lambda expression: _try_resolve_known_name_silent_fallback_runtime_value(
            expression,
            known_name_values,
        ),
    )
    if empty_all_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_all_value
    empty_len_value = _try_evaluate_statically_empty_len_call_value(
        node,
        lambda expression: _try_resolve_known_name_silent_fallback_runtime_value(
            expression,
            known_name_values,
        ),
    )
    if empty_len_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_len_value
    empty_sum_value = _try_evaluate_statically_empty_sum_call_value(
        node,
        lambda expression: _try_resolve_known_name_silent_fallback_runtime_value(
            expression,
            known_name_values,
        ),
    )
    if empty_sum_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_sum_value
    empty_count_value = _try_evaluate_statically_empty_count_method_value(
        node,
        lambda expression: _try_resolve_known_name_silent_fallback_runtime_value(
            expression,
            known_name_values,
        ),
    )
    if empty_count_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_count_value
    empty_removal_value = _try_evaluate_statically_empty_removal_method_value(
        node,
        lambda expression: _try_resolve_known_name_silent_fallback_runtime_value(
            expression,
            known_name_values,
        ),
    )
    if empty_removal_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_removal_value
    empty_strip_arg_value = _try_evaluate_statically_empty_strip_method_with_arg_value(
        node,
        lambda expression: _try_resolve_known_name_silent_fallback_runtime_value(
            expression,
            known_name_values,
        ),
    )
    if empty_strip_arg_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_strip_arg_value
    empty_replace_value = _try_evaluate_statically_empty_replace_method_value(
        node,
        lambda expression: _try_resolve_known_name_silent_fallback_runtime_value(
            expression,
            known_name_values,
        ),
    )
    if empty_replace_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_replace_value
    empty_translate_value = _try_evaluate_statically_empty_translate_method_value(
        node,
        lambda expression: _try_resolve_known_name_silent_fallback_runtime_value(
            expression,
            known_name_values,
        ),
    )
    if empty_translate_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_translate_value
    empty_codec_value = _try_evaluate_statically_empty_codec_method_value(
        node,
        lambda expression: _try_resolve_known_name_silent_fallback_runtime_value(
            expression,
            known_name_values,
        ),
    )
    if empty_codec_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_codec_value
    empty_format_value = _try_evaluate_statically_empty_format_method_value(
        node,
        lambda expression: _try_resolve_known_name_silent_fallback_runtime_value(
            expression,
            known_name_values,
        ),
    )
    if empty_format_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_format_value
    empty_format_map_value = _try_evaluate_statically_empty_format_map_method_value(
        node,
        lambda expression: _try_resolve_known_name_silent_fallback_runtime_value(
            expression,
            known_name_values,
        ),
    )
    if empty_format_map_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_format_map_value
    empty_padding_value = _try_evaluate_statically_empty_padding_method_value(
        node,
        lambda expression: _try_resolve_known_name_silent_fallback_runtime_value(
            expression,
            known_name_values,
        ),
    )
    if empty_padding_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_padding_value
    empty_fromhex_value = _try_evaluate_statically_empty_fromhex_classmethod_value(
        node,
        lambda expression: _try_resolve_known_name_silent_fallback_runtime_value(
            expression,
            known_name_values,
        ),
    )
    if empty_fromhex_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_fromhex_value
    empty_next_value = _try_evaluate_statically_empty_next_call_value(
        node,
        lambda expression: _try_resolve_known_name_silent_fallback_runtime_value(
            expression,
            known_name_values,
        ),
    )
    if empty_next_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_next_value
    empty_min_max_default_value = _try_evaluate_statically_empty_min_max_default_call_value(
        node,
        lambda expression: _try_resolve_known_name_silent_fallback_runtime_value(
            expression,
            known_name_values,
        ),
    )
    if empty_min_max_default_value is not _STATIC_VALUE_NOT_AVAILABLE:
        return empty_min_max_default_value
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
