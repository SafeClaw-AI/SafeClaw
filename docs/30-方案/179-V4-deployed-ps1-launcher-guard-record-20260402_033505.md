# V4 deployed ps1 launcher guard record

- Time: 2026-04-02 03:35:05 +0800
- Slice: M2 Slice 305
- Action: Extended `tests/contracts/test_safeclaw_personal_deploy_cli.py` with a PowerShell stable-launcher contract for the deployed slot. The new test exposed a real bug: `safeclaw-personal.ps1` built the target script path in one nested expression and produced an invalid path at runtime. `tools/mvp/safeclaw_personal_deploy.py` now composes the release path step by step, and the default personal production slot was redeployed afterward.
- Code Closure: This round does not widen behavior; it only fixes the already-shipped PowerShell stable launcher so it matches the same truth as the cmd stable launcher.
- Contracts: The new contract now fail-closes on three truths: the deployed `safeclaw-personal.ps1` can run `status`, first-use guidance still appears, and the next-step prompt is pinned to `safeclaw-personal.ps1 archive-note --name <name> --content <text>`.
- Result: SafeClaw personal production no longer has a broken备用 PowerShell entry; both stable launchers now resolve the deployed repo snapshot correctly.
- Verify: `python -X utf8 -m unittest tests.contracts.test_safeclaw_personal_deploy_cli.SafeclawPersonalDeployCliTest.test_deployed_powershell_launcher_status_uses_ps1_entry_prompt -v`, `powershell.exe -ExecutionPolicy Bypass -File %USERPROFILE%\.safeclaw-personal-production\safeclaw-personal.ps1 status`, `python -X utf8 tools/checks/selfcheck.py`.
- Why: Compared with继续补别的优化，先修掉生产位里真实坏掉的一个入口更值，因为这是确凿 bug，不是想象需求。
- Next: Stop here; tomorrow morning collect exactly one biggest real-use pain point and only fix that one.
