# V4 empty filter call silent fallback gate record

- Time: 2026-03-30 20:36:32 +0800
- Slice: M1b Slice 266
- Action: Connected empty `filter()` evaluation to the shared silent-fallback truth source in `tools/checks/check_reference_redlines.py` for both static expression evaluation and known-name runtime resolution.
- Code Closure: Now `except ValueError: return list(filter(None, ()))`, `except TypeError: payload = []; return tuple(filter(None, payload))`, and `except OSError: payload = []; items = filter(None, payload); return set(items)` are treated as silent fallbacks and fail closed.
- Contracts: Added 3 contract tests in `tests/contracts/test_reference_redlines_check.py`, covering direct, known-name, and alias paths.
- Result: This slice extends the expression-level truth source to the `filter()` built-in while reusing the shared empty-iterator semantic.
- Verify: `python -X utf8 -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py`, `python -X utf8 -m unittest tests.contracts.test_reference_redlines_check -v`, `python -X utf8 tools/checks/check_reference_redlines.py`, `python -X utf8 tools/checks/check_ledger_alignment.py`, `git diff --check`
- Why: Compared with sweeping more iterator corner cases, covering `filter()` closes another reusable built-in call gap that plugs into existing constructor-consumption logic.
- Next: Continue scanning for built-in / method / classmethod / value-semantic gaps of the same level instead of dropping back to low-yield iterator corner cases.
