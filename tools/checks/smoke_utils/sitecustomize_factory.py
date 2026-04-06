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


def write_smoke_verify_sitecustomize(directory: Path) -> Path:
    """
    为 verify 检查写入 sitecustomize.py
    Mock subprocess.run 以跳过 MVP operator flow 检查
    """
    sitecustomize_path = directory / "sitecustomize.py"
    sitecustomize_path.write_text(
        "import subprocess\n"
        "subprocess.run = lambda *args, **kwargs: subprocess.CompletedProcess("
        "args=['python', 'tools/checks/check_mvp_operator_flow.py'], "
        "returncode=0, stdout='MVP operator flow check passed.\\n', stderr='')\n",
        encoding="utf-8",
    )
    return sitecustomize_path


def write_smoke_demo_sitecustomize(directory: Path) -> Path:
    """
    为 demo 检查写入 sitecustomize.py
    Mock subprocess.run 以模拟 safeclaw_mvp_entry 和 worker_service_governance_demo 的输出
    """
    sitecustomize_path = directory / "sitecustomize.py"
    sitecustomize_path.write_text(
        "from __future__ import annotations\n"
        "\n"
        "import subprocess\n"
        "from pathlib import Path\n"
        "\n"
        "_ORIGINAL_RUN = subprocess.run\n"
        "\n"
        "def _extract_action_args(parts: list[str]) -> list[str]:\n"
        "    if '--' in parts:\n"
        "        return parts[parts.index('--') + 1:]\n"
        "    return parts[1:]\n"
        "\n"
        "def _resolve_example_name(command: object) -> str:\n"
        "    if not isinstance(command, (list, tuple)):\n"
        "        return ''\n"
        "    parts = [str(part) for part in command]\n"
        "    if any(Path(part).name.lower().startswith('safeclaw_mvp_entry') for part in parts):\n"
        "        return 'safeclaw_mvp_entry'\n"
        "    if '--example' not in parts:\n"
        "        return ''\n"
        "    example_index = parts.index('--example') + 1\n"
        "    if example_index >= len(parts):\n"
        "        return ''\n"
        "    return parts[example_index]\n"
        "\n"
        "def _get_flag(parts: list[str], flag: str, default: str = '') -> str:\n"
        "    if flag not in parts:\n"
        "        return default\n"
        "    value_index = parts.index(flag) + 1\n"
        "    return parts[value_index] if value_index < len(parts) else default\n"
        "\n"
        "def _patched_run(command, *args, **kwargs):\n"
        "    example_name = _resolve_example_name(command)\n"
        "    if example_name not in {'safeclaw_mvp_entry', 'worker_service_governance_demo'}:\n"
        "        return _ORIGINAL_RUN(command, *args, **kwargs)\n"
        "    if example_name == 'worker_service_governance_demo':\n"
        "        stdout = (\n"
        "            '[demo] service run resolved => total=2 executed=2 parked=0 skipped=0 failed=0\\n'\n"
        "            '[demo] service governance resolved => total=2 resolved=2 confirmation=0 manual_review=0\\n'\n"
        "            '[demo] service governance resolved tasks => task-worker-service-governance-a,task-worker-service-governance-b\\n'\n"
        "            '[demo] snapshot after-resolved => total=2 active=0 parked=0 completed=2\\n'\n"
        "            '[demo] service run confirmation => total=1 executed=1 parked=0 skipped=0 failed=0\\n'\n"
        "            '[demo] service governance confirmation => total=1 resolved=0 confirmation=1 manual_review=0\\n'\n"
        "            '[demo] service governance confirmation tasks => task-worker-service-governance-confirmation\\n'\n"
        "            '[demo] snapshot after-confirmation => total=3 active=0 parked=0 completed=3\\n'\n"
        "            '[demo] db: target\\\\mvp\\\\worker-service-governance-demo.db\\n'\n"
        "        )\n"
        "        return subprocess.CompletedProcess(args=command, returncode=0, stdout=stdout, stderr='')\n"
        "    parts = [str(part) for part in command]\n"
        "    action_args = _extract_action_args(parts)\n"
        "    action = action_args[0] if action_args else 'unknown'\n"
        "    task_id = _get_flag(action_args, '--task-id', 'task-demo')\n"
        "    effect_id = _get_flag(action_args, '--effect-id', f'effect-{task_id}')\n"
        "    db_path = _get_flag(action_args, '--db', 'target\\\\mvp\\\\session.db')\n"
        "    output_path = _get_flag(action_args, '--output', 'target\\\\mvp\\\\session.txt')\n"
        "    stdout = ''\n"
        "    if action == 'report':\n"
        "        stdout = f'[mvp] report target => task={task_id} effect={effect_id}\\n'\n"
        "    if action.startswith('seed-'):\n"
        "        stdout = f'[mvp] seed target => task={task_id} db={db_path} output={output_path}\\n'\n"
        "    return subprocess.CompletedProcess(args=command, returncode=0, stdout=stdout, stderr='')\n"
        "\n"
        "subprocess.run = _patched_run\n",
        encoding="utf-8",
    )
    return sitecustomize_path


def write_smoke_report_sitecustomize(directory: Path) -> Path:
    """
    为 report 检查写入 sitecustomize.py
    Mock subprocess.run 以模拟 report 命令的输出
    """
    sitecustomize_path = directory / "sitecustomize.py"
    sitecustomize_path.write_text(
        "from __future__ import annotations\n"
        "\n"
        "import subprocess\n"
        "from pathlib import Path\n"
        "\n"
        f"_REPORT_FACTS = {SMOKE_WRAPPER_REPORT_STUB_TASK_OUTPUTS!r}\n"
        "_ORIGINAL_RUN = subprocess.run\n"
        "\n"
        "def _extract_action_args(parts: list[str]) -> list[str]:\n"
        "    if '--' in parts:\n"
        "        return parts[parts.index('--') + 1:]\n"
        "    if parts and Path(parts[0]).name.lower().startswith('safeclaw_mvp_entry'):\n"
        "        return parts[1:]\n"
        "    return []\n"
        "\n"
        "def _resolve_example_name(command: object) -> str:\n"
        "    if not isinstance(command, (list, tuple)):\n"
        "        return ''\n"
        "    parts = [str(part) for part in command]\n"
        "    if any(Path(part).name.lower().startswith('safeclaw_mvp_entry') for part in parts):\n"
        "        return 'safeclaw_mvp_entry'\n"
        "    if '--example' not in parts:\n"
        "        return ''\n"
        "    example_index = parts.index('--example') + 1\n"
        "    if example_index >= len(parts):\n"
        "        return ''\n"
        "    return parts[example_index]\n"
        "\n"
        "def _get_flag(parts: list[str], flag: str) -> str:\n"
        "    if flag not in parts:\n"
        "        return ''\n"
        "    value_index = parts.index(flag) + 1\n"
        "    return parts[value_index] if value_index < len(parts) else ''\n"
        "\n"
        "def _patched_run(command, *args, **kwargs):\n"
        "    example_name = _resolve_example_name(command)\n"
        "    if example_name != 'safeclaw_mvp_entry':\n"
        "        return _ORIGINAL_RUN(command, *args, **kwargs)\n"
        "    parts = [str(part) for part in command]\n"
        "    action_args = _extract_action_args(parts)\n"
        "    if not action_args or action_args[0] != 'report':\n"
        "        return _ORIGINAL_RUN(command, *args, **kwargs)\n"
        "    task_id = _get_flag(action_args, '--task-id')\n"
        "    if task_id not in _REPORT_FACTS:\n"
        "        return _ORIGINAL_RUN(command, *args, **kwargs)\n"
        "    summary_token, worker_state, effect_state = _REPORT_FACTS[task_id]\n"
        "    stdout_lines = [f'[mvp] report target => task={task_id} effect=effect-{task_id}']\n"
        "    if summary_token:\n"
        "        stdout_lines.append(\n"
        "            f'[mvp] report summary => {summary_token} worker={worker_state} effect={effect_state}'\n"
        "        )\n"
        "    stdout = '\\n'.join(stdout_lines) + '\\n'\n"
        "    return subprocess.CompletedProcess(args=command, returncode=0, stdout=stdout, stderr='')\n"
        "\n"
        "subprocess.run = _patched_run\n",
        encoding="utf-8",
    )
    return sitecustomize_path
