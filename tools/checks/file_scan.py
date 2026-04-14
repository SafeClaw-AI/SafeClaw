from __future__ import annotations

import os
from pathlib import Path


def _is_ignored_rel_parts(rel_parts: tuple[str, ...], ignored_dir_names: set[str]) -> bool:
    return any(part in ignored_dir_names for part in rel_parts)


def _filter_dirnames(dirnames: list[str], ignored_dir_names: set[str]) -> list[str]:
    return sorted(dirname for dirname in dirnames if dirname not in ignored_dir_names)


def _iter_matching_files(
    repo_root: Path,
    current_root_path: Path,
    filenames: list[str],
    normalized_suffixes: set[str],
    ignored_dir_names: set[str],
) -> list[Path]:
    paths: list[Path] = []

    for filename in sorted(filenames):
        path = current_root_path / filename
        if path.suffix.lower() not in normalized_suffixes:
            continue
        try:
            rel_parts = path.relative_to(repo_root).parts
        except ValueError:
            continue
        if _is_ignored_rel_parts(rel_parts, ignored_dir_names):
            continue
        paths.append(path)

    return paths


def iter_repo_files(
    repo_root: Path,
    suffixes: set[str],
    ignored_dir_names: set[str],
) -> list[Path]:
    normalized_suffixes = {suffix.lower() for suffix in suffixes}
    paths: list[Path] = []

    def _handle_walk_error(error: OSError) -> None:
        if isinstance(error, FileNotFoundError):
            return
        raise error

    for current_root, dirnames, filenames in os.walk(
        repo_root,
        topdown=True,
        onerror=_handle_walk_error,
    ):
        dirnames[:] = _filter_dirnames(dirnames, ignored_dir_names)
        current_root_path = Path(current_root)
        paths.extend(
            _iter_matching_files(
                repo_root,
                current_root_path,
                filenames,
                normalized_suffixes,
                ignored_dir_names,
            )
        )

    return sorted(paths)
