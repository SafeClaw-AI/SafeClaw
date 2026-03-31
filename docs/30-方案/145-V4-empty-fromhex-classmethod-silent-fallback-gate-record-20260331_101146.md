# V4 empty fromhex classmethod silent fallback gate record

- Time: 2026-03-31 10:11:46 +0800
- Slice: M1b Slice 273
- Action: Connected empty `bytes.fromhex()` / `bytearray.fromhex()` classmethod evaluation to the shared silent-fallback truth source in `tools/checks/check_reference_redlines.py` for both static expression evaluation and known-name runtime resolution.
- Code Closure: Now `except ValueError: return bytes.fromhex('')`, `except TypeError: payload = ''; return bytearray.fromhex(payload)`, and `except OSError: payload = ''; fallback = bytes.fromhex(payload); return bytearray(fallback)` are treated as silent fallbacks and fail closed.
- Contracts: Added 3 contract tests in `tests/contracts/test_reference_redlines_check.py`, covering direct, known-name, and alias-consumed paths.
- Result: This slice extends the expression-level gap scan from empty-truthiness built-in semantics to empty classmethod decoding semantics on `fromhex()`.
- Verify: `python -X utf8 -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py`, `python -X utf8 -m unittest tests.contracts.test_reference_redlines_check.ReferenceRedlinesCheckTest.test_value_error_cannot_directly_silently_fallback_with_bytes_fromhex_on_empty_text tests.contracts.test_reference_redlines_check.ReferenceRedlinesCheckTest.test_type_error_cannot_directly_silently_fallback_with_bytearray_fromhex_on_known_empty_text_alias tests.contracts.test_reference_redlines_check.ReferenceRedlinesCheckTest.test_os_error_cannot_return_bytearray_wrapped_bytes_fromhex_on_known_empty_text_alias -v`, `python -X utf8 -m unittest tests.contracts.test_reference_redlines_check -v`, `python -X utf8 tools/checks/check_reference_redlines.py`, `python -X utf8 tools/checks/check_ledger_alignment.py`, `git diff --check`
- Why: Compared with lower-yield edge sweeps, landing empty `fromhex()` closes a same-level built-in classmethod lane with low implementation cost and reusable byte-empty semantics.
- Next: Continue scanning same-level built-in / method / classmethod / value-semantic gaps instead of dropping back to low-yield iterator corner cases.
