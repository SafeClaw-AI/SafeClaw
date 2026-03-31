# V4 M1b exit and M2 panel entry freeze record

- Time: 2026-03-31 19:52:12 +0800
- Slice: M1b Slice 290
- Action: Added `docs/chancellor-mode/v2/01-m1b-exit-and-m2-panel-entry.md` as the current truth source, froze `M1b` exit gates, and defined the first `M2` panel-visible delivery around `丞相状态` / `丞相检查` / `丞相版本` / `丞相验板`.
- Code Closure: This round does not change runtime code; it removes the planning ambiguity that would otherwise let `M1b` keep expanding while `M2` still has two competing entry assumptions.
- Contracts: Synced `开发计划.md`, `MVP_PROGRESS.md`, and `PUSH_LOG.md` so the current mainline, graduation rules, and next visible delivery all point to the same truth source.
- Result: The project now has a single current answer for three questions: when `M1b` is allowed to stop, what no longer belongs to `M1b`, and what `M2` must show to users first.
- Verify: `python -X utf8 tools/checks/check_consistency.py`, `python -X utf8 tools/checks/check_ledger_alignment.py`, `python -X utf8 tools/checks/check_public_docs.py`, `python -X utf8 tools/checks/check_scaffold.py`, `python -X utf8 tools/checks/selfcheck.py`, `git diff --check`.
- Why: Compared with继续只补 fail-closed 尾刀，先把入口口径和毕业边界冻结成真源，长期收益更高；这样后面每一刀都知道自己是在收 `M1b`，还是在交付 `M2` 的第一眼价值。
- Next: Keep `M1b` bounded to its tail pack and `tmp/` blocker cleanup, then switch to the first panel-visible `M2` slice instead of reopening old UI assumptions.
