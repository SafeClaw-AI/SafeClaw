from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.mvp import code_agent_guard


class CodeAgentGuardTest(unittest.TestCase):
    def test_normalize_target_files_deduplicates_repo_relative_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            target_files = code_agent_guard.normalize_target_files(
                [
                    "tools/mvp/code_agent_guard.py",
                    repo_root / "tools" / "mvp" / "code_agent_guard.py",
                ],
                repo_root=repo_root,
            )
        self.assertEqual(len(target_files), 1)
        self.assertEqual(
            target_files[0],
            (repo_root / "tools" / "mvp" / "code_agent_guard.py").resolve(),
        )

    def test_normalize_target_files_rejects_escape_from_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            escaped = repo_root.parent / "outside.py"
            with self.assertRaisesRegex(ValueError, "target file escapes repo root"):
                code_agent_guard.normalize_target_files([escaped], repo_root=repo_root)

    def test_build_target_scopes_uses_scope_prefix_and_repo_relative_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            target_files = (
                repo_root / "tools" / "mvp" / "code_agent_guard.py",
                repo_root / "tests" / "contracts" / "test_code_agent_guard.py",
            )
            scopes = code_agent_guard.build_target_scopes(target_files, repo_root=repo_root)
        self.assertEqual(
            scopes,
            (
                "scope:tools/mvp/code_agent_guard.py",
                "scope:tests/contracts/test_code_agent_guard.py",
            ),
        )

    def test_collect_code_agent_git_snapshot_parses_branch_remote_and_dirty_paths(self) -> None:
        with patch(
            "tools.mvp.code_agent_guard.run_git_command",
            side_effect=[
                subprocess.CompletedProcess(
                    args=["git", "rev-parse", "--is-inside-work-tree"],
                    returncode=0,
                    stdout="true\n",
                    stderr="",
                ),
                subprocess.CompletedProcess(
                    args=["git", "branch", "--show-current"],
                    returncode=0,
                    stdout="main\n",
                    stderr="",
                ),
                subprocess.CompletedProcess(
                    args=["git", "remote"],
                    returncode=0,
                    stdout="origin\nupstream\n",
                    stderr="",
                ),
                subprocess.CompletedProcess(
                    args=["git", "status", "--short"],
                    returncode=0,
                    stdout=(
                        " M tools/mvp/code_agent_guard.py\n"
                        "?? tests/contracts/test_code_agent_guard.py\n"
                    ),
                    stderr="",
                ),
            ],
        ):
            snapshot = code_agent_guard.collect_code_agent_git_snapshot()
        self.assertTrue(snapshot.git_available)
        self.assertTrue(snapshot.is_git_repo)
        self.assertEqual(snapshot.branch, "main")
        self.assertEqual(snapshot.remote_names, ("origin", "upstream"))
        self.assertEqual(
            snapshot.dirty_paths,
            (
                "tools/mvp/code_agent_guard.py",
                "tests/contracts/test_code_agent_guard.py",
            ),
        )
        self.assertEqual(snapshot.status_error, "")

    def test_collect_code_agent_git_snapshot_handles_non_git_repo(self) -> None:
        with patch(
            "tools.mvp.code_agent_guard.run_git_command",
            return_value=subprocess.CompletedProcess(
                args=["git", "rev-parse", "--is-inside-work-tree"],
                returncode=128,
                stdout="",
                stderr="fatal: not a git repository",
            ),
        ):
            snapshot = code_agent_guard.collect_code_agent_git_snapshot()
        self.assertTrue(snapshot.git_available)
        self.assertFalse(snapshot.is_git_repo)
        self.assertEqual(snapshot.remote_names, ())
        self.assertEqual(snapshot.dirty_paths, ())
        self.assertEqual(snapshot.status_error, "fatal: not a git repository")

    def test_build_code_agent_guard_snapshot_aggregates_targets_and_git(self) -> None:
        fake_git = code_agent_guard.CodeAgentGitSnapshot(
            git_available=True,
            is_git_repo=True,
            branch="main",
            remote_names=("origin",),
            dirty_paths=("tools/mvp/code_agent_guard.py",),
            status_error="",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            with patch(
                "tools.mvp.code_agent_guard.collect_code_agent_git_snapshot",
                return_value=fake_git,
            ):
                snapshot = code_agent_guard.build_code_agent_guard_snapshot(
                    [
                        "tools/mvp/code_agent_guard.py",
                        "tests/contracts/test_code_agent_guard.py",
                    ],
                    repo_root=repo_root,
                )
        self.assertTrue(snapshot.requires_write)
        self.assertEqual(snapshot.git, fake_git)
        self.assertEqual(
            snapshot.target_scopes,
            (
                "scope:tools/mvp/code_agent_guard.py",
                "scope:tests/contracts/test_code_agent_guard.py",
            ),
        )
        self.assertEqual(
            snapshot.target_files,
            (
                (repo_root / "tools" / "mvp" / "code_agent_guard.py").resolve(),
                (repo_root / "tests" / "contracts" / "test_code_agent_guard.py").resolve(),
            ),
        )


if __name__ == "__main__":
    unittest.main()
