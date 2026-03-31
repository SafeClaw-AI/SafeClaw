# V4 tmp root governance alignment record

- Time: 2026-03-31 20:09:28 +0800
- Slice: M1b Slice 291
- Action: Updated `docs/30-方案/02-V4-目录锁定清单.md` to explicitly govern `tmp/`, `temp/`, and `docs/chancellor-mode/`, and updated `docs/reference/02-仓库卫生与命名规范.md` so the hygiene truth matches the current execution rules.
- Code Closure: This round does not change runtime code; it removes a stale governance mismatch that had been making `check_scaffold.py` and `selfcheck.py` fail even though `tmp/` is now an intentional, governed validation-output location.
- Contracts: Re-ran `tests/contracts/test_scaffold_check.py`, `check_scaffold.py`, `check_public_docs.py`, `check_consistency.py`, and `selfcheck.py`; all now pass on the current baseline.
- Result: The long-standing `tmp/` root blocker is gone, `M1b` graduation no longer has a fake red light at the structure-governance layer, and `docs/chancellor-mode/` is now an explicit governed docs area instead of a silent exception.
- Verify: `python -X utf8 -m unittest tests.contracts.test_scaffold_check -v`, `python -X utf8 tools/checks/check_scaffold.py`, `python -X utf8 tools/checks/check_public_docs.py`, `python -X utf8 tools/checks/check_consistency.py`, `python -X utf8 tools/checks/selfcheck.py`, `git diff --check`.
- Why: Compared with继续补新的 fail-closed 语义切片，先清掉毕业门禁里这条历史假阻塞，长期收益更高；后面看到红灯时，才知道那是真的工程问题，不是口径滞后。
- Next: Use the newly green scaffold/selfcheck chain to run the bounded `M1b` graduation pass, then switch to the first panel-visible `M2` slice.
