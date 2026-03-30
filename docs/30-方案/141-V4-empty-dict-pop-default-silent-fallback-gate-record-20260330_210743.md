# V4 empty dict pop default silent fallback gate record

- Time: 2026-03-30 21:07:43 +0800
- Slice: M1b Slice 269
- Action: Connected empty `dict.pop(key, default)` evaluation to the shared silent-fallback truth source in `tools/checks/check_reference_redlines.py` for both static expression evaluation and known-name runtime resolution.
- Code Closure: Now `except ValueError: return {}.pop('missing', None)`, `except TypeError: payload = {}; return payload.pop('missing', False)`, and `except OSError: payload = {}; fallback = []; item = payload.pop('missing', fallback); return list(item)` are treated as silent fallbacks and fail closed.
- Contracts: Added 3 contract tests in `tests/contracts/test_reference_redlines_check.py`, covering direct, known-name, and alias-consumed paths.
- Result: This slice extends the expression-level truth source from empty-dict-plus-default read semantics to empty-dict-plus-default pop semantics.
- Verify: `python -X utf8 -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py`, `python -X utf8 -m unittest tests.contracts.test_reference_redlines_check -v`, `python -X utf8 tools/checks/check_reference_redlines.py`, `python -X utf8 tools/checks/check_ledger_alignment.py`, `git diff --check`
- Why: Compared with sweeping simpler helper edges, covering empty `dict.pop(key, default)` closes a reusable mapping-default semantic lane that commonly appears in real fallback code.
- Next: Continue scanning for built-in / method / classmethod / value-semantic gaps of the same level instead of dropping back to low-yield iterator corner cases.
