from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CodegenArtifactContext:
    repo_root: Path


def append_codegen_artifact_errors(
    errors: list[str],
    *,
    repo_root: Path,
) -> None:
    ctx = CodegenArtifactContext(repo_root=repo_root)
    root_index = ctx.repo_root / "generated" / "index.json"
    if not root_index.exists():
        errors.append(
            f"缺少 codegen 产物: {root_index.relative_to(ctx.repo_root).as_posix()}"
        )

    for target in ("rust", "python", "ts"):
        manifest_path = ctx.repo_root / "generated" / target / "manifest.json"
        stable_ids_path = ctx.repo_root / "generated" / target / "stable_ids.json"
        if not manifest_path.exists():
            errors.append(
                f"缺少 codegen 产物: {manifest_path.relative_to(ctx.repo_root).as_posix()}"
            )
        if not stable_ids_path.exists():
            errors.append(
                f"缺少 codegen 产物: {stable_ids_path.relative_to(ctx.repo_root).as_posix()}"
            )
