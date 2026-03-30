# V4 empty sorted call silent fallback gate record

- Time: 2026-03-30 19:42:22 +0800
- Slice: M1b Slice 261
- Action: Connected empty `sorted()` evaluation to the shared silent-fallback truth source in `tools/checks/check_reference_redlines.py` for both static expression evaluation and known-name runtime resolution.
- Code Closure: Now `except ValueError: return sorted(())`, `except TypeError: payload = []; return sorted(payload)`, and `except OSError: payload = []; items = sorted(payload); return tuple(items)` are treated as silent fallbacks and fail closed.
- Contracts: Added 3 contract tests in `tests/contracts/test_reference_redlines_check.py`, covering direct, known-name, and alias paths.
- Result: This slice opens a new expression-level built-in call lane beyond iterator helpers, letting empty `sorted()` collapse to `[]` through the same truth source.
- Verify: `python -X utf8 -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py`, `python -X utf8 -m unittest tests.contracts.test_reference_redlines_check -v`, `python -X utf8 tools/checks/check_reference_redlines.py`, `python -X utf8 tools/checks/check_ledger_alignment.py`, `git diff --check`
- Why: Compared with sweeping more iterator edge cases, landing a built-in call that directly collapses empty iterables into empty containers has better long-term leverage.
- Next: Continue scanning for built-in call / expression gaps of the same level instead of dropping back to low-yield iterator corner cases.
