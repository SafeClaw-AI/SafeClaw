from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class CodeAgentGitSnapshot:
    git_available: bool
    is_git_repo: bool
    branch: str
    remote_names: tuple[str, ...]
    dirty_paths: tuple[str, ...]
    status_error: str


@dataclass(frozen=True)
class CodeAgentGuardSnapshot:
    repo_root: Path
    target_files: tuple[Path, ...]
    target_scopes: tuple[str, ...]
    requires_write: bool
    git: CodeAgentGitSnapshot


def normalize_relpath(relpath: str) -> str:
    normalized = relpath.strip()
    if normalized.startswith('"') and normalized.endswith('"'):
        normalized = normalized[1:-1]
    return normalized.replace("\\", "/")


def parse_status_line(line: str) -> tuple[str, str]:
    status = line[:2].strip() or line[:2]
    relpath = line[3:].strip()
    if " -> " in relpath:
        relpath = relpath.split(" -> ", 1)[1]
    return status, normalize_relpath(relpath)


def build_scope_value(value: str) -> str:
    normalized = value.strip().replace("\\", "/")
    if not normalized:
        return ""
    if normalized.startswith("scope:"):
        return normalized
    return f"scope:{normalized}"


def resolve_target_file(target_file: str | Path, repo_root: Path = REPO_ROOT) -> Path:
    candidate = Path(target_file)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    resolved_repo_root = repo_root.resolve()
    resolved_candidate = candidate.resolve(strict=False)
    try:
        resolved_candidate.relative_to(resolved_repo_root)
    except ValueError as error:
        raise ValueError(f"target file escapes repo root: {candidate}") from error
    return resolved_candidate


def normalize_target_files(
    target_files: Sequence[str | Path],
    repo_root: Path = REPO_ROOT,
) -> tuple[Path, ...]:
    resolved_files: list[Path] = []
    seen: set[str] = set()
    for target_file in target_files:
        resolved_target = resolve_target_file(target_file, repo_root=repo_root)
        key = str(resolved_target).lower()
        if key in seen:
            continue
        seen.add(key)
        resolved_files.append(resolved_target)
    return tuple(resolved_files)


def build_target_scopes(
    target_files: Sequence[Path],
    repo_root: Path = REPO_ROOT,
) -> tuple[str, ...]:
    resolved_repo_root = repo_root.resolve()
    scopes: list[str] = []
    for target_file in target_files:
        relative_path = target_file.resolve(strict=False).relative_to(resolved_repo_root).as_posix()
        scopes.append(build_scope_value(relative_path))
    return tuple(scopes)


def run_git_command(arguments: Sequence[str], repo_root: Path = REPO_ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def completed_output_text(completed: subprocess.CompletedProcess[str]) -> str:
    return (completed.stdout or completed.stderr or "").strip()


def build_git_unavailable_snapshot(status_error: str) -> CodeAgentGitSnapshot:
    return CodeAgentGitSnapshot(
        git_available=False,
        is_git_repo=False,
        branch="",
        remote_names=(),
        dirty_paths=(),
        status_error=status_error,
    )


def build_not_git_repo_snapshot(status_error: str) -> CodeAgentGitSnapshot:
    return CodeAgentGitSnapshot(
        git_available=True,
        is_git_repo=False,
        branch="",
        remote_names=(),
        dirty_paths=(),
        status_error=status_error,
    )


def repo_check_allows_git_snapshot(repo_check: subprocess.CompletedProcess[str]) -> bool:
    return repo_check.returncode == 0 and completed_output_text(repo_check).lower() == "true"


def collect_dirty_paths(status_result: subprocess.CompletedProcess[str]) -> tuple[str, ...]:
    return tuple(
        parse_status_line(line)[1]
        for line in status_result.stdout.splitlines()
        if line.strip()
    )


def collect_remote_names(remote_result: subprocess.CompletedProcess[str]) -> tuple[str, ...]:
    return tuple(
        line.strip()
        for line in remote_result.stdout.splitlines()
        if line.strip()
    )


def collect_git_command_errors(results: Sequence[subprocess.CompletedProcess[str]]) -> str:
    errors = [completed_output_text(result) for result in results if result.returncode != 0]
    return "; ".join(error for error in errors if error)


def build_git_repo_snapshot(
    branch_result: subprocess.CompletedProcess[str],
    remote_result: subprocess.CompletedProcess[str],
    status_result: subprocess.CompletedProcess[str],
) -> CodeAgentGitSnapshot:
    return CodeAgentGitSnapshot(
        git_available=True,
        is_git_repo=True,
        branch=(branch_result.stdout or "").strip(),
        remote_names=collect_remote_names(remote_result),
        dirty_paths=collect_dirty_paths(status_result),
        status_error=collect_git_command_errors((branch_result, remote_result, status_result)),
    )


def collect_code_agent_git_snapshot(repo_root: Path = REPO_ROOT) -> CodeAgentGitSnapshot:
    try:
        repo_check = run_git_command(["rev-parse", "--is-inside-work-tree"], repo_root=repo_root)
    except FileNotFoundError as error:
        return build_git_unavailable_snapshot(str(error).strip())

    if not repo_check_allows_git_snapshot(repo_check):
        return build_not_git_repo_snapshot(completed_output_text(repo_check))

    branch_result = run_git_command(["branch", "--show-current"], repo_root=repo_root)
    remote_result = run_git_command(["remote"], repo_root=repo_root)
    status_result = run_git_command(
        ["-c", "core.quotepath=false", "status", "--short"],
        repo_root=repo_root,
    )
    return build_git_repo_snapshot(branch_result, remote_result, status_result)


def build_code_agent_guard_snapshot(
    target_files: Sequence[str | Path],
    repo_root: Path = REPO_ROOT,
) -> CodeAgentGuardSnapshot:
    normalized_target_files = normalize_target_files(target_files, repo_root=repo_root)
    return CodeAgentGuardSnapshot(
        repo_root=repo_root.resolve(),
        target_files=normalized_target_files,
        target_scopes=build_target_scopes(normalized_target_files, repo_root=repo_root),
        requires_write=bool(normalized_target_files),
        git=collect_code_agent_git_snapshot(repo_root=repo_root),
    )


def render_code_agent_guard_snapshot(snapshot: CodeAgentGuardSnapshot) -> str:
    payload = {
        "repo_root": str(snapshot.repo_root),
        "target_files": [str(path) for path in snapshot.target_files],
        "target_scopes": list(snapshot.target_scopes),
        "requires_write": snapshot.requires_write,
        "git": {
            "git_available": snapshot.git.git_available,
            "is_git_repo": snapshot.git.is_git_repo,
            "branch": snapshot.git.branch,
            "remote_names": list(snapshot.git.remote_names),
            "dirty_paths": list(snapshot.git.dirty_paths),
            "status_error": snapshot.git.status_error,
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a minimal file/git/write-lock guard snapshot for future code-agent work."
    )
    parser.add_argument(
        "--target-file",
        action="append",
        default=[],
        help="Repo-contained file path that the future code agent intends to touch. Repeatable.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    snapshot = build_code_agent_guard_snapshot(args.target_file)
    print(render_code_agent_guard_snapshot(snapshot))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
