from __future__ import annotations

import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOYER = REPO_ROOT / "tools" / "mvp" / "safeclaw_personal_deploy.py"
TEST_DEPLOY_ROOT = REPO_ROOT / "target" / "test-safeclaw-personal-deploy"
TEST_PERSONAL_ROOT = REPO_ROOT / "target" / "test-safeclaw-personal-deploy-data"
ARCHIVE_DATE = "2026-04-02"
ARCHIVE_NAME = "Deployed Roundtrip"
ARCHIVE_FILE = TEST_PERSONAL_ROOT / "archive" / "2026-04" / "2026-04-02-deployed-roundtrip.md"


class SafeclawPersonalDeployCliTest(unittest.TestCase):
    def setUp(self) -> None:
        shutil.rmtree(TEST_DEPLOY_ROOT, ignore_errors=True)
        shutil.rmtree(TEST_PERSONAL_ROOT, ignore_errors=True)

    def run_deployer(self, *args: str, release_id: str | None = None) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["SAFECLAW_PERSONAL_DEPLOY_ROOT"] = str(TEST_DEPLOY_ROOT)
        if release_id is not None:
            env["SAFECLAW_PERSONAL_DEPLOY_RELEASE_ID"] = release_id
        return subprocess.run(
            [sys.executable, "-X", "utf8", str(DEPLOYER), *args],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def run_prod_launcher(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["SAFECLAW_PERSONAL_ROOT"] = str(TEST_PERSONAL_ROOT)
        return subprocess.run(
            ["cmd", "/c", str(TEST_DEPLOY_ROOT / "safeclaw-personal.cmd"), *args],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def run_prod_launcher_ps1(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["SAFECLAW_PERSONAL_ROOT"] = str(TEST_PERSONAL_ROOT)
        return subprocess.run(
            [
                "powershell.exe",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(TEST_DEPLOY_ROOT / "safeclaw-personal.ps1"),
                *args,
            ],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_deploy_creates_stable_launcher_and_snapshot(self) -> None:
        completed = self.run_deployer("deploy", release_id="release-one")
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("[deploy] summary => 个人生产位已经更新到新版本。", completed.stdout)
        self.assertIn("[deploy] current release => release-one", completed.stdout)
        self.assertTrue((TEST_DEPLOY_ROOT / "safeclaw-personal.cmd").exists())
        self.assertTrue((TEST_DEPLOY_ROOT / "safeclaw-personal.ps1").exists())
        self.assertTrue((TEST_DEPLOY_ROOT / "safeclaw-personal-panel.cmd").exists())
        self.assertTrue((TEST_DEPLOY_ROOT / "safeclaw-personal-panel.ps1").exists())
        self.assertEqual((TEST_DEPLOY_ROOT / "current_release.txt").read_text(encoding="utf-8").strip(), "release-one")
        self.assertTrue((TEST_DEPLOY_ROOT / "releases" / "release-one" / "repo" / "Cargo.toml").exists())
        self.assertTrue((TEST_DEPLOY_ROOT / "releases" / "release-one" / "repo" / "tools" / "mvp" / "safeclaw_personal_mvp.py").exists())
        self.assertTrue((TEST_DEPLOY_ROOT / "releases" / "release-one" / "repo" / "tools" / "mvp" / "safeclaw_personal_panel.py").exists())
        self.assertTrue((TEST_DEPLOY_ROOT / "releases" / "release-one" / "repo" / "tools" / "mvp" / "safeclaw_personal_panel.pyw").exists())
        self.assertTrue((TEST_DEPLOY_ROOT / "releases" / "release-one" / "repo" / "target" / "debug" / "examples" / "safeclaw_mvp_entry.exe").exists())
        self.assertIn(f"[deploy] next => {TEST_DEPLOY_ROOT / 'safeclaw-personal-panel.cmd'}", completed.stdout)

        status_completed = self.run_prod_launcher("status")
        self.assertEqual(status_completed.returncode, 0, status_completed.stdout + status_completed.stderr)
        self.assertIn("[personal] last note => none", status_completed.stdout)
        self.assertIn("safeclaw-personal.cmd archive-note --name <name> --content <text>", status_completed.stdout)

    def test_rollback_moves_current_release_back_to_previous_one(self) -> None:
        first = self.run_deployer("deploy", release_id="release-one")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        second = self.run_deployer("deploy", release_id="release-two")
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)

        rollback = self.run_deployer("rollback")
        self.assertEqual(rollback.returncode, 0, rollback.stdout + rollback.stderr)
        self.assertIn("[deploy] summary => 个人生产位已经切回上一版。", rollback.stdout)
        self.assertIn("[deploy] rolled back => release-one", rollback.stdout)
        self.assertIn(f"[deploy] next => {TEST_DEPLOY_ROOT / 'safeclaw-personal-panel.cmd'}", rollback.stdout)
        self.assertEqual((TEST_DEPLOY_ROOT / "current_release.txt").read_text(encoding="utf-8").strip(), "release-one")

    def test_deploy_with_existing_release_id_explains_status_next_step(self) -> None:
        first = self.run_deployer("deploy", release_id="release-one")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)

        second = self.run_deployer("deploy", release_id="release-one")
        self.assertEqual(second.returncode, 1, second.stdout + second.stderr)
        self.assertIn("[deploy] summary => 这个版本号已经存在，这次没有重复部署。", second.stdout)
        self.assertIn("[deploy] release already exists => release-one", second.stdout)
        self.assertIn(
            "[deploy] next => python -X utf8 tools/mvp/safeclaw_personal_deploy.py status",
            second.stdout,
        )
        self.assertLess(
            second.stdout.index("[deploy] summary => 这个版本号已经存在，这次没有重复部署。"),
            second.stdout.index("[deploy] release already exists => release-one"),
        )
        self.assertLess(
            second.stdout.index("[deploy] release already exists => release-one"),
            second.stdout.index("[deploy] next => python -X utf8 tools/mvp/safeclaw_personal_deploy.py status"),
        )

    def test_status_without_release_explains_next_step(self) -> None:
        status_completed = self.run_deployer("status")
        self.assertEqual(status_completed.returncode, 0, status_completed.stdout + status_completed.stderr)
        self.assertIn("[deploy] summary => 当前还没有部署版本。", status_completed.stdout)
        self.assertIn(
            "[deploy] next => python -X utf8 tools/mvp/safeclaw_personal_deploy.py deploy",
            status_completed.stdout,
        )
        self.assertIn("[deploy] current release => none", status_completed.stdout)
        self.assertLess(
            status_completed.stdout.index("[deploy] summary => 当前还没有部署版本。"),
            status_completed.stdout.index("[deploy] root => "),
        )
        self.assertLess(
            status_completed.stdout.index("[deploy] panel => "),
            status_completed.stdout.index(
                "[deploy] next => python -X utf8 tools/mvp/safeclaw_personal_deploy.py deploy"
            ),
        )

    def test_rollback_without_release_explains_next_step(self) -> None:
        rollback = self.run_deployer("rollback")
        self.assertEqual(rollback.returncode, 1, rollback.stdout + rollback.stderr)
        self.assertIn("[deploy] summary => 当前还没有可回滚的生产版本。", rollback.stdout)
        self.assertIn("[deploy] no current release", rollback.stdout)
        self.assertIn(
            "[deploy] next => python -X utf8 tools/mvp/safeclaw_personal_deploy.py deploy",
            rollback.stdout,
        )
        self.assertLess(
            rollback.stdout.index("[deploy] summary => 当前还没有可回滚的生产版本。"),
            rollback.stdout.index("[deploy] no current release"),
        )
        self.assertLess(
            rollback.stdout.index("[deploy] no current release"),
            rollback.stdout.index(
                "[deploy] next => python -X utf8 tools/mvp/safeclaw_personal_deploy.py deploy"
            ),
        )

    def test_rollback_with_only_one_release_explains_status_next_step(self) -> None:
        deploy = self.run_deployer("deploy", release_id="release-one")
        self.assertEqual(deploy.returncode, 0, deploy.stdout + deploy.stderr)

        rollback = self.run_deployer("rollback")
        self.assertEqual(rollback.returncode, 1, rollback.stdout + rollback.stderr)
        self.assertIn("[deploy] summary => 当前只有一个生产版本，还没有上一版可回滚。", rollback.stdout)
        self.assertIn("[deploy] no previous release to roll back to", rollback.stdout)
        self.assertIn(
            "[deploy] next => python -X utf8 tools/mvp/safeclaw_personal_deploy.py status",
            rollback.stdout,
        )
        self.assertLess(
            rollback.stdout.index("[deploy] summary => 当前只有一个生产版本，还没有上一版可回滚。"),
            rollback.stdout.index("[deploy] no previous release to roll back to"),
        )
        self.assertLess(
            rollback.stdout.index("[deploy] no previous release to roll back to"),
            rollback.stdout.index(
                "[deploy] next => python -X utf8 tools/mvp/safeclaw_personal_deploy.py status"
            ),
        )

    def test_deployed_powershell_launcher_status_uses_ps1_entry_prompt(self) -> None:
        deploy = self.run_deployer("deploy", release_id="release-ps1")
        self.assertEqual(deploy.returncode, 0, deploy.stdout + deploy.stderr)

        status_completed = self.run_prod_launcher_ps1("status")
        self.assertEqual(status_completed.returncode, 0, status_completed.stdout + status_completed.stderr)
        self.assertIn("[personal] last note => none", status_completed.stdout)
        self.assertIn(
            "safeclaw-personal.ps1 archive-note --name <name> --content <text>",
            status_completed.stdout,
        )

    def test_deployed_launcher_runs_archive_note_status_undo_roundtrip(self) -> None:
        deploy = self.run_deployer("deploy", release_id="release-roundtrip")
        self.assertEqual(deploy.returncode, 0, deploy.stdout + deploy.stderr)

        archive_completed = self.run_prod_launcher(
            "archive-note",
            "--name",
            ARCHIVE_NAME,
            "--date",
            ARCHIVE_DATE,
            "--content",
            "已部署入口真实回路验证",
        )
        self.assertEqual(
            archive_completed.returncode,
            0,
            archive_completed.stdout + archive_completed.stderr,
        )
        self.assertIn("[mvp] archive note => created", archive_completed.stdout)
        self.assertIn("[personal] next => safeclaw-personal.cmd undo", archive_completed.stdout)
        self.assertTrue(ARCHIVE_FILE.exists())

        status_completed = self.run_prod_launcher("status")
        self.assertEqual(status_completed.returncode, 0, status_completed.stdout + status_completed.stderr)
        self.assertIn("[personal] archive exists => True", status_completed.stdout)
        self.assertIn("[personal] next => safeclaw-personal.cmd undo", status_completed.stdout)

        undo_completed = self.run_prod_launcher("undo")
        self.assertEqual(undo_completed.returncode, 0, undo_completed.stdout + undo_completed.stderr)
        self.assertIn(
            "[mvp] undo result => worker=RolledBack effect=RolledBack compensation=0",
            undo_completed.stdout,
        )
        self.assertIn("[personal] archive exists => False", undo_completed.stdout)
        self.assertIn(
            "[personal] next => safeclaw-personal.cmd archive-note --name <name> --content <text>",
            undo_completed.stdout,
        )
        self.assertFalse(ARCHIVE_FILE.exists())

    def test_deployed_powershell_launcher_runs_archive_note_status_undo_roundtrip(self) -> None:
        deploy = self.run_deployer("deploy", release_id="release-ps1-roundtrip")
        self.assertEqual(deploy.returncode, 0, deploy.stdout + deploy.stderr)

        archive_completed = self.run_prod_launcher_ps1(
            "archive-note",
            "--name",
            ARCHIVE_NAME,
            "--date",
            ARCHIVE_DATE,
            "--content",
            "已部署 PowerShell 入口真实回路验证",
        )
        self.assertEqual(
            archive_completed.returncode,
            0,
            archive_completed.stdout + archive_completed.stderr,
        )
        self.assertIn("[mvp] archive note => created", archive_completed.stdout)
        self.assertIn("[personal] next => safeclaw-personal.ps1 undo", archive_completed.stdout)
        self.assertTrue(ARCHIVE_FILE.exists())

        status_completed = self.run_prod_launcher_ps1("status")
        self.assertEqual(status_completed.returncode, 0, status_completed.stdout + status_completed.stderr)
        self.assertIn("[personal] archive exists => True", status_completed.stdout)
        self.assertIn("[personal] next => safeclaw-personal.ps1 undo", status_completed.stdout)

        undo_completed = self.run_prod_launcher_ps1("undo")
        self.assertEqual(undo_completed.returncode, 0, undo_completed.stdout + undo_completed.stderr)
        self.assertIn(
            "[mvp] undo result => worker=RolledBack effect=RolledBack compensation=0",
            undo_completed.stdout,
        )
        self.assertIn("[personal] archive exists => False", undo_completed.stdout)
        self.assertIn(
            "[personal] next => safeclaw-personal.ps1 archive-note --name <name> --content <text>",
            undo_completed.stdout,
        )
        self.assertFalse(ARCHIVE_FILE.exists())

    def test_rollback_keeps_personal_data_and_old_release_can_continue(self) -> None:
        first = self.run_deployer("deploy", release_id="release-one")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)

        archive_completed = self.run_prod_launcher(
            "archive-note",
            "--name",
            ARCHIVE_NAME,
            "--date",
            ARCHIVE_DATE,
            "--content",
            "回滚后继续使用验证",
        )
        self.assertEqual(
            archive_completed.returncode,
            0,
            archive_completed.stdout + archive_completed.stderr,
        )
        self.assertTrue(ARCHIVE_FILE.exists())

        second = self.run_deployer("deploy", release_id="release-two")
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)

        rollback = self.run_deployer("rollback")
        self.assertEqual(rollback.returncode, 0, rollback.stdout + rollback.stderr)
        self.assertIn("[deploy] rolled back => release-one", rollback.stdout)
        self.assertTrue(ARCHIVE_FILE.exists())

        status_completed = self.run_prod_launcher("status")
        self.assertEqual(status_completed.returncode, 0, status_completed.stdout + status_completed.stderr)
        self.assertIn("[personal] archive exists => True", status_completed.stdout)
        self.assertIn("[personal] next => safeclaw-personal.cmd undo", status_completed.stdout)

        undo_completed = self.run_prod_launcher("undo")
        self.assertEqual(undo_completed.returncode, 0, undo_completed.stdout + undo_completed.stderr)
        self.assertIn("[personal] archive exists => False", undo_completed.stdout)
        self.assertFalse(ARCHIVE_FILE.exists())

    def test_rollback_keeps_personal_data_and_old_powershell_release_can_continue(self) -> None:
        first = self.run_deployer("deploy", release_id="release-ps1-one")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)

        archive_completed = self.run_prod_launcher_ps1(
            "archive-note",
            "--name",
            ARCHIVE_NAME,
            "--date",
            ARCHIVE_DATE,
            "--content",
            "PowerShell 回滚后继续使用验证",
        )
        self.assertEqual(
            archive_completed.returncode,
            0,
            archive_completed.stdout + archive_completed.stderr,
        )
        self.assertTrue(ARCHIVE_FILE.exists())

        second = self.run_deployer("deploy", release_id="release-ps1-two")
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)

        rollback = self.run_deployer("rollback")
        self.assertEqual(rollback.returncode, 0, rollback.stdout + rollback.stderr)
        self.assertIn("[deploy] rolled back => release-ps1-one", rollback.stdout)
        self.assertTrue(ARCHIVE_FILE.exists())

        status_completed = self.run_prod_launcher_ps1("status")
        self.assertEqual(status_completed.returncode, 0, status_completed.stdout + status_completed.stderr)
        self.assertIn("[personal] archive exists => True", status_completed.stdout)
        self.assertIn("[personal] next => safeclaw-personal.ps1 undo", status_completed.stdout)

        undo_completed = self.run_prod_launcher_ps1("undo")
        self.assertEqual(undo_completed.returncode, 0, undo_completed.stdout + undo_completed.stderr)
        self.assertIn("[personal] archive exists => False", undo_completed.stdout)
        self.assertFalse(ARCHIVE_FILE.exists())


if __name__ == "__main__":
    unittest.main()
