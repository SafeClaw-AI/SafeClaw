from __future__ import annotations

from pathlib import Path
from typing import Any


_LABEL = "mvp-wrapper-service-demo"
_RESOLVED_GOVERNANCE = (
    "[demo] service governance resolved => total=2 resolved=2 confirmation=0 manual_review=0"
)
_CONFIRMATION_GOVERNANCE = (
    "[demo] service governance confirmation => total=1 resolved=0 confirmation=1 manual_review=0"
)


def _py_command(python_executable: str, *args: str) -> list[str]:
    return [python_executable, "tools/mvp/safeclaw_mvp.py", *args]


def append_wrapper_service_demo_text_errors(
    errors: list[str],
    *,
    repo_root: Path,
    python_executable: str,
    subprocess_module: Any,
) -> None:
    wrapper_service_demo = subprocess_module.run(
        _py_command(python_executable, "service-demo"),
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    output = (wrapper_service_demo.stdout or "") + (wrapper_service_demo.stderr or "")

    if wrapper_service_demo.returncode != 0:
        errors.append(f"{_LABEL} 执行失败: exit={wrapper_service_demo.returncode}")
        return
    if _RESOLVED_GOVERNANCE not in output:
        errors.append("mvp-wrapper-service-demo 输出缺少 resolved governance")
        return
    if _CONFIRMATION_GOVERNANCE not in output:
        errors.append("mvp-wrapper-service-demo 输出缺少 confirmation governance")
