# V4 empty any silent fallback gate record

- Time: 2026-03-31 00:36:58 +0800
- Slice: M1b Slice 272
- Action: Connected empty `any()` evaluation to the shared silent-fallback truth source in `tools/checks/check_reference_redlines.py` for both static expression evaluation and known-name runtime resolution.
- Code Closure: Now `except ValueError: return any([])`, `except TypeError: payload = []; return any(payload)`, and `except OSError: payload = []; flag = any(payload); return bool(flag)` are treated as silent fallbacks and fail closed.
- Contracts: Added 3 contract tests in `tests/contracts/test_reference_redlines_check.py`, covering direct, known-name, and alias-consumed paths.
- Result: This slice extends the expression-level truth source from keyword-default built-in semantics to empty-truthiness built-in semantics on `any()`.
- Verify: `python -X utf8 -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py`, `python -X utf8 -m unittest tests.contracts.test_reference_redlines_check.ReferenceRedlinesCheckTest.test_value_error_cannot_directly_silently_fallback_with_any_on_empty_list tests.contracts.test_reference_redlines_check.ReferenceRedlinesCheckTest.test_type_error_cannot_directly_silently_fallback_with_any_on_known_empty_iterable_alias tests.contracts.test_reference_redlines_check.ReferenceRedlinesCheckTest.test_os_error_cannot_return_bool_wrapped_any_on_known_empty_iterable_alias -v`, `python -X utf8 -m unittest tests.contracts.test_reference_redlines_check -v`, `python -X utf8 tools/checks/check_reference_redlines.py`, `python -X utf8 tools/checks/check_ledger_alignment.py`, `git diff --check`
- Why: Compared with sweeping simpler helper edges, covering empty `any()` closes a reusable built-in truthiness lane with higher long-term leverage.
- Next: Continue scanning for built-in / method / classmethod / value-semantic gaps of the same level instead of dropping back to low-yield iterator corner cases.
