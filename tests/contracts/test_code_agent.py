from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tools.mvp import code_agent
from tools.mvp import code_agent_guard


class CodeAgentTest(unittest.TestCase):
    def build_guard_snapshot(
        self,
        *,
        target_files: tuple[Path, ...],
        target_scopes: tuple[str, ...],
        requires_write: bool = True,
        git_available: bool = True,
        is_git_repo: bool = True,
        branch: str = "main",
        remote_names: tuple[str, ...] = ("origin",),
        dirty_paths: tuple[str, ...] = (),
        status_error: str = "",
    ) -> code_agent_guard.CodeAgentGuardSnapshot:
        return code_agent_guard.CodeAgentGuardSnapshot(
            repo_root=Path("V:/repo"),
            target_files=target_files,
            target_scopes=target_scopes,
            requires_write=requires_write,
            git=code_agent_guard.CodeAgentGitSnapshot(
                git_available=git_available,
                is_git_repo=is_git_repo,
                branch=branch,
                remote_names=remote_names,
                dirty_paths=dirty_paths,
                status_error=status_error,
            ),
        )

    def test_build_code_agent_result_allows_clean_repo_targets(self) -> None:
        snapshot = self.build_guard_snapshot(
            target_files=(Path("V:/repo/tools/mvp/code_agent.py"),),
            target_scopes=("scope:tools/mvp/code_agent.py",),
        )
        with patch(
            "tools.mvp.code_agent.build_code_agent_guard_snapshot",
            return_value=snapshot,
        ):
            result = code_agent.build_code_agent_result(
                ["tools/mvp/code_agent.py"],
                git_action="status",
            )
        self.assertTrue(result["allowed"])
        self.assertEqual(result["decision"], "allowed")
        self.assertEqual(result["git_action"], "status")
        self.assertEqual(
            result["target_files"],
            ["V:\\repo\\tools\\mvp\\code_agent.py"],
        )
        self.assertEqual(result["target_scopes"], ["scope:tools/mvp/code_agent.py"])

    def test_build_code_agent_result_denies_missing_target_files(self) -> None:
        snapshot = self.build_guard_snapshot(
            target_files=(),
            target_scopes=(),
            requires_write=False,
        )
        with patch(
            "tools.mvp.code_agent.build_code_agent_guard_snapshot",
            return_value=snapshot,
        ):
            result = code_agent.build_code_agent_result([], git_action="none")
        self.assertFalse(result["allowed"])
        self.assertEqual(result["decision"], "missing_target_files")
        self.assertEqual(result["git_action"], "none")

    def test_build_code_agent_result_denies_non_git_repo(self) -> None:
        snapshot = self.build_guard_snapshot(
            target_files=(Path("V:/repo/tools/mvp/code_agent.py"),),
            target_scopes=("scope:tools/mvp/code_agent.py",),
            is_git_repo=False,
            remote_names=(),
            status_error="fatal: not a git repository",
        )
        with patch(
            "tools.mvp.code_agent.build_code_agent_guard_snapshot",
            return_value=snapshot,
        ):
            result = code_agent.build_code_agent_result(
                ["tools/mvp/code_agent.py"],
                git_action="none",
            )
        self.assertFalse(result["allowed"])
        self.assertEqual(result["decision"], "not_git_repo")
        self.assertEqual(result["git"]["status_error"], "fatal: not a git repository")

    def test_build_code_agent_result_denies_dirty_worktree_without_opt_in(self) -> None:
        snapshot = self.build_guard_snapshot(
            target_files=(Path("V:/repo/tools/mvp/code_agent.py"),),
            target_scopes=("scope:tools/mvp/code_agent.py",),
            dirty_paths=("tools/mvp/code_agent.py",),
        )
        with patch(
            "tools.mvp.code_agent.build_code_agent_guard_snapshot",
            return_value=snapshot,
        ):
            result = code_agent.build_code_agent_result(
                ["tools/mvp/code_agent.py"],
                git_action="status",
                allow_dirty_worktree=False,
            )
        self.assertFalse(result["allowed"])
        self.assertEqual(result["decision"], "dirty_worktree_requires_explicit_allow")

    def test_build_code_agent_result_allows_dirty_worktree_with_opt_in(self) -> None:
        snapshot = self.build_guard_snapshot(
            target_files=(Path("V:/repo/tools/mvp/code_agent.py"),),
            target_scopes=("scope:tools/mvp/code_agent.py",),
            dirty_paths=("tools/mvp/code_agent.py",),
        )
        with patch(
            "tools.mvp.code_agent.build_code_agent_guard_snapshot",
            return_value=snapshot,
        ):
            result = code_agent.build_code_agent_result(
                ["tools/mvp/code_agent.py"],
                git_action="status",
                allow_dirty_worktree=True,
            )
        self.assertTrue(result["allowed"])
        self.assertEqual(result["decision"], "allowed")

    def test_main_renders_json_error_for_unsupported_git_action(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = code_agent.main(
                [
                    "--target-file",
                    "tools/mvp/code_agent.py",
                    "--git-action",
                    "commit",
                ]
            )
        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["action"], "code-agent")
        self.assertEqual(payload["schema_version"], "code-agent.v1")
        self.assertEqual(payload["error"]["code"], "unsupported_git_action")
        self.assertEqual(payload["error"]["reason"], "git_action_not_allowed")
        self.assertEqual(payload["error"]["details"]["git_action"], "commit")

    def test_main_renders_json_result_for_denied_preflight(self) -> None:
        snapshot = self.build_guard_snapshot(
            target_files=(Path("V:/repo/tools/mvp/code_agent.py"),),
            target_scopes=("scope:tools/mvp/code_agent.py",),
            dirty_paths=("tools/mvp/code_agent.py",),
        )
        stdout = io.StringIO()
        with patch(
            "tools.mvp.code_agent.build_code_agent_guard_snapshot",
            return_value=snapshot,
        ):
            with redirect_stdout(stdout):
                exit_code = code_agent.main(
                    [
                        "--target-file",
                        "tools/mvp/code_agent.py",
                        "--git-action",
                        "status",
                    ]
                )
        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["result"]["decision"], "dirty_worktree_requires_explicit_allow")
        self.assertFalse(payload["result"]["allowed"])


if __name__ == "__main__":
    unittest.main()
