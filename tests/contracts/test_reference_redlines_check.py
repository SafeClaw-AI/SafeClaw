from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.checks.check_reference_redlines import (  # noqa: E402
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
