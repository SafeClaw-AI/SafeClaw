# V4 empty join method silent fallback gate record

- Time: 2026-03-30 19:55:46 +0800
- Slice: M1b Slice 262
- Action: Connected empty `join()` method evaluation to the shared silent-fallback truth source in `tools/checks/check_reference_redlines.py` for both static expression evaluation and known-name runtime resolution.
- Code Closure: Now `except ValueError: return ''.join(())`, `except TypeError: separator = b''; payload = []; return separator.join(payload)`, and `except OSError: separator = bytearray(); payload = []; joined = separator.join(payload); return bytes(joined)` are treated as silent fallbacks and fail closed.
- Contracts: Added 3 contract tests in `tests/contracts/test_reference_redlines_check.py`, covering direct, known-name, and alias paths.
- Result: This slice extends the expression-level truth source from built-in calls to method calls that collapse empty iterables into empty text / bytes values.
- Verify: `python -X utf8 -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py`, `python -X utf8 -m unittest tests.contracts.test_reference_redlines_check -v`, `python -X utf8 tools/checks/check_reference_redlines.py`, `python -X utf8 tools/checks/check_ledger_alignment.py`, `git diff --check`
- Why: Compared with sweeping more iterator edge cases, covering `join()` closes a broader and more reusable expression-level collapse path.
- Next: Continue scanning for built-in / method call gaps of the same level instead of dropping back to low-yield iterator corner cases.
