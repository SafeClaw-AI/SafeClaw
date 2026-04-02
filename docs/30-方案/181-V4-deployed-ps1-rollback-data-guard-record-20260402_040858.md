# V4 deployed ps1 rollback data guard record

- Time: 2026-04-02 04:08:58 +0800
- Slice: M2 Slice 307
- Action: Extended `tests/contracts/test_safeclaw_personal_deploy_cli.py` with a rollback-safety contract for the deployed PowerShell stable launcher. The test now deploys `release-ps1-one`, creates a real archived note through `safeclaw-personal.ps1`, deploys `release-ps1-two`, runs `rollback`, then verifies the archived file is still present and the rolled-back PowerShell launcher can continue with `status -> undo` against the same personal data root.
- Code Closure: This round does not change runtime behavior; it only proves the existing PowerShell deployed path keeps the same rollback safety truth as the cmd deployed path.
- Contracts: The new contract now fail-closes on four truths: rollback only changes the release pointer, the personal archive file survives release switching, the rolled-back PowerShell launcher still sees `archive exists => True`, and the rolled-back PowerShell launcher can still finish `undo` cleanly.
- Result: SafeClaw personal production now has rollback-data safety guarded for both real deployed entrances: `cmd` and `ps1`.
- Verify: `python -X utf8 -m unittest tests.contracts.test_safeclaw_personal_deploy_cli.SafeclawPersonalDeployCliTest.test_rollback_keeps_personal_data_and_old_powershell_release_can_continue -v`, `python -X utf8 tools/checks/selfcheck.py`.
- Why: Compared with继续加别的功能，先让两个真实生产入口都具备同等强度的回滚保数护栏更值，因为这是当前最接近真实使用面的安全边界。
- Next: Stop here; tomorrow morning collect exactly one biggest real-use pain point and only fix that one.
