"""Factory functions for generating sitecustomize.py files for smoke tests."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from smoke_utils.constants import (
    SMOKE_DEMO_STUB_ACTIONS,
    SMOKE_DEMO_STUB_TASK_IDS,
    SMOKE_WRAPPER_SERVICE_STUB_ACTIONS,
    SMOKE_WRAPPER_SERVICE_STUB_TASK_IDS,
    SMOKE_WRAPPER_SERVICE_REPORT_STUB_ACTIONS,
    SMOKE_WRAPPER_SERVICE_REPORT_STUB_TASK_IDS,
    SMOKE_ROOT_PS1_SERVICE_REPORT_STUB_ACTIONS,
    SMOKE_ROOT_PS1_SERVICE_REPORT_STUB_TASK_IDS,
    SMOKE_WRAPPER_REPORT_STUB_TASK_OUTPUTS,
)

# Global list to track temporary directories
_SMOKE_TEMP_DIRS: list[tempfile.TemporaryDirectory[str]] = []


def get_smoke_command_flag(command_parts: list[str], flag: str) -> str | None:
    """Extract flag value from command parts."""
    if flag not in command_parts:
        return None
    index = command_parts.index(flag) + 1
    if index >= len(command_parts):
        return None
    return command_parts[index]


def should_use_smoke_demo_sitecustomize(command: object) -> bool:
    """Check if command should use demo sitecustomize."""
    if not isinstance(command, (list, tuple)):
        return False
    command_parts = [str(part) for part in command]
    if len(command_parts) < 3:
        return False
    script_path = command_parts[1].replace("\\", "/")
    if not script_path.endswith("tools/mvp/safeclaw_mvp.py"):
        return False
    if command_parts[2] not in SMOKE_DEMO_STUB_ACTIONS:
        return False
    if "--bogus" in command_parts:
        return False
    if command_parts[2] == "service-demo":
        return True
    task_id = get_smoke_command_flag(command_parts, "--task-id")
    return task_id in SMOKE_DEMO_STUB_TASK_IDS


def should_use_smoke_wrapper_service_sitecustomize(command: object) -> bool:
    """Check if command should use wrapper service sitecustomize."""
    if not isinstance(command, (list, tuple)):
        return False
    command_parts = [str(part) for part in command]
    if len(command_parts) < 4:
        return False
    if "--bogus" in command_parts:
        return False
    lower_parts = [part.lower() for part in command_parts]
    script_path = ""
    action_index = -1
    if lower_parts[0] in {"cmd", "cmd.exe"} and lower_parts[1] == "/c":
        script_path = command_parts[2].replace("\\", "/")
        action_index = 3
    elif (
        lower_parts[0] in {"powershell", "powershell.exe", "pwsh", "pwsh.exe"}
        and "-file" in lower_parts
    ):
        file_index = lower_parts.index("-file")
        if file_index + 2 >= len(command_parts):
            return False
        script_path = command_parts[file_index + 1].replace("\\", "/")
        action_index = file_index + 2
    else:
        return False
    if script_path not in {"tools/mvp/safeclaw_mvp.cmd", "tools/mvp/safeclaw_mvp.ps1"}:
        return False
    if action_index >= len(command_parts):
        return False
    action = command_parts[action_index]
    if action not in SMOKE_WRAPPER_SERVICE_STUB_ACTIONS:
        return False
    if action == "service-demo":
        return True
    task_id = get_smoke_command_flag(command_parts, "--task-id")
    return task_id in SMOKE_WRAPPER_SERVICE_STUB_TASK_IDS


def should_use_smoke_wrapper_report_sitecustomize(command: object) -> bool:
    """Check if command should use wrapper report sitecustomize."""
    if not isinstance(command, (list, tuple)):
        return False
    command_parts = [str(part) for part in command]
    if len(command_parts) < 7:
        return False
    if "--bogus" in command_parts or "--json" not in command_parts:
        return False
    lower_parts = [part.lower() for part in command_parts]
    if lower_parts[0] not in {"powershell", "powershell.exe", "pwsh", "pwsh.exe"}:
        return False
    if "-file" not in lower_parts:
        return False
    file_index = lower_parts.index("-file")
    if file_index + 2 >= len(command_parts):
        return False
    script_path = command_parts[file_index + 1].replace("\\", "/")
    if script_path != "tools/mvp/safeclaw_mvp.ps1":
        return False
    if command_parts[file_index + 2] != "report":
        return False
    db_path = get_smoke_command_flag(command_parts, "--db")
    task_id = get_smoke_command_flag(command_parts, "--task-id")
    return db_path is not None and task_id in SMOKE_WRAPPER_REPORT_STUB_TASK_OUTPUTS


def should_use_smoke_wrapper_service_report_sitecustomize(command: object) -> bool:
    """Check if command should use wrapper service report sitecustomize."""
    if not isinstance(command, (list, tuple)):
        return False
    command_parts = [str(part) for part in command]
    if len(command_parts) < 9:
        return False
    if (
        "--bogus" in command_parts
        or "--json" not in command_parts
        or "--report" not in command_parts
    ):
        return False
    lower_parts = [part.lower() for part in command_parts]
    if lower_parts[0] not in {"powershell", "powershell.exe", "pwsh", "pwsh.exe"}:
        return False
    if "-file" not in lower_parts:
        return False
    file_index = lower_parts.index("-file")
    if file_index + 2 >= len(command_parts):
        return False
    script_path = command_parts[file_index + 1].replace("\\", "/")
    if script_path != "tools/mvp/safeclaw_mvp.ps1":
        return False
    action = command_parts[file_index + 2]
    if action not in SMOKE_WRAPPER_SERVICE_REPORT_STUB_ACTIONS:
        return False
    db_path = get_smoke_command_flag(command_parts, "--db")
    task_id = get_smoke_command_flag(command_parts, "--task-id")
    return (
        db_path is not None and task_id in SMOKE_WRAPPER_SERVICE_REPORT_STUB_TASK_IDS
    )


def should_use_smoke_root_ps1_service_report_sitecustomize(command: object) -> bool:
    """Check if command should use root ps1 service report sitecustomize."""
    if not isinstance(command, (list, tuple)):
        return False
    command_parts = [str(part) for part in command]
    if len(command_parts) < 9:
        return False
    if (
        "--bogus" in command_parts
        or "--json" not in command_parts
        or "--report" not in command_parts
        or "--preflight" in command_parts
    ):
        return False
    lower_parts = [part.lower() for part in command_parts]
    if lower_parts[0] not in {"powershell", "powershell.exe", "pwsh", "pwsh.exe"}:
        return False
    if "-file" not in lower_parts:
        return False
    file_index = lower_parts.index("-file")
    if file_index + 2 >= len(command_parts):
        return False
    script_path = command_parts[file_index + 1].replace("\\", "/")
    if script_path != "safeclaw.ps1":
        return False
    action = command_parts[file_index + 2]
    if action not in SMOKE_ROOT_PS1_SERVICE_REPORT_STUB_ACTIONS:
        return False
    task_id = get_smoke_command_flag(command_parts, "--task-id")
    return task_id in SMOKE_ROOT_PS1_SERVICE_REPORT_STUB_TASK_IDS


def build_smoke_pythonpath_env(
    base_env: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build environment with PYTHONPATH pointing to demo sitecustomize."""
    temp_dir = tempfile.TemporaryDirectory()
    _SMOKE_TEMP_DIRS.append(temp_dir)
    temp_path = Path(temp_dir.name)
    write_smoke_demo_sitecustomize(temp_path)

    env = os.environ.copy() if base_env is None else dict(base_env)
    existing = env.get("PYTHONPATH") or ""
    env["PYTHONPATH"] = (
        str(temp_path) if not existing else f"{temp_path}{os.pathsep}{existing}"
    )
    return env


def build_smoke_report_pythonpath_env(
    base_env: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build environment with PYTHONPATH pointing to report sitecustomize."""
    temp_dir = tempfile.TemporaryDirectory()
    _SMOKE_TEMP_DIRS.append(temp_dir)
    temp_path = Path(temp_dir.name)
    write_smoke_report_sitecustomize(temp_path)

    env = os.environ.copy() if base_env is None else dict(base_env)
    existing = env.get("PYTHONPATH") or ""
    env["PYTHONPATH"] = (
        str(temp_path) if not existing else f"{temp_path}{os.pathsep}{existing}"
    )
    return env


def write_smoke_demo_sitecustomize(directory: Path) -> Path:
    """Write demo sitecustomize.py - placeholder for now."""
    sitecustomize_path = directory / "sitecustomize.py"
    sitecustomize_path.write_text("# Demo sitecustomize - to be implemented\n", encoding="utf-8")
    return sitecustomize_path


def write_smoke_report_sitecustomize(directory: Path) -> Path:
    """Write report sitecustomize.py - placeholder for now."""
    sitecustomize_path = directory / "sitecustomize.py"
    sitecustomize_path.write_text("# Report sitecustomize - to be implemented\n", encoding="utf-8")
    return sitecustomize_path
