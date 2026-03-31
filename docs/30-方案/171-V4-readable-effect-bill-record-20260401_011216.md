# V4 readable effect bill record

- Time: 2026-04-01 01:12:16 +0800
- Slice: M2 Slice 297
- Action: First locked readable-bill expectations in `tools/checks/check_examples_smoke.py`, then extended `safeclaw-sqlite/examples/safeclaw_mvp_entry.rs` so the shared `report/status` output path now renders a human-readable operation bill from runtime effect data.
- Code Closure: This round intentionally does not add user-level `undo` yet; it closes the higher-leverage prerequisite first by making the current MVP path show what happened in ordinary language before asking users to trust later rollback promises.
- Contracts: The example smoke now fail-closes on three readable bill lines: `操作账单`, `账单条目`, and `账单撤销能力`.
- Result: SafeClaw now has its first screenshotable value proof on the existing MVP path; the next slice can move to a real task scenario instead of refining wording in the abstract.
- Verify: `python -X utf8 tools/checks/check_examples_smoke.py`, `python -X utf8 -m unittest tests.contracts.test_chancellor_panel tests.contracts.test_public_docs_check -v`, `python -X utf8 tools/checks/selfcheck.py`, `git diff --check`.
- Why: Compared with直接继续做 `丞相检查`，先让现有任务输出一张能被普通人看懂的账单，更接近大众产品路线的第一手价值证明。
- Next: Start `M2-P0-2 一个真实任务场景` by choosing one stable, screenshotable task on top of the new readable bill path.
