from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_ROOT_ENV = "SAFECLAW_PERSONAL_DEPLOY_ROOT"
DEPLOY_RELEASE_ID_ENV = "SAFECLAW_PERSONAL_DEPLOY_RELEASE_ID"
DEFAULT_DEPLOY_ROOT = Path(
    os.environ.get(DEPLOY_ROOT_ENV) or (Path.home() / ".safeclaw-personal-production")
).expanduser()
RELEASES_DIR = DEFAULT_DEPLOY_ROOT / "releases"
CURRENT_RELEASE_FILE = DEFAULT_DEPLOY_ROOT / "current_release.txt"
DEPLOY_LEDGER_FILE = DEFAULT_DEPLOY_ROOT / "deployments.json"
STABLE_CMD = DEFAULT_DEPLOY_ROOT / "safeclaw-personal.cmd"
STABLE_PS1 = DEFAULT_DEPLOY_ROOT / "safeclaw-personal.ps1"
STABLE_PANEL_CMD = DEFAULT_DEPLOY_ROOT / "safeclaw-personal-panel.cmd"
STABLE_PANEL_PS1 = DEFAULT_DEPLOY_ROOT / "safeclaw-personal-panel.ps1"
DEPLOY_SNAPSHOT_PATHS = (
    Path("Cargo.toml"),
    Path("Cargo.lock"),
    Path("VERSION"),
    Path("safeclaw-core"),
    Path("safeclaw-sqlite"),
    Path("tools/mvp/safeclaw_personal_mvp.py"),
    Path("tools/mvp/safeclaw_personal_mvp.cmd"),
    Path("tools/mvp/safeclaw_personal_mvp.ps1"),
    Path("tools/mvp/safeclaw_personal_panel.py"),
    Path("tools/mvp/safeclaw_personal_panel.pyw"),
    Path("tools/mvp/PERSONAL_MVP_PLAYBOOK.md"),
)
OPTIONAL_DEPLOY_SNAPSHOT_PATHS = (
    Path("target/debug/examples/safeclaw_mvp_entry.exe"),
)
DEPLOY_IGNORED_DIRECTORY_NAMES = ("target", "__pycache__", ".pytest_cache")


def print_deploy_summary(summary_text: str) -> None:
    print(f"[deploy] summary => {summary_text}")


def print_deploy_next(next_text: str) -> None:
    print(f"[deploy] next => {next_text}")


def build_release_id() -> str:
    override = os.environ.get(DEPLOY_RELEASE_ID_ENV)
    if override:
        return override.strip()
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def ensure_deploy_dirs() -> None:
    DEFAULT_DEPLOY_ROOT.mkdir(parents=True, exist_ok=True)
    RELEASES_DIR.mkdir(parents=True, exist_ok=True)


def read_ledger() -> dict[str, list[dict[str, str]]]:
    if not DEPLOY_LEDGER_FILE.exists():
        return {"releases": []}
    payload = json.loads(DEPLOY_LEDGER_FILE.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"invalid deploy ledger: {DEPLOY_LEDGER_FILE}")
    releases = payload.get("releases")
    if not isinstance(releases, list):
        raise ValueError(f"invalid deploy ledger releases: {DEPLOY_LEDGER_FILE}")
    return {"releases": [dict(item) for item in releases]}


def write_ledger(payload: dict[str, list[dict[str, str]]]) -> None:
    DEPLOY_LEDGER_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def read_current_release() -> str | None:
    if not CURRENT_RELEASE_FILE.exists():
        return None
    value = CURRENT_RELEASE_FILE.read_text(encoding="utf-8").strip()
    return value or None


def write_current_release(release_id: str) -> None:
    CURRENT_RELEASE_FILE.write_text(f"{release_id}\n", encoding="utf-8")


def build_cmd_launcher() -> str:
    return """@echo off
setlocal
set SCRIPT_DIR=%~dp0
set CURRENT_RELEASE=
for /f \"usebackq delims=\" %%i in (\"%SCRIPT_DIR%current_release.txt\") do set CURRENT_RELEASE=%%i
if not defined CURRENT_RELEASE (
  >&2 echo [deploy] missing current release pointer: %SCRIPT_DIR%current_release.txt
  exit /b 1
)
set SAFECLAW_PERSONAL_ENTRY_COMMAND=safeclaw-personal.cmd
python -X utf8 \"%SCRIPT_DIR%releases\\%CURRENT_RELEASE%\\repo\\tools\\mvp\\safeclaw_personal_mvp.py\" %*
exit /b %ERRORLEVEL%
"""


def build_ps1_launcher() -> str:
    return """$deployRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$currentReleaseFile = Join-Path $deployRoot 'current_release.txt'
if (-not (Test-Path $currentReleaseFile)) {
    Write-Error "[deploy] missing current release pointer: $currentReleaseFile"
    exit 1
}
$currentRelease = (Get-Content -LiteralPath $currentReleaseFile -Raw).Trim()
if (-not $currentRelease) {
    Write-Error "[deploy] empty current release pointer: $currentReleaseFile"
    exit 1
}
$releaseRoot = Join-Path (Join-Path $deployRoot 'releases') $currentRelease
$repoRoot = Join-Path $releaseRoot 'repo'
$toolsRoot = Join-Path $repoRoot 'tools'
$mvpRoot = Join-Path $toolsRoot 'mvp'
$scriptPath = Join-Path $mvpRoot 'safeclaw_personal_mvp.py'
if (-not (Test-Path $scriptPath)) {
    Write-Error "[deploy] missing personal MVP launcher: $scriptPath"
    exit 1
}
$env:SAFECLAW_PERSONAL_ENTRY_COMMAND = 'safeclaw-personal.ps1'
python -X utf8 $scriptPath @args
exit $LASTEXITCODE
"""


def build_panel_cmd_launcher() -> str:
    return """@echo off
setlocal
set SCRIPT_DIR=%~dp0
set CURRENT_RELEASE=
for /f "usebackq delims=" %%i in ("%SCRIPT_DIR%current_release.txt") do set CURRENT_RELEASE=%%i
if not defined CURRENT_RELEASE (
  >&2 echo [deploy] missing current release pointer: %SCRIPT_DIR%current_release.txt
  exit /b 1
)
set PANEL_SCRIPT=%SCRIPT_DIR%releases\%CURRENT_RELEASE%\repo\tools\mvp\safeclaw_personal_panel.pyw
if not exist "%PANEL_SCRIPT%" (
  >&2 echo [deploy] missing personal panel launcher: %PANEL_SCRIPT%
  exit /b 1
)
set SAFECLAW_PERSONAL_GUI_ENTRY_PATH=%SCRIPT_DIR%safeclaw-personal.cmd
start "" pythonw -X utf8 "%PANEL_SCRIPT%"
exit /b 0
"""


def build_panel_ps1_launcher() -> str:
    return """$deployRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$currentReleaseFile = Join-Path $deployRoot 'current_release.txt'
if (-not (Test-Path $currentReleaseFile)) {
    Write-Error "[deploy] missing current release pointer: $currentReleaseFile"
    exit 1
}
$currentRelease = (Get-Content -LiteralPath $currentReleaseFile -Raw).Trim()
if (-not $currentRelease) {
    Write-Error "[deploy] empty current release pointer: $currentReleaseFile"
    exit 1
}
$releaseRoot = Join-Path (Join-Path $deployRoot 'releases') $currentRelease
$repoRoot = Join-Path $releaseRoot 'repo'
$toolsRoot = Join-Path $repoRoot 'tools'
$mvpRoot = Join-Path $toolsRoot 'mvp'
$scriptPath = Join-Path $mvpRoot 'safeclaw_personal_panel.pyw'
if (-not (Test-Path $scriptPath)) {
    Write-Error "[deploy] missing personal panel launcher: $scriptPath"
    exit 1
}
$env:SAFECLAW_PERSONAL_GUI_ENTRY_PATH = Join-Path $deployRoot 'safeclaw-personal.ps1'
Start-Process -FilePath 'pythonw' -ArgumentList @('-X', 'utf8', $scriptPath)
exit 0
"""


def write_stable_launchers() -> None:
    STABLE_CMD.write_text(build_cmd_launcher(), encoding="utf-8")
    STABLE_PS1.write_text(build_ps1_launcher(), encoding="utf-8")
    STABLE_PANEL_CMD.write_text(build_panel_cmd_launcher(), encoding="utf-8")
    STABLE_PANEL_PS1.write_text(build_panel_ps1_launcher(), encoding="utf-8")


def collect_personal_deploy_snapshot_paths() -> tuple[Path, ...]:
    snapshot_paths = list(DEPLOY_SNAPSHOT_PATHS)
    for relative_path in OPTIONAL_DEPLOY_SNAPSHOT_PATHS:
        if (REPO_ROOT / relative_path).exists():
            snapshot_paths.append(relative_path)
    return tuple(snapshot_paths)


def build_deploy_copy_ignore_names(child_names: list[str]) -> set[str]:
    return {name for name in child_names if name in DEPLOY_IGNORED_DIRECTORY_NAMES}


def copy_snapshot_path(relative_path: Path, release_repo_root: Path) -> None:
    source_path = REPO_ROOT / relative_path
    if not source_path.exists():
        raise FileNotFoundError(f"missing deploy source: {relative_path.as_posix()}")
    target_path = release_repo_root / relative_path
    if source_path.is_dir():
        shutil.copytree(
            source_path,
            target_path,
            dirs_exist_ok=True,
            ignore=lambda _current_dir, child_names: build_deploy_copy_ignore_names(child_names),
        )
        return
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target_path)


def append_release_record(release_id: str) -> None:
    payload = read_ledger()
    payload["releases"].append(
        {
            "id": release_id,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source_repo": str(REPO_ROOT),
        }
    )
    write_ledger(payload)


def pick_rollback_release(releases: list[dict[str, str]], current_release: str) -> str | None:
    release_ids = [str(item.get("id", "")).strip() for item in releases if str(item.get("id", "")).strip()]
    if current_release not in release_ids:
        return None
    current_index = release_ids.index(current_release)
    if current_index == 0:
        return None
    return release_ids[current_index - 1]


def deploy_release(_: argparse.Namespace) -> int:
    ensure_deploy_dirs()
    release_id = build_release_id()
    release_root = RELEASES_DIR / release_id
    release_repo_root = release_root / "repo"
    snapshot_paths = collect_personal_deploy_snapshot_paths()
    if release_root.exists():
        print(f"[deploy] release already exists => {release_id}")
        return 1
    for relative_path in snapshot_paths:
        copy_snapshot_path(relative_path, release_repo_root)
    (release_root / "release.json").write_text(
        json.dumps(
            {
                "id": release_id,
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "source_repo": str(REPO_ROOT),
                "snapshot_paths": [path.as_posix() for path in snapshot_paths],
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    append_release_record(release_id)
    write_current_release(release_id)
    write_stable_launchers()
    print_deploy_summary("个人生产位已经更新到新版本。")
    print(f"[deploy] root => {DEFAULT_DEPLOY_ROOT}")
    print(f"[deploy] current release => {release_id}")
    print(f"[deploy] launcher => {STABLE_CMD}")
    print(f"[deploy] panel => {STABLE_PANEL_CMD}")
    print_deploy_next(str(STABLE_PANEL_CMD))
    return 0


def rollback_release(_: argparse.Namespace) -> int:
    ensure_deploy_dirs()
    current_release = read_current_release()
    if current_release is None:
        print_deploy_summary("当前还没有可回滚的生产版本。")
        print("[deploy] no current release")
        print_deploy_next("python -X utf8 tools/mvp/safeclaw_personal_deploy.py deploy")
        return 1
    payload = read_ledger()
    rollback_release_id = pick_rollback_release(payload["releases"], current_release)
    if rollback_release_id is None:
        print_deploy_summary("当前只有一个生产版本，还没有上一版可回滚。")
        print("[deploy] no previous release to roll back to")
        print_deploy_next("python -X utf8 tools/mvp/safeclaw_personal_deploy.py status")
        return 1
    write_current_release(rollback_release_id)
    write_stable_launchers()
    print_deploy_summary("个人生产位已经切回上一版。")
    print(f"[deploy] rolled back => {rollback_release_id}")
    print(f"[deploy] launcher => {STABLE_CMD}")
    print(f"[deploy] panel => {STABLE_PANEL_CMD}")
    print_deploy_next(str(STABLE_PANEL_CMD))
    return 0


def show_status(_: argparse.Namespace) -> int:
    ensure_deploy_dirs()
    payload = read_ledger()
    current_release = read_current_release()
    if current_release is None:
        print_deploy_summary("当前还没有部署版本。")
    else:
        print_deploy_summary("个人生产位已有可用版本。")
    print(f"[deploy] root => {DEFAULT_DEPLOY_ROOT}")
    print(f"[deploy] current release => {current_release or 'none'}")
    print(f"[deploy] releases => {len(payload['releases'])}")
    print(f"[deploy] launcher => {STABLE_CMD}")
    print(f"[deploy] panel => {STABLE_PANEL_CMD}")
    if current_release is None:
        print_deploy_next("python -X utf8 tools/mvp/safeclaw_personal_deploy.py deploy")
    else:
        print_deploy_next(str(STABLE_PANEL_CMD))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="SafeClaw 个人最小版生产部署：只做 deploy / rollback / status。",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    deploy_parser = subparsers.add_parser("deploy")
    deploy_parser.set_defaults(handler=deploy_release)

    rollback_parser = subparsers.add_parser("rollback")
    rollback_parser.set_defaults(handler=rollback_release)

    status_parser = subparsers.add_parser("status")
    status_parser.set_defaults(handler=show_status)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
