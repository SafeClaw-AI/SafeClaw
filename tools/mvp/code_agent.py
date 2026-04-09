from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.mvp.code_agent_guard import (
    CodeAgentGuardSnapshot,
    build_code_agent_guard_snapshot,
)

ACTION_NAME = "code-agent"
SCHEMA_VERSION = "code-agent.v1"
SUPPORTED_GIT_ACTIONS = ("none", "status")


def normalize_git_action(git_action: str) -> str:
    normalized = git_action.strip().lower()
    if normalized in SUPPORTED_GIT_ACTIONS:
        return normalized
    raise ValueError(f"unsupported git action: {git_action}")


def render_git_snapshot(snapshot: CodeAgentGuardSnapshot) -> dict[str, object]:
    return {
        "git_available": snapshot.git.git_available,
        "is_git_repo": snapshot.git.is_git_repo,
        "branch": snapshot.git.branch,
        "remote_names": list(snapshot.git.remote_names),
        "dirty_paths": list(snapshot.git.dirty_paths),
        "status_error": snapshot.git.status_error,
    }


def decide_code_agent_request(
    snapshot: CodeAgentGuardSnapshot,
    *,
    allow_dirty_worktree: bool,
) -> tuple[bool, str]:
    if not snapshot.target_files:
        return False, "missing_target_files"
    if not snapshot.git.git_available:
        return False, "git_unavailable"
    if not snapshot.git.is_git_repo:
        return False, "not_git_repo"
    if snapshot.requires_write and snapshot.git.dirty_paths and not allow_dirty_worktree:
        return False, "dirty_worktree_requires_explicit_allow"
    return True, "allowed"


def build_code_agent_result(
    target_files: Sequence[str | Path],
    *,
    git_action: str = "none",
    allow_dirty_worktree: bool = False,
    repo_root: Path = REPO_ROOT,
) -> dict[str, object]:
    normalized_git_action = normalize_git_action(git_action)
    snapshot = build_code_agent_guard_snapshot(target_files, repo_root=repo_root)
    allowed, decision = decide_code_agent_request(
        snapshot,
        allow_dirty_worktree=allow_dirty_worktree,
    )
    return {
        "allowed": allowed,
        "decision": decision,
        "repo_root": str(snapshot.repo_root),
        "target_files": [str(path) for path in snapshot.target_files],
        "target_scopes": list(snapshot.target_scopes),
        "requires_write": snapshot.requires_write,
        "git_action": normalized_git_action,
        "allow_dirty_worktree": allow_dirty_worktree,
        "git": render_git_snapshot(snapshot),
    }


def emit_json_result(result: object, *, exit_code: int) -> int:
    payload = {
        "ok": exit_code == 0,
        "action": ACTION_NAME,
        "schema_version": SCHEMA_VERSION,
        "result": result,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return exit_code


def emit_json_error(
    *,
    message: str,
    exit_code: int,
    code: str,
    reason: str,
    details: object,
) -> int:
    payload = {
        "ok": False,
        "action": ACTION_NAME,
        "schema_version": SCHEMA_VERSION,
        "error": {
            "message": message,
            "exit_code": exit_code,
            "code": code,
            "reason": reason,
            "details": details,
        },
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return exit_code


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fail-closed preflight for future code-agent file/git actions."
    )
    parser.add_argument(
        "--target-file",
        action="append",
        default=[],
        help="Repo-contained file path that the code agent intends to touch. Repeatable.",
    )
    parser.add_argument(
        "--git-action",
        default="none",
        help="Requested git action. Supported values: none, status.",
    )
    parser.add_argument(
        "--allow-dirty-worktree",
        action="store_true",
        help="Explicitly allow preflight to continue when git status is dirty.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        normalize_git_action(args.git_action)
    except ValueError:
        return emit_json_error(
            message="unsupported git action",
            exit_code=2,
            code="unsupported_git_action",
            reason="git_action_not_allowed",
            details={
                "git_action": args.git_action,
                "supported_git_actions": list(SUPPORTED_GIT_ACTIONS),
            },
        )

    try:
        result = build_code_agent_result(
            args.target_file,
            git_action=args.git_action,
            allow_dirty_worktree=args.allow_dirty_worktree,
        )
    except ValueError as error:
        return emit_json_error(
            message="invalid target file",
            exit_code=2,
            code="invalid_target_file",
            reason="target_file_outside_repo",
            details={
                "target_files": list(args.target_file),
                "error": str(error),
            },
        )

    exit_code = 0 if bool(result.get("allowed")) else 1
    return emit_json_result(result, exit_code=exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
