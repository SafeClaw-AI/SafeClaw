from __future__ import annotations

import ast
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.checks.check_reference_redlines import (  # noqa: E402
    _build_handler_exception_gate_profile,
    _collect_python_reference_redline_errors,
    _iter_exception_handler_gate_profiles,
    _iter_reference_redline_scan_texts,
    _parse_python_text_for_reference_check,
    _handler_caught_types,
    _handler_uses_broad_exception_family,
    _is_direct_silent_fallback_return_value,
    _is_silent_fallback_constructor_call,
    BARE_CONTEXT_REQUIRED_MESSAGE,
    BARE_SILENT_FALLBACK_MESSAGE,
    BROAD_CONTEXT_REQUIRED_MESSAGE,
    BROAD_EXCEPTION_TYPE_NAMES,
    BROAD_SILENT_FALLBACK_MESSAGE,
    CONTEXT_REQUIRED_EXCEPTION_TYPES,
    HIGH_RISK_EXCEPTION_TYPES,
    CONTEXT_REQUIRED_SUFFIX,
    MULTI_CONTEXT_REQUIRED_MESSAGE,
    SILENT_FALLBACK_SUFFIX,
    SILENT_FALLBACK_EXCEPTION_TYPES,
    SILENT_FALLBACK_EXCEPTION_TYPE_ORDER,
    TODO_METADATA_REQUIREMENTS,
    collect_empty_exception_errors_for_powershell_text,
    collect_empty_exception_errors_for_python_text,
    collect_errors,
    collect_silent_fallback_exception_errors_for_python_text,
    collect_todo_metadata_errors_for_text,
    collect_uncontextualized_exception_errors_for_python_text,
    collect_unused_bound_exception_context_errors_for_python_text,
)


class ReferenceRedlinesCheckTest(unittest.TestCase):
    def test_todo_metadata_requirements_are_stable(self) -> None:
        self.assertEqual(
            TODO_METADATA_REQUIREMENTS,
            ("owner", "due", "req"),
        )

    def test_broad_exception_truth_source_is_stable(self) -> None:
        self.assertEqual(BROAD_EXCEPTION_TYPE_NAMES, {"BaseException", "Exception"})

    def test_exception_message_truth_sources_are_stable(self) -> None:
        self.assertEqual(CONTEXT_REQUIRED_SUFFIX, "必须绑定 `as error` 以保留上下文")
        self.assertEqual(SILENT_FALLBACK_SUFFIX, "不能直接静默降级为 None/False/空字符串/空字节串/空容器")
        self.assertEqual(BARE_CONTEXT_REQUIRED_MESSAGE, "裸 except 不允许；必须显式捕获异常类型并绑定 `as error`")
        self.assertEqual(BROAD_CONTEXT_REQUIRED_MESSAGE, f"broad except {CONTEXT_REQUIRED_SUFFIX}")
        self.assertEqual(MULTI_CONTEXT_REQUIRED_MESSAGE, f"多异常 except {CONTEXT_REQUIRED_SUFFIX}")
        self.assertEqual(BARE_SILENT_FALLBACK_MESSAGE, f"裸 except {SILENT_FALLBACK_SUFFIX}")
        self.assertEqual(BROAD_SILENT_FALLBACK_MESSAGE, f"broad except {SILENT_FALLBACK_SUFFIX}")

    def test_broad_exception_family_helper_is_stable(self) -> None:
        broad_cases = [
            "try:\n    work()\nexcept Exception:\n    return None\n",
            "try:\n    work()\nexcept BaseException:\n    return None\n",
            "try:\n    work()\nexcept (Exception, ValueError):\n    return None\n",
            "try:\n    work()\nexcept (BaseException, KeyError):\n    return None\n",
        ]
        for source in broad_cases:
            handler = ast.parse(source).body[0].handlers[0]
            self.assertTrue(_handler_uses_broad_exception_family(handler))
        non_broad_handler = ast.parse(
            "try:\n    work()\nexcept (OSError, ValueError):\n    return None\n"
        ).body[0].handlers[0]
        self.assertFalse(_handler_uses_broad_exception_family(non_broad_handler))

    def test_handler_caught_types_helper_is_stable(self) -> None:
        timeout_handler = ast.parse(
            "try:\n    work()\nexcept subprocess.TimeoutExpired:\n    return None\n"
        ).body[0].handlers[0]
        tuple_handler = ast.parse(
            "try:\n    work()\nexcept (OSError, ValueError):\n    return None\n"
        ).body[0].handlers[0]
        broad_tuple_handler = ast.parse(
            "try:\n    work()\nexcept (Exception, ValueError):\n    return None\n"
        ).body[0].handlers[0]
        self.assertEqual(_handler_caught_types(timeout_handler), {"subprocess.TimeoutExpired"})
        self.assertEqual(_handler_caught_types(tuple_handler), {"OSError", "ValueError"})
        self.assertEqual(_handler_caught_types(broad_tuple_handler), {"Exception", "ValueError"})

    def test_silent_fallback_constructor_call_helper_is_stable(self) -> None:
        for source in ("return bool()", "return str()", "return bytes()", "return bytearray()", "return list()", "return dict()", "return tuple()", "return set()", "return frozenset()"):
            node = ast.parse(source).body[0].value
            self.assertTrue(_is_silent_fallback_constructor_call(node))

        self.assertFalse(_is_silent_fallback_constructor_call(ast.parse("return bytes([1])").body[0].value))
        self.assertFalse(_is_silent_fallback_constructor_call(ast.parse("return list([1])").body[0].value))
        self.assertFalse(_is_silent_fallback_constructor_call(ast.parse("return path.as_posix()").body[0].value))

    def test_direct_silent_fallback_return_value_helper_accepts_empty_aliases(self) -> None:
        for source in (
            "return f''",
            "return bool(False)",
            "return str('')",
            "return bytes([])",
            "return bytearray([])",
            "return list(())",
            "return dict([])",
            "return tuple([])",
            "return set(())",
            "return frozenset([])",
        ):
            self.assertTrue(_is_direct_silent_fallback_return_value(ast.parse(source).body[0].value))

        for source in (
            "return f'{name}'",
            "return bool('value')",
            "return str(b'')",
            "return bytes([1])",
            "return list([1])",
            "return dict([('key', 'value')])",
        ):
            self.assertFalse(_is_direct_silent_fallback_return_value(ast.parse(source).body[0].value))

    def test_direct_silent_fallback_return_value_helper_accepts_static_expression_aliases(self) -> None:
        for source in (
            "return '' if True else 'fallback'",
            "return [] or []",
            "return {} if False else {}",
            "return False and True",
            "return not True",
            "return 1 == 0",
            "return '' + ''",
            "return [] + []",
            "return {} | {}",
        ):
            self.assertTrue(_is_direct_silent_fallback_return_value(ast.parse(source).body[0].value))

        for source in (
            "return '' if flag else 'fallback'",
            "return values or []",
            "return {'key': 'value'} if True else {}",
            "return True and 'value'",
            "return not values",
            "return 1 == 1",
            "return prefix + ''",
            "return [1] + []",
            "return mapping | {}",
        ):
            self.assertFalse(_is_direct_silent_fallback_return_value(ast.parse(source).body[0].value))

    def test_handler_exception_gate_profile_is_stable(self) -> None:
        bare_handler = ast.parse(
            "try:\n    work()\nexcept:\n    return None\n"
        ).body[0].handlers[0]
        tuple_handler = ast.parse(
            "try:\n    work()\nexcept (OSError, ValueError):\n    return None\n"
        ).body[0].handlers[0]
        broad_tuple_handler = ast.parse(
            "try:\n    work()\nexcept (Exception, ValueError):\n    return None\n"
        ).body[0].handlers[0]
        high_risk_handler = ast.parse(
            "try:\n    work()\nexcept OSError:\n    return None\n"
        ).body[0].handlers[0]
        value_error_handler = ast.parse(
            "try:\n    work()\nexcept ValueError:\n    return None\n"
        ).body[0].handlers[0]


        bare_profile = _build_handler_exception_gate_profile(bare_handler)
        tuple_profile = _build_handler_exception_gate_profile(tuple_handler)
        broad_tuple_profile = _build_handler_exception_gate_profile(broad_tuple_handler)
        high_risk_profile = _build_handler_exception_gate_profile(high_risk_handler)
        value_error_profile = _build_handler_exception_gate_profile(value_error_handler)

        self.assertEqual(bare_profile.caught_types, {"<bare>"})
        self.assertEqual(bare_profile.ordered_high_risk_exception_names, ())
        self.assertEqual(bare_profile.context_requirement_message, BARE_CONTEXT_REQUIRED_MESSAGE)
        self.assertEqual(bare_profile.silent_fallback_requirement_message, BARE_SILENT_FALLBACK_MESSAGE)
        self.assertTrue(bare_profile.requires_bound_error)
        self.assertTrue(bare_profile.is_direct_silent_fallback)
        self.assertTrue(bare_profile.is_bare_handler)
        self.assertFalse(bare_profile.uses_high_risk_exception_family)
        self.assertFalse(bare_profile.uses_multi_exception_family)
        self.assertFalse(bare_profile.uses_broad_exception_family)

        self.assertEqual(tuple_profile.caught_types, {"OSError", "ValueError"})
        self.assertEqual(tuple_profile.ordered_high_risk_exception_names, ("OSError",))
        self.assertEqual(tuple_profile.context_requirement_message, MULTI_CONTEXT_REQUIRED_MESSAGE)
        self.assertEqual(tuple_profile.silent_fallback_requirement_message, f"OSError / ValueError {SILENT_FALLBACK_SUFFIX}")
        self.assertTrue(tuple_profile.requires_bound_error)
        self.assertTrue(tuple_profile.is_direct_silent_fallback)
        self.assertFalse(tuple_profile.is_bare_handler)
        self.assertTrue(tuple_profile.uses_high_risk_exception_family)
        self.assertTrue(tuple_profile.uses_multi_exception_family)
        self.assertFalse(tuple_profile.uses_broad_exception_family)

        self.assertEqual(broad_tuple_profile.caught_types, {"Exception", "ValueError"})
        self.assertEqual(broad_tuple_profile.ordered_high_risk_exception_names, ())
        self.assertEqual(broad_tuple_profile.context_requirement_message, BROAD_CONTEXT_REQUIRED_MESSAGE)
        self.assertEqual(broad_tuple_profile.silent_fallback_requirement_message, BROAD_SILENT_FALLBACK_MESSAGE)
        self.assertTrue(broad_tuple_profile.requires_bound_error)
        self.assertTrue(broad_tuple_profile.is_direct_silent_fallback)
        self.assertFalse(broad_tuple_profile.is_bare_handler)
        self.assertFalse(broad_tuple_profile.uses_high_risk_exception_family)
        self.assertTrue(broad_tuple_profile.uses_multi_exception_family)
        self.assertTrue(broad_tuple_profile.uses_broad_exception_family)

        self.assertEqual(high_risk_profile.caught_types, {"OSError"})
        self.assertEqual(high_risk_profile.ordered_high_risk_exception_names, ("OSError",))
        self.assertEqual(high_risk_profile.context_requirement_message, f"OSError {CONTEXT_REQUIRED_SUFFIX}")
        self.assertEqual(high_risk_profile.silent_fallback_requirement_message, f"OSError {SILENT_FALLBACK_SUFFIX}")
        self.assertTrue(high_risk_profile.requires_bound_error)
        self.assertTrue(high_risk_profile.is_direct_silent_fallback)
        self.assertFalse(high_risk_profile.is_bare_handler)
        self.assertTrue(high_risk_profile.uses_high_risk_exception_family)
        self.assertFalse(high_risk_profile.uses_multi_exception_family)
        self.assertFalse(high_risk_profile.uses_broad_exception_family)

        self.assertEqual(value_error_profile.caught_types, {"ValueError"})
        self.assertEqual(value_error_profile.ordered_high_risk_exception_names, ())
        self.assertEqual(value_error_profile.silent_fallback_requirement_message, f"ValueError {SILENT_FALLBACK_SUFFIX}")
        self.assertFalse(value_error_profile.requires_bound_error)
        self.assertTrue(value_error_profile.is_direct_silent_fallback)
        self.assertFalse(value_error_profile.is_bare_handler)
        self.assertFalse(value_error_profile.uses_high_risk_exception_family)
        self.assertFalse(value_error_profile.uses_multi_exception_family)
        self.assertFalse(value_error_profile.uses_broad_exception_family)

    def test_iter_exception_handler_gate_profiles_is_stable(self) -> None:
        tree = ast.parse(
            "try:\n    work()\nexcept OSError:\n    return None\nexcept Exception:\n    return None\n"
        )

        profiles = list(_iter_exception_handler_gate_profiles(tree))

        self.assertEqual(len(profiles), 2)
        first_handler, first_profile = profiles[0]
        second_handler, second_profile = profiles[1]

        self.assertEqual(first_handler.lineno, 3)
        self.assertEqual(first_profile.caught_types, {"OSError"})
        self.assertEqual(first_profile.context_requirement_message, f"OSError {CONTEXT_REQUIRED_SUFFIX}")
        self.assertTrue(first_profile.requires_bound_error)
        self.assertTrue(first_profile.is_direct_silent_fallback)

        self.assertEqual(second_handler.lineno, 5)
        self.assertEqual(second_profile.caught_types, {"Exception"})
        self.assertEqual(second_profile.context_requirement_message, BROAD_CONTEXT_REQUIRED_MESSAGE)
        self.assertTrue(second_profile.requires_bound_error)
        self.assertTrue(second_profile.is_direct_silent_fallback)

    def test_parse_python_text_for_reference_check_is_stable(self) -> None:
        valid = _parse_python_text_for_reference_check(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    return None\n",
        )
        invalid = _parse_python_text_for_reference_check(
            Path("sample.py"),
            "def broken(:\n    pass\n",
        )

        self.assertEqual(valid.relpath, "sample.py")
        self.assertIsInstance(valid.tree, ast.Module)
        self.assertIsNone(valid.syntax_error_message)

        self.assertEqual(invalid.relpath, "sample.py")
        self.assertIsNone(invalid.tree)
        self.assertEqual(invalid.syntax_error_message, "无法解析 Python 文件: sample.py:1 -> invalid syntax")

    def test_iter_reference_redline_scan_texts_is_stable(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as temp_dir:
            temp_root = Path(temp_dir)
            python_file = temp_root / "sample.py"
            powershell_file = temp_root / "sample.ps1"
            cmd_file = temp_root / "sample.cmd"
            python_file.write_text("print('ok')\n", encoding="utf-8")
            powershell_file.write_text("Write-Host 'ok'\n", encoding="utf-8")
            cmd_file.write_text("echo ok\n", encoding="utf-8")

            with patch(
                "tools.checks.check_reference_redlines.iter_reference_redline_files",
                return_value=[python_file, powershell_file, cmd_file],
            ):
                scan_texts = _iter_reference_redline_scan_texts({".py", ".ps1"})

            self.assertEqual(
                [(item.relpath.as_posix(), item.suffix, item.text) for item in scan_texts],
                [
                    (python_file.relative_to(REPO_ROOT).as_posix(), ".py", "print('ok')\n"),
                    (powershell_file.relative_to(REPO_ROOT).as_posix(), ".ps1", "Write-Host 'ok'\n"),
                ],
            )

    def test_collect_python_reference_redline_errors_is_stable(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as temp_dir:
            temp_root = Path(temp_dir)
            python_file = temp_root / "sample.py"
            powershell_file = temp_root / "sample.ps1"
            python_file.write_text("print('ok')\n", encoding="utf-8")
            powershell_file.write_text("Write-Host 'ok'\n", encoding="utf-8")

            seen: list[tuple[str, str]] = []

            def collector(path: Path, text: str) -> list[str]:
                seen.append((path.as_posix(), text))
                return [f"hit:{path.as_posix()}"]

            with patch("tools.checks.check_reference_redlines.iter_reference_redline_files", return_value=[python_file, powershell_file]):
                errors = _collect_python_reference_redline_errors(collector)

            expected_relpath = python_file.relative_to(REPO_ROOT).as_posix()
            self.assertEqual(errors, [f"hit:{expected_relpath}"])
            self.assertEqual(seen, [(expected_relpath, "print('ok')\n")])

    def test_high_risk_exception_truth_sources_are_aligned(self) -> None:
        context_required_expected = (
            "FileExistsError",
            "KeyError",
            "OSError",
            "RuntimeError",
            "SyntaxError",
            "SystemError",
            "json.JSONDecodeError",
            "subprocess.TimeoutExpired",
        )
        silent_fallback_expected = context_required_expected + ("ValueError", "TypeError")
        self.assertEqual(SILENT_FALLBACK_EXCEPTION_TYPE_ORDER, silent_fallback_expected)
        self.assertEqual(HIGH_RISK_EXCEPTION_TYPES, set(context_required_expected))
        self.assertIs(CONTEXT_REQUIRED_EXCEPTION_TYPES, HIGH_RISK_EXCEPTION_TYPES)
        self.assertEqual(CONTEXT_REQUIRED_EXCEPTION_TYPES, set(context_required_expected))
        self.assertEqual(SILENT_FALLBACK_EXCEPTION_TYPES, set(silent_fallback_expected))
        self.assertNotEqual(SILENT_FALLBACK_EXCEPTION_TYPES, HIGH_RISK_EXCEPTION_TYPES)

    def test_orphan_todo_is_blocked(self) -> None:
        errors = collect_todo_metadata_errors_for_text(
            Path("sample.py"),
            "# TODO: fix later\n",
        )
        self.assertEqual(
            errors,
            [
                "TODO 缺少责任元数据: sample.py:1 -> 需要同时包含 owner / due / req",
            ],
        )

    def test_owned_todo_passes(self) -> None:
        self.assertEqual(
            collect_todo_metadata_errors_for_text(
                Path("sample.py"),
                "# TODO(owner=alice, due=2026-03-31, req=SC-123): fix later\n",
            ),
            [],
        )

    def test_python_pass_only_except_is_blocked(self) -> None:
        errors = collect_empty_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    pass\n",
        )
        self.assertEqual(
            errors,
            ["空异常处理违规: sample.py:3 -> except 块不能只写 pass/省略号"],
        )

    def test_powershell_empty_catch_is_blocked(self) -> None:
        errors = collect_empty_exception_errors_for_powershell_text(
            Path("sample.ps1"),
            "try { Invoke-Thing } catch {\n    # ignore\n}\n",
        )
        self.assertEqual(
            errors,
            ["空异常处理违规: sample.ps1:1 -> catch 块不能为空或只含注释"],
        )

    def test_uncontextualized_multi_exception_is_blocked(self) -> None:
        errors = collect_uncontextualized_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept (OSError, ValueError):\n    return None\n",
        )
        self.assertEqual(
            errors,
            ["异常处理缺少上下文: sample.py:3 -> 多异常 except 必须绑定 `as error` 以保留上下文"],
        )

    def test_contextualized_multi_exception_passes(self) -> None:
        self.assertEqual(
            collect_uncontextualized_exception_errors_for_python_text(
                Path("sample.py"),
                "try:\n    work()\nexcept (OSError, ValueError) as error:\n    raise RuntimeError(f'load failed: {error}')\n",
            ),
            [],
        )

    def test_bare_except_is_blocked(self) -> None:
        errors = collect_uncontextualized_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept:\n    return None\n",
        )
        self.assertEqual(
            errors,
            ["异常处理缺少上下文: sample.py:3 -> 裸 except 不允许；必须显式捕获异常类型并绑定 `as error`"],
        )

    def test_exception_without_bound_context_is_blocked(self) -> None:
        errors = collect_uncontextualized_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept Exception:\n    return None\n",
        )
        self.assertEqual(
            errors,
            ["异常处理缺少上下文: sample.py:3 -> broad except 必须绑定 `as error` 以保留上下文"],
        )

    def test_exception_with_contextual_usage_passes(self) -> None:
        self.assertEqual(
            collect_unused_bound_exception_context_errors_for_python_text(
                Path("sample.py"),
                "try:\n    work()\nexcept Exception as error:\n    raise RuntimeError(f'wrapped exception: {error}')\n",
            ),
            [],
        )

    def test_base_exception_without_bound_context_is_blocked(self) -> None:
        errors = collect_uncontextualized_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept BaseException:\n    return None\n",
        )
        self.assertEqual(
            errors,
            ["异常处理缺少上下文: sample.py:3 -> broad except 必须绑定 `as error` 以保留上下文"],
        )

    def test_base_exception_with_contextual_usage_passes(self) -> None:
        self.assertEqual(
            collect_unused_bound_exception_context_errors_for_python_text(
                Path("sample.py"),
                "try:\n    work()\nexcept BaseException as error:\n    raise RuntimeError(f'wrapped base exception: {error}')\n",
            ),
            [],
        )

    def test_tuple_with_exception_without_bound_context_is_blocked(self) -> None:
        errors = collect_uncontextualized_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept (Exception, ValueError):\n    return None\n",
        )
        self.assertEqual(
            errors,
            ["异常处理缺少上下文: sample.py:3 -> broad except 必须绑定 `as error` 以保留上下文"],
        )

    def test_tuple_with_base_exception_without_bound_context_is_blocked(self) -> None:
        errors = collect_uncontextualized_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept (BaseException, KeyError):\n    return None\n",
        )
        self.assertEqual(
            errors,
            ["异常处理缺少上下文: sample.py:3 -> broad except 必须绑定 `as error` 以保留上下文"],
        )

    def test_json_decode_error_without_bound_context_is_blocked(self) -> None:
        errors = collect_uncontextualized_exception_errors_for_python_text(
            Path("sample.py"),
            "import json\ntry:\n    json.loads('{')\nexcept json.JSONDecodeError:\n    return None\n",
        )
        self.assertEqual(
            errors,
            ["异常处理缺少上下文: sample.py:4 -> json.JSONDecodeError 必须绑定 `as error` 以保留上下文"],
        )

    def test_json_decode_error_with_contextual_usage_passes(self) -> None:
        self.assertEqual(
            collect_unused_bound_exception_context_errors_for_python_text(
                Path("sample.py"),
                "import json\ntry:\n    json.loads('{')\nexcept json.JSONDecodeError as error:\n    raise RuntimeError(f'invalid json: {error}')\n",
            ),
            [],
        )

    def test_os_error_without_bound_context_is_blocked(self) -> None:
        errors = collect_uncontextualized_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    raise RuntimeError('io failed')\n",
        )
        self.assertEqual(
            errors,
            ["异常处理缺少上下文: sample.py:3 -> OSError 必须绑定 `as error` 以保留上下文"],
        )

    def test_os_error_with_contextual_usage_passes(self) -> None:
        self.assertEqual(
            collect_unused_bound_exception_context_errors_for_python_text(
                Path("sample.py"),
                "try:\n    work()\nexcept OSError as error:\n    raise RuntimeError(f'io failed: {error}')\n",
            ),
            [],
        )

    def test_file_exists_error_without_bound_context_is_blocked(self) -> None:
        errors = collect_uncontextualized_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept FileExistsError:\n    raise RuntimeError('busy')\n",
        )
        self.assertEqual(
            errors,
            ["异常处理缺少上下文: sample.py:3 -> FileExistsError 必须绑定 `as error` 以保留上下文"],
        )

    def test_file_exists_error_with_contextual_usage_passes(self) -> None:
        self.assertEqual(
            collect_unused_bound_exception_context_errors_for_python_text(
                Path("sample.py"),
                "try:\n    work()\nexcept FileExistsError as error:\n    raise RuntimeError(f'busy: {error}')\n",
            ),
            [],
        )

    def test_key_error_without_bound_context_is_blocked(self) -> None:
        errors = collect_uncontextualized_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    mapping['missing']\nexcept KeyError:\n    raise RuntimeError('missing key')\n",
        )
        self.assertEqual(
            errors,
            ["异常处理缺少上下文: sample.py:3 -> KeyError 必须绑定 `as error` 以保留上下文"],
        )

    def test_key_error_with_contextual_usage_passes(self) -> None:
        self.assertEqual(
            collect_unused_bound_exception_context_errors_for_python_text(
                Path("sample.py"),
                "try:\n    mapping['missing']\nexcept KeyError as error:\n    raise RuntimeError(f'missing key: {error}')\n",
            ),
            [],
        )

    def test_runtime_error_without_bound_context_is_blocked(self) -> None:
        errors = collect_uncontextualized_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept RuntimeError:\n    return None\n",
        )
        self.assertEqual(
            errors,
            ["异常处理缺少上下文: sample.py:3 -> RuntimeError 必须绑定 `as error` 以保留上下文"],
        )

    def test_runtime_error_with_contextual_usage_passes(self) -> None:
        self.assertEqual(
            collect_unused_bound_exception_context_errors_for_python_text(
                Path("sample.py"),
                "try:\n    work()\nexcept RuntimeError as error:\n    raise RuntimeError(f'wrapped runtime error: {error}')\n",
            ),
            [],
        )

    def test_system_error_without_bound_context_is_blocked(self) -> None:
        errors = collect_uncontextualized_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept SystemError:\n    return False\n",
        )
        self.assertEqual(
            errors,
            ["异常处理缺少上下文: sample.py:3 -> SystemError 必须绑定 `as error` 以保留上下文"],
        )

    def test_system_error_with_contextual_usage_passes(self) -> None:
        self.assertEqual(
            collect_unused_bound_exception_context_errors_for_python_text(
                Path("sample.py"),
                "try:\n    work()\nexcept SystemError as error:\n    raise RuntimeError(f'signal probe failed: {error}')\n",
            ),
            [],
        )

    def test_timeout_expired_without_bound_context_is_blocked(self) -> None:
        errors = collect_uncontextualized_exception_errors_for_python_text(
            Path("sample.py"),
            "import subprocess\ntry:\n    work()\nexcept subprocess.TimeoutExpired:\n    return False\n",
        )
        self.assertEqual(
            errors,
            ["异常处理缺少上下文: sample.py:4 -> subprocess.TimeoutExpired 必须绑定 `as error` 以保留上下文"],
        )

    def test_timeout_expired_with_contextual_usage_passes(self) -> None:
        self.assertEqual(
            collect_unused_bound_exception_context_errors_for_python_text(
                Path("sample.py"),
                "import subprocess\ntry:\n    work()\nexcept subprocess.TimeoutExpired as error:\n    raise RuntimeError(f'timeout: {error}')\n",
            ),
            [],
        )
    def test_syntax_error_without_bound_context_is_blocked(self) -> None:
        errors = collect_uncontextualized_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    compile('(', '<inline>', 'eval')\nexcept SyntaxError:\n    return None\n",
        )
        self.assertEqual(
            errors,
            ["异常处理缺少上下文: sample.py:3 -> SyntaxError 必须绑定 `as error` 以保留上下文"],
        )

    def test_syntax_error_with_contextual_usage_passes(self) -> None:
        self.assertEqual(
            collect_unused_bound_exception_context_errors_for_python_text(
                Path("sample.py"),
                "try:\n    compile('(', '<inline>', 'eval')\nexcept SyntaxError as error:\n    raise RuntimeError(f'syntax failed: {error}')\n",
            ),
            [],
        )

    def test_bound_exception_context_must_be_meaningfully_used(self) -> None:
        errors = collect_unused_bound_exception_context_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept (OSError, ValueError) as error:\n    _ = error\n    return None\n",
        )
        self.assertEqual(
            errors,
            ["异常上下文未真正使用: sample.py:3 -> 绑定了 `as error` 后，异常上下文不能只做占位赋值"],
        )

    def test_meaningfully_used_exception_context_passes(self) -> None:
        self.assertEqual(
            collect_unused_bound_exception_context_errors_for_python_text(
                Path("sample.py"),
                "try:\n    work()\nexcept (OSError, ValueError) as error:\n    return False, str(error)\n",
            ),
            [],
        )

    def test_risky_exception_cannot_directly_silently_fallback(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    return False\n",
        )
        self.assertEqual(
            errors,
            [
                "异常降级缺少上下文: sample.py:3 -> OSError 不能直接静默降级为 None/False/空字符串/空字节串/空容器",
            ],
        )

    def test_risky_exception_contextual_fallback_passes(self) -> None:
        self.assertEqual(
            collect_silent_fallback_exception_errors_for_python_text(
                Path("sample.py"),
                "try:\n    work()\nexcept OSError as error:\n    return error.errno == 1\n",
            ),
            [],
        )

    def test_bare_except_cannot_directly_silently_fallback(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept:\n    return False\n",
        )
        self.assertEqual(
            errors,
            [
                "异常降级缺少上下文: sample.py:3 -> 裸 except 不能直接静默降级为 None/False/空字符串/空字节串/空容器",
            ],
        )

    def test_exception_cannot_directly_silently_fallback(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept Exception:\n    return None\n",
        )
        self.assertEqual(
            errors,
            [
                "异常降级缺少上下文: sample.py:3 -> broad except 不能直接静默降级为 None/False/空字符串/空字节串/空容器",
            ],
        )

    def test_base_exception_cannot_directly_silently_fallback(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept BaseException:\n    return False\n",
        )
        self.assertEqual(
            errors,
            [
                "异常降级缺少上下文: sample.py:3 -> broad except 不能直接静默降级为 None/False/空字符串/空字节串/空容器",
            ],
        )

    def test_tuple_with_exception_cannot_directly_silently_fallback(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept (Exception, ValueError):\n    return None\n",
        )
        self.assertEqual(
            errors,
            [
                "异常降级缺少上下文: sample.py:3 -> broad except 不能直接静默降级为 None/False/空字符串/空字节串/空容器",
            ],
        )

    def test_tuple_with_base_exception_cannot_directly_silently_fallback(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept (BaseException, KeyError):\n    return False\n",
        )
        self.assertEqual(
            errors,
            [
                "异常降级缺少上下文: sample.py:3 -> broad except 不能直接静默降级为 None/False/空字符串/空字节串/空容器",
            ],
        )

    def test_system_error_cannot_directly_silently_fallback(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept SystemError:\n    return False\n",
        )
        self.assertEqual(
            errors,
            [
                "异常降级缺少上下文: sample.py:3 -> SystemError 不能直接静默降级为 None/False/空字符串/空字节串/空容器",
            ],
        )

    def test_timeout_expired_cannot_directly_silently_fallback(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "import subprocess\ntry:\n    work()\nexcept subprocess.TimeoutExpired:\n    return False\n",
        )
        self.assertEqual(
            errors,
            [
                "异常降级缺少上下文: sample.py:4 -> subprocess.TimeoutExpired 不能直接静默降级为 None/False/空字符串/空字节串/空容器",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_to_empty_string(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return ''\n",
        )
        self.assertEqual(
            errors,
            [
                "异常降级缺少上下文: sample.py:3 -> ValueError 不能直接静默降级为 None/False/空字符串/空字节串/空容器",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_to_empty_list(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    return []\n",
        )
        self.assertEqual(
            errors,
            [
                "异常降级缺少上下文: sample.py:3 -> TypeError 不能直接静默降级为 None/False/空字符串/空字节串/空容器",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_to_empty_set_call(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return set()\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_to_empty_frozenset_call(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    return frozenset()\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )


    def test_value_error_cannot_directly_silently_fallback_to_empty_str_call(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return str()\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_to_empty_list_call(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    return list()\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_to_empty_dict_call(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return dict()\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_to_empty_tuple_call(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    return tuple()\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_directly_silently_fallback_with_implicit_none_return(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    return\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_implicit_none_return(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_to_false_bool_call(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return bool()\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_assign_none_then_return_same_name(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    fallback = None\n    return fallback\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_assign_empty_list_call_then_return_same_name(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    fallback = list()\n    return fallback\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_annotate_none_then_return_same_name(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    fallback: object = None\n    return fallback\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_annotate_empty_list_then_return_same_name(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    fallback: list[str] = []\n    return fallback\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_to_empty_bytes_literal(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return b''\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_to_empty_bytes_call(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    return bytes()\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_to_empty_bytearray_call(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return bytearray()\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )


    def test_value_error_cannot_directly_silently_fallback_to_empty_f_string(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return f''\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_assign_empty_f_string_then_return_same_name(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    fallback = f''\n    return fallback\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_to_single_arg_empty_dict_call(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return dict([])\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_to_single_arg_empty_bytes_call(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    return bytes([])\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_assign_single_arg_false_bool_then_return_same_name(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    fallback = bool(False)\n    return fallback\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )


    def test_value_error_cannot_directly_silently_fallback_with_static_if_expression(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return '' if True else 'fallback'\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_static_boolop(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    return [] or []\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_assign_static_if_expression_then_return_same_name(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    fallback = {} if False else {}\n    return fallback\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )


    def test_value_error_cannot_directly_silently_fallback_with_static_compare(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return 1 == 0\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_static_unary_not(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    return not True\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_assign_static_compare_then_return_same_name(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    fallback = 1 == 0\n    return fallback\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )


    def test_value_error_cannot_directly_silently_fallback_with_static_binop_add(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return '' + ''\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_static_binop_bitor(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    return {} | {}\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_assign_static_binop_add_then_return_same_name(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    fallback = [] + []\n    return fallback\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )


    def test_value_error_cannot_assign_empty_list_alias_chain_then_return_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    fallback = []\n    alias = fallback\n    return alias\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_assign_false_bool_alias_chain_then_return_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    fallback = bool(False)\n    alias: object = fallback\n    return alias\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_assign_empty_string_binop_alias_chain_then_return_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    empty = '' + ''\n    fallback = empty\n    return fallback\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )


    def test_value_error_cannot_multi_assign_empty_list_then_return_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    fallback = alias = []\n    return alias\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_multi_assign_false_bool_then_return_primary(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    primary = alias = bool(False)\n    return primary\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_multi_assign_binop_then_alias_chain_return_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    empty = fallback = '' + ''\n    alias = empty\n    return alias\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_return_list_wrapped_known_empty_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    fallback = []\n    return list(fallback)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_return_bool_wrapped_known_false_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    fallback = bool(False)\n    return bool(fallback)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_str_wrapped_known_empty_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    empty = '' + ''\n    alias = empty\n    return str(alias)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_return_nested_list_wrapped_known_empty_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    fallback = []\n    return list(list(fallback))\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_return_nested_bool_wrapped_known_false_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    fallback = bool(False)\n    return bool(bool(fallback))\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_nested_str_wrapped_known_empty_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    empty = '' + ''\n    alias = empty\n    return str(str(alias))\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_return_list_wrapped_ifexp_known_empty_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    fallback = []\n    return list(fallback if True else [1])\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_return_bool_wrapped_ifexp_known_false_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    fallback = bool(False)\n    return bool(True if False else fallback)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_str_wrapped_ifexp_known_empty_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    empty = '' + ''\n    alias = empty\n    return str(alias if True else 'fallback')\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_return_list_wrapped_boolop_known_empty_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    fallback = []\n    return list(fallback or [])\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_return_bool_wrapped_boolop_known_false_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    fallback = bool(False)\n    return bool(True and fallback)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_str_wrapped_boolop_known_empty_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    empty = '' + ''\n    alias = empty\n    return str(alias or '')\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_return_bool_wrapped_compare_known_empty_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    fallback = []\n    return bool(fallback == [1])\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_return_bool_wrapped_unary_known_false_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    fallback = bool(False)\n    return bool(not not fallback)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_bool_wrapped_compare_known_empty_string_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    empty = '' + ''\n    alias = empty\n    return bool(alias != '')\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_return_list_wrapped_binop_known_empty_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    fallback = []\n    return list(fallback + [])\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_return_bool_wrapped_binop_known_false_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    fallback = bool(False)\n    return bool(fallback | False)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_str_wrapped_binop_known_empty_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    empty = '' + ''\n    alias = empty\n    return str(alias + '')\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_keyword_str_constructor(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return str(object='')\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_keyword_bytes_constructor(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    return bytes(source=b'')\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_keyword_str_constructor_wrapped_known_empty_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    empty = '' + ''\n    alias = empty\n    return str(object=alias)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_static_list_slice(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return [][:]\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_return_slice_known_empty_string_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    empty = '' + ''\n    return empty[:]\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_slice_known_empty_bytes_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    payload = b''\n    return payload[:]\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_static_starred_list_unpack(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return [*[]]\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_return_starred_list_unpack_known_empty_string_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    empty = '' + ''\n    return [*empty]\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_directly_silently_fallback_with_static_dict_unpack(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    return {**{}}\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_runtime_error_cannot_return_dict_unpack_known_empty_mapping_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept RuntimeError:\n    mapping = {}\n    return {**mapping}\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> RuntimeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_named_expression_list(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return (fallback := [])\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_named_expression_false(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    return (fallback := False)\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_constructor_wrapped_named_expression_known_empty_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    empty = '' + ''\n    return str((alias := empty))\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_fstring_empty_constant(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return f\"{''}\"\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_fstring_known_empty_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    empty = '' + ''\n    return f\"{empty}\"\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_constructor_wrapped_fstring_known_empty_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    empty = '' + ''\n    return str(f\"{empty}\")\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_copy_method_on_list_literal(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return [].copy()\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_copy_method_on_known_empty_mapping(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    mapping = {}\n    return mapping.copy()\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_constructor_wrapped_copy_method_on_known_empty_list(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    values = []\n    return list(values.copy())\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_strip_method_on_empty_string(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return ''.strip()\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_lower_method_on_known_empty_string(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    empty = '' + ''\n    return empty.lower()\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_constructor_wrapped_rstrip_method_on_known_empty_bytes(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    payload = b''\n    return bytes(payload.rstrip())\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_split_method_on_empty_string(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return ''.split()\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_splitlines_method_on_known_empty_string(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    empty = '' + ''\n    return empty.splitlines()\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_constructor_wrapped_splitlines_method_on_known_empty_bytes(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    payload = b''\n    return tuple(payload.splitlines())\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )


    def test_value_error_cannot_directly_silently_fallback_with_isalnum_method_on_empty_string(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return ''.isalnum()\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_isdigit_method_on_known_empty_bytes(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = b''\n    return payload.isdigit()\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_constructor_wrapped_isidentifier_method_on_known_empty_string(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    name = '' + ''\n    return bool(name.isidentifier())\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )


    def test_value_error_cannot_directly_silently_fallback_with_capitalize_method_on_empty_string(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return ''.capitalize()\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_expandtabs_method_on_known_empty_bytes(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = b''\n    return payload.expandtabs()\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_constructor_wrapped_title_method_on_known_empty_bytearray(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    payload = bytearray()\n    return bytearray(payload.title())\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )


    def test_value_error_cannot_directly_silently_fallback_with_encode_method_on_empty_string(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return ''.encode()\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_decode_method_on_known_empty_bytes(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = b''\n    return payload.decode()\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_constructor_wrapped_encode_method_on_known_empty_string(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    name = '' + ''\n    return bytearray(name.encode())\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )


    def test_value_error_cannot_directly_silently_fallback_with_rsplit_method_on_empty_string(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return ''.rsplit()\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_rsplit_method_on_known_empty_bytes(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = b''\n    return payload.rsplit()\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_constructor_wrapped_rsplit_method_on_known_empty_bytearray(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    payload = bytearray()\n    return tuple(payload.rsplit())\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_clear_method_on_empty_list(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return [].clear()\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_reverse_method_on_known_empty_bytearray(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = bytearray()\n    return payload.reverse()\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_bool_wrapped_sort_method_on_known_empty_list(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    values = []\n    return bool(values.sort())\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_difference_method_on_empty_set(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return set().difference()\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_union_method_on_known_empty_set(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = set()\n    return payload.union()\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_constructor_wrapped_intersection_method_on_known_empty_frozenset(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    payload = frozenset()\n    return set(payload.intersection())\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_update_method_on_empty_dict(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return {}.update()\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_difference_update_method_on_known_empty_set(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = set()\n    return payload.difference_update()\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_bool_wrapped_intersection_update_method_on_known_empty_set(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    payload = set()\n    return bool(payload.intersection_update())\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_format_method_on_empty_string(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return ''.format()\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_hex_method_on_known_empty_bytes(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = b''\n    return payload.hex()\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_constructor_wrapped_hex_method_on_known_empty_bytearray(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    payload = bytearray()\n    return str(payload.hex())\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_empty_list_comprehension(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return [item for item in []]\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_empty_set_comprehension_from_known_empty_set(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = set()\n    return {item for item in payload}\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_constructor_wrapped_empty_dict_comprehension_from_known_empty_pairs(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    pairs = []\n    return dict({key: value for key, value in pairs})\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_empty_generator_expression_consumed_by_list(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return list(item for item in ())\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_empty_generator_expression_consumed_by_tuple_from_known_empty_set(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = set()\n    return tuple(item for item in payload)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_dict_wrapped_empty_generator_expression_from_known_empty_pairs(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    pairs = []\n    return dict((key, value) for key, value in pairs)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_empty_generator_expression_consumed_by_bytes(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return bytes(item for item in ())\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_empty_generator_expression_consumed_by_bytearray_from_known_empty_list(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = []\n    return bytearray(item for item in payload)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_keyword_bytes_wrapped_empty_generator_expression_from_known_empty_list(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    payload = []\n    return bytes(source=(item for item in payload))\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_empty_zip_consumed_by_list(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return list(zip())\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_empty_zip_from_known_empty_list_consumed_by_tuple(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = []\n    return tuple(zip(payload, [1]))\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_dict_wrapped_empty_zip_from_known_empty_pairs(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    keys = []\n    values = []\n    return dict(zip(keys, values))\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_empty_iter_consumed_by_list(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return list(iter(()))\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_empty_iter_from_known_empty_list_consumed_by_tuple(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = []\n    return tuple(iter(payload))\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_bytes_wrapped_empty_iter_from_known_empty_list(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    payload = []\n    return bytes(iter(payload))\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_return_list_wrapped_empty_iter_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    payload = []\n    items = iter(payload)\n    return list(items)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_return_tuple_wrapped_empty_zip_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = []\n    items = zip(payload, [1])\n    return tuple(items)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_set_wrapped_empty_generator_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    payload = []\n    items = (item for item in payload)\n    return set(items)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_empty_reversed_consumed_by_list(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return list(reversed(()))\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_empty_reversed_from_known_empty_list_consumed_by_tuple(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = []\n    return tuple(reversed(payload))\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_bytes_wrapped_empty_reversed_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    payload = b''\n    items = reversed(payload)\n    return bytes(items)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_empty_enumerate_consumed_by_list(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return list(enumerate(()))\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_empty_enumerate_from_known_empty_list_consumed_by_tuple(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = []\n    return tuple(enumerate(payload))\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_dict_wrapped_empty_enumerate_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    payload = []\n    items = enumerate(payload)\n    return dict(items)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_empty_map_consumed_by_list(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return list(map(str, ()))\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_empty_map_from_known_empty_list_consumed_by_tuple(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = []\n    return tuple(map(str, payload))\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_set_wrapped_empty_map_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    payload = []\n    items = map(str, payload)\n    return set(items)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_empty_sorted_on_empty_tuple(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return sorted(())\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_sorted_on_known_empty_list(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = []\n    return sorted(payload)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_tuple_wrapped_empty_sorted_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    payload = []\n    items = sorted(payload)\n    return tuple(items)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_empty_str_join(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return ''.join(())\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_empty_bytes_join_from_known_empty_list(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    separator = b''\n    payload = []\n    return separator.join(payload)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_bytes_wrapped_empty_bytearray_join_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    separator = bytearray()\n    payload = []\n    joined = separator.join(payload)\n    return bytes(joined)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_empty_dict_fromkeys(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return dict.fromkeys(())\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_dict_fromkeys_on_known_empty_list(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = []\n    return dict.fromkeys(payload)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_dict_wrapped_empty_dict_fromkeys_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    payload = []\n    mapping = dict.fromkeys(payload)\n    return dict(mapping)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_empty_range_stop_zero(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return range(0)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_empty_range_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    items = range(0)\n    return items\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_list_wrapped_empty_range_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    items = range(0)\n    return list(items)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_empty_dict_keys_view(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return list({}.keys())\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_empty_dict_values_view_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = {}\n    return tuple(payload.values())\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_dict_wrapped_empty_dict_items_view_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    payload = {}\n    items = payload.items()\n    return dict(items)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_empty_filter_consumed_by_list(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return list(filter(None, ()))\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_empty_filter_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = []\n    return tuple(filter(None, payload))\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_set_wrapped_empty_filter_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    payload = []\n    items = filter(None, payload)\n    return set(items)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_next_default_none_on_empty_iterator(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return next(iter(()), None)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_next_default_false_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = []\n    return next(iter(payload), False)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_list_wrapped_next_default_empty_list_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    payload = []\n    fallback = []\n    item = next(iter(payload), fallback)\n    return list(item)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_empty_dict_get_without_default(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return {}.get('missing')\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_empty_dict_get_false_default(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = {}\n    return payload.get('missing', False)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_list_wrapped_empty_dict_get_list_default_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    payload = {}\n    fallback = []\n    item = payload.get('missing', fallback)\n    return list(item)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_empty_dict_pop_none_default(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return {}.pop('missing', None)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_empty_dict_pop_false_default(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = {}\n    return payload.pop('missing', False)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_list_wrapped_empty_dict_pop_list_default_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    payload = {}\n    fallback = []\n    item = payload.pop('missing', fallback)\n    return list(item)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_empty_dict_setdefault_without_default(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return {}.setdefault('missing')\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_empty_dict_setdefault_false_default(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = {}\n    return payload.setdefault('missing', False)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_list_wrapped_empty_dict_setdefault_list_default_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    payload = {}\n    fallback = []\n    item = payload.setdefault('missing', fallback)\n    return list(item)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_min_default_none_on_empty_iterable(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return min([], default=None)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_max_default_false_on_empty_iterable_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = []\n    return max(payload, key=0, default=False)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_list_wrapped_min_default_list_on_empty_iterable_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    payload = []\n    fallback = []\n    item = min(payload, default=fallback, key=0)\n    return list(item)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_any_on_empty_list(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return any([])\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_any_on_known_empty_iterable_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = []\n    return any(payload)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_bool_wrapped_any_on_known_empty_iterable_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    payload = []\n    flag = any(payload)\n    return bool(flag)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_negated_all_on_empty_list(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return not all([])\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_negated_all_on_known_empty_iterable_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = []\n    return not all(payload)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_bool_wrapped_negated_all_on_known_empty_iterable_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    payload = []\n    return bool(not all(payload))\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_bool_wrapped_len_on_empty_list(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return bool(len([]))\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_bool_wrapped_len_on_known_empty_iterable_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = []\n    return bool(len(payload))\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_directly_silently_fallback_with_len_compare_on_known_empty_iterable_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    payload = []\n    return len(payload) > 0\n",
        )
        self.assertEqual(
            errors,
            [
                f"异常降级缺少上下文: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_bool_wrapped_sum_on_empty_list(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return bool(sum([]))\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_bool_wrapped_sum_on_known_empty_iterable_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = []\n    return bool(sum(payload))\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_directly_silently_fallback_with_sum_compare_on_known_empty_iterable_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    payload = []\n    return sum(payload) > 0\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_bool_wrapped_count_on_empty_list(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return bool([].count(1))\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_bool_wrapped_count_on_known_empty_iterable_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = []\n    return bool(payload.count(1))\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_directly_silently_fallback_with_count_compare_on_known_empty_iterable_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    payload = []\n    return payload.count(1) > 0\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_empty_string_removeprefix(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return \"\".removeprefix(\"x\")\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_empty_string_removesuffix_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = \"\"\n    return payload.removesuffix(\"x\")\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_bytearray_wrapped_empty_bytes_removeprefix_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    payload = b\"\"\n    cleaned = payload.removeprefix(b\"x\")\n    return bytearray(cleaned)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_empty_string_strip_arg(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return \"\".strip(\"x\")\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_empty_bytes_lstrip_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = b\"\"\n    return payload.lstrip(b\"x\")\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_bytearray_wrapped_empty_bytes_rstrip_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    payload = b\"\"\n    cleaned = payload.rstrip(b\"x\")\n    return bytearray(cleaned)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_empty_string_replace(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return \"\".replace(\"x\", \"y\")\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_empty_bytes_replace_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = b\"\"\n    return payload.replace(b\"x\", b\"y\")\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_bytearray_wrapped_empty_bytes_replace_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    payload = b\"\"\n    cleaned = payload.replace(b\"x\", b\"y\")\n    return bytearray(cleaned)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_empty_string_replace_count(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return \"\".replace(\"x\", \"y\", 1)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_empty_bytes_replace_count_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = b\"\"\n    return payload.replace(b\"x\", b\"y\", 1)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_bytearray_wrapped_empty_bytes_replace_count_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    payload = b\"\"\n    cleaned = payload.replace(b\"x\", b\"y\", 1)\n    return bytearray(cleaned)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_empty_string_replace_keyword_count(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return \"\".replace(\"x\", \"y\", count=1)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_empty_bytes_replace_keyword_count_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = b\"\"\n    return payload.replace(b\"x\", b\"y\", count=1)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_bytearray_wrapped_empty_bytes_replace_keyword_count_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    payload = b\"\"\n    cleaned = payload.replace(b\"x\", b\"y\", count=1)\n    return bytearray(cleaned)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_empty_string_translate(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return \"\".translate({})\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_empty_bytes_translate_none_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = b\"\"\n    return payload.translate(None)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_bytes_wrapped_empty_bytearray_translate_none_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    payload = bytearray()\n    cleaned = payload.translate(None)\n    return bytes(cleaned)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_empty_string_encode_utf8(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return \"\".encode(\"utf-8\")\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_empty_bytes_decode_utf8_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = b\"\"\n    return payload.decode(\"utf-8\")\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_bytearray_wrapped_empty_bytearray_decode_utf8_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    payload = bytearray()\n    text = payload.decode(\"utf-8\")\n    return bytearray(text.encode(\"utf-8\"))\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_empty_string_encode_keyword_utf8(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return \"\".encode(encoding=\"utf-8\")\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_empty_bytes_decode_keyword_utf8_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = b\"\"\n    return payload.decode(encoding=\"utf-8\")\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_bytearray_wrapped_empty_bytearray_decode_keyword_utf8_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    payload = bytearray()\n    text = payload.decode(encoding=\"utf-8\")\n    return bytearray(text.encode(encoding=\"utf-8\"))\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_empty_string_format_args(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return \"\".format(1)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_empty_string_format_kwargs_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    template = \"\"\n    return template.format(name=1)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_bytearray_wrapped_empty_string_format_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    template = \"\"\n    text = template.format(1, name=2)\n    return bytearray(text.encode())\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_empty_string_encode_keyword_errors(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return \"\".encode(errors=\"ignore\")\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_empty_bytes_decode_keyword_errors_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = b\"\"\n    return payload.decode(errors=\"ignore\")\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_bytearray_wrapped_empty_bytearray_decode_keyword_encoding_errors_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    payload = bytearray()\n    text = payload.decode(encoding=\"utf-8\", errors=\"ignore\")\n    return bytearray(text.encode(encoding=\"utf-8\", errors=\"ignore\"))\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_value_error_cannot_directly_silently_fallback_with_bytes_fromhex_on_empty_text(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return bytes.fromhex('')\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> ValueError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_type_error_cannot_directly_silently_fallback_with_bytearray_fromhex_on_known_empty_text_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    payload = ''\n    return bytearray.fromhex(payload)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> TypeError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_os_error_cannot_return_bytearray_wrapped_bytes_fromhex_on_known_empty_text_alias(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept OSError:\n    payload = ''\n    fallback = bytes.fromhex(payload)\n    return bytearray(fallback)\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> OSError {SILENT_FALLBACK_SUFFIX}",
            ],
        )

    def test_key_error_cannot_directly_silently_fallback(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    mapping['missing']\nexcept KeyError:\n    return None\n",
        )
        self.assertEqual(
            errors,
            [
                f"\u5f02\u5e38\u964d\u7ea7\u7f3a\u5c11\u4e0a\u4e0b\u6587: sample.py:3 -> KeyError {SILENT_FALLBACK_SUFFIX}",
            ],
        )


    def test_type_error_cannot_directly_silently_fallback(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept TypeError:\n    return False\n",
        )
        self.assertEqual(
            errors,
            [
                "异常降级缺少上下文: sample.py:3 -> TypeError 不能直接静默降级为 None/False/空字符串/空字节串/空容器",
            ],
        )

    def test_type_error_without_direct_none_false_fallback_passes(self) -> None:
        self.assertEqual(
            collect_silent_fallback_exception_errors_for_python_text(
                Path("sample.py"),
                "try:\n    work()\nexcept TypeError:\n    return 'fallback'\n",
            ),
            [],
        )
        self.assertEqual(
            collect_uncontextualized_exception_errors_for_python_text(
                Path("sample.py"),
                "try:\n    work()\nexcept TypeError:\n    return 'fallback'\n",
            ),
            [],
        )

    def test_value_error_cannot_directly_silently_fallback(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept ValueError:\n    return None\n",
        )
        self.assertEqual(
            errors,
            [
                "异常降级缺少上下文: sample.py:3 -> ValueError 不能直接静默降级为 None/False/空字符串/空字节串/空容器",
            ],
        )

    def test_value_error_without_direct_none_false_fallback_passes(self) -> None:
        self.assertEqual(
            collect_silent_fallback_exception_errors_for_python_text(
                Path("sample.py"),
                "try:\n    work()\nexcept ValueError:\n    return 'fallback'\n",
            ),
            [],
        )
        self.assertEqual(
            collect_uncontextualized_exception_errors_for_python_text(
                Path("sample.py"),
                "try:\n    work()\nexcept ValueError:\n    return 'fallback'\n",
            ),
            [],
        )

    def test_runtime_error_cannot_directly_silently_fallback(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept RuntimeError:\n    return False\n",
        )
        self.assertEqual(
            errors,
            [
                "异常降级缺少上下文: sample.py:3 -> RuntimeError 不能直接静默降级为 None/False/空字符串/空字节串/空容器",
            ],
        )
    def test_non_empty_exception_handling_passes(self) -> None:
        self.assertEqual(
            collect_empty_exception_errors_for_python_text(
                Path("sample.py"),
                "try:\n    work()\nexcept OSError as error:\n    raise RuntimeError(str(error))\n",
            ),
            [],
        )
        self.assertEqual(
            collect_empty_exception_errors_for_powershell_text(
                Path("sample.ps1"),
                "try { Invoke-Thing } catch { throw $_ }\n",
            ),
            [],
        )

    def test_reference_redlines_pass_current_baseline(self) -> None:
        self.assertEqual(collect_errors(), [])


if __name__ == "__main__":
    unittest.main()
