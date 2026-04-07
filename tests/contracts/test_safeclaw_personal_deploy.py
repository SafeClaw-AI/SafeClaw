from __future__ import annotations

import unittest
from pathlib import Path

from tests.contracts import REPO_ROOT
from tools.mvp.safeclaw_personal_deploy import (
    DEPLOY_SNAPSHOT_PATHS,
    build_deploy_copy_ignore_names,
    build_cmd_launcher,
    build_panel_cmd_launcher,
    build_panel_ps1_launcher,
    build_ps1_launcher,
    pick_rollback_release,
)


class SafeclawPersonalDeployTest(unittest.TestCase):
    def test_snapshot_paths_cover_minimal_personal_runtime(self) -> None:
        self.assertIn(Path("Cargo.toml"), DEPLOY_SNAPSHOT_PATHS)
        self.assertIn(Path("Cargo.lock"), DEPLOY_SNAPSHOT_PATHS)
        self.assertIn(Path("VERSION"), DEPLOY_SNAPSHOT_PATHS)
        self.assertIn(Path("safeclaw-core"), DEPLOY_SNAPSHOT_PATHS)
        self.assertIn(Path("safeclaw-sqlite"), DEPLOY_SNAPSHOT_PATHS)
        self.assertIn(Path("tools/mvp/safeclaw_personal_mvp.py"), DEPLOY_SNAPSHOT_PATHS)
        self.assertIn(Path("tools/mvp/safeclaw_personal_mvp.cmd"), DEPLOY_SNAPSHOT_PATHS)
        self.assertIn(Path("tools/mvp/safeclaw_personal_mvp.ps1"), DEPLOY_SNAPSHOT_PATHS)
        self.assertIn(Path("tools/mvp/safeclaw_personal_panel.py"), DEPLOY_SNAPSHOT_PATHS)
        self.assertIn(Path("tools/mvp/safeclaw_personal_panel.pyw"), DEPLOY_SNAPSHOT_PATHS)
        self.assertIn(Path("tools/mvp/PERSONAL_MVP_PLAYBOOK.md"), DEPLOY_SNAPSHOT_PATHS)

    def test_build_cmd_launcher_resolves_current_release_snapshot(self) -> None:
        launcher = build_cmd_launcher()
        self.assertIn("current_release.txt", launcher)
        self.assertIn(r"releases\%CURRENT_RELEASE%\repo\tools\mvp\safeclaw_personal_mvp.py", launcher)
        self.assertIn("[deploy] summary =^> 当前还没有可用的生产版本入口。", launcher)
        self.assertIn("[deploy] next =^> 先检查并修复 current_release.txt，再重新部署。", launcher)
        self.assertIn("[deploy] summary =^> 当前生产入口不完整，这次没法继续。", launcher)
        self.assertIn("[deploy] next =^> 先重新部署当前版本，再重试。", launcher)

    def test_build_ps1_launcher_resolves_current_release_snapshot(self) -> None:
        launcher = build_ps1_launcher()
        self.assertIn("current_release.txt", launcher)
        self.assertIn("releases", launcher)
        self.assertIn("safeclaw_personal_mvp.py", launcher)
        self.assertIn("[deploy] summary => 当前还没有可用的生产版本入口。", launcher)
        self.assertIn("[deploy] empty current release pointer => $currentReleaseFile", launcher)
        self.assertIn("[deploy] summary => 当前生产入口不完整，这次没法继续。", launcher)

    def test_build_panel_cmd_launcher_resolves_current_release_snapshot(self) -> None:
        launcher = build_panel_cmd_launcher()
        self.assertIn("current_release.txt", launcher)
        self.assertIn("safeclaw_personal_panel.pyw", launcher)
        self.assertIn("SAFECLAW_PERSONAL_GUI_ENTRY_PATH", launcher)
        self.assertIn("[deploy] summary =^> 当前还没有可用的面板入口。", launcher)
        self.assertIn("[deploy] summary =^> 当前面板入口不完整，这次没法打开。", launcher)
        self.assertIn("[deploy] next =^> 先重新部署当前版本，再重试。", launcher)

    def test_build_panel_ps1_launcher_resolves_current_release_snapshot(self) -> None:
        launcher = build_panel_ps1_launcher()
        self.assertIn("current_release.txt", launcher)
        self.assertIn("safeclaw_personal_panel.pyw", launcher)
        self.assertIn("SAFECLAW_PERSONAL_GUI_ENTRY_PATH", launcher)
        self.assertIn("[deploy] summary => 当前还没有可用的面板入口。", launcher)
        self.assertIn("[deploy] empty current release pointer => $currentReleaseFile", launcher)
        self.assertIn("[deploy] summary => 当前面板入口不完整，这次没法打开。", launcher)

    def test_pick_rollback_release_returns_previous_release(self) -> None:
        releases = [
            {"id": "release-one"},
            {"id": "release-two"},
            {"id": "release-three"},
        ]
        self.assertEqual(pick_rollback_release(releases, "release-three"), "release-two")
        self.assertEqual(pick_rollback_release(releases, "release-one"), None)

    def test_build_deploy_copy_ignore_names_skips_build_artifacts(self) -> None:
        ignored_names = build_deploy_copy_ignore_names(
            ["src", "tests", "target", "__pycache__", ".pytest_cache", "Cargo.toml"]
        )
        self.assertEqual(ignored_names, {"target", "__pycache__", ".pytest_cache"})


if __name__ == "__main__":
    unittest.main()
