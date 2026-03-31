# V4 M2 panel command truth table record

- Time: 2026-03-31 20:54:14 +0800
- Slice: M2-1 Slice 293
- Action: Added `docs/chancellor-mode/v2/02-m2-panel-command-truth-source.md` as the single truth table for the first four panel-visible commands: `丞相状态`, `丞相检查`, `丞相版本`, and `丞相验板`.
- Code Closure: This round does not implement aggregation logic yet; it fixes the meaning layer first by defining the public fields, their human meaning, and their primary data sources before command-specific behavior starts diverging.
- Contracts: Indexed the new truth file in `docs/README.md`, linked it from `docs/chancellor-mode/v2/01-m1b-exit-and-m2-panel-entry.md`, and extended `tools/checks/check_public_docs.py` plus `tests/contracts/test_public_docs_check.py` so the new table is fail-closed guarded by public-doc contracts.
- Result: `M2-1` now has a verifiable schema-level starting point; future slices can implement `丞相状态` / `丞相检查` / `丞相版本` / `丞相验板` without re-arguing what each card must show.
- Verify: `python -X utf8 -m unittest tests.contracts.test_public_docs_check -v`, `python -X utf8 tools/checks/check_public_docs.py`, `python -X utf8 tools/checks/check_consistency.py`, `python -X utf8 tools/checks/check_scaffold.py`, `python -X utf8 tools/checks/selfcheck.py`, `git diff --check`.
- Why: Compared with直接先实现某一个命令，先把四命令共同字段收成单一真源更稳；后面每个命令只是在消费这张表，而不是边写边重新发明字段语义。
- Next: Start the first real consumer slice by wiring `丞相状态` to this truth table and locking its `mode` / `stability` / `next_step` / `summary` contract.
