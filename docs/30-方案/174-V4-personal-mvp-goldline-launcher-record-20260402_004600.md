# V4 personal MVP goldline launcher record

- Time: 2026-04-02 00:46:00 +0800
- Slice: M2 Slice 300
- Action: Added a new owner-only launcher trio `tools/mvp/safeclaw_personal_mvp.py` / `.cmd` / `.ps1`, plus `tools/mvp/PERSONAL_MVP_PLAYBOOK.md`, so the current personal-use production path is reduced to `archive-note -> status -> undo` with persistent owner-local state under `%USERPROFILE%\.safeclaw-personal` (or `SAFECLAW_PERSONAL_ROOT`).
- Code Closure: This round intentionally does not widen `safeclaw.cmd`, does not mix in chancellor or governor flows, and does not add new task types; it only narrows the current real-task goldline into a directly usable personal loop.
- Contracts: Added `tests/contracts/test_safeclaw_personal_mvp.py` to lock slug normalization, archive path construction, task-id generation, and the pinned cargo command shape for the personal launcher.
- Result: SafeClaw now has an isolated personal MVP entry that the repo owner can run tomorrow morning without loading the full wrapper mental model: write one archive note, inspect current state, undo the last note, then repeat.
- Verify: `python -X utf8 -m unittest tests.contracts.test_safeclaw_personal_mvp -v`, `python -X utf8 tools/mvp/safeclaw_personal_mvp.py archive-note --name "Bedtime Note" --content "今晚先把最小版跑通"` with `SAFECLAW_PERSONAL_ROOT=target/personal-smoke`, `python -X utf8 tools/mvp/safeclaw_personal_mvp.py status`, `python -X utf8 tools/mvp/safeclaw_personal_mvp.py undo`, `python -X utf8 tools/checks/selfcheck.py`.
- Why: Compared with继续扩大既有 wrapper / 面板 / GUI 面，先把“仓库主人自己能马上用”的最小金线收成独立入口更稳，因为它直接回答了“我明天起床能不能先开始用，再在使用中提意见迭代”这个当前最高优先级问题。
- Next: Freeze the current personal MVP around this single loop, then translate only the minimum helpful human-facing layer on top of it instead of reopening broad system integration.
