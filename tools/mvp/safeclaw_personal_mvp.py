from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLCHAIN = "stable-x86_64-pc-windows-gnu"
TOOLCHAIN_BIN_PATH = Path.home() / ".rustup" / "toolchains" / TOOLCHAIN / "bin"
LINKER = (
    r"C:\Users\tianduan999\AppData\Local\Microsoft\WinGet\Packages\BrechtSanders."
    r"WinLibs.POSIX.UCRT_Microsoft.Winget.Source_8wekyb3d8bbwe\mingw64\bin\x86_64-w64-mingw32-gcc.exe"
)
CARGO_SAFECLAW_MVP_ENTRY_PREFIX = [
    "cargo",
    f"+{TOOLCHAIN}",
    "run",
    "-p",
    "safeclaw-sqlite",
    "--example",
    "safeclaw_mvp_entry",
    "--quiet",
    "--",
]
SAFECLAW_MVP_ENTRY_EXE_RELATIVE_PATH = Path("target/debug/examples/safeclaw_mvp_entry.exe")
PROFILE_ROOT_ENV = "SAFECLAW_PERSONAL_ROOT"
DEFAULT_PROFILE_ROOT = Path(
    os.environ.get(PROFILE_ROOT_ENV) or (Path.home() / ".safeclaw-personal")
).expanduser()
STATE_DIR = DEFAULT_PROFILE_ROOT / "state"
ARCHIVE_ROOT = DEFAULT_PROFILE_ROOT / "archive"
DB_PATH = STATE_DIR / "session.db"
LAST_NOTE_FILE = STATE_DIR / "last_note.json"
ENTRY_COMMAND_ENV = "SAFECLAW_PERSONAL_ENTRY_COMMAND"
ENTRY_COMMAND = os.environ.get(ENTRY_COMMAND_ENV) or r"tools\mvp\safeclaw_personal_mvp.cmd"
DEFAULT_OWNER_ID = "safeclaw-personal"
ARCHIVE_NOTE_NAME_REQUIRED_REASON = "标题不能为空。"
ARCHIVE_NOTE_CONTENT_REQUIRED_REASON = "内容不能为空。"


def render_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def print_personal_summary(summary_text: str) -> None:
    print(f"[personal] summary => {summary_text}")


def sanitize_note_name(value: str) -> str:
    sanitized: list[str] = []
    previous_dash = False
    for character in value.strip():
        if "a" <= character <= "z" or "0" <= character <= "9":
            normalized = character
        elif "A" <= character <= "Z":
            normalized = character.lower()
        elif character in {" ", "-", "_"}:
            normalized = "-"
        elif character.isascii() and character.isalnum():
            normalized = character.lower()
        else:
            normalized = None
        if normalized is None:
            continue
        if normalized == "-":
            if previous_dash:
                continue
            previous_dash = True
        else:
            previous_dash = False
        sanitized.append(normalized)
    return "".join(sanitized).strip("-")


def validate_archive_date(value: str) -> str:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as error:
        raise argparse.ArgumentTypeError("--date requires YYYY-MM-DD") from error
    return value


def build_archive_output_path(archive_root: Path, archive_date: str, note_name: str) -> Path:
    archive_slug = sanitize_note_name(note_name)
    if not archive_slug:
        raise ValueError(ARCHIVE_NOTE_NAME_REQUIRED_REASON)
    month_scope = archive_date[:7]
    return archive_root / month_scope / f"{archive_date}-{archive_slug}.md"


def build_task_id(note_name: str, now: datetime) -> str:
    archive_slug = sanitize_note_name(note_name)
    if not archive_slug:
        raise ValueError(ARCHIVE_NOTE_NAME_REQUIRED_REASON)
    timestamp = now.strftime("%Y%m%d-%H%M%S")
    return f"task-safeclaw-personal-{timestamp}-{archive_slug}"


def build_archive_note_command(
    note_name: str,
    archive_date: str,
    content: str,
    task_id: str,
) -> list[str]:
    return [
        *CARGO_SAFECLAW_MVP_ENTRY_PREFIX,
        "archive-note",
        "--db",
        str(DB_PATH),
        "--archive-root",
        str(ARCHIVE_ROOT),
        "--archive-date",
        archive_date,
        "--archive-name",
        note_name,
        "--content",
        content,
        "--task-id",
        task_id,
        "--owner-id",
        DEFAULT_OWNER_ID,
    ]


def build_undo_command(task_id: str) -> list[str]:
    return [
        *CARGO_SAFECLAW_MVP_ENTRY_PREFIX,
        "undo",
        "--db",
        str(DB_PATH),
        "--task-id",
        task_id,
        "--owner-id",
        DEFAULT_OWNER_ID,
    ]


def ensure_profile_dirs() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_ROOT.mkdir(parents=True, exist_ok=True)


def load_last_note() -> dict[str, str] | None:
    if not LAST_NOTE_FILE.exists():
        return None
    payload = json.loads(LAST_NOTE_FILE.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"invalid last note file: {LAST_NOTE_FILE}")
    return {key: str(value) for key, value in payload.items()}


def save_last_note(payload: dict[str, str]) -> None:
    ensure_profile_dirs()
    LAST_NOTE_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def prepend_runtime_path_entries(runtime_env: dict[str, str], path_entries: list[str]) -> dict[str, str]:
    if not path_entries:
        return runtime_env
    existing_entries = [entry for entry in runtime_env.get("PATH", "").split(os.pathsep) if entry]
    seen_entries = {os.path.normcase(os.path.normpath(entry)) for entry in existing_entries}
    additions: list[str] = []
    for entry in path_entries:
        normalized_entry = os.path.normcase(os.path.normpath(entry))
        if normalized_entry in seen_entries:
            continue
        seen_entries.add(normalized_entry)
        additions.append(entry)
    if additions:
        runtime_env["PATH"] = os.pathsep.join([*additions, *existing_entries])
    return runtime_env


def resolve_safeclaw_mvp_runtime_command(
    command: list[str],
    repo_root: Path = REPO_ROOT,
) -> list[str]:
    if command[: len(CARGO_SAFECLAW_MVP_ENTRY_PREFIX)] != CARGO_SAFECLAW_MVP_ENTRY_PREFIX:
        return list(command)
    example_path = repo_root / SAFECLAW_MVP_ENTRY_EXE_RELATIVE_PATH
    if not example_path.exists():
        return list(command)
    return [str(example_path), *command[len(CARGO_SAFECLAW_MVP_ENTRY_PREFIX) :]]


def build_safeclaw_mvp_runtime_env(command: list[str]) -> dict[str, str]:
    runtime_env = os.environ.copy()
    path_entries: list[str] = []
    if TOOLCHAIN_BIN_PATH.exists():
        path_entries.append(str(TOOLCHAIN_BIN_PATH))
    if command[: len(CARGO_SAFECLAW_MVP_ENTRY_PREFIX)] == CARGO_SAFECLAW_MVP_ENTRY_PREFIX:
        runtime_env.setdefault("CARGO_TARGET_X86_64_PC_WINDOWS_GNU_LINKER", LINKER)
    return prepend_runtime_path_entries(runtime_env, path_entries)


def check_configured_linker_accessible() -> bool:
    try:
        return Path(LINKER).exists()
    except PermissionError as error:
        print(f"[personal] linker probe permission denied => {LINKER} ({error})")
        return True


def print_personal_runtime_failure(reason_text: str, next_text: str) -> int:
    print_personal_summary("当前机器还没准备好个人归档运行环境。")
    print(f"[personal] {reason_text}")
    print(f"[personal] next => {next_text}")
    return 1


def run_checked(command: list[str]) -> int:
    runtime_command = resolve_safeclaw_mvp_runtime_command(command)
    if runtime_command == command:
        cargo_path = shutil.which("cargo")
        if cargo_path is None:
            return print_personal_runtime_failure(
                "missing cargo in PATH",
                "先安装 Rust cargo，再重试当前命令。",
            )
        if not check_configured_linker_accessible():
            return print_personal_runtime_failure(
                f"missing GNU linker => {LINKER}",
                "先检查 GNU linker 路径是否存在，再重试当前命令。",
            )
    completed = subprocess.run(
        runtime_command,
        cwd=REPO_ROOT,
        env=build_safeclaw_mvp_runtime_env(runtime_command),
        check=False,
    )
    return completed.returncode


def read_content(args: argparse.Namespace) -> str:
    if args.content is not None:
        return args.content
    if args.content_file is not None:
        content_file_path = Path(args.content_file)
        try:
            return content_file_path.read_text(encoding="utf-8")
        except OSError as error:
            raise ValueError(f"archive-note content-file missing => {render_path(content_file_path)}") from error
    raise ValueError(ARCHIVE_NOTE_CONTENT_REQUIRED_REASON)


def print_archive_note_failure(reason_text: str) -> int:
    print_personal_summary("这次还没写成笔记。")
    print(f"[personal] {reason_text}")
    print(f"[personal] next => {ENTRY_COMMAND} archive-note --name <name> --content <text>")
    return 1


def print_last_note_state_failure() -> int:
    state_file_path = render_path(LAST_NOTE_FILE)
    print_personal_summary("最近笔记状态文件有问题，这次没法继续。")
    print(f"[personal] invalid last note file => {state_file_path}")
    print(f"[personal] next => 先检查并修复 {state_file_path}，再重试当前命令。")
    return 1


def run_archive_note(args: argparse.Namespace) -> int:
    ensure_profile_dirs()
    archive_date = args.date or date.today().isoformat()
    note_name = (args.name or "").strip()
    if not note_name:
        return print_archive_note_failure(ARCHIVE_NOTE_NAME_REQUIRED_REASON)
    try:
        content = read_content(args)
        task_id = build_task_id(note_name, datetime.now())
        output_path = build_archive_output_path(ARCHIVE_ROOT, archive_date, note_name)
    except ValueError as error:
        return print_archive_note_failure(str(error))
    exit_code = run_checked(build_archive_note_command(note_name, archive_date, content, task_id))
    if exit_code != 0:
        return exit_code
    save_last_note(
        {
            "task_id": task_id,
            "archive_date": archive_date,
            "archive_name": note_name,
            "archive_output": str(output_path),
            "db_path": str(DB_PATH),
            "archive_root": str(ARCHIVE_ROOT),
            "owner_id": DEFAULT_OWNER_ID,
            "entry": ENTRY_COMMAND,
        }
    )
    print_personal_summary("最近一次笔记已归档，需要时可以直接撤销。")
    print(f"[personal] profile => {render_path(DEFAULT_PROFILE_ROOT)}")
    print(f"[personal] last note => task={task_id} output={render_path(output_path)}")
    print(f"[personal] next => {ENTRY_COMMAND} undo")
    return 0


def run_undo(_: argparse.Namespace) -> int:
    try:
        note = load_last_note()
    except ValueError:
        return print_last_note_state_failure()
    if note is None:
        print_personal_summary("这次没有可撤销的最近笔记。")
        print("[personal] 还没有最近笔记，所以这次没法撤销。")
        print(f"[personal] next => {ENTRY_COMMAND} archive-note --name <name> --content <text>")
        return 1
    exit_code = run_checked(build_undo_command(note["task_id"]))
    if exit_code != 0:
        return exit_code
    updated_note = dict(note)
    updated_note["undone_at"] = datetime.now().isoformat(timespec="seconds")
    save_last_note(updated_note)
    output_path = Path(note["archive_output"])
    print_personal_summary("已撤销最近一次归档。")
    print(f"[personal] profile => {render_path(DEFAULT_PROFILE_ROOT)}")
    print(f"[personal] archive exists => {output_path.exists()}")
    print(f"[personal] next => {ENTRY_COMMAND} archive-note --name <name> --content <text>")
    return 0


def run_status(_: argparse.Namespace) -> int:
    ensure_profile_dirs()
    try:
        note = load_last_note()
    except ValueError:
        return print_last_note_state_failure()
    summary_text = "当前还没有最近笔记。"
    next_text = f"{ENTRY_COMMAND} archive-note --name <name> --content <text>"
    if note is None:
        print_personal_summary(summary_text)
        print(f"[personal] profile => {render_path(DEFAULT_PROFILE_ROOT)}")
        print(f"[personal] db => {render_path(DB_PATH)}")
        print(f"[personal] archive_root => {render_path(ARCHIVE_ROOT)}")
        print("[personal] last note => none")
        print(f"[personal] next => {next_text}")
        return 0
    output_path = Path(note["archive_output"])
    if output_path.exists():
        summary_text = "最近一次笔记还在，需要时可以直接撤销。"
        next_text = f"{ENTRY_COMMAND} undo"
    else:
        summary_text = "最近一次笔记记录还在，但归档文件已经不在了。"
    print_personal_summary(summary_text)
    print(f"[personal] profile => {render_path(DEFAULT_PROFILE_ROOT)}")
    print(f"[personal] db => {render_path(DB_PATH)}")
    print(f"[personal] archive_root => {render_path(ARCHIVE_ROOT)}")
    print(
        "[personal] last note => "
        f"task={note['task_id']} name={note['archive_name']} date={note['archive_date']}"
    )
    print(f"[personal] archive_output => {render_path(output_path)}")
    print(f"[personal] archive exists => {output_path.exists()}")
    print(f"[personal] next => {next_text}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="SafeClaw 个人自用最小版：只保留 archive-note / status / undo。",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    archive_note_parser = subparsers.add_parser("archive-note")
    archive_note_parser.add_argument("--name", help="归档标题")
    archive_note_parser.add_argument("--date", type=validate_archive_date, help="归档日期，默认今天")
    archive_note_content = archive_note_parser.add_mutually_exclusive_group()
    archive_note_content.add_argument("--content", help="归档内容")
    archive_note_content.add_argument("--content-file", help="从文件读取归档内容")
    archive_note_parser.set_defaults(handler=run_archive_note)

    undo_parser = subparsers.add_parser("undo")
    undo_parser.set_defaults(handler=run_undo)

    status_parser = subparsers.add_parser("status")
    status_parser.set_defaults(handler=run_status)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
