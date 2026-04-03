from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from queue import Empty, Queue
from typing import Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
PERSONAL_PANEL_ENTRY_PATH_ENV = "SAFECLAW_PERSONAL_GUI_ENTRY_PATH"
PERSONAL_PANEL_TITLE_ENV = "SAFECLAW_PERSONAL_GUI_TITLE"
DEFAULT_PANEL_TITLE = "SafeClaw 个人小面板"
DEFAULT_PANEL_POLL_INTERVAL_MS = 150
PANEL_ACTION_TITLES = {
    "archive-note": "写笔记",
    "status": "查看状态",
    "undo": "撤销上一步",
}


def build_entry_process_command(entry_path: Path) -> list[str]:
    resolved_path = str(entry_path)
    suffix = entry_path.suffix.lower()
    if suffix == ".cmd":
        return ["cmd", "/c", resolved_path]
    if suffix == ".ps1":
        return ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", resolved_path]
    if suffix in {".py", ".pyw"}:
        return [sys.executable, "-X", "utf8", resolved_path]
    return [resolved_path]


def resolve_personal_panel_entry_command(
    env: Mapping[str, str] | None = None,
    user_home: Path | None = None,
    repo_root: Path = REPO_ROOT,
) -> list[str]:
    env_map = env or os.environ
    override_path = (env_map.get(PERSONAL_PANEL_ENTRY_PATH_ENV) or "").strip()
    if override_path:
        return build_entry_process_command(Path(override_path).expanduser())
    resolved_home = (user_home or Path.home()).expanduser()
    production_root = resolved_home / ".safeclaw-personal-production"
    for entry_name in ("safeclaw-personal.cmd", "safeclaw-personal.ps1"):
        candidate = production_root / entry_name
        if candidate.exists():
            return build_entry_process_command(candidate)
    return [sys.executable, "-X", "utf8", str(repo_root / "tools/mvp/safeclaw_personal_mvp.py")]


def describe_personal_panel_entry_command(command: Sequence[str]) -> str:
    rendered_parts: list[str] = []
    for item in command:
        if " " in item:
            rendered_parts.append(f'"{item}"')
        else:
            rendered_parts.append(item)
    return " ".join(rendered_parts)


def build_archive_note_panel_arguments(note_name: str, content_file: Path) -> list[str]:
    return ["archive-note", "--name", note_name, "--content-file", str(content_file)]


def build_status_panel_arguments() -> list[str]:
    return ["status"]


def build_undo_panel_arguments() -> list[str]:
    return ["undo"]


def get_personal_panel_action_title(action_name: str) -> str:
    return PANEL_ACTION_TITLES.get(action_name, action_name)


def build_personal_panel_progress_text(action_name: str) -> str:
    if action_name == "archive-note":
        return "正在写入笔记，请稍等。"
    if action_name == "status":
        return "正在刷新状态，请稍等。"
    if action_name == "undo":
        return "正在撤销上一步，请稍等。"
    return f"正在执行：{action_name}"


def build_personal_panel_undo_confirmation_text() -> str:
    return "\n".join(
        [
            "这会尝试撤销最近一次归档笔记。",
            "如果最近一次笔记已经写入归档，对应文件可能会被删除。",
            "确定继续吗？",
        ]
    )


def build_panel_action_command(
    entry_command: Sequence[str],
    action_name: str,
    note_name: str = "",
    content_file: Path | None = None,
) -> list[str]:
    if action_name == "archive-note":
        if content_file is None:
            raise ValueError("archive-note requires content file")
        return list(entry_command) + build_archive_note_panel_arguments(note_name, content_file)
    if action_name == "status":
        return list(entry_command) + build_status_panel_arguments()
    if action_name == "undo":
        return list(entry_command) + build_undo_panel_arguments()
    raise ValueError(f"unsupported panel action: {action_name}")


def write_panel_content_file(note_content: str) -> Path:
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".md",
        prefix="safeclaw-personal-panel-",
        delete=False,
    ) as handle:
        handle.write(note_content)
        handle.write("\n")
        return Path(handle.name)


def run_personal_panel_action(
    entry_command: Sequence[str],
    action_name: str,
    note_name: str = "",
    note_content: str = "",
) -> subprocess.CompletedProcess[str]:
    content_file: Path | None = None
    try:
        if action_name == "archive-note":
            content_file = write_panel_content_file(note_content)
        command = build_panel_action_command(
            entry_command,
            action_name,
            note_name=note_name,
            content_file=content_file,
        )
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        return subprocess.run(
            command,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            creationflags=creation_flags,
        )
    finally:
        if content_file is not None:
            content_file.unlink(missing_ok=True)


def extract_personal_output_value(output_text: str, label: str) -> str | None:
    prefix = f"[personal] {label} => "
    for line in output_text.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip()
    return None


def build_personal_panel_error_hint(output_text: str) -> str | None:
    lowered_output = output_text.lower()
    if "no last note recorded" in lowered_output:
        return "还没有最近笔记，先点“写笔记”。"
    if "archive-note requires --name" in lowered_output:
        return "标题不能为空。"
    if "archive-note requires --content" in lowered_output:
        return "内容不能为空。"
    if "undo target missing" in lowered_output:
        return "要撤销的归档文件已经不存在，请先点“查看状态”。"
    return None


def build_archive_note_summary_lines(output_text: str) -> list[str]:
    lines = ["结果：已写入归档笔记"]
    last_note = extract_personal_output_value(output_text, "last note")
    next_step = extract_personal_output_value(output_text, "next")
    if last_note:
        lines.append(f"最近笔记：{last_note}")
    if next_step:
        lines.append(f"下一步：{next_step}")
    return lines


def build_status_summary_lines(output_text: str) -> list[str]:
    lines = ["结果：已刷新当前状态"]
    profile_path = extract_personal_output_value(output_text, "profile")
    database_path = extract_personal_output_value(output_text, "db")
    archive_root = extract_personal_output_value(output_text, "archive_root")
    last_note = extract_personal_output_value(output_text, "last note")
    archive_output = extract_personal_output_value(output_text, "archive_output")
    archive_exists = extract_personal_output_value(output_text, "archive exists")
    next_step = extract_personal_output_value(output_text, "next")
    if profile_path:
        lines.append(f"个人目录：{profile_path}")
    if database_path:
        lines.append(f"状态库：{database_path}")
    if archive_root:
        lines.append(f"归档目录：{archive_root}")
    if last_note == "none":
        lines.append("最近笔记：还没有")
    elif last_note:
        lines.append(f"最近笔记：{last_note}")
    if archive_output:
        lines.append(f"归档文件：{archive_output}")
    if archive_exists:
        lines.append(f"归档文件还在：{archive_exists}")
    if next_step:
        lines.append(f"下一步：{next_step}")
    return lines


def build_undo_summary_lines(output_text: str) -> list[str]:
    lines = ["结果：已执行撤销"]
    archive_exists = extract_personal_output_value(output_text, "archive exists")
    next_step = extract_personal_output_value(output_text, "next")
    if archive_exists:
        lines.append(f"归档文件还在：{archive_exists}")
    if next_step:
        lines.append(f"下一步：{next_step}")
    return lines


def build_personal_panel_summary_lines(action_name: str, output_text: str) -> list[str]:
    if action_name == "archive-note":
        return build_archive_note_summary_lines(output_text)
    if action_name == "status":
        return build_status_summary_lines(output_text)
    if action_name == "undo":
        return build_undo_summary_lines(output_text)
    return ["结果：已执行"]


def build_personal_panel_result_text(
    action_name: str,
    completed: subprocess.CompletedProcess[str],
) -> str:
    output_text = ((completed.stdout or "") + (completed.stderr or "")).strip()
    lines = [f"【{get_personal_panel_action_title(action_name)}】"]
    if completed.returncode == 0:
        lines.extend(build_personal_panel_summary_lines(action_name, output_text))
    else:
        lines.append(f"退出码：{completed.returncode}")
        lines.append("结果：执行失败")
        error_hint = build_personal_panel_error_hint(output_text)
        if error_hint:
            lines.append(f"提示：{error_hint}")
        else:
            lines.append("提示：下面是程序原始输出，便于排查。")
    if output_text and completed.returncode != 0:
        lines.extend(["", "【原始输出】", output_text])
    return "\n".join(lines)


def build_personal_panel_welcome_text(entry_command: Sequence[str]) -> str:
    return "\n".join(
        [
            "欢迎使用 SafeClaw 个人小面板。",
            f"当前入口：{describe_personal_panel_entry_command(entry_command)}",
            "这个面板只做三件事：写笔记、查看状态、撤销上一步。",
            "窗口打开后会自动刷新一次当前状态。",
        ]
    )


class SafeclawPersonalPanelController:
    def __init__(
        self,
        root: object,
        tkinter_module: object,
        ttk_module: object,
        scrolledtext_module: object,
        messagebox_module: object,
        entry_command: Sequence[str],
    ) -> None:
        self.root = root
        self.tk = tkinter_module
        self.ttk = ttk_module
        self.messagebox = messagebox_module
        self.entry_command = list(entry_command)
        self.result_queue: Queue[tuple[str, str]] = Queue()
        self.title_var = tkinter_module.StringVar()
        self.entry_var = tkinter_module.StringVar(
            value=describe_personal_panel_entry_command(self.entry_command)
        )
        self.content_text: object | None = None
        self.output_text: object | None = None
        self.archive_button: object | None = None
        self.status_button: object | None = None
        self.undo_button: object | None = None
        self._build_layout(scrolledtext_module)
        self._set_output(build_personal_panel_welcome_text(self.entry_command))
        self.root.after(DEFAULT_PANEL_POLL_INTERVAL_MS, self._drain_result_queue)

    def _build_layout(self, scrolledtext_module: object) -> None:
        self.root.geometry("980x720")
        self.root.minsize(820, 620)
        outer_frame = self.ttk.Frame(self.root, padding=16)
        outer_frame.pack(fill=self.tk.BOTH, expand=True)
        self.ttk.Label(
            outer_frame,
            text="SafeClaw 个人小面板：只包住 archive-note → status → undo",
        ).pack(anchor=self.tk.W)
        self.ttk.Label(outer_frame, textvariable=self.entry_var, foreground="#666666").pack(anchor=self.tk.W, pady=(4, 12))
        self.ttk.Label(outer_frame, text="笔记标题").pack(anchor=self.tk.W)
        self.ttk.Entry(outer_frame, textvariable=self.title_var).pack(fill=self.tk.X, pady=(4, 12))
        self.ttk.Label(outer_frame, text="笔记内容").pack(anchor=self.tk.W)
        self.content_text = scrolledtext_module.ScrolledText(outer_frame, height=12, wrap=self.tk.WORD)
        self.content_text.pack(fill=self.tk.BOTH, expand=False, pady=(4, 12))
        button_row = self.ttk.Frame(outer_frame)
        button_row.pack(fill=self.tk.X, pady=(0, 12))
        self.archive_button = self.ttk.Button(button_row, text="写笔记", command=self.request_archive_note)
        self.archive_button.pack(side=self.tk.LEFT)
        self.status_button = self.ttk.Button(button_row, text="查看状态", command=self.request_status)
        self.status_button.pack(side=self.tk.LEFT, padx=(8, 0))
        self.undo_button = self.ttk.Button(button_row, text="撤销上一步", command=self.request_undo)
        self.undo_button.pack(side=self.tk.LEFT, padx=(8, 0))
        self.ttk.Label(outer_frame, text="结果").pack(anchor=self.tk.W)
        self.output_text = scrolledtext_module.ScrolledText(outer_frame, height=18, wrap=self.tk.WORD)
        self.output_text.pack(fill=self.tk.BOTH, expand=True)

    def _set_buttons_enabled(self, enabled: bool) -> None:
        next_state = self.tk.NORMAL if enabled else self.tk.DISABLED
        for button in (self.archive_button, self.status_button, self.undo_button):
            if button is not None:
                button.configure(state=next_state)

    def _set_output(self, text: str) -> None:
        if self.output_text is None:
            return
        self.output_text.delete("1.0", self.tk.END)
        self.output_text.insert(self.tk.END, text)
        self.output_text.see(self.tk.END)

    def request_archive_note(self) -> None:
        if self.content_text is None:
            return
        note_name = self.title_var.get().strip()
        note_content = self.content_text.get("1.0", "end-1c").strip()
        if not note_name:
            self.messagebox.showerror("SafeClaw 个人小面板", "标题不能为空。")
            return
        if not note_content:
            self.messagebox.showerror("SafeClaw 个人小面板", "内容不能为空。")
            return
        self._queue_action("archive-note", note_name=note_name, note_content=note_content)

    def request_status(self) -> None:
        self._queue_action("status")

    def request_undo(self) -> None:
        if not self.messagebox.askyesno(
            "SafeClaw 个人小面板",
            build_personal_panel_undo_confirmation_text(),
        ):
            self._set_output("已取消：这次没有执行撤销。")
            return
        self._queue_action("undo")

    def _queue_action(self, action_name: str, note_name: str = "", note_content: str = "") -> None:
        self._set_buttons_enabled(False)
        self._set_output(build_personal_panel_progress_text(action_name))
        worker = threading.Thread(
            target=self._run_action_worker,
            args=(action_name, note_name, note_content),
            daemon=True,
        )
        worker.start()

    def _run_action_worker(self, action_name: str, note_name: str, note_content: str) -> None:
        completed = run_personal_panel_action(
            self.entry_command,
            action_name,
            note_name=note_name,
            note_content=note_content,
        )
        rendered_text = build_personal_panel_result_text(action_name, completed)
        self.result_queue.put((action_name, rendered_text))

    def _drain_result_queue(self) -> None:
        try:
            while True:
                _, rendered_text = self.result_queue.get_nowait()
                self._set_output(rendered_text)
                self._set_buttons_enabled(True)
        except Empty:
            self.root.after(DEFAULT_PANEL_POLL_INTERVAL_MS, self._drain_result_queue)
            return
        self.root.after(DEFAULT_PANEL_POLL_INTERVAL_MS, self._drain_result_queue)


def launch_personal_panel(entry_command: Sequence[str] | None = None) -> int:
    import tkinter as tk
    from tkinter import messagebox, scrolledtext, ttk

    resolved_command = list(entry_command or resolve_personal_panel_entry_command())
    root = tk.Tk()
    root.title(os.environ.get(PERSONAL_PANEL_TITLE_ENV) or DEFAULT_PANEL_TITLE)
    controller = SafeclawPersonalPanelController(
        root,
        tk,
        ttk,
        scrolledtext,
        messagebox,
        resolved_command,
    )
    controller.request_status()
    root.mainloop()
    return 0


def main() -> int:
    return launch_personal_panel()


if __name__ == "__main__":
    raise SystemExit(main())
