# V4 personal MVP e2e contract record

- Time: 2026-04-02 01:10:00 +0800
- Slice: M2 Slice 301
- Action: Added `tests/contracts/test_safeclaw_personal_mvp_cli.py` as the first end-to-end contract for the isolated personal launcher, covering `status` before first use plus the full `archive-note -> status -> undo` roundtrip under `SAFECLAW_PERSONAL_ROOT=target/test-safeclaw-personal-cli`.
- Code Closure: This round does not widen the personal launcher surface; it only adds a stable automated guard around the exact owner-only loop already delivered in Slice 300.
- Contracts: The new contract now fail-closes on three user-facing truths: first-use guidance when no last note exists, archive success creating a real file plus the `undo` hint, and post-undo absence of the archived file.
- Result: The personal MVP loop is no longer only “manually verified once”; it is now guarded by a deterministic contract that protects the exact self-use production path the repo owner will rely on tomorrow morning.
- Verify: `python -X utf8 -m unittest tests.contracts.test_safeclaw_personal_mvp_cli -v`, `python -X utf8 tools/checks/selfcheck.py`.
- Why: Compared with继续加更多个人入口功能，先把现有个人最小版的真实链路锁成自动护栏更稳，因为它直接减少“明天能用，后天被无意改坏”的风险。
- Next: Keep the personal MVP loop frozen around one goldline, then only accept changes that improve daily self-use clarity or stability.
