# V4 deployed ps1 roundtrip guard record

- Time: 2026-04-02 03:50:12 +0800
- Slice: M2 Slice 306
- Action: Extended `tests/contracts/test_safeclaw_personal_deploy_cli.py` so the deployed `safeclaw-personal.ps1` stable launcher now has a full `archive-note -> status -> undo` roundtrip contract instead of only a first-use `status` contract.
- Code Closure: This round does not change runtime behavior and does not require a new production redeploy; it only tightens the already working PowerShell stable entry around the exact self-use loop.
- Contracts: The new contract now fail-closes on four truths: archive creation through `safeclaw-personal.ps1`, follow-up `status` showing `archive exists => True`, `undo` deleting the archived file again, and all next-step prompts staying pinned to `safeclaw-personal.ps1`.
- Result: SafeClaw personal production no longer has any unguarded stable entry path; both `cmd` and `ps1` deployed launchers are now guarded end to end.
- Verify: `python -X utf8 -m unittest tests.contracts.test_safeclaw_personal_deploy_cli.SafeclawPersonalDeployCliTest.test_deployed_powershell_launcher_runs_archive_note_status_undo_roundtrip -v`, `python -X utf8 tools/checks/selfcheck.py`.
- Why: Compared with继续加别的功能，先让两个真实生产入口都具备同等强度的自动护栏更值，因为这是当前最接近真实使用面的风险。
- Next: Stop here; tomorrow morning collect exactly one biggest real-use pain point and only fix that one.
