# V4 m2 product value rebaseline record

- Time: 2026-04-01 00:48:36 +0800
- Slice: M2 Slice 296
- Action: Added `docs/chancellor-mode/v2/03-m2-product-value-rebaseline.md` as the current M2 sequencing truth so the project stops polishing explanation-first panel commands before shipping a screenshotable, undoable proof of value.
- Code Closure: This round intentionally does not implement the readable ledger bill yet; it closes the higher-leverage planning root cause first so the next code slice lands on the right product proof path.
- Contracts: Updated `docs/README.md`, `tools/checks/check_public_docs.py`, and `tests/contracts/test_public_docs_check.py` so the new “可读账单 → 真实任务 → undo” priority is public-doc fail-closed guarded.
- Result: `M2` now has a single current truth source that matches the real product roadmap: first prove value to ordinary users, then continue explanation layer, then consider GUI and model-threshold reductions.
- Verify: `python -X utf8 -m unittest tests.contracts.test_public_docs_check -v`, `python -X utf8 tools/checks/check_public_docs.py`, `python -X utf8 tools/checks/check_consistency.py`, `python -X utf8 tools/checks/check_scaffold.py`, `git diff --check`.
- Why: Compared with继续做 `丞相检查`，先把主线改成“可读账单 / 真实任务 / undo”更符合大众产品路线，也更接近 SafeClaw 最有力的差异化证明。
- Next: Start `M2-P0-1 Effect Ledger 可读账单` by finding the narrowest place to render a human-readable operation bill from the existing effect/runtime data.
