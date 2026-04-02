# V4 rollback keeps personal data record

- Time: 2026-04-02 03:15:34 +0800
- Slice: M2 Slice 304
- Action: Extended `tests/contracts/test_safeclaw_personal_deploy_cli.py` with a rollback-safety contract for the deployed slot. The test now deploys `release-one`, creates a real archived note through `safeclaw-personal.cmd`, deploys `release-two`, runs `rollback`, then verifies the archived file is still present and the rolled-back stable launcher can continue with `status -> undo` against the same personal data root.
- Code Closure: This round does not widen product behavior; it only proves the current release-switching path does not mutate user data and remains usable after rollback.
- Contracts: The new contract now fail-closes on four truths: rollback only changes the release pointer, the personal archive file survives release switching, the rolled-back launcher still sees `archive exists => True`, and the rolled-back launcher can still finish `undo` cleanly.
- Result: SafeClaw personal production now has an automated proof for the most important self-use safety promise: release rollback does not eat your notes.
- Verify: `python -X utf8 -m unittest tests.contracts.test_safeclaw_personal_deploy_cli.SafeclawPersonalDeployCliTest.test_rollback_keeps_personal_data_and_old_release_can_continue -v`, `python -X utf8 tools/checks/selfcheck.py`.
- Why: Compared with继续加别的入口或小优化，先锁“回滚不碰数据”更值，因为它直接回答了个人生产位最关键的安全问题。
- Next: Stop here; tomorrow morning collect exactly one real pain point from actual use and only fix that one.
