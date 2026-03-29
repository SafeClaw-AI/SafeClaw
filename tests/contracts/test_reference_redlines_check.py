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
    _parse_python_text_for_reference_check,
    _handler_caught_types,
    _handler_uses_broad_exception_family,
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
        self.assertEqual(SILENT_FALLBACK_SUFFIX, "不能直接静默降级为 None/False")
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

        bare_profile = _build_handler_exception_gate_profile(bare_handler)
        tuple_profile = _build_handler_exception_gate_profile(tuple_handler)
        broad_tuple_profile = _build_handler_exception_gate_profile(broad_tuple_handler)
        high_risk_profile = _build_handler_exception_gate_profile(high_risk_handler)

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
        self.assertEqual(tuple_profile.silent_fallback_requirement_message, f"OSError {SILENT_FALLBACK_SUFFIX}")
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
        expected = (
            "FileExistsError",
            "KeyError",
            "OSError",
            "RuntimeError",
            "SyntaxError",
            "SystemError",
            "json.JSONDecodeError",
            "subprocess.TimeoutExpired",
        )
        self.assertEqual(SILENT_FALLBACK_EXCEPTION_TYPE_ORDER, expected)
        self.assertEqual(HIGH_RISK_EXCEPTION_TYPES, set(expected))
        self.assertIs(SILENT_FALLBACK_EXCEPTION_TYPES, HIGH_RISK_EXCEPTION_TYPES)
        self.assertIs(CONTEXT_REQUIRED_EXCEPTION_TYPES, HIGH_RISK_EXCEPTION_TYPES)
        self.assertEqual(SILENT_FALLBACK_EXCEPTION_TYPES, set(expected))
        self.assertEqual(CONTEXT_REQUIRED_EXCEPTION_TYPES, set(expected))

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
                "异常降级缺少上下文: sample.py:3 -> OSError 不能直接静默降级为 None/False",
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
                "异常降级缺少上下文: sample.py:3 -> 裸 except 不能直接静默降级为 None/False",
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
                "异常降级缺少上下文: sample.py:3 -> broad except 不能直接静默降级为 None/False",
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
                "异常降级缺少上下文: sample.py:3 -> broad except 不能直接静默降级为 None/False",
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
                "异常降级缺少上下文: sample.py:3 -> broad except 不能直接静默降级为 None/False",
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
                "异常降级缺少上下文: sample.py:3 -> broad except 不能直接静默降级为 None/False",
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
                "异常降级缺少上下文: sample.py:3 -> SystemError 不能直接静默降级为 None/False",
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
                "异常降级缺少上下文: sample.py:4 -> subprocess.TimeoutExpired 不能直接静默降级为 None/False",
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
                "异常降级缺少上下文: sample.py:3 -> KeyError 不能直接静默降级为 None/False",
            ],
        )

    def test_runtime_error_cannot_directly_silently_fallback(self) -> None:
        errors = collect_silent_fallback_exception_errors_for_python_text(
            Path("sample.py"),
            "try:\n    work()\nexcept RuntimeError:\n    return False\n",
        )
        self.assertEqual(
            errors,
            [
                "异常降级缺少上下文: sample.py:3 -> RuntimeError 不能直接静默降级为 None/False",
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
