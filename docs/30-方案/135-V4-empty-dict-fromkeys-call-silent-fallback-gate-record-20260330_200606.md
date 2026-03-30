# V4 empty dict fromkeys call silent fallback gate record

- Time: 2026-03-30 20:06:06 +0800
- Slice: M1b Slice 263
- Action: Connected empty `dict.fromkeys()` evaluation to the shared silent-fallback truth source in `tools/checks/check_reference_redlines.py` for both static expression evaluation and known-name runtime resolution.
- Code Closure: Now `except ValueError: return dict.fromkeys(())`, `except TypeError: payload = []; return dict.fromkeys(payload)`, and `except OSError: payload = []; mapping = dict.fromkeys(payload); return dict(mapping)` are treated as silent fallbacks and fail closed.
- Contracts: Added 3 contract tests in `tests/contracts/test_reference_redlines_check.py`, covering direct, known-name, and alias paths.
- Result: This slice extends the expression-level truth source from built-in / method calls to built-in classmethod calls that collapse empty iterables into empty mappings.
- Verify: `python -X utf8 -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py`, `python -X utf8 -m unittest tests.contracts.test_reference_redlines_check -v`, `python -X utf8 tools/checks/check_reference_redlines.py`, `python -X utf8 tools/checks/check_ledger_alignment.py`, `git diff --check`
- Why: Compared with sweeping more iterator edge cases, covering `dict.fromkeys()` closes a reusable expression-level collapse path for empty mappings.
- Next: Continue scanning for built-in / method / classmethod gaps of the same level instead of dropping back to low-yield iterator corner cases.
