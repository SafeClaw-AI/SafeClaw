# V4 personal MVP deploy slot record

- Time: 2026-04-02 02:03:41 +0800
- Slice: M2 Slice 302
- Action: Added `tools/mvp/safeclaw_personal_deploy.py` as the maintenance-layer deploy helper for the owner-only MVP. It only does `deploy / rollback / status`, snapshots the minimal personal runtime into `%USERPROFILE%\.safeclaw-personal-production\releases\<release>\repo`, writes stable launchers `safeclaw-personal.cmd` / `.ps1`, and uses `current_release.txt` as the rollback pointer.
- Code Closure: This round does not widen the personal product surface and does not mix in chancellor or governor flows; it only gives the already-frozen personal goldline a reversible production slot separate from the live working repo.
- Contracts: Added `tests/contracts/test_safeclaw_personal_deploy.py` to lock snapshot scope, stable launcher text, and rollback target selection; added `tests/contracts/test_safeclaw_personal_deploy_cli.py` to lock `deploy`, stable launcher `status`, and `rollback` end to end.
- Result: SafeClaw personal MVP now has a truthful “deploy for self-use, keep rollback ready” path. The repo owner can ship the current goldline into a separate slot, use the stable launcher there, and switch back to the previous release without touching the personal data root.
- Verify: `python -X utf8 -m unittest tests.contracts.test_safeclaw_personal_deploy -v`, `python -X utf8 -m unittest tests.contracts.test_safeclaw_personal_deploy_cli -v`.
- Why: Compared with继续扩大 GUI / 面板 / 多入口面，先把已经可用的个人金线隔离进一个可回滚的生产槽位更稳，因为它直接解决“我想尽快推生产自用，但不想和开发仓库绑死”这个当前最高复利问题。
- Next: Keep the deployed personal slot frozen, let the repo owner really use it once tomorrow morning, then only fix the single biggest pain point found in daily use.
