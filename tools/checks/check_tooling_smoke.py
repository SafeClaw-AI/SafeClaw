from __future__ import annotations

import json

import os

import sqlite3

import time

import subprocess

import sys

import tempfile

from pathlib import Path

from mvp_state_guard import _process_is_running, acquire_mvp_state_lock

REPO_ROOT = Path(__file__).resolve().parents[2]

PYTHON = sys.executable
_ORIGINAL_SUBPROCESS_MODULE = subprocess
_SMOKE_RUN_COUNTER = 0
_SMOKE_STARTED_AT = 0.0
_SMOKE_PARENT_PID = 0
_SMOKE_MONITOR_INTERVAL_SECONDS = 0.5
_SMOKE_TEMP_DIRS: list[tempfile.TemporaryDirectory[str]] = []
_SMOKE_DEMO_STUB_ACTIONS = {"demo", "recover-demo", "retry-demo", "service-demo"}
_SMOKE_DEMO_STUB_TASK_IDS = {
    "task-wrapper-demo",
    "task-wrapper-demo-json",
    "task-wrapper-demo-preflight",
    "task-wrapper-recover-demo",
    "task-wrapper-recover-demo-json",
    "task-wrapper-retry-demo",
    "task-wrapper-retry-demo-json",
}
_SMOKE_WRAPPER_SERVICE_STUB_ACTIONS = {"service-demo", "service-run"}
_SMOKE_WRAPPER_SERVICE_STUB_TASK_IDS = {
    "task-wrapper-service-run-json",
    "task-wrapper-service-run-report-json",
}
_SMOKE_WRAPPER_SERVICE_REPORT_STUB_ACTIONS = {
    "service-retry",
    "service-recover",
    "service-resume",
    "service-reconcile",
}
_SMOKE_WRAPPER_SERVICE_REPORT_STUB_TASK_IDS = {
    "task-wrapper-service-retry-report-json",
    "task-wrapper-service-recover-report-json",
    "task-wrapper-service-resume-report-json",
    "task-wrapper-service-reconcile-report-json",
}
_SMOKE_ROOT_PS1_SERVICE_REPORT_STUB_ACTIONS = {
    "service-run",
    "service-retry",
    "service-recover",
    "service-resume",
    "service-reconcile",
}
_SMOKE_ROOT_PS1_SERVICE_REPORT_STUB_TASK_IDS = {
    "task-readme-root",
    "task-readme-root-failed-ps1",
    "task-readme-root-uncertain-ps1",
    "task-readme-root-hibernated-ps1",
    "task-readme-root-assumed-ps1",
}
_SMOKE_WRAPPER_REPORT_STUB_TASK_OUTPUTS = {
    "task-wrapper-recover-json": ("", "", ""),
    "task-wrapper-report-explicit-crash": (
        "QueueForManualReview",
        "Uncertain",
        "Uncertain",
    ),
    "task-wrapper-session-explicit-crash": (
        "QueueForManualReview",
        "Uncertain",
        "Uncertain",
    ),
    "task-wrapper-sessions-explicit-crash": (
        "QueueForManualReview",
        "Uncertain",
        "Uncertain",
    ),
    "task-wrapper-status-session-crash": (
        "QueueForManualReview",
        "Uncertain",
        "Uncertain",
    ),
    "task-wrapper-report-session-crash": (
        "QueueForManualReview",
        "Uncertain",
        "Uncertain",
    ),
    "task-wrapper-recover-session-crash": (
        "QueueForManualReview",
        "Uncertain",
        "Uncertain",
    ),
    "task-wrapper-cmd-recover-session-crash": (
        "QueueForManualReview",
        "Uncertain",
        "Uncertain",
    ),
    "task-wrapper-retry-session": ("RetryEligible", "Failed", "Prepared"),
    "task-wrapper-cmd-retry-session": ("RetryEligible", "Failed", "Prepared"),
    "task-wrapper-status-failed-session": ("RetryEligible", "Failed", "Prepared"),
    "task-wrapper-report-failed-session": ("RetryEligible", "Failed", "Prepared"),
    "task-wrapper-session-failed": ("RetryEligible", "Failed", "Prepared"),
    "task-wrapper-sessions-failed": ("RetryEligible", "Failed", "Prepared"),
    "task-wrapper-report-explicit-failed": ("RetryEligible", "Failed", "Prepared"),
    "task-wrapper-service-retry-report-json": ("", "", ""),
    "task-wrapper-service-recover-report-json": ("", "", ""),
    "task-wrapper-service-resume-report-json": ("", "", ""),
    "task-wrapper-service-reconcile-report-json": ("", "", ""),
    "task-readme-root": ("", "", ""),
    "task-readme-root-failed-ps1": ("", "", ""),
    "task-readme-root-uncertain-ps1": ("", "", ""),
    "task-readme-root-hibernated-ps1": ("", "", ""),
    "task-readme-root-assumed-ps1": ("", "", ""),
}
_SMOKE_WRAPPER_HELP_EXPECTATIONS = [
    (
        "[mvp-wrapper] usage => tools\\mvp\\safeclaw_mvp.cmd <action> [flags]",
        "mvp-wrapper-help 输出缺少包装入口说明",
    ),
    (
        "[mvp-wrapper] local actions => demo, recover-demo, retry-demo, service-demo, service-run, service-retry, service-recover, service-resume, service-reconcile, service-status, session, sessions, use, forget, workspace, doctor, preflight, verify",
        "mvp-wrapper-help 输出缺少本地动作列表",
    ),
    (
        "[mvp-wrapper] examples => demo | recover-demo | retry-demo | service-demo | service-run --reset --limit 1 | service-run --reset --limit 1 --report | service-retry --task-id task-demo --limit 1 --report | service-recover --task-id task-demo --limit 1 --report | service-resume --task-id task-demo --limit 1 --report | service-reconcile --task-id task-demo --decision executed --limit 1 --report | service-status --limit 5 | session | sessions --limit 5 | use --index 0 | use --task-id task-demo | status --task-id task-demo | report --task-id task-demo | undo --task-id task-demo | reconcile --task-id task-demo --decision executed | forget | workspace | workspace --name demo | workspace --clear | doctor | preflight --action service-run --enforce-permission | verify",
        "mvp-wrapper-help 输出缺少 task-id/status/report 示例提示",
    ),
    (
        "[mvp-wrapper] demo flows => demo=run->status->report; recover-demo=seed-crash->recover->report; retry-demo=seed-failed->retry->report; service-demo=worker-service-governance; service-run=run->service-status; service-retry=retry->service-status; service-recover=recover->service-status; service-resume=resume->service-status; service-reconcile=reconcile->service-status",
        "mvp-wrapper-help 输出缺少 demo 链路提示",
    ),
    (
        "[mvp-wrapper] failure flows => run 直接执行到完成；seed-crash/recover 演示 uncertain 恢复；seed-failed/retry 演示失败态重试",
        "mvp-wrapper-help 输出缺少异常链提示",
    ),
    (
        "[mvp-wrapper] errors => invalid-argument / missing-task-context / resume-target-missing / resume-target-not-hibernated；组合动作 JSON 失败会额外附带 failed_step / code / error_message",
        "mvp-wrapper-help 输出缺少 JSON 错误码提示",
    ),
    (
        "[mvp-wrapper] error hints => invalid-argument 多为未知参数或 flag 缺值；missing-task-context 时请传 --task-id，或先 use/run/seed-crash/seed-failed 建立上下文；resume-target-* 时请先跑 service-status 确认当前 task 是否仍在 hibernated",
        "mvp-wrapper-help 输出缺少错误码解释提示",
    ),
    (
        "[mvp-wrapper] error message => error.message 是稳定的 wrapper 级消息；脚本无需解析底层 cargo 文案",
        "mvp-wrapper-help 输出缺少稳定 error.message 提示",
    ),
    (
        "[mvp-wrapper] service run => service-run executes run then service-status with one command; supports write flags plus --limit / --preflight / --enforce-permission / --json",
        "mvp-wrapper-help missing service-run help hint",
    ),
    (
        "[mvp-wrapper] service retry => service-retry executes retry then service-status for a failed task; supports retry flags plus --limit / --preflight / --enforce-permission / --json",
        "mvp-wrapper-help missing service-retry help hint",
    ),
    (
        "[mvp-wrapper] service recover => service-recover executes recover then service-status for an uncertain task; supports recover flags plus --limit / --preflight / --enforce-permission / --json",
        "mvp-wrapper-help missing service-recover help hint",
    ),
    (
        "[mvp-wrapper] service resume => service-resume executes resume then service-status for a hibernated task; supports resume flags plus --limit / --report / --preflight / --enforce-permission / --json",
        "mvp-wrapper-help missing service-resume help hint",
    ),
    (
        "[mvp-wrapper] service reconcile => service-reconcile executes reconcile then service-status for an executed_assumed task; requires --decision executed|not-executed and supports reconcile flags plus --limit / --report / --preflight / --enforce-permission / --json",
        "mvp-wrapper-help missing service-reconcile help hint",
    ),
    (
        "[mvp-wrapper] service status => service-status shows queue / worker / effect / probe / heartbeat summary / runtime / model-provider / sidecar snapshots / offline gate summary / coordination summary / recent task summary, plus scope, same-scope peer / scope-quarantine visibility, permission decisions, lease freshness, active-lease wait timing, next action hints, suggested commands, short reasons, blockers, coordination hints, and one-line summaries; supports --db / --limit / --json",
        "mvp-wrapper-help missing service-status help hint",
    ),
    (
        "[mvp-wrapper] error session => 包装层错误 JSON 若当前存在 remembered session；会在 error.details.remembered_session 附带它",
        "mvp-wrapper-help 输出缺少错误 remembered_session 提示",
    ),
    (
        "[mvp-wrapper] session => session 显示当前记忆的最近成功会话；sessions/use/forget 管理 remembered session；status/report/recover/retry/resume/doctor 会尽量复用它",
        "mvp-wrapper-help 输出缺少 session 最近成功会话提示",
    ),
    (
        "[mvp-wrapper] status/report => status 默认查看当前 remembered session，也可显式传 --task-id；report 查看指定 task/effect 的治理视图",
        "mvp-wrapper-help 输出缺少 status/report 语义提示",
    ),
    (
        "[mvp-wrapper] doctor => 文本模式会检查包装入口、cargo/toolchain/linker、remembered session 路径，并给出 db/output 来源；--json 会额外返回 status 与 failing_checks",
        "mvp-wrapper-help 输出缺少 doctor 检查项提示",
    ),
    (
        "[mvp-wrapper] preflight => preflight checks whether an action stays allowed in the current local-only MVP entry; common wrapper/session actions auto-infer permission context from remembered session/workspace/default output, preflight-only ai-reason returns ERR_AI_PROVIDER_UNAVAILABLE when no provider/sidecar is configured, explicit --scope / --write / --doctor-bypass override permission context, and --enforce-permission fails closed on confirm / deny; supports --action <name> / --scope <value> / --json",
        "mvp-wrapper-help missing preflight help hint",
    ),
    (
        "[mvp-wrapper] combo preflight override => demo/recover-demo/retry-demo/service-run/service-retry/service-recover/service-resume/service-reconcile accept --preflight-action <name>; blocked combo JSON keeps full error.details.preflight, mirrors preflight-blocked at top-level error.code, mirrors preflight_reason at top-level error.reason, mirrors optional preflight_error_code at top-level error.error_code, mirrors degradation_mode at top-level error.degradation_mode, mirrors requires_model at top-level error.requires_model, mirrors requires_sidecar at top-level error.requires_sidecar, mirrors preflight_summary at top-level error.summary, mirrors preflight_requested_action at top-level error.requested_action, and mirrors preflight_requested_action / preflight_reason / preflight_summary / optional preflight_error_code at the error.details top level",
        "mvp-wrapper-help missing combo preflight override hint",
    ),
    (
        "[mvp-wrapper] source hints => status/report/recover/retry/resume/reconcile --json 会额外返回 result.source_hints；可直接看到 db/output/owner_id/task_context 来源",
        "mvp-wrapper-help 输出缺少 source_hints 提示",
    ),
    (
        "[mvp-wrapper] combo source hints => demo/recover-demo/retry-demo/service-run/service-retry/service-recover/service-resume/service-reconcile --json result.steps[*] and error.details.steps[*] include source_hints",
        "mvp-wrapper-help missing combo source_hints hint",
    ),
    (
        "[mvp-wrapper] combo session => demo/recover-demo/retry-demo/service-run/service-retry/service-recover/service-resume/service-reconcile --json returns result.remembered_session; result.session stays as a compatibility alias; scripts should prefer remembered_session",
        "mvp-wrapper-help missing combo remembered_session hint",
    ),
    (
        "[mvp-wrapper] session list => sessions 会列出当前 db 的最近任务快照；use 可按 --index / --task-id 激活其中一条",
        "mvp-wrapper-help 输出缺少 sessions 快照提示",
    ),
    (
        "[mvp-wrapper] session selectors => status 可显式传 --task-id；use 支持 --index / --task-id 选择历史会话",
        "mvp-wrapper-help 输出缺少 session 选择方式提示",
    ),
    (
        "[mvp-wrapper] session sources => sessions 默认优先复用 remembered session 的 db，文本/JSON 都会标 source；use 文本/JSON 都会标选择来源与 db/output/owner 来源，--json 会返回 source/db_source/output_source/owner_id_source",
        "mvp-wrapper-help 输出缺少 use 来源提示",
    ),
    (
        "[mvp-wrapper] session paths => session 文本输出会带 remembered session 文件路径；forget 文本/JSON 会显式给出 reason/path，且不删除 db/output 文件",
        "mvp-wrapper-help 输出缺少 forget 保留文件提示",
    ),
    (
        "[mvp-wrapper] session repair => remembered session 文件损坏时会自动丢弃并回退为 session => none",
        "mvp-wrapper-help 输出缺少 session repair 提示",
    ),
]
_SMOKE_WRAPPER_HELP_GROUPED_EXPECTATIONS = [
    (
        (
            "demo/recover-demo/retry-demo/service-demo/service-run/service-retry/service-recover/service-resume/service-reconcile/service-status/run/report/status/",
            "seed-crash/seed-hibernated/recover/seed-failed/retry/resume/reconcile/undo/session/sessions/use/forget/workspace/doctor/preflight/verify",
            "{ok, action, schema_version, result|error}",
        ),
        "mvp-wrapper-help missing JSON envelope hint",
    ),
]


def format_smoke_command(command: object) -> str:
    if isinstance(command, str):
        return command
    if not isinstance(command, (list, tuple)):
        return repr(command)
    preview = " ".join(str(part) for part in command[:8])
    if len(command) > 8:
        preview = f"{preview} ..."
    return preview


def get_smoke_command_flag(command_parts: list[str], flag: str) -> str | None:
    if flag not in command_parts:
        return None
    index = command_parts.index(flag) + 1
    if index >= len(command_parts):
        return None
    return command_parts[index]


def should_use_smoke_demo_sitecustomize(command: object) -> bool:
    if not isinstance(command, (list, tuple)):
        return False
    command_parts = [str(part) for part in command]
    if len(command_parts) < 3:
        return False
    script_path = command_parts[1].replace("\\", "/")
    if not script_path.endswith("tools/mvp/safeclaw_mvp.py"):
        return False
    if command_parts[2] not in _SMOKE_DEMO_STUB_ACTIONS:
        return False
    if "--bogus" in command_parts:
        return False
    if command_parts[2] == "service-demo":
        return True
    task_id = get_smoke_command_flag(command_parts, "--task-id")
    return task_id in _SMOKE_DEMO_STUB_TASK_IDS


def should_use_smoke_wrapper_service_sitecustomize(command: object) -> bool:
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
    if action not in _SMOKE_WRAPPER_SERVICE_STUB_ACTIONS:
        return False
    if action == "service-demo":
        return True
    task_id = get_smoke_command_flag(command_parts, "--task-id")
    return task_id in _SMOKE_WRAPPER_SERVICE_STUB_TASK_IDS


def should_use_smoke_wrapper_report_sitecustomize(command: object) -> bool:
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
    return db_path is not None and task_id in _SMOKE_WRAPPER_REPORT_STUB_TASK_OUTPUTS


def should_use_smoke_wrapper_service_report_sitecustomize(command: object) -> bool:
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
    if action not in _SMOKE_WRAPPER_SERVICE_REPORT_STUB_ACTIONS:
        return False
    db_path = get_smoke_command_flag(command_parts, "--db")
    task_id = get_smoke_command_flag(command_parts, "--task-id")
    return (
        db_path is not None and task_id in _SMOKE_WRAPPER_SERVICE_REPORT_STUB_TASK_IDS
    )


def should_use_smoke_root_ps1_service_report_sitecustomize(command: object) -> bool:
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
    if action not in _SMOKE_ROOT_PS1_SERVICE_REPORT_STUB_ACTIONS:
        return False
    task_id = get_smoke_command_flag(command_parts, "--task-id")
    return task_id in _SMOKE_ROOT_PS1_SERVICE_REPORT_STUB_TASK_IDS


def reset_smoke_progress() -> None:
    global _SMOKE_PARENT_PID, _SMOKE_RUN_COUNTER, _SMOKE_STARTED_AT
    _SMOKE_RUN_COUNTER = 0
    _SMOKE_STARTED_AT = time.monotonic()
    _SMOKE_PARENT_PID = os.getppid()


def _smoke_parent_is_running() -> bool:
    if _SMOKE_PARENT_PID <= 0:
        return True
    return _process_is_running(_SMOKE_PARENT_PID)


def _terminate_smoke_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=1.0)
    except _ORIGINAL_SUBPROCESS_MODULE.TimeoutExpired:
        process.kill()
        process.wait()


def run_smoke_subprocess(
    command: object, *args: object, **kwargs: object
) -> subprocess.CompletedProcess[str]:
    global _SMOKE_RUN_COUNTER
    _SMOKE_RUN_COUNTER += 1
    sequence = _SMOKE_RUN_COUNTER
    started_at = time.monotonic()
    elapsed = started_at - _SMOKE_STARTED_AT if _SMOKE_STARTED_AT > 0 else 0.0
    popen_kwargs = dict(kwargs)
    if should_use_smoke_demo_sitecustomize(
        command
    ) or should_use_smoke_wrapper_service_sitecustomize(command):
        popen_kwargs["env"] = build_smoke_demo_pythonpath_env(
            base_env=popen_kwargs.get("env"),
        )
    elif (
        should_use_smoke_wrapper_report_sitecustomize(command)
        or should_use_smoke_wrapper_service_report_sitecustomize(command)
        or should_use_smoke_root_ps1_service_report_sitecustomize(command)
    ):
        popen_kwargs["env"] = build_smoke_report_pythonpath_env(
            base_env=popen_kwargs.get("env"),
        )
    capture_output = bool(popen_kwargs.pop("capture_output", False))
    input_data = popen_kwargs.pop("input", None)
    check = bool(popen_kwargs.pop("check", False))
    timeout = popen_kwargs.pop("timeout", None)
    if capture_output:
        if "stdout" in popen_kwargs or "stderr" in popen_kwargs:
            raise ValueError(
                "stdout and stderr arguments may not be used with capture_output"
            )
        popen_kwargs["stdout"] = _ORIGINAL_SUBPROCESS_MODULE.PIPE
        popen_kwargs["stderr"] = _ORIGINAL_SUBPROCESS_MODULE.PIPE
    if input_data is not None:
        if "stdin" in popen_kwargs:
            raise ValueError("stdin and input arguments may not both be used.")
        popen_kwargs["stdin"] = _ORIGINAL_SUBPROCESS_MODULE.PIPE
    print(
        f"[tooling-smoke {sequence:03d}] start +{elapsed:.1f}s => {format_smoke_command(command)}",
        flush=True,
    )
    process = _ORIGINAL_SUBPROCESS_MODULE.Popen(command, *args, **popen_kwargs)
    deadline = None if timeout is None else started_at + float(timeout)
    stdout = None
    stderr = None
    try:
        while True:
            wait_timeout = _SMOKE_MONITOR_INTERVAL_SECONDS
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise _ORIGINAL_SUBPROCESS_MODULE.TimeoutExpired(command, timeout)
                wait_timeout = min(wait_timeout, remaining)
            try:
                stdout, stderr = process.communicate(
                    input=input_data, timeout=wait_timeout
                )
                input_data = None
                break
            except _ORIGINAL_SUBPROCESS_MODULE.TimeoutExpired:
                input_data = None
                if not _smoke_parent_is_running():
                    raise RuntimeError(
                        f"tooling smoke parent exited while running {format_smoke_command(command)}"
                    )
                continue
    except BaseException:
        _terminate_smoke_process(process)
        raise
    completed = _ORIGINAL_SUBPROCESS_MODULE.CompletedProcess(
        args=command,
        returncode=process.returncode or 0,
        stdout=stdout,
        stderr=stderr,
    )
    duration = time.monotonic() - started_at
    print(
        f"[tooling-smoke {sequence:03d}] done exit={completed.returncode} duration={duration:.1f}s",
        flush=True,
    )
    if check and completed.returncode != 0:
        raise _ORIGINAL_SUBPROCESS_MODULE.CalledProcessError(
            completed.returncode,
            command,
            output=completed.stdout,
            stderr=completed.stderr,
        )
    return completed


class _TracingSubprocessModule:
    def __init__(self, delegate: object) -> None:
        self._delegate = delegate

    def run(
        self, command: object, *args: object, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        return run_smoke_subprocess(command, *args, **kwargs)

    def __getattr__(self, name: str) -> object:
        return getattr(self._delegate, name)


subprocess = _TracingSubprocessModule(_ORIGINAL_SUBPROCESS_MODULE)

CHECKS: list[tuple[str, list[str], str]] = [
    (
        "codegen-rust",
        [PYTHON, "tools/codegen/main.py", "--target", "rust"],
        "SafeClaw codegen stub ready.",
    ),
    (
        "codegen-python",
        [PYTHON, "tools/codegen/main.py", "--target", "python"],
        "SafeClaw codegen stub ready.",
    ),
    (
        "codegen-ts",
        [PYTHON, "tools/codegen/main.py", "--target", "ts"],
        "SafeClaw codegen stub ready.",
    ),
    (
        "codegen-regenerate-all",
        [PYTHON, "tools/codegen/regenerate_all.py"],
        "SafeClaw codegen sync ready.",
    ),
    (
        "schema-diff-dir",
        [PYTHON, "tools/schema_diff/main.py", "specs", "specs"],
        "SafeClaw schema diff ready.",
    ),
    (
        "schema-diff-file",
        [
            PYTHON,
            "tools/schema_diff/main.py",
            "specs/schemas/action_tiers.json",
            "specs/schemas/action_tiers.json",
        ],
        "SafeClaw schema diff ready.",
    ),
]


def load_json_payload(
    completed: subprocess.CompletedProcess[str],
    errors: list[str],
    name: str,
    expected_exit: int,
) -> dict[str, object] | None:
    if completed.returncode != expected_exit:
        errors.append(f"{name} 执行失败: exit={completed.returncode}")

        return None

    try:
        payload = json.loads(completed.stdout)

    except json.JSONDecodeError as error:
        errors.append(f"{name} 输出不是合法 JSON: {error}")

        return None

    if not isinstance(payload, dict):
        errors.append(f"{name} 输出不是对象 JSON")

        return None

    return payload


def extract_json_error(
    payload: dict[str, object],
    errors: list[str],
    name: str,
    action: str,
) -> tuple[dict[str, object] | None, dict[str, object] | None]:
    error = payload.get("error") or {}

    details = error.get("details") or {}

    if payload.get("ok") is not False or payload.get("action") != action:
        errors.append(f"{name} 输出缺少统一错误信封")

        return None, None

    return (
        error if isinstance(error, dict) else None,
        details if isinstance(details, dict) else None,
    )


def extract_json_result(
    payload: dict[str, object],
    errors: list[str],
    name: str,
    action: str,
) -> dict[str, object] | None:
    result = payload.get("result") or {}

    if payload.get("ok") is not True or payload.get("action") != action:
        errors.append(f"{name} 输出缺少统一信封")

        return None

    if not isinstance(result, dict):
        errors.append(f"{name} result 不是对象")

        return None

    return result


def assert_verify_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
) -> None:
    if result is None:
        return

    if result.get("exit_code") != 0:
        errors.append(f"{name} missing exit_code=0")

    elif result.get("script") != "tools/checks/check_mvp_operator_flow.py":
        errors.append(f"{name} missing verify script path")

    elif not result.get("python"):
        errors.append(f"{name} missing python path")

    elif "MVP operator flow check passed." not in str(
        result.get("captured_output", "")
    ):
        errors.append(f"{name} missing verify success output")


def assert_doctor_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    expected_db_path: str,
    expected_output_path: str,
    expected_db_source: str = "flag",
    expected_output_source: str = "flag",
    expected_workspace_active: bool | None = None,
    expected_workspace_name: str | None = None,
) -> None:
    if result is None:
        return

    python_info = result.get("python") or {}

    workspace_info = result.get("workspace") or {}

    if result.get("status") != "ready":
        errors.append(f"{name} missing status=ready")

    elif result.get("failing_checks") != []:
        errors.append(f"{name} missing empty failing_checks")

    elif not isinstance(python_info, dict) or python_info.get("ok") is not True:
        errors.append(f"{name} missing python ok")

    elif not python_info.get("detail"):
        errors.append(f"{name} missing python detail")

    elif result.get("entrypoints", {}).get("cmd", {}).get("exists") is not True:
        errors.append(f"{name} missing cmd entry ok")

    elif result.get("entrypoints", {}).get("ps1", {}).get("exists") is not True:
        errors.append(f"{name} missing ps1 entry ok")

    elif result.get("entrypoints", {}).get("py", {}).get("exists") is not True:
        errors.append(f"{name} missing py entry ok")

    elif result.get("cargo", {}).get("ok") is not True:
        errors.append(f"{name} missing cargo ok")

    elif result.get("toolchain", {}).get("ok") is not True:
        errors.append(f"{name} missing toolchain ok")

    elif result.get("linker", {}).get("ok") is not True:
        errors.append(f"{name} missing linker ok")

    elif result.get("session_path") != "target\mvp\last_session.json":
        errors.append(f"{name} missing session_path")

    elif (
        not isinstance(workspace_info, dict)
        or workspace_info.get("path") != "target\mvp\workspace.json"
    ):
        errors.append(f"{name} missing workspace_path")

    elif (
        expected_workspace_active is not None
        and workspace_info.get("active") is not expected_workspace_active
    ):
        errors.append(f"{name} missing workspace active={expected_workspace_active}")

    elif (
        expected_workspace_name is None
        and expected_workspace_active is False
        and workspace_info.get("name") is not None
    ):
        errors.append(f"{name} unexpected workspace name")

    elif (
        expected_workspace_name is not None
        and workspace_info.get("name") != expected_workspace_name
    ):
        errors.append(f"{name} missing workspace name={expected_workspace_name}")

    elif result.get("db", {}).get("path") != expected_db_path:
        errors.append(f"{name} missing db path={expected_db_path}")

    elif result.get("db", {}).get("source") != expected_db_source:
        errors.append(f"{name} missing db source={expected_db_source}")

    elif result.get("output", {}).get("path") != expected_output_path:
        errors.append(f"{name} missing output path={expected_output_path}")

    elif result.get("output", {}).get("source") != expected_output_source:
        errors.append(f"{name} missing output source={expected_output_source}")

    else:
        runtime_profile = result.get("runtime_profile") or {}

        model_provider = result.get("model_provider") or {}

        sidecar = result.get("sidecar") or {}

        if not isinstance(runtime_profile, dict):
            errors.append(f"{name} missing runtime_profile")

        elif runtime_profile.get("mode") != "local_mvp":
            errors.append(f"{name} missing runtime_profile.mode=local_mvp")

        elif runtime_profile.get("offline_ready") is not True:
            errors.append(f"{name} missing runtime_profile.offline_ready=true")

        elif runtime_profile.get("llm_required") is not False:
            errors.append(f"{name} missing runtime_profile.llm_required=false")

        elif runtime_profile.get("sidecar_required") is not False:
            errors.append(f"{name} missing runtime_profile.sidecar_required=false")

        elif not isinstance(model_provider, dict):
            errors.append(f"{name} missing model_provider")

        elif model_provider.get("configured") is not False:
            errors.append(f"{name} missing model_provider.configured=false")

        elif model_provider.get("required") is not False:
            errors.append(f"{name} missing model_provider.required=false")

        elif model_provider.get("status") != "not-configured":
            errors.append(f"{name} missing model_provider.status=not-configured")

        elif model_provider.get("degradation_mode") != "local_only_ok":
            errors.append(
                f"{name} missing model_provider.degradation_mode=local_only_ok"
            )

        elif not model_provider.get("detail"):
            errors.append(f"{name} missing model_provider.detail")

        elif not isinstance(sidecar, dict):
            errors.append(f"{name} missing sidecar")

        elif sidecar.get("configured") is not False:
            errors.append(f"{name} missing sidecar.configured=false")

        elif sidecar.get("required") is not False:
            errors.append(f"{name} missing sidecar.required=false")

        elif sidecar.get("status") != "not-configured":
            errors.append(f"{name} missing sidecar.status=not-configured")

        elif not sidecar.get("detail"):
            errors.append(f"{name} missing sidecar.detail")


def assert_preflight_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    expected_requested_action: str,
    expected_known: bool,
    expected_action_class: str,
    expected_tier: str,
    expected_writes_state: bool,
    expected_permission_context_source: str,
    expected_target_scope: str,
    expected_requires_write: bool,
    expected_doctor_bypass: bool,
    expected_permission_context_applied: bool,
    expected_permission_tier: str,
    expected_permission_policy: str,
    expected_permission_reason: str,
    expected_permission_enforced: bool,
    expected_action_allowed: bool,
    expected_action_decision: str,
    expected_action_reason: str,
    expected_allowed: bool,
    expected_decision: str,
    expected_offline_ready: bool,
    expected_degradation_mode: str,
    expected_reason: str,
    expected_requires_model: bool = False,
    expected_requires_sidecar: bool = False,
    expected_error_code: str | None = None,
) -> None:
    if result is None:
        return

    runtime_profile = result.get("runtime_profile") or {}

    model_provider = result.get("model_provider") or {}

    sidecar = result.get("sidecar") or {}

    if result.get("requested_action") != expected_requested_action:
        errors.append(f"{name} missing requested_action={expected_requested_action}")

    elif result.get("known") is not expected_known:
        errors.append(f"{name} missing known={expected_known}")

    elif result.get("action_class") != expected_action_class:
        errors.append(f"{name} missing action_class={expected_action_class}")

    elif result.get("tier") != expected_tier:
        errors.append(f"{name} missing tier={expected_tier}")

    elif result.get("writes_state") is not expected_writes_state:
        errors.append(f"{name} missing writes_state={expected_writes_state}")

    elif result.get("permission_context_source") != expected_permission_context_source:
        errors.append(
            f"{name} missing permission_context_source={expected_permission_context_source}"
        )

    elif result.get("target_scope") != expected_target_scope:
        errors.append(f"{name} missing target_scope={expected_target_scope}")

    elif result.get("requires_write") is not expected_requires_write:
        errors.append(f"{name} missing requires_write={expected_requires_write}")

    elif result.get("doctor_bypass") is not expected_doctor_bypass:
        errors.append(f"{name} missing doctor_bypass={expected_doctor_bypass}")

    elif (
        result.get("permission_context_applied")
        is not expected_permission_context_applied
    ):
        errors.append(
            f"{name} missing permission_context_applied={expected_permission_context_applied}"
        )

    elif result.get("permission_tier") != expected_permission_tier:
        errors.append(f"{name} missing permission_tier={expected_permission_tier}")

    elif result.get("permission_policy") != expected_permission_policy:
        errors.append(f"{name} missing permission_policy={expected_permission_policy}")

    elif result.get("permission_reason") != expected_permission_reason:
        errors.append(f"{name} missing permission_reason={expected_permission_reason}")

    elif result.get("permission_enforced") is not expected_permission_enforced:
        errors.append(
            f"{name} missing permission_enforced={expected_permission_enforced}"
        )

    elif result.get("action_allowed") is not expected_action_allowed:
        errors.append(f"{name} missing action_allowed={expected_action_allowed}")

    elif result.get("action_decision") != expected_action_decision:
        errors.append(f"{name} missing action_decision={expected_action_decision}")

    elif result.get("action_reason") != expected_action_reason:
        errors.append(f"{name} missing action_reason={expected_action_reason}")

    elif result.get("allowed") is not expected_allowed:
        errors.append(f"{name} missing allowed={expected_allowed}")

    elif result.get("decision") != expected_decision:
        errors.append(f"{name} missing decision={expected_decision}")

    elif result.get("offline_ready") is not expected_offline_ready:
        errors.append(f"{name} missing offline_ready={expected_offline_ready}")

    elif result.get("requires_model") is not expected_requires_model:
        errors.append(f"{name} missing requires_model={expected_requires_model}")

    elif result.get("requires_sidecar") is not expected_requires_sidecar:
        errors.append(f"{name} missing requires_sidecar={expected_requires_sidecar}")

    elif result.get("degradation_mode") != expected_degradation_mode:
        errors.append(f"{name} missing degradation_mode={expected_degradation_mode}")

    elif result.get("reason") != expected_reason:
        errors.append(f"{name} missing reason={expected_reason}")

    elif (
        expected_error_code is not None
        and result.get("error_code") != expected_error_code
    ):
        errors.append(f"{name} missing error_code={expected_error_code}")

    elif not result.get("detail"):
        errors.append(f"{name} missing detail")

    elif (
        not isinstance(runtime_profile, dict)
        or runtime_profile.get("mode") != "local_mvp"
    ):
        errors.append(f"{name} missing runtime_profile.mode=local_mvp")

    elif runtime_profile.get("offline_ready") is not True:
        errors.append(f"{name} missing runtime_profile.offline_ready=true")

    elif (
        not isinstance(model_provider, dict)
        or model_provider.get("status") != "not-configured"
    ):
        errors.append(f"{name} missing model_provider.status=not-configured")

    elif model_provider.get("degradation_mode") != "local_only_ok":
        errors.append(f"{name} missing model_provider.degradation_mode=local_only_ok")

    elif not isinstance(sidecar, dict) or sidecar.get("status") != "not-configured":
        errors.append(f"{name} missing sidecar.status=not-configured")

    elif sidecar.get("required") is not False:
        errors.append(f"{name} missing sidecar.required=false")

    elif sidecar.get("configured") is not False:
        errors.append(f"{name} missing sidecar.configured=false")

    elif not sidecar.get("detail"):
        errors.append(f"{name} missing sidecar.detail")

    elif "budget" in result:
        errors.append(f"{name} unexpectedly exposed budget without runtime source")


def assert_workspace_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    expected_active: bool,
    expected_name: str | None,
    expected_db_path: str,
    expected_output_path: str,
    expected_changed: bool | None = None,
) -> None:
    if result is None:
        return

    normalized_db = str(result.get("db") or "").replace("/", chr(92))

    normalized_output = str(result.get("output") or "").replace("/", chr(92))

    expected_db = expected_db_path.replace("/", chr(92))

    expected_output = expected_output_path.replace("/", chr(92))

    if result.get("active") is not expected_active:
        errors.append(f"{name} missing active={expected_active}")

    elif result.get("name") != expected_name:
        errors.append(f"{name} missing name={expected_name}")

    elif normalized_db != expected_db:
        errors.append(f"{name} missing db={expected_db_path}")

    elif normalized_output != expected_output:
        errors.append(f"{name} missing output={expected_output_path}")

    elif result.get("path") != "target\mvp\workspace.json":
        errors.append(f"{name} missing workspace path")

    elif expected_changed is not None and result.get("changed") is not expected_changed:
        errors.append(f"{name} missing changed={expected_changed}")


def assert_service_demo_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
) -> None:
    if result is None:
        return

    resolved_run = result.get("resolved_run") or {}

    resolved_governance = result.get("resolved_governance") or {}

    confirmation_governance = result.get("confirmation_governance") or {}

    resolved_tasks = result.get("resolved_tasks") or []

    confirmation_tasks = result.get("confirmation_tasks") or []

    captured_output = str(result.get("captured_output") or "")

    if result.get("example") != "worker_service_governance_demo":
        errors.append(f"{name} missing example name")

    elif not isinstance(resolved_run, dict) or resolved_run.get("executed") != 2:
        errors.append(f"{name} missing resolved_run.executed=2")

    elif resolved_run.get("parked") != 0:
        errors.append(f"{name} missing resolved_run.parked=0")

    elif (
        not isinstance(resolved_governance, dict)
        or resolved_governance.get("resolved") != 2
    ):
        errors.append(f"{name} missing resolved_governance.resolved=2")

    elif resolved_governance.get("confirmation") != 0:
        errors.append(f"{name} missing resolved_governance.confirmation=0")

    elif (
        not isinstance(confirmation_governance, dict)
        or confirmation_governance.get("confirmation") != 1
    ):
        errors.append(f"{name} missing confirmation_governance.confirmation=1")

    elif confirmation_governance.get("manual_review") != 0:
        errors.append(f"{name} missing confirmation_governance.manual_review=0")

    elif (
        not isinstance(resolved_tasks, list)
        or "task-worker-service-governance-a" not in resolved_tasks
    ):
        errors.append(f"{name} missing resolved task a")

    elif "task-worker-service-governance-b" not in resolved_tasks:
        errors.append(f"{name} missing resolved task b")

    elif (
        not isinstance(confirmation_tasks, list)
        or "task-worker-service-governance-confirmation" not in confirmation_tasks
    ):
        errors.append(f"{name} missing confirmation task")

    elif not str(result.get("db_path") or "").lower().endswith(".db"):
        errors.append(f"{name} missing db_path")

    elif (
        "[demo] service governance resolved => total=2 resolved=2 confirmation=0 manual_review=0"
        not in captured_output
    ):
        errors.append(f"{name} missing resolved governance output")

    elif (
        "[demo] service governance confirmation => total=1 resolved=0 confirmation=1 manual_review=0"
        not in captured_output
    ):
        errors.append(f"{name} missing confirmation governance output")


def assert_service_status_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    expected_db: str,
    expected_db_source: str,
    expected_task_id: str,
    expected_limit: int = 5,
    expected_target_scope: str | None = None,
    expected_requires_write: bool | None = None,
    expected_doctor_bypass: bool | None = None,
    expected_permission_tier: str | None = None,
    expected_permission_policy: str | None = None,
    expected_permission_reason: str | None = None,
    expected_lease_state: str | None = None,
    expected_lease_freshness: str | None = None,
    expected_lease_owner_id: str | None = None,
    expected_lease_fencing_token: int | None = None,
    expected_heartbeat_freshness: str | None = None,
    expected_heartbeat_status: str | None = None,
    expected_heartbeat_interval_ms: int | None = None,
    expected_heartbeat_event_driven: bool | None = None,
    expected_heartbeat_reason: str | None = None,
    expect_heartbeat_latest_updated_at_present: bool = False,
    expect_heartbeat_latest_updated_at_absent: bool = False,
    expect_heartbeat_latest_age_ms_present: bool = False,
    expect_heartbeat_latest_age_ms_absent: bool = False,
    expected_next_action: str | None = None,
    expected_next_command: str | None = None,
    expected_next_reason: str | None = None,
    expected_next_blocker: str | None = None,
    expected_next_summary: str | None = None,
    expected_coordination_status: str | None = None,
    expected_coordination_reason: str | None = None,
    expected_coordination_summary: str | None = None,
    expected_service_coordination_status: str | None = None,
    expected_service_coordination_reason: str | None = None,
    expected_service_coordination_summary: str | None = None,
) -> None:
    if result is None:
        return

    queue = result.get("queue") or {}

    workers = result.get("workers") or {}

    effects = result.get("effects") or {}

    probes = result.get("probes") or {}

    heartbeat = result.get("heartbeat") or {}

    coordination = result.get("coordination") or {}

    recent_tasks = result.get("recent_tasks") or []

    current_session = result.get("current_session") or {}

    runtime_profile = result.get("runtime_profile") or {}

    model_provider = result.get("model_provider") or {}

    sidecar = result.get("sidecar") or {}

    offline_gate = result.get("offline_gate") or {}

    actual_db = str(result.get("db") or "").replace("\\", "/")

    normalized_expected_db = expected_db.replace("\\", "/")

    worker_succeeded = (
        None
        if not isinstance(workers, dict)
        else (
            workers.get("succeeded")
            if "succeeded" in workers
            else workers.get("Succeeded")
        )
    )

    effect_executed = (
        None
        if not isinstance(effects, dict)
        else (
            effects.get("executed")
            if "executed" in effects
            else effects.get("Executed")
        )
    )

    if actual_db != normalized_expected_db:
        errors.append(f"{name} missing db={expected_db}")

    elif result.get("db_source") != expected_db_source:
        errors.append(f"{name} missing db_source={expected_db_source}")

    elif result.get("limit") != expected_limit:
        errors.append(f"{name} missing limit={expected_limit}")

    elif result.get("current_db") is not True:
        errors.append(f"{name} missing current_db=true")

    elif (
        not isinstance(current_session, dict)
        or current_session.get("task_id") != expected_task_id
    ):
        errors.append(f"{name} missing current_session {expected_task_id}")

    elif not isinstance(queue, dict) or queue.get("queued") != 0:
        errors.append(f"{name} missing queue.queued=0")

    elif queue.get("active") != 0:
        errors.append(f"{name} missing queue.active=0")

    elif queue.get("expired") != 0:
        errors.append(f"{name} missing queue.expired=0")

    elif queue.get("completed") != 1:
        errors.append(f"{name} missing queue.completed=1")

    elif worker_succeeded != 1:
        errors.append(f"{name} missing workers.succeeded=1")

    elif effect_executed != 1:
        errors.append(f"{name} missing effects.executed=1")

    elif not isinstance(probes, dict) or probes.get("none") != 1:
        errors.append(f"{name} missing probes.none=1")

    elif (
        expected_heartbeat_freshness is not None
        and heartbeat.get("latest_freshness") != expected_heartbeat_freshness
    ):
        errors.append(
            f"{name} missing heartbeat.latest_freshness={expected_heartbeat_freshness}"
        )

    elif (
        expected_heartbeat_status is not None
        and heartbeat.get("status") != expected_heartbeat_status
    ):
        errors.append(f"{name} missing heartbeat.status={expected_heartbeat_status}")

    elif (
        expected_heartbeat_interval_ms is not None
        and heartbeat.get("interval_ms") != expected_heartbeat_interval_ms
    ):
        errors.append(
            f"{name} missing heartbeat.interval_ms={expected_heartbeat_interval_ms}"
        )

    elif (
        expected_heartbeat_event_driven is not None
        and heartbeat.get("event_driven") is not expected_heartbeat_event_driven
    ):
        errors.append(
            f"{name} missing heartbeat.event_driven={expected_heartbeat_event_driven}"
        )

    elif (
        expected_heartbeat_reason is not None
        and heartbeat.get("reason") != expected_heartbeat_reason
    ):
        errors.append(f"{name} missing heartbeat.reason={expected_heartbeat_reason}")

    elif expect_heartbeat_latest_updated_at_present and not heartbeat.get(
        "latest_updated_at"
    ):
        errors.append(f"{name} missing heartbeat.latest_updated_at")

    elif (
        expect_heartbeat_latest_updated_at_absent
        and heartbeat.get("latest_updated_at") is not None
    ):
        errors.append(f"{name} expected heartbeat.latest_updated_at=None")

    elif expect_heartbeat_latest_age_ms_present and not isinstance(
        heartbeat.get("latest_age_ms"), int
    ):
        errors.append(f"{name} missing heartbeat.latest_age_ms int")

    elif (
        expect_heartbeat_latest_age_ms_absent
        and heartbeat.get("latest_age_ms") is not None
    ):
        errors.append(f"{name} expected heartbeat.latest_age_ms=None")

    elif (
        expected_service_coordination_status is not None
        and coordination.get("status") != expected_service_coordination_status
    ):
        errors.append(
            f"{name} missing coordination.status={expected_service_coordination_status}"
        )

    elif (
        expected_service_coordination_reason is not None
        and coordination.get("reason") != expected_service_coordination_reason
    ):
        errors.append(
            f"{name} missing coordination.reason={expected_service_coordination_reason}"
        )

    elif (
        expected_service_coordination_summary is not None
        and coordination.get("summary") != expected_service_coordination_summary
    ):
        errors.append(
            f"{name} missing coordination.summary={expected_service_coordination_summary}"
        )

    elif (
        not isinstance(runtime_profile, dict)
        or runtime_profile.get("mode") != "local_mvp"
    ):
        errors.append(f"{name} missing runtime_profile.mode=local_mvp")

    elif runtime_profile.get("offline_ready") is not True:
        errors.append(f"{name} missing runtime_profile.offline_ready=true")

    elif runtime_profile.get("llm_required") is not False:
        errors.append(f"{name} missing runtime_profile.llm_required=false")

    elif runtime_profile.get("sidecar_required") is not False:
        errors.append(f"{name} missing runtime_profile.sidecar_required=false")

    elif not runtime_profile.get("detail"):
        errors.append(f"{name} missing runtime_profile.detail")

    elif (
        not isinstance(model_provider, dict)
        or model_provider.get("status") != "not-configured"
    ):
        errors.append(f"{name} missing model_provider.status=not-configured")

    elif model_provider.get("required") is not False:
        errors.append(f"{name} missing model_provider.required=false")

    elif model_provider.get("configured") is not False:
        errors.append(f"{name} missing model_provider.configured=false")

    elif model_provider.get("degradation_mode") != "local_only_ok":
        errors.append(f"{name} missing model_provider.degradation_mode=local_only_ok")

    elif not model_provider.get("detail"):
        errors.append(f"{name} missing model_provider.detail")

    elif not isinstance(sidecar, dict) or sidecar.get("status") != "not-configured":
        errors.append(f"{name} missing sidecar.status=not-configured")

    elif sidecar.get("required") is not False:
        errors.append(f"{name} missing sidecar.required=false")

    elif sidecar.get("configured") is not False:
        errors.append(f"{name} missing sidecar.configured=false")

    elif not sidecar.get("detail"):
        errors.append(f"{name} missing sidecar.detail")

    elif not isinstance(offline_gate, dict) or offline_gate.get("status") != "blocked":
        errors.append(f"{name} missing offline_gate.status=blocked")

    elif offline_gate.get("reason") != "ERR_AI_PROVIDER_UNAVAILABLE":
        errors.append(f"{name} missing offline_gate.reason=ERR_AI_PROVIDER_UNAVAILABLE")

    elif offline_gate.get("summary") != "ai_actions_require_provider":
        errors.append(
            f"{name} missing offline_gate.summary=ai_actions_require_provider"
        )

    elif offline_gate.get("requested_action") != "ai-reason":
        errors.append(f"{name} missing offline_gate.requested_action=ai-reason")

    elif offline_gate.get("requires_model") is not True:
        errors.append(f"{name} missing offline_gate.requires_model=true")

    elif offline_gate.get("requires_sidecar") is not True:
        errors.append(f"{name} missing offline_gate.requires_sidecar=true")

    elif (
        offline_gate.get("next_command") != "safeclaw.cmd preflight --action ai-reason"
    ):
        errors.append(
            f"{name} missing offline_gate.next_command=safeclaw.cmd preflight --action ai-reason"
        )

    elif offline_gate.get("error_code") != "ERR_AI_PROVIDER_UNAVAILABLE":
        errors.append(
            f"{name} missing offline_gate.error_code=ERR_AI_PROVIDER_UNAVAILABLE"
        )

    elif "budget" in result:
        errors.append(f"{name} unexpectedly exposed budget without runtime source")

    elif (
        not isinstance(recent_tasks, list)
        or not recent_tasks
        or recent_tasks[0].get("task_id") != expected_task_id
    ):
        errors.append(f"{name} missing recent task {expected_task_id}")

    elif recent_tasks[0].get("current") is not True:
        errors.append(f"{name} missing recent current=true")

    elif (
        expected_target_scope is not None
        and recent_tasks[0].get("target_scope") != expected_target_scope
    ):
        errors.append(f"{name} missing recent target_scope={expected_target_scope}")

    elif (
        expected_requires_write is not None
        and recent_tasks[0].get("requires_write") != expected_requires_write
    ):
        errors.append(f"{name} missing recent requires_write={expected_requires_write}")

    elif (
        expected_doctor_bypass is not None
        and recent_tasks[0].get("doctor_bypass") != expected_doctor_bypass
    ):
        errors.append(f"{name} missing recent doctor_bypass={expected_doctor_bypass}")

    elif (
        expected_permission_tier is not None
        and recent_tasks[0].get("permission_tier") != expected_permission_tier
    ):
        errors.append(
            f"{name} missing recent permission_tier={expected_permission_tier}"
        )

    elif (
        expected_permission_policy is not None
        and recent_tasks[0].get("permission_policy") != expected_permission_policy
    ):
        errors.append(
            f"{name} missing recent permission_policy={expected_permission_policy}"
        )

    elif (
        expected_permission_reason is not None
        and recent_tasks[0].get("permission_reason") != expected_permission_reason
    ):
        errors.append(
            f"{name} missing recent permission_reason={expected_permission_reason}"
        )

    elif (
        expected_lease_state is not None
        and recent_tasks[0].get("lease_state") != expected_lease_state
    ):
        errors.append(f"{name} missing recent lease_state={expected_lease_state}")

    elif (
        expected_lease_freshness is not None
        and recent_tasks[0].get("lease_freshness") != expected_lease_freshness
    ):
        errors.append(
            f"{name} missing recent lease_freshness={expected_lease_freshness}"
        )

    elif (
        expected_lease_owner_id is not None
        and recent_tasks[0].get("lease_owner_id") != expected_lease_owner_id
    ):
        errors.append(f"{name} missing recent lease_owner_id={expected_lease_owner_id}")

    elif (
        expected_lease_fencing_token is not None
        and recent_tasks[0].get("lease_fencing_token") != expected_lease_fencing_token
    ):
        errors.append(
            f"{name} missing recent lease_fencing_token={expected_lease_fencing_token}"
        )

    elif (
        expected_next_action is not None
        and recent_tasks[0].get("next_action") != expected_next_action
    ):
        errors.append(f"{name} missing recent next_action={expected_next_action}")

    elif (
        expected_next_command is not None
        and recent_tasks[0].get("next_command") != expected_next_command
    ):
        errors.append(f"{name} missing recent next_command={expected_next_command}")

    elif (
        expected_next_reason is not None
        and recent_tasks[0].get("next_reason") != expected_next_reason
    ):
        errors.append(f"{name} missing recent next_reason={expected_next_reason}")

    elif (
        expected_next_blocker is not None
        and recent_tasks[0].get("next_blocker") != expected_next_blocker
    ):
        errors.append(f"{name} missing recent next_blocker={expected_next_blocker}")

    elif (
        expected_next_summary is not None
        and recent_tasks[0].get("next_summary") != expected_next_summary
    ):
        errors.append(f"{name} missing recent next_summary={expected_next_summary}")

    elif (
        expected_coordination_status is not None
        and recent_tasks[0].get("coordination_status") != expected_coordination_status
    ):
        errors.append(
            f"{name} missing recent coordination_status={expected_coordination_status}"
        )

    elif (
        expected_coordination_reason is not None
        and recent_tasks[0].get("coordination_reason") != expected_coordination_reason
    ):
        errors.append(
            f"{name} missing recent coordination_reason={expected_coordination_reason}"
        )

    elif (
        expected_coordination_summary is not None
        and recent_tasks[0].get("coordination_summary") != expected_coordination_summary
    ):
        errors.append(
            f"{name} missing recent coordination_summary={expected_coordination_summary}"
        )


def assert_service_run_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    expected_db: str,
    expected_db_source: str,
    expected_task_id: str,
    expected_limit: int,
    expected_steps: list[str] | None = None,
    expect_report_payload: bool = False,
    expected_run_db_source: str = "flag",
    expected_run_task_context_source: str = "flag",
    expected_preflight_context_source: str | None = None,
) -> None:
    if result is None:
        return

    expected_steps = expected_steps or ["run", "service-status"]

    steps = result.get("steps") or []

    remembered_session = result.get("remembered_session") or {}

    session = result.get("session") or {}

    run_payload = result.get("run") or {}

    if (
        not isinstance(steps, list)
        or [step.get("action") for step in steps] != expected_steps
    ):
        errors.append(f"{name} step sequence is incorrect")

        return

    if (
        not isinstance(remembered_session, dict)
        or remembered_session.get("task_id") != expected_task_id
    ):
        errors.append(f"{name} missing remembered_session {expected_task_id}")

        return

    if not isinstance(session, dict) or session.get("task_id") != expected_task_id:
        errors.append(f"{name} missing session alias {expected_task_id}")

        return

    assert_matching_session_alias(result, errors, name)

    if not isinstance(run_payload, dict):
        errors.append(f"{name} missing nested run payload")

        return

    saved_session = run_payload.get("saved_session") or {}

    nested_remembered_session = run_payload.get("remembered_session") or {}

    if (
        not isinstance(saved_session, dict)
        or saved_session.get("task_id") != expected_task_id
    ):
        errors.append(f"{name} nested run missing saved_session {expected_task_id}")

        return

    if (
        not isinstance(nested_remembered_session, dict)
        or nested_remembered_session.get("task_id") != expected_task_id
    ):
        errors.append(
            f"{name} nested run missing remembered_session {expected_task_id}"
        )

        return

    expected_step_hints: list[tuple[str, dict[str, str]]] = []

    if expected_steps and expected_steps[0] == "preflight":
        expected_step_hints.append(
            (
                "preflight",
                {"permission_context": expected_preflight_context_source or "none"},
            )
        )

        expected_step_hints.append(
            (
                "run",
                {
                    "db": expected_run_db_source,
                    "task_context": expected_run_task_context_source,
                },
            )
        )

        expected_step_hints.append(
            ("service-status", {"db": expected_db_source, "task_context": "session"})
        )

    else:
        expected_step_hints.append(
            (
                "run",
                {
                    "db": expected_run_db_source,
                    "task_context": expected_run_task_context_source,
                },
            )
        )

        expected_step_hints.append(
            ("service-status", {"db": expected_db_source, "task_context": "session"})
        )

    assert_step_source_hints(
        steps[: len(expected_step_hints)],
        errors,
        name,
        expected_step_hints,
    )

    if expect_report_payload:
        report_payload = result.get("report") or {}

        nested_report_session = report_payload.get("remembered_session") or {}

        prepared_report = report_payload.get("prepared") or []

        if not isinstance(report_payload, dict):
            errors.append(f"{name} missing nested report payload")

            return

        if (
            not isinstance(prepared_report, list)
            or not prepared_report
            or prepared_report[0] != "report"
        ):
            errors.append(f"{name} nested report missing prepared report")

            return

        if (
            not isinstance(nested_report_session, dict)
            or nested_report_session.get("task_id") != expected_task_id
        ):
            errors.append(
                f"{name} nested report missing remembered_session {expected_task_id}"
            )

            return

    service_status = result.get("service_status")

    if not isinstance(service_status, dict):
        errors.append(f"{name} missing service_status payload")

        return

    assert_service_status_json_result(
        service_status,
        errors,
        f"{name} service_status",
        expected_db=expected_db,
        expected_db_source=expected_db_source,
        expected_task_id=expected_task_id,
        expected_limit=expected_limit,
    )


def assert_service_retry_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    expected_db: str,
    expected_db_source: str,
    expected_task_id: str,
    expected_limit: int,
    expected_steps: list[str] | None = None,
    expect_report_payload: bool = False,
) -> None:
    if result is None:
        return

    expected_steps = expected_steps or ["retry", "service-status"]

    steps = result.get("steps") or []

    remembered_session = result.get("remembered_session") or {}

    session = result.get("session") or {}

    retry_payload = result.get("retry") or {}

    if (
        not isinstance(steps, list)
        or [step.get("action") for step in steps] != expected_steps
    ):
        errors.append(f"{name} step sequence is incorrect")

        return

    if (
        not isinstance(remembered_session, dict)
        or remembered_session.get("task_id") != expected_task_id
    ):
        errors.append(f"{name} missing remembered_session {expected_task_id}")

        return

    if not isinstance(session, dict) or session.get("task_id") != expected_task_id:
        errors.append(f"{name} missing session alias {expected_task_id}")

        return

    assert_matching_session_alias(result, errors, name)

    if not isinstance(retry_payload, dict):
        errors.append(f"{name} missing nested retry payload")

        return

    prepared = retry_payload.get("prepared") or []

    nested_remembered_session = retry_payload.get("remembered_session") or {}

    if not isinstance(prepared, list) or not prepared or prepared[0] != "retry":
        errors.append(f"{name} nested retry missing prepared retry")

        return

    if retry_payload.get("saved_session") is not None:
        errors.append(f"{name} nested retry should not save session")

        return

    if (
        not isinstance(nested_remembered_session, dict)
        or nested_remembered_session.get("task_id") != expected_task_id
    ):
        errors.append(
            f"{name} nested retry missing remembered_session {expected_task_id}"
        )

        return

    assert_step_source_hints(
        steps[:2],
        errors,
        name,
        [
            ("retry", {"db": expected_db_source, "task_context": "flag"}),
            ("service-status", {"db": expected_db_source, "task_context": "session"}),
        ],
    )

    if expect_report_payload:
        report_payload = result.get("report") or {}

        nested_report_session = report_payload.get("remembered_session") or {}

        prepared_report = report_payload.get("prepared") or []

        if not isinstance(report_payload, dict):
            errors.append(f"{name} missing nested report payload")

            return

        if (
            not isinstance(prepared_report, list)
            or not prepared_report
            or prepared_report[0] != "report"
        ):
            errors.append(f"{name} nested report missing prepared report")

            return

        if (
            not isinstance(nested_report_session, dict)
            or nested_report_session.get("task_id") != expected_task_id
        ):
            errors.append(
                f"{name} nested report missing remembered_session {expected_task_id}"
            )

            return

    service_status = result.get("service_status")

    if not isinstance(service_status, dict):
        errors.append(f"{name} missing service_status payload")

        return

    assert_service_status_json_result(
        service_status,
        errors,
        f"{name} service_status",
        expected_db=expected_db,
        expected_db_source=expected_db_source,
        expected_task_id=expected_task_id,
        expected_limit=expected_limit,
    )


def assert_service_recover_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    expected_db: str,
    expected_db_source: str,
    expected_task_id: str,
    expected_limit: int,
    expected_steps: list[str] | None = None,
    expect_report_payload: bool = False,
) -> None:
    if result is None:
        return

    expected_steps = expected_steps or ["recover", "service-status"]

    steps = result.get("steps") or []

    remembered_session = result.get("remembered_session") or {}

    session = result.get("session") or {}

    recover_payload = result.get("recover") or {}

    if (
        not isinstance(steps, list)
        or [step.get("action") for step in steps] != expected_steps
    ):
        errors.append(f"{name} step sequence is incorrect")

        return

    if (
        not isinstance(remembered_session, dict)
        or remembered_session.get("task_id") != expected_task_id
    ):
        errors.append(f"{name} missing remembered_session {expected_task_id}")

        return

    if not isinstance(session, dict) or session.get("task_id") != expected_task_id:
        errors.append(f"{name} missing session alias {expected_task_id}")

        return

    assert_matching_session_alias(result, errors, name)

    if not isinstance(recover_payload, dict):
        errors.append(f"{name} missing nested recover payload")

        return

    prepared = recover_payload.get("prepared") or []

    nested_remembered_session = recover_payload.get("remembered_session") or {}

    if not isinstance(prepared, list) or not prepared or prepared[0] != "recover":
        errors.append(f"{name} nested recover missing prepared recover")

        return

    if recover_payload.get("saved_session") is not None:
        errors.append(f"{name} nested recover should not save session")

        return

    if (
        not isinstance(nested_remembered_session, dict)
        or nested_remembered_session.get("task_id") != expected_task_id
    ):
        errors.append(
            f"{name} nested recover missing remembered_session {expected_task_id}"
        )

        return

    assert_step_source_hints(
        steps[:2],
        errors,
        name,
        [
            ("recover", {"db": expected_db_source, "task_context": "flag"}),
            ("service-status", {"db": expected_db_source, "task_context": "session"}),
        ],
    )

    if expect_report_payload:
        report_payload = result.get("report") or {}

        nested_report_session = report_payload.get("remembered_session") or {}

        prepared_report = report_payload.get("prepared") or []

        if not isinstance(report_payload, dict):
            errors.append(f"{name} missing nested report payload")

            return

        if (
            not isinstance(prepared_report, list)
            or not prepared_report
            or prepared_report[0] != "report"
        ):
            errors.append(f"{name} nested report missing prepared report")

            return

        if (
            not isinstance(nested_report_session, dict)
            or nested_report_session.get("task_id") != expected_task_id
        ):
            errors.append(
                f"{name} nested report missing remembered_session {expected_task_id}"
            )

            return

    service_status = result.get("service_status")

    if not isinstance(service_status, dict):
        errors.append(f"{name} missing service_status payload")

        return

    assert_service_status_json_result(
        service_status,
        errors,
        f"{name} service_status",
        expected_db=expected_db,
        expected_db_source=expected_db_source,
        expected_task_id=expected_task_id,
        expected_limit=expected_limit,
    )


def assert_service_resume_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    expected_db: str,
    expected_db_source: str,
    expected_task_id: str,
    expected_limit: int,
    expected_steps: list[str] | None = None,
    expect_report_payload: bool = False,
) -> None:
    if result is None:
        return

    expected_steps = expected_steps or ["resume", "service-status"]

    steps = result.get("steps") or []

    remembered_session = result.get("remembered_session") or {}

    session = result.get("session") or {}

    resume_payload = result.get("resume") or {}

    if (
        not isinstance(steps, list)
        or [step.get("action") for step in steps] != expected_steps
    ):
        errors.append(f"{name} step sequence is incorrect")

        return

    if (
        not isinstance(remembered_session, dict)
        or remembered_session.get("task_id") != expected_task_id
    ):
        errors.append(f"{name} missing remembered_session {expected_task_id}")

        return

    if not isinstance(session, dict) or session.get("task_id") != expected_task_id:
        errors.append(f"{name} missing session alias {expected_task_id}")

        return

    assert_matching_session_alias(result, errors, name)

    if not isinstance(resume_payload, dict):
        errors.append(f"{name} missing nested resume payload")

        return

    prepared = resume_payload.get("prepared") or []

    nested_remembered_session = resume_payload.get("remembered_session") or {}

    if not isinstance(prepared, list) or not prepared or prepared[0] != "resume":
        errors.append(f"{name} nested resume missing prepared resume")

        return

    if resume_payload.get("saved_session") is not None:
        errors.append(f"{name} nested resume should not save session")

        return

    if (
        not isinstance(nested_remembered_session, dict)
        or nested_remembered_session.get("task_id") != expected_task_id
    ):
        errors.append(
            f"{name} nested resume missing remembered_session {expected_task_id}"
        )

        return

    assert_step_source_hints(
        steps[:2],
        errors,
        name,
        [
            ("resume", {"db": expected_db_source, "task_context": "flag"}),
            ("service-status", {"db": expected_db_source, "task_context": "session"}),
        ],
    )

    if expect_report_payload:
        report_payload = result.get("report") or {}

        nested_report_session = report_payload.get("remembered_session") or {}

        prepared_report = report_payload.get("prepared") or []

        if not isinstance(report_payload, dict):
            errors.append(f"{name} missing nested report payload")

            return

        if (
            not isinstance(prepared_report, list)
            or not prepared_report
            or prepared_report[0] != "report"
        ):
            errors.append(f"{name} nested report missing prepared report")

            return

        if (
            not isinstance(nested_report_session, dict)
            or nested_report_session.get("task_id") != expected_task_id
        ):
            errors.append(
                f"{name} nested report missing remembered_session {expected_task_id}"
            )

            return

    service_status = result.get("service_status")

    if not isinstance(service_status, dict):
        errors.append(f"{name} missing service_status payload")

        return

    assert_service_status_json_result(
        service_status,
        errors,
        f"{name} service_status",
        expected_db=expected_db,
        expected_db_source=expected_db_source,
        expected_task_id=expected_task_id,
        expected_limit=expected_limit,
    )


def assert_service_reconcile_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    expected_db: str,
    expected_db_source: str,
    expected_task_id: str,
    expected_limit: int,
    expected_decision: str,
    expected_steps: list[str] | None = None,
    expect_report_payload: bool = False,
) -> None:
    if result is None:
        return

    expected_steps = expected_steps or ["reconcile", "service-status"]

    steps = result.get("steps") or []

    remembered_session = result.get("remembered_session") or {}

    session = result.get("session") or {}

    reconcile_payload = result.get("reconcile") or {}

    if (
        not isinstance(steps, list)
        or [step.get("action") for step in steps] != expected_steps
    ):
        errors.append(f"{name} step sequence is incorrect")

        return

    if (
        not isinstance(remembered_session, dict)
        or remembered_session.get("task_id") != expected_task_id
    ):
        errors.append(f"{name} missing remembered_session {expected_task_id}")

        return

    if not isinstance(session, dict) or session.get("task_id") != expected_task_id:
        errors.append(f"{name} missing session alias {expected_task_id}")

        return

    assert_matching_session_alias(result, errors, name)

    if not isinstance(reconcile_payload, dict):
        errors.append(f"{name} missing nested reconcile payload")

        return

    prepared = reconcile_payload.get("prepared") or []

    nested_remembered_session = reconcile_payload.get("remembered_session") or {}

    if not isinstance(prepared, list) or not prepared or prepared[0] != "reconcile":
        errors.append(f"{name} nested reconcile missing prepared reconcile")

        return

    if "--decision" not in prepared:
        errors.append(f"{name} nested reconcile missing --decision")

        return

    if prepared[prepared.index("--decision") + 1] != expected_decision:
        errors.append(f"{name} nested reconcile missing --decision {expected_decision}")

        return

    if reconcile_payload.get("saved_session") is not None:
        errors.append(f"{name} nested reconcile should not save session")

        return

    if (
        not isinstance(nested_remembered_session, dict)
        or nested_remembered_session.get("task_id") != expected_task_id
    ):
        errors.append(
            f"{name} nested reconcile missing remembered_session {expected_task_id}"
        )

        return

    assert_step_source_hints(
        steps[:2],
        errors,
        name,
        [
            ("reconcile", {"db": expected_db_source, "task_context": "flag"}),
            ("service-status", {"db": expected_db_source, "task_context": "session"}),
        ],
    )

    if expect_report_payload:
        report_payload = result.get("report") or {}

        nested_report_session = report_payload.get("remembered_session") or {}

        prepared_report = report_payload.get("prepared") or []

        if not isinstance(report_payload, dict):
            errors.append(f"{name} missing nested report payload")

            return

        if (
            not isinstance(prepared_report, list)
            or not prepared_report
            or prepared_report[0] != "report"
        ):
            errors.append(f"{name} nested report missing prepared report")

            return

        if (
            not isinstance(nested_report_session, dict)
            or nested_report_session.get("task_id") != expected_task_id
        ):
            errors.append(
                f"{name} nested report missing remembered_session {expected_task_id}"
            )

            return

    service_status = result.get("service_status")

    if not isinstance(service_status, dict):
        errors.append(f"{name} missing service_status payload")

        return

    assert_service_status_json_result(
        service_status,
        errors,
        f"{name} service_status",
        expected_db=expected_db,
        expected_db_source=expected_db_source,
        expected_task_id=expected_task_id,
        expected_limit=expected_limit,
    )


def assert_run_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    expected_task_id: str,
    expected_db_path: str | None = None,
    expected_output_path: str | None = None,
    expected_db_source: str,
    expected_output_source: str,
    expected_owner_source: str = "default",
    expected_task_context_source: str = "flag",
) -> None:
    if result is None:
        return

    saved_session = result.get("saved_session") or {}

    remembered_session = result.get("remembered_session") or {}

    source_hints = result.get("source_hints") or {}

    captured_output = str(result.get("captured_output") or "").replace("/", chr(92))

    normalized_saved_db = str(saved_session.get("db") or "").replace("/", chr(92))

    normalized_saved_output = str(saved_session.get("output") or "").replace(
        "/", chr(92)
    )

    normalized_expected_db = (
        None if expected_db_path is None else expected_db_path.replace("/", chr(92))
    )

    normalized_expected_output = (
        None
        if expected_output_path is None
        else expected_output_path.replace("/", chr(92))
    )

    if (
        not isinstance(saved_session, dict)
        or saved_session.get("task_id") != expected_task_id
    ):
        errors.append(f"{name} missing saved_session task_id={expected_task_id}")

    elif (
        normalized_expected_db is not None
        and normalized_saved_db != normalized_expected_db
    ):
        errors.append(f"{name} missing saved_session db={expected_db_path}")

    elif (
        normalized_expected_output is not None
        and normalized_saved_output != normalized_expected_output
    ):
        errors.append(f"{name} missing saved_session output={expected_output_path}")

    elif (
        not isinstance(remembered_session, dict) or remembered_session != saved_session
    ):
        errors.append(f"{name} missing remembered_session mirror")

    elif (
        not isinstance(source_hints, dict)
        or source_hints.get("db") != expected_db_source
    ):
        errors.append(f"{name} missing source_hints.db={expected_db_source}")

    elif source_hints.get("output") != expected_output_source:
        errors.append(f"{name} missing source_hints.output={expected_output_source}")

    elif source_hints.get("owner_id") != expected_owner_source:
        errors.append(f"{name} missing source_hints.owner_id={expected_owner_source}")

    elif source_hints.get("task_context") != expected_task_context_source:
        errors.append(
            f"{name} missing source_hints.task_context={expected_task_context_source}"
        )

    elif (
        normalized_expected_db is not None
        and normalized_expected_db not in captured_output
    ):
        errors.append(f"{name} missing captured db path")

    elif (
        normalized_expected_output is not None
        and normalized_expected_output not in captured_output
    ):
        errors.append(f"{name} missing captured output path")


def assert_use_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    expected_task_id: str,
    expected_source: str,
) -> None:
    if result is None:
        return

    if (
        result.get("task_id") != expected_task_id
        or result.get("source") != expected_source
    ):
        errors.append(f"{name} missing task_id/source")

    elif result.get("db_source") != "session":
        errors.append(f"{name} missing db_source=session")

    elif result.get("output_source") != "task_scope":
        errors.append(f"{name} missing output_source=task_scope")

    elif result.get("owner_id_source") != "session":
        errors.append(f"{name} missing owner_id_source=session")


def assert_session_passthrough_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    action: str,
    expected_task_id: str,
) -> None:
    if result is None:
        return

    prepared = result.get("prepared") or []

    remembered_session = result.get("remembered_session") or {}

    source_hints = result.get("source_hints") or {}

    captured_output = str(result.get("captured_output") or "")

    if not prepared or prepared[0] != action:
        errors.append(f"{name} missing prepared {action}")

    elif expected_task_id not in captured_output:
        errors.append(f"{name} missing captured task {expected_task_id}")

    elif (
        not isinstance(remembered_session, dict)
        or remembered_session.get("task_id") != expected_task_id
    ):
        errors.append(f"{name} missing remembered session {expected_task_id}")

    elif not isinstance(source_hints, dict) or source_hints.get("db") != "session":
        errors.append(f"{name} missing source_hints.db=session")

    elif source_hints.get("output") != "session":
        errors.append(f"{name} missing source_hints.output=session")

    elif source_hints.get("owner_id") != "session":
        errors.append(f"{name} missing source_hints.owner_id=session")

    elif source_hints.get("task_context") != "session":
        errors.append(f"{name} missing source_hints.task_context=session")


def assert_session_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    expected_task_id: str,
) -> None:
    if result is None:
        return

    expected_effect_id = f"effect-{expected_task_id}"

    if result.get("task_id") != expected_task_id:
        errors.append(f"{name} missing task_id={expected_task_id}")

    elif result.get("effect_id") != expected_effect_id:
        errors.append(f"{name} missing effect_id={expected_effect_id}")

    elif result.get("db") != "target\mvp\session.db":
        errors.append(f"{name} missing db=target\mvp\session.db")

    elif result.get("output") != "target\mvp\output.txt":
        errors.append(f"{name} missing output=target\mvp\output.txt")

    elif result.get("owner_id") != "safeclaw-mvp":
        errors.append(f"{name} missing owner_id=safeclaw-mvp")


def assert_sessions_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    expected_current_task_id: str,
    expected_previous_task_id: str,
) -> None:
    if result is None:
        return

    rows = result.get("rows") or []

    current_session = result.get("current_session") or {}

    if result.get("db") != "target\mvp\session.db":
        errors.append(f"{name} missing db=target\mvp\session.db")

    elif result.get("db_source") != "session":
        errors.append(f"{name} missing db_source=session")

    elif result.get("limit") != 5:
        errors.append(f"{name} missing limit=5")

    elif (
        not isinstance(current_session, dict)
        or current_session.get("task_id") != expected_current_task_id
    ):
        errors.append(f"{name} missing current_session {expected_current_task_id}")

    elif not rows or rows[0].get("task_id") != expected_current_task_id:
        errors.append(f"{name} missing recent[0] task={expected_current_task_id}")

    elif rows[0].get("current") is not True:
        errors.append(f"{name} missing recent[0] current=true")

    elif len(rows) < 2 or rows[1].get("task_id") != expected_previous_task_id:
        errors.append(f"{name} missing recent[1] task={expected_previous_task_id}")

    elif rows[1].get("current") is not False:
        errors.append(f"{name} missing recent[1] current=false")


def assert_json_null_result(
    payload: dict[str, object] | None,
    errors: list[str],
    name: str,
    action: str,
) -> None:
    if payload is None:
        return

    if payload.get("ok") is not True or payload.get("action") != action:
        errors.append(f"{name} missing envelope")

    elif "result" not in payload or payload.get("result") is not None:
        errors.append(f"{name} missing result=null")


def load_json_file_payload(
    path: Path, errors: list[str], name: str
) -> dict[str, object] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))

    except OSError as exc:
        errors.append(f"{name} 读取失败: {exc}")

        return None

    except json.JSONDecodeError as error:
        errors.append(f"{name} 输出不是合法 JSON: {error}")

        return None

    if not isinstance(payload, dict):
        errors.append(f"{name} 输出不是对象 JSON")

        return None

    return payload


def assert_json_error_fields(
    error: dict[str, object] | None,
    details: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    expected_error_message_substring: str | None = None,
    error_message_label: str | None = None,
    expected_top_level_error_code: str | None = None,
    expected_top_level_error_reason: str | None = None,
    expected_top_level_error_error_code: str | None = None,
    expect_top_level_error_error_code_absent: bool = False,
    expected_top_level_error_degradation_mode: str | None = None,
    expected_top_level_error_requires_model: bool | None = None,
    expected_top_level_error_requires_sidecar: bool | None = None,
    expected_top_level_error_requested_action: str | None = None,
    expected_code: str | None = None,
    expected_failed_step: str | None = None,
    expected_details_message_substring: str | None = None,
    details_message_field: str = "error_message",
    details_message_label: str | None = None,
    expected_remembered_session_task_id: str | None = None,
    remembered_session_label: str | None = None,
    expect_no_remembered_session: bool = False,
    expected_preflight_requested_action: str | None = None,
    expected_preflight_reason: str | None = None,
    expected_preflight_error_code: str | None = None,
    expect_preflight_error_code_absent: bool = False,
    expected_preflight_summary_substring: str | None = None,
    expect_top_level_error_summary_matches_preflight: bool = False,
) -> None:
    if error is None:
        return

    if expected_error_message_substring is not None:
        if expected_error_message_substring not in str(error.get("message", "")):
            errors.append(error_message_label or f"{name} 输出缺少错误信息")

            return

    if expected_top_level_error_code is not None:
        if error.get("code") != expected_top_level_error_code:
            errors.append(f"{name} missing error.code={expected_top_level_error_code}")

            return

    if expected_top_level_error_reason is not None:
        if error.get("reason") != expected_top_level_error_reason:
            errors.append(
                f"{name} missing error.reason={expected_top_level_error_reason}"
            )

            return

    if expected_top_level_error_error_code is not None:
        if error.get("error_code") != expected_top_level_error_error_code:
            errors.append(
                f"{name} missing error.error_code={expected_top_level_error_error_code}"
            )

            return

    if expect_top_level_error_error_code_absent:
        if error.get("error_code") is not None:
            errors.append(f"{name} expected no error.error_code")

            return

    if expected_top_level_error_degradation_mode is not None:
        if error.get("degradation_mode") != expected_top_level_error_degradation_mode:
            errors.append(
                f"{name} missing error.degradation_mode={expected_top_level_error_degradation_mode}"
            )

            return

    if expected_top_level_error_requires_model is not None:
        if error.get("requires_model") is not expected_top_level_error_requires_model:
            errors.append(
                f"{name} missing error.requires_model={expected_top_level_error_requires_model}"
            )

            return

    if expected_top_level_error_requires_sidecar is not None:
        if (
            error.get("requires_sidecar")
            is not expected_top_level_error_requires_sidecar
        ):
            errors.append(
                f"{name} missing error.requires_sidecar={expected_top_level_error_requires_sidecar}"
            )

            return

    if expected_top_level_error_requested_action is not None:
        if error.get("requested_action") != expected_top_level_error_requested_action:
            errors.append(
                f"{name} missing error.requested_action={expected_top_level_error_requested_action}"
            )

            return

    if details is None:
        return

    if expected_failed_step is not None:
        if details.get("failed_step") != expected_failed_step:
            errors.append(f"{name} 缺少失败步骤 {expected_failed_step}")

            return

    if expected_code is not None:
        if details.get("code") != expected_code:
            errors.append(f"{name} 缺少错误代码 {expected_code}")

            return

    if expected_details_message_substring is not None:
        if expected_details_message_substring not in str(
            details.get(details_message_field, "")
        ):
            errors.append(details_message_label or f"{name} 缺少错误明细")

            return

    if expect_no_remembered_session:
        if details.get("remembered_session") is not None:
            errors.append(f"{name} remembered_session 预期为空")

            return

    if expected_remembered_session_task_id is not None:
        remembered_session = details.get("remembered_session") or {}

        if (
            not isinstance(remembered_session, dict)
            or remembered_session.get("task_id") != expected_remembered_session_task_id
        ):
            errors.append(
                remembered_session_label
                or f"{name} remembered_session 缺少 {expected_remembered_session_task_id}"
            )

            return

    if expected_preflight_requested_action is not None:
        if (
            details.get("preflight_requested_action")
            != expected_preflight_requested_action
        ):
            errors.append(
                f"{name} missing preflight_requested_action={expected_preflight_requested_action}"
            )

            return

    if expected_preflight_reason is not None:
        if details.get("preflight_reason") != expected_preflight_reason:
            errors.append(
                f"{name} missing preflight_reason={expected_preflight_reason}"
            )

            return

    if expected_preflight_error_code is not None:
        if details.get("preflight_error_code") != expected_preflight_error_code:
            errors.append(
                f"{name} missing preflight_error_code={expected_preflight_error_code}"
            )

            return

    if expect_preflight_error_code_absent:
        if details.get("preflight_error_code") is not None:
            errors.append(f"{name} expected no preflight_error_code")

            return

    if expected_preflight_summary_substring is not None:
        if expected_preflight_summary_substring not in str(
            details.get("preflight_summary", "")
        ):
            errors.append(
                f"{name} missing preflight_summary substring {expected_preflight_summary_substring}"
            )

            return

    if expect_top_level_error_summary_matches_preflight:
        if error.get("summary") != details.get("preflight_summary"):
            errors.append(
                f"{name} missing mirrored error.summary from preflight_summary"
            )


def run_wrapper_command(
    command: list[str],
    *,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command, cwd=REPO_ROOT, env=env, capture_output=True, text=True
    )


def build_smoke_pythonpath_env(
    extra_path: Path,
    base_env: dict[str, str] | None = None,
) -> dict[str, str]:
    env = os.environ.copy() if base_env is None else dict(base_env)
    existing = env.get("PYTHONPATH") or ""
    env["PYTHONPATH"] = (
        str(extra_path) if not existing else f"{extra_path}{os.pathsep}{existing}"
    )
    return env


def write_smoke_verify_sitecustomize(directory: Path) -> Path:
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
    sitecustomize_path = directory / "sitecustomize.py"
    sitecustomize_path.write_text(
        "from __future__ import annotations\n"
        "\n"
        "import subprocess\n"
        "from pathlib import Path\n"
        "\n"
        f"_REPORT_FACTS = {_SMOKE_WRAPPER_REPORT_STUB_TASK_OUTPUTS!r}\n"
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


def build_smoke_demo_pythonpath_env(
    base_env: dict[str, str] | None = None,
) -> dict[str, str]:
    demo_temp_dir = tempfile.TemporaryDirectory(prefix="tooling-smoke-demo-")
    _SMOKE_TEMP_DIRS.append(demo_temp_dir)
    demo_stub_dir = Path(demo_temp_dir.name)
    write_smoke_demo_sitecustomize(demo_stub_dir)
    demo_stub_env = build_smoke_pythonpath_env(demo_stub_dir, base_env=base_env)
    return demo_stub_env


def build_smoke_report_pythonpath_env(
    base_env: dict[str, str] | None = None,
) -> dict[str, str]:
    report_temp_dir = tempfile.TemporaryDirectory(prefix="tooling-smoke-report-")
    _SMOKE_TEMP_DIRS.append(report_temp_dir)
    report_stub_dir = Path(report_temp_dir.name)
    write_smoke_report_sitecustomize(report_stub_dir)
    report_stub_env = build_smoke_pythonpath_env(report_stub_dir, base_env=base_env)
    return report_stub_env


def assert_command_failure_output(
    command: list[str],
    errors: list[str],
    name: str,
    *,
    expected_substring: str,
    missing_output_label: str,
    expected_exit: int | None = None,
) -> None:
    completed = run_wrapper_command(command)

    output = (completed.stdout or "") + (completed.stderr or "")

    if expected_exit is None:
        if completed.returncode == 0:
            errors.append(f"{name} missing non-zero exit")

            return

    elif completed.returncode != expected_exit:
        errors.append(f"{name} failed: exit={completed.returncode}")

        return

    if expected_substring not in output:
        errors.append(missing_output_label)


def assert_command_json_error(
    command: list[str],
    errors: list[str],
    name: str,
    action: str,
    *,
    expected_exit: int = 2,
    reject_legacy_session: bool = False,
    legacy_session_label: str | None = None,
    **error_expectations: object,
) -> dict[str, object] | None:
    payload = load_json_payload(
        run_wrapper_command(command), errors, name, expected_exit
    )

    if payload is None:
        return None

    error, details = extract_json_error(payload, errors, name, action)

    assert_json_error_fields(error, details, errors, name, **error_expectations)

    if (
        reject_legacy_session
        and details is not None
        and details.get("session") is not None
    ):
        errors.append(legacy_session_label or f"{name} should not keep legacy session")

    return details


def assert_command_json_result(
    command: list[str],
    errors: list[str],
    name: str,
    action: str,
    *,
    expected_exit: int = 0,
    env: dict[str, str] | None = None,
) -> dict[str, object] | None:
    payload = load_json_payload(
        run_wrapper_command(command, env=env), errors, name, expected_exit
    )

    if payload is None:
        return None

    return extract_json_result(payload, errors, name, action)


def assert_workspace_seed_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    expected_action: str,
    expected_task_id: str,
) -> None:
    if result is None:
        return

    prepared = result.get("prepared") or []
    session = result.get("saved_session") or {}
    source_hints = result.get("source_hints") or {}

    if not prepared or prepared[0] != expected_action:
        errors.append(f"{name} missing prepared {expected_action}")
    elif session.get("task_id") != expected_task_id:
        errors.append(f"{name} missing saved session task")
    elif source_hints.get("db") != "workspace":
        errors.append(f"{name} missing workspace db source")


def assert_preflight_ai_reason_blocked_json_error(
    command: list[str],
    errors: list[str],
    name: str,
    action: str,
) -> None:
    assert_command_json_error(
        command,
        errors,
        name,
        action,
        expected_exit=1,
        expected_error_message_substring="failed step=preflight",
        expected_top_level_error_code="preflight-blocked",
        expected_top_level_error_reason="ERR_AI_PROVIDER_UNAVAILABLE",
        expected_top_level_error_error_code="ERR_AI_PROVIDER_UNAVAILABLE",
        expected_top_level_error_degradation_mode="provider_unavailable",
        expected_top_level_error_requires_model=True,
        expected_top_level_error_requires_sidecar=True,
        expected_top_level_error_requested_action="ai-reason",
        expected_failed_step="preflight",
        expected_code="preflight-blocked",
        expected_preflight_requested_action="ai-reason",
        expected_preflight_reason="ERR_AI_PROVIDER_UNAVAILABLE",
        expected_preflight_error_code="ERR_AI_PROVIDER_UNAVAILABLE",
        expected_preflight_summary_substring="action=ai-reason",
        expect_top_level_error_summary_matches_preflight=True,
    )


def append_root_ps1_service_retry_errors(errors: list[str]) -> None:
    root_ps1 = [
        "powershell.exe",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        "safeclaw.ps1",
    ]
    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-failed",
            "--reset",
            "--task-id",
            "task-readme-root-failed-ps1",
            "--json",
        ],
        errors,
        "safeclaw-root-ps1-service-retry-seed-failed-json",
        "seed-failed",
    )
    assert_workspace_seed_json_result(
        result,
        errors,
        "safeclaw-root-ps1-service-retry-seed-failed-json",
        expected_action="seed-failed",
        expected_task_id="task-readme-root-failed-ps1",
    )
    assert_preflight_ai_reason_blocked_json_error(
        [
            *root_ps1,
            "service-retry",
            "--task-id",
            "task-readme-root-failed-ps1",
            "--limit",
            "1",
            "--report",
            "--preflight",
            "--preflight-action",
            "ai-reason",
            "--json",
        ],
        errors,
        "safeclaw-root-ps1-service-retry-preflight-ai-json",
        "service-retry",
    )
    result = assert_command_json_result(
        [
            *root_ps1,
            "service-retry",
            "--task-id",
            "task-readme-root-failed-ps1",
            "--limit",
            "1",
            "--report",
            "--json",
        ],
        errors,
        "safeclaw-root-ps1-service-retry-json",
        "service-retry",
    )
    assert_service_retry_json_result(
        result,
        errors,
        "safeclaw-root-ps1-service-retry-json",
        expected_db="target/mvp/workspaces/readme-root/session.db",
        expected_db_source="session",
        expected_task_id="task-readme-root-failed-ps1",
        expected_limit=1,
        expected_steps=["retry", "service-status", "report"],
        expect_report_payload=True,
    )


def append_root_ps1_service_resume_errors(errors: list[str]) -> None:
    root_ps1 = [
        "powershell.exe",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        "safeclaw.ps1",
    ]
    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-failed",
            "--reset",
            "--task-id",
            "task-readme-root-failed-resume-ps1",
            "--json",
        ],
        errors,
        "safeclaw-root-ps1-service-resume-not-hibernated-seed-failed-json",
        "seed-failed",
    )
    assert_workspace_seed_json_result(
        result,
        errors,
        "safeclaw-root-ps1-service-resume-not-hibernated-seed-failed-json",
        expected_action="seed-failed",
        expected_task_id="task-readme-root-failed-resume-ps1",
    )
    assert_command_json_error(
        [
            *root_ps1,
            "service-resume",
            "--task-id",
            "task-readme-root-failed-resume-ps1",
            "--limit",
            "1",
            "--json",
        ],
        errors,
        "safeclaw-root-ps1-service-resume-not-hibernated-json",
        "service-resume",
        expected_exit=1,
        expected_error_message_substring="failed step=resume",
        expected_top_level_error_code="resume-target-not-hibernated",
        expected_top_level_error_reason="resume_target_not_hibernated",
        expected_failed_step="resume",
        expected_code="resume-target-not-hibernated",
        expected_details_message_substring="resume only works for hibernated tasks",
    )
    result = assert_command_json_result(
        [
            *root_ps1,
            "service-run",
            "--reset",
            "--task-id",
            "task-readme-root-missing-resume-ps1",
            "--limit",
            "1",
            "--report",
            "--json",
        ],
        errors,
        "safeclaw-root-ps1-service-resume-missing-service-run-json",
        "service-run",
    )
    assert_service_run_json_result(
        result,
        errors,
        "safeclaw-root-ps1-service-resume-missing-service-run-json",
        expected_db="target/mvp/workspaces/readme-root/session.db",
        expected_db_source="session",
        expected_task_id="task-readme-root-missing-resume-ps1",
        expected_limit=1,
        expected_steps=["run", "service-status", "report"],
        expect_report_payload=True,
        expected_run_db_source="workspace",
    )
    assert_command_json_error(
        [
            *root_ps1,
            "service-resume",
            "--task-id",
            "task-readme-root-missing-resume-ps1",
            "--limit",
            "1",
            "--json",
        ],
        errors,
        "safeclaw-root-ps1-service-resume-missing-json",
        "service-resume",
        expected_exit=1,
        expected_error_message_substring="failed step=resume",
        expected_top_level_error_code="resume-target-missing",
        expected_top_level_error_reason="hibernated_runtime_missing",
        expected_failed_step="resume",
        expected_code="resume-target-missing",
        expected_details_message_substring="resume requires a hibernated runtime for the selected task",
    )
    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-hibernated",
            "--reset",
            "--task-id",
            "task-readme-root-hibernated-ps1",
            "--json",
        ],
        errors,
        "safeclaw-root-ps1-service-resume-seed-hibernated-json",
        "seed-hibernated",
    )
    assert_workspace_seed_json_result(
        result,
        errors,
        "safeclaw-root-ps1-service-resume-seed-hibernated-json",
        expected_action="seed-hibernated",
        expected_task_id="task-readme-root-hibernated-ps1",
    )
    assert_preflight_ai_reason_blocked_json_error(
        [
            *root_ps1,
            "service-resume",
            "--task-id",
            "task-readme-root-hibernated-ps1",
            "--limit",
            "1",
            "--report",
            "--preflight",
            "--preflight-action",
            "ai-reason",
            "--json",
        ],
        errors,
        "safeclaw-root-ps1-service-resume-preflight-ai-json",
        "service-resume",
    )
    result = assert_command_json_result(
        [
            *root_ps1,
            "service-resume",
            "--task-id",
            "task-readme-root-hibernated-ps1",
            "--limit",
            "1",
            "--report",
            "--json",
        ],
        errors,
        "safeclaw-root-ps1-service-resume-json",
        "service-resume",
    )
    assert_service_resume_json_result(
        result,
        errors,
        "safeclaw-root-ps1-service-resume-json",
        expected_db="target/mvp/workspaces/readme-root/session.db",
        expected_db_source="session",
        expected_task_id="task-readme-root-hibernated-ps1",
        expected_limit=1,
        expected_steps=["resume", "service-status", "report"],
        expect_report_payload=True,
    )


def append_root_ps1_service_reconcile_errors(errors: list[str]) -> None:
    root_ps1 = [
        "powershell.exe",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        "safeclaw.ps1",
    ]
    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-crash",
            "--reset",
            "--probe-mode",
            "none",
            "--task-id",
            "task-readme-root-assumed-ps1",
            "--json",
        ],
        errors,
        "safeclaw-root-ps1-service-reconcile-seed-crash-json",
        "seed-crash",
    )
    assert_workspace_seed_json_result(
        result,
        errors,
        "safeclaw-root-ps1-service-reconcile-seed-crash-json",
        expected_action="seed-crash",
        expected_task_id="task-readme-root-assumed-ps1",
    )
    assert_preflight_ai_reason_blocked_json_error(
        [
            *root_ps1,
            "service-reconcile",
            "--task-id",
            "task-readme-root-assumed-ps1",
            "--decision",
            "executed",
            "--limit",
            "1",
            "--report",
            "--preflight",
            "--preflight-action",
            "ai-reason",
            "--json",
        ],
        errors,
        "safeclaw-root-ps1-service-reconcile-preflight-ai-json",
        "service-reconcile",
    )
    result = assert_command_json_result(
        [
            *root_ps1,
            "service-reconcile",
            "--task-id",
            "task-readme-root-assumed-ps1",
            "--decision",
            "executed",
            "--limit",
            "1",
            "--report",
            "--json",
        ],
        errors,
        "safeclaw-root-ps1-service-reconcile-json",
        "service-reconcile",
    )
    assert_service_reconcile_json_result(
        result,
        errors,
        "safeclaw-root-ps1-service-reconcile-json",
        expected_db="target/mvp/workspaces/readme-root/session.db",
        expected_db_source="session",
        expected_task_id="task-readme-root-assumed-ps1",
        expected_limit=1,
        expected_decision="executed",
        expected_steps=["reconcile", "service-status", "report"],
        expect_report_payload=True,
    )


def append_root_ps1_service_recover_errors(errors: list[str]) -> None:
    root_ps1 = [
        "powershell.exe",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        "safeclaw.ps1",
    ]
    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-crash",
            "--reset",
            "--task-id",
            "task-readme-root-uncertain-ps1",
            "--json",
        ],
        errors,
        "safeclaw-root-ps1-service-recover-seed-crash-json",
        "seed-crash",
    )
    assert_workspace_seed_json_result(
        result,
        errors,
        "safeclaw-root-ps1-service-recover-seed-crash-json",
        expected_action="seed-crash",
        expected_task_id="task-readme-root-uncertain-ps1",
    )
    assert_preflight_ai_reason_blocked_json_error(
        [
            *root_ps1,
            "service-recover",
            "--task-id",
            "task-readme-root-uncertain-ps1",
            "--limit",
            "1",
            "--report",
            "--preflight",
            "--preflight-action",
            "ai-reason",
            "--json",
        ],
        errors,
        "safeclaw-root-ps1-service-recover-preflight-ai-json",
        "service-recover",
    )
    result = assert_command_json_result(
        [
            *root_ps1,
            "service-recover",
            "--task-id",
            "task-readme-root-uncertain-ps1",
            "--limit",
            "1",
            "--report",
            "--json",
        ],
        errors,
        "safeclaw-root-ps1-service-recover-json",
        "service-recover",
    )
    assert_service_recover_json_result(
        result,
        errors,
        "safeclaw-root-ps1-service-recover-json",
        expected_db="target/mvp/workspaces/readme-root/session.db",
        expected_db_source="session",
        expected_task_id="task-readme-root-uncertain-ps1",
        expected_limit=1,
        expected_steps=["recover", "service-status", "report"],
        expect_report_payload=True,
    )


def assert_step_source_hints(
    steps: object,
    errors: list[str],
    name: str,
    expected: list[tuple[str, dict[str, str]]],
) -> None:
    if not isinstance(steps, list):
        errors.append(f"{name} steps 不是列表")

        return

    for index, (expected_action, expected_hints) in enumerate(expected):
        if index >= len(steps) or not isinstance(steps[index], dict):
            errors.append(f"{name} 缺少步骤 {expected_action}")

            return

        step = steps[index]

        if step.get("action") != expected_action:
            errors.append(f"{name} 步骤 {index} 不是 {expected_action}")

            return

        source_hints = step.get("source_hints") or {}

        if not isinstance(source_hints, dict):
            errors.append(f"{name} 步骤 {expected_action} 缺少 source_hints")

            return

        for field, expected_value in expected_hints.items():
            if source_hints.get(field) != expected_value:
                errors.append(
                    f"{name} 步骤 {expected_action} source_hints.{field} != {expected_value}"
                )

                return


def assert_matching_session_alias(
    payload: dict[str, object] | None,
    errors: list[str],
    name: str,
) -> None:
    if payload is None:
        return

    remembered_session = payload.get("remembered_session") or {}

    session = payload.get("session") or {}

    if not isinstance(remembered_session, dict):
        errors.append(f"{name} remembered_session 不是对象")

        return

    if not isinstance(session, dict):
        errors.append(f"{name} session 兼容别名不是对象")

        return

    if session != remembered_session:
        errors.append(f"{name} session 兼容别名与 remembered_session 不一致")


def append_expected_substring_errors(
    output: str,
    errors: list[str],
    expectations: list[tuple[str, str]],
    grouped_expectations: list[tuple[tuple[str, ...], str]] | None = None,
) -> None:
    for needle, message in expectations:
        if needle not in output:
            errors.append(message)
            return
    for needles, message in grouped_expectations or []:
        if any(needle not in output for needle in needles):
            errors.append(message)
            return


def load_help_output(
    command: list[str],
    errors: list[str],
    name: str,
    *,
    failure_verb: str,
) -> str | None:
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        errors.append(f"{name} {failure_verb}: exit={completed.returncode}")
        return None
    return (completed.stdout or "") + (completed.stderr or "")


def append_help_usage_error(
    errors: list[str],
    name: str,
    command: list[str],
    expected_usage: str,
    missing_message: str,
    *,
    failure_verb: str,
) -> None:
    output = load_help_output(command, errors, name, failure_verb=failure_verb)
    if output is not None and expected_usage not in output:
        errors.append(missing_message)


def append_smoke_setup_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "workspace", "--clear", "--json"],
        errors,
        "mvp-wrapper-workspace-clear-before-json",
        "workspace",
    )
    if result is not None:
        clear_state = (result.get("cleared"), result.get("reason"))
        if result.get("path") != "target\mvp\workspace.json":
            errors.append("mvp-wrapper-workspace-clear-before-json missing workspace path")
        elif clear_state not in {(True, "removed"), (False, "none")}:
            errors.append(
                "mvp-wrapper-workspace-clear-before-json unexpected clear state"
            )
    result = assert_command_json_result(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "forget", "--json"],
        errors,
        "mvp-wrapper-forget-before-json",
        "forget",
    )
    if result is not None:
        forget_state = (result.get("forgot"), result.get("reason"))
        if result.get("path") != "target\mvp\last_session.json":
            errors.append("mvp-wrapper-forget-before-json missing session path")
        elif forget_state not in {(True, "removed"), (False, "none")}:
            errors.append("mvp-wrapper-forget-before-json unexpected forget state")
    for name, command, expected in CHECKS:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        output = (completed.stdout or "") + (completed.stderr or "")
        if completed.returncode != 0:
            errors.append(f"{name} 执行失败: exit={completed.returncode}")
            continue
        if expected not in output:
            errors.append(f"{name} 输出缺少关键文本: {expected}")


def append_wrapper_help_errors(errors: list[str]) -> None:
    output = load_help_output(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "help"],
        errors,
        "mvp-wrapper-help",
        failure_verb="执行失败",
    )
    if output is None:
        return
    append_expected_substring_errors(
        output,
        errors,
        _SMOKE_WRAPPER_HELP_EXPECTATIONS,
        _SMOKE_WRAPPER_HELP_GROUPED_EXPECTATIONS,
    )


def append_entrypoint_help_errors(errors: list[str]) -> None:
    append_help_usage_error(
        errors,
        "mvp-wrapper-cmd-help",
        ["cmd", "/c", "tools\\mvp\\safeclaw_mvp.cmd", "help"],
        "[mvp-wrapper] usage => tools\\mvp\\safeclaw_mvp.cmd <action> [flags]",
        "mvp-wrapper-cmd-help 输出缺少 usage",
        failure_verb="执行失败",
    )
    append_help_usage_error(
        errors,
        "mvp-wrapper-ps1-help",
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\\mvp\\safeclaw_mvp.ps1",
            "help",
        ],
        "[mvp-wrapper] usage => tools\\mvp\\safeclaw_mvp.cmd <action> [flags]",
        "mvp-wrapper-ps1-help 输出缺少 usage",
        failure_verb="执行失败",
    )
    append_help_usage_error(
        errors,
        "safeclaw-root-cmd-help",
        ["cmd", "/c", "safeclaw.cmd", "help"],
        "[mvp-wrapper] usage => safeclaw.cmd <action> [flags]",
        "safeclaw-root-cmd-help missing usage",
        failure_verb="failed",
    )
    append_help_usage_error(
        errors,
        "safeclaw-root-ps1-help",
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "safeclaw.ps1",
            "help",
        ],
        "[mvp-wrapper] usage => safeclaw.cmd <action> [flags]",
        "safeclaw-root-ps1-help missing usage",
        failure_verb="failed",
    )


def assert_default_service_status_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    expected_db: str,
    expected_db_source: str = "default",
    expected_limit: int = 5,
) -> None:
    if result is None:
        return
    runtime_profile = result.get("runtime_profile") or {}
    model_provider = result.get("model_provider") or {}
    sidecar = result.get("sidecar") or {}
    offline_gate = result.get("offline_gate") or {}
    actual_db = str(result.get("db") or "").replace("\\", "/")
    if actual_db != expected_db.replace("\\", "/"):
        errors.append(f"{name} missing db={expected_db}")
    elif result.get("db_source") != expected_db_source:
        errors.append(f"{name} missing db_source={expected_db_source}")
    elif result.get("limit") != expected_limit:
        errors.append(f"{name} missing limit={expected_limit}")
    elif result.get("current_session") is not None:
        errors.append(f"{name} unexpected current_session")
    elif result.get("current_db") is not False:
        errors.append(f"{name} missing current_db=false")
    elif not isinstance(runtime_profile, dict) or runtime_profile.get("mode") != "local_mvp":
        errors.append(f"{name} missing runtime_profile.mode=local_mvp")
    elif runtime_profile.get("offline_ready") is not True:
        errors.append(f"{name} missing runtime_profile.offline_ready=true")
    elif not isinstance(model_provider, dict) or model_provider.get("status") != "not-configured":
        errors.append(f"{name} missing model_provider.status=not-configured")
    elif model_provider.get("degradation_mode") != "local_only_ok":
        errors.append(f"{name} missing model_provider.degradation_mode=local_only_ok")
    elif not isinstance(sidecar, dict) or sidecar.get("status") != "not-configured":
        errors.append(f"{name} missing sidecar.status=not-configured")
    elif not isinstance(offline_gate, dict) or offline_gate.get("status") != "blocked":
        errors.append(f"{name} missing offline_gate.status=blocked")
    elif offline_gate.get("reason") != "ERR_AI_PROVIDER_UNAVAILABLE":
        errors.append(f"{name} missing offline_gate.reason=ERR_AI_PROVIDER_UNAVAILABLE")
    elif offline_gate.get("summary") != "ai_actions_require_provider":
        errors.append(f"{name} missing offline_gate.summary=ai_actions_require_provider")
    elif offline_gate.get("requested_action") != "ai-reason":
        errors.append(f"{name} missing offline_gate.requested_action=ai-reason")
    elif offline_gate.get("requires_model") is not True:
        errors.append(f"{name} missing offline_gate.requires_model=true")
    elif offline_gate.get("requires_sidecar") is not True:
        errors.append(f"{name} missing offline_gate.requires_sidecar=true")
    elif offline_gate.get("error_code") != "ERR_AI_PROVIDER_UNAVAILABLE":
        errors.append(f"{name} missing offline_gate.error_code=ERR_AI_PROVIDER_UNAVAILABLE")
    elif offline_gate.get("next_command") != "safeclaw.cmd preflight --action ai-reason":
        errors.append(f"{name} missing offline_gate.next_command")


def append_root_default_workspace_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", "safeclaw.ps1", "workspace", "--json"],
        errors,
        "safeclaw-root-ps1-workspace-state-json",
        "workspace",
    )
    assert_workspace_json_result(
        result,
        errors,
        "safeclaw-root-ps1-workspace-state-json",
        expected_active=False,
        expected_name=None,
        expected_db_path="target/mvp/session.db",
        expected_output_path="target/mvp/output.txt",
    )
    result = assert_command_json_result(
        ["cmd", "/c", "safeclaw.cmd", "workspace", "--json"],
        errors,
        "safeclaw-root-cmd-workspace-state-json",
        "workspace",
    )
    assert_workspace_json_result(
        result,
        errors,
        "safeclaw-root-cmd-workspace-state-json",
        expected_active=False,
        expected_name=None,
        expected_db_path="target/mvp/session.db",
        expected_output_path="target/mvp/output.txt",
    )


def append_root_default_runtime_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        ["cmd", "/c", "safeclaw.cmd", "doctor", "--json"],
        errors,
        "safeclaw-root-cmd-doctor-default-json",
        "doctor",
    )
    assert_doctor_json_result(
        result,
        errors,
        "safeclaw-root-cmd-doctor-default-json",
        expected_db_path="target\mvp\session.db",
        expected_output_path="target\mvp\output.txt",
        expected_db_source="default",
        expected_output_source="default",
        expected_workspace_active=False,
    )
    result = assert_command_json_result(
        ["cmd", "/c", "safeclaw.cmd", "service-status", "--limit", "5", "--json"],
        errors,
        "safeclaw-root-cmd-service-status-json",
        "service-status",
    )
    assert_default_service_status_json_result(
        result,
        errors,
        "safeclaw-root-cmd-service-status-json",
        expected_db="target/mvp/session.db",
    )
    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "safeclaw.ps1",
            "service-status",
            "--limit",
            "5",
            "--json",
        ],
        errors,
        "safeclaw-root-ps1-service-status-json",
        "service-status",
    )
    assert_default_service_status_json_result(
        result,
        errors,
        "safeclaw-root-ps1-service-status-json",
        expected_db="target/mvp/session.db",
    )
    result = assert_command_json_result(
        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", "safeclaw.ps1", "doctor", "--json"],
        errors,
        "safeclaw-root-ps1-doctor-json",
        "doctor",
    )
    assert_doctor_json_result(
        result,
        errors,
        "safeclaw-root-ps1-doctor-json",
        expected_db_path="target\mvp\session.db",
        expected_output_path="target\mvp\output.txt",
        expected_db_source="default",
        expected_output_source="default",
        expected_workspace_active=False,
    )


def append_root_default_entry_errors(errors: list[str]) -> None:
    append_root_default_workspace_errors(errors)
    append_root_default_runtime_errors(errors)


def append_root_workspace_entry_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", "safeclaw.ps1", "workspace", "--name", "readme-root-ps1", "--json"],
        errors,
        "safeclaw-root-ps1-workspace-json",
        "workspace",
    )
    assert_workspace_json_result(
        result,
        errors,
        "safeclaw-root-ps1-workspace-json",
        expected_active=True,
        expected_name="readme-root-ps1",
        expected_db_path="target/mvp/workspaces/readme-root-ps1/session.db",
        expected_output_path="target/mvp/workspaces/readme-root-ps1/output.txt",
        expected_changed=True,
    )
    result = assert_command_json_result(
        ["cmd", "/c", "safeclaw.cmd", "workspace", "--name", "readme-root", "--json"],
        errors,
        "safeclaw-root-cmd-workspace-json",
        "workspace",
    )
    assert_workspace_json_result(
        result,
        errors,
        "safeclaw-root-cmd-workspace-json",
        expected_active=True,
        expected_name="readme-root",
        expected_db_path="target/mvp/workspaces/readme-root/session.db",
        expected_output_path="target/mvp/workspaces/readme-root/output.txt",
        expected_changed=True,
    )
    result = assert_command_json_result(
        ["cmd", "/c", "safeclaw.cmd", "doctor", "--json"],
        errors,
        "safeclaw-root-cmd-doctor-json",
        "doctor",
    )
    assert_doctor_json_result(
        result,
        errors,
        "safeclaw-root-cmd-doctor-json",
        expected_db_path="target\mvp\workspaces\readme-root\session.db",
        expected_output_path="target\mvp\workspaces\readme-root\output.txt",
        expected_db_source="workspace",
        expected_output_source="workspace",
        expected_workspace_active=True,
        expected_workspace_name="readme-root",
    )


def append_root_service_run_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        ["cmd", "/c", "safeclaw.cmd", "service-run", "--reset", "--task-id", "task-readme-root", "--limit", "1", "--report", "--json"],
        errors,
        "safeclaw-root-cmd-service-run-json",
        "service-run",
    )
    assert_service_run_json_result(
        result,
        errors,
        "safeclaw-root-cmd-service-run-json",
        expected_db="target/mvp/workspaces/readme-root/session.db",
        expected_db_source="session",
        expected_task_id="task-readme-root",
        expected_limit=1,
        expected_steps=["run", "service-status", "report"],
        expect_report_payload=True,
        expected_run_db_source="workspace",
    )
    assert_preflight_ai_reason_blocked_json_error(
        ["cmd", "/c", "safeclaw.cmd", "service-run", "--reset", "--task-id", "task-readme-root-service-run-preflight-ai-cmd", "--limit", "1", "--report", "--preflight", "--preflight-action", "ai-reason", "--json"],
        errors,
        "safeclaw-root-cmd-service-run-preflight-ai-json",
        "service-run",
    )
    assert_preflight_ai_reason_blocked_json_error(
        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", "safeclaw.ps1", "service-run", "--reset", "--task-id", "task-readme-root-service-run-preflight-ai-ps1", "--limit", "1", "--report", "--preflight", "--preflight-action", "ai-reason", "--json"],
        errors,
        "safeclaw-root-ps1-service-run-preflight-ai-json",
        "service-run",
    )
    result = assert_command_json_result(
        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", "safeclaw.ps1", "service-run", "--reset", "--task-id", "task-readme-root", "--limit", "1", "--report", "--json"],
        errors,
        "safeclaw-root-ps1-service-run-json",
        "service-run",
    )
    assert_service_run_json_result(
        result,
        errors,
        "safeclaw-root-ps1-service-run-json",
        expected_db="target/mvp/workspaces/readme-root/session.db",
        expected_db_source="session",
        expected_task_id="task-readme-root",
        expected_limit=1,
        expected_steps=["run", "service-status", "report"],
        expect_report_payload=True,
        expected_run_db_source="workspace",
    )


def append_root_service_retry_errors(errors: list[str]) -> None:
    payload = load_json_payload(
        run_wrapper_command(
            ["cmd", "/c", "safeclaw.cmd", "seed-failed", "--reset", "--task-id", "task-readme-root-failed", "--json"]
        ),
        errors,
        "safeclaw-root-cmd-seed-failed-json",
        0,
    )
    result = None if payload is None else extract_json_result(
        payload,
        errors,
        "safeclaw-root-cmd-seed-failed-json",
        "seed-failed",
    )
    assert_workspace_seed_json_result(
        result,
        errors,
        "safeclaw-root-cmd-seed-failed-json",
        expected_action="seed-failed",
        expected_task_id="task-readme-root-failed",
    )
    assert_preflight_ai_reason_blocked_json_error(
        ["cmd", "/c", "safeclaw.cmd", "service-retry", "--task-id", "task-readme-root-failed", "--limit", "1", "--report", "--preflight", "--preflight-action", "ai-reason", "--json"],
        errors,
        "safeclaw-root-cmd-service-retry-preflight-ai-json",
        "service-retry",
    )
    result = assert_command_json_result(
        ["cmd", "/c", "safeclaw.cmd", "service-retry", "--task-id", "task-readme-root-failed", "--limit", "1", "--report", "--json"],
        errors,
        "safeclaw-root-cmd-service-retry-json",
        "service-retry",
    )
    assert_service_retry_json_result(
        result,
        errors,
        "safeclaw-root-cmd-service-retry-json",
        expected_db="target/mvp/workspaces/readme-root/session.db",
        expected_db_source="session",
        expected_task_id="task-readme-root-failed",
        expected_limit=1,
        expected_steps=["retry", "service-status", "report"],
        expect_report_payload=True,
    )
    append_root_ps1_service_retry_errors(errors)


def append_root_service_recover_errors(errors: list[str]) -> None:
    payload = load_json_payload(
        run_wrapper_command(
            ["cmd", "/c", "safeclaw.cmd", "seed-crash", "--reset", "--task-id", "task-readme-root-uncertain", "--json"]
        ),
        errors,
        "safeclaw-root-cmd-seed-crash-json",
        0,
    )
    result = None if payload is None else extract_json_result(
        payload,
        errors,
        "safeclaw-root-cmd-seed-crash-json",
        "seed-crash",
    )
    assert_workspace_seed_json_result(
        result,
        errors,
        "safeclaw-root-cmd-seed-crash-json",
        expected_action="seed-crash",
        expected_task_id="task-readme-root-uncertain",
    )
    assert_preflight_ai_reason_blocked_json_error(
        ["cmd", "/c", "safeclaw.cmd", "service-recover", "--task-id", "task-readme-root-uncertain", "--limit", "1", "--report", "--preflight", "--preflight-action", "ai-reason", "--json"],
        errors,
        "safeclaw-root-cmd-service-recover-preflight-ai-json",
        "service-recover",
    )
    result = assert_command_json_result(
        ["cmd", "/c", "safeclaw.cmd", "service-recover", "--task-id", "task-readme-root-uncertain", "--limit", "1", "--report", "--json"],
        errors,
        "safeclaw-root-cmd-service-recover-json",
        "service-recover",
    )
    assert_service_recover_json_result(
        result,
        errors,
        "safeclaw-root-cmd-service-recover-json",
        expected_db="target/mvp/workspaces/readme-root/session.db",
        expected_db_source="session",
        expected_task_id="task-readme-root-uncertain",
        expected_limit=1,
        expected_steps=["recover", "service-status", "report"],
        expect_report_payload=True,
    )
    append_root_ps1_service_recover_errors(errors)


def append_root_cmd_service_resume_invalid_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "seed-failed", "--reset", "--task-id", "task-readme-root-failed-resume-cmd", "--json"],
        errors,
        "safeclaw-root-cmd-service-resume-not-hibernated-seed-failed-json",
        "seed-failed",
    )
    assert_workspace_seed_json_result(
        result,
        errors,
        "safeclaw-root-cmd-service-resume-not-hibernated-seed-failed-json",
        expected_action="seed-failed",
        expected_task_id="task-readme-root-failed-resume-cmd",
    )
    assert_command_json_error(
        ["cmd", "/c", "safeclaw.cmd", "service-resume", "--task-id", "task-readme-root-failed-resume-cmd", "--limit", "1", "--json"],
        errors,
        "safeclaw-root-cmd-service-resume-not-hibernated-json",
        "service-resume",
        expected_exit=1,
        expected_error_message_substring="failed step=resume",
        expected_top_level_error_code="resume-target-not-hibernated",
        expected_top_level_error_reason="resume_target_not_hibernated",
        expected_failed_step="resume",
        expected_code="resume-target-not-hibernated",
        expected_details_message_substring="resume only works for hibernated tasks",
    )
    result = assert_command_json_result(
        ["cmd", "/c", "safeclaw.cmd", "service-run", "--reset", "--task-id", "task-readme-root-missing-resume-cmd", "--limit", "1", "--report", "--json"],
        errors,
        "safeclaw-root-cmd-service-resume-missing-service-run-json",
        "service-run",
    )
    assert_service_run_json_result(
        result,
        errors,
        "safeclaw-root-cmd-service-resume-missing-service-run-json",
        expected_db="target/mvp/workspaces/readme-root/session.db",
        expected_db_source="session",
        expected_task_id="task-readme-root-missing-resume-cmd",
        expected_limit=1,
        expected_steps=["run", "service-status", "report"],
        expect_report_payload=True,
        expected_run_db_source="workspace",
    )
    assert_command_json_error(
        ["cmd", "/c", "safeclaw.cmd", "service-resume", "--task-id", "task-readme-root-missing-resume-cmd", "--limit", "1", "--json"],
        errors,
        "safeclaw-root-cmd-service-resume-missing-json",
        "service-resume",
        expected_exit=1,
        expected_error_message_substring="failed step=resume",
        expected_top_level_error_code="resume-target-missing",
        expected_top_level_error_reason="hibernated_runtime_missing",
        expected_failed_step="resume",
        expected_code="resume-target-missing",
        expected_details_message_substring="resume requires a hibernated runtime for the selected task",
    )


def append_root_cmd_service_resume_hibernated_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "seed-hibernated", "--reset", "--task-id", "task-readme-root-hibernated-cmd", "--json"],
        errors,
        "safeclaw-root-cmd-service-resume-seed-hibernated-json",
        "seed-hibernated",
    )
    assert_workspace_seed_json_result(
        result,
        errors,
        "safeclaw-root-cmd-service-resume-seed-hibernated-json",
        expected_action="seed-hibernated",
        expected_task_id="task-readme-root-hibernated-cmd",
    )
    assert_preflight_ai_reason_blocked_json_error(
        ["cmd", "/c", "safeclaw.cmd", "service-resume", "--task-id", "task-readme-root-hibernated-cmd", "--limit", "1", "--report", "--preflight", "--preflight-action", "ai-reason", "--json"],
        errors,
        "safeclaw-root-cmd-service-resume-preflight-ai-json",
        "service-resume",
    )
    result = assert_command_json_result(
        ["cmd", "/c", "safeclaw.cmd", "service-resume", "--task-id", "task-readme-root-hibernated-cmd", "--limit", "1", "--report", "--json"],
        errors,
        "safeclaw-root-cmd-service-resume-json",
        "service-resume",
    )
    assert_service_resume_json_result(
        result,
        errors,
        "safeclaw-root-cmd-service-resume-json",
        expected_db="target/mvp/workspaces/readme-root/session.db",
        expected_db_source="session",
        expected_task_id="task-readme-root-hibernated-cmd",
        expected_limit=1,
        expected_steps=["resume", "service-status", "report"],
        expect_report_payload=True,
    )


def append_root_service_resume_errors(errors: list[str]) -> None:
    append_root_cmd_service_resume_invalid_errors(errors)
    append_root_cmd_service_resume_hibernated_errors(errors)
    append_root_ps1_service_resume_errors(errors)


def append_root_service_reconcile_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "seed-crash", "--reset", "--probe-mode", "none", "--task-id", "task-readme-root-assumed-cmd", "--json"],
        errors,
        "safeclaw-root-cmd-service-reconcile-seed-crash-json",
        "seed-crash",
    )
    assert_workspace_seed_json_result(
        result,
        errors,
        "safeclaw-root-cmd-service-reconcile-seed-crash-json",
        expected_action="seed-crash",
        expected_task_id="task-readme-root-assumed-cmd",
    )
    assert_preflight_ai_reason_blocked_json_error(
        ["cmd", "/c", "safeclaw.cmd", "service-reconcile", "--task-id", "task-readme-root-assumed-cmd", "--decision", "executed", "--limit", "1", "--report", "--preflight", "--preflight-action", "ai-reason", "--json"],
        errors,
        "safeclaw-root-cmd-service-reconcile-preflight-ai-json",
        "service-reconcile",
    )
    result = assert_command_json_result(
        ["cmd", "/c", "safeclaw.cmd", "service-reconcile", "--task-id", "task-readme-root-assumed-cmd", "--decision", "executed", "--limit", "1", "--report", "--json"],
        errors,
        "safeclaw-root-cmd-service-reconcile-json",
        "service-reconcile",
    )
    assert_service_reconcile_json_result(
        result,
        errors,
        "safeclaw-root-cmd-service-reconcile-json",
        expected_db="target/mvp/workspaces/readme-root/session.db",
        expected_db_source="session",
        expected_task_id="task-readme-root-assumed-cmd",
        expected_limit=1,
        expected_decision="executed",
        expected_steps=["reconcile", "service-status", "report"],
        expect_report_payload=True,
    )
    append_root_ps1_service_reconcile_errors(errors)


def append_root_verify_errors(errors: list[str]) -> None:
    assert_command_json_error(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "safeclaw.ps1",
            "verify",
            "--bogus",
            "--json",
        ],
        errors,
        "safeclaw-root-ps1-verify-invalid-json",
        "verify",
        expected_error_message_substring="unknown argument: --bogus",
    )
    with tempfile.TemporaryDirectory() as verify_mock_dir:
        write_smoke_verify_sitecustomize(Path(verify_mock_dir))
        verify_mock_env = build_smoke_pythonpath_env(Path(verify_mock_dir))
        previous_pythonpath = os.environ.get("PYTHONPATH")
        os.environ["PYTHONPATH"] = verify_mock_env["PYTHONPATH"]
        try:
            result = assert_command_json_result(
                ["cmd", "/c", "safeclaw.cmd", "verify", "--json"],
                errors,
                "safeclaw-root-cmd-verify-json",
                "verify",
            )
        finally:
            if previous_pythonpath is None:
                os.environ.pop("PYTHONPATH", None)
            else:
                os.environ["PYTHONPATH"] = previous_pythonpath
    assert_verify_json_result(result, errors, "safeclaw-root-cmd-verify-json")


def append_root_workspace_clear_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        ["cmd", "/c", "safeclaw.cmd", "workspace", "--clear", "--json"],
        errors,
        "safeclaw-root-cmd-workspace-clear-json",
        "workspace",
    )
    if result is not None:
        clear_state = (result.get("cleared"), result.get("reason"))
        if result.get("path") != "target\mvp\workspace.json":
            errors.append("safeclaw-root-cmd-workspace-clear-json missing workspace path")
        elif clear_state not in {(True, "removed"), (False, "none")}:
            errors.append(
                "safeclaw-root-cmd-workspace-clear-json unexpected clear state"
            )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "safeclaw.ps1",
            "workspace",
            "--clear",
            "--json",
        ],
        errors,
        "safeclaw-root-ps1-workspace-clear-json",
        "workspace",
    )
    if result is not None:
        clear_state = (result.get("cleared"), result.get("reason"))
        if result.get("path") != "target\mvp\workspace.json":
            errors.append("safeclaw-root-ps1-workspace-clear-json missing workspace path")
        elif clear_state != (False, "none"):
            errors.append(
                "safeclaw-root-ps1-workspace-clear-json unexpected clear state"
            )


def append_root_ps1_seed_crash_failed_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "safeclaw.ps1",
            "seed-crash",
            "--reset",
            "--task-id",
            "task-root-ps1-seed-crash-json",
            "--db",
            "target/mvp/root-ps1-seed-crash-json.db",
            "--output",
            "target/mvp/root-ps1-seed-crash-json.txt",
            "--json",
        ],
        errors,
        "safeclaw-root-ps1-seed-crash-json",
        "seed-crash",
    )
    assert_run_json_result(
        result,
        errors,
        "safeclaw-root-ps1-seed-crash-json",
        expected_task_id="task-root-ps1-seed-crash-json",
        expected_db_path="target/mvp/root-ps1-seed-crash-json.db",
        expected_output_path="target/mvp/root-ps1-seed-crash-json.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "safeclaw.ps1",
            "seed-failed",
            "--reset",
            "--task-id",
            "task-root-ps1-seed-failed-json",
            "--db",
            "target/mvp/root-ps1-seed-failed-json.db",
            "--output",
            "target/mvp/root-ps1-seed-failed-json.txt",
            "--json",
        ],
        errors,
        "safeclaw-root-ps1-seed-failed-json",
        "seed-failed",
    )
    assert_run_json_result(
        result,
        errors,
        "safeclaw-root-ps1-seed-failed-json",
        expected_task_id="task-root-ps1-seed-failed-json",
        expected_db_path="target/mvp/root-ps1-seed-failed-json.db",
        expected_output_path="target/mvp/root-ps1-seed-failed-json.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )


def append_root_ps1_seed_hibernated_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "safeclaw.ps1",
            "seed-hibernated",
            "--reset",
            "--task-id",
            "task-root-ps1-seed-hibernated-json",
            "--db",
            "target/mvp/root-ps1-seed-hibernated-json.db",
            "--output",
            "target/mvp/root-ps1-seed-hibernated-json.txt",
            "--json",
        ],
        errors,
        "safeclaw-root-ps1-seed-hibernated-json",
        "seed-hibernated",
    )
    assert_run_json_result(
        result,
        errors,
        "safeclaw-root-ps1-seed-hibernated-json",
        expected_task_id="task-root-ps1-seed-hibernated-json",
        expected_db_path="target/mvp/root-ps1-seed-hibernated-json.db",
        expected_output_path="target/mvp/root-ps1-seed-hibernated-json.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )


def append_root_ps1_resume_seed_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-hibernated",
            "--reset",
            "--task-id",
            "task-root-ps1-resume-json",
            "--db",
            "target/mvp/root-ps1-resume-json.db",
            "--output",
            "target/mvp/root-ps1-resume-json.txt",
            "--json",
        ],
        errors,
        "safeclaw-root-ps1-resume-json-seed-hibernated-json",
        "seed-hibernated",
    )
    assert_run_json_result(
        result,
        errors,
        "safeclaw-root-ps1-resume-json-seed-hibernated-json",
        expected_task_id="task-root-ps1-resume-json",
        expected_db_path="target/mvp/root-ps1-resume-json.db",
        expected_output_path="target/mvp/root-ps1-resume-json.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )


def append_root_ps1_resume_errors(errors: list[str]) -> None:
    append_root_ps1_resume_seed_errors(errors)
    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "safeclaw.ps1",
            "resume",
            "--db",
            "target/mvp/root-ps1-resume-json.db",
            "--task-id",
            "task-root-ps1-resume-json",
            "--output",
            "target/mvp/root-ps1-resume-json.txt",
            "--json",
        ],
        errors,
        "safeclaw-root-ps1-resume-json",
        "resume",
    )
    if result is not None:
        prepared = result.get("prepared") or []
        remembered_session = result.get("remembered_session") or {}
        source_hints = result.get("source_hints") or {}
        captured_output = str(result.get("captured_output") or "")
        if not prepared or prepared[0] != "resume":
            errors.append("safeclaw-root-ps1-resume-json missing prepared resume")
        elif "task-root-ps1-resume-json" not in captured_output:
            errors.append(
                "safeclaw-root-ps1-resume-json missing captured task task-root-ps1-resume-json"
            )
        elif result.get("saved_session") is not None:
            errors.append("safeclaw-root-ps1-resume-json should not save session")
        elif (
            not isinstance(remembered_session, dict)
            or remembered_session.get("task_id") != "task-root-ps1-resume-json"
        ):
            errors.append(
                "safeclaw-root-ps1-resume-json missing remembered session task-root-ps1-resume-json"
            )
        elif remembered_session.get("db") != "target/mvp/root-ps1-resume-json.db":
            errors.append("safeclaw-root-ps1-resume-json missing remembered session db")
        elif remembered_session.get("output") != "target/mvp/root-ps1-resume-json.txt":
            errors.append(
                "safeclaw-root-ps1-resume-json missing remembered session output"
            )
        elif not isinstance(source_hints, dict) or source_hints.get("db") != "flag":
            errors.append("safeclaw-root-ps1-resume-json missing source_hints.db=flag")
        elif source_hints.get("output") != "flag":
            errors.append(
                "safeclaw-root-ps1-resume-json missing source_hints.output=flag"
            )
        elif source_hints.get("owner_id") != "session":
            errors.append(
                "safeclaw-root-ps1-resume-json missing source_hints.owner_id=session"
            )
        elif source_hints.get("task_context") != "flag":
            errors.append(
                "safeclaw-root-ps1-resume-json missing source_hints.task_context=flag"
            )


def append_root_cmd_seed_hibernated_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            "cmd",
            "/c",
            "safeclaw.cmd",
            "seed-hibernated",
            "--reset",
            "--task-id",
            "task-root-cmd-seed-hibernated-json",
            "--db",
            "target/mvp/root-cmd-seed-hibernated-json.db",
            "--output",
            "target/mvp/root-cmd-seed-hibernated-json.txt",
            "--json",
        ],
        errors,
        "safeclaw-root-cmd-seed-hibernated-json",
        "seed-hibernated",
    )
    assert_run_json_result(
        result,
        errors,
        "safeclaw-root-cmd-seed-hibernated-json",
        expected_task_id="task-root-cmd-seed-hibernated-json",
        expected_db_path="target/mvp/root-cmd-seed-hibernated-json.db",
        expected_output_path="target/mvp/root-cmd-seed-hibernated-json.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )


def append_root_cmd_resume_seed_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-hibernated",
            "--reset",
            "--task-id",
            "task-wrapper-root-cmd-resume-json",
            "--db",
            "target/mvp/root-cmd-resume-json.db",
            "--output",
            "target/mvp/root-cmd-resume-json.txt",
            "--json",
        ],
        errors,
        "safeclaw-root-cmd-resume-json-seed-hibernated-json",
        "seed-hibernated",
    )
    assert_run_json_result(
        result,
        errors,
        "safeclaw-root-cmd-resume-json-seed-hibernated-json",
        expected_task_id="task-wrapper-root-cmd-resume-json",
        expected_db_path="target/mvp/root-cmd-resume-json.db",
        expected_output_path="target/mvp/root-cmd-resume-json.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )


def append_root_cmd_resume_errors(errors: list[str]) -> None:
    append_root_cmd_resume_seed_errors(errors)
    result = assert_command_json_result(
        [
            "cmd",
            "/c",
            "safeclaw.cmd",
            "resume",
            "--db",
            "target/mvp/root-cmd-resume-json.db",
            "--task-id",
            "task-wrapper-root-cmd-resume-json",
            "--output",
            "target/mvp/root-cmd-resume-json.txt",
            "--json",
        ],
        errors,
        "safeclaw-root-cmd-resume-json",
        "resume",
    )
    if result is not None:
        prepared = result.get("prepared") or []
        remembered_session = result.get("remembered_session") or {}
        source_hints = result.get("source_hints") or {}
        captured_output = str(result.get("captured_output") or "")
        if not prepared or prepared[0] != "resume":
            errors.append("safeclaw-root-cmd-resume-json missing prepared resume")
        elif "task-wrapper-root-cmd-resume-json" not in captured_output:
            errors.append(
                "safeclaw-root-cmd-resume-json missing captured task task-wrapper-root-cmd-resume-json"
            )
        elif result.get("saved_session") is not None:
            errors.append("safeclaw-root-cmd-resume-json should not save session")
        elif (
            not isinstance(remembered_session, dict)
            or remembered_session.get("task_id") != "task-wrapper-root-cmd-resume-json"
        ):
            errors.append(
                "safeclaw-root-cmd-resume-json missing remembered session task-wrapper-root-cmd-resume-json"
            )
        elif remembered_session.get("db") != "target/mvp/root-cmd-resume-json.db":
            errors.append("safeclaw-root-cmd-resume-json missing remembered session db")
        elif remembered_session.get("output") != "target/mvp/root-cmd-resume-json.txt":
            errors.append(
                "safeclaw-root-cmd-resume-json missing remembered session output"
            )
        elif not isinstance(source_hints, dict) or source_hints.get("db") != "flag":
            errors.append("safeclaw-root-cmd-resume-json missing source_hints.db=flag")
        elif source_hints.get("output") != "flag":
            errors.append(
                "safeclaw-root-cmd-resume-json missing source_hints.output=flag"
            )
        elif source_hints.get("owner_id") != "session":
            errors.append(
                "safeclaw-root-cmd-resume-json missing source_hints.owner_id=session"
            )
        elif source_hints.get("task_context") != "flag":
            errors.append(
                "safeclaw-root-cmd-resume-json missing source_hints.task_context=flag"
            )


def append_root_forget_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        ["cmd", "/c", "safeclaw.cmd", "forget", "--json"],
        errors,
        "safeclaw-root-cmd-forget-json",
        "forget",
    )
    if result is not None:
        forget_state = (result.get("forgot"), result.get("reason"))
        if result.get("path") != "target\mvp\last_session.json":
            errors.append("safeclaw-root-cmd-forget-json missing session path")
        elif forget_state not in {(True, "removed"), (False, "none")}:
            errors.append("safeclaw-root-cmd-forget-json unexpected forget state")

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "safeclaw.ps1",
            "forget",
            "--json",
        ],
        errors,
        "safeclaw-root-ps1-forget-json",
        "forget",
    )
    if result is not None:
        forget_state = (result.get("forgot"), result.get("reason"))
        if result.get("path") != "target\mvp\last_session.json":
            errors.append("safeclaw-root-ps1-forget-json missing session path")
        elif forget_state != (False, "none"):
            errors.append("safeclaw-root-ps1-forget-json unexpected forget state")


def append_root_cmd_preflight_local_action_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        ["cmd", "/c", "safeclaw.cmd", "preflight", "--action", "service-run", "--json"],
        errors,
        "safeclaw-root-cmd-preflight-service-run-json",
        "preflight",
    )
    assert_preflight_json_result(
        result,
        errors,
        "safeclaw-root-cmd-preflight-service-run-json",
        expected_requested_action="service-run",
        expected_known=True,
        expected_action_class="local-action",
        expected_tier="TIER_1",
        expected_writes_state=True,
        expected_permission_context_source="action-template",
        expected_target_scope="scope:target/mvp/output.txt",
        expected_requires_write=True,
        expected_doctor_bypass=False,
        expected_permission_context_applied=True,
        expected_permission_tier="TIER_1",
        expected_permission_policy="confirm",
        expected_permission_reason="write_scope_requires_confirmation",
        expected_permission_enforced=False,
        expected_action_allowed=True,
        expected_action_decision="allow",
        expected_action_reason="current_mvp_action_is_local_only",
        expected_allowed=True,
        expected_decision="allow",
        expected_offline_ready=True,
        expected_degradation_mode="local_only_ok",
        expected_reason="current_mvp_action_is_local_only",
    )

    result = assert_command_json_result(
        ["cmd", "/c", "safeclaw.cmd", "preflight", "--action", "demo", "--json"],
        errors,
        "safeclaw-root-cmd-preflight-demo-json",
        "preflight",
    )
    assert_preflight_json_result(
        result,
        errors,
        "safeclaw-root-cmd-preflight-demo-json",
        expected_requested_action="demo",
        expected_known=True,
        expected_action_class="local-action",
        expected_tier="TIER_1",
        expected_writes_state=True,
        expected_permission_context_source="action-template",
        expected_target_scope="scope:target/mvp/output.txt",
        expected_requires_write=True,
        expected_doctor_bypass=False,
        expected_permission_context_applied=True,
        expected_permission_tier="TIER_1",
        expected_permission_policy="confirm",
        expected_permission_reason="write_scope_requires_confirmation",
        expected_permission_enforced=False,
        expected_action_allowed=True,
        expected_action_decision="allow",
        expected_action_reason="current_mvp_action_is_local_only",
        expected_allowed=True,
        expected_decision="allow",
        expected_offline_ready=True,
        expected_degradation_mode="local_only_ok",
        expected_reason="current_mvp_action_is_local_only",
    )


def append_root_cmd_preflight_ai_reason_errors(errors: list[str]) -> None:
    payload = load_json_payload(
        run_wrapper_command(
            [
                "cmd",
                "/c",
                "safeclaw.cmd",
                "preflight",
                "--action",
                "ai-reason",
                "--json",
            ]
        ),
        errors,
        "safeclaw-root-cmd-preflight-ai-reason-json",
        1,
    )
    result = None
    if payload is not None:
        if payload.get("ok") is not False or payload.get("action") != "preflight":
            errors.append(
                "safeclaw-root-cmd-preflight-ai-reason-json unexpected top-level payload"
            )
        else:
            candidate = payload.get("result")
            if not isinstance(candidate, dict):
                errors.append(
                    "safeclaw-root-cmd-preflight-ai-reason-json missing result payload"
                )
            else:
                result = candidate
    assert_preflight_json_result(
        result,
        errors,
        "safeclaw-root-cmd-preflight-ai-reason-json",
        expected_requested_action="ai-reason",
        expected_known=True,
        expected_action_class="ai-action",
        expected_tier="TIER_2",
        expected_writes_state=False,
        expected_permission_context_source="none",
        expected_target_scope="",
        expected_requires_write=False,
        expected_doctor_bypass=False,
        expected_permission_context_applied=False,
        expected_permission_tier="TIER_0",
        expected_permission_policy="not_evaluated",
        expected_permission_reason="permission_context_not_provided",
        expected_permission_enforced=False,
        expected_action_allowed=False,
        expected_action_decision="deny",
        expected_action_reason="ERR_AI_PROVIDER_UNAVAILABLE",
        expected_allowed=False,
        expected_decision="deny",
        expected_offline_ready=False,
        expected_degradation_mode="provider_unavailable",
        expected_reason="ERR_AI_PROVIDER_UNAVAILABLE",
        expected_requires_model=True,
        expected_requires_sidecar=True,
        expected_error_code="ERR_AI_PROVIDER_UNAVAILABLE",
    )


def append_root_ps1_preflight_ai_reason_errors(errors: list[str]) -> None:
    payload = load_json_payload(
        run_wrapper_command(
            [
                "powershell.exe",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                "safeclaw.ps1",
                "preflight",
                "--action",
                "ai-reason",
                "--json",
            ]
        ),
        errors,
        "safeclaw-root-ps1-preflight-ai-reason-json",
        1,
    )
    result = None
    if payload is not None:
        if payload.get("ok") is not False or payload.get("action") != "preflight":
            errors.append(
                "safeclaw-root-ps1-preflight-ai-reason-json unexpected top-level payload"
            )
        else:
            candidate = payload.get("result")
            if not isinstance(candidate, dict):
                errors.append(
                    "safeclaw-root-ps1-preflight-ai-reason-json missing result payload"
                )
            else:
                result = candidate
    assert_preflight_json_result(
        result,
        errors,
        "safeclaw-root-ps1-preflight-ai-reason-json",
        expected_requested_action="ai-reason",
        expected_known=True,
        expected_action_class="ai-action",
        expected_tier="TIER_2",
        expected_writes_state=False,
        expected_permission_context_source="none",
        expected_target_scope="",
        expected_requires_write=False,
        expected_doctor_bypass=False,
        expected_permission_context_applied=False,
        expected_permission_tier="TIER_0",
        expected_permission_policy="not_evaluated",
        expected_permission_reason="permission_context_not_provided",
        expected_permission_enforced=False,
        expected_action_allowed=False,
        expected_action_decision="deny",
        expected_action_reason="ERR_AI_PROVIDER_UNAVAILABLE",
        expected_allowed=False,
        expected_decision="deny",
        expected_offline_ready=False,
        expected_degradation_mode="provider_unavailable",
        expected_reason="ERR_AI_PROVIDER_UNAVAILABLE",
        expected_requires_model=True,
        expected_requires_sidecar=True,
        expected_error_code="ERR_AI_PROVIDER_UNAVAILABLE",
    )


def append_root_ps1_preflight_local_action_errors(errors: list[str]) -> None:
    for action, name in (
        ("service-run", "safeclaw-root-ps1-preflight-service-run-json"),
        ("demo", "safeclaw-root-ps1-preflight-demo-json"),
    ):
        result = assert_command_json_result(
            [
                "powershell.exe",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                "safeclaw.ps1",
                "preflight",
                "--action",
                action,
                "--json",
            ],
            errors,
            name,
            "preflight",
        )
        assert_preflight_json_result(
            result,
            errors,
            name,
            expected_requested_action=action,
            expected_known=True,
            expected_action_class="local-action",
            expected_tier="TIER_1",
            expected_writes_state=True,
            expected_permission_context_source="action-template",
            expected_target_scope="scope:target/mvp/output.txt",
            expected_requires_write=True,
            expected_doctor_bypass=False,
            expected_permission_context_applied=True,
            expected_permission_tier="TIER_1",
            expected_permission_policy="confirm",
            expected_permission_reason="write_scope_requires_confirmation",
            expected_permission_enforced=False,
            expected_action_allowed=True,
            expected_action_decision="allow",
            expected_action_reason="current_mvp_action_is_local_only",
            expected_allowed=True,
            expected_decision="allow",
            expected_offline_ready=True,
            expected_degradation_mode="local_only_ok",
            expected_reason="current_mvp_action_is_local_only",
        )
    for command, name in (
        (
            ["cmd", "/c", "safeclaw.cmd", "demo", "--preflight", "--preflight-action", "ai-reason", "--json"],
            "safeclaw-root-cmd-demo-preflight-ai-json",
        ),
        (
            [
                "powershell.exe",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                "safeclaw.ps1",
                "demo",
                "--preflight",
                "--preflight-action",
                "ai-reason",
                "--json",
            ],
            "safeclaw-root-ps1-demo-preflight-ai-json",
        ),
    ):
        assert_preflight_ai_reason_blocked_json_error(command, errors, name, "demo")


def append_wrapper_doctor_shell_json_errors(errors: list[str]) -> None:
    for command, name, db_path, output_path in (
        (
            ["cmd", "/c", "tools\\mvp\\safeclaw_mvp.cmd", "doctor", "--db", "target\\mvp\\doctor-wrapper-cmd.db", "--output", "target\\mvp\\doctor-wrapper-cmd.txt", "--json"],
            "mvp-wrapper-cmd-doctor-json",
            "target\\mvp\\doctor-wrapper-cmd.db",
            "target\\mvp\\doctor-wrapper-cmd.txt",
        ),
        (
            ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", "tools\\mvp\\safeclaw_mvp.ps1", "doctor", "--db", "target\\mvp\\doctor-wrapper-ps1.db", "--output", "target\\mvp\\doctor-wrapper-ps1.txt", "--json"],
            "mvp-wrapper-ps1-doctor-json",
            "target\\mvp\\doctor-wrapper-ps1.db",
            "target\\mvp\\doctor-wrapper-ps1.txt",
        ),
    ):
        result = assert_command_json_result(command, errors, name, "doctor")
        assert_doctor_json_result(
            result,
            errors,
            name,
            expected_db_path=db_path,
            expected_output_path=output_path,
        )


def append_wrapper_doctor_text_errors(errors: list[str]) -> None:
    wrapper_doctor = subprocess.run(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "doctor",
            "--db",
            "target/mvp/doctor-check.db",
            "--output",
            "target/mvp/doctor-check.txt",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    wrapper_doctor_output = (wrapper_doctor.stdout or "") + (wrapper_doctor.stderr or "")
    if wrapper_doctor.returncode != 0:
        errors.append(f"mvp-wrapper-doctor 执行失败: exit={wrapper_doctor.returncode}")
        return
    expected_checks = [
        (
            "[mvp-wrapper] doctor entry => ok cmd=tools\\mvp\\safeclaw_mvp.cmd ps1=tools\\mvp\\safeclaw_mvp.ps1 py=tools\\mvp\\safeclaw_mvp.py",
            "mvp-wrapper-doctor 输出缺少入口检查",
        ),
        ("[mvp-wrapper] doctor cargo => ok", "mvp-wrapper-doctor 输出缺少 cargo 检查"),
        ("[mvp-wrapper] doctor toolchain => ok", "mvp-wrapper-doctor 输出缺少 toolchain 检查"),
        ("[mvp-wrapper] doctor linker => ok", "mvp-wrapper-doctor 输出缺少 linker 检查"),
        ("[mvp-wrapper] doctor session_path => target\\mvp\\last_session.json", "mvp-wrapper-doctor 输出缺少 session_path"),
        ("[mvp-wrapper] doctor source => db=flag output=flag", "mvp-wrapper-doctor 输出缺少来源提示"),
        ("[mvp-wrapper] doctor runtime => mode=local_mvp offline_ready=true llm_required=false sidecar_required=false", "mvp-wrapper-doctor ???? runtime profile ??"),
        ("[mvp-wrapper] doctor model => status=not-configured required=false configured=false degradation=local_only_ok", "mvp-wrapper-doctor ???? model provider ??"),
        ("[mvp-wrapper] doctor sidecar => status=not-configured required=false configured=false detail=sidecar lifecycle is specified for later phases; current local MVP wrapper does not depend on it", "mvp-wrapper-doctor ???? sidecar ??"),
        ("[mvp-wrapper] doctor summary => ready", "mvp-wrapper-doctor 输出缺少聚合状态提示"),
    ]
    for snippet, error_message in expected_checks:
        if snippet not in wrapper_doctor_output:
            errors.append(error_message)
            return
    if "[mvp-wrapper] doctor budget =>" in wrapper_doctor_output:
        errors.append("mvp-wrapper-doctor 意外暴露 budget 文本")


def append_wrapper_doctor_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "doctor",
            "--db",
            "target/mvp/doctor-check.db",
            "--output",
            "target/mvp/doctor-check.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-doctor-json",
        "doctor",
    )
    assert_doctor_json_result(
        result,
        errors,
        "mvp-wrapper-doctor-json",
        expected_db_path="target\\mvp\\doctor-check.db",
        expected_output_path="target\\mvp\\doctor-check.txt",
    )


def append_wrapper_preflight_text_errors(errors: list[str]) -> None:
    wrapper_preflight = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "preflight", "--action", "service-run"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    wrapper_preflight_output = (wrapper_preflight.stdout or "") + (
        wrapper_preflight.stderr or ""
    )
    if wrapper_preflight.returncode != 0:
        errors.append(
            f"mvp-wrapper-preflight failed: exit={wrapper_preflight.returncode}"
        )
    elif (
        "[mvp-wrapper] preflight => action=service-run known=true class=local-action tier=TIER_1 writes_state=true target_scope=scope:target/mvp/output.txt requires_write=true doctor_bypass=false perm_ctx=true perm_ctx_src=action-template enforce_perm=false perm=confirm perm_tier=TIER_1 perm_reason=write_scope_requires_confirmation decision=allow allowed=true offline_ready=true requires_model=false requires_sidecar=false degradation=local_only_ok reason=current_mvp_action_is_local_only"
        not in wrapper_preflight_output
    ):
        errors.append("mvp-wrapper-preflight missing allow summary")


def append_wrapper_preflight_allow_json_errors(errors: list[str]) -> None:
    for command, name in (
        (
            [PYTHON, "tools/mvp/safeclaw_mvp.py", "preflight", "--action", "service-run", "--json"],
            "mvp-wrapper-preflight-json",
        ),
        (
            ["cmd", "/c", "tools\\mvp\\safeclaw_mvp.cmd", "preflight", "--action", "service-run", "--json"],
            "mvp-wrapper-cmd-preflight-json",
        ),
    ):
        result = assert_command_json_result(command, errors, name, "preflight")
        assert_preflight_json_result(
            result,
            errors,
            name,
            expected_requested_action="service-run",
            expected_known=True,
            expected_action_class="local-action",
            expected_tier="TIER_1",
            expected_writes_state=True,
            expected_permission_context_source="action-template",
            expected_target_scope="scope:target/mvp/output.txt",
            expected_requires_write=True,
            expected_doctor_bypass=False,
            expected_permission_context_applied=True,
            expected_permission_tier="TIER_1",
            expected_permission_policy="confirm",
            expected_permission_reason="write_scope_requires_confirmation",
            expected_permission_enforced=False,
            expected_action_allowed=True,
            expected_action_decision="allow",
            expected_action_reason="current_mvp_action_is_local_only",
            expected_allowed=True,
            expected_decision="allow",
            expected_offline_ready=True,
            expected_degradation_mode="local_only_ok",
            expected_reason="current_mvp_action_is_local_only",
        )


def append_wrapper_preflight_unknown_text_errors(errors: list[str]) -> None:
    wrapper_preflight_unknown = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "preflight", "--action", "external-send"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_preflight_unknown_output = (wrapper_preflight_unknown.stdout or "") + (
        wrapper_preflight_unknown.stderr or ""
    )

    if wrapper_preflight_unknown.returncode != 1:
        errors.append(
            f"mvp-wrapper-preflight-unknown failed: exit={wrapper_preflight_unknown.returncode}"
        )

    elif (
        "[mvp-wrapper] preflight => action=external-send known=false class=unknown tier=TIER_2 writes_state=false target_scope=none requires_write=false doctor_bypass=false perm_ctx=false perm_ctx_src=none enforce_perm=false perm=not_evaluated perm_tier=TIER_0 perm_reason=permission_context_not_provided decision=deny allowed=false offline_ready=false requires_model=false requires_sidecar=false degradation=deny_unknown reason=unknown_action_defaults_to_strict_deny"
        not in wrapper_preflight_unknown_output
    ):
        errors.append("mvp-wrapper-preflight-unknown missing deny summary")


def append_wrapper_preflight_unknown_json_errors(errors: list[str]) -> None:
    payload = load_json_payload(
        run_wrapper_command(
            [
                PYTHON,
                "tools/mvp/safeclaw_mvp.py",
                "preflight",
                "--action",
                "external-send",
                "--json",
            ]
        ),
        errors,
        "mvp-wrapper-preflight-unknown-json",
        1,
    )

    result = None

    if payload is not None:
        if payload.get("ok") is not False or payload.get("action") != "preflight":
            errors.append("mvp-wrapper-preflight-unknown-json 输出缺少拒绝信封")

        else:
            candidate = payload.get("result")

            if not isinstance(candidate, dict):
                errors.append(
                    "mvp-wrapper-preflight-unknown-json missing result payload"
                )

            else:
                result = candidate

    assert_preflight_json_result(
        result,
        errors,
        "mvp-wrapper-preflight-unknown-json",
        expected_requested_action="external-send",
        expected_known=False,
        expected_action_class="unknown",
        expected_tier="TIER_2",
        expected_writes_state=False,
        expected_permission_context_source="none",
        expected_target_scope="",
        expected_requires_write=False,
        expected_doctor_bypass=False,
        expected_permission_context_applied=False,
        expected_permission_tier="TIER_0",
        expected_permission_policy="not_evaluated",
        expected_permission_reason="permission_context_not_provided",
        expected_permission_enforced=False,
        expected_action_allowed=False,
        expected_action_decision="deny",
        expected_action_reason="unknown_action_defaults_to_strict_deny",
        expected_allowed=False,
        expected_decision="deny",
        expected_offline_ready=False,
        expected_degradation_mode="deny_unknown",
        expected_reason="unknown_action_defaults_to_strict_deny",
    )


def append_wrapper_preflight_ai_reason_text_errors(errors: list[str]) -> None:
    wrapper_preflight_ai_reason = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "preflight", "--action", "ai-reason"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_preflight_ai_reason_output = (wrapper_preflight_ai_reason.stdout or "") + (
        wrapper_preflight_ai_reason.stderr or ""
    )

    if wrapper_preflight_ai_reason.returncode != 1:
        errors.append(
            f"mvp-wrapper-preflight-ai-reason failed: exit={wrapper_preflight_ai_reason.returncode}"
        )

    elif (
        "[mvp-wrapper] preflight => action=ai-reason known=true class=ai-action tier=TIER_2 writes_state=false target_scope=none requires_write=false doctor_bypass=false perm_ctx=false perm_ctx_src=none enforce_perm=false perm=not_evaluated perm_tier=TIER_0 perm_reason=permission_context_not_provided decision=deny allowed=false offline_ready=false requires_model=true requires_sidecar=true degradation=provider_unavailable reason=ERR_AI_PROVIDER_UNAVAILABLE error_code=ERR_AI_PROVIDER_UNAVAILABLE"
        not in wrapper_preflight_ai_reason_output
    ):
        errors.append(
            "mvp-wrapper-preflight-ai-reason missing provider-unavailable summary"
        )


def append_wrapper_preflight_ai_reason_json_errors(errors: list[str]) -> None:
    payload = load_json_payload(
        run_wrapper_command(
            [
                PYTHON,
                "tools/mvp/safeclaw_mvp.py",
                "preflight",
                "--action",
                "ai-reason",
                "--json",
            ]
        ),
        errors,
        "mvp-wrapper-preflight-ai-reason-json",
        1,
    )

    result = None

    if payload is not None:
        if payload.get("ok") is not False or payload.get("action") != "preflight":
            errors.append("mvp-wrapper-preflight-ai-reason-json ????????")

        else:
            candidate = payload.get("result")

            if not isinstance(candidate, dict):
                errors.append(
                    "mvp-wrapper-preflight-ai-reason-json missing result payload"
                )

            else:
                result = candidate

    assert_preflight_json_result(
        result,
        errors,
        "mvp-wrapper-preflight-ai-reason-json",
        expected_requested_action="ai-reason",
        expected_known=True,
        expected_action_class="ai-action",
        expected_tier="TIER_2",
        expected_writes_state=False,
        expected_permission_context_source="none",
        expected_target_scope="",
        expected_requires_write=False,
        expected_doctor_bypass=False,
        expected_permission_context_applied=False,
        expected_permission_tier="TIER_0",
        expected_permission_policy="not_evaluated",
        expected_permission_reason="permission_context_not_provided",
        expected_permission_enforced=False,
        expected_action_allowed=False,
        expected_action_decision="deny",
        expected_action_reason="ERR_AI_PROVIDER_UNAVAILABLE",
        expected_allowed=False,
        expected_decision="deny",
        expected_offline_ready=False,
        expected_degradation_mode="provider_unavailable",
        expected_reason="ERR_AI_PROVIDER_UNAVAILABLE",
        expected_requires_model=True,
        expected_requires_sidecar=True,
        expected_error_code="ERR_AI_PROVIDER_UNAVAILABLE",
    )


def append_wrapper_preflight_status_text_errors(errors: list[str]) -> None:
    wrapper_preflight_status = subprocess.run(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "preflight",
            "--action",
            "service-status",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_preflight_status_output = (wrapper_preflight_status.stdout or "") + (
        wrapper_preflight_status.stderr or ""
    )

    if wrapper_preflight_status.returncode != 0:
        errors.append(
            f"mvp-wrapper-preflight-status failed: exit={wrapper_preflight_status.returncode}"
        )

    elif (
        "[mvp-wrapper] preflight => action=service-status known=true class=local-action tier=TIER_0 writes_state=false target_scope=scope:target/mvp/output.txt requires_write=false doctor_bypass=false perm_ctx=true perm_ctx_src=action-template enforce_perm=false perm=allow perm_tier=TIER_0 perm_reason=read_scope_allowed decision=allow allowed=true offline_ready=true requires_model=false requires_sidecar=false degradation=local_only_ok reason=current_mvp_action_is_local_only"
        not in wrapper_preflight_status_output
    ):
        errors.append("mvp-wrapper-preflight-status missing inferred status summary")


def append_wrapper_preflight_status_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "preflight",
            "--action",
            "service-status",
            "--json",
        ],
        errors,
        "mvp-wrapper-preflight-status-json",
        "preflight",
    )

    assert_preflight_json_result(
        result,
        errors,
        "mvp-wrapper-preflight-status-json",
        expected_requested_action="service-status",
        expected_known=True,
        expected_action_class="local-action",
        expected_tier="TIER_0",
        expected_writes_state=False,
        expected_permission_context_source="action-template",
        expected_target_scope="scope:target/mvp/output.txt",
        expected_requires_write=False,
        expected_doctor_bypass=False,
        expected_permission_context_applied=True,
        expected_permission_tier="TIER_0",
        expected_permission_policy="allow",
        expected_permission_reason="read_scope_allowed",
        expected_permission_enforced=False,
        expected_action_allowed=True,
        expected_action_decision="allow",
        expected_action_reason="current_mvp_action_is_local_only",
        expected_allowed=True,
        expected_decision="allow",
        expected_offline_ready=True,
        expected_degradation_mode="local_only_ok",
        expected_reason="current_mvp_action_is_local_only",
    )


def append_wrapper_preflight_scope_text_errors(errors: list[str]) -> None:
    wrapper_preflight_scope = subprocess.run(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "preflight",
            "--action",
            "service-status",
            "--scope",
            "demo.workspace",
            "--write",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_preflight_scope_output = (wrapper_preflight_scope.stdout or "") + (
        wrapper_preflight_scope.stderr or ""
    )

    if wrapper_preflight_scope.returncode != 0:
        errors.append(
            f"mvp-wrapper-preflight-scope failed: exit={wrapper_preflight_scope.returncode}"
        )

    elif (
        "[mvp-wrapper] preflight => action=service-status known=true class=local-action tier=TIER_0 writes_state=false target_scope=demo.workspace requires_write=true doctor_bypass=false perm_ctx=true perm_ctx_src=explicit enforce_perm=false perm=confirm perm_tier=TIER_1 perm_reason=write_scope_requires_confirmation decision=allow allowed=true offline_ready=true requires_model=false requires_sidecar=false degradation=local_only_ok reason=current_mvp_action_is_local_only"
        not in wrapper_preflight_scope_output
    ):
        errors.append("mvp-wrapper-preflight-scope missing permission summary")


def append_wrapper_preflight_scope_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "preflight",
            "--action",
            "service-status",
            "--scope",
            "demo.workspace",
            "--write",
            "--json",
        ],
        errors,
        "mvp-wrapper-preflight-scope-json",
        "preflight",
    )

    assert_preflight_json_result(
        result,
        errors,
        "mvp-wrapper-preflight-scope-json",
        expected_requested_action="service-status",
        expected_known=True,
        expected_action_class="local-action",
        expected_tier="TIER_0",
        expected_writes_state=False,
        expected_permission_context_source="explicit",
        expected_target_scope="demo.workspace",
        expected_requires_write=True,
        expected_doctor_bypass=False,
        expected_permission_context_applied=True,
        expected_permission_tier="TIER_1",
        expected_permission_policy="confirm",
        expected_permission_reason="write_scope_requires_confirmation",
        expected_permission_enforced=False,
        expected_action_allowed=True,
        expected_action_decision="allow",
        expected_action_reason="current_mvp_action_is_local_only",
        expected_allowed=True,
        expected_decision="allow",
        expected_offline_ready=True,
        expected_degradation_mode="local_only_ok",
        expected_reason="current_mvp_action_is_local_only",
    )


def append_wrapper_preflight_scope_enforced_text_errors(errors: list[str]) -> None:
    wrapper_preflight_scope_enforced = subprocess.run(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "preflight",
            "--action",
            "service-status",
            "--scope",
            "demo.workspace",
            "--write",
            "--enforce-permission",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_preflight_scope_enforced_output = (
        wrapper_preflight_scope_enforced.stdout or ""
    ) + (wrapper_preflight_scope_enforced.stderr or "")

    if wrapper_preflight_scope_enforced.returncode != 1:
        errors.append(
            f"mvp-wrapper-preflight-scope-enforced failed: exit={wrapper_preflight_scope_enforced.returncode}"
        )

    elif (
        "[mvp-wrapper] preflight => action=service-status known=true class=local-action tier=TIER_0 writes_state=false target_scope=demo.workspace requires_write=true doctor_bypass=false perm_ctx=true perm_ctx_src=explicit enforce_perm=true perm=confirm perm_tier=TIER_1 perm_reason=write_scope_requires_confirmation decision=confirm allowed=false offline_ready=true requires_model=false requires_sidecar=false degradation=local_only_ok reason=write_scope_requires_confirmation"
        not in wrapper_preflight_scope_enforced_output
    ):
        errors.append(
            "mvp-wrapper-preflight-scope-enforced missing permission gate summary"
        )


def append_wrapper_preflight_scope_enforced_json_errors(errors: list[str]) -> None:
    payload = load_json_payload(
        run_wrapper_command(
            [
                PYTHON,
                "tools/mvp/safeclaw_mvp.py",
                "preflight",
                "--action",
                "service-status",
                "--scope",
                "demo.workspace",
                "--write",
                "--enforce-permission",
                "--json",
            ]
        ),
        errors,
        "mvp-wrapper-preflight-scope-enforced-json",
        1,
    )

    result = None

    if payload is not None:
        if payload.get("ok") is not False or payload.get("action") != "preflight":
            errors.append("mvp-wrapper-preflight-scope-enforced-json 输出缺少拒绝信封")

        else:
            candidate = payload.get("result")

            if not isinstance(candidate, dict):
                errors.append(
                    "mvp-wrapper-preflight-scope-enforced-json missing result payload"
                )

            else:
                result = candidate

    assert_preflight_json_result(
        result,
        errors,
        "mvp-wrapper-preflight-scope-enforced-json",
        expected_requested_action="service-status",
        expected_known=True,
        expected_action_class="local-action",
        expected_tier="TIER_0",
        expected_writes_state=False,
        expected_permission_context_source="explicit",
        expected_target_scope="demo.workspace",
        expected_requires_write=True,
        expected_doctor_bypass=False,
        expected_permission_context_applied=True,
        expected_permission_tier="TIER_1",
        expected_permission_policy="confirm",
        expected_permission_reason="write_scope_requires_confirmation",
        expected_permission_enforced=True,
        expected_action_allowed=True,
        expected_action_decision="allow",
        expected_action_reason="current_mvp_action_is_local_only",
        expected_allowed=False,
        expected_decision="confirm",
        expected_offline_ready=True,
        expected_degradation_mode="local_only_ok",
        expected_reason="write_scope_requires_confirmation",
    )


def append_wrapper_preflight_enforce_without_context_json_errors(errors: list[str]) -> None:
    payload = load_json_payload(
        run_wrapper_command(
            [
                PYTHON,
                "tools/mvp/safeclaw_mvp.py",
                "preflight",
                "--action",
                "service-run",
                "--enforce-permission",
                "--json",
            ]
        ),
        errors,
        "mvp-wrapper-preflight-enforce-without-context-json",
        1,
    )

    result = None

    if payload is not None:
        if payload.get("ok") is not False or payload.get("action") != "preflight":
            errors.append("mvp-wrapper-preflight-enforce-without-context-json 输出缺少拒绝信封")

        else:
            candidate = payload.get("result")

            if not isinstance(candidate, dict):
                errors.append(
                    "mvp-wrapper-preflight-enforce-without-context-json missing result payload"
                )

            else:
                result = candidate

    assert_preflight_json_result(
        result,
        errors,
        "mvp-wrapper-preflight-enforce-without-context-json",
        expected_requested_action="service-run",
        expected_known=True,
        expected_action_class="local-action",
        expected_tier="TIER_1",
        expected_writes_state=True,
        expected_permission_context_source="action-template",
        expected_target_scope="scope:target/mvp/output.txt",
        expected_requires_write=True,
        expected_doctor_bypass=False,
        expected_permission_context_applied=True,
        expected_permission_tier="TIER_1",
        expected_permission_policy="confirm",
        expected_permission_reason="write_scope_requires_confirmation",
        expected_permission_enforced=True,
        expected_action_allowed=True,
        expected_action_decision="allow",
        expected_action_reason="current_mvp_action_is_local_only",
        expected_allowed=False,
        expected_decision="confirm",
        expected_offline_ready=True,
        expected_degradation_mode="local_only_ok",
        expected_reason="write_scope_requires_confirmation",
    )


def append_wrapper_preflight_bypass_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "preflight",
            "--action",
            "service-run",
            "--scope",
            "demo.workspace",
            "--doctor-bypass",
            "--enforce-permission",
            "--json",
        ],
        errors,
        "mvp-wrapper-preflight-bypass-json",
        "preflight",
    )

    assert_preflight_json_result(
        result,
        errors,
        "mvp-wrapper-preflight-bypass-json",
        expected_requested_action="service-run",
        expected_known=True,
        expected_action_class="local-action",
        expected_tier="TIER_1",
        expected_writes_state=True,
        expected_permission_context_source="explicit",
        expected_target_scope="demo.workspace",
        expected_requires_write=True,
        expected_doctor_bypass=True,
        expected_permission_context_applied=True,
        expected_permission_tier="TIER_1",
        expected_permission_policy="allow",
        expected_permission_reason="doctor_bypass_privileged_context",
        expected_permission_enforced=True,
        expected_action_allowed=True,
        expected_action_decision="allow",
        expected_action_reason="current_mvp_action_is_local_only",
        expected_allowed=True,
        expected_decision="allow",
        expected_offline_ready=True,
        expected_degradation_mode="local_only_ok",
        expected_reason="doctor_bypass_privileged_context",
    )


def append_wrapper_doctor_no_cargo_path_json_errors(errors: list[str]) -> None:
    wrapper_env = os.environ.copy()

    wrapper_env["PATH"] = os.pathsep.join(
        entry
        for entry in wrapper_env.get("PATH", "").split(os.pathsep)
        if ".cargo" not in entry.lower()
    )

    wrapper_doctor_without_cargo_path = subprocess.run(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "doctor",
            "--db",
            "target/mvp/doctor-no-path.db",
            "--output",
            "target/mvp/doctor-no-path.txt",
            "--json",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=wrapper_env,
    )

    payload = load_json_payload(
        wrapper_doctor_without_cargo_path,
        errors,
        "mvp-wrapper-doctor-no-cargo-path-json",
        0,
    )

    result = (
        None
        if payload is None
        else extract_json_result(
            payload,
            errors,
            "mvp-wrapper-doctor-no-cargo-path-json",
            "doctor",
        )
    )

    assert_doctor_json_result(
        result,
        errors,
        "mvp-wrapper-doctor-no-cargo-path-json",
        expected_db_path="target\mvp\doctor-no-path.db",
        expected_output_path="target\mvp\doctor-no-path.txt",
    )


def append_wrapper_workspace_default_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "workspace", "--json"],
        errors,
        "mvp-wrapper-workspace-default-json",
        "workspace",
    )

    assert_workspace_json_result(
        result,
        errors,
        "mvp-wrapper-workspace-default-json",
        expected_active=False,
        expected_name=None,
        expected_db_path="target\mvp\session.db",
        expected_output_path="target\mvp\output.txt",
    )


def append_wrapper_workspace_activate_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "workspace", "--name", "demo", "--json"],
        errors,
        "mvp-wrapper-workspace-activate-json",
        "workspace",
    )

    assert_workspace_json_result(
        result,
        errors,
        "mvp-wrapper-workspace-activate-json",
        expected_active=True,
        expected_name="demo",
        expected_db_path="target\mvp\workspaces\demo\session.db",
        expected_output_path="target\mvp\workspaces\demo\output.txt",
        expected_changed=True,
    )


def append_wrapper_cmd_workspace_activate_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            "cmd",
            "/c",
            "tools\mvp\safeclaw_mvp.cmd",
            "workspace",
            "--name",
            "demo",
            "--json",
        ],
        errors,
        "mvp-wrapper-cmd-workspace-activate-json",
        "workspace",
    )

    assert_workspace_json_result(
        result,
        errors,
        "mvp-wrapper-cmd-workspace-activate-json",
        expected_active=True,
        expected_name="demo",
        expected_db_path="target\mvp\workspaces\demo\session.db",
        expected_output_path="target\mvp\workspaces\demo\output.txt",
        expected_changed=True,
    )


def append_wrapper_workspace_doctor_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "doctor", "--json"],
        errors,
        "mvp-wrapper-workspace-doctor-json",
        "doctor",
    )

    assert_doctor_json_result(
        result,
        errors,
        "mvp-wrapper-workspace-doctor-json",
        expected_db_path="target\mvp\workspaces\demo\session.db",
        expected_output_path="target\mvp\workspaces\demo\output.txt",
        expected_db_source="workspace",
        expected_output_source="workspace",
        expected_workspace_active=True,
        expected_workspace_name="demo",
    )


def append_wrapper_workspace_run_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "run",
            "--reset",
            "--task-id",
            "task-wrapper-workspace",
            "--json",
        ],
        errors,
        "mvp-wrapper-workspace-run-json",
        "run",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-workspace-run-json",
        expected_task_id="task-wrapper-workspace",
        expected_db_path="target\mvp\workspaces\demo\session.db",
        expected_output_path="target\mvp\workspaces\demo\output.txt",
        expected_db_source="workspace",
        expected_output_source="workspace",
    )


def append_wrapper_workspace_clear_after_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "workspace", "--clear", "--json"],
        errors,
        "mvp-wrapper-workspace-clear-after-json",
        "workspace",
    )

    if result is not None:
        if result.get("path") != "target\mvp\workspace.json":
            errors.append("mvp-wrapper-workspace-clear-after-json missing workspace path")

        elif (result.get("cleared"), result.get("reason")) != (True, "removed"):
            errors.append("mvp-wrapper-workspace-clear-after-json unexpected clear state")


def append_wrapper_cmd_workspace_clear_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "workspace", "--clear", "--json"],
        errors,
        "mvp-wrapper-cmd-workspace-clear-json",
        "workspace",
    )
    if result is not None:
        clear_state = (result.get("cleared"), result.get("reason"))
        if result.get("path") != "target\mvp\workspace.json":
            errors.append("mvp-wrapper-cmd-workspace-clear-json missing workspace path")
        elif clear_state not in {(True, "removed"), (False, "none")}:
            errors.append("mvp-wrapper-cmd-workspace-clear-json unexpected clear state")


def append_wrapper_forget_after_workspace_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "forget", "--json"],
        errors,
        "mvp-wrapper-forget-after-workspace-json",
        "forget",
    )

    if result is not None:
        if result.get("path") != "target\mvp\last_session.json":
            errors.append(
                "mvp-wrapper-forget-after-workspace-json missing session path"
            )

        elif (result.get("forgot"), result.get("reason")) != (True, "removed"):
            errors.append(
                "mvp-wrapper-forget-after-workspace-json unexpected forget state"
            )


def append_wrapper_service_status_seed_run_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "run",
            "--reset",
            "--task-id",
            "task-wrapper-service-status",
            "--db",
            "target/mvp/service-status.db",
            "--output",
            "target/mvp/service-status.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-status-seed-run-json",
        "run",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-service-status-seed-run-json",
        expected_task_id="task-wrapper-service-status",
        expected_db_path="target/mvp/service-status.db",
        expected_output_path="target/mvp/service-status.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )


def append_wrapper_service_status_text_errors(errors: list[str]) -> None:
    wrapper_service_status = subprocess.run(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "service-status",
            "--db",
            "target/mvp/service-status.db",
            "--limit",
            "1",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_service_status_output = (wrapper_service_status.stdout or "") + (
        wrapper_service_status.stderr or ""
    )

    if wrapper_service_status.returncode != 0:
        errors.append(
            f"mvp-wrapper-service-status ????: exit={wrapper_service_status.returncode}"
        )

    elif (
        "[mvp-wrapper] service-status => db=target/mvp/service-status.db limit=1 source=flag"
        not in wrapper_service_status_output
    ):
        errors.append("mvp-wrapper-service-status ????????")

    elif (
        "[mvp-wrapper] service queue => queued=0 active=0 expired=0 completed=1"
        not in wrapper_service_status_output
    ):
        errors.append("mvp-wrapper-service-status ???? queue ??")

    elif (
        "[mvp-wrapper] service workers => succeeded=1"
        not in wrapper_service_status_output
    ):
        errors.append("mvp-wrapper-service-status missing worker summary")

    elif (
        "[mvp-wrapper] service effects => executed=1"
        not in wrapper_service_status_output
    ):
        errors.append("mvp-wrapper-service-status missing effect summary")

    elif "[mvp-wrapper] service probes => none=1" not in wrapper_service_status_output:
        errors.append("mvp-wrapper-service-status ???? probe ??")

    elif (
        "[mvp-wrapper] service heartbeat => interval_ms=10000 event_driven=true latest_updated_at=none age_ms=none freshness=none status=idle reason=no_active_lease_heartbeat"
        not in wrapper_service_status_output
    ):
        errors.append("mvp-wrapper-service-status missing heartbeat summary")

    elif " age_ms=" not in wrapper_service_status_output:
        errors.append("mvp-wrapper-service-status missing heartbeat age")

    elif (
        "freshness=none status=idle reason=no_active_lease_heartbeat"
        not in wrapper_service_status_output
    ):
        errors.append("mvp-wrapper-service-status missing heartbeat freshness")

    elif (
        "[mvp-wrapper] service runtime => mode=local_mvp offline_ready=true llm_required=false sidecar_required=false"
        not in wrapper_service_status_output
    ):
        errors.append("mvp-wrapper-service-status missing runtime summary")

    elif (
        "[mvp-wrapper] service model => status=not-configured required=false configured=false degradation=local_only_ok"
        not in wrapper_service_status_output
    ):
        errors.append("mvp-wrapper-service-status missing model summary")

    elif (
        "[mvp-wrapper] service sidecar => status=not-configured required=false configured=false detail=sidecar lifecycle is specified for later phases; current local MVP wrapper does not depend on it"
        not in wrapper_service_status_output
    ):
        errors.append("mvp-wrapper-service-status missing sidecar summary")

    elif (
        "[mvp-wrapper] service offline => status=blocked reason=ERR_AI_PROVIDER_UNAVAILABLE summary=ai_actions_require_provider action=ai-reason requires_model=true requires_sidecar=true next=safeclaw.cmd preflight --action ai-reason error_code=ERR_AI_PROVIDER_UNAVAILABLE"
        not in wrapper_service_status_output
    ):
        errors.append("mvp-wrapper-service-status missing offline gate summary")

    elif "[mvp-wrapper] service budget =>" in wrapper_service_status_output:
        errors.append("mvp-wrapper-service-status 意外暴露 budget 文本")

    elif (
        "[mvp-wrapper] service coordination => status=clear reason=execution_already_confirmed summary=no_followup_needed task=task-wrapper-service-status"
        not in wrapper_service_status_output
    ):
        errors.append("mvp-wrapper-service-status missing coordination summary")

    elif "task=task-wrapper-service-status" not in wrapper_service_status_output:
        errors.append("mvp-wrapper-service-status ???? recent task")

    elif (
        "scope=scope:target/mvp/service-status.txt write=true doctor_bypass=false perm=confirm perm_tier=TIER_1 perm_reason=write_scope_requires_confirmation"
        not in wrapper_service_status_output
    ):
        errors.append("mvp-wrapper-service-status missing permission visibility")

    elif (
        "lease=released lease_owner=safeclaw-mvp lease_fence=1 lease_age_ms="
        not in wrapper_service_status_output
    ):
        errors.append("mvp-wrapper-service-status missing lease age visibility")

    elif (
        'lease_freshness=lost wait_ms=none next=ok next_reason=execution_already_confirmed blocker=none coordination=clear coordination_reason=execution_already_confirmed coordination_summary=no_followup_needed next_summary=ready_now:action=ok,reason=execution_already_confirmed next_cmd=safeclaw.cmd report --db "target/mvp/service-status.db" --task-id "task-wrapper-service-status"'
        not in wrapper_service_status_output
    ):
        errors.append("mvp-wrapper-service-status missing lease freshness visibility")


def append_wrapper_cmd_service_status_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "service-status", "--json"],
        errors,
        "mvp-wrapper-cmd-service-status-json",
        "service-status",
    )

    assert_service_status_json_result(
        result,
        errors,
        "mvp-wrapper-cmd-service-status-json",
        expected_db="target\mvp\service-status.db",
        expected_db_source="session",
        expected_task_id="task-wrapper-service-status",
        expected_target_scope="scope:target/mvp/service-status.txt",
        expected_requires_write=True,
        expected_doctor_bypass=False,
        expected_permission_tier="TIER_1",
        expected_permission_policy="confirm",
        expected_permission_reason="write_scope_requires_confirmation",
        expected_lease_state="released",
        expected_lease_freshness="lost",
        expected_lease_owner_id="safeclaw-mvp",
        expected_lease_fencing_token=1,
        expected_heartbeat_freshness="none",
        expected_heartbeat_status="idle",
        expected_heartbeat_interval_ms=10000,
        expected_heartbeat_event_driven=True,
        expected_heartbeat_reason="no_active_lease_heartbeat",
        expect_heartbeat_latest_updated_at_absent=True,
        expect_heartbeat_latest_age_ms_absent=True,
        expected_next_action="ok",
        expected_next_command='safeclaw.cmd report --db "target/mvp/service-status.db" --task-id "task-wrapper-service-status"',
        expected_next_reason="execution_already_confirmed",
        expected_next_blocker="none",
        expected_next_summary="ready_now:action=ok,reason=execution_already_confirmed",
        expected_coordination_status="clear",
        expected_coordination_reason="execution_already_confirmed",
        expected_coordination_summary="no_followup_needed",
        expected_service_coordination_status="clear",
        expected_service_coordination_reason="execution_already_confirmed",
        expected_service_coordination_summary="no_followup_needed",
    )


def append_wrapper_ps1_service_status_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\\mvp\\safeclaw_mvp.ps1",
            "service-status",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-service-status-json",
        "service-status",
    )

    assert_service_status_json_result(
        result,
        errors,
        "mvp-wrapper-ps1-service-status-json",
        expected_db="target\\mvp\\service-status.db",
        expected_db_source="session",
        expected_task_id="task-wrapper-service-status",
        expected_target_scope="scope:target/mvp/service-status.txt",
        expected_requires_write=True,
        expected_doctor_bypass=False,
        expected_permission_tier="TIER_1",
        expected_permission_policy="confirm",
        expected_permission_reason="write_scope_requires_confirmation",
        expected_lease_state="released",
        expected_lease_freshness="lost",
        expected_lease_owner_id="safeclaw-mvp",
        expected_lease_fencing_token=1,
        expected_heartbeat_freshness="none",
        expected_heartbeat_status="idle",
        expected_heartbeat_interval_ms=10000,
        expected_heartbeat_event_driven=True,
        expected_heartbeat_reason="no_active_lease_heartbeat",
        expect_heartbeat_latest_updated_at_absent=True,
        expect_heartbeat_latest_age_ms_absent=True,
        expected_next_action="ok",
        expected_next_command='safeclaw.cmd report --db "target/mvp/service-status.db" --task-id "task-wrapper-service-status"',
        expected_next_reason="execution_already_confirmed",
        expected_next_blocker="none",
        expected_next_summary="ready_now:action=ok,reason=execution_already_confirmed",
        expected_coordination_status="clear",
        expected_coordination_reason="execution_already_confirmed",
        expected_coordination_summary="no_followup_needed",
        expected_service_coordination_status="clear",
        expected_service_coordination_reason="execution_already_confirmed",
        expected_service_coordination_summary="no_followup_needed",
    )


def append_wrapper_service_status_invalid_limit_json_errors(errors: list[str]) -> None:
    assert_command_json_error(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "service-status",
            "--limit",
            "bogus",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-status-invalid-limit-json",
        "service-status",
        expected_error_message_substring="invalid --limit: bogus",
    )


def append_wrapper_service_status_hibernated_seed_failed_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-failed",
            "--reset",
            "--task-id",
            "task-wrapper-service-status-hibernated",
            "--db",
            "target/mvp/service-status-hibernated.db",
            "--output",
            "target/mvp/service-status-hibernated.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-status-hibernated-seed-failed-json",
        "seed-failed",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-service-status-hibernated-seed-failed-json",
        expected_task_id="task-wrapper-service-status-hibernated",
        expected_db_path="target/mvp/service-status-hibernated.db",
        expected_output_path="target/mvp/service-status-hibernated.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )


def append_wrapper_service_status_hibernated_state_setup_errors(errors: list[str]) -> None:
    hibernated_db_path = REPO_ROOT / "target" / "mvp" / "service-status-hibernated.db"

    future_updated_at = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 5)
    )

    with sqlite3.connect(hibernated_db_path) as connection:
        connection.execute(
            "UPDATE task_snapshots SET worker_state = ?1, updated_at = ?2 WHERE task_id = ?3",
            ("hibernated", future_updated_at, "task-wrapper-service-status-hibernated"),
        )

        connection.execute(
            "UPDATE orchestrator_leases SET released_at_ms = ?1 WHERE task_id = ?2",
            (int(time.time() * 1000), "task-wrapper-service-status-hibernated"),
        )

        connection.commit()


def append_wrapper_service_status_hibernated_text_errors(errors: list[str]) -> None:
    wrapper_service_status_hibernated = subprocess.run(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "service-status",
            "--db",
            "target/mvp/service-status-hibernated.db",
            "--limit",
            "1",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_service_status_hibernated_output = (
        wrapper_service_status_hibernated.stdout or ""
    ) + (wrapper_service_status_hibernated.stderr or "")

    if wrapper_service_status_hibernated.returncode != 0:
        errors.append(
            f"mvp-wrapper-service-status-hibernated failed: exit={wrapper_service_status_hibernated.returncode}"
        )

    elif (
        "[mvp-wrapper] service workers => hibernated=1"
        not in wrapper_service_status_hibernated_output
    ):
        errors.append(
            "mvp-wrapper-service-status-hibernated missing hibernated worker summary"
        )

    elif (
        "[mvp-wrapper] service coordination => status=hibernated reason=hibernated_waiting_for_resume summary=inspect_and_resume_or_expire task=task-wrapper-service-status-hibernated"
        not in wrapper_service_status_hibernated_output
    ):
        errors.append(
            "mvp-wrapper-service-status-hibernated missing hibernated coordination summary"
        )

    elif "worker=hibernated" not in wrapper_service_status_hibernated_output:
        errors.append(
            "mvp-wrapper-service-status-hibernated missing hibernated recent task"
        )

    elif (
        'next=inspect next_reason=hibernated_waiting_for_resume blocker=manual_review_needed coordination=hibernated coordination_reason=hibernated_waiting_for_resume coordination_summary=inspect_and_resume_or_expire next_summary=blocked:action=inspect,blocker=manual_review_needed,reason=hibernated_waiting_for_resume next_cmd=safeclaw.cmd service-resume --db "target/mvp/service-status-hibernated.db" --task-id "task-wrapper-service-status-hibernated" --limit 1 --report'
        not in wrapper_service_status_hibernated_output
    ):
        errors.append(
            "mvp-wrapper-service-status-hibernated missing hibernated next hints"
        )


def append_wrapper_service_status_hibernated_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "service-status",
            "--db",
            "target/mvp/service-status-hibernated.db",
            "--limit",
            "1",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-status-hibernated-json",
        "service-status",
    )

    if result is not None:
        coordination = result.get("coordination") or {}

        recent_tasks = result.get("recent_tasks") or []

        current_session = result.get("current_session") or {}

        if (
            not isinstance(current_session, dict)
            or current_session.get("task_id")
            != "task-wrapper-service-status-hibernated"
        ):
            errors.append(
                "mvp-wrapper-service-status-hibernated-json missing current_session task-wrapper-service-status-hibernated"
            )

        elif (result.get("workers") or {}).get("hibernated") != 1:
            errors.append(
                "mvp-wrapper-service-status-hibernated-json missing workers.hibernated=1"
            )

        elif coordination.get("status") != "hibernated":
            errors.append(
                "mvp-wrapper-service-status-hibernated-json missing coordination.status=hibernated"
            )

        elif coordination.get("reason") != "hibernated_waiting_for_resume":
            errors.append(
                "mvp-wrapper-service-status-hibernated-json missing coordination.reason=hibernated_waiting_for_resume"
            )

        elif coordination.get("summary") != "inspect_and_resume_or_expire":
            errors.append(
                "mvp-wrapper-service-status-hibernated-json missing coordination.summary=inspect_and_resume_or_expire"
            )

        elif (
            coordination.get("next_task_id") != "task-wrapper-service-status-hibernated"
        ):
            errors.append(
                "mvp-wrapper-service-status-hibernated-json missing coordination.next_task_id=task-wrapper-service-status-hibernated"
            )

        elif not isinstance(recent_tasks, list) or not recent_tasks:
            errors.append(
                "mvp-wrapper-service-status-hibernated-json missing recent task"
            )

        elif recent_tasks[0].get("task_id") != "task-wrapper-service-status-hibernated":
            errors.append(
                "mvp-wrapper-service-status-hibernated-json missing recent task task-wrapper-service-status-hibernated"
            )

        elif recent_tasks[0].get("worker_state") != "hibernated":
            errors.append(
                "mvp-wrapper-service-status-hibernated-json missing worker_state=hibernated"
            )

        elif recent_tasks[0].get("lease_state") != "released":
            errors.append(
                "mvp-wrapper-service-status-hibernated-json missing lease_state=released"
            )

        elif recent_tasks[0].get("next_action") != "inspect":
            errors.append(
                "mvp-wrapper-service-status-hibernated-json missing next_action=inspect"
            )

        elif recent_tasks[0].get("next_reason") != "hibernated_waiting_for_resume":
            errors.append(
                "mvp-wrapper-service-status-hibernated-json missing next_reason=hibernated_waiting_for_resume"
            )

        elif recent_tasks[0].get("next_blocker") != "manual_review_needed":
            errors.append(
                "mvp-wrapper-service-status-hibernated-json missing next_blocker=manual_review_needed"
            )

        elif (
            recent_tasks[0].get("next_summary")
            != "blocked:action=inspect,blocker=manual_review_needed,reason=hibernated_waiting_for_resume"
        ):
            errors.append(
                "mvp-wrapper-service-status-hibernated-json missing next_summary hibernated payload"
            )

        elif recent_tasks[0].get("coordination_status") != "hibernated":
            errors.append(
                "mvp-wrapper-service-status-hibernated-json missing coordination_status=hibernated"
            )

        elif (
            recent_tasks[0].get("coordination_reason")
            != "hibernated_waiting_for_resume"
        ):
            errors.append(
                "mvp-wrapper-service-status-hibernated-json missing coordination_reason=hibernated_waiting_for_resume"
            )

        elif (
            recent_tasks[0].get("coordination_summary")
            != "inspect_and_resume_or_expire"
        ):
            errors.append(
                "mvp-wrapper-service-status-hibernated-json missing coordination_summary=inspect_and_resume_or_expire"
            )

        elif (
            recent_tasks[0].get("next_command")
            != 'safeclaw.cmd service-resume --db "target/mvp/service-status-hibernated.db" --task-id "task-wrapper-service-status-hibernated" --limit 1 --report'
        ):
            errors.append(
                "mvp-wrapper-service-status-hibernated-json missing next_command=service-resume"
            )


def append_wrapper_service_resume_json_seed_hibernated_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-hibernated",
            "--reset",
            "--task-id",
            "task-wrapper-service-resume-json",
            "--db",
            "target/mvp/service-resume-json.db",
            "--output",
            "target/mvp/service-resume-json.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-resume-json-seed-hibernated-json",
        "seed-hibernated",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-service-resume-json-seed-hibernated-json",
        expected_task_id="task-wrapper-service-resume-json",
        expected_db_path="target/mvp/service-resume-json.db",
        expected_output_path="target/mvp/service-resume-json.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )


def append_wrapper_cmd_service_resume_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            "cmd",
            "/c",
            "tools\\mvp\\safeclaw_mvp.cmd",
            "service-resume",
            "--db",
            "target/mvp/service-resume-json.db",
            "--task-id",
            "task-wrapper-service-resume-json",
            "--limit",
            "1",
            "--report",
            "--json",
        ],
        errors,
        "mvp-wrapper-cmd-service-resume-json",
        "service-resume",
    )

    assert_service_resume_json_result(
        result,
        errors,
        "mvp-wrapper-cmd-service-resume-json",
        expected_db="target\\mvp\\service-resume-json.db",
        expected_db_source="flag",
        expected_task_id="task-wrapper-service-resume-json",
        expected_limit=1,
        expected_steps=["resume", "service-status", "report"],
        expect_report_payload=True,
    )


def append_wrapper_resume_json_seed_hibernated_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-hibernated",
            "--reset",
            "--task-id",
            "task-wrapper-resume-json",
            "--db",
            "target/mvp/resume-json.db",
            "--output",
            "target/mvp/resume-json.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-resume-json-seed-hibernated-json",
        "seed-hibernated",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-resume-json-seed-hibernated-json",
        expected_task_id="task-wrapper-resume-json",
        expected_db_path="target/mvp/resume-json.db",
        expected_output_path="target/mvp/resume-json.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )


def append_wrapper_resume_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "resume",
            "--db",
            "target/mvp/resume-json.db",
            "--task-id",
            "task-wrapper-resume-json",
            "--output",
            "target/mvp/resume-json.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-resume-json",
        "resume",
    )

    if result is not None:
        prepared = result.get("prepared") or []

        remembered_session = result.get("remembered_session") or {}

        source_hints = result.get("source_hints") or {}

        captured_output = str(result.get("captured_output") or "")

        if not prepared or prepared[0] != "resume":
            errors.append("mvp-wrapper-resume-json missing prepared resume")

        elif "task-wrapper-resume-json" not in captured_output:
            errors.append(
                "mvp-wrapper-resume-json missing captured task task-wrapper-resume-json"
            )

        elif result.get("saved_session") is not None:
            errors.append("mvp-wrapper-resume-json should not save session")

        elif (
            not isinstance(remembered_session, dict)
            or remembered_session.get("task_id") != "task-wrapper-resume-json"
        ):
            errors.append(
                "mvp-wrapper-resume-json missing remembered session task-wrapper-resume-json"
            )

        elif remembered_session.get("db") != "target/mvp/resume-json.db":
            errors.append("mvp-wrapper-resume-json missing remembered session db")

        elif remembered_session.get("output") != "target/mvp/resume-json.txt":
            errors.append("mvp-wrapper-resume-json missing remembered session output")

        elif not isinstance(source_hints, dict) or source_hints.get("db") != "flag":
            errors.append("mvp-wrapper-resume-json missing source_hints.db=flag")

        elif source_hints.get("output") != "flag":
            errors.append("mvp-wrapper-resume-json missing source_hints.output=flag")

        elif source_hints.get("owner_id") != "session":
            errors.append(
                "mvp-wrapper-resume-json missing source_hints.owner_id=session"
            )

        elif source_hints.get("task_context") != "flag":
            errors.append(
                "mvp-wrapper-resume-json missing source_hints.task_context=flag"
            )


def append_wrapper_cmd_resume_json_seed_hibernated_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            "cmd",
            "/c",
            "tools\\mvp\\safeclaw_mvp.cmd",
            "seed-hibernated",
            "--reset",
            "--task-id",
            "task-wrapper-cmd-resume-json",
            "--db",
            "target/mvp/cmd-resume-json.db",
            "--output",
            "target/mvp/cmd-resume-json.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-cmd-resume-json-seed-hibernated-json",
        "seed-hibernated",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-cmd-resume-json-seed-hibernated-json",
        expected_task_id="task-wrapper-cmd-resume-json",
        expected_db_path="target/mvp/cmd-resume-json.db",
        expected_output_path="target/mvp/cmd-resume-json.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )


def append_wrapper_cmd_resume_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            "cmd",
            "/c",
            "tools\\mvp\\safeclaw_mvp.cmd",
            "resume",
            "--db",
            "target/mvp/cmd-resume-json.db",
            "--task-id",
            "task-wrapper-cmd-resume-json",
            "--output",
            "target/mvp/cmd-resume-json.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-cmd-resume-json",
        "resume",
    )

    if result is not None:
        prepared = result.get("prepared") or []

        remembered_session = result.get("remembered_session") or {}

        source_hints = result.get("source_hints") or {}

        captured_output = str(result.get("captured_output") or "")

        if not prepared or prepared[0] != "resume":
            errors.append("mvp-wrapper-cmd-resume-json missing prepared resume")

        elif "task-wrapper-cmd-resume-json" not in captured_output:
            errors.append(
                "mvp-wrapper-cmd-resume-json missing captured task task-wrapper-cmd-resume-json"
            )

        elif result.get("saved_session") is not None:
            errors.append("mvp-wrapper-cmd-resume-json should not save session")

        elif (
            not isinstance(remembered_session, dict)
            or remembered_session.get("task_id") != "task-wrapper-cmd-resume-json"
        ):
            errors.append(
                "mvp-wrapper-cmd-resume-json missing remembered session task-wrapper-cmd-resume-json"
            )

        elif remembered_session.get("db") != "target/mvp/cmd-resume-json.db":
            errors.append("mvp-wrapper-cmd-resume-json missing remembered session db")

        elif remembered_session.get("output") != "target/mvp/cmd-resume-json.txt":
            errors.append(
                "mvp-wrapper-cmd-resume-json missing remembered session output"
            )

        elif not isinstance(source_hints, dict) or source_hints.get("db") != "flag":
            errors.append("mvp-wrapper-cmd-resume-json missing source_hints.db=flag")

        elif source_hints.get("output") != "flag":
            errors.append(
                "mvp-wrapper-cmd-resume-json missing source_hints.output=flag"
            )

        elif source_hints.get("owner_id") != "session":
            errors.append(
                "mvp-wrapper-cmd-resume-json missing source_hints.owner_id=session"
            )

        elif source_hints.get("task_context") != "flag":
            errors.append(
                "mvp-wrapper-cmd-resume-json missing source_hints.task_context=flag"
            )


def append_wrapper_cmd_seed_hibernated_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            "cmd",
            "/c",
            "tools\\mvp\\safeclaw_mvp.cmd",
            "seed-hibernated",
            "--reset",
            "--task-id",
            "task-wrapper-cmd-seed-hibernated-json",
            "--db",
            "target/mvp/cmd-seed-hibernated-json.db",
            "--output",
            "target/mvp/cmd-seed-hibernated-json.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-cmd-seed-hibernated-json",
        "seed-hibernated",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-cmd-seed-hibernated-json",
        expected_task_id="task-wrapper-cmd-seed-hibernated-json",
        expected_db_path="target/mvp/cmd-seed-hibernated-json.db",
        expected_output_path="target/mvp/cmd-seed-hibernated-json.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )


def append_wrapper_service_resume_not_hibernated_seed_failed_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-failed",
            "--reset",
            "--task-id",
            "task-wrapper-service-resume-not-hibernated",
            "--db",
            "target/mvp/service-resume-not-hibernated.db",
            "--output",
            "target/mvp/service-resume-not-hibernated.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-resume-not-hibernated-seed-failed-json",
        "seed-failed",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-service-resume-not-hibernated-seed-failed-json",
        expected_task_id="task-wrapper-service-resume-not-hibernated",
        expected_db_path="target/mvp/service-resume-not-hibernated.db",
        expected_output_path="target/mvp/service-resume-not-hibernated.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )


def append_wrapper_cmd_service_resume_not_hibernated_errors(errors: list[str]) -> None:
    assert_command_failure_output(
        [
            "cmd",
            "/c",
            "tools\\mvp\\safeclaw_mvp.cmd",
            "service-resume",
            "--db",
            "target/mvp/service-resume-not-hibernated.db",
            "--task-id",
            "task-wrapper-service-resume-not-hibernated",
            "--limit",
            "1",
        ],
        errors,
        "mvp-wrapper-cmd-service-resume-not-hibernated",
        expected_substring='[mvp-wrapper] service-resume hint => current task is not hibernated; inspect state via safeclaw.cmd service-status --db "target/mvp/service-resume-not-hibernated.db" --limit 1',
        missing_output_label="mvp-wrapper-cmd-service-resume-not-hibernated missing resume hint",
        expected_exit=1,
    )


def append_wrapper_service_resume_not_hibernated_json_seed_failed_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-failed",
            "--reset",
            "--task-id",
            "task-wrapper-service-resume-not-hibernated-json",
            "--db",
            "target/mvp/service-resume-not-hibernated-json.db",
            "--output",
            "target/mvp/service-resume-not-hibernated-json.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-resume-not-hibernated-json-seed-failed-json",
        "seed-failed",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-service-resume-not-hibernated-json-seed-failed-json",
        expected_task_id="task-wrapper-service-resume-not-hibernated-json",
        expected_db_path="target/mvp/service-resume-not-hibernated-json.db",
        expected_output_path="target/mvp/service-resume-not-hibernated-json.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )


def append_wrapper_service_resume_json_seed_hibernated_ps1_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-hibernated",
            "--reset",
            "--task-id",
            "task-wrapper-service-resume-json",
            "--db",
            "target/mvp/service-resume-json.db",
            "--output",
            "target/mvp/service-resume-json.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-resume-json-seed-hibernated-ps1-json",
        "seed-hibernated",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-service-resume-json-seed-hibernated-ps1-json",
        expected_task_id="task-wrapper-service-resume-json",
        expected_db_path="target/mvp/service-resume-json.db",
        expected_output_path="target/mvp/service-resume-json.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )


def append_wrapper_ps1_service_resume_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "service-resume",
            "--db",
            "target/mvp/service-resume-json.db",
            "--task-id",
            "task-wrapper-service-resume-json",
            "--limit",
            "1",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-service-resume-json",
        "service-resume",
    )

    assert_service_resume_json_result(
        result,
        errors,
        "mvp-wrapper-ps1-service-resume-json",
        expected_db="target\mvp\service-resume-json.db",
        expected_db_source="flag",
        expected_task_id="task-wrapper-service-resume-json",
        expected_limit=1,
    )


def append_wrapper_service_resume_report_json_seed_hibernated_ps1_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-hibernated",
            "--reset",
            "--task-id",
            "task-wrapper-service-resume-report-json",
            "--db",
            "target/mvp/service-resume-report-json.db",
            "--output",
            "target/mvp/service-resume-report-json.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-resume-report-json-seed-hibernated-ps1-json",
        "seed-hibernated",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-service-resume-report-json-seed-hibernated-ps1-json",
        expected_task_id="task-wrapper-service-resume-report-json",
        expected_db_path="target/mvp/service-resume-report-json.db",
        expected_output_path="target/mvp/service-resume-report-json.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )


def append_wrapper_ps1_service_resume_report_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "service-resume",
            "--db",
            "target/mvp/service-resume-report-json.db",
            "--task-id",
            "task-wrapper-service-resume-report-json",
            "--limit",
            "1",
            "--report",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-service-resume-report-json",
        "service-resume",
    )

    assert_service_resume_json_result(
        result,
        errors,
        "mvp-wrapper-ps1-service-resume-report-json",
        expected_db="target\mvp\service-resume-report-json.db",
        expected_db_source="flag",
        expected_task_id="task-wrapper-service-resume-report-json",
        expected_limit=1,
        expected_steps=["resume", "service-status", "report"],
        expect_report_payload=True,
    )


def append_wrapper_cmd_service_resume_not_hibernated_json_errors(errors: list[str]) -> None:
    assert_command_json_error(
        [
            "cmd",
            "/c",
            "tools\mvp\safeclaw_mvp.cmd",
            "service-resume",
            "--db",
            "target/mvp/service-resume-not-hibernated-json.db",
            "--task-id",
            "task-wrapper-service-resume-not-hibernated-json",
            "--limit",
            "1",
            "--json",
        ],
        errors,
        "mvp-wrapper-cmd-service-resume-not-hibernated-json",
        "service-resume",
        expected_exit=1,
        expected_error_message_substring="failed step=resume",
        expected_top_level_error_code="resume-target-not-hibernated",
        expected_top_level_error_reason="resume_target_not_hibernated",
        expected_failed_step="resume",
        expected_code="resume-target-not-hibernated",
        expected_details_message_substring="resume only works for hibernated tasks",
    )


def append_wrapper_service_resume_missing_run_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "run",
            "--reset",
            "--task-id",
            "task-wrapper-service-resume-missing",
            "--db",
            "target/mvp/service-resume-missing.db",
            "--output",
            "target/mvp/service-resume-missing.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-resume-missing-run-json",
        "run",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-service-resume-missing-run-json",
        expected_task_id="task-wrapper-service-resume-missing",
        expected_db_path="target/mvp/service-resume-missing.db",
        expected_output_path="target/mvp/service-resume-missing.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )


def append_wrapper_service_resume_missing_json_errors(errors: list[str]) -> None:
    assert_command_json_error(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "service-resume",
            "--db",
            "target/mvp/service-resume-missing.db",
            "--task-id",
            "task-wrapper-service-resume-missing",
            "--limit",
            "1",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-resume-missing-json",
        "service-resume",
        expected_exit=1,
        expected_error_message_substring="failed step=resume",
        expected_top_level_error_code="resume-target-missing",
        expected_top_level_error_reason="hibernated_runtime_missing",
        expected_failed_step="resume",
        expected_code="resume-target-missing",
        expected_details_message_substring="resume requires a hibernated runtime for the selected task",
    )


def append_wrapper_service_status_active_seed_failed_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-failed",
            "--reset",
            "--task-id",
            "task-wrapper-service-status-active",
            "--db",
            "target/mvp/service-status-active.db",
            "--output",
            "target/mvp/service-status-active.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-status-active-seed-failed-json",
        "seed-failed",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-service-status-active-seed-failed-json",
        expected_task_id="task-wrapper-service-status-active",
        expected_db_path="target/mvp/service-status-active.db",
        expected_output_path="target/mvp/service-status-active.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )


def append_wrapper_service_status_active_state_setup_errors(errors: list[str]) -> None:
    active_db_path = REPO_ROOT / "target" / "mvp" / "service-status-active.db"

    future_expires_at_ms = int(time.time() * 1000) + 45_000

    with sqlite3.connect(active_db_path) as connection:
        connection.execute(
            """

            UPDATE orchestrator_leases

            SET expires_at_ms = ?1,

                released_at_ms = NULL

            WHERE task_id = ?2

            """,
            (future_expires_at_ms, "task-wrapper-service-status-active"),
        )

        connection.commit()


def append_wrapper_service_status_active_text_errors(errors: list[str]) -> None:
    wrapper_service_status_active = subprocess.run(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "service-status",
            "--db",
            "target/mvp/service-status-active.db",
            "--limit",
            "1",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_service_status_active_output = (
        wrapper_service_status_active.stdout or ""
    ) + (wrapper_service_status_active.stderr or "")

    if wrapper_service_status_active.returncode != 0:
        errors.append(
            f"mvp-wrapper-service-status-active failed: exit={wrapper_service_status_active.returncode}"
        )

    elif (
        "[mvp-wrapper] service queue => queued=0 active=1 expired=0 completed=0"
        not in wrapper_service_status_active_output
    ):
        errors.append("mvp-wrapper-service-status-active missing active queue summary")

    elif (
        "[mvp-wrapper] service heartbeat => interval_ms=10000 event_driven=true latest_updated_at="
        not in wrapper_service_status_active_output
    ):
        errors.append("mvp-wrapper-service-status-active missing heartbeat summary")

    elif " age_ms=" not in wrapper_service_status_active_output:
        errors.append("mvp-wrapper-service-status-active missing heartbeat age")

    elif (
        "freshness=lost status=failed reason=recent_task_update_exceeded_grace_window"
        not in wrapper_service_status_active_output
    ):
        errors.append("mvp-wrapper-service-status-active missing heartbeat freshness")

    elif (
        "[mvp-wrapper] service coordination => status=stalled reason=active_lease_without_recent_heartbeat summary=inspect_owner_or_wait_for_lease_expiry task=task-wrapper-service-status-active"
        not in wrapper_service_status_active_output
    ):
        errors.append("mvp-wrapper-service-status-active missing coordination summary")

    elif (
        "task=task-wrapper-service-status-active"
        not in wrapper_service_status_active_output
    ):
        errors.append("mvp-wrapper-service-status-active missing recent task")

    elif (
        "perm=confirm perm_tier=TIER_1 perm_reason=write_scope_requires_confirmation"
        not in wrapper_service_status_active_output
    ):
        errors.append("mvp-wrapper-service-status-active missing permission visibility")

    elif (
        "lease=active lease_owner=safeclaw-mvp lease_fence=1 lease_age_ms="
        not in wrapper_service_status_active_output
    ):
        errors.append(
            "mvp-wrapper-service-status-active missing active lease age visibility"
        )

    elif "lease_freshness=lost" not in wrapper_service_status_active_output:
        errors.append(
            "mvp-wrapper-service-status-active missing active lease freshness visibility"
        )

    elif (
        "next=inspect next_reason=lease_still_active blocker=active_lease coordination=stalled coordination_reason=active_lease_without_recent_heartbeat coordination_summary=inspect_owner_or_wait_for_lease_expiry next_summary=wait:"
        not in wrapper_service_status_active_output
    ):
        errors.append("mvp-wrapper-service-status-active missing active next hint")

    elif "wait_ms=" not in wrapper_service_status_active_output:
        errors.append("mvp-wrapper-service-status-active missing wait_ms visibility")


def append_wrapper_service_status_active_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "service-status",
            "--db",
            "target/mvp/service-status-active.db",
            "--limit",
            "1",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-status-active-json",
        "service-status",
    )

    if result is not None:
        queue = result.get("queue") or {}

        workers = result.get("workers") or {}

        effects = result.get("effects") or {}

        probes = result.get("probes") or {}

        heartbeat = result.get("heartbeat") or {}

        recent_tasks = result.get("recent_tasks") or []

        if queue.get("queued") != 0:
            errors.append(
                "mvp-wrapper-service-status-active-json missing queue.queued=0"
            )

        elif queue.get("active") != 1:
            errors.append(
                "mvp-wrapper-service-status-active-json missing queue.active=1"
            )

        elif queue.get("expired") != 0:
            errors.append(
                "mvp-wrapper-service-status-active-json missing queue.expired=0"
            )

        elif queue.get("completed") != 0:
            errors.append(
                "mvp-wrapper-service-status-active-json missing queue.completed=0"
            )

        elif workers.get("failed") != 1:
            errors.append(
                "mvp-wrapper-service-status-active-json missing workers.failed=1"
            )

        elif effects.get("prepared") != 1:
            errors.append(
                "mvp-wrapper-service-status-active-json missing effects.prepared=1"
            )

        elif probes.get("none") != 1:
            errors.append(
                "mvp-wrapper-service-status-active-json missing probes.none=1"
            )

        elif heartbeat.get("latest_freshness") != "lost":
            errors.append(
                "mvp-wrapper-service-status-active-json missing heartbeat.latest_freshness=lost"
            )

        elif heartbeat.get("status") != "failed":
            errors.append(
                "mvp-wrapper-service-status-active-json missing heartbeat.status=failed"
            )

        elif heartbeat.get("interval_ms") != 10000:
            errors.append(
                "mvp-wrapper-service-status-active-json missing heartbeat.interval_ms=10000"
            )

        elif heartbeat.get("event_driven") is not True:
            errors.append(
                "mvp-wrapper-service-status-active-json missing heartbeat.event_driven=true"
            )

        elif heartbeat.get("reason") != "recent_task_update_exceeded_grace_window":
            errors.append(
                "mvp-wrapper-service-status-active-json missing heartbeat.reason=recent_task_update_exceeded_grace_window"
            )

        elif not heartbeat.get("latest_updated_at"):
            errors.append(
                "mvp-wrapper-service-status-active-json missing heartbeat.latest_updated_at"
            )

        elif not isinstance(heartbeat.get("latest_age_ms"), int):
            errors.append(
                "mvp-wrapper-service-status-active-json missing heartbeat.latest_age_ms int"
            )

        elif not isinstance(recent_tasks, list) or not recent_tasks:
            errors.append("mvp-wrapper-service-status-active-json missing recent task")

        elif recent_tasks[0].get("permission_tier") != "TIER_1":
            errors.append(
                "mvp-wrapper-service-status-active-json missing permission_tier=TIER_1"
            )

        elif recent_tasks[0].get("permission_policy") != "confirm":
            errors.append(
                "mvp-wrapper-service-status-active-json missing permission_policy=confirm"
            )

        elif (
            recent_tasks[0].get("permission_reason")
            != "write_scope_requires_confirmation"
        ):
            errors.append(
                "mvp-wrapper-service-status-active-json missing permission_reason=write_scope_requires_confirmation"
            )

        elif recent_tasks[0].get("lease_state") != "active":
            errors.append(
                "mvp-wrapper-service-status-active-json missing lease_state=active"
            )

        elif recent_tasks[0].get("lease_freshness") != "lost":
            errors.append(
                "mvp-wrapper-service-status-active-json missing lease_freshness=lost"
            )

        elif recent_tasks[0].get("next_action") != "inspect":
            errors.append(
                "mvp-wrapper-service-status-active-json missing next_action=inspect"
            )

        elif recent_tasks[0].get("next_reason") != "lease_still_active":
            errors.append(
                "mvp-wrapper-service-status-active-json missing next_reason=lease_still_active"
            )

        elif recent_tasks[0].get("next_blocker") != "active_lease":
            errors.append(
                "mvp-wrapper-service-status-active-json missing next_blocker=active_lease"
            )

        elif (
            recent_tasks[0].get("next_command")
            != 'safeclaw.cmd report --db "target/mvp/service-status-active.db" --task-id "task-wrapper-service-status-active"'
        ):
            errors.append(
                "mvp-wrapper-service-status-active-json missing next_command=report"
            )

        elif recent_tasks[0].get("coordination_status") != "stalled":
            errors.append(
                "mvp-wrapper-service-status-active-json missing coordination_status=stalled"
            )

        elif (
            recent_tasks[0].get("coordination_reason")
            != "active_lease_without_recent_heartbeat"
        ):
            errors.append(
                "mvp-wrapper-service-status-active-json missing coordination_reason=active_lease_without_recent_heartbeat"
            )

        elif (
            recent_tasks[0].get("coordination_summary")
            != "inspect_owner_or_wait_for_lease_expiry"
        ):
            errors.append(
                "mvp-wrapper-service-status-active-json missing coordination_summary=inspect_owner_or_wait_for_lease_expiry"
            )

        elif (result.get("coordination") or {}).get("status") != "stalled":
            errors.append(
                "mvp-wrapper-service-status-active-json missing coordination.status=stalled"
            )

        elif not isinstance(recent_tasks, list) or not recent_tasks:
            errors.append("mvp-wrapper-service-status-active-json missing recent task")

        elif recent_tasks[0].get("permission_tier") != "TIER_1":
            errors.append(
                "mvp-wrapper-service-status-active-json missing permission_tier=TIER_1"
            )

        elif recent_tasks[0].get("permission_policy") != "confirm":
            errors.append(
                "mvp-wrapper-service-status-active-json missing permission_policy=confirm"
            )

        elif (
            recent_tasks[0].get("permission_reason")
            != "write_scope_requires_confirmation"
        ):
            errors.append(
                "mvp-wrapper-service-status-active-json missing permission_reason=write_scope_requires_confirmation"
            )

        elif recent_tasks[0].get("lease_state") != "active":
            errors.append(
                "mvp-wrapper-service-status-active-json missing lease_state=active"
            )

        elif recent_tasks[0].get("next_action") != "inspect":
            errors.append(
                "mvp-wrapper-service-status-active-json missing next_action=inspect"
            )

        elif recent_tasks[0].get("next_reason") != "lease_still_active":
            errors.append(
                "mvp-wrapper-service-status-active-json missing next_reason=lease_still_active"
            )

        elif recent_tasks[0].get("next_blocker") != "active_lease":
            errors.append(
                "mvp-wrapper-service-status-active-json missing next_blocker=active_lease"
            )

        elif (
            recent_tasks[0].get("next_command")
            != 'safeclaw.cmd report --db "target/mvp/service-status-active.db" --task-id "task-wrapper-service-status-active"'
        ):
            errors.append(
                "mvp-wrapper-service-status-active-json missing next_command=report"
            )

        else:
            lease_remaining_ms = recent_tasks[0].get("lease_remaining_ms")

            next_summary = recent_tasks[0].get("next_summary")

            if not isinstance(lease_remaining_ms, int) or lease_remaining_ms <= 0:
                errors.append(
                    "mvp-wrapper-service-status-active-json missing positive lease_remaining_ms"
                )

            elif not isinstance(next_summary, str) or not next_summary.startswith(
                "wait:remaining_ms="
            ):
                errors.append(
                    "mvp-wrapper-service-status-active-json missing next_summary wait prefix"
                )

            elif ",blocker=active_lease,reason=lease_still_active" not in next_summary:
                errors.append(
                    "mvp-wrapper-service-status-active-json missing next_summary active payload"
                )


def append_wrapper_service_status_scope_a_seed_failed_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-failed",
            "--reset",
            "--task-id",
            "task-wrapper-service-status-scope-a",
            "--db",
            "target/mvp/service-status-scope.db",
            "--output",
            "target/mvp/service-status-scope-a.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-status-scope-a-seed-failed-json",
        "seed-failed",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-service-status-scope-a-seed-failed-json",
        expected_task_id="task-wrapper-service-status-scope-a",
        expected_db_path="target/mvp/service-status-scope.db",
        expected_output_path="target/mvp/service-status-scope-a.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )


def append_wrapper_service_status_scope_b_seed_failed_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-failed",
            "--task-id",
            "task-wrapper-service-status-scope-b",
            "--db",
            "target/mvp/service-status-scope.db",
            "--output",
            "target/mvp/service-status-scope-b.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-status-scope-b-seed-failed-json",
        "seed-failed",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-service-status-scope-b-seed-failed-json",
        expected_task_id="task-wrapper-service-status-scope-b",
        expected_db_path="target/mvp/service-status-scope.db",
        expected_output_path="target/mvp/service-status-scope-b.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )


def append_wrapper_service_status_scope_use_json_errors(errors: list[str]) -> None:
    scope_db_path = REPO_ROOT / "target" / "mvp" / "service-status-scope.db"

    shared_scope = "scope:target/mvp/service-status-shared.txt"

    future_expires_at_ms = int(time.time() * 1000) + 45_000

    latest_updated_at = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 5)
    )

    with sqlite3.connect(scope_db_path) as connection:
        connection.execute(
            "UPDATE orchestrator_tasks SET target_scope = ?1 WHERE task_id IN (?2, ?3)",
            (
                shared_scope,
                "task-wrapper-service-status-scope-a",
                "task-wrapper-service-status-scope-b",
            ),
        )

        connection.execute(
            """

            UPDATE orchestrator_leases

            SET expires_at_ms = ?1,

                released_at_ms = NULL

            WHERE task_id = ?2

            """,
            (int(time.time() * 1000) - 1_000, "task-wrapper-service-status-scope-a"),
        )

        connection.execute(
            """

            UPDATE orchestrator_leases

            SET expires_at_ms = ?1,

                released_at_ms = NULL

            WHERE task_id = ?2

            """,
            (future_expires_at_ms, "task-wrapper-service-status-scope-b"),
        )

        connection.execute(
            "UPDATE task_snapshots SET updated_at = ?1 WHERE task_id = ?2",
            (latest_updated_at, "task-wrapper-service-status-scope-a"),
        )

        connection.commit()

    use_scope_result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "use",
            "--db",
            "target/mvp/service-status-scope.db",
            "--task-id",
            "task-wrapper-service-status-scope-a",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-status-scope-use-json",
        "use",
    )

    if use_scope_result is not None:
        if use_scope_result.get("task_id") != "task-wrapper-service-status-scope-a":
            errors.append(
                "mvp-wrapper-service-status-scope-use-json missing task-wrapper-service-status-scope-a"
            )

        elif use_scope_result.get("db") != "target/mvp/service-status-scope.db":
            errors.append("mvp-wrapper-service-status-scope-use-json missing scope db")


def append_wrapper_service_status_scope_text_errors(errors: list[str]) -> None:
    wrapper_service_status_scope = subprocess.run(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "service-status",
            "--db",
            "target/mvp/service-status-scope.db",
            "--limit",
            "2",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_service_status_scope_output = (
        wrapper_service_status_scope.stdout or ""
    ) + (wrapper_service_status_scope.stderr or "")

    if wrapper_service_status_scope.returncode != 0:
        errors.append(
            f"mvp-wrapper-service-status-scope failed: exit={wrapper_service_status_scope.returncode}"
        )

    elif (
        "[mvp-wrapper] service coordination => status=contended reason=same_scope_peer_active summary=wait_for_scope_peer_release task=task-wrapper-service-status-scope-a"
        not in wrapper_service_status_scope_output
    ):
        errors.append(
            "mvp-wrapper-service-status-scope missing contended coordination summary"
        )

    elif (
        "scope_peers=1 scope_active_peers=1 scope_active_task=task-wrapper-service-status-scope-b"
        not in wrapper_service_status_scope_output
    ):
        errors.append(
            "mvp-wrapper-service-status-scope missing same-scope peer visibility"
        )

    elif "task=task-wrapper-service-status-scope-a" not in wrapper_service_status_scope_output:
        errors.append("mvp-wrapper-service-status-scope missing scope task a")


def append_wrapper_service_status_scope_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "service-status",
            "--db",
            "target/mvp/service-status-scope.db",
            "--limit",
            "2",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-status-scope-json",
        "service-status",
    )

    if result is not None:
        coordination = result.get("coordination") or {}

        recent_tasks = result.get("recent_tasks") or []

        current_session = result.get("current_session") or {}

        if (
            not isinstance(current_session, dict)
            or current_session.get("task_id") != "task-wrapper-service-status-scope-a"
        ):
            errors.append(
                "mvp-wrapper-service-status-scope-json missing current_session task-wrapper-service-status-scope-a"
            )

        elif coordination.get("status") != "contended":
            errors.append(
                "mvp-wrapper-service-status-scope-json missing coordination.status=contended"
            )

        elif coordination.get("reason") != "same_scope_peer_active":
            errors.append(
                "mvp-wrapper-service-status-scope-json missing coordination.reason=same_scope_peer_active"
            )

        elif coordination.get("summary") != "wait_for_scope_peer_release":
            errors.append(
                "mvp-wrapper-service-status-scope-json missing coordination.summary=wait_for_scope_peer_release"
            )

        elif coordination.get("scope_peer_count") != 1:
            errors.append(
                "mvp-wrapper-service-status-scope-json missing coordination.scope_peer_count=1"
            )

        elif coordination.get("scope_active_peer_count") != 1:
            errors.append(
                "mvp-wrapper-service-status-scope-json missing coordination.scope_active_peer_count=1"
            )

        elif (
            coordination.get("scope_active_peer_task_id")
            != "task-wrapper-service-status-scope-b"
        ):
            errors.append(
                "mvp-wrapper-service-status-scope-json missing coordination.scope_active_peer_task_id=task-wrapper-service-status-scope-b"
            )

        elif not isinstance(recent_tasks, list) or not recent_tasks:
            errors.append("mvp-wrapper-service-status-scope-json missing recent task")

        elif recent_tasks[0].get("task_id") != "task-wrapper-service-status-scope-a":
            errors.append("mvp-wrapper-service-status-scope-json missing recent task a")

        elif recent_tasks[0].get("next_action") != "retry":
            errors.append(
                "mvp-wrapper-service-status-scope-json missing next_action=retry"
            )

        elif recent_tasks[0].get("coordination_status") != "contended":
            errors.append(
                "mvp-wrapper-service-status-scope-json missing coordination_status=contended"
            )

        elif recent_tasks[0].get("coordination_reason") != "same_scope_peer_active":
            errors.append(
                "mvp-wrapper-service-status-scope-json missing coordination_reason=same_scope_peer_active"
            )

        elif (
            recent_tasks[0].get("coordination_summary") != "wait_for_scope_peer_release"
        ):
            errors.append(
                "mvp-wrapper-service-status-scope-json missing coordination_summary=wait_for_scope_peer_release"
            )

        elif recent_tasks[0].get("scope_peer_count") != 1:
            errors.append(
                "mvp-wrapper-service-status-scope-json missing scope_peer_count=1"
            )

        elif recent_tasks[0].get("scope_active_peer_count") != 1:
            errors.append(
                "mvp-wrapper-service-status-scope-json missing scope_active_peer_count=1"
            )

        elif (
            recent_tasks[0].get("scope_active_peer_task_id")
            != "task-wrapper-service-status-scope-b"
        ):
            errors.append(
                "mvp-wrapper-service-status-scope-json missing scope_active_peer_task_id=task-wrapper-service-status-scope-b"
            )

        elif (
            recent_tasks[0].get("next_summary")
            != "ready_now:action=retry,reason=failed_state_ready_for_retry"
        ):
            errors.append(
                "mvp-wrapper-service-status-scope-json missing next_summary retry"
            )


def append_wrapper_service_status_quarantine_a_seed_failed_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-failed",
            "--reset",
            "--task-id",
            "task-wrapper-service-status-quarantine-a",
            "--db",
            "target/mvp/service-status-quarantine.db",
            "--output",
            "target/mvp/service-status-quarantine-a.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-status-quarantine-a-seed-failed-json",
        "seed-failed",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-service-status-quarantine-a-seed-failed-json",
        expected_task_id="task-wrapper-service-status-quarantine-a",
        expected_db_path="target/mvp/service-status-quarantine.db",
        expected_output_path="target/mvp/service-status-quarantine-a.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )


def append_wrapper_service_status_quarantine_b_seed_failed_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-failed",
            "--task-id",
            "task-wrapper-service-status-quarantine-b",
            "--db",
            "target/mvp/service-status-quarantine.db",
            "--output",
            "target/mvp/service-status-quarantine-b.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-status-quarantine-b-seed-failed-json",
        "seed-failed",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-service-status-quarantine-b-seed-failed-json",
        expected_task_id="task-wrapper-service-status-quarantine-b",
        expected_db_path="target/mvp/service-status-quarantine.db",
        expected_output_path="target/mvp/service-status-quarantine-b.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )


def append_wrapper_service_status_quarantine_use_json_errors(errors: list[str]) -> None:
    quarantine_db_path = REPO_ROOT / "target" / "mvp" / "service-status-quarantine.db"

    shared_scope = "scope:target/mvp/service-status-quarantine-shared.txt"

    future_updated_at = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 5)
    )

    with sqlite3.connect(quarantine_db_path) as connection:
        connection.execute(
            "UPDATE orchestrator_tasks SET target_scope = ?1 WHERE task_id IN (?2, ?3)",
            (
                shared_scope,
                "task-wrapper-service-status-quarantine-a",
                "task-wrapper-service-status-quarantine-b",
            ),
        )

        connection.execute(
            "UPDATE task_snapshots SET effect_status = ?1 WHERE task_id = ?2",
            ("executed_assumed", "task-wrapper-service-status-quarantine-a"),
        )

        connection.execute(
            "UPDATE task_snapshots SET updated_at = ?1 WHERE task_id = ?2",
            (future_updated_at, "task-wrapper-service-status-quarantine-b"),
        )

        expired_ms = int(time.time() * 1000) - 1_000

        connection.execute(
            "UPDATE orchestrator_leases SET expires_at_ms = ?1, released_at_ms = NULL WHERE task_id = ?2",
            (expired_ms, "task-wrapper-service-status-quarantine-a"),
        )

        connection.execute(
            "UPDATE orchestrator_leases SET expires_at_ms = ?1, released_at_ms = NULL WHERE task_id = ?2",
            (expired_ms, "task-wrapper-service-status-quarantine-b"),
        )

        connection.commit()

    use_quarantine_result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "use",
            "--db",
            "target/mvp/service-status-quarantine.db",
            "--task-id",
            "task-wrapper-service-status-quarantine-b",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-status-quarantine-use-json",
        "use",
    )

    if use_quarantine_result is not None:
        if (
            use_quarantine_result.get("task_id")
            != "task-wrapper-service-status-quarantine-b"
        ):
            errors.append(
                "mvp-wrapper-service-status-quarantine-use-json missing task-wrapper-service-status-quarantine-b"
            )

        elif (
            use_quarantine_result.get("db") != "target/mvp/service-status-quarantine.db"
        ):
            errors.append(
                "mvp-wrapper-service-status-quarantine-use-json missing quarantine db"
            )


def append_wrapper_service_status_quarantine_text_errors(errors: list[str]) -> None:
    wrapper_service_status_quarantine = subprocess.run(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "service-status",
            "--db",
            "target/mvp/service-status-quarantine.db",
            "--limit",
            "2",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_service_status_quarantine_output = (
        wrapper_service_status_quarantine.stdout or ""
    ) + (wrapper_service_status_quarantine.stderr or "")

    if wrapper_service_status_quarantine.returncode != 0:
        errors.append(
            f"mvp-wrapper-service-status-quarantine failed: exit={wrapper_service_status_quarantine.returncode}"
        )

    elif (
        "[mvp-wrapper] service coordination => status=quarantined reason=peer_executed_assumed_scope_quarantine summary=wait_for_scope_reconcile task=task-wrapper-service-status-quarantine-b"
        not in wrapper_service_status_quarantine_output
    ):
        errors.append(
            "mvp-wrapper-service-status-quarantine missing quarantined coordination summary"
        )

    elif (
        "scope_quarantine=true quarantine_source=peer quarantine_task=task-wrapper-service-status-quarantine-a quarantine_count=1 next_task=task-wrapper-service-status-quarantine-a"
        not in wrapper_service_status_quarantine_output
    ):
        errors.append(
            "mvp-wrapper-service-status-quarantine missing quarantine visibility"
        )

    elif (
        'next=inspect next_reason=scope_quarantined_by_peer blocker=scope_quarantine coordination=quarantined coordination_reason=peer_executed_assumed_scope_quarantine coordination_summary=wait_for_scope_reconcile next_summary=blocked:action=inspect,blocker=scope_quarantine,reason=scope_quarantined_by_peer next_cmd=safeclaw.cmd report --db "target/mvp/service-status-quarantine.db" --task-id "task-wrapper-service-status-quarantine-a" next_task=task-wrapper-service-status-quarantine-a'
        not in wrapper_service_status_quarantine_output
    ):
        errors.append(
            "mvp-wrapper-service-status-quarantine missing quarantine next command"
        )


def append_wrapper_service_status_quarantine_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "service-status",
            "--db",
            "target/mvp/service-status-quarantine.db",
            "--limit",
            "2",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-status-quarantine-json",
        "service-status",
    )

    if result is not None:
        coordination = result.get("coordination") or {}

        recent_tasks = result.get("recent_tasks") or []

        current_session = result.get("current_session") or {}

        if not isinstance(current_session, dict) or (
            current_session.get("task_id") != "task-wrapper-service-status-quarantine-b"
        ):
            errors.append(
                "mvp-wrapper-service-status-quarantine-json missing current_session task-wrapper-service-status-quarantine-b"
            )

        elif coordination.get("status") != "quarantined":
            errors.append(
                "mvp-wrapper-service-status-quarantine-json missing coordination.status=quarantined"
            )

        elif coordination.get("reason") != "peer_executed_assumed_scope_quarantine":
            errors.append(
                "mvp-wrapper-service-status-quarantine-json missing coordination.reason=peer_executed_assumed_scope_quarantine"
            )

        elif coordination.get("summary") != "wait_for_scope_reconcile":
            errors.append(
                "mvp-wrapper-service-status-quarantine-json missing coordination.summary=wait_for_scope_reconcile"
            )

        elif coordination.get("scope_quarantine_active") is not True:
            errors.append(
                "mvp-wrapper-service-status-quarantine-json missing coordination.scope_quarantine_active=true"
            )

        elif coordination.get("scope_quarantine_source") != "peer":
            errors.append(
                "mvp-wrapper-service-status-quarantine-json missing coordination.scope_quarantine_source=peer"
            )

        elif (
            coordination.get("scope_quarantine_task_id")
            != "task-wrapper-service-status-quarantine-a"
        ):
            errors.append(
                "mvp-wrapper-service-status-quarantine-json missing coordination.scope_quarantine_task_id=task-wrapper-service-status-quarantine-a"
            )

        elif coordination.get("scope_quarantine_count") != 1:
            errors.append(
                "mvp-wrapper-service-status-quarantine-json missing coordination.scope_quarantine_count=1"
            )

        elif (
            coordination.get("next_task_id")
            != "task-wrapper-service-status-quarantine-a"
        ):
            errors.append(
                "mvp-wrapper-service-status-quarantine-json missing coordination.next_task_id=task-wrapper-service-status-quarantine-a"
            )

        elif not isinstance(recent_tasks, list) or not recent_tasks:
            errors.append(
                "mvp-wrapper-service-status-quarantine-json missing recent task"
            )

        elif (
            recent_tasks[0].get("task_id") != "task-wrapper-service-status-quarantine-b"
        ):
            errors.append(
                "mvp-wrapper-service-status-quarantine-json missing recent task b"
            )

        elif recent_tasks[0].get("next_action") != "inspect":
            errors.append(
                "mvp-wrapper-service-status-quarantine-json missing next_action=inspect"
            )

        elif recent_tasks[0].get("next_reason") != "scope_quarantined_by_peer":
            errors.append(
                "mvp-wrapper-service-status-quarantine-json missing next_reason=scope_quarantined_by_peer"
            )

        elif recent_tasks[0].get("next_blocker") != "scope_quarantine":
            errors.append(
                "mvp-wrapper-service-status-quarantine-json missing next_blocker=scope_quarantine"
            )

        elif (
            recent_tasks[0].get("next_summary")
            != "blocked:action=inspect,blocker=scope_quarantine,reason=scope_quarantined_by_peer"
        ):
            errors.append(
                "mvp-wrapper-service-status-quarantine-json missing quarantine next_summary"
            )

        elif recent_tasks[0].get("coordination_status") != "quarantined":
            errors.append(
                "mvp-wrapper-service-status-quarantine-json missing coordination_status=quarantined"
            )

        elif (
            recent_tasks[0].get("coordination_reason")
            != "peer_executed_assumed_scope_quarantine"
        ):
            errors.append(
                "mvp-wrapper-service-status-quarantine-json missing coordination_reason=peer_executed_assumed_scope_quarantine"
            )

        elif recent_tasks[0].get("coordination_summary") != "wait_for_scope_reconcile":
            errors.append(
                "mvp-wrapper-service-status-quarantine-json missing coordination_summary=wait_for_scope_reconcile"
            )

        elif recent_tasks[0].get("scope_quarantine_active") is not True:
            errors.append(
                "mvp-wrapper-service-status-quarantine-json missing scope_quarantine_active=true"
            )

        elif recent_tasks[0].get("scope_quarantine_source") != "peer":
            errors.append(
                "mvp-wrapper-service-status-quarantine-json missing scope_quarantine_source=peer"
            )

        elif (
            recent_tasks[0].get("scope_quarantine_task_id")
            != "task-wrapper-service-status-quarantine-a"
        ):
            errors.append(
                "mvp-wrapper-service-status-quarantine-json missing scope_quarantine_task_id=task-wrapper-service-status-quarantine-a"
            )

        elif recent_tasks[0].get("scope_quarantine_count") != 1:
            errors.append(
                "mvp-wrapper-service-status-quarantine-json missing scope_quarantine_count=1"
            )

        elif (
            recent_tasks[0].get("next_task_id")
            != "task-wrapper-service-status-quarantine-a"
        ):
            errors.append(
                "mvp-wrapper-service-status-quarantine-json missing next_task_id=task-wrapper-service-status-quarantine-a"
            )

        elif (
            recent_tasks[0].get("next_command")
            != 'safeclaw.cmd report --db "target/mvp/service-status-quarantine.db" --task-id "task-wrapper-service-status-quarantine-a"'
        ):
            errors.append(
                "mvp-wrapper-service-status-quarantine-json missing next_command=quarantine-source report"
            )


def append_wrapper_service_run_text_errors(errors: list[str]) -> None:
    wrapper_service_run = subprocess.run(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "service-run",
            "--reset",
            "--task-id",
            "task-wrapper-service-run",
            "--db",
            "target/mvp/service-run.db",
            "--output",
            "target/mvp/service-run.txt",
            "--limit",
            "1",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_service_run_output = (wrapper_service_run.stdout or "") + (
        wrapper_service_run.stderr or ""
    )

    if wrapper_service_run.returncode != 0:
        errors.append(
            f"mvp-wrapper-service-run failed: exit={wrapper_service_run.returncode}"
        )

    elif "[mvp-wrapper] service-run => run" not in wrapper_service_run_output:
        errors.append("mvp-wrapper-service-run missing run step marker")

    elif "[mvp-wrapper] service-run => service-status" not in wrapper_service_run_output:
        errors.append("mvp-wrapper-service-run missing service-status step marker")

    elif (
        "[mvp] accepted task => task=task-wrapper-service-run effect=effect-task-wrapper-service-run"
        not in wrapper_service_run_output
    ):
        errors.append("mvp-wrapper-service-run missing run acceptance output")

    elif (
        "[mvp-wrapper] service-status => db=target/mvp/service-run.db limit=1 source=flag"
        not in wrapper_service_run_output
    ):
        errors.append("mvp-wrapper-service-run missing service-status output")

    elif "[mvp-wrapper] service workers => succeeded=1" not in wrapper_service_run_output:
        errors.append("mvp-wrapper-service-run missing worker summary")


def append_wrapper_service_run_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            "cmd",
            "/c",
            "tools\mvp\safeclaw_mvp.cmd",
            "service-run",
            "--reset",
            "--task-id",
            "task-wrapper-service-run-json",
            "--db",
            "target/mvp/service-run-json.db",
            "--output",
            "target/mvp/service-run-json.txt",
            "--limit",
            "1",
            "--json",
        ],
        errors,
        "mvp-wrapper-cmd-service-run-json",
        "service-run",
    )

    assert_service_run_json_result(
        result,
        errors,
        "mvp-wrapper-cmd-service-run-json",
        expected_db="target\mvp\service-run-json.db",
        expected_db_source="flag",
        expected_task_id="task-wrapper-service-run-json",
        expected_limit=1,
    )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\\mvp\\safeclaw_mvp.ps1",
            "service-run",
            "--reset",
            "--task-id",
            "task-wrapper-service-run-json",
            "--db",
            "target/mvp/service-run-json.db",
            "--output",
            "target/mvp/service-run-json.txt",
            "--limit",
            "1",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-service-run-json",
        "service-run",
    )

    assert_service_run_json_result(
        result,
        errors,
        "mvp-wrapper-ps1-service-run-json",
        expected_db="target\\mvp\\service-run-json.db",
        expected_db_source="flag",
        expected_task_id="task-wrapper-service-run-json",
        expected_limit=1,
    )


def append_wrapper_service_run_preflight_text_errors(errors: list[str]) -> None:
    wrapper_service_run_preflight = subprocess.run(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "service-run",
            "--reset",
            "--task-id",
            "task-wrapper-service-run-preflight",
            "--db",
            "target/mvp/service-run-preflight.db",
            "--output",
            "target/mvp/service-run-preflight.txt",
            "--limit",
            "1",
            "--preflight",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_service_run_preflight_output = (
        wrapper_service_run_preflight.stdout or ""
    ) + (wrapper_service_run_preflight.stderr or "")

    if wrapper_service_run_preflight.returncode != 0:
        errors.append(
            f"mvp-wrapper-service-run-preflight failed: exit={wrapper_service_run_preflight.returncode}"
        )

    elif (
        "[mvp-wrapper] service-run => preflight"
        not in wrapper_service_run_preflight_output
    ):
        errors.append("mvp-wrapper-service-run-preflight missing preflight step marker")

    elif (
        "[mvp-wrapper] preflight => action=service-run known=true class=local-action tier=TIER_1 writes_state=true target_scope=scope:target/mvp/service-run-preflight.txt requires_write=true doctor_bypass=false perm_ctx=true perm_ctx_src=prepared-action enforce_perm=false perm=confirm perm_tier=TIER_1 perm_reason=write_scope_requires_confirmation decision=allow allowed=true offline_ready=true requires_model=false requires_sidecar=false degradation=local_only_ok reason=current_mvp_action_is_local_only"
        not in wrapper_service_run_preflight_output
    ):
        errors.append("mvp-wrapper-service-run-preflight missing preflight summary")

    elif "[mvp-wrapper] service-run => run" not in wrapper_service_run_preflight_output:
        errors.append("mvp-wrapper-service-run-preflight missing run step marker")

    elif (
        "[mvp-wrapper] service-run => service-status"
        not in wrapper_service_run_preflight_output
    ):
        errors.append(
            "mvp-wrapper-service-run-preflight missing service-status step marker"
        )


def append_wrapper_service_run_preflight_ai_reason_text_errors(errors: list[str]) -> None:
    wrapper_service_run_preflight_ai_reason = subprocess.run(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "service-run",
            "--reset",
            "--task-id",
            "task-wrapper-service-run-preflight-ai",
            "--db",
            "target/mvp/service-run-preflight-ai.db",
            "--output",
            "target/mvp/service-run-preflight-ai.txt",
            "--limit",
            "1",
            "--preflight",
            "--preflight-action",
            "ai-reason",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_service_run_preflight_ai_reason_output = (
        wrapper_service_run_preflight_ai_reason.stdout or ""
    ) + (wrapper_service_run_preflight_ai_reason.stderr or "")

    if wrapper_service_run_preflight_ai_reason.returncode != 1:
        errors.append(
            f"mvp-wrapper-service-run-preflight-ai-reason failed: exit={wrapper_service_run_preflight_ai_reason.returncode}"
        )

    elif (
        "[mvp-wrapper] service-run => preflight"
        not in wrapper_service_run_preflight_ai_reason_output
    ):
        errors.append(
            "mvp-wrapper-service-run-preflight-ai-reason missing preflight step marker"
        )

    elif (
        "[mvp-wrapper] preflight => action=ai-reason known=true class=ai-action tier=TIER_2 writes_state=false target_scope=scope:target/mvp/service-run-preflight-ai.txt requires_write=true doctor_bypass=false perm_ctx=true perm_ctx_src=prepared-action enforce_perm=false perm=confirm perm_tier=TIER_1 perm_reason=write_scope_requires_confirmation decision=deny allowed=false offline_ready=false requires_model=true requires_sidecar=true degradation=provider_unavailable reason=ERR_AI_PROVIDER_UNAVAILABLE error_code=ERR_AI_PROVIDER_UNAVAILABLE"
        not in wrapper_service_run_preflight_ai_reason_output
    ):
        errors.append(
            "mvp-wrapper-service-run-preflight-ai-reason missing provider-unavailable preflight summary"
        )

    elif (
        "[mvp-wrapper] service-run => failed step=preflight exit=1"
        not in wrapper_service_run_preflight_ai_reason_output
    ):
        errors.append(
            "mvp-wrapper-service-run-preflight-ai-reason missing failed preflight marker"
        )


def append_wrapper_service_run_preflight_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "service-run",
            "--reset",
            "--task-id",
            "task-wrapper-service-run-preflight-json",
            "--db",
            "target/mvp/service-run-preflight-json.db",
            "--output",
            "target/mvp/service-run-preflight-json.txt",
            "--limit",
            "1",
            "--preflight",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-run-preflight-json",
        "service-run",
    )

    assert_service_run_json_result(
        result,
        errors,
        "mvp-wrapper-service-run-preflight-json",
        expected_db="target\mvp\service-run-preflight-json.db",
        expected_db_source="flag",
        expected_task_id="task-wrapper-service-run-preflight-json",
        expected_limit=1,
        expected_steps=["preflight", "run", "service-status"],
        expected_preflight_context_source="prepared-action",
    )

    assert_preflight_json_result(
        None if result is None else result.get("preflight"),
        errors,
        "mvp-wrapper-service-run-preflight-json preflight",
        expected_requested_action="service-run",
        expected_known=True,
        expected_action_class="local-action",
        expected_tier="TIER_1",
        expected_writes_state=True,
        expected_permission_context_source="prepared-action",
        expected_target_scope="scope:target/mvp/service-run-preflight-json.txt",
        expected_requires_write=True,
        expected_doctor_bypass=False,
        expected_permission_context_applied=True,
        expected_permission_tier="TIER_1",
        expected_permission_policy="confirm",
        expected_permission_reason="write_scope_requires_confirmation",
        expected_permission_enforced=False,
        expected_action_allowed=True,
        expected_action_decision="allow",
        expected_action_reason="current_mvp_action_is_local_only",
        expected_allowed=True,
        expected_decision="allow",
        expected_offline_ready=True,
        expected_degradation_mode="local_only_ok",
        expected_reason="current_mvp_action_is_local_only",
    )


def append_wrapper_service_run_preflight_ai_reason_json_errors(errors: list[str]) -> None:
    details = assert_command_json_error(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "service-run",
            "--reset",
            "--task-id",
            "task-wrapper-service-run-preflight-ai-json",
            "--db",
            "target/mvp/service-run-preflight-ai-json.db",
            "--output",
            "target/mvp/service-run-preflight-ai-json.txt",
            "--limit",
            "1",
            "--preflight",
            "--preflight-action",
            "ai-reason",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-run-preflight-ai-json",
        "service-run",
        expected_exit=1,
        expected_error_message_substring="failed step=preflight",
        expected_top_level_error_code="preflight-blocked",
        expected_top_level_error_reason="ERR_AI_PROVIDER_UNAVAILABLE",
        expected_top_level_error_error_code="ERR_AI_PROVIDER_UNAVAILABLE",
        expected_top_level_error_degradation_mode="provider_unavailable",
        expected_top_level_error_requires_model=True,
        expected_top_level_error_requires_sidecar=True,
        expected_top_level_error_requested_action="ai-reason",
        expected_code="preflight-blocked",
        expected_failed_step="preflight",
        expected_preflight_requested_action="ai-reason",
        expected_preflight_reason="ERR_AI_PROVIDER_UNAVAILABLE",
        expected_preflight_error_code="ERR_AI_PROVIDER_UNAVAILABLE",
        expected_preflight_summary_substring="action=ai-reason",
        expect_top_level_error_summary_matches_preflight=True,
    )

    if isinstance(details, dict):
        preflight_payload = details.get("preflight")

        if not isinstance(preflight_payload, dict):
            errors.append(
                "mvp-wrapper-service-run-preflight-ai-json missing preflight payload"
            )

        else:
            assert_preflight_json_result(
                preflight_payload,
                errors,
                "mvp-wrapper-service-run-preflight-ai-json preflight",
                expected_requested_action="ai-reason",
                expected_known=True,
                expected_action_class="ai-action",
                expected_tier="TIER_2",
                expected_writes_state=False,
                expected_permission_context_source="prepared-action",
                expected_target_scope="scope:target/mvp/service-run-preflight-ai-json.txt",
                expected_requires_write=True,
                expected_doctor_bypass=False,
                expected_permission_context_applied=True,
                expected_permission_tier="TIER_1",
                expected_permission_policy="confirm",
                expected_permission_reason="write_scope_requires_confirmation",
                expected_permission_enforced=False,
                expected_action_allowed=False,
                expected_action_decision="deny",
                expected_action_reason="ERR_AI_PROVIDER_UNAVAILABLE",
                expected_allowed=False,
                expected_decision="deny",
                expected_offline_ready=False,
                expected_degradation_mode="provider_unavailable",
                expected_reason="ERR_AI_PROVIDER_UNAVAILABLE",
                expected_requires_model=True,
                expected_requires_sidecar=True,
                expected_error_code="ERR_AI_PROVIDER_UNAVAILABLE",
            )

        steps = details.get("steps") or []

        if (
            not isinstance(steps, list)
            or len(steps) != 1
            or not isinstance(steps[0], dict)
        ):
            errors.append(
                "mvp-wrapper-service-run-preflight-ai-json missing isolated preflight step"
            )

        elif steps[0].get("action") != "preflight":
            errors.append(
                "mvp-wrapper-service-run-preflight-ai-json missing preflight step action"
            )


def append_wrapper_service_run_enforced_json_errors(errors: list[str]) -> None:
    details = assert_command_json_error(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "service-run",
            "--reset",
            "--task-id",
            "task-wrapper-service-run-enforced",
            "--db",
            "target/mvp/service-run-enforced.db",
            "--output",
            "target/mvp/service-run-enforced.txt",
            "--limit",
            "1",
            "--enforce-permission",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-run-enforced-json",
        "service-run",
        expected_exit=1,
        expected_error_message_substring="failed step=preflight",
        expected_top_level_error_code="preflight-blocked",
        expected_top_level_error_reason="write_scope_requires_confirmation",
        expect_top_level_error_error_code_absent=True,
        expected_top_level_error_degradation_mode="local_only_ok",
        expected_top_level_error_requires_model=False,
        expected_top_level_error_requires_sidecar=False,
        expected_top_level_error_requested_action="service-run",
        expected_code="preflight-blocked",
        expected_failed_step="preflight",
        expected_preflight_requested_action="service-run",
        expected_preflight_reason="write_scope_requires_confirmation",
        expect_preflight_error_code_absent=True,
        expected_preflight_summary_substring="action=service-run",
        expect_top_level_error_summary_matches_preflight=True,
    )

    if isinstance(details, dict):
        preflight_payload = details.get("preflight")

        if not isinstance(preflight_payload, dict):
            errors.append(
                "mvp-wrapper-service-run-enforced-json missing preflight payload"
            )

        else:
            assert_preflight_json_result(
                preflight_payload,
                errors,
                "mvp-wrapper-service-run-enforced-json preflight",
                expected_requested_action="service-run",
                expected_known=True,
                expected_action_class="local-action",
                expected_tier="TIER_1",
                expected_writes_state=True,
                expected_permission_context_source="prepared-action",
                expected_target_scope="scope:target/mvp/service-run-enforced.txt",
                expected_requires_write=True,
                expected_doctor_bypass=False,
                expected_permission_context_applied=True,
                expected_permission_tier="TIER_1",
                expected_permission_policy="confirm",
                expected_permission_reason="write_scope_requires_confirmation",
                expected_permission_enforced=True,
                expected_action_allowed=True,
                expected_action_decision="allow",
                expected_action_reason="current_mvp_action_is_local_only",
                expected_allowed=False,
                expected_decision="confirm",
                expected_offline_ready=True,
                expected_degradation_mode="local_only_ok",
                expected_reason="write_scope_requires_confirmation",
            )

        steps = details.get("steps") or []

        if (
            not isinstance(steps, list)
            or len(steps) != 1
            or not isinstance(steps[0], dict)
        ):
            errors.append(
                "mvp-wrapper-service-run-enforced-json missing isolated preflight step"
            )

        elif steps[0].get("action") != "preflight":
            errors.append(
                "mvp-wrapper-service-run-enforced-json missing preflight step action"
            )


def append_wrapper_cmd_service_run_invalid_limit_json_errors(errors: list[str]) -> None:
    assert_command_json_error(
        [
            "cmd",
            "/c",
            "tools\mvp\safeclaw_mvp.cmd",
            "service-run",
            "--limit",
            "bad",
            "--json",
        ],
        errors,
        "mvp-wrapper-cmd-service-run-invalid-limit-json",
        "service-run",
        expected_error_message_substring="invalid --limit",
        error_message_label="mvp-wrapper-cmd-service-run-invalid-limit-json missing invalid --limit",
    )


def append_wrapper_ps1_service_run_invalid_limit_json_errors(errors: list[str]) -> None:
    assert_command_json_error(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "service-run",
            "--limit",
            "bad",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-service-run-invalid-limit-json",
        "service-run",
        expected_error_message_substring="invalid --limit",
        error_message_label="mvp-wrapper-ps1-service-run-invalid-limit-json missing invalid --limit",
    )


def append_wrapper_cmd_service_retry_invalid_limit_json_errors(errors: list[str]) -> None:
    assert_command_json_error(
        [
            "cmd",
            "/c",
            "tools\\mvp\\safeclaw_mvp.cmd",
            "service-retry",
            "--limit",
            "bad",
            "--json",
        ],
        errors,
        "mvp-wrapper-cmd-service-retry-invalid-limit-json",
        "service-retry",
        expected_error_message_substring="invalid --limit",
        error_message_label="mvp-wrapper-cmd-service-retry-invalid-limit-json missing invalid --limit",
    )


def append_wrapper_ps1_service_retry_invalid_limit_json_errors(errors: list[str]) -> None:
    assert_command_json_error(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\\mvp\\safeclaw_mvp.ps1",
            "service-retry",
            "--limit",
            "bad",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-service-retry-invalid-limit-json",
        "service-retry",
        expected_error_message_substring="invalid --limit",
        error_message_label="mvp-wrapper-ps1-service-retry-invalid-limit-json missing invalid --limit",
    )


def append_wrapper_cmd_service_recover_invalid_limit_json_errors(errors: list[str]) -> None:
    assert_command_json_error(
        [
            "cmd",
            "/c",
            "tools\\mvp\\safeclaw_mvp.cmd",
            "service-recover",
            "--limit",
            "bad",
            "--json",
        ],
        errors,
        "mvp-wrapper-cmd-service-recover-invalid-limit-json",
        "service-recover",
        expected_error_message_substring="invalid --limit",
        error_message_label="mvp-wrapper-cmd-service-recover-invalid-limit-json missing invalid --limit",
    )


def append_wrapper_ps1_service_recover_invalid_limit_json_errors(errors: list[str]) -> None:
    assert_command_json_error(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\\mvp\\safeclaw_mvp.ps1",
            "service-recover",
            "--limit",
            "bad",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-service-recover-invalid-limit-json",
        "service-recover",
        expected_error_message_substring="invalid --limit",
        error_message_label="mvp-wrapper-ps1-service-recover-invalid-limit-json missing invalid --limit",
    )


def append_wrapper_cmd_service_status_invalid_limit_json_errors(errors: list[str]) -> None:
    assert_command_json_error(
        [
            "cmd",
            "/c",
            "tools\\mvp\\safeclaw_mvp.cmd",
            "service-status",
            "--limit",
            "bad",
            "--json",
        ],
        errors,
        "mvp-wrapper-cmd-service-status-invalid-limit-json",
        "service-status",
        expected_error_message_substring="invalid --limit",
        error_message_label="mvp-wrapper-cmd-service-status-invalid-limit-json missing invalid --limit",
    )


def append_wrapper_ps1_service_status_invalid_limit_json_errors(errors: list[str]) -> None:
    assert_command_json_error(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\\mvp\\safeclaw_mvp.ps1",
            "service-status",
            "--limit",
            "bad",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-service-status-invalid-limit-json",
        "service-status",
        expected_error_message_substring="invalid --limit",
        error_message_label="mvp-wrapper-ps1-service-status-invalid-limit-json missing invalid --limit",
    )


def append_wrapper_service_run_invalid_limit_json_errors(errors: list[str]) -> None:
    assert_command_json_error(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "service-run",
            "--limit",
            "bogus",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-run-invalid-limit-json",
        "service-run",
        expected_error_message_substring="invalid --limit: bogus",
    )


def append_wrapper_service_retry_seed_failed_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-failed",
            "--reset",
            "--task-id",
            "task-wrapper-service-retry",
            "--db",
            "target/mvp/service-retry.db",
            "--output",
            "target/mvp/service-retry.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-retry-seed-failed-json",
        "seed-failed",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-service-retry-seed-failed-json",
        expected_task_id="task-wrapper-service-retry",
        expected_db_path="target/mvp/service-retry.db",
        expected_output_path="target/mvp/service-retry.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )


def append_wrapper_service_retry_status_before_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "service-status",
            "--db",
            "target/mvp/service-retry.db",
            "--limit",
            "1",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-retry-status-before-json",
        "service-status",
    )

    if result is not None:
        queue = result.get("queue") or {}

        workers = result.get("workers") or {}

        effects = result.get("effects") or {}

        probes = result.get("probes") or {}

        recent_tasks = result.get("recent_tasks") or []

        if queue.get("expired") != 1:
            errors.append(
                "mvp-wrapper-service-retry-status-before-json missing queue.expired=1"
            )

        elif queue.get("completed") != 0:
            errors.append(
                "mvp-wrapper-service-retry-status-before-json missing queue.completed=0"
            )

        elif workers.get("failed") != 1:
            errors.append(
                "mvp-wrapper-service-retry-status-before-json missing workers.failed=1"
            )

        elif effects.get("prepared") != 1:
            errors.append(
                "mvp-wrapper-service-retry-status-before-json missing effects.prepared=1"
            )

        elif probes.get("none") != 1:
            errors.append(
                "mvp-wrapper-service-retry-status-before-json missing probes.none=1"
            )

        elif not isinstance(recent_tasks, list) or not recent_tasks:
            errors.append(
                "mvp-wrapper-service-retry-status-before-json missing recent task"
            )

        elif recent_tasks[0].get("permission_tier") != "TIER_1":
            errors.append(
                "mvp-wrapper-service-retry-status-before-json missing permission_tier=TIER_1"
            )

        elif recent_tasks[0].get("permission_policy") != "confirm":
            errors.append(
                "mvp-wrapper-service-retry-status-before-json missing permission_policy=confirm"
            )

        elif (
            recent_tasks[0].get("permission_reason")
            != "write_scope_requires_confirmation"
        ):
            errors.append(
                "mvp-wrapper-service-retry-status-before-json missing permission_reason=write_scope_requires_confirmation"
            )

        elif recent_tasks[0].get("next_action") != "retry":
            errors.append(
                "mvp-wrapper-service-retry-status-before-json missing next_action=retry"
            )

        elif (
            recent_tasks[0].get("next_command")
            != 'safeclaw.cmd service-retry --db "target/mvp/service-retry.db" --task-id "task-wrapper-service-retry" --limit 1 --report'
        ):
            errors.append(
                "mvp-wrapper-service-retry-status-before-json missing next_command=service-retry"
            )

        elif recent_tasks[0].get("next_reason") != "failed_state_ready_for_retry":
            errors.append(
                "mvp-wrapper-service-retry-status-before-json missing next_reason=failed_state_ready_for_retry"
            )

        elif recent_tasks[0].get("next_blocker") != "none":
            errors.append(
                "mvp-wrapper-service-retry-status-before-json missing next_blocker=none"
            )

        elif (
            recent_tasks[0].get("next_summary")
            != "ready_now:action=retry,reason=failed_state_ready_for_retry"
        ):
            errors.append(
                "mvp-wrapper-service-retry-status-before-json missing next_summary=retry"
            )

        elif recent_tasks[0].get("coordination_status") != "ready":
            errors.append(
                "mvp-wrapper-service-retry-status-before-json missing coordination_status=ready"
            )

        elif (
            recent_tasks[0].get("coordination_reason") != "failed_state_ready_for_retry"
        ):
            errors.append(
                "mvp-wrapper-service-retry-status-before-json missing coordination_reason=failed_state_ready_for_retry"
            )

        elif recent_tasks[0].get("coordination_summary") != "retry_now":
            errors.append(
                "mvp-wrapper-service-retry-status-before-json missing coordination_summary=retry_now"
            )

        elif (result.get("coordination") or {}).get("status") != "ready":
            errors.append(
                "mvp-wrapper-service-retry-status-before-json missing coordination.status=ready"
            )


def append_wrapper_service_retry_text_errors(errors: list[str]) -> None:
    wrapper_service_retry = subprocess.run(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "service-retry",
            "--db",
            "target/mvp/service-retry.db",
            "--task-id",
            "task-wrapper-service-retry",
            "--limit",
            "1",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_service_retry_output = (wrapper_service_retry.stdout or "") + (
        wrapper_service_retry.stderr or ""
    )

    if wrapper_service_retry.returncode != 0:
        errors.append(
            f"mvp-wrapper-service-retry failed: exit={wrapper_service_retry.returncode}"
        )

    elif "[mvp-wrapper] service-retry => retry" not in wrapper_service_retry_output:
        errors.append("mvp-wrapper-service-retry missing retry step marker")

    elif (
        "[mvp-wrapper] service-retry => service-status"
        not in wrapper_service_retry_output
    ):
        errors.append("mvp-wrapper-service-retry missing service-status step marker")

    elif (
        "[mvp] retry result => worker=Succeeded, effect=Executed, completed=true"
        not in wrapper_service_retry_output
    ):
        errors.append("mvp-wrapper-service-retry missing retry success output")

    elif (
        "[mvp-wrapper] service-status => db=target/mvp/service-retry.db limit=1 source=flag"
        not in wrapper_service_retry_output
    ):
        errors.append("mvp-wrapper-service-retry missing service-status output")

    elif "[mvp-wrapper] service workers => succeeded=1" not in wrapper_service_retry_output:
        errors.append("mvp-wrapper-service-retry missing worker summary")


def append_wrapper_service_retry_json_seed_failed_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-failed",
            "--reset",
            "--task-id",
            "task-wrapper-service-retry-json",
            "--db",
            "target/mvp/service-retry-json.db",
            "--output",
            "target/mvp/service-retry-json.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-retry-json-seed-failed-json",
        "seed-failed",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-service-retry-json-seed-failed-json",
        expected_task_id="task-wrapper-service-retry-json",
        expected_db_path="target/mvp/service-retry-json.db",
        expected_output_path="target/mvp/service-retry-json.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )


def append_wrapper_cmd_service_retry_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            "cmd",
            "/c",
            "tools\mvp\safeclaw_mvp.cmd",
            "service-retry",
            "--db",
            "target/mvp/service-retry-json.db",
            "--task-id",
            "task-wrapper-service-retry-json",
            "--limit",
            "1",
            "--json",
        ],
        errors,
        "mvp-wrapper-cmd-service-retry-json",
        "service-retry",
    )

    assert_service_retry_json_result(
        result,
        errors,
        "mvp-wrapper-cmd-service-retry-json",
        expected_db="target\mvp\service-retry-json.db",
        expected_db_source="flag",
        expected_task_id="task-wrapper-service-retry-json",
        expected_limit=1,
    )


def append_wrapper_service_retry_json_seed_failed_ps1_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-failed",
            "--reset",
            "--task-id",
            "task-wrapper-service-retry-json",
            "--db",
            "target/mvp/service-retry-json.db",
            "--output",
            "target/mvp/service-retry-json.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-retry-json-seed-failed-ps1-json",
        "seed-failed",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-service-retry-json-seed-failed-ps1-json",
        expected_task_id="task-wrapper-service-retry-json",
        expected_db_path="target/mvp/service-retry-json.db",
        expected_output_path="target/mvp/service-retry-json.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )


def append_wrapper_ps1_service_retry_json_errors(errors: list[str]) -> None:
    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "service-retry",
            "--db",
            "target/mvp/service-retry-json.db",
            "--task-id",
            "task-wrapper-service-retry-json",
            "--limit",
            "1",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-service-retry-json",
        "service-retry",
    )

    assert_service_retry_json_result(
        result,
        errors,
        "mvp-wrapper-ps1-service-retry-json",
        expected_db="target\mvp\service-retry-json.db",
        expected_db_source="flag",
        expected_task_id="task-wrapper-service-retry-json",
        expected_limit=1,
    )


def append_wrapper_service_retry_invalid_limit_json_errors(errors: list[str]) -> None:
    assert_command_json_error(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "service-retry",
            "--limit",
            "bogus",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-retry-invalid-limit-json",
        "service-retry",
        expected_error_message_substring="invalid --limit: bogus",
    )


def append_wrapper_service_retry_missing_task_json_errors(errors: list[str]) -> None:
    assert_command_json_error(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "service-retry",
            "--db",
            "target/mvp/service-retry-missing.db",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-retry-missing-task-json",
        "service-retry",
        expected_error_message_substring="failed step=retry",
        expected_failed_step="retry",
        expected_code="missing-task-context",
        expected_details_message_substring="missing task context",
        expected_remembered_session_task_id="task-wrapper-service-retry-json",
        remembered_session_label="mvp-wrapper-service-retry-missing-task-json missing task-wrapper-service-retry-json",
        reject_legacy_session=True,
        legacy_session_label="mvp-wrapper-service-retry-missing-task-json should not keep legacy session",
    )


def collect_errors() -> list[str]:
    errors: list[str] = []
    reset_smoke_progress()
    append_smoke_setup_errors(errors)
    append_wrapper_help_errors(errors)

    append_entrypoint_help_errors(errors)

    append_root_default_entry_errors(errors)

    append_root_workspace_entry_errors(errors)
    append_root_service_run_errors(errors)
    append_root_service_retry_errors(errors)
    append_root_service_recover_errors(errors)
    append_root_service_resume_errors(errors)
    append_root_service_reconcile_errors(errors)
    append_root_verify_errors(errors)
    append_root_workspace_clear_errors(errors)
    append_root_ps1_seed_crash_failed_errors(errors)
    append_root_ps1_seed_hibernated_errors(errors)
    append_root_ps1_resume_errors(errors)
    append_root_cmd_seed_hibernated_errors(errors)
    append_root_cmd_resume_errors(errors)
    append_root_forget_errors(errors)
    append_root_cmd_preflight_local_action_errors(errors)
    append_root_cmd_preflight_ai_reason_errors(errors)
    append_root_ps1_preflight_ai_reason_errors(errors)
    append_root_ps1_preflight_local_action_errors(errors)
    append_wrapper_doctor_shell_json_errors(errors)
    append_wrapper_doctor_text_errors(errors)
    append_wrapper_doctor_json_errors(errors)
    append_wrapper_preflight_text_errors(errors)
    append_wrapper_preflight_allow_json_errors(errors)
    append_wrapper_preflight_unknown_text_errors(errors)
    append_wrapper_preflight_unknown_json_errors(errors)
    append_wrapper_preflight_ai_reason_text_errors(errors)
    append_wrapper_preflight_ai_reason_json_errors(errors)
    append_wrapper_preflight_status_text_errors(errors)
    append_wrapper_preflight_status_json_errors(errors)
    append_wrapper_preflight_scope_text_errors(errors)
    append_wrapper_preflight_scope_json_errors(errors)
    append_wrapper_preflight_scope_enforced_text_errors(errors)
    append_wrapper_preflight_scope_enforced_json_errors(errors)
    append_wrapper_preflight_enforce_without_context_json_errors(errors)
    append_wrapper_preflight_bypass_json_errors(errors)
    append_wrapper_doctor_no_cargo_path_json_errors(errors)
    append_wrapper_workspace_default_json_errors(errors)
    append_wrapper_workspace_activate_json_errors(errors)
    append_wrapper_cmd_workspace_activate_json_errors(errors)
    append_wrapper_workspace_doctor_json_errors(errors)
    append_wrapper_workspace_run_json_errors(errors)
    append_wrapper_workspace_clear_after_json_errors(errors)
    append_wrapper_cmd_workspace_clear_json_errors(errors)
    append_wrapper_forget_after_workspace_json_errors(errors)
    append_wrapper_service_status_seed_run_json_errors(errors)
    append_wrapper_service_status_text_errors(errors)
    append_wrapper_cmd_service_status_json_errors(errors)
    append_wrapper_ps1_service_status_json_errors(errors)
    append_wrapper_service_status_invalid_limit_json_errors(errors)
    append_wrapper_service_status_hibernated_seed_failed_json_errors(errors)
    append_wrapper_service_status_hibernated_state_setup_errors(errors)
    append_wrapper_service_status_hibernated_text_errors(errors)
    append_wrapper_service_status_hibernated_json_errors(errors)
    append_wrapper_service_resume_json_seed_hibernated_json_errors(errors)
    append_wrapper_cmd_service_resume_json_errors(errors)
    append_wrapper_resume_json_seed_hibernated_json_errors(errors)
    append_wrapper_resume_json_errors(errors)
    append_wrapper_cmd_resume_json_seed_hibernated_json_errors(errors)
    append_wrapper_cmd_resume_json_errors(errors)
    append_wrapper_cmd_seed_hibernated_json_errors(errors)
    append_wrapper_service_resume_not_hibernated_seed_failed_json_errors(errors)
    append_wrapper_cmd_service_resume_not_hibernated_errors(errors)
    append_wrapper_service_resume_not_hibernated_json_seed_failed_json_errors(errors)
    append_wrapper_service_resume_json_seed_hibernated_ps1_json_errors(errors)
    append_wrapper_ps1_service_resume_json_errors(errors)
    append_wrapper_service_resume_report_json_seed_hibernated_ps1_json_errors(errors)
    append_wrapper_ps1_service_resume_report_json_errors(errors)
    append_wrapper_cmd_service_resume_not_hibernated_json_errors(errors)
    append_wrapper_service_resume_missing_run_json_errors(errors)
    append_wrapper_service_resume_missing_json_errors(errors)
    append_wrapper_service_status_active_seed_failed_json_errors(errors)
    append_wrapper_service_status_active_state_setup_errors(errors)
    append_wrapper_service_status_active_text_errors(errors)
    append_wrapper_service_status_active_json_errors(errors)
    append_wrapper_service_status_scope_a_seed_failed_json_errors(errors)
    append_wrapper_service_status_scope_b_seed_failed_json_errors(errors)
    append_wrapper_service_status_scope_use_json_errors(errors)
    append_wrapper_service_status_scope_text_errors(errors)
    append_wrapper_service_status_scope_json_errors(errors)
    append_wrapper_service_status_quarantine_a_seed_failed_json_errors(errors)
    append_wrapper_service_status_quarantine_b_seed_failed_json_errors(errors)
    append_wrapper_service_status_quarantine_use_json_errors(errors)
    append_wrapper_service_status_quarantine_text_errors(errors)
    append_wrapper_service_status_quarantine_json_errors(errors)
    append_wrapper_service_run_text_errors(errors)
    append_wrapper_service_run_json_errors(errors)
    append_wrapper_service_run_preflight_text_errors(errors)
    append_wrapper_service_run_preflight_ai_reason_text_errors(errors)
    append_wrapper_service_run_preflight_json_errors(errors)
    append_wrapper_service_run_preflight_ai_reason_json_errors(errors)
    append_wrapper_service_run_enforced_json_errors(errors)
    append_wrapper_cmd_service_run_invalid_limit_json_errors(errors)
    append_wrapper_ps1_service_run_invalid_limit_json_errors(errors)
    append_wrapper_cmd_service_retry_invalid_limit_json_errors(errors)
    append_wrapper_ps1_service_retry_invalid_limit_json_errors(errors)
    append_wrapper_cmd_service_recover_invalid_limit_json_errors(errors)
    append_wrapper_ps1_service_recover_invalid_limit_json_errors(errors)
    append_wrapper_cmd_service_status_invalid_limit_json_errors(errors)
    append_wrapper_ps1_service_status_invalid_limit_json_errors(errors)
    append_wrapper_service_run_invalid_limit_json_errors(errors)
    append_wrapper_service_retry_seed_failed_json_errors(errors)
    append_wrapper_service_retry_status_before_json_errors(errors)
    append_wrapper_service_retry_text_errors(errors)
    append_wrapper_service_retry_json_seed_failed_json_errors(errors)
    append_wrapper_cmd_service_retry_json_errors(errors)
    append_wrapper_service_retry_json_seed_failed_ps1_json_errors(errors)
    append_wrapper_ps1_service_retry_json_errors(errors)
    append_wrapper_service_retry_invalid_limit_json_errors(errors)
    append_wrapper_service_retry_missing_task_json_errors(errors)

    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-crash",
            "--reset",
            "--task-id",
            "task-wrapper-service-recover",
            "--db",
            "target/mvp/service-recover.db",
            "--output",
            "target/mvp/service-recover.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-recover-seed-crash-json",
        "seed-crash",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-service-recover-seed-crash-json",
        expected_task_id="task-wrapper-service-recover",
        expected_db_path="target/mvp/service-recover.db",
        expected_output_path="target/mvp/service-recover.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )

    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "service-status",
            "--db",
            "target/mvp/service-recover.db",
            "--limit",
            "1",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-recover-status-before-json",
        "service-status",
    )

    if result is not None:
        queue = result.get("queue") or {}

        workers = result.get("workers") or {}

        effects = result.get("effects") or {}

        probes = result.get("probes") or {}

        recent_tasks = result.get("recent_tasks") or []

        if queue.get("expired") != 1:
            errors.append(
                "mvp-wrapper-service-recover-status-before-json missing queue.expired=1"
            )

        elif queue.get("completed") != 0:
            errors.append(
                "mvp-wrapper-service-recover-status-before-json missing queue.completed=0"
            )

        elif workers.get("uncertain") != 1:
            errors.append(
                "mvp-wrapper-service-recover-status-before-json missing workers.uncertain=1"
            )

        elif effects.get("uncertain") != 1:
            errors.append(
                "mvp-wrapper-service-recover-status-before-json missing effects.uncertain=1"
            )

        elif probes.get("probe_pending") != 1:
            errors.append(
                "mvp-wrapper-service-recover-status-before-json missing probes.probe_pending=1"
            )

        elif not isinstance(recent_tasks, list) or not recent_tasks:
            errors.append(
                "mvp-wrapper-service-recover-status-before-json missing recent task"
            )

        elif recent_tasks[0].get("permission_tier") != "TIER_1":
            errors.append(
                "mvp-wrapper-service-recover-status-before-json missing permission_tier=TIER_1"
            )

        elif recent_tasks[0].get("permission_policy") != "confirm":
            errors.append(
                "mvp-wrapper-service-recover-status-before-json missing permission_policy=confirm"
            )

        elif (
            recent_tasks[0].get("permission_reason")
            != "write_scope_requires_confirmation"
        ):
            errors.append(
                "mvp-wrapper-service-recover-status-before-json missing permission_reason=write_scope_requires_confirmation"
            )

        elif recent_tasks[0].get("next_action") != "recover":
            errors.append(
                "mvp-wrapper-service-recover-status-before-json missing next_action=recover"
            )

        elif (
            recent_tasks[0].get("next_command")
            != 'safeclaw.cmd service-recover --db "target/mvp/service-recover.db" --task-id "task-wrapper-service-recover" --limit 1 --report'
        ):
            errors.append(
                "mvp-wrapper-service-recover-status-before-json missing next_command=service-recover"
            )

        elif recent_tasks[0].get("next_reason") != "uncertain_state_ready_for_recover":
            errors.append(
                "mvp-wrapper-service-recover-status-before-json missing next_reason=uncertain_state_ready_for_recover"
            )

        elif recent_tasks[0].get("next_blocker") != "none":
            errors.append(
                "mvp-wrapper-service-recover-status-before-json missing next_blocker=none"
            )

        elif (
            recent_tasks[0].get("next_summary")
            != "ready_now:action=recover,reason=uncertain_state_ready_for_recover"
        ):
            errors.append(
                "mvp-wrapper-service-recover-status-before-json missing next_summary=recover"
            )

        elif recent_tasks[0].get("coordination_status") != "ready":
            errors.append(
                "mvp-wrapper-service-recover-status-before-json missing coordination_status=ready"
            )

        elif (
            recent_tasks[0].get("coordination_reason")
            != "uncertain_state_ready_for_recover"
        ):
            errors.append(
                "mvp-wrapper-service-recover-status-before-json missing coordination_reason=uncertain_state_ready_for_recover"
            )

        elif recent_tasks[0].get("coordination_summary") != "recover_now":
            errors.append(
                "mvp-wrapper-service-recover-status-before-json missing coordination_summary=recover_now"
            )

        elif (result.get("coordination") or {}).get("status") != "ready":
            errors.append(
                "mvp-wrapper-service-recover-status-before-json missing coordination.status=ready"
            )

    wrapper_service_recover = subprocess.run(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "service-recover",
            "--db",
            "target/mvp/service-recover.db",
            "--task-id",
            "task-wrapper-service-recover",
            "--limit",
            "1",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_service_recover_output = (wrapper_service_recover.stdout or "") + (
        wrapper_service_recover.stderr or ""
    )

    if wrapper_service_recover.returncode != 0:
        errors.append(
            f"mvp-wrapper-service-recover failed: exit={wrapper_service_recover.returncode}"
        )

    elif (
        "[mvp-wrapper] service-recover => recover" not in wrapper_service_recover_output
    ):
        errors.append("mvp-wrapper-service-recover missing recover step marker")

    elif (
        "[mvp-wrapper] service-recover => service-status"
        not in wrapper_service_recover_output
    ):
        errors.append("mvp-wrapper-service-recover missing service-status step marker")

    elif (
        "[mvp] recover result => from=Uncertain, worker=Succeeded, effect=Executed, completed=true"
        not in wrapper_service_recover_output
    ):
        errors.append("mvp-wrapper-service-recover missing recover success output")

    elif (
        "[mvp-wrapper] service-status => db=target/mvp/service-recover.db limit=1 source=flag"
        not in wrapper_service_recover_output
    ):
        errors.append("mvp-wrapper-service-recover missing service-status output")

    elif (
        "[mvp-wrapper] service workers => succeeded=1"
        not in wrapper_service_recover_output
    ):
        errors.append("mvp-wrapper-service-recover missing worker summary")

    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-crash",
            "--reset",
            "--task-id",
            "task-wrapper-service-recover-json",
            "--db",
            "target/mvp/service-recover-json.db",
            "--output",
            "target/mvp/service-recover-json.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-recover-json-seed-crash-json",
        "seed-crash",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-service-recover-json-seed-crash-json",
        expected_task_id="task-wrapper-service-recover-json",
        expected_db_path="target/mvp/service-recover-json.db",
        expected_output_path="target/mvp/service-recover-json.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )

    result = assert_command_json_result(
        [
            "cmd",
            "/c",
            "tools\mvp\safeclaw_mvp.cmd",
            "service-recover",
            "--db",
            "target/mvp/service-recover-json.db",
            "--task-id",
            "task-wrapper-service-recover-json",
            "--limit",
            "1",
            "--json",
        ],
        errors,
        "mvp-wrapper-cmd-service-recover-json",
        "service-recover",
    )

    assert_service_recover_json_result(
        result,
        errors,
        "mvp-wrapper-cmd-service-recover-json",
        expected_db="target\mvp\service-recover-json.db",
        expected_db_source="flag",
        expected_task_id="task-wrapper-service-recover-json",
        expected_limit=1,
    )

    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-crash",
            "--reset",
            "--task-id",
            "task-wrapper-service-recover-json",
            "--db",
            "target/mvp/service-recover-json.db",
            "--output",
            "target/mvp/service-recover-json.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-recover-json-seed-crash-ps1-json",
        "seed-crash",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-service-recover-json-seed-crash-ps1-json",
        expected_task_id="task-wrapper-service-recover-json",
        expected_db_path="target/mvp/service-recover-json.db",
        expected_output_path="target/mvp/service-recover-json.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "service-recover",
            "--db",
            "target/mvp/service-recover-json.db",
            "--task-id",
            "task-wrapper-service-recover-json",
            "--limit",
            "1",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-service-recover-json",
        "service-recover",
    )

    assert_service_recover_json_result(
        result,
        errors,
        "mvp-wrapper-ps1-service-recover-json",
        expected_db="target\mvp\service-recover-json.db",
        expected_db_source="flag",
        expected_task_id="task-wrapper-service-recover-json",
        expected_limit=1,
    )

    assert_command_json_error(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "service-recover",
            "--limit",
            "bogus",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-recover-invalid-limit-json",
        "service-recover",
        expected_error_message_substring="invalid --limit: bogus",
    )

    assert_command_json_error(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "service-recover",
            "--db",
            "target/mvp/service-recover-missing.db",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-recover-missing-task-json",
        "service-recover",
        expected_error_message_substring="failed step=recover",
        expected_failed_step="recover",
        expected_code="missing-task-context",
        expected_details_message_substring="missing task context",
        expected_remembered_session_task_id="task-wrapper-service-recover-json",
        remembered_session_label="mvp-wrapper-service-recover-missing-task-json missing task-wrapper-service-recover-json",
        reject_legacy_session=True,
        legacy_session_label="mvp-wrapper-service-recover-missing-task-json should not keep legacy session",
    )

    wrapper_service_demo = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "service-demo"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_service_demo_output = (wrapper_service_demo.stdout or "") + (
        wrapper_service_demo.stderr or ""
    )

    if wrapper_service_demo.returncode != 0:
        errors.append(
            f"mvp-wrapper-service-demo ????: exit={wrapper_service_demo.returncode}"
        )

    elif (
        "[demo] service governance resolved => total=2 resolved=2 confirmation=0 manual_review=0"
        not in wrapper_service_demo_output
    ):
        errors.append("mvp-wrapper-service-demo ???? resolved governance")

    elif (
        "[demo] service governance confirmation => total=1 resolved=0 confirmation=1 manual_review=0"
        not in wrapper_service_demo_output
    ):
        errors.append("mvp-wrapper-service-demo ???? confirmation governance")

    result = assert_command_json_result(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "service-demo", "--json"],
        errors,
        "mvp-wrapper-cmd-service-demo-json",
        "service-demo",
    )

    assert_service_demo_json_result(result, errors, "mvp-wrapper-cmd-service-demo-json")

    wrapper_service_env = os.environ.copy()

    wrapper_service_env["PATH"] = os.pathsep.join(
        entry
        for entry in wrapper_service_env.get("PATH", "").split(os.pathsep)
        if ".cargo" not in entry.lower() and "mingw64" not in entry.lower()
    )

    service_demo_without_tool_path = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "service-demo", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=wrapper_service_env,
    )

    payload = load_json_payload(
        service_demo_without_tool_path,
        errors,
        "mvp-wrapper-service-demo-no-tool-path-json",
        0,
    )

    result = (
        None
        if payload is None
        else extract_json_result(
            payload,
            errors,
            "mvp-wrapper-service-demo-no-tool-path-json",
            "service-demo",
        )
    )

    assert_service_demo_json_result(
        result, errors, "mvp-wrapper-service-demo-no-tool-path-json"
    )

    details = assert_command_json_error(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "service-demo", "--bogus", "--json"],
        errors,
        "mvp-wrapper-service-demo-invalid-json",
        "service-demo",
        expected_error_message_substring="unknown argument: --bogus",
        expect_no_remembered_session=True,
    )

    if details is not None and details.get("remembered_session") is not None:
        errors.append("mvp-wrapper-service-demo-invalid-json ???? remembered_session")

    space_wrapper_dir = REPO_ROOT / "target" / "mvp" / "space wrapper"

    space_wrapper_dir.mkdir(parents=True, exist_ok=True)

    result = assert_command_json_result(
        [
            "cmd",
            "/c",
            "tools\mvp\safeclaw_mvp.cmd",
            "run",
            "--reset",
            "--task-id",
            "task-wrapper-cmd-space",
            "--db",
            "target/mvp/space wrapper/run wrapper cmd.db",
            "--output",
            "target/mvp/space wrapper/run wrapper cmd.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-cmd-run-json",
        "run",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-cmd-run-json",
        expected_task_id="task-wrapper-cmd-space",
        expected_db_path="target/mvp/space wrapper/run wrapper cmd.db",
        expected_output_path="target/mvp/space wrapper/run wrapper cmd.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "run",
            "--reset",
            "--task-id",
            "task-wrapper-ps1-space",
            "--db",
            "target/mvp/space wrapper/run wrapper ps1.db",
            "--output",
            "target/mvp/space wrapper/run wrapper ps1.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-run-json",
        "run",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-ps1-run-json",
        expected_task_id="task-wrapper-ps1-space",
        expected_db_path="target/mvp/space wrapper/run wrapper ps1.db",
        expected_output_path="target/mvp/space wrapper/run wrapper ps1.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )

    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "run",
            "--reset",
            "--task-id",
            "task-wrapper-json",
            "--json",
        ],
        errors,
        "mvp-wrapper-run-json",
        "run",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-run-json",
        expected_task_id="task-wrapper-json",
        expected_db_source="default",
        expected_output_source="default",
    )

    wrapper_run_a = subprocess.run(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "run",
            "--reset",
            "--task-id",
            "task-wrapper-a",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_run_a_output = (wrapper_run_a.stdout or "") + (wrapper_run_a.stderr or "")

    if wrapper_run_a.returncode != 0:
        errors.append(f"mvp-wrapper-run-a 执行失败: exit={wrapper_run_a.returncode}")

    elif (
        "[mvp] accepted task => task=task-wrapper-a effect=effect-task-wrapper-a"
        not in wrapper_run_a_output
    ):
        errors.append("mvp-wrapper-run-a 输出缺少 task-wrapper-a")

    wrapper_run_b = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "run", "--task-id", "task-wrapper-b"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_run_b_output = (wrapper_run_b.stdout or "") + (wrapper_run_b.stderr or "")

    if wrapper_run_b.returncode != 0:
        errors.append(f"mvp-wrapper-run-b 执行失败: exit={wrapper_run_b.returncode}")

    elif (
        "[mvp] accepted task => task=task-wrapper-b effect=effect-task-wrapper-b"
        not in wrapper_run_b_output
    ):
        errors.append("mvp-wrapper-run-b 输出缺少 task-wrapper-b")

    wrapper_status = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "status"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_status_output = (wrapper_status.stdout or "") + (
        wrapper_status.stderr or ""
    )

    if wrapper_status.returncode != 0:
        errors.append(f"mvp-wrapper-status 执行失败: exit={wrapper_status.returncode}")

    elif (
        "[mvp] status target => task=task-wrapper-b effect=effect-task-wrapper-b"
        not in wrapper_status_output
    ):
        errors.append("mvp-wrapper-status 输出缺少当前会话 task-wrapper-b")

    wrapper_status_json = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "status", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    payload = load_json_payload(
        wrapper_status_json, errors, "mvp-wrapper-status-json", expected_exit=0
    )

    if payload is not None:
        result = extract_json_result(
            payload, errors, "mvp-wrapper-status-json", "status"
        )

        if result is not None:
            prepared = result.get("prepared") or []

            source_hints = result.get("source_hints") or {}

            if not prepared or prepared[0] != "status":
                errors.append("mvp-wrapper-status-json 缺少 prepared status")

            elif "task-wrapper-b" not in (result.get("captured_output") or ""):
                errors.append("mvp-wrapper-status-json 缺少当前会话 task-wrapper-b 输出")

            elif source_hints.get("task_context") != "session":
                errors.append("mvp-wrapper-status-json 缺少 task_context=session")

    assert_command_json_error(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "status", "--bogus", "--json"],
        errors,
        "mvp-wrapper-cmd-status-fail-json",
        "status",
        expected_error_message_substring="unknown argument",
        error_message_label="mvp-wrapper-cmd-status-fail-json missing unknown argument",
        expected_code="invalid-argument",
        expected_remembered_session_task_id="task-wrapper-b",
        remembered_session_label="mvp-wrapper-cmd-status-fail-json missing task-wrapper-b",
    )

    assert_command_json_error(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "status",
            "--bogus",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-status-fail-json",
        "status",
        expected_error_message_substring="unknown argument",
        error_message_label="mvp-wrapper-ps1-status-fail-json missing unknown argument",
        expected_code="invalid-argument",
        expected_remembered_session_task_id="task-wrapper-b",
        remembered_session_label="mvp-wrapper-ps1-status-fail-json missing task-wrapper-b",
    )

    assert_command_json_error(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "status", "--db", "--json"],
        errors,
        "mvp-wrapper-cmd-status-missing-db-json",
        "status",
        expected_error_message_substring="missing value after --db",
        error_message_label="mvp-wrapper-cmd-status-missing-db-json missing value after --db",
        expected_code="invalid-argument",
        expected_remembered_session_task_id="task-wrapper-b",
        remembered_session_label="mvp-wrapper-cmd-status-missing-db-json missing task-wrapper-b",
    )

    assert_command_json_error(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "status",
            "--db",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-status-missing-db-json",
        "status",
        expected_error_message_substring="missing value after --db",
        error_message_label="mvp-wrapper-ps1-status-missing-db-json missing value after --db",
        expected_code="invalid-argument",
        expected_remembered_session_task_id="task-wrapper-b",
        remembered_session_label="mvp-wrapper-ps1-status-missing-db-json missing task-wrapper-b",
    )

    assert_command_json_error(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "status", "--bogus", "--json"],
        errors,
        "mvp-wrapper-status-fail-json",
        "status",
        expected_error_message_substring="unknown argument",
        error_message_label="mvp-wrapper-status-fail-json 缺少 wrapper 级 unknown argument",
        expected_code="invalid-argument",
        expected_remembered_session_task_id="task-wrapper-b",
        remembered_session_label="mvp-wrapper-status-fail-json remembered_session 缺少 task-wrapper-b",
    )

    assert_command_json_error(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "status", "--db", "--json"],
        errors,
        "mvp-wrapper-status-missing-db-json",
        "status",
        expected_error_message_substring="missing value after --db",
        error_message_label="mvp-wrapper-status-missing-db-json 缺少 missing value after --db",
        expected_code="invalid-argument",
        expected_remembered_session_task_id="task-wrapper-b",
        remembered_session_label="mvp-wrapper-status-missing-db-json remembered_session 缺少 task-wrapper-b",
    )

    wrapper_session = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "session"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_session_output = (wrapper_session.stdout or "") + (
        wrapper_session.stderr or ""
    )

    if wrapper_session.returncode != 0:
        errors.append(f"mvp-wrapper-session 执行失败: exit={wrapper_session.returncode}")

    elif (
        "[mvp-wrapper] session => task=task-wrapper-b effect=effect-task-wrapper-b"
        not in wrapper_session_output
    ):
        errors.append("mvp-wrapper-session 输出缺少当前会话 task-wrapper-b")

    elif "path=target\\mvp\\last_session.json" not in wrapper_session_output:
        errors.append("mvp-wrapper-session 输出缺少 remembered session 路径")

    wrapper_session_json = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "session", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_session_json_output = (wrapper_session_json.stdout or "") + (
        wrapper_session_json.stderr or ""
    )

    payload = load_json_payload(
        wrapper_session_json, errors, "mvp-wrapper-session-json", expected_exit=0
    )

    if payload is not None:
        result = extract_json_result(
            payload, errors, "mvp-wrapper-session-json", "session"
        )

        if result is not None:
            if (
                result.get("task_id") != "task-wrapper-b"
                or result.get("effect_id") != "effect-task-wrapper-b"
            ):
                errors.append("mvp-wrapper-session-json 输出缺少当前会话 task-wrapper-b")

    wrapper_sessions = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "sessions"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_sessions_output = (wrapper_sessions.stdout or "") + (
        wrapper_sessions.stderr or ""
    )

    if wrapper_sessions.returncode != 0:
        errors.append(f"mvp-wrapper-sessions 执行失败: exit={wrapper_sessions.returncode}")

    elif (
        "[mvp-wrapper] sessions => db=target\\mvp\\session.db limit=5 source=session"
        not in wrapper_sessions_output
    ):
        errors.append("mvp-wrapper-sessions 输出缺少 db source=session")

    elif (
        "[mvp-wrapper] recent[0] => task=task-wrapper-b effect=effect-task-wrapper-b"
        not in wrapper_sessions_output
    ):
        errors.append("mvp-wrapper-sessions 输出缺少最近任务 task-wrapper-b")

    elif (
        "[mvp-wrapper] recent[1] => task=task-wrapper-a effect=effect-task-wrapper-a"
        not in wrapper_sessions_output
    ):
        errors.append("mvp-wrapper-sessions 输出缺少旧任务 task-wrapper-a")

    wrapper_sessions_json = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "sessions", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    payload = load_json_payload(
        wrapper_sessions_json, errors, "mvp-wrapper-sessions-json", expected_exit=0
    )

    if payload is not None:
        result = extract_json_result(
            payload, errors, "mvp-wrapper-sessions-json", "sessions"
        )

        if result is not None:
            rows = result.get("rows") or []

            if result.get("db_source") != "session":
                errors.append("mvp-wrapper-sessions-json 输出缺少 db_source=session")

            elif not rows or rows[0].get("task_id") != "task-wrapper-b":
                errors.append("mvp-wrapper-sessions-json 输出缺少最近任务 task-wrapper-b")

            elif len(rows) < 2 or rows[1].get("task_id") != "task-wrapper-a":
                errors.append("mvp-wrapper-sessions-json 输出缺少旧任务 task-wrapper-a")

    wrapper_cmd_session = subprocess.run(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "session"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_cmd_session_output = (wrapper_cmd_session.stdout or "") + (
        wrapper_cmd_session.stderr or ""
    )

    if wrapper_cmd_session.returncode != 0:
        errors.append(
            f"mvp-wrapper-cmd-session failed: exit={wrapper_cmd_session.returncode}"
        )

    elif (
        "[mvp-wrapper] session => task=task-wrapper-b effect=effect-task-wrapper-b"
        not in wrapper_cmd_session_output
    ):
        errors.append("mvp-wrapper-cmd-session missing current session task-wrapper-b")

    elif "path=target\mvp\last_session.json" not in wrapper_cmd_session_output:
        errors.append("mvp-wrapper-cmd-session missing remembered session path")

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "session",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-session-json",
        "session",
    )

    assert_session_json_result(
        result,
        errors,
        "mvp-wrapper-ps1-session-json",
        expected_task_id="task-wrapper-b",
    )

    wrapper_cmd_sessions = subprocess.run(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "sessions"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_cmd_sessions_output = (wrapper_cmd_sessions.stdout or "") + (
        wrapper_cmd_sessions.stderr or ""
    )

    if wrapper_cmd_sessions.returncode != 0:
        errors.append(
            f"mvp-wrapper-cmd-sessions failed: exit={wrapper_cmd_sessions.returncode}"
        )

    elif (
        "[mvp-wrapper] sessions => db=target\mvp\session.db limit=5 source=session"
        not in wrapper_cmd_sessions_output
    ):
        errors.append("mvp-wrapper-cmd-sessions missing db source=session")

    elif (
        "[mvp-wrapper] current => task=task-wrapper-b effect=effect-task-wrapper-b current_db=true"
        not in wrapper_cmd_sessions_output
    ):
        errors.append("mvp-wrapper-cmd-sessions missing task-wrapper-b row")

    elif (
        "[mvp-wrapper] recent[0] => task=task-wrapper-b effect=effect-task-wrapper-b"
        not in wrapper_cmd_sessions_output
    ):
        errors.append("mvp-wrapper-cmd-sessions missing task-wrapper-b row")

    elif (
        "[mvp-wrapper] recent[1] => task=task-wrapper-a effect=effect-task-wrapper-a"
        not in wrapper_cmd_sessions_output
    ):
        errors.append("mvp-wrapper-cmd-sessions missing task-wrapper-a row")

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "sessions",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-sessions-json",
        "sessions",
    )

    assert_sessions_json_result(
        result,
        errors,
        "mvp-wrapper-ps1-sessions-json",
        expected_current_task_id="task-wrapper-b",
        expected_previous_task_id="task-wrapper-a",
    )

    result = assert_command_json_result(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "use", "--index", "1", "--json"],
        errors,
        "mvp-wrapper-cmd-use-json",
        "use",
    )

    assert_use_json_result(
        result,
        errors,
        "mvp-wrapper-cmd-use-json",
        expected_task_id="task-wrapper-a",
        expected_source="index:1",
    )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "status",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-status-json",
        "status",
    )

    assert_session_passthrough_json_result(
        result,
        errors,
        "mvp-wrapper-ps1-status-json",
        action="status",
        expected_task_id="task-wrapper-a",
    )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "use",
            "--index",
            "0",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-use-json",
        "use",
    )

    assert_use_json_result(
        result,
        errors,
        "mvp-wrapper-ps1-use-json",
        expected_task_id="task-wrapper-b",
        expected_source="index:0",
    )

    result = assert_command_json_result(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "status", "--json"],
        errors,
        "mvp-wrapper-cmd-status-json",
        "status",
    )

    assert_session_passthrough_json_result(
        result,
        errors,
        "mvp-wrapper-cmd-status-json",
        action="status",
        expected_task_id="task-wrapper-b",
    )

    result = assert_command_json_result(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "report", "--json"],
        errors,
        "mvp-wrapper-cmd-report-json",
        "report",
    )

    assert_session_passthrough_json_result(
        result,
        errors,
        "mvp-wrapper-cmd-report-json",
        action="report",
        expected_task_id="task-wrapper-b",
    )

    result = assert_command_json_result(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "session", "--json"],
        errors,
        "mvp-wrapper-cmd-session-json",
        "session",
    )

    assert_session_json_result(
        result,
        errors,
        "mvp-wrapper-cmd-session-json",
        expected_task_id="task-wrapper-b",
    )

    result = assert_command_json_result(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "sessions", "--json"],
        errors,
        "mvp-wrapper-cmd-sessions-json",
        "sessions",
    )

    assert_sessions_json_result(
        result,
        errors,
        "mvp-wrapper-cmd-sessions-json",
        expected_current_task_id="task-wrapper-b",
        expected_previous_task_id="task-wrapper-a",
    )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "report",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-report-json",
        "report",
    )

    assert_session_passthrough_json_result(
        result,
        errors,
        "mvp-wrapper-ps1-report-json",
        action="report",
        expected_task_id="task-wrapper-b",
    )

    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-failed",
            "--reset",
            "--task-id",
            "task-wrapper-retry-json",
            "--db",
            "target/mvp/retry-json.db",
            "--output",
            "target/mvp/retry-json.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-retry-json-seed-failed-ps1-json",
        "seed-failed",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-retry-json-seed-failed-ps1-json",
        expected_task_id="task-wrapper-retry-json",
        expected_db_path="target/mvp/retry-json.db",
        expected_output_path="target/mvp/retry-json.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "retry",
            "--db",
            "target/mvp/retry-json.db",
            "--task-id",
            "task-wrapper-retry-json",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-retry-json",
        "retry",
    )

    if result is not None:
        prepared = result.get("prepared") or []

        remembered_session = result.get("remembered_session") or {}

        source_hints = result.get("source_hints") or {}

        captured_output = str(result.get("captured_output") or "")

        if not prepared or prepared[0] != "retry":
            errors.append("mvp-wrapper-ps1-retry-json missing prepared retry")

        elif "task-wrapper-retry-json" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-retry-json missing captured task task-wrapper-retry-json"
            )

        elif (
            not isinstance(remembered_session, dict)
            or remembered_session.get("task_id") != "task-wrapper-retry-json"
        ):
            errors.append(
                "mvp-wrapper-ps1-retry-json missing remembered session task-wrapper-retry-json"
            )

        elif not isinstance(source_hints, dict) or source_hints.get("db") != "flag":
            errors.append("mvp-wrapper-ps1-retry-json missing source_hints.db=flag")

        elif source_hints.get("output") != "session":
            errors.append(
                "mvp-wrapper-ps1-retry-json missing source_hints.output=session"
            )

        elif source_hints.get("owner_id") != "session":
            errors.append(
                "mvp-wrapper-ps1-retry-json missing source_hints.owner_id=session"
            )

        elif source_hints.get("task_context") != "flag":
            errors.append(
                "mvp-wrapper-ps1-retry-json missing source_hints.task_context=flag"
            )

    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-crash",
            "--reset",
            "--task-id",
            "task-wrapper-recover-json",
            "--db",
            "target/mvp/recover-json.db",
            "--output",
            "target/mvp/recover-json.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-recover-json-seed-crash-ps1-json",
        "seed-crash",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-recover-json-seed-crash-ps1-json",
        expected_task_id="task-wrapper-recover-json",
        expected_db_path="target/mvp/recover-json.db",
        expected_output_path="target/mvp/recover-json.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "recover",
            "--db",
            "target/mvp/recover-json.db",
            "--task-id",
            "task-wrapper-recover-json",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-recover-json",
        "recover",
    )

    if result is not None:
        prepared = result.get("prepared") or []

        remembered_session = result.get("remembered_session") or {}

        source_hints = result.get("source_hints") or {}

        captured_output = str(result.get("captured_output") or "")

        if not prepared or prepared[0] != "recover":
            errors.append("mvp-wrapper-ps1-recover-json missing prepared recover")

        elif "task-wrapper-recover-json" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-recover-json missing captured task task-wrapper-recover-json"
            )

        elif (
            not isinstance(remembered_session, dict)
            or remembered_session.get("task_id") != "task-wrapper-recover-json"
        ):
            errors.append(
                "mvp-wrapper-ps1-recover-json missing remembered session task-wrapper-recover-json"
            )

        elif not isinstance(source_hints, dict) or source_hints.get("db") != "flag":
            errors.append("mvp-wrapper-ps1-recover-json missing source_hints.db=flag")

        elif source_hints.get("output") != "session":
            errors.append(
                "mvp-wrapper-ps1-recover-json missing source_hints.output=session"
            )

        elif source_hints.get("owner_id") != "session":
            errors.append(
                "mvp-wrapper-ps1-recover-json missing source_hints.owner_id=session"
            )

        elif source_hints.get("task_context") != "flag":
            errors.append(
                "mvp-wrapper-ps1-recover-json missing source_hints.task_context=flag"
            )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "status",
            "--db",
            "target/mvp/recover-json.db",
            "--task-id",
            "task-wrapper-recover-json",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-status-explicit-json",
        "status",
    )

    if result is not None:
        prepared = result.get("prepared") or []

        remembered_session = result.get("remembered_session") or {}

        source_hints = result.get("source_hints") or {}

        captured_output = str(result.get("captured_output") or "")

        if not prepared or prepared[0] != "status":
            errors.append(
                "mvp-wrapper-ps1-status-explicit-json missing prepared status"
            )

        elif "task-wrapper-recover-json" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-status-explicit-json missing captured task task-wrapper-recover-json"
            )

        elif (
            not isinstance(remembered_session, dict)
            or remembered_session.get("task_id") != "task-wrapper-recover-json"
        ):
            errors.append(
                "mvp-wrapper-ps1-status-explicit-json missing remembered session task-wrapper-recover-json"
            )

        elif not isinstance(source_hints, dict) or source_hints.get("db") != "flag":
            errors.append(
                "mvp-wrapper-ps1-status-explicit-json missing source_hints.db=flag"
            )

        elif source_hints.get("output") != "session":
            errors.append(
                "mvp-wrapper-ps1-status-explicit-json missing source_hints.output=session"
            )

        elif source_hints.get("owner_id") != "session":
            errors.append(
                "mvp-wrapper-ps1-status-explicit-json missing source_hints.owner_id=session"
            )

        elif source_hints.get("task_context") != "flag":
            errors.append(
                "mvp-wrapper-ps1-status-explicit-json missing source_hints.task_context=flag"
            )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "report",
            "--db",
            "target/mvp/recover-json.db",
            "--task-id",
            "task-wrapper-recover-json",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-report-explicit-json",
        "report",
    )

    if result is not None:
        prepared = result.get("prepared") or []

        remembered_session = result.get("remembered_session") or {}

        source_hints = result.get("source_hints") or {}

        captured_output = str(result.get("captured_output") or "")

        if not prepared or prepared[0] != "report":
            errors.append(
                "mvp-wrapper-ps1-report-explicit-json missing prepared report"
            )

        elif "task-wrapper-recover-json" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-explicit-json missing captured task task-wrapper-recover-json"
            )

        elif (
            not isinstance(remembered_session, dict)
            or remembered_session.get("task_id") != "task-wrapper-recover-json"
        ):
            errors.append(
                "mvp-wrapper-ps1-report-explicit-json missing remembered session task-wrapper-recover-json"
            )

        elif not isinstance(source_hints, dict) or source_hints.get("db") != "flag":
            errors.append(
                "mvp-wrapper-ps1-report-explicit-json missing source_hints.db=flag"
            )

        elif source_hints.get("output") != "session":
            errors.append(
                "mvp-wrapper-ps1-report-explicit-json missing source_hints.output=session"
            )

        elif source_hints.get("owner_id") != "session":
            errors.append(
                "mvp-wrapper-ps1-report-explicit-json missing source_hints.owner_id=session"
            )

        elif source_hints.get("task_context") != "flag":
            errors.append(
                "mvp-wrapper-ps1-report-explicit-json missing source_hints.task_context=flag"
            )

    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-crash",
            "--reset",
            "--task-id",
            "task-wrapper-status-explicit-crash",
            "--db",
            "target/mvp/status-explicit-crash.db",
            "--output",
            "target/mvp/status-explicit-crash.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-status-explicit-crash-seed-json",
        "seed-crash",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-status-explicit-crash-seed-json",
        expected_task_id="task-wrapper-status-explicit-crash",
        expected_db_path="target/mvp/status-explicit-crash.db",
        expected_output_path="target/mvp/status-explicit-crash.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "status",
            "--db",
            "target/mvp/status-explicit-crash.db",
            "--task-id",
            "task-wrapper-status-explicit-crash",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-status-explicit-crash-json",
        "status",
    )

    if result is not None:
        prepared = result.get("prepared") or []

        remembered_session = result.get("remembered_session") or {}

        source_hints = result.get("source_hints") or {}

        captured_output = str(result.get("captured_output") or "")

        if not prepared or prepared[0] != "status":
            errors.append(
                "mvp-wrapper-ps1-status-explicit-crash-json missing prepared status"
            )

        elif "task-wrapper-status-explicit-crash" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-status-explicit-crash-json missing captured task task-wrapper-status-explicit-crash"
            )

        elif "QueueForManualReview" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-status-explicit-crash-json missing QueueForManualReview"
            )

        elif "worker=Uncertain" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-status-explicit-crash-json missing worker=Uncertain"
            )

        elif "effect=Uncertain" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-status-explicit-crash-json missing effect=Uncertain"
            )

        elif (
            not isinstance(remembered_session, dict)
            or remembered_session.get("task_id") != "task-wrapper-status-explicit-crash"
        ):
            errors.append(
                "mvp-wrapper-ps1-status-explicit-crash-json missing remembered session task-wrapper-status-explicit-crash"
            )

        elif not isinstance(source_hints, dict) or source_hints.get("db") != "flag":
            errors.append(
                "mvp-wrapper-ps1-status-explicit-crash-json missing source_hints.db=flag"
            )

        elif source_hints.get("output") != "session":
            errors.append(
                "mvp-wrapper-ps1-status-explicit-crash-json missing source_hints.output=session"
            )

        elif source_hints.get("owner_id") != "session":
            errors.append(
                "mvp-wrapper-ps1-status-explicit-crash-json missing source_hints.owner_id=session"
            )

        elif source_hints.get("task_context") != "flag":
            errors.append(
                "mvp-wrapper-ps1-status-explicit-crash-json missing source_hints.task_context=flag"
            )

    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-crash",
            "--reset",
            "--task-id",
            "task-wrapper-report-explicit-crash",
            "--db",
            "target/mvp/report-explicit-crash.db",
            "--output",
            "target/mvp/report-explicit-crash.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-report-explicit-crash-seed-json",
        "seed-crash",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-report-explicit-crash-seed-json",
        expected_task_id="task-wrapper-report-explicit-crash",
        expected_db_path="target/mvp/report-explicit-crash.db",
        expected_output_path="target/mvp/report-explicit-crash.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "report",
            "--db",
            "target/mvp/report-explicit-crash.db",
            "--task-id",
            "task-wrapper-report-explicit-crash",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-report-explicit-crash-json",
        "report",
    )

    if result is not None:
        prepared = result.get("prepared") or []

        remembered_session = result.get("remembered_session") or {}

        source_hints = result.get("source_hints") or {}

        captured_output = str(result.get("captured_output") or "")

        if not prepared or prepared[0] != "report":
            errors.append(
                "mvp-wrapper-ps1-report-explicit-crash-json missing prepared report"
            )

        elif "task-wrapper-report-explicit-crash" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-explicit-crash-json missing captured task task-wrapper-report-explicit-crash"
            )

        elif "QueueForManualReview" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-explicit-crash-json missing QueueForManualReview"
            )

        elif "worker=Uncertain" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-explicit-crash-json missing worker=Uncertain"
            )

        elif "effect=Uncertain" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-explicit-crash-json missing effect=Uncertain"
            )

        elif (
            not isinstance(remembered_session, dict)
            or remembered_session.get("task_id") != "task-wrapper-report-explicit-crash"
        ):
            errors.append(
                "mvp-wrapper-ps1-report-explicit-crash-json missing remembered session task-wrapper-report-explicit-crash"
            )

        elif not isinstance(source_hints, dict) or source_hints.get("db") != "flag":
            errors.append(
                "mvp-wrapper-ps1-report-explicit-crash-json missing source_hints.db=flag"
            )

        elif source_hints.get("output") != "session":
            errors.append(
                "mvp-wrapper-ps1-report-explicit-crash-json missing source_hints.output=session"
            )

        elif source_hints.get("owner_id") != "session":
            errors.append(
                "mvp-wrapper-ps1-report-explicit-crash-json missing source_hints.owner_id=session"
            )

        elif source_hints.get("task_context") != "flag":
            errors.append(
                "mvp-wrapper-ps1-report-explicit-crash-json missing source_hints.task_context=flag"
            )

    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-crash",
            "--reset",
            "--task-id",
            "task-wrapper-session-explicit-crash",
            "--db",
            "target/mvp/session-explicit-crash.db",
            "--output",
            "target/mvp/session-explicit-crash.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-session-explicit-crash-seed-json",
        "seed-crash",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-session-explicit-crash-seed-json",
        expected_task_id="task-wrapper-session-explicit-crash",
        expected_db_path="target/mvp/session-explicit-crash.db",
        expected_output_path="target/mvp/session-explicit-crash.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "report",
            "--db",
            "target/mvp/session-explicit-crash.db",
            "--task-id",
            "task-wrapper-session-explicit-crash",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-report-session-explicit-crash-json",
        "report",
    )

    if result is not None:
        prepared = result.get("prepared") or []

        remembered_session = result.get("remembered_session") or {}

        source_hints = result.get("source_hints") or {}

        captured_output = str(result.get("captured_output") or "")

        if not prepared or prepared[0] != "report":
            errors.append(
                "mvp-wrapper-ps1-report-session-explicit-crash-json missing prepared report"
            )

        elif "task-wrapper-session-explicit-crash" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-session-explicit-crash-json missing captured task task-wrapper-session-explicit-crash"
            )

        elif "QueueForManualReview" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-session-explicit-crash-json missing QueueForManualReview"
            )

        elif "worker=Uncertain" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-session-explicit-crash-json missing worker=Uncertain"
            )

        elif "effect=Uncertain" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-session-explicit-crash-json missing effect=Uncertain"
            )

        elif (
            not isinstance(remembered_session, dict)
            or remembered_session.get("task_id")
            != "task-wrapper-session-explicit-crash"
        ):
            errors.append(
                "mvp-wrapper-ps1-report-session-explicit-crash-json missing remembered session task-wrapper-session-explicit-crash"
            )

        elif not isinstance(source_hints, dict) or source_hints.get("db") != "flag":
            errors.append(
                "mvp-wrapper-ps1-report-session-explicit-crash-json missing source_hints.db=flag"
            )

        elif source_hints.get("output") != "session":
            errors.append(
                "mvp-wrapper-ps1-report-session-explicit-crash-json missing source_hints.output=session"
            )

        elif source_hints.get("owner_id") != "session":
            errors.append(
                "mvp-wrapper-ps1-report-session-explicit-crash-json missing source_hints.owner_id=session"
            )

        elif source_hints.get("task_context") != "flag":
            errors.append(
                "mvp-wrapper-ps1-report-session-explicit-crash-json missing source_hints.task_context=flag"
            )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "session",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-session-explicit-crash-json",
        "session",
    )

    if result is not None:
        if result.get("task_id") != "task-wrapper-session-explicit-crash":
            errors.append(
                "mvp-wrapper-ps1-session-explicit-crash-json missing task_id=task-wrapper-session-explicit-crash"
            )

        elif result.get("effect_id") != "effect-task-wrapper-session-explicit-crash":
            errors.append(
                "mvp-wrapper-ps1-session-explicit-crash-json missing effect_id=effect-task-wrapper-session-explicit-crash"
            )

        elif result.get("db") != "target/mvp/session-explicit-crash.db":
            errors.append(
                "mvp-wrapper-ps1-session-explicit-crash-json missing db=target/mvp/session-explicit-crash.db"
            )

        elif result.get("output") != "target/mvp/session-explicit-crash.txt":
            errors.append(
                "mvp-wrapper-ps1-session-explicit-crash-json missing output=target/mvp/session-explicit-crash.txt"
            )

        elif result.get("owner_id") != "safeclaw-mvp":
            errors.append(
                "mvp-wrapper-ps1-session-explicit-crash-json missing owner_id=safeclaw-mvp"
            )

    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-crash",
            "--reset",
            "--task-id",
            "task-wrapper-sessions-explicit-crash",
            "--db",
            "target/mvp/sessions-explicit-crash.db",
            "--output",
            "target/mvp/sessions-explicit-crash.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-sessions-explicit-crash-seed-json",
        "seed-crash",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-sessions-explicit-crash-seed-json",
        expected_task_id="task-wrapper-sessions-explicit-crash",
        expected_db_path="target/mvp/sessions-explicit-crash.db",
        expected_output_path="target/mvp/sessions-explicit-crash.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "report",
            "--db",
            "target/mvp/sessions-explicit-crash.db",
            "--task-id",
            "task-wrapper-sessions-explicit-crash",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-report-sessions-explicit-crash-json",
        "report",
    )

    if result is not None:
        prepared = result.get("prepared") or []

        remembered_session = result.get("remembered_session") or {}

        source_hints = result.get("source_hints") or {}

        captured_output = str(result.get("captured_output") or "")

        if not prepared or prepared[0] != "report":
            errors.append(
                "mvp-wrapper-ps1-report-sessions-explicit-crash-json missing prepared report"
            )

        elif "task-wrapper-sessions-explicit-crash" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-sessions-explicit-crash-json missing captured task task-wrapper-sessions-explicit-crash"
            )

        elif "QueueForManualReview" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-sessions-explicit-crash-json missing QueueForManualReview"
            )

        elif "worker=Uncertain" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-sessions-explicit-crash-json missing worker=Uncertain"
            )

        elif "effect=Uncertain" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-sessions-explicit-crash-json missing effect=Uncertain"
            )

        elif (
            not isinstance(remembered_session, dict)
            or remembered_session.get("task_id")
            != "task-wrapper-sessions-explicit-crash"
        ):
            errors.append(
                "mvp-wrapper-ps1-report-sessions-explicit-crash-json missing remembered session task-wrapper-sessions-explicit-crash"
            )

        elif not isinstance(source_hints, dict) or source_hints.get("db") != "flag":
            errors.append(
                "mvp-wrapper-ps1-report-sessions-explicit-crash-json missing source_hints.db=flag"
            )

        elif source_hints.get("output") != "session":
            errors.append(
                "mvp-wrapper-ps1-report-sessions-explicit-crash-json missing source_hints.output=session"
            )

        elif source_hints.get("owner_id") != "session":
            errors.append(
                "mvp-wrapper-ps1-report-sessions-explicit-crash-json missing source_hints.owner_id=session"
            )

        elif source_hints.get("task_context") != "flag":
            errors.append(
                "mvp-wrapper-ps1-report-sessions-explicit-crash-json missing source_hints.task_context=flag"
            )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "sessions",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-sessions-explicit-crash-json",
        "sessions",
    )

    if result is not None:
        rows = result.get("rows") or []

        current_session = result.get("current_session") or {}

        if result.get("db") != "target/mvp/sessions-explicit-crash.db":
            errors.append(
                "mvp-wrapper-ps1-sessions-explicit-crash-json missing db=target/mvp/sessions-explicit-crash.db"
            )

        elif result.get("db_source") != "session":
            errors.append(
                "mvp-wrapper-ps1-sessions-explicit-crash-json missing db_source=session"
            )

        elif result.get("limit") != 5:
            errors.append(
                "mvp-wrapper-ps1-sessions-explicit-crash-json missing limit=5"
            )

        elif (
            not isinstance(current_session, dict)
            or current_session.get("task_id") != "task-wrapper-sessions-explicit-crash"
        ):
            errors.append(
                "mvp-wrapper-ps1-sessions-explicit-crash-json missing current_session task-wrapper-sessions-explicit-crash"
            )

        elif (
            current_session.get("effect_id")
            != "effect-task-wrapper-sessions-explicit-crash"
        ):
            errors.append(
                "mvp-wrapper-ps1-sessions-explicit-crash-json missing current_session effect-task-wrapper-sessions-explicit-crash"
            )

        elif current_session.get("db") != "target/mvp/sessions-explicit-crash.db":
            errors.append(
                "mvp-wrapper-ps1-sessions-explicit-crash-json missing current_session db=target/mvp/sessions-explicit-crash.db"
            )

        elif current_session.get("output") != "target/mvp/sessions-explicit-crash.txt":
            errors.append(
                "mvp-wrapper-ps1-sessions-explicit-crash-json missing current_session output=target/mvp/sessions-explicit-crash.txt"
            )

        elif current_session.get("owner_id") != "safeclaw-mvp":
            errors.append(
                "mvp-wrapper-ps1-sessions-explicit-crash-json missing current_session owner_id=safeclaw-mvp"
            )

        elif (
            not rows or rows[0].get("task_id") != "task-wrapper-sessions-explicit-crash"
        ):
            errors.append(
                "mvp-wrapper-ps1-sessions-explicit-crash-json missing rows[0] task-wrapper-sessions-explicit-crash"
            )

        elif rows[0].get("effect_id") != "effect-task-wrapper-sessions-explicit-crash":
            errors.append(
                "mvp-wrapper-ps1-sessions-explicit-crash-json missing rows[0] effect-task-wrapper-sessions-explicit-crash"
            )

        elif rows[0].get("worker_state") != "uncertain":
            errors.append(
                "mvp-wrapper-ps1-sessions-explicit-crash-json missing rows[0] worker_state=uncertain"
            )

        elif rows[0].get("effect_status") != "uncertain":
            errors.append(
                "mvp-wrapper-ps1-sessions-explicit-crash-json missing rows[0] effect_status=uncertain"
            )

        elif rows[0].get("next_action") != "recover":
            errors.append(
                "mvp-wrapper-ps1-sessions-explicit-crash-json missing rows[0] next_action=recover"
            )

        elif rows[0].get("coordination_summary") != "recover_now":
            errors.append(
                "mvp-wrapper-ps1-sessions-explicit-crash-json missing rows[0] coordination_summary=recover_now"
            )

        elif rows[0].get("current") is not True:
            errors.append(
                "mvp-wrapper-ps1-sessions-explicit-crash-json missing rows[0] current=true"
            )

    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-crash",
            "--reset",
            "--task-id",
            "task-wrapper-status-session-crash",
            "--db",
            "target/mvp/status-session-crash.db",
            "--output",
            "target/mvp/status-session-crash.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-status-session-crash-seed-json",
        "seed-crash",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-status-session-crash-seed-json",
        expected_task_id="task-wrapper-status-session-crash",
        expected_db_path="target/mvp/status-session-crash.db",
        expected_output_path="target/mvp/status-session-crash.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "report",
            "--db",
            "target/mvp/status-session-crash.db",
            "--task-id",
            "task-wrapper-status-session-crash",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-report-status-session-crash-json",
        "report",
    )

    if result is not None:
        prepared = result.get("prepared") or []

        remembered_session = result.get("remembered_session") or {}

        source_hints = result.get("source_hints") or {}

        captured_output = str(result.get("captured_output") or "")

        if not prepared or prepared[0] != "report":
            errors.append(
                "mvp-wrapper-ps1-report-status-session-crash-json missing prepared report"
            )

        elif "task-wrapper-status-session-crash" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-status-session-crash-json missing captured task task-wrapper-status-session-crash"
            )

        elif "QueueForManualReview" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-status-session-crash-json missing QueueForManualReview"
            )

        elif "worker=Uncertain" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-status-session-crash-json missing worker=Uncertain"
            )

        elif "effect=Uncertain" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-status-session-crash-json missing effect=Uncertain"
            )

        elif (
            not isinstance(remembered_session, dict)
            or remembered_session.get("task_id") != "task-wrapper-status-session-crash"
        ):
            errors.append(
                "mvp-wrapper-ps1-report-status-session-crash-json missing remembered session task-wrapper-status-session-crash"
            )

        elif not isinstance(source_hints, dict) or source_hints.get("db") != "flag":
            errors.append(
                "mvp-wrapper-ps1-report-status-session-crash-json missing source_hints.db=flag"
            )

        elif source_hints.get("output") != "session":
            errors.append(
                "mvp-wrapper-ps1-report-status-session-crash-json missing source_hints.output=session"
            )

        elif source_hints.get("owner_id") != "session":
            errors.append(
                "mvp-wrapper-ps1-report-status-session-crash-json missing source_hints.owner_id=session"
            )

        elif source_hints.get("task_context") != "flag":
            errors.append(
                "mvp-wrapper-ps1-report-status-session-crash-json missing source_hints.task_context=flag"
            )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "status",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-status-session-crash-json",
        "status",
    )

    if result is not None:
        prepared = result.get("prepared") or []

        remembered_session = result.get("remembered_session") or {}

        source_hints = result.get("source_hints") or {}

        captured_output = str(result.get("captured_output") or "")

        if not prepared or prepared[0] != "status":
            errors.append(
                "mvp-wrapper-ps1-status-session-crash-json missing prepared status"
            )

        elif "task-wrapper-status-session-crash" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-status-session-crash-json missing captured task task-wrapper-status-session-crash"
            )

        elif "QueueForManualReview" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-status-session-crash-json missing QueueForManualReview"
            )

        elif "worker=Uncertain" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-status-session-crash-json missing worker=Uncertain"
            )

        elif "effect=Uncertain" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-status-session-crash-json missing effect=Uncertain"
            )

        elif (
            not isinstance(remembered_session, dict)
            or remembered_session.get("task_id") != "task-wrapper-status-session-crash"
        ):
            errors.append(
                "mvp-wrapper-ps1-status-session-crash-json missing remembered session task-wrapper-status-session-crash"
            )

        elif not isinstance(source_hints, dict) or source_hints.get("db") != "session":
            errors.append(
                "mvp-wrapper-ps1-status-session-crash-json missing source_hints.db=session"
            )

        elif source_hints.get("output") != "session":
            errors.append(
                "mvp-wrapper-ps1-status-session-crash-json missing source_hints.output=session"
            )

        elif source_hints.get("owner_id") != "session":
            errors.append(
                "mvp-wrapper-ps1-status-session-crash-json missing source_hints.owner_id=session"
            )

        elif source_hints.get("task_context") != "session":
            errors.append(
                "mvp-wrapper-ps1-status-session-crash-json missing source_hints.task_context=session"
            )

    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-crash",
            "--reset",
            "--task-id",
            "task-wrapper-report-session-crash",
            "--db",
            "target/mvp/report-session-crash.db",
            "--output",
            "target/mvp/report-session-crash.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-report-session-crash-seed-json",
        "seed-crash",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-report-session-crash-seed-json",
        expected_task_id="task-wrapper-report-session-crash",
        expected_db_path="target/mvp/report-session-crash.db",
        expected_output_path="target/mvp/report-session-crash.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "report",
            "--db",
            "target/mvp/report-session-crash.db",
            "--task-id",
            "task-wrapper-report-session-crash",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-report-report-session-crash-json",
        "report",
    )

    if result is not None:
        prepared = result.get("prepared") or []

        remembered_session = result.get("remembered_session") or {}

        source_hints = result.get("source_hints") or {}

        captured_output = str(result.get("captured_output") or "")

        if not prepared or prepared[0] != "report":
            errors.append(
                "mvp-wrapper-ps1-report-report-session-crash-json missing prepared report"
            )

        elif "task-wrapper-report-session-crash" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-report-session-crash-json missing captured task task-wrapper-report-session-crash"
            )

        elif "QueueForManualReview" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-report-session-crash-json missing QueueForManualReview"
            )

        elif "worker=Uncertain" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-report-session-crash-json missing worker=Uncertain"
            )

        elif "effect=Uncertain" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-report-session-crash-json missing effect=Uncertain"
            )

        elif (
            not isinstance(remembered_session, dict)
            or remembered_session.get("task_id") != "task-wrapper-report-session-crash"
        ):
            errors.append(
                "mvp-wrapper-ps1-report-report-session-crash-json missing remembered session task-wrapper-report-session-crash"
            )

        elif not isinstance(source_hints, dict) or source_hints.get("db") != "flag":
            errors.append(
                "mvp-wrapper-ps1-report-report-session-crash-json missing source_hints.db=flag"
            )

        elif source_hints.get("output") != "session":
            errors.append(
                "mvp-wrapper-ps1-report-report-session-crash-json missing source_hints.output=session"
            )

        elif source_hints.get("owner_id") != "session":
            errors.append(
                "mvp-wrapper-ps1-report-report-session-crash-json missing source_hints.owner_id=session"
            )

        elif source_hints.get("task_context") != "flag":
            errors.append(
                "mvp-wrapper-ps1-report-report-session-crash-json missing source_hints.task_context=flag"
            )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "report",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-report-session-crash-json",
        "report",
    )

    if result is not None:
        prepared = result.get("prepared") or []

        remembered_session = result.get("remembered_session") or {}

        source_hints = result.get("source_hints") or {}

        captured_output = str(result.get("captured_output") or "")

        if not prepared or prepared[0] != "report":
            errors.append(
                "mvp-wrapper-ps1-report-session-crash-json missing prepared report"
            )

        elif "task-wrapper-report-session-crash" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-session-crash-json missing captured task task-wrapper-report-session-crash"
            )

        elif "QueueForManualReview" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-session-crash-json missing QueueForManualReview"
            )

        elif "worker=Uncertain" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-session-crash-json missing worker=Uncertain"
            )

        elif "effect=Uncertain" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-session-crash-json missing effect=Uncertain"
            )

        elif (
            not isinstance(remembered_session, dict)
            or remembered_session.get("task_id") != "task-wrapper-report-session-crash"
        ):
            errors.append(
                "mvp-wrapper-ps1-report-session-crash-json missing remembered session task-wrapper-report-session-crash"
            )

        elif not isinstance(source_hints, dict) or source_hints.get("db") != "session":
            errors.append(
                "mvp-wrapper-ps1-report-session-crash-json missing source_hints.db=session"
            )

        elif source_hints.get("output") != "session":
            errors.append(
                "mvp-wrapper-ps1-report-session-crash-json missing source_hints.output=session"
            )

        elif source_hints.get("owner_id") != "session":
            errors.append(
                "mvp-wrapper-ps1-report-session-crash-json missing source_hints.owner_id=session"
            )

        elif source_hints.get("task_context") != "session":
            errors.append(
                "mvp-wrapper-ps1-report-session-crash-json missing source_hints.task_context=session"
            )

    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-crash",
            "--reset",
            "--task-id",
            "task-wrapper-recover-session-crash",
            "--db",
            "target/mvp/recover-session-crash.db",
            "--output",
            "target/mvp/recover-session-crash.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-recover-session-crash-seed-json",
        "seed-crash",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-recover-session-crash-seed-json",
        expected_task_id="task-wrapper-recover-session-crash",
        expected_db_path="target/mvp/recover-session-crash.db",
        expected_output_path="target/mvp/recover-session-crash.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "report",
            "--db",
            "target/mvp/recover-session-crash.db",
            "--task-id",
            "task-wrapper-recover-session-crash",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-report-recover-session-crash-json",
        "report",
    )

    if result is not None:
        prepared = result.get("prepared") or []

        remembered_session = result.get("remembered_session") or {}

        source_hints = result.get("source_hints") or {}

        captured_output = str(result.get("captured_output") or "")

        if not prepared or prepared[0] != "report":
            errors.append(
                "mvp-wrapper-ps1-report-recover-session-crash-json missing prepared report"
            )

        elif "task-wrapper-recover-session-crash" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-recover-session-crash-json missing captured task task-wrapper-recover-session-crash"
            )

        elif "QueueForManualReview" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-recover-session-crash-json missing QueueForManualReview"
            )

        elif "worker=Uncertain" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-recover-session-crash-json missing worker=Uncertain"
            )

        elif "effect=Uncertain" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-recover-session-crash-json missing effect=Uncertain"
            )

        elif (
            not isinstance(remembered_session, dict)
            or remembered_session.get("task_id") != "task-wrapper-recover-session-crash"
        ):
            errors.append(
                "mvp-wrapper-ps1-report-recover-session-crash-json missing remembered session task-wrapper-recover-session-crash"
            )

        elif not isinstance(source_hints, dict) or source_hints.get("db") != "flag":
            errors.append(
                "mvp-wrapper-ps1-report-recover-session-crash-json missing source_hints.db=flag"
            )

        elif source_hints.get("output") != "session":
            errors.append(
                "mvp-wrapper-ps1-report-recover-session-crash-json missing source_hints.output=session"
            )

        elif source_hints.get("owner_id") != "session":
            errors.append(
                "mvp-wrapper-ps1-report-recover-session-crash-json missing source_hints.owner_id=session"
            )

        elif source_hints.get("task_context") != "flag":
            errors.append(
                "mvp-wrapper-ps1-report-recover-session-crash-json missing source_hints.task_context=flag"
            )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "recover",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-recover-session-crash-json",
        "recover",
    )

    if result is not None:
        prepared = result.get("prepared") or []

        remembered_session = result.get("remembered_session") or {}

        source_hints = result.get("source_hints") or {}

        captured_output = str(result.get("captured_output") or "")

        if not prepared or prepared[0] != "recover":
            errors.append(
                "mvp-wrapper-ps1-recover-session-crash-json missing prepared recover"
            )

        elif "task-wrapper-recover-session-crash" not in prepared:
            errors.append(
                "mvp-wrapper-ps1-recover-session-crash-json missing prepared task task-wrapper-recover-session-crash"
            )

        elif "recover blocked before expiry => true" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-recover-session-crash-json missing recover blocked before expiry"
            )

        elif "recover result => from=Uncertain" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-recover-session-crash-json missing from=Uncertain"
            )

        elif "worker=Succeeded" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-recover-session-crash-json missing worker=Succeeded"
            )

        elif "effect=Executed" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-recover-session-crash-json missing effect=Executed"
            )

        elif "completed=true" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-recover-session-crash-json missing completed=true"
            )

        elif (
            not isinstance(remembered_session, dict)
            or remembered_session.get("task_id") != "task-wrapper-recover-session-crash"
        ):
            errors.append(
                "mvp-wrapper-ps1-recover-session-crash-json missing remembered session task-wrapper-recover-session-crash"
            )

        elif not isinstance(source_hints, dict) or source_hints.get("db") != "session":
            errors.append(
                "mvp-wrapper-ps1-recover-session-crash-json missing source_hints.db=session"
            )

        elif source_hints.get("output") != "session":
            errors.append(
                "mvp-wrapper-ps1-recover-session-crash-json missing source_hints.output=session"
            )

        elif source_hints.get("owner_id") != "session":
            errors.append(
                "mvp-wrapper-ps1-recover-session-crash-json missing source_hints.owner_id=session"
            )

        elif source_hints.get("task_context") != "session":
            errors.append(
                "mvp-wrapper-ps1-recover-session-crash-json missing source_hints.task_context=session"
            )

    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-crash",
            "--reset",
            "--task-id",
            "task-wrapper-cmd-recover-session-crash",
            "--db",
            "target/mvp/cmd-recover-session-crash.db",
            "--output",
            "target/mvp/cmd-recover-session-crash.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-cmd-recover-session-crash-seed-json",
        "seed-crash",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-cmd-recover-session-crash-seed-json",
        expected_task_id="task-wrapper-cmd-recover-session-crash",
        expected_db_path="target/mvp/cmd-recover-session-crash.db",
        expected_output_path="target/mvp/cmd-recover-session-crash.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "report",
            "--db",
            "target/mvp/cmd-recover-session-crash.db",
            "--task-id",
            "task-wrapper-cmd-recover-session-crash",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-report-cmd-recover-session-crash-json",
        "report",
    )

    if result is not None:
        prepared = result.get("prepared") or []

        remembered_session = result.get("remembered_session") or {}

        source_hints = result.get("source_hints") or {}

        captured_output = str(result.get("captured_output") or "")

        if not prepared or prepared[0] != "report":
            errors.append(
                "mvp-wrapper-ps1-report-cmd-recover-session-crash-json missing prepared report"
            )

        elif "task-wrapper-cmd-recover-session-crash" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-cmd-recover-session-crash-json missing captured task task-wrapper-cmd-recover-session-crash"
            )

        elif "QueueForManualReview" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-cmd-recover-session-crash-json missing QueueForManualReview"
            )

        elif "worker=Uncertain" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-cmd-recover-session-crash-json missing worker=Uncertain"
            )

        elif "effect=Uncertain" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-cmd-recover-session-crash-json missing effect=Uncertain"
            )

        elif (
            not isinstance(remembered_session, dict)
            or remembered_session.get("task_id")
            != "task-wrapper-cmd-recover-session-crash"
        ):
            errors.append(
                "mvp-wrapper-ps1-report-cmd-recover-session-crash-json missing remembered session task-wrapper-cmd-recover-session-crash"
            )

        elif not isinstance(source_hints, dict) or source_hints.get("db") != "flag":
            errors.append(
                "mvp-wrapper-ps1-report-cmd-recover-session-crash-json missing source_hints.db=flag"
            )

        elif source_hints.get("output") != "session":
            errors.append(
                "mvp-wrapper-ps1-report-cmd-recover-session-crash-json missing source_hints.output=session"
            )

        elif source_hints.get("owner_id") != "session":
            errors.append(
                "mvp-wrapper-ps1-report-cmd-recover-session-crash-json missing source_hints.owner_id=session"
            )

        elif source_hints.get("task_context") != "flag":
            errors.append(
                "mvp-wrapper-ps1-report-cmd-recover-session-crash-json missing source_hints.task_context=flag"
            )

    result = assert_command_json_result(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "recover", "--json"],
        errors,
        "mvp-wrapper-cmd-recover-session-crash-json",
        "recover",
    )

    if result is not None:
        prepared = result.get("prepared") or []

        remembered_session = result.get("remembered_session") or {}

        source_hints = result.get("source_hints") or {}

        captured_output = str(result.get("captured_output") or "")

        if not prepared or prepared[0] != "recover":
            errors.append(
                "mvp-wrapper-cmd-recover-session-crash-json missing prepared recover"
            )

        elif "task-wrapper-cmd-recover-session-crash" not in prepared:
            errors.append(
                "mvp-wrapper-cmd-recover-session-crash-json missing prepared task task-wrapper-cmd-recover-session-crash"
            )

        elif "recover blocked before expiry => true" not in captured_output:
            errors.append(
                "mvp-wrapper-cmd-recover-session-crash-json missing recover blocked before expiry"
            )

        elif "recover result => from=Uncertain" not in captured_output:
            errors.append(
                "mvp-wrapper-cmd-recover-session-crash-json missing from=Uncertain"
            )

        elif "worker=Succeeded" not in captured_output:
            errors.append(
                "mvp-wrapper-cmd-recover-session-crash-json missing worker=Succeeded"
            )

        elif "effect=Executed" not in captured_output:
            errors.append(
                "mvp-wrapper-cmd-recover-session-crash-json missing effect=Executed"
            )

        elif "completed=true" not in captured_output:
            errors.append(
                "mvp-wrapper-cmd-recover-session-crash-json missing completed=true"
            )

        elif (
            not isinstance(remembered_session, dict)
            or remembered_session.get("task_id")
            != "task-wrapper-cmd-recover-session-crash"
        ):
            errors.append(
                "mvp-wrapper-cmd-recover-session-crash-json missing remembered session task-wrapper-cmd-recover-session-crash"
            )

        elif not isinstance(source_hints, dict) or source_hints.get("db") != "session":
            errors.append(
                "mvp-wrapper-cmd-recover-session-crash-json missing source_hints.db=session"
            )

        elif source_hints.get("output") != "session":
            errors.append(
                "mvp-wrapper-cmd-recover-session-crash-json missing source_hints.output=session"
            )

        elif source_hints.get("owner_id") != "session":
            errors.append(
                "mvp-wrapper-cmd-recover-session-crash-json missing source_hints.owner_id=session"
            )

        elif source_hints.get("task_context") != "session":
            errors.append(
                "mvp-wrapper-cmd-recover-session-crash-json missing source_hints.task_context=session"
            )

    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-failed",
            "--reset",
            "--task-id",
            "task-wrapper-retry-session",
            "--db",
            "target/mvp/retry-session.db",
            "--output",
            "target/mvp/retry-session.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-retry-session-seed-failed-json",
        "seed-failed",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-retry-session-seed-failed-json",
        expected_task_id="task-wrapper-retry-session",
        expected_db_path="target/mvp/retry-session.db",
        expected_output_path="target/mvp/retry-session.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "report",
            "--db",
            "target/mvp/retry-session.db",
            "--task-id",
            "task-wrapper-retry-session",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-report-retry-session-json",
        "report",
    )

    if result is not None:
        prepared = result.get("prepared") or []

        remembered_session = result.get("remembered_session") or {}

        source_hints = result.get("source_hints") or {}

        captured_output = str(result.get("captured_output") or "")

        if not prepared or prepared[0] != "report":
            errors.append(
                "mvp-wrapper-ps1-report-retry-session-json missing prepared report"
            )

        elif "task-wrapper-retry-session" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-retry-session-json missing captured task task-wrapper-retry-session"
            )

        elif "RetryEligible" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-retry-session-json missing RetryEligible"
            )

        elif "worker=Failed" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-retry-session-json missing worker=Failed"
            )

        elif "effect=Prepared" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-retry-session-json missing effect=Prepared"
            )

        elif (
            not isinstance(remembered_session, dict)
            or remembered_session.get("task_id") != "task-wrapper-retry-session"
        ):
            errors.append(
                "mvp-wrapper-ps1-report-retry-session-json missing remembered session task-wrapper-retry-session"
            )

        elif not isinstance(source_hints, dict) or source_hints.get("db") != "flag":
            errors.append(
                "mvp-wrapper-ps1-report-retry-session-json missing source_hints.db=flag"
            )

        elif source_hints.get("output") != "session":
            errors.append(
                "mvp-wrapper-ps1-report-retry-session-json missing source_hints.output=session"
            )

        elif source_hints.get("owner_id") != "session":
            errors.append(
                "mvp-wrapper-ps1-report-retry-session-json missing source_hints.owner_id=session"
            )

        elif source_hints.get("task_context") != "flag":
            errors.append(
                "mvp-wrapper-ps1-report-retry-session-json missing source_hints.task_context=flag"
            )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "retry",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-retry-session-json",
        "retry",
    )

    if result is not None:
        prepared = result.get("prepared") or []

        remembered_session = result.get("remembered_session") or {}

        source_hints = result.get("source_hints") or {}

        captured_output = str(result.get("captured_output") or "")

        if not prepared or prepared[0] != "retry":
            errors.append("mvp-wrapper-ps1-retry-session-json missing prepared retry")

        elif "task-wrapper-retry-session" not in prepared:
            errors.append(
                "mvp-wrapper-ps1-retry-session-json missing prepared task task-wrapper-retry-session"
            )

        elif "retry blocked before expiry => true" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-retry-session-json missing retry blocked before expiry"
            )

        elif "worker=Succeeded" not in captured_output:
            errors.append("mvp-wrapper-ps1-retry-session-json missing worker=Succeeded")

        elif "effect=Executed" not in captured_output:
            errors.append("mvp-wrapper-ps1-retry-session-json missing effect=Executed")

        elif "completed=true" not in captured_output:
            errors.append("mvp-wrapper-ps1-retry-session-json missing completed=true")

        elif (
            not isinstance(remembered_session, dict)
            or remembered_session.get("task_id") != "task-wrapper-retry-session"
        ):
            errors.append(
                "mvp-wrapper-ps1-retry-session-json missing remembered session task-wrapper-retry-session"
            )

        elif not isinstance(source_hints, dict) or source_hints.get("db") != "session":
            errors.append(
                "mvp-wrapper-ps1-retry-session-json missing source_hints.db=session"
            )

        elif source_hints.get("output") != "session":
            errors.append(
                "mvp-wrapper-ps1-retry-session-json missing source_hints.output=session"
            )

        elif source_hints.get("owner_id") != "session":
            errors.append(
                "mvp-wrapper-ps1-retry-session-json missing source_hints.owner_id=session"
            )

        elif source_hints.get("task_context") != "session":
            errors.append(
                "mvp-wrapper-ps1-retry-session-json missing source_hints.task_context=session"
            )

    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-failed",
            "--reset",
            "--task-id",
            "task-wrapper-cmd-retry-session",
            "--db",
            "target/mvp/cmd-retry-session.db",
            "--output",
            "target/mvp/cmd-retry-session.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-cmd-retry-session-seed-json",
        "seed-failed",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-cmd-retry-session-seed-json",
        expected_task_id="task-wrapper-cmd-retry-session",
        expected_db_path="target/mvp/cmd-retry-session.db",
        expected_output_path="target/mvp/cmd-retry-session.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "report",
            "--db",
            "target/mvp/cmd-retry-session.db",
            "--task-id",
            "task-wrapper-cmd-retry-session",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-report-cmd-retry-session-json",
        "report",
    )

    if result is not None:
        prepared = result.get("prepared") or []

        remembered_session = result.get("remembered_session") or {}

        source_hints = result.get("source_hints") or {}

        captured_output = str(result.get("captured_output") or "")

        if not prepared or prepared[0] != "report":
            errors.append(
                "mvp-wrapper-ps1-report-cmd-retry-session-json missing prepared report"
            )

        elif "task-wrapper-cmd-retry-session" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-cmd-retry-session-json missing captured task task-wrapper-cmd-retry-session"
            )

        elif "RetryEligible" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-cmd-retry-session-json missing RetryEligible"
            )

        elif "worker=Failed" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-cmd-retry-session-json missing worker=Failed"
            )

        elif "effect=Prepared" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-cmd-retry-session-json missing effect=Prepared"
            )

        elif (
            not isinstance(remembered_session, dict)
            or remembered_session.get("task_id") != "task-wrapper-cmd-retry-session"
        ):
            errors.append(
                "mvp-wrapper-ps1-report-cmd-retry-session-json missing remembered session task-wrapper-cmd-retry-session"
            )

        elif not isinstance(source_hints, dict) or source_hints.get("db") != "flag":
            errors.append(
                "mvp-wrapper-ps1-report-cmd-retry-session-json missing source_hints.db=flag"
            )

        elif source_hints.get("output") != "session":
            errors.append(
                "mvp-wrapper-ps1-report-cmd-retry-session-json missing source_hints.output=session"
            )

        elif source_hints.get("owner_id") != "session":
            errors.append(
                "mvp-wrapper-ps1-report-cmd-retry-session-json missing source_hints.owner_id=session"
            )

        elif source_hints.get("task_context") != "flag":
            errors.append(
                "mvp-wrapper-ps1-report-cmd-retry-session-json missing source_hints.task_context=flag"
            )

    result = assert_command_json_result(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "retry", "--json"],
        errors,
        "mvp-wrapper-cmd-retry-session-json",
        "retry",
    )

    if result is not None:
        prepared = result.get("prepared") or []

        remembered_session = result.get("remembered_session") or {}

        source_hints = result.get("source_hints") or {}

        captured_output = str(result.get("captured_output") or "")

        if not prepared or prepared[0] != "retry":
            errors.append("mvp-wrapper-cmd-retry-session-json missing prepared retry")

        elif "task-wrapper-cmd-retry-session" not in prepared:
            errors.append(
                "mvp-wrapper-cmd-retry-session-json missing prepared task task-wrapper-cmd-retry-session"
            )

        elif "retry blocked before expiry => true" not in captured_output:
            errors.append(
                "mvp-wrapper-cmd-retry-session-json missing retry blocked before expiry"
            )

        elif "worker=Succeeded" not in captured_output:
            errors.append("mvp-wrapper-cmd-retry-session-json missing worker=Succeeded")

        elif "effect=Executed" not in captured_output:
            errors.append("mvp-wrapper-cmd-retry-session-json missing effect=Executed")

        elif "completed=true" not in captured_output:
            errors.append("mvp-wrapper-cmd-retry-session-json missing completed=true")

        elif (
            not isinstance(remembered_session, dict)
            or remembered_session.get("task_id") != "task-wrapper-cmd-retry-session"
        ):
            errors.append(
                "mvp-wrapper-cmd-retry-session-json missing remembered session task-wrapper-cmd-retry-session"
            )

        elif not isinstance(source_hints, dict) or source_hints.get("db") != "session":
            errors.append(
                "mvp-wrapper-cmd-retry-session-json missing source_hints.db=session"
            )

        elif source_hints.get("output") != "session":
            errors.append(
                "mvp-wrapper-cmd-retry-session-json missing source_hints.output=session"
            )

        elif source_hints.get("owner_id") != "session":
            errors.append(
                "mvp-wrapper-cmd-retry-session-json missing source_hints.owner_id=session"
            )

        elif source_hints.get("task_context") != "session":
            errors.append(
                "mvp-wrapper-cmd-retry-session-json missing source_hints.task_context=session"
            )

    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-failed",
            "--reset",
            "--task-id",
            "task-wrapper-status-failed-session",
            "--db",
            "target/mvp/status-failed-session.db",
            "--output",
            "target/mvp/status-failed-session.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-status-failed-session-seed-failed-json",
        "seed-failed",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-status-failed-session-seed-failed-json",
        expected_task_id="task-wrapper-status-failed-session",
        expected_db_path="target/mvp/status-failed-session.db",
        expected_output_path="target/mvp/status-failed-session.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "report",
            "--db",
            "target/mvp/status-failed-session.db",
            "--task-id",
            "task-wrapper-status-failed-session",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-report-status-failed-session-json",
        "report",
    )

    if result is not None:
        prepared = result.get("prepared") or []

        remembered_session = result.get("remembered_session") or {}

        source_hints = result.get("source_hints") or {}

        captured_output = str(result.get("captured_output") or "")

        if not prepared or prepared[0] != "report":
            errors.append(
                "mvp-wrapper-ps1-report-status-failed-session-json missing prepared report"
            )

        elif "task-wrapper-status-failed-session" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-status-failed-session-json missing captured task task-wrapper-status-failed-session"
            )

        elif "RetryEligible" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-status-failed-session-json missing RetryEligible"
            )

        elif "worker=Failed" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-status-failed-session-json missing worker=Failed"
            )

        elif "effect=Prepared" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-status-failed-session-json missing effect=Prepared"
            )

        elif (
            not isinstance(remembered_session, dict)
            or remembered_session.get("task_id") != "task-wrapper-status-failed-session"
        ):
            errors.append(
                "mvp-wrapper-ps1-report-status-failed-session-json missing remembered session task-wrapper-status-failed-session"
            )

        elif not isinstance(source_hints, dict) or source_hints.get("db") != "flag":
            errors.append(
                "mvp-wrapper-ps1-report-status-failed-session-json missing source_hints.db=flag"
            )

        elif source_hints.get("output") != "session":
            errors.append(
                "mvp-wrapper-ps1-report-status-failed-session-json missing source_hints.output=session"
            )

        elif source_hints.get("owner_id") != "session":
            errors.append(
                "mvp-wrapper-ps1-report-status-failed-session-json missing source_hints.owner_id=session"
            )

        elif source_hints.get("task_context") != "flag":
            errors.append(
                "mvp-wrapper-ps1-report-status-failed-session-json missing source_hints.task_context=flag"
            )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "status",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-status-failed-session-json",
        "status",
    )

    if result is not None:
        prepared = result.get("prepared") or []

        remembered_session = result.get("remembered_session") or {}

        source_hints = result.get("source_hints") or {}

        captured_output = str(result.get("captured_output") or "")

        if not prepared or prepared[0] != "status":
            errors.append(
                "mvp-wrapper-ps1-status-failed-session-json missing prepared status"
            )

        elif "task-wrapper-status-failed-session" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-status-failed-session-json missing captured task task-wrapper-status-failed-session"
            )

        elif "RetryEligible" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-status-failed-session-json missing RetryEligible"
            )

        elif "worker=Failed" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-status-failed-session-json missing worker=Failed"
            )

        elif "effect=Prepared" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-status-failed-session-json missing effect=Prepared"
            )

        elif (
            not isinstance(remembered_session, dict)
            or remembered_session.get("task_id") != "task-wrapper-status-failed-session"
        ):
            errors.append(
                "mvp-wrapper-ps1-status-failed-session-json missing remembered session task-wrapper-status-failed-session"
            )

        elif not isinstance(source_hints, dict) or source_hints.get("db") != "session":
            errors.append(
                "mvp-wrapper-ps1-status-failed-session-json missing source_hints.db=session"
            )

        elif source_hints.get("output") != "session":
            errors.append(
                "mvp-wrapper-ps1-status-failed-session-json missing source_hints.output=session"
            )

        elif source_hints.get("owner_id") != "session":
            errors.append(
                "mvp-wrapper-ps1-status-failed-session-json missing source_hints.owner_id=session"
            )

        elif source_hints.get("task_context") != "session":
            errors.append(
                "mvp-wrapper-ps1-status-failed-session-json missing source_hints.task_context=session"
            )

    result = assert_command_json_result(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "status", "--json"],
        errors,
        "mvp-wrapper-cmd-status-failed-session-json",
        "status",
    )

    if result is not None:
        prepared = result.get("prepared") or []

        remembered_session = result.get("remembered_session") or {}

        source_hints = result.get("source_hints") or {}

        captured_output = str(result.get("captured_output") or "")

        if not prepared or prepared[0] != "status":
            errors.append(
                "mvp-wrapper-cmd-status-failed-session-json missing prepared status"
            )

        elif "task-wrapper-status-failed-session" not in captured_output:
            errors.append(
                "mvp-wrapper-cmd-status-failed-session-json missing captured task task-wrapper-status-failed-session"
            )

        elif "RetryEligible" not in captured_output:
            errors.append(
                "mvp-wrapper-cmd-status-failed-session-json missing RetryEligible"
            )

        elif "worker=Failed" not in captured_output:
            errors.append(
                "mvp-wrapper-cmd-status-failed-session-json missing worker=Failed"
            )

        elif "effect=Prepared" not in captured_output:
            errors.append(
                "mvp-wrapper-cmd-status-failed-session-json missing effect=Prepared"
            )

        elif (
            not isinstance(remembered_session, dict)
            or remembered_session.get("task_id") != "task-wrapper-status-failed-session"
        ):
            errors.append(
                "mvp-wrapper-cmd-status-failed-session-json missing remembered session task-wrapper-status-failed-session"
            )

        elif not isinstance(source_hints, dict) or source_hints.get("db") != "session":
            errors.append(
                "mvp-wrapper-cmd-status-failed-session-json missing source_hints.db=session"
            )

        elif source_hints.get("output") != "session":
            errors.append(
                "mvp-wrapper-cmd-status-failed-session-json missing source_hints.output=session"
            )

        elif source_hints.get("owner_id") != "session":
            errors.append(
                "mvp-wrapper-cmd-status-failed-session-json missing source_hints.owner_id=session"
            )

        elif source_hints.get("task_context") != "session":
            errors.append(
                "mvp-wrapper-cmd-status-failed-session-json missing source_hints.task_context=session"
            )

    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-failed",
            "--reset",
            "--task-id",
            "task-wrapper-report-failed-session",
            "--db",
            "target/mvp/report-failed-session.db",
            "--output",
            "target/mvp/report-failed-session.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-report-failed-session-seed-failed-json",
        "seed-failed",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-report-failed-session-seed-failed-json",
        expected_task_id="task-wrapper-report-failed-session",
        expected_db_path="target/mvp/report-failed-session.db",
        expected_output_path="target/mvp/report-failed-session.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "report",
            "--db",
            "target/mvp/report-failed-session.db",
            "--task-id",
            "task-wrapper-report-failed-session",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-report-report-failed-session-json",
        "report",
    )

    if result is not None:
        prepared = result.get("prepared") or []

        remembered_session = result.get("remembered_session") or {}

        source_hints = result.get("source_hints") or {}

        captured_output = str(result.get("captured_output") or "")

        if not prepared or prepared[0] != "report":
            errors.append(
                "mvp-wrapper-ps1-report-report-failed-session-json missing prepared report"
            )

        elif "task-wrapper-report-failed-session" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-report-failed-session-json missing captured task task-wrapper-report-failed-session"
            )

        elif "RetryEligible" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-report-failed-session-json missing RetryEligible"
            )

        elif "worker=Failed" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-report-failed-session-json missing worker=Failed"
            )

        elif "effect=Prepared" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-report-failed-session-json missing effect=Prepared"
            )

        elif (
            not isinstance(remembered_session, dict)
            or remembered_session.get("task_id") != "task-wrapper-report-failed-session"
        ):
            errors.append(
                "mvp-wrapper-ps1-report-report-failed-session-json missing remembered session task-wrapper-report-failed-session"
            )

        elif not isinstance(source_hints, dict) or source_hints.get("db") != "flag":
            errors.append(
                "mvp-wrapper-ps1-report-report-failed-session-json missing source_hints.db=flag"
            )

        elif source_hints.get("output") != "session":
            errors.append(
                "mvp-wrapper-ps1-report-report-failed-session-json missing source_hints.output=session"
            )

        elif source_hints.get("owner_id") != "session":
            errors.append(
                "mvp-wrapper-ps1-report-report-failed-session-json missing source_hints.owner_id=session"
            )

        elif source_hints.get("task_context") != "flag":
            errors.append(
                "mvp-wrapper-ps1-report-report-failed-session-json missing source_hints.task_context=flag"
            )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "report",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-report-failed-session-json",
        "report",
    )

    if result is not None:
        prepared = result.get("prepared") or []

        remembered_session = result.get("remembered_session") or {}

        source_hints = result.get("source_hints") or {}

        captured_output = str(result.get("captured_output") or "")

        if not prepared or prepared[0] != "report":
            errors.append(
                "mvp-wrapper-ps1-report-failed-session-json missing prepared report"
            )

        elif "task-wrapper-report-failed-session" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-failed-session-json missing captured task task-wrapper-report-failed-session"
            )

        elif "RetryEligible" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-failed-session-json missing RetryEligible"
            )

        elif "worker=Failed" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-failed-session-json missing worker=Failed"
            )

        elif "effect=Prepared" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-failed-session-json missing effect=Prepared"
            )

        elif (
            not isinstance(remembered_session, dict)
            or remembered_session.get("task_id") != "task-wrapper-report-failed-session"
        ):
            errors.append(
                "mvp-wrapper-ps1-report-failed-session-json missing remembered session task-wrapper-report-failed-session"
            )

        elif not isinstance(source_hints, dict) or source_hints.get("db") != "session":
            errors.append(
                "mvp-wrapper-ps1-report-failed-session-json missing source_hints.db=session"
            )

        elif source_hints.get("output") != "session":
            errors.append(
                "mvp-wrapper-ps1-report-failed-session-json missing source_hints.output=session"
            )

        elif source_hints.get("owner_id") != "session":
            errors.append(
                "mvp-wrapper-ps1-report-failed-session-json missing source_hints.owner_id=session"
            )

        elif source_hints.get("task_context") != "session":
            errors.append(
                "mvp-wrapper-ps1-report-failed-session-json missing source_hints.task_context=session"
            )

    result = assert_command_json_result(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "report", "--json"],
        errors,
        "mvp-wrapper-cmd-report-failed-session-json",
        "report",
    )

    if result is not None:
        prepared = result.get("prepared") or []

        remembered_session = result.get("remembered_session") or {}

        source_hints = result.get("source_hints") or {}

        captured_output = str(result.get("captured_output") or "")

        if not prepared or prepared[0] != "report":
            errors.append(
                "mvp-wrapper-cmd-report-failed-session-json missing prepared report"
            )

        elif "task-wrapper-report-failed-session" not in captured_output:
            errors.append(
                "mvp-wrapper-cmd-report-failed-session-json missing captured task task-wrapper-report-failed-session"
            )

        elif "RetryEligible" not in captured_output:
            errors.append(
                "mvp-wrapper-cmd-report-failed-session-json missing RetryEligible"
            )

        elif "worker=Failed" not in captured_output:
            errors.append(
                "mvp-wrapper-cmd-report-failed-session-json missing worker=Failed"
            )

        elif "effect=Prepared" not in captured_output:
            errors.append(
                "mvp-wrapper-cmd-report-failed-session-json missing effect=Prepared"
            )

        elif (
            not isinstance(remembered_session, dict)
            or remembered_session.get("task_id") != "task-wrapper-report-failed-session"
        ):
            errors.append(
                "mvp-wrapper-cmd-report-failed-session-json missing remembered session task-wrapper-report-failed-session"
            )

        elif not isinstance(source_hints, dict) or source_hints.get("db") != "session":
            errors.append(
                "mvp-wrapper-cmd-report-failed-session-json missing source_hints.db=session"
            )

        elif source_hints.get("output") != "session":
            errors.append(
                "mvp-wrapper-cmd-report-failed-session-json missing source_hints.output=session"
            )

        elif source_hints.get("owner_id") != "session":
            errors.append(
                "mvp-wrapper-cmd-report-failed-session-json missing source_hints.owner_id=session"
            )

        elif source_hints.get("task_context") != "session":
            errors.append(
                "mvp-wrapper-cmd-report-failed-session-json missing source_hints.task_context=session"
            )

    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-failed",
            "--reset",
            "--task-id",
            "task-wrapper-session-failed",
            "--db",
            "target/mvp/session-failed.db",
            "--output",
            "target/mvp/session-failed.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-session-failed-seed-json",
        "seed-failed",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-session-failed-seed-json",
        expected_task_id="task-wrapper-session-failed",
        expected_db_path="target/mvp/session-failed.db",
        expected_output_path="target/mvp/session-failed.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "report",
            "--db",
            "target/mvp/session-failed.db",
            "--task-id",
            "task-wrapper-session-failed",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-report-session-failed-json",
        "report",
    )

    if result is not None:
        prepared = result.get("prepared") or []

        remembered_session = result.get("remembered_session") or {}

        source_hints = result.get("source_hints") or {}

        captured_output = str(result.get("captured_output") or "")

        if not prepared or prepared[0] != "report":
            errors.append(
                "mvp-wrapper-ps1-report-session-failed-json missing prepared report"
            )

        elif "task-wrapper-session-failed" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-session-failed-json missing captured task task-wrapper-session-failed"
            )

        elif "RetryEligible" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-session-failed-json missing RetryEligible"
            )

        elif "worker=Failed" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-session-failed-json missing worker=Failed"
            )

        elif "effect=Prepared" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-session-failed-json missing effect=Prepared"
            )

        elif (
            not isinstance(remembered_session, dict)
            or remembered_session.get("task_id") != "task-wrapper-session-failed"
        ):
            errors.append(
                "mvp-wrapper-ps1-report-session-failed-json missing remembered session task-wrapper-session-failed"
            )

        elif not isinstance(source_hints, dict) or source_hints.get("db") != "flag":
            errors.append(
                "mvp-wrapper-ps1-report-session-failed-json missing source_hints.db=flag"
            )

        elif source_hints.get("output") != "session":
            errors.append(
                "mvp-wrapper-ps1-report-session-failed-json missing source_hints.output=session"
            )

        elif source_hints.get("owner_id") != "session":
            errors.append(
                "mvp-wrapper-ps1-report-session-failed-json missing source_hints.owner_id=session"
            )

        elif source_hints.get("task_context") != "flag":
            errors.append(
                "mvp-wrapper-ps1-report-session-failed-json missing source_hints.task_context=flag"
            )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "session",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-session-failed-json",
        "session",
    )

    if result is not None:
        if result.get("task_id") != "task-wrapper-session-failed":
            errors.append(
                "mvp-wrapper-ps1-session-failed-json missing task_id=task-wrapper-session-failed"
            )

        elif result.get("effect_id") != "effect-task-wrapper-session-failed":
            errors.append(
                "mvp-wrapper-ps1-session-failed-json missing effect_id=effect-task-wrapper-session-failed"
            )

        elif result.get("db") != "target/mvp/session-failed.db":
            errors.append(
                "mvp-wrapper-ps1-session-failed-json missing db=target/mvp/session-failed.db"
            )

        elif result.get("output") != "target/mvp/session-failed.txt":
            errors.append(
                "mvp-wrapper-ps1-session-failed-json missing output=target/mvp/session-failed.txt"
            )

        elif result.get("owner_id") != "safeclaw-mvp":
            errors.append(
                "mvp-wrapper-ps1-session-failed-json missing owner_id=safeclaw-mvp"
            )

    result = assert_command_json_result(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "session", "--json"],
        errors,
        "mvp-wrapper-cmd-session-failed-json",
        "session",
    )

    if result is not None:
        if result.get("task_id") != "task-wrapper-session-failed":
            errors.append(
                "mvp-wrapper-cmd-session-failed-json missing task_id=task-wrapper-session-failed"
            )

        elif result.get("effect_id") != "effect-task-wrapper-session-failed":
            errors.append(
                "mvp-wrapper-cmd-session-failed-json missing effect_id=effect-task-wrapper-session-failed"
            )

        elif result.get("db") != "target/mvp/session-failed.db":
            errors.append(
                "mvp-wrapper-cmd-session-failed-json missing db=target/mvp/session-failed.db"
            )

        elif result.get("output") != "target/mvp/session-failed.txt":
            errors.append(
                "mvp-wrapper-cmd-session-failed-json missing output=target/mvp/session-failed.txt"
            )

        elif result.get("owner_id") != "safeclaw-mvp":
            errors.append(
                "mvp-wrapper-cmd-session-failed-json missing owner_id=safeclaw-mvp"
            )

    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-failed",
            "--reset",
            "--task-id",
            "task-wrapper-sessions-failed",
            "--db",
            "target/mvp/sessions-failed.db",
            "--output",
            "target/mvp/sessions-failed.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-sessions-failed-seed-json",
        "seed-failed",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-sessions-failed-seed-json",
        expected_task_id="task-wrapper-sessions-failed",
        expected_db_path="target/mvp/sessions-failed.db",
        expected_output_path="target/mvp/sessions-failed.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "report",
            "--db",
            "target/mvp/sessions-failed.db",
            "--task-id",
            "task-wrapper-sessions-failed",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-report-sessions-failed-json",
        "report",
    )

    if result is not None:
        prepared = result.get("prepared") or []

        remembered_session = result.get("remembered_session") or {}

        source_hints = result.get("source_hints") or {}

        captured_output = str(result.get("captured_output") or "")

        if not prepared or prepared[0] != "report":
            errors.append(
                "mvp-wrapper-ps1-report-sessions-failed-json missing prepared report"
            )

        elif "task-wrapper-sessions-failed" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-sessions-failed-json missing captured task task-wrapper-sessions-failed"
            )

        elif "RetryEligible" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-sessions-failed-json missing RetryEligible"
            )

        elif "worker=Failed" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-sessions-failed-json missing worker=Failed"
            )

        elif "effect=Prepared" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-sessions-failed-json missing effect=Prepared"
            )

        elif (
            not isinstance(remembered_session, dict)
            or remembered_session.get("task_id") != "task-wrapper-sessions-failed"
        ):
            errors.append(
                "mvp-wrapper-ps1-report-sessions-failed-json missing remembered session task-wrapper-sessions-failed"
            )

        elif not isinstance(source_hints, dict) or source_hints.get("db") != "flag":
            errors.append(
                "mvp-wrapper-ps1-report-sessions-failed-json missing source_hints.db=flag"
            )

        elif source_hints.get("output") != "session":
            errors.append(
                "mvp-wrapper-ps1-report-sessions-failed-json missing source_hints.output=session"
            )

        elif source_hints.get("owner_id") != "session":
            errors.append(
                "mvp-wrapper-ps1-report-sessions-failed-json missing source_hints.owner_id=session"
            )

        elif source_hints.get("task_context") != "flag":
            errors.append(
                "mvp-wrapper-ps1-report-sessions-failed-json missing source_hints.task_context=flag"
            )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "sessions",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-sessions-failed-json",
        "sessions",
    )

    if result is not None:
        rows = result.get("rows") or []

        current_session = result.get("current_session") or {}

        if result.get("db") != "target/mvp/sessions-failed.db":
            errors.append(
                "mvp-wrapper-ps1-sessions-failed-json missing db=target/mvp/sessions-failed.db"
            )

        elif result.get("db_source") != "session":
            errors.append(
                "mvp-wrapper-ps1-sessions-failed-json missing db_source=session"
            )

        elif result.get("limit") != 5:
            errors.append("mvp-wrapper-ps1-sessions-failed-json missing limit=5")

        elif (
            not isinstance(current_session, dict)
            or current_session.get("task_id") != "task-wrapper-sessions-failed"
        ):
            errors.append(
                "mvp-wrapper-ps1-sessions-failed-json missing current_session task-wrapper-sessions-failed"
            )

        elif current_session.get("effect_id") != "effect-task-wrapper-sessions-failed":
            errors.append(
                "mvp-wrapper-ps1-sessions-failed-json missing current_session effect-task-wrapper-sessions-failed"
            )

        elif current_session.get("db") != "target/mvp/sessions-failed.db":
            errors.append(
                "mvp-wrapper-ps1-sessions-failed-json missing current_session db=target/mvp/sessions-failed.db"
            )

        elif current_session.get("output") != "target/mvp/sessions-failed.txt":
            errors.append(
                "mvp-wrapper-ps1-sessions-failed-json missing current_session output=target/mvp/sessions-failed.txt"
            )

        elif current_session.get("owner_id") != "safeclaw-mvp":
            errors.append(
                "mvp-wrapper-ps1-sessions-failed-json missing current_session owner_id=safeclaw-mvp"
            )

        elif not rows or rows[0].get("task_id") != "task-wrapper-sessions-failed":
            errors.append(
                "mvp-wrapper-ps1-sessions-failed-json missing rows[0] task-wrapper-sessions-failed"
            )

        elif rows[0].get("effect_id") != "effect-task-wrapper-sessions-failed":
            errors.append(
                "mvp-wrapper-ps1-sessions-failed-json missing rows[0] effect-task-wrapper-sessions-failed"
            )

        elif rows[0].get("worker_state") != "failed":
            errors.append(
                "mvp-wrapper-ps1-sessions-failed-json missing rows[0] worker_state=failed"
            )

        elif rows[0].get("effect_status") != "prepared":
            errors.append(
                "mvp-wrapper-ps1-sessions-failed-json missing rows[0] effect_status=prepared"
            )

        elif rows[0].get("next_action") != "retry":
            errors.append(
                "mvp-wrapper-ps1-sessions-failed-json missing rows[0] next_action=retry"
            )

        elif rows[0].get("coordination_summary") != "retry_now":
            errors.append(
                "mvp-wrapper-ps1-sessions-failed-json missing rows[0] coordination_summary=retry_now"
            )

        elif rows[0].get("current") is not True:
            errors.append(
                "mvp-wrapper-ps1-sessions-failed-json missing rows[0] current=true"
            )

    result = assert_command_json_result(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "sessions", "--json"],
        errors,
        "mvp-wrapper-cmd-sessions-failed-json",
        "sessions",
    )

    if result is not None:
        rows = result.get("rows") or []

        current_session = result.get("current_session") or {}

        if result.get("db") != "target/mvp/sessions-failed.db":
            errors.append(
                "mvp-wrapper-cmd-sessions-failed-json missing db=target/mvp/sessions-failed.db"
            )

        elif result.get("db_source") != "session":
            errors.append(
                "mvp-wrapper-cmd-sessions-failed-json missing db_source=session"
            )

        elif result.get("limit") != 5:
            errors.append("mvp-wrapper-cmd-sessions-failed-json missing limit=5")

        elif (
            not isinstance(current_session, dict)
            or current_session.get("task_id") != "task-wrapper-sessions-failed"
        ):
            errors.append(
                "mvp-wrapper-cmd-sessions-failed-json missing current_session task-wrapper-sessions-failed"
            )

        elif current_session.get("effect_id") != "effect-task-wrapper-sessions-failed":
            errors.append(
                "mvp-wrapper-cmd-sessions-failed-json missing current_session effect-task-wrapper-sessions-failed"
            )

        elif current_session.get("db") != "target/mvp/sessions-failed.db":
            errors.append(
                "mvp-wrapper-cmd-sessions-failed-json missing current_session db=target/mvp/sessions-failed.db"
            )

        elif current_session.get("output") != "target/mvp/sessions-failed.txt":
            errors.append(
                "mvp-wrapper-cmd-sessions-failed-json missing current_session output=target/mvp/sessions-failed.txt"
            )

        elif current_session.get("owner_id") != "safeclaw-mvp":
            errors.append(
                "mvp-wrapper-cmd-sessions-failed-json missing current_session owner_id=safeclaw-mvp"
            )

        elif not rows or rows[0].get("task_id") != "task-wrapper-sessions-failed":
            errors.append(
                "mvp-wrapper-cmd-sessions-failed-json missing rows[0] task-wrapper-sessions-failed"
            )

        elif rows[0].get("effect_id") != "effect-task-wrapper-sessions-failed":
            errors.append(
                "mvp-wrapper-cmd-sessions-failed-json missing rows[0] effect-task-wrapper-sessions-failed"
            )

        elif rows[0].get("worker_state") != "failed":
            errors.append(
                "mvp-wrapper-cmd-sessions-failed-json missing rows[0] worker_state=failed"
            )

        elif rows[0].get("effect_status") != "prepared":
            errors.append(
                "mvp-wrapper-cmd-sessions-failed-json missing rows[0] effect_status=prepared"
            )

        elif rows[0].get("next_action") != "retry":
            errors.append(
                "mvp-wrapper-cmd-sessions-failed-json missing rows[0] next_action=retry"
            )

        elif rows[0].get("coordination_summary") != "retry_now":
            errors.append(
                "mvp-wrapper-cmd-sessions-failed-json missing rows[0] coordination_summary=retry_now"
            )

        elif rows[0].get("current") is not True:
            errors.append(
                "mvp-wrapper-cmd-sessions-failed-json missing rows[0] current=true"
            )

    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-failed",
            "--reset",
            "--task-id",
            "task-wrapper-status-explicit-failed",
            "--db",
            "target/mvp/status-explicit-failed.db",
            "--output",
            "target/mvp/status-explicit-failed.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-status-explicit-failed-seed-json",
        "seed-failed",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-status-explicit-failed-seed-json",
        expected_task_id="task-wrapper-status-explicit-failed",
        expected_db_path="target/mvp/status-explicit-failed.db",
        expected_output_path="target/mvp/status-explicit-failed.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "status",
            "--db",
            "target/mvp/status-explicit-failed.db",
            "--task-id",
            "task-wrapper-status-explicit-failed",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-status-explicit-failed-json",
        "status",
    )

    if result is not None:
        prepared = result.get("prepared") or []

        remembered_session = result.get("remembered_session") or {}

        source_hints = result.get("source_hints") or {}

        captured_output = str(result.get("captured_output") or "")

        if not prepared or prepared[0] != "status":
            errors.append(
                "mvp-wrapper-ps1-status-explicit-failed-json missing prepared status"
            )

        elif "task-wrapper-status-explicit-failed" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-status-explicit-failed-json missing captured task task-wrapper-status-explicit-failed"
            )

        elif "RetryEligible" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-status-explicit-failed-json missing RetryEligible"
            )

        elif "worker=Failed" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-status-explicit-failed-json missing worker=Failed"
            )

        elif "effect=Prepared" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-status-explicit-failed-json missing effect=Prepared"
            )

        elif (
            not isinstance(remembered_session, dict)
            or remembered_session.get("task_id")
            != "task-wrapper-status-explicit-failed"
        ):
            errors.append(
                "mvp-wrapper-ps1-status-explicit-failed-json missing remembered session task-wrapper-status-explicit-failed"
            )

        elif not isinstance(source_hints, dict) or source_hints.get("db") != "flag":
            errors.append(
                "mvp-wrapper-ps1-status-explicit-failed-json missing source_hints.db=flag"
            )

        elif source_hints.get("output") != "session":
            errors.append(
                "mvp-wrapper-ps1-status-explicit-failed-json missing source_hints.output=session"
            )

        elif source_hints.get("owner_id") != "session":
            errors.append(
                "mvp-wrapper-ps1-status-explicit-failed-json missing source_hints.owner_id=session"
            )

        elif source_hints.get("task_context") != "flag":
            errors.append(
                "mvp-wrapper-ps1-status-explicit-failed-json missing source_hints.task_context=flag"
            )

    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-failed",
            "--reset",
            "--task-id",
            "task-wrapper-report-explicit-failed",
            "--db",
            "target/mvp/report-explicit-failed.db",
            "--output",
            "target/mvp/report-explicit-failed.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-report-explicit-failed-seed-json",
        "seed-failed",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-report-explicit-failed-seed-json",
        expected_task_id="task-wrapper-report-explicit-failed",
        expected_db_path="target/mvp/report-explicit-failed.db",
        expected_output_path="target/mvp/report-explicit-failed.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "report",
            "--db",
            "target/mvp/report-explicit-failed.db",
            "--task-id",
            "task-wrapper-report-explicit-failed",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-report-explicit-failed-json",
        "report",
    )

    if result is not None:
        prepared = result.get("prepared") or []

        remembered_session = result.get("remembered_session") or {}

        source_hints = result.get("source_hints") or {}

        captured_output = str(result.get("captured_output") or "")

        if not prepared or prepared[0] != "report":
            errors.append(
                "mvp-wrapper-ps1-report-explicit-failed-json missing prepared report"
            )

        elif "task-wrapper-report-explicit-failed" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-explicit-failed-json missing captured task task-wrapper-report-explicit-failed"
            )

        elif "RetryEligible" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-explicit-failed-json missing RetryEligible"
            )

        elif "worker=Failed" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-explicit-failed-json missing worker=Failed"
            )

        elif "effect=Prepared" not in captured_output:
            errors.append(
                "mvp-wrapper-ps1-report-explicit-failed-json missing effect=Prepared"
            )

        elif (
            not isinstance(remembered_session, dict)
            or remembered_session.get("task_id")
            != "task-wrapper-report-explicit-failed"
        ):
            errors.append(
                "mvp-wrapper-ps1-report-explicit-failed-json missing remembered session task-wrapper-report-explicit-failed"
            )

        elif not isinstance(source_hints, dict) or source_hints.get("db") != "flag":
            errors.append(
                "mvp-wrapper-ps1-report-explicit-failed-json missing source_hints.db=flag"
            )

        elif source_hints.get("output") != "session":
            errors.append(
                "mvp-wrapper-ps1-report-explicit-failed-json missing source_hints.output=session"
            )

        elif source_hints.get("owner_id") != "session":
            errors.append(
                "mvp-wrapper-ps1-report-explicit-failed-json missing source_hints.owner_id=session"
            )

        elif source_hints.get("task_context") != "flag":
            errors.append(
                "mvp-wrapper-ps1-report-explicit-failed-json missing source_hints.task_context=flag"
            )

    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-failed",
            "--reset",
            "--task-id",
            "task-wrapper-cmd-status-explicit-failed",
            "--db",
            "target/mvp/cmd-status-explicit-failed.db",
            "--output",
            "target/mvp/cmd-status-explicit-failed.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-cmd-status-explicit-failed-seed-json",
        "seed-failed",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-cmd-status-explicit-failed-seed-json",
        expected_task_id="task-wrapper-cmd-status-explicit-failed",
        expected_db_path="target/mvp/cmd-status-explicit-failed.db",
        expected_output_path="target/mvp/cmd-status-explicit-failed.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )

    result = assert_command_json_result(
        [
            "cmd",
            "/c",
            "tools\mvp\safeclaw_mvp.cmd",
            "status",
            "--db",
            "target/mvp/cmd-status-explicit-failed.db",
            "--task-id",
            "task-wrapper-cmd-status-explicit-failed",
            "--json",
        ],
        errors,
        "mvp-wrapper-cmd-status-explicit-failed-json",
        "status",
    )

    if result is not None:
        prepared = result.get("prepared") or []

        remembered_session = result.get("remembered_session") or {}

        source_hints = result.get("source_hints") or {}

        captured_output = str(result.get("captured_output") or "")

        if not prepared or prepared[0] != "status":
            errors.append(
                "mvp-wrapper-cmd-status-explicit-failed-json missing prepared status"
            )

        elif "task-wrapper-cmd-status-explicit-failed" not in captured_output:
            errors.append(
                "mvp-wrapper-cmd-status-explicit-failed-json missing captured task task-wrapper-cmd-status-explicit-failed"
            )

        elif "RetryEligible" not in captured_output:
            errors.append(
                "mvp-wrapper-cmd-status-explicit-failed-json missing RetryEligible"
            )

        elif "worker=Failed" not in captured_output:
            errors.append(
                "mvp-wrapper-cmd-status-explicit-failed-json missing worker=Failed"
            )

        elif "effect=Prepared" not in captured_output:
            errors.append(
                "mvp-wrapper-cmd-status-explicit-failed-json missing effect=Prepared"
            )

        elif (
            not isinstance(remembered_session, dict)
            or remembered_session.get("task_id")
            != "task-wrapper-cmd-status-explicit-failed"
        ):
            errors.append(
                "mvp-wrapper-cmd-status-explicit-failed-json missing remembered session task-wrapper-cmd-status-explicit-failed"
            )

        elif not isinstance(source_hints, dict) or source_hints.get("db") != "flag":
            errors.append(
                "mvp-wrapper-cmd-status-explicit-failed-json missing source_hints.db=flag"
            )

        elif source_hints.get("output") != "session":
            errors.append(
                "mvp-wrapper-cmd-status-explicit-failed-json missing source_hints.output=session"
            )

        elif source_hints.get("owner_id") != "session":
            errors.append(
                "mvp-wrapper-cmd-status-explicit-failed-json missing source_hints.owner_id=session"
            )

        elif source_hints.get("task_context") != "flag":
            errors.append(
                "mvp-wrapper-cmd-status-explicit-failed-json missing source_hints.task_context=flag"
            )

    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-failed",
            "--reset",
            "--task-id",
            "task-wrapper-cmd-report-explicit-failed",
            "--db",
            "target/mvp/cmd-report-explicit-failed.db",
            "--output",
            "target/mvp/cmd-report-explicit-failed.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-cmd-report-explicit-failed-seed-json",
        "seed-failed",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-cmd-report-explicit-failed-seed-json",
        expected_task_id="task-wrapper-cmd-report-explicit-failed",
        expected_db_path="target/mvp/cmd-report-explicit-failed.db",
        expected_output_path="target/mvp/cmd-report-explicit-failed.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )

    result = assert_command_json_result(
        [
            "cmd",
            "/c",
            "tools\mvp\safeclaw_mvp.cmd",
            "report",
            "--db",
            "target/mvp/cmd-report-explicit-failed.db",
            "--task-id",
            "task-wrapper-cmd-report-explicit-failed",
            "--json",
        ],
        errors,
        "mvp-wrapper-cmd-report-explicit-failed-json",
        "report",
    )

    if result is not None:
        prepared = result.get("prepared") or []

        remembered_session = result.get("remembered_session") or {}

        source_hints = result.get("source_hints") or {}

        captured_output = str(result.get("captured_output") or "")

        if not prepared or prepared[0] != "report":
            errors.append(
                "mvp-wrapper-cmd-report-explicit-failed-json missing prepared report"
            )

        elif "task-wrapper-cmd-report-explicit-failed" not in captured_output:
            errors.append(
                "mvp-wrapper-cmd-report-explicit-failed-json missing captured task task-wrapper-cmd-report-explicit-failed"
            )

        elif "RetryEligible" not in captured_output:
            errors.append(
                "mvp-wrapper-cmd-report-explicit-failed-json missing RetryEligible"
            )

        elif "worker=Failed" not in captured_output:
            errors.append(
                "mvp-wrapper-cmd-report-explicit-failed-json missing worker=Failed"
            )

        elif "effect=Prepared" not in captured_output:
            errors.append(
                "mvp-wrapper-cmd-report-explicit-failed-json missing effect=Prepared"
            )

        elif (
            not isinstance(remembered_session, dict)
            or remembered_session.get("task_id")
            != "task-wrapper-cmd-report-explicit-failed"
        ):
            errors.append(
                "mvp-wrapper-cmd-report-explicit-failed-json missing remembered session task-wrapper-cmd-report-explicit-failed"
            )

        elif not isinstance(source_hints, dict) or source_hints.get("db") != "flag":
            errors.append(
                "mvp-wrapper-cmd-report-explicit-failed-json missing source_hints.db=flag"
            )

        elif source_hints.get("output") != "session":
            errors.append(
                "mvp-wrapper-cmd-report-explicit-failed-json missing source_hints.output=session"
            )

        elif source_hints.get("owner_id") != "session":
            errors.append(
                "mvp-wrapper-cmd-report-explicit-failed-json missing source_hints.owner_id=session"
            )

        elif source_hints.get("task_context") != "flag":
            errors.append(
                "mvp-wrapper-cmd-report-explicit-failed-json missing source_hints.task_context=flag"
            )

    wrapper_restore_after_ps1_retry_a = subprocess.run(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "run",
            "--reset",
            "--task-id",
            "task-wrapper-a",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    if wrapper_restore_after_ps1_retry_a.returncode != 0:
        errors.append(
            f"mvp-wrapper-restore-after-ps1-retry-a failed: exit={wrapper_restore_after_ps1_retry_a.returncode}"
        )

    wrapper_restore_after_ps1_retry_b = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "run", "--task-id", "task-wrapper-b"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    if wrapper_restore_after_ps1_retry_b.returncode != 0:
        errors.append(
            f"mvp-wrapper-restore-after-ps1-retry-b failed: exit={wrapper_restore_after_ps1_retry_b.returncode}"
        )

    wrapper_use = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "use", "--index", "1"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_use_output = (wrapper_use.stdout or "") + (wrapper_use.stderr or "")

    if wrapper_use.returncode != 0:
        errors.append(f"mvp-wrapper-use 执行失败: exit={wrapper_use.returncode}")

    elif (
        "[mvp-wrapper] activated => task=task-wrapper-a effect=effect-task-wrapper-a"
        not in wrapper_use_output
    ):
        errors.append("mvp-wrapper-use 输出缺少切回 task-wrapper-a")

    elif (
        "source=index:1 db_source=session output_source=task_scope owner_source=session"
        not in wrapper_use_output
    ):
        errors.append("mvp-wrapper-use 输出缺少来源说明")

    wrapper_session_after_use = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "session"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_session_after_use_output = (wrapper_session_after_use.stdout or "") + (
        wrapper_session_after_use.stderr or ""
    )

    if wrapper_session_after_use.returncode != 0:
        errors.append(
            f"mvp-wrapper-session-after-use 执行失败: exit={wrapper_session_after_use.returncode}"
        )

    elif (
        "[mvp-wrapper] session => task=task-wrapper-a effect=effect-task-wrapper-a"
        not in wrapper_session_after_use_output
    ):
        errors.append("mvp-wrapper-session-after-use 输出缺少已切换 task-wrapper-a")

    elif "path=target\\mvp\\last_session.json" not in wrapper_session_after_use_output:
        errors.append("mvp-wrapper-session-after-use 输出缺少 remembered session 路径")

    wrapper_status_after_use = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "status"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_status_after_use_output = (wrapper_status_after_use.stdout or "") + (
        wrapper_status_after_use.stderr or ""
    )

    if wrapper_status_after_use.returncode != 0:
        errors.append(
            f"mvp-wrapper-status-after-use 执行失败: exit={wrapper_status_after_use.returncode}"
        )

    elif (
        "[mvp] status target => task=task-wrapper-a effect=effect-task-wrapper-a"
        not in wrapper_status_after_use_output
    ):
        errors.append("mvp-wrapper-status-after-use 输出缺少已切换 task-wrapper-a")

    wrapper_use_json = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "use", "--index", "0", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    payload = load_json_payload(
        wrapper_use_json, errors, "mvp-wrapper-use-json", expected_exit=0
    )

    if payload is not None:
        result = extract_json_result(payload, errors, "mvp-wrapper-use-json", "use")

        if result is not None:
            if (
                result.get("task_id") != "task-wrapper-b"
                or result.get("source") != "index:0"
            ):
                errors.append("mvp-wrapper-use-json 输出缺少切回 task-wrapper-b")

            elif result.get("db_source") != "session":
                errors.append("mvp-wrapper-use-json 输出缺少 db_source=session")

            elif result.get("output_source") != "task_scope":
                errors.append("mvp-wrapper-use-json 输出缺少 output_source=task_scope")

            elif result.get("owner_id_source") != "session":
                errors.append("mvp-wrapper-use-json 输出缺少 owner_id_source=session")

    wrapper_report_json = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "report", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    payload = load_json_payload(
        wrapper_report_json, errors, "mvp-wrapper-report-json", expected_exit=0
    )

    if payload is not None:
        result = extract_json_result(
            payload, errors, "mvp-wrapper-report-json", "report"
        )

        if result is not None:
            prepared = result.get("prepared") or []

            source_hints = result.get("source_hints") or {}

            if not prepared or prepared[0] != "report":
                errors.append("mvp-wrapper-report-json 缺少 prepared report")

            elif "task-wrapper-b" not in (result.get("captured_output") or ""):
                errors.append("mvp-wrapper-report-json 缺少当前会话 task-wrapper-b 输出")

            elif (result.get("remembered_session") or {}).get(
                "task_id"
            ) != "task-wrapper-b":
                errors.append(
                    "mvp-wrapper-report-json 缺少 remembered session task-wrapper-b"
                )

            elif source_hints.get("task_context") != "session":
                errors.append("mvp-wrapper-report-json 缺少 task_context=session")

    wrapper_cmd_forget = subprocess.run(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "forget"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_cmd_forget_output = (wrapper_cmd_forget.stdout or "") + (
        wrapper_cmd_forget.stderr or ""
    )

    if wrapper_cmd_forget.returncode != 0:
        errors.append(
            f"mvp-wrapper-cmd-forget failed: exit={wrapper_cmd_forget.returncode}"
        )

    elif (
        "[mvp-wrapper] forgot => reason=removed path=target\mvp\last_session.json"
        not in wrapper_cmd_forget_output
    ):
        errors.append("mvp-wrapper-cmd-forget missing removed path")

    result = assert_command_json_result(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "forget", "--json"],
        errors,
        "mvp-wrapper-cmd-forget-json",
        "forget",
    )
    if result is not None:
        forget_state = (result.get("forgot"), result.get("reason"))
        if result.get("path") != "target\mvp\last_session.json":
            errors.append("mvp-wrapper-cmd-forget-json missing session path")
        elif forget_state not in {(True, "removed"), (False, "none")}:
            errors.append("mvp-wrapper-cmd-forget-json unexpected forget state")
    wrapper_ps1_session_after_cmd_forget_json = subprocess.run(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "session",
            "--json",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    payload = load_json_payload(
        wrapper_ps1_session_after_cmd_forget_json,
        errors,
        "mvp-wrapper-ps1-session-after-cmd-forget-json",
        expected_exit=0,
    )

    assert_json_null_result(
        payload, errors, "mvp-wrapper-ps1-session-after-cmd-forget-json", "session"
    )

    wrapper_restore_after_cmd_forget = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "use", "--task-id", "task-wrapper-b"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_restore_after_cmd_forget_output = (
        wrapper_restore_after_cmd_forget.stdout or ""
    ) + (wrapper_restore_after_cmd_forget.stderr or "")

    if wrapper_restore_after_cmd_forget.returncode != 0:
        errors.append(
            f"mvp-wrapper-restore-after-cmd-forget failed: exit={wrapper_restore_after_cmd_forget.returncode}"
        )

    elif (
        "[mvp-wrapper] activated => task=task-wrapper-b effect=effect-task-wrapper-b"
        not in wrapper_restore_after_cmd_forget_output
    ):
        errors.append("mvp-wrapper-restore-after-cmd-forget missing task-wrapper-b")

    wrapper_forget = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "forget"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_forget_output = (wrapper_forget.stdout or "") + (
        wrapper_forget.stderr or ""
    )

    if wrapper_forget.returncode != 0:
        errors.append(f"mvp-wrapper-forget 执行失败: exit={wrapper_forget.returncode}")

    elif (
        "[mvp-wrapper] forgot => reason=removed path=target\\mvp\\last_session.json"
        not in wrapper_forget_output
    ):
        errors.append("mvp-wrapper-forget 输出缺少会话清空标记")

    wrapper_forget_json = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "forget", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    payload = load_json_payload(
        wrapper_forget_json, errors, "mvp-wrapper-forget-json", expected_exit=0
    )

    if payload is not None:
        result = extract_json_result(
            payload, errors, "mvp-wrapper-forget-json", "forget"
        )

        if result is not None:
            if (
                result.get("forgot") is not False
                or result.get("path") != "target\\mvp\\last_session.json"
            ):
                errors.append("mvp-wrapper-forget-json 输出不符合预期")

            elif result.get("reason") != "none":
                errors.append("mvp-wrapper-forget-json 输出缺少 reason=none")

    wrapper_session_after_forget = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "session"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_session_after_forget_output = (
        wrapper_session_after_forget.stdout or ""
    ) + (wrapper_session_after_forget.stderr or "")

    if wrapper_session_after_forget.returncode != 0:
        errors.append(
            f"mvp-wrapper-session-after-forget 执行失败: exit={wrapper_session_after_forget.returncode}"
        )

    elif (
        "[mvp-wrapper] session => none path=target\\mvp\\last_session.json"
        not in wrapper_session_after_forget_output
    ):
        errors.append("mvp-wrapper-session-after-forget 输出缺少 none/path")

    assert_command_json_error(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "report", "--json"],
        errors,
        "mvp-wrapper-cmd-report-without-session-json",
        "report",
        expected_error_message_substring="missing task context",
        error_message_label="mvp-wrapper-cmd-report-without-session-json missing wrapper error",
        expected_code="missing-task-context",
        expect_no_remembered_session=True,
    )

    assert_command_json_error(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "report",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-report-without-session-json",
        "report",
        expected_error_message_substring="missing task context",
        error_message_label="mvp-wrapper-ps1-report-without-session-json missing wrapper error",
        expected_code="missing-task-context",
        expect_no_remembered_session=True,
    )

    assert_command_json_error(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "report", "--json"],
        errors,
        "mvp-wrapper-report-without-session-json",
        "report",
        expected_error_message_substring="missing task context",
        error_message_label="mvp-wrapper-report-without-session-json 缺少 wrapper 级错误消息",
        expected_code="missing-task-context",
        expect_no_remembered_session=True,
    )

    assert_command_json_error(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "recover", "--json"],
        errors,
        "mvp-wrapper-cmd-recover-without-session-json",
        "recover",
        expected_error_message_substring="missing task context",
        error_message_label="mvp-wrapper-cmd-recover-without-session-json missing wrapper error",
        expected_code="missing-task-context",
        expect_no_remembered_session=True,
    )

    assert_command_json_error(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "recover",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-recover-without-session-json",
        "recover",
        expected_error_message_substring="missing task context",
        error_message_label="mvp-wrapper-ps1-recover-without-session-json missing wrapper error",
        expected_code="missing-task-context",
        expect_no_remembered_session=True,
    )

    assert_command_json_error(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "recover", "--json"],
        errors,
        "mvp-wrapper-recover-without-session-json",
        "recover",
        expected_error_message_substring="missing task context",
        error_message_label="mvp-wrapper-recover-without-session-json ?? wrapper ?????",
        expected_code="missing-task-context",
        expect_no_remembered_session=True,
    )

    assert_command_json_error(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "retry", "--json"],
        errors,
        "mvp-wrapper-cmd-retry-without-session-json",
        "retry",
        expected_error_message_substring="missing task context",
        error_message_label="mvp-wrapper-cmd-retry-without-session-json missing wrapper error",
        expected_code="missing-task-context",
        expect_no_remembered_session=True,
    )

    assert_command_json_error(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "retry",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-retry-without-session-json",
        "retry",
        expected_error_message_substring="missing task context",
        error_message_label="mvp-wrapper-ps1-retry-without-session-json missing wrapper error",
        expected_code="missing-task-context",
        expect_no_remembered_session=True,
    )

    assert_command_json_error(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "retry", "--json"],
        errors,
        "mvp-wrapper-retry-without-session-json",
        "retry",
        expected_error_message_substring="missing task context",
        error_message_label="mvp-wrapper-retry-without-session-json 缺少 wrapper 级错误消息",
        expected_code="missing-task-context",
        expect_no_remembered_session=True,
    )

    assert_command_json_error(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "service-resume", "--json"],
        errors,
        "mvp-wrapper-service-resume-without-session-json",
        "service-resume",
        expected_error_message_substring="failed step=resume",
        error_message_label="mvp-wrapper-service-resume-without-session-json missing wrapper error",
        expected_failed_step="resume",
        expected_code="missing-task-context",
        expected_details_message_substring="missing task context",
        expect_no_remembered_session=True,
    )

    assert_command_json_error(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "resume",
            "--db",
            "target/mvp/resume-missing.db",
            "--json",
        ],
        errors,
        "mvp-wrapper-resume-missing-task-json",
        "resume",
        expected_error_message_substring="missing task context",
        error_message_label="mvp-wrapper-resume-missing-task-json missing wrapper error",
        expected_code="missing-task-context",
        expect_no_remembered_session=True,
    )

    assert_command_json_error(
        [
            "cmd",
            "/c",
            "tools\mvp\safeclaw_mvp.cmd",
            "resume",
            "--db",
            "target/mvp/resume-missing-cmd.db",
            "--json",
        ],
        errors,
        "mvp-wrapper-cmd-resume-missing-task-json",
        "resume",
        expected_error_message_substring="missing task context",
        error_message_label="mvp-wrapper-cmd-resume-missing-task-json missing wrapper error",
        expected_code="missing-task-context",
        expect_no_remembered_session=True,
    )

    assert_command_json_error(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "resume",
            "--db",
            "target/mvp/resume-missing-ps1.db",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-resume-missing-task-json",
        "resume",
        expected_error_message_substring="missing task context",
        error_message_label="mvp-wrapper-ps1-resume-missing-task-json missing wrapper error",
        expected_code="missing-task-context",
        expect_no_remembered_session=True,
    )

    assert_command_json_error(
        [
            "cmd",
            "/c",
            "tools\mvp\safeclaw_mvp.cmd",
            "reconcile",
            "--db",
            "target/mvp/reconcile-missing-cmd.db",
            "--decision",
            "executed",
            "--json",
        ],
        errors,
        "mvp-wrapper-cmd-reconcile-missing-task-json",
        "reconcile",
        expected_error_message_substring="missing task context",
        error_message_label="mvp-wrapper-cmd-reconcile-missing-task-json missing wrapper error",
        expected_code="missing-task-context",
        expect_no_remembered_session=True,
    )

    assert_command_json_error(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "reconcile",
            "--db",
            "target/mvp/reconcile-missing-ps1.db",
            "--decision",
            "executed",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-reconcile-missing-task-json",
        "reconcile",
        expected_error_message_substring="missing task context",
        error_message_label="mvp-wrapper-ps1-reconcile-missing-task-json missing wrapper error",
        expected_code="missing-task-context",
        expect_no_remembered_session=True,
    )

    assert_command_json_error(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "reconcile",
            "--db",
            "target/mvp/reconcile-missing.db",
            "--decision",
            "executed",
            "--json",
        ],
        errors,
        "mvp-wrapper-reconcile-missing-task-json",
        "reconcile",
        expected_error_message_substring="missing task context",
        error_message_label="mvp-wrapper-reconcile-missing-task-json missing wrapper error",
        expected_code="missing-task-context",
        expect_no_remembered_session=True,
    )

    assert_command_json_error(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "service-reconcile",
            "--db",
            "target/mvp/service-reconcile-missing.db",
            "--decision",
            "executed",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-reconcile-missing-task-json",
        "service-reconcile",
        expected_error_message_substring="failed step=reconcile",
        error_message_label="mvp-wrapper-service-reconcile-missing-task-json missing wrapper error",
        expected_failed_step="reconcile",
        expected_code="missing-task-context",
        expected_details_message_substring="missing task context",
        expect_no_remembered_session=True,
    )

    wrapper_invalid_json_base = subprocess.run(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "run",
            "--reset",
            "--task-id",
            "task-wrapper-invalid-json-base",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_invalid_json_base_output = (wrapper_invalid_json_base.stdout or "") + (
        wrapper_invalid_json_base.stderr or ""
    )

    if wrapper_invalid_json_base.returncode != 0:
        errors.append(
            f"mvp-wrapper-invalid-json-base 执行失败: exit={wrapper_invalid_json_base.returncode}"
        )

    elif (
        "[mvp] accepted task => task=task-wrapper-invalid-json-base effect=effect-task-wrapper-invalid-json-base"
        not in wrapper_invalid_json_base_output
    ):
        errors.append(
            "mvp-wrapper-invalid-json-base 输出缺少基座会话 task-wrapper-invalid-json-base"
        )

    assert_command_json_error(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "report", "--bogus", "--json"],
        errors,
        "mvp-wrapper-cmd-report-invalid-json",
        "report",
        expected_error_message_substring="unknown argument",
        error_message_label="mvp-wrapper-cmd-report-invalid-json missing unknown argument",
        expected_code="invalid-argument",
        expected_remembered_session_task_id="task-wrapper-invalid-json-base",
        remembered_session_label="mvp-wrapper-cmd-report-invalid-json missing invalid-json-base",
    )

    assert_command_json_error(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\\mvp\\safeclaw_mvp.ps1",
            "report",
            "--bogus",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-report-invalid-json",
        "report",
        expected_error_message_substring="unknown argument",
        error_message_label="mvp-wrapper-ps1-report-invalid-json missing unknown argument",
        expected_code="invalid-argument",
        expected_remembered_session_task_id="task-wrapper-invalid-json-base",
        remembered_session_label="mvp-wrapper-ps1-report-invalid-json missing invalid-json-base",
    )

    assert_command_json_error(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "report", "--bogus", "--json"],
        errors,
        "mvp-wrapper-report-invalid-json",
        "report",
        expected_error_message_substring="unknown argument",
        error_message_label="mvp-wrapper-report-invalid-json 缺少 wrapper 级 unknown argument",
        expected_code="invalid-argument",
        expected_remembered_session_task_id="task-wrapper-invalid-json-base",
        remembered_session_label="mvp-wrapper-report-invalid-json remembered_session 缺少基座会话",
    )

    assert_command_json_error(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "recover", "--bogus", "--json"],
        errors,
        "mvp-wrapper-cmd-recover-invalid-json",
        "recover",
        expected_error_message_substring="unknown argument",
        error_message_label="mvp-wrapper-cmd-recover-invalid-json missing unknown argument",
        expected_code="invalid-argument",
        expected_remembered_session_task_id="task-wrapper-invalid-json-base",
        remembered_session_label="mvp-wrapper-cmd-recover-invalid-json missing invalid-json-base",
    )

    assert_command_json_error(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "recover",
            "--bogus",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-recover-invalid-json",
        "recover",
        expected_error_message_substring="unknown argument",
        error_message_label="mvp-wrapper-ps1-recover-invalid-json missing unknown argument",
        expected_code="invalid-argument",
        expected_remembered_session_task_id="task-wrapper-invalid-json-base",
        remembered_session_label="mvp-wrapper-ps1-recover-invalid-json missing invalid-json-base",
    )

    assert_command_json_error(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "recover", "--bogus", "--json"],
        errors,
        "mvp-wrapper-recover-invalid-json",
        "recover",
        expected_error_message_substring="unknown argument",
        error_message_label="mvp-wrapper-recover-invalid-json 缺少 wrapper 级 unknown argument",
        expected_code="invalid-argument",
        expected_remembered_session_task_id="task-wrapper-invalid-json-base",
        remembered_session_label="mvp-wrapper-recover-invalid-json remembered_session 缺少基座会话",
    )

    assert_command_json_error(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "retry", "--bogus", "--json"],
        errors,
        "mvp-wrapper-cmd-retry-invalid-json",
        "retry",
        expected_error_message_substring="unknown argument",
        error_message_label="mvp-wrapper-cmd-retry-invalid-json missing unknown argument",
        expected_code="invalid-argument",
        expected_remembered_session_task_id="task-wrapper-invalid-json-base",
        remembered_session_label="mvp-wrapper-cmd-retry-invalid-json missing invalid-json-base",
    )

    assert_command_json_error(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "retry",
            "--bogus",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-retry-invalid-json",
        "retry",
        expected_error_message_substring="unknown argument",
        error_message_label="mvp-wrapper-ps1-retry-invalid-json missing unknown argument",
        expected_code="invalid-argument",
        expected_remembered_session_task_id="task-wrapper-invalid-json-base",
        remembered_session_label="mvp-wrapper-ps1-retry-invalid-json missing invalid-json-base",
    )

    assert_command_json_error(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "retry", "--bogus", "--json"],
        errors,
        "mvp-wrapper-retry-invalid-json",
        "retry",
        expected_error_message_substring="unknown argument",
        error_message_label="mvp-wrapper-retry-invalid-json 缺少 wrapper 级 unknown argument",
        expected_code="invalid-argument",
        expected_remembered_session_task_id="task-wrapper-invalid-json-base",
        remembered_session_label="mvp-wrapper-retry-invalid-json remembered_session 缺少基座会话",
    )

    assert_command_json_error(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "session", "--bogus", "--json"],
        errors,
        "mvp-wrapper-cmd-invalid-session-json",
        "session",
        expected_error_message_substring="unknown argument",
    )

    assert_command_json_error(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "session",
            "--bogus",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-invalid-session-json",
        "session",
        expected_error_message_substring="unknown argument",
    )

    assert_command_json_error(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "doctor", "--db", "--json"],
        errors,
        "mvp-wrapper-cmd-invalid-doctor-json",
        "doctor",
        expected_error_message_substring="missing value after --db",
    )

    assert_command_json_error(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "doctor",
            "--db",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-invalid-doctor-json",
        "doctor",
        expected_error_message_substring="missing value after --db",
    )

    assert_command_json_error(
        [
            "cmd",
            "/c",
            "tools\mvp\safeclaw_mvp.cmd",
            "sessions",
            "--limit",
            "bad",
            "--json",
        ],
        errors,
        "mvp-wrapper-cmd-invalid-sessions-json",
        "sessions",
        expected_error_message_substring="invalid --limit",
    )

    assert_command_json_error(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "sessions",
            "--limit",
            "bad",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-invalid-sessions-json",
        "sessions",
        expected_error_message_substring="invalid --limit",
    )

    assert_command_json_error(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "session", "--bogus", "--json"],
        errors,
        "mvp-wrapper-invalid-session-json",
        "session",
        expected_error_message_substring="unknown argument",
    )

    assert_command_json_error(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "doctor", "--db", "--json"],
        errors,
        "mvp-wrapper-invalid-doctor-json",
        "doctor",
        expected_error_message_substring="missing value after --db",
    )

    wrapper_service_run_report = subprocess.run(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "service-run",
            "--reset",
            "--task-id",
            "task-wrapper-service-run-report",
            "--db",
            "target/mvp/service-run-report.db",
            "--output",
            "target/mvp/service-run-report.txt",
            "--limit",
            "1",
            "--report",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_service_run_report_output = (wrapper_service_run_report.stdout or "") + (
        wrapper_service_run_report.stderr or ""
    )

    if wrapper_service_run_report.returncode != 0:
        errors.append(
            f"mvp-wrapper-service-run-report failed: exit={wrapper_service_run_report.returncode}"
        )

    elif "[mvp-wrapper] service-run => run" not in wrapper_service_run_report_output:
        errors.append("mvp-wrapper-service-run-report missing run step marker")

    elif (
        "[mvp-wrapper] service-run => service-status"
        not in wrapper_service_run_report_output
    ):
        errors.append(
            "mvp-wrapper-service-run-report missing service-status step marker"
        )

    elif "[mvp-wrapper] service-run => report" not in wrapper_service_run_report_output:
        errors.append("mvp-wrapper-service-run-report missing report step marker")

    elif (
        "[mvp] report target => task=task-wrapper-service-run-report effect=effect-task-wrapper-service-run-report"
        not in wrapper_service_run_report_output
    ):
        errors.append("mvp-wrapper-service-run-report missing report output")

    result = assert_command_json_result(
        [
            "cmd",
            "/c",
            "tools\mvp\safeclaw_mvp.cmd",
            "service-run",
            "--reset",
            "--task-id",
            "task-wrapper-service-run-report-json",
            "--db",
            "target/mvp/service-run-report-json.db",
            "--output",
            "target/mvp/service-run-report-json.txt",
            "--limit",
            "1",
            "--report",
            "--json",
        ],
        errors,
        "mvp-wrapper-cmd-service-run-report-json",
        "service-run",
    )

    assert_service_run_json_result(
        result,
        errors,
        "mvp-wrapper-cmd-service-run-report-json",
        expected_db="target\mvp\service-run-report-json.db",
        expected_db_source="flag",
        expected_task_id="task-wrapper-service-run-report-json",
        expected_limit=1,
        expected_steps=["run", "service-status", "report"],
        expect_report_payload=True,
    )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "service-run",
            "--reset",
            "--task-id",
            "task-wrapper-service-run-report-json",
            "--db",
            "target/mvp/service-run-report-json.db",
            "--output",
            "target/mvp/service-run-report-json.txt",
            "--limit",
            "1",
            "--report",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-service-run-report-json",
        "service-run",
    )

    assert_service_run_json_result(
        result,
        errors,
        "mvp-wrapper-ps1-service-run-report-json",
        expected_db="target\mvp\service-run-report-json.db",
        expected_db_source="flag",
        expected_task_id="task-wrapper-service-run-report-json",
        expected_limit=1,
        expected_steps=["run", "service-status", "report"],
        expect_report_payload=True,
    )

    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-failed",
            "--reset",
            "--task-id",
            "task-wrapper-service-retry-report-json",
            "--db",
            "target/mvp/service-retry-report-json.db",
            "--output",
            "target/mvp/service-retry-report-json.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-retry-report-json-seed-failed-json",
        "seed-failed",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-service-retry-report-json-seed-failed-json",
        expected_task_id="task-wrapper-service-retry-report-json",
        expected_db_path="target/mvp/service-retry-report-json.db",
        expected_output_path="target/mvp/service-retry-report-json.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )

    result = assert_command_json_result(
        [
            "cmd",
            "/c",
            "tools\mvp\safeclaw_mvp.cmd",
            "service-retry",
            "--db",
            "target/mvp/service-retry-report-json.db",
            "--task-id",
            "task-wrapper-service-retry-report-json",
            "--limit",
            "1",
            "--report",
            "--json",
        ],
        errors,
        "mvp-wrapper-cmd-service-retry-report-json",
        "service-retry",
    )

    assert_service_retry_json_result(
        result,
        errors,
        "mvp-wrapper-cmd-service-retry-report-json",
        expected_db="target\mvp\service-retry-report-json.db",
        expected_db_source="flag",
        expected_task_id="task-wrapper-service-retry-report-json",
        expected_limit=1,
        expected_steps=["retry", "service-status", "report"],
        expect_report_payload=True,
    )

    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-failed",
            "--reset",
            "--task-id",
            "task-wrapper-service-retry-report-json",
            "--db",
            "target/mvp/service-retry-report-json.db",
            "--output",
            "target/mvp/service-retry-report-json.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-retry-report-json-seed-failed-ps1-json",
        "seed-failed",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-service-retry-report-json-seed-failed-ps1-json",
        expected_task_id="task-wrapper-service-retry-report-json",
        expected_db_path="target/mvp/service-retry-report-json.db",
        expected_output_path="target/mvp/service-retry-report-json.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "service-retry",
            "--db",
            "target/mvp/service-retry-report-json.db",
            "--task-id",
            "task-wrapper-service-retry-report-json",
            "--limit",
            "1",
            "--report",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-service-retry-report-json",
        "service-retry",
    )

    assert_service_retry_json_result(
        result,
        errors,
        "mvp-wrapper-ps1-service-retry-report-json",
        expected_db="target\mvp\service-retry-report-json.db",
        expected_db_source="flag",
        expected_task_id="task-wrapper-service-retry-report-json",
        expected_limit=1,
        expected_steps=["retry", "service-status", "report"],
        expect_report_payload=True,
    )

    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-crash",
            "--reset",
            "--task-id",
            "task-wrapper-service-recover-report-json",
            "--db",
            "target/mvp/service-recover-report-json.db",
            "--output",
            "target/mvp/service-recover-report-json.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-recover-report-json-seed-crash-json",
        "seed-crash",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-service-recover-report-json-seed-crash-json",
        expected_task_id="task-wrapper-service-recover-report-json",
        expected_db_path="target/mvp/service-recover-report-json.db",
        expected_output_path="target/mvp/service-recover-report-json.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )

    result = assert_command_json_result(
        [
            "cmd",
            "/c",
            "tools\mvp\safeclaw_mvp.cmd",
            "service-recover",
            "--db",
            "target/mvp/service-recover-report-json.db",
            "--task-id",
            "task-wrapper-service-recover-report-json",
            "--limit",
            "1",
            "--report",
            "--json",
        ],
        errors,
        "mvp-wrapper-cmd-service-recover-report-json",
        "service-recover",
    )

    assert_service_recover_json_result(
        result,
        errors,
        "mvp-wrapper-cmd-service-recover-report-json",
        expected_db="target\mvp\service-recover-report-json.db",
        expected_db_source="flag",
        expected_task_id="task-wrapper-service-recover-report-json",
        expected_limit=1,
        expected_steps=["recover", "service-status", "report"],
        expect_report_payload=True,
    )

    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-crash",
            "--reset",
            "--task-id",
            "task-wrapper-service-recover-report-json",
            "--db",
            "target/mvp/service-recover-report-json.db",
            "--output",
            "target/mvp/service-recover-report-json.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-recover-report-json-seed-crash-ps1-json",
        "seed-crash",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-service-recover-report-json-seed-crash-ps1-json",
        expected_task_id="task-wrapper-service-recover-report-json",
        expected_db_path="target/mvp/service-recover-report-json.db",
        expected_output_path="target/mvp/service-recover-report-json.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "service-recover",
            "--db",
            "target/mvp/service-recover-report-json.db",
            "--task-id",
            "task-wrapper-service-recover-report-json",
            "--limit",
            "1",
            "--report",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-service-recover-report-json",
        "service-recover",
    )

    assert_service_recover_json_result(
        result,
        errors,
        "mvp-wrapper-ps1-service-recover-report-json",
        expected_db="target\mvp\service-recover-report-json.db",
        expected_db_source="flag",
        expected_task_id="task-wrapper-service-recover-report-json",
        expected_limit=1,
        expected_steps=["recover", "service-status", "report"],
        expect_report_payload=True,
    )

    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-crash",
            "--reset",
            "--probe-mode",
            "none",
            "--task-id",
            "task-wrapper-service-reconcile-json",
            "--db",
            "target/mvp/service-reconcile-json.db",
            "--output",
            "target/mvp/service-reconcile-json.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-reconcile-seed-crash-json",
        "seed-crash",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-service-reconcile-seed-crash-json",
        expected_task_id="task-wrapper-service-reconcile-json",
        expected_db_path="target/mvp/service-reconcile-json.db",
        expected_output_path="target/mvp/service-reconcile-json.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )

    wrapper_service_status_reconcile = subprocess.run(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "service-status",
            "--db",
            "target/mvp/service-reconcile-json.db",
            "--limit",
            "1",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_service_status_reconcile_output = (
        wrapper_service_status_reconcile.stdout or ""
    ) + (wrapper_service_status_reconcile.stderr or "")

    if wrapper_service_status_reconcile.returncode != 0:
        errors.append(
            f"mvp-wrapper-service-reconcile-status-before failed: exit={wrapper_service_status_reconcile.returncode}"
        )

    elif (
        "[mvp-wrapper] service coordination => status=quarantined reason=self_executed_assumed_scope_quarantine summary=reconcile_self_before_scope_write task=task-wrapper-service-reconcile-json"
        not in wrapper_service_status_reconcile_output
    ):
        errors.append(
            "mvp-wrapper-service-reconcile-status-before missing self quarantine coordination summary"
        )

    elif (
        "next=inspect next_reason=executed_assumed_requires_reconcile blocker=scope_quarantine coordination=quarantined coordination_reason=self_executed_assumed_scope_quarantine coordination_summary=reconcile_self_before_scope_write"
        not in wrapper_service_status_reconcile_output
    ):
        errors.append(
            "mvp-wrapper-service-reconcile-status-before missing reconcile next hint"
        )

    elif (
        '[mvp-wrapper] service recent[0] reconcile => executed=safeclaw.cmd service-reconcile --db "target/mvp/service-reconcile-json.db" --task-id "task-wrapper-service-reconcile-json" --decision executed --limit 1 --report not_executed=safeclaw.cmd service-reconcile --db "target/mvp/service-reconcile-json.db" --task-id "task-wrapper-service-reconcile-json" --decision not-executed --limit 1 --report'
        not in wrapper_service_status_reconcile_output
    ):
        errors.append(
            "mvp-wrapper-service-reconcile-status-before missing reconcile command choices"
        )

    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "service-status",
            "--db",
            "target/mvp/service-reconcile-json.db",
            "--limit",
            "1",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-reconcile-status-before-json",
        "service-status",
    )

    if result is not None:
        coordination = result.get("coordination") or {}

        recent_tasks = result.get("recent_tasks") or []

        current_session = result.get("current_session") or {}

        if (
            not isinstance(current_session, dict)
            or current_session.get("task_id") != "task-wrapper-service-reconcile-json"
        ):
            errors.append(
                "mvp-wrapper-service-reconcile-status-before-json missing current_session task-wrapper-service-reconcile-json"
            )

        elif coordination.get("status") != "quarantined":
            errors.append(
                "mvp-wrapper-service-reconcile-status-before-json missing coordination.status=quarantined"
            )

        elif coordination.get("reason") != "self_executed_assumed_scope_quarantine":
            errors.append(
                "mvp-wrapper-service-reconcile-status-before-json missing coordination.reason=self_executed_assumed_scope_quarantine"
            )

        elif coordination.get("summary") != "reconcile_self_before_scope_write":
            errors.append(
                "mvp-wrapper-service-reconcile-status-before-json missing coordination.summary=reconcile_self_before_scope_write"
            )

        elif coordination.get("scope_quarantine_active") is not True:
            errors.append(
                "mvp-wrapper-service-reconcile-status-before-json missing coordination.scope_quarantine_active=true"
            )

        elif coordination.get("scope_quarantine_source") != "self":
            errors.append(
                "mvp-wrapper-service-reconcile-status-before-json missing coordination.scope_quarantine_source=self"
            )

        elif (
            coordination.get("scope_quarantine_task_id")
            != "task-wrapper-service-reconcile-json"
        ):
            errors.append(
                "mvp-wrapper-service-reconcile-status-before-json missing coordination.scope_quarantine_task_id=task-wrapper-service-reconcile-json"
            )

        elif coordination.get("next_task_id") != "task-wrapper-service-reconcile-json":
            errors.append(
                "mvp-wrapper-service-reconcile-status-before-json missing coordination.next_task_id=task-wrapper-service-reconcile-json"
            )

        elif not isinstance(recent_tasks, list) or not recent_tasks:
            errors.append(
                "mvp-wrapper-service-reconcile-status-before-json missing recent task"
            )

        elif recent_tasks[0].get("task_id") != "task-wrapper-service-reconcile-json":
            errors.append(
                "mvp-wrapper-service-reconcile-status-before-json missing recent task task-wrapper-service-reconcile-json"
            )

        elif recent_tasks[0].get("next_action") != "inspect":
            errors.append(
                "mvp-wrapper-service-reconcile-status-before-json missing next_action=inspect"
            )

        elif (
            recent_tasks[0].get("next_reason") != "executed_assumed_requires_reconcile"
        ):
            errors.append(
                "mvp-wrapper-service-reconcile-status-before-json missing next_reason=executed_assumed_requires_reconcile"
            )

        elif recent_tasks[0].get("next_blocker") != "scope_quarantine":
            errors.append(
                "mvp-wrapper-service-reconcile-status-before-json missing next_blocker=scope_quarantine"
            )

        elif (
            recent_tasks[0].get("next_task_id") != "task-wrapper-service-reconcile-json"
        ):
            errors.append(
                "mvp-wrapper-service-reconcile-status-before-json missing next_task_id=task-wrapper-service-reconcile-json"
            )

        else:
            reconcile_commands = recent_tasks[0].get("reconcile_commands") or {}

            if not isinstance(reconcile_commands, dict):
                errors.append(
                    "mvp-wrapper-service-reconcile-status-before-json missing reconcile_commands object"
                )

            elif (
                reconcile_commands.get("executed")
                != 'safeclaw.cmd service-reconcile --db "target/mvp/service-reconcile-json.db" --task-id "task-wrapper-service-reconcile-json" --decision executed --limit 1 --report'
            ):
                errors.append(
                    "mvp-wrapper-service-reconcile-status-before-json missing reconcile_commands.executed"
                )

            elif (
                reconcile_commands.get("not_executed")
                != 'safeclaw.cmd service-reconcile --db "target/mvp/service-reconcile-json.db" --task-id "task-wrapper-service-reconcile-json" --decision not-executed --limit 1 --report'
            ):
                errors.append(
                    "mvp-wrapper-service-reconcile-status-before-json missing reconcile_commands.not_executed"
                )

    result = assert_command_json_result(
        [
            "cmd",
            "/c",
            "tools\mvp\safeclaw_mvp.cmd",
            "service-reconcile",
            "--db",
            "target/mvp/service-reconcile-json.db",
            "--task-id",
            "task-wrapper-service-reconcile-json",
            "--decision",
            "executed",
            "--limit",
            "1",
            "--report",
            "--json",
        ],
        errors,
        "mvp-wrapper-cmd-service-reconcile-json",
        "service-reconcile",
    )

    assert_service_reconcile_json_result(
        result,
        errors,
        "mvp-wrapper-cmd-service-reconcile-json",
        expected_db="target\mvp\service-reconcile-json.db",
        expected_db_source="flag",
        expected_task_id="task-wrapper-service-reconcile-json",
        expected_limit=1,
        expected_decision="executed",
        expected_steps=["reconcile", "service-status", "report"],
        expect_report_payload=True,
    )

    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-crash",
            "--reset",
            "--probe-mode",
            "none",
            "--task-id",
            "task-wrapper-service-reconcile-json",
            "--db",
            "target/mvp/service-reconcile-json.db",
            "--output",
            "target/mvp/service-reconcile-json.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-reconcile-json-seed-crash-ps1-json",
        "seed-crash",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-service-reconcile-json-seed-crash-ps1-json",
        expected_task_id="task-wrapper-service-reconcile-json",
        expected_db_path="target/mvp/service-reconcile-json.db",
        expected_output_path="target/mvp/service-reconcile-json.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\\mvp\\safeclaw_mvp.ps1",
            "service-reconcile",
            "--db",
            "target/mvp/service-reconcile-json.db",
            "--task-id",
            "task-wrapper-service-reconcile-json",
            "--decision",
            "executed",
            "--limit",
            "1",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-service-reconcile-json",
        "service-reconcile",
    )

    assert_service_reconcile_json_result(
        result,
        errors,
        "mvp-wrapper-ps1-service-reconcile-json",
        expected_db="target\\mvp\\service-reconcile-json.db",
        expected_db_source="flag",
        expected_task_id="task-wrapper-service-reconcile-json",
        expected_limit=1,
        expected_decision="executed",
    )

    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-crash",
            "--reset",
            "--probe-mode",
            "none",
            "--task-id",
            "task-wrapper-service-reconcile-report-json",
            "--db",
            "target/mvp/service-reconcile-report-json.db",
            "--output",
            "target/mvp/service-reconcile-report-json.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-service-reconcile-report-json-seed-crash-ps1-json",
        "seed-crash",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-service-reconcile-report-json-seed-crash-ps1-json",
        expected_task_id="task-wrapper-service-reconcile-report-json",
        expected_db_path="target/mvp/service-reconcile-report-json.db",
        expected_output_path="target/mvp/service-reconcile-report-json.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )

    result = assert_command_json_result(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "service-reconcile",
            "--db",
            "target/mvp/service-reconcile-report-json.db",
            "--task-id",
            "task-wrapper-service-reconcile-report-json",
            "--decision",
            "executed",
            "--limit",
            "1",
            "--report",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-service-reconcile-report-json",
        "service-reconcile",
    )

    assert_service_reconcile_json_result(
        result,
        errors,
        "mvp-wrapper-ps1-service-reconcile-report-json",
        expected_db="target\mvp\service-reconcile-report-json.db",
        expected_db_source="flag",
        expected_task_id="task-wrapper-service-reconcile-report-json",
        expected_limit=1,
        expected_decision="executed",
        expected_steps=["reconcile", "service-status", "report"],
        expect_report_payload=True,
    )

    with tempfile.TemporaryDirectory() as verify_mock_dir:
        write_smoke_verify_sitecustomize(Path(verify_mock_dir))
        wrapper_cmd_verify = subprocess.run(
            ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "verify", "--json"],
            env=build_smoke_pythonpath_env(Path(verify_mock_dir)),
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

    wrapper_cmd_verify_payload = load_json_payload(
        wrapper_cmd_verify,
        errors,
        "mvp-wrapper-cmd-verify-json",
        0,
    )
    wrapper_cmd_verify_result = None
    if wrapper_cmd_verify_payload is not None:
        wrapper_cmd_verify_result = extract_json_result(
            wrapper_cmd_verify_payload,
            errors,
            "mvp-wrapper-cmd-verify-json",
            "verify",
        )

    assert_verify_json_result(
        wrapper_cmd_verify_result, errors, "mvp-wrapper-cmd-verify-json"
    )

    result = assert_command_json_result(
        [
            PYTHON,
            "-c",
            "import subprocess; from tools.mvp import safeclaw_mvp as m; "
            "m.subprocess.run = lambda *args, **kwargs: subprocess.CompletedProcess("
            "args=['python', 'tools/checks/check_mvp_operator_flow.py'], "
            "returncode=0, stdout='MVP operator flow check passed.\\n', stderr=''); "
            "raise SystemExit(m.run_verify(['--json']))",
        ],
        errors,
        "mvp-wrapper-verify-json",
        "verify",
    )

    assert_verify_json_result(result, errors, "mvp-wrapper-verify-json")

    assert_command_json_error(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "verify", "--bogus", "--json"],
        errors,
        "mvp-wrapper-cmd-verify-invalid-json",
        "verify",
        expected_error_message_substring="unknown argument: --bogus",
    )

    assert_command_json_error(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "verify",
            "--bogus",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-verify-invalid-json",
        "verify",
        expected_error_message_substring="unknown argument: --bogus",
    )

    assert_command_json_error(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "verify", "--bogus", "--json"],
        errors,
        "mvp-wrapper-verify-invalid-json",
        "verify",
        expected_error_message_substring="unknown argument: --bogus",
    )

    assert_command_json_error(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "sessions", "--limit", "bad", "--json"],
        errors,
        "mvp-wrapper-invalid-sessions-json",
        "sessions",
        expected_error_message_substring="invalid --limit",
    )

    assert_command_failure_output(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "not-real-action"],
        errors,
        "mvp-wrapper-cmd-passthrough-fail",
        expected_substring="[mvp-wrapper] cargo => failed action=not-real-action exit=1",
        missing_output_label="mvp-wrapper-cmd-passthrough-fail missing failed action marker",
    )

    wrapper_passthrough_fail = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "not-real-action"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_passthrough_fail_output = (wrapper_passthrough_fail.stdout or "") + (
        wrapper_passthrough_fail.stderr or ""
    )

    if wrapper_passthrough_fail.returncode == 0:
        errors.append("mvp-wrapper-passthrough-fail 未按预期返回非 0")

    elif (
        "[mvp-wrapper] cargo => failed action=not-real-action exit=1"
        not in wrapper_passthrough_fail_output
    ):
        errors.append("mvp-wrapper-passthrough-fail 输出缺少透传失败承接提示")

    assert_command_failure_output(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "demo",
            "--bogus",
        ],
        errors,
        "mvp-wrapper-ps1-demo-fail",
        expected_exit=2,
        expected_substring="[mvp-wrapper] demo => failed step=run exit=2",
        missing_output_label="mvp-wrapper-ps1-demo-fail missing failed step marker",
    )

    wrapper_demo_fail = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "demo", "--bogus"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_demo_fail_output = (wrapper_demo_fail.stdout or "") + (
        wrapper_demo_fail.stderr or ""
    )

    if wrapper_demo_fail.returncode != 2:
        errors.append(
            f"mvp-wrapper-demo-fail 执行失败: exit={wrapper_demo_fail.returncode}"
        )

    elif "[mvp-wrapper] demo => failed step=run exit=2" not in wrapper_demo_fail_output:
        errors.append("mvp-wrapper-demo-fail 输出缺少组合动作失败承接提示")

    wrapper_session_file = REPO_ROOT / "target" / "mvp" / "last_session.json"

    wrapper_session_file.parent.mkdir(parents=True, exist_ok=True)

    wrapper_session_file.write_text("{broken", encoding="utf-8")

    wrapper_session_after_corrupt = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "session"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_session_after_corrupt_output = (
        wrapper_session_after_corrupt.stdout or ""
    ) + (wrapper_session_after_corrupt.stderr or "")

    if wrapper_session_after_corrupt.returncode != 0:
        errors.append(
            f"mvp-wrapper-session-after-corrupt 执行失败: exit={wrapper_session_after_corrupt.returncode}"
        )

    elif (
        "[mvp-wrapper] session repair => dropped invalid target\\mvp\\last_session.json"
        not in wrapper_session_after_corrupt_output
    ):
        errors.append("mvp-wrapper-session-after-corrupt 输出缺少损坏会话修复提示")

    elif (
        "[mvp-wrapper] session => none path=target\\mvp\\last_session.json"
        not in wrapper_session_after_corrupt_output
    ):
        errors.append("mvp-wrapper-session-after-corrupt 输出缺少 none/path")

    elif wrapper_session_file.exists():
        errors.append("mvp-wrapper-session-after-corrupt 未移除损坏会话文件")

    wrapper_session_file.write_text("{broken", encoding="utf-8")

    wrapper_ps1_session_after_corrupt_json = subprocess.run(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "session",
            "--json",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_ps1_session_after_corrupt_output = (
        wrapper_ps1_session_after_corrupt_json.stdout or ""
    ) + (wrapper_ps1_session_after_corrupt_json.stderr or "")

    payload = load_json_payload(
        wrapper_ps1_session_after_corrupt_json,
        errors,
        "mvp-wrapper-ps1-session-after-corrupt-json",
        expected_exit=0,
    )

    assert_json_null_result(
        payload, errors, "mvp-wrapper-ps1-session-after-corrupt-json", "session"
    )

    if (
        "[mvp-wrapper] session repair => dropped invalid target\mvp\last_session.json"
        not in wrapper_ps1_session_after_corrupt_output
    ):
        errors.append(
            "mvp-wrapper-ps1-session-after-corrupt-json missing repair notice"
        )

    elif wrapper_session_file.exists():
        errors.append(
            "mvp-wrapper-ps1-session-after-corrupt-json did not remove invalid file"
        )

    wrapper_cmd_session_after_ps1_repair = subprocess.run(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "session"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_cmd_session_after_ps1_repair_output = (
        wrapper_cmd_session_after_ps1_repair.stdout or ""
    ) + (wrapper_cmd_session_after_ps1_repair.stderr or "")

    if wrapper_cmd_session_after_ps1_repair.returncode != 0:
        errors.append(
            f"mvp-wrapper-cmd-session-after-ps1-repair failed: exit={wrapper_cmd_session_after_ps1_repair.returncode}"
        )

    elif (
        "[mvp-wrapper] session => none path=target\mvp\last_session.json"
        not in wrapper_cmd_session_after_ps1_repair_output
    ):
        errors.append("mvp-wrapper-cmd-session-after-ps1-repair missing none/path")

    wrapper_seed_crash_json = subprocess.run(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-crash",
            "--reset",
            "--task-id",
            "task-wrapper-seed-crash-json",
            "--json",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    payload = load_json_payload(
        wrapper_seed_crash_json, errors, "mvp-wrapper-seed-crash-json", expected_exit=0
    )

    if payload is not None:
        result = extract_json_result(
            payload, errors, "mvp-wrapper-seed-crash-json", "seed-crash"
        )

        if result is not None:
            prepared = result.get("prepared") or []

            session = result.get("saved_session") or {}

            if not prepared or prepared[0] != "seed-crash":
                errors.append("mvp-wrapper-seed-crash-json 缺少 prepared seed-crash")

            elif session.get("task_id") != "task-wrapper-seed-crash-json":
                errors.append(
                    "mvp-wrapper-seed-crash-json 缺少保存后的 task-wrapper-seed-crash-json 会话"
                )

            elif "task-wrapper-seed-crash-json" not in (
                result.get("captured_output") or ""
            ):
                errors.append(
                    "mvp-wrapper-seed-crash-json 缺少 task-wrapper-seed-crash-json 输出"
                )

    wrapper_recover_json = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "recover", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    payload = load_json_payload(
        wrapper_recover_json, errors, "mvp-wrapper-recover-json", expected_exit=0
    )

    if payload is not None:
        result = extract_json_result(
            payload, errors, "mvp-wrapper-recover-json", "recover"
        )

        if result is not None:
            prepared = result.get("prepared") or []

            source_hints = result.get("source_hints") or {}

            if not prepared or prepared[0] != "recover":
                errors.append("mvp-wrapper-recover-json 缺少 prepared recover")

            elif "task-wrapper-seed-crash-json" not in (
                result.get("captured_output") or ""
            ):
                errors.append(
                    "mvp-wrapper-recover-json 缺少当前会话 task-wrapper-seed-crash-json 输出"
                )

            elif (result.get("remembered_session") or {}).get(
                "task_id"
            ) != "task-wrapper-seed-crash-json":
                errors.append(
                    "mvp-wrapper-recover-json 缺少 remembered session task-wrapper-seed-crash-json"
                )

            elif source_hints.get("task_context") != "session":
                errors.append("mvp-wrapper-recover-json 缺少 task_context=session")

    result = assert_command_json_result(
        [
            "cmd",
            "/c",
            "tools\mvp\safeclaw_mvp.cmd",
            "seed-crash",
            "--reset",
            "--task-id",
            "task-wrapper-cmd-seed-crash-json",
            "--db",
            "target/mvp/cmd-seed-crash-json.db",
            "--output",
            "target/mvp/cmd-seed-crash-json.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-cmd-seed-crash-json",
        "seed-crash",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-cmd-seed-crash-json",
        expected_task_id="task-wrapper-cmd-seed-crash-json",
        expected_db_path="target/mvp/cmd-seed-crash-json.db",
        expected_output_path="target/mvp/cmd-seed-crash-json.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )

    wrapper_seed_failed_json = subprocess.run(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "seed-failed",
            "--reset",
            "--task-id",
            "task-wrapper-seed-failed-json",
            "--json",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    payload = load_json_payload(
        wrapper_seed_failed_json,
        errors,
        "mvp-wrapper-seed-failed-json",
        expected_exit=0,
    )

    if payload is not None:
        result = extract_json_result(
            payload, errors, "mvp-wrapper-seed-failed-json", "seed-failed"
        )

        if result is not None:
            prepared = result.get("prepared") or []

            session = result.get("saved_session") or {}

            if not prepared or prepared[0] != "seed-failed":
                errors.append("mvp-wrapper-seed-failed-json 缺少 prepared seed-failed")

            elif session.get("task_id") != "task-wrapper-seed-failed-json":
                errors.append(
                    "mvp-wrapper-seed-failed-json 缺少保存后的 task-wrapper-seed-failed-json 会话"
                )

            elif "task-wrapper-seed-failed-json" not in (
                result.get("captured_output") or ""
            ):
                errors.append(
                    "mvp-wrapper-seed-failed-json 缺少 task-wrapper-seed-failed-json 输出"
                )

    wrapper_retry_json = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "retry", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    payload = load_json_payload(
        wrapper_retry_json, errors, "mvp-wrapper-retry-json", expected_exit=0
    )

    if payload is not None:
        result = extract_json_result(payload, errors, "mvp-wrapper-retry-json", "retry")

        if result is not None:
            prepared = result.get("prepared") or []

            source_hints = result.get("source_hints") or {}

            if not prepared or prepared[0] != "retry":
                errors.append("mvp-wrapper-retry-json 缺少 prepared retry")

            elif "task-wrapper-seed-failed-json" not in (
                result.get("captured_output") or ""
            ):
                errors.append(
                    "mvp-wrapper-retry-json 缺少当前会话 task-wrapper-seed-failed-json 输出"
                )

            elif (result.get("remembered_session") or {}).get(
                "task_id"
            ) != "task-wrapper-seed-failed-json":
                errors.append(
                    "mvp-wrapper-retry-json 缺少 remembered session task-wrapper-seed-failed-json"
                )

            elif source_hints.get("task_context") != "session":
                errors.append("mvp-wrapper-retry-json 缺少 task_context=session")

    result = assert_command_json_result(
        [
            "cmd",
            "/c",
            "tools\mvp\safeclaw_mvp.cmd",
            "seed-failed",
            "--reset",
            "--task-id",
            "task-wrapper-cmd-seed-failed-json",
            "--db",
            "target/mvp/cmd-seed-failed-json.db",
            "--output",
            "target/mvp/cmd-seed-failed-json.txt",
            "--json",
        ],
        errors,
        "mvp-wrapper-cmd-seed-failed-json",
        "seed-failed",
    )

    assert_run_json_result(
        result,
        errors,
        "mvp-wrapper-cmd-seed-failed-json",
        expected_task_id="task-wrapper-cmd-seed-failed-json",
        expected_db_path="target/mvp/cmd-seed-failed-json.db",
        expected_output_path="target/mvp/cmd-seed-failed-json.txt",
        expected_db_source="flag",
        expected_output_source="flag",
    )

    wrapper_demo = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "demo", "--task-id", "task-wrapper-demo"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_demo_output = (wrapper_demo.stdout or "") + (wrapper_demo.stderr or "")

    if wrapper_demo.returncode != 0:
        errors.append(f"mvp-wrapper-demo 执行失败: exit={wrapper_demo.returncode}")

    elif "[mvp-wrapper] demo => run" not in wrapper_demo_output:
        errors.append("mvp-wrapper-demo 输出缺少 run 标记")

    elif "[mvp-wrapper] demo => status" not in wrapper_demo_output:
        errors.append("mvp-wrapper-demo 输出缺少 status 标记")

    elif "[mvp-wrapper] demo => report" not in wrapper_demo_output:
        errors.append("mvp-wrapper-demo 输出缺少 report 标记")

    elif (
        "[mvp] report target => task=task-wrapper-demo effect=effect-task-wrapper-demo"
        not in wrapper_demo_output
    ):
        errors.append("mvp-wrapper-demo 输出缺少 task-wrapper-demo report 目标")

    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "demo",
            "--task-id",
            "task-wrapper-demo-json",
            "--json",
        ],
        errors,
        "mvp-wrapper-demo-json",
        "demo",
    )

    if result is not None:
        steps = result.get("steps") or []

        session = result.get("session") or {}

        remembered_session = result.get("remembered_session") or {}

        if [step.get("action") for step in steps] != ["run", "status", "report"]:
            errors.append("mvp-wrapper-demo-json 步骤序列不正确")

        elif remembered_session.get("task_id") != "task-wrapper-demo-json":
            errors.append(
                "mvp-wrapper-demo-json 缺少 remembered_session task-wrapper-demo-json"
            )

        elif session.get("task_id") != "task-wrapper-demo-json":
            errors.append("mvp-wrapper-demo-json 缺少兼容 session task-wrapper-demo-json")

        else:
            assert_matching_session_alias(result, errors, "mvp-wrapper-demo-json")

            assert_step_source_hints(
                steps,
                errors,
                "mvp-wrapper-demo-json",
                [
                    (
                        "run",
                        {
                            "db": "default",
                            "output": "default",
                            "owner_id": "default",
                            "task_context": "flag",
                        },
                    ),
                    (
                        "status",
                        {
                            "db": "session",
                            "output": "session",
                            "owner_id": "session",
                            "task_context": "flag",
                        },
                    ),
                    (
                        "report",
                        {
                            "db": "session",
                            "output": "session",
                            "owner_id": "session",
                            "task_context": "flag",
                        },
                    ),
                ],
            )

    wrapper_demo_preflight = subprocess.run(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "demo",
            "--task-id",
            "task-wrapper-demo-preflight",
            "--output",
            "target/mvp/demo-preflight.txt",
            "--preflight",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_demo_preflight_output = (wrapper_demo_preflight.stdout or "") + (
        wrapper_demo_preflight.stderr or ""
    )

    if wrapper_demo_preflight.returncode != 0:
        errors.append(
            f"mvp-wrapper-demo-preflight failed: exit={wrapper_demo_preflight.returncode}"
        )

    elif "[mvp-wrapper] demo => preflight" not in wrapper_demo_preflight_output:
        errors.append("mvp-wrapper-demo-preflight missing preflight step marker")

    elif (
        "[mvp-wrapper] preflight => action=demo known=true class=local-action tier=TIER_1 writes_state=true target_scope=scope:target/mvp/demo-preflight.txt requires_write=true doctor_bypass=false perm_ctx=true perm_ctx_src=prepared-action enforce_perm=false perm=confirm perm_tier=TIER_1 perm_reason=write_scope_requires_confirmation decision=allow allowed=true offline_ready=true requires_model=false requires_sidecar=false degradation=local_only_ok reason=current_mvp_action_is_local_only"
        not in wrapper_demo_preflight_output
    ):
        errors.append("mvp-wrapper-demo-preflight missing preflight summary")

    elif "[mvp-wrapper] demo => run" not in wrapper_demo_preflight_output:
        errors.append("mvp-wrapper-demo-preflight missing run step marker")

    elif "[mvp-wrapper] demo => status" not in wrapper_demo_preflight_output:
        errors.append("mvp-wrapper-demo-preflight missing status step marker")

    elif "[mvp-wrapper] demo => report" not in wrapper_demo_preflight_output:
        errors.append("mvp-wrapper-demo-preflight missing report step marker")

    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "demo",
            "--task-id",
            "task-wrapper-demo-json",
            "--output",
            "target/mvp/demo-preflight-json.txt",
            "--preflight",
            "--json",
        ],
        errors,
        "mvp-wrapper-demo-preflight-json",
        "demo",
    )

    if result is not None:
        steps = result.get("steps") or []

        session = result.get("session") or {}

        remembered_session = result.get("remembered_session") or {}

        if [step.get("action") for step in steps] != [
            "preflight",
            "run",
            "status",
            "report",
        ]:
            errors.append("mvp-wrapper-demo-preflight-json step sequence is incorrect")

        elif remembered_session.get("task_id") != "task-wrapper-demo-json":
            errors.append(
                "mvp-wrapper-demo-preflight-json missing remembered_session task-wrapper-demo-json"
            )

        elif session.get("task_id") != "task-wrapper-demo-json":
            errors.append(
                "mvp-wrapper-demo-preflight-json missing session alias task-wrapper-demo-json"
            )

        else:
            assert_matching_session_alias(
                result, errors, "mvp-wrapper-demo-preflight-json"
            )

            assert_step_source_hints(
                steps,
                errors,
                "mvp-wrapper-demo-preflight-json",
                [
                    ("preflight", {"permission_context": "prepared-action"}),
                    (
                        "run",
                        {
                            "db": "default",
                            "output": "flag",
                            "owner_id": "default",
                            "task_context": "flag",
                        },
                    ),
                    (
                        "status",
                        {
                            "db": "session",
                            "output": "flag",
                            "owner_id": "session",
                            "task_context": "flag",
                        },
                    ),
                    (
                        "report",
                        {
                            "db": "session",
                            "output": "flag",
                            "owner_id": "session",
                            "task_context": "flag",
                        },
                    ),
                ],
            )

        assert_preflight_json_result(
            None if result is None else result.get("preflight"),
            errors,
            "mvp-wrapper-demo-preflight-json preflight",
            expected_requested_action="demo",
            expected_known=True,
            expected_action_class="local-action",
            expected_tier="TIER_1",
            expected_writes_state=True,
            expected_permission_context_source="prepared-action",
            expected_target_scope="scope:target/mvp/demo-preflight-json.txt",
            expected_requires_write=True,
            expected_doctor_bypass=False,
            expected_permission_context_applied=True,
            expected_permission_tier="TIER_1",
            expected_permission_policy="confirm",
            expected_permission_reason="write_scope_requires_confirmation",
            expected_permission_enforced=False,
            expected_action_allowed=True,
            expected_action_decision="allow",
            expected_action_reason="current_mvp_action_is_local_only",
            expected_allowed=True,
            expected_decision="allow",
            expected_offline_ready=True,
            expected_degradation_mode="local_only_ok",
            expected_reason="current_mvp_action_is_local_only",
        )

    details = assert_command_json_error(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "demo",
            "--task-id",
            "task-wrapper-demo-enforced",
            "--output",
            "target/mvp/demo-enforced.txt",
            "--enforce-permission",
            "--json",
        ],
        errors,
        "mvp-wrapper-demo-enforced-json",
        "demo",
        expected_exit=1,
        expected_error_message_substring="failed step=preflight",
        expected_top_level_error_code="preflight-blocked",
        expected_top_level_error_reason="write_scope_requires_confirmation",
        expect_top_level_error_error_code_absent=True,
        expected_top_level_error_degradation_mode="local_only_ok",
        expected_top_level_error_requires_model=False,
        expected_top_level_error_requires_sidecar=False,
        expected_top_level_error_requested_action="demo",
        expected_code="preflight-blocked",
        expected_failed_step="preflight",
        expected_preflight_requested_action="demo",
        expected_preflight_reason="write_scope_requires_confirmation",
        expect_preflight_error_code_absent=True,
        expected_preflight_summary_substring="action=demo",
        expect_top_level_error_summary_matches_preflight=True,
    )

    if isinstance(details, dict):
        preflight_payload = details.get("preflight")

        if not isinstance(preflight_payload, dict):
            errors.append("mvp-wrapper-demo-enforced-json missing preflight payload")

        else:
            assert_preflight_json_result(
                preflight_payload,
                errors,
                "mvp-wrapper-demo-enforced-json preflight",
                expected_requested_action="demo",
                expected_known=True,
                expected_action_class="local-action",
                expected_tier="TIER_1",
                expected_writes_state=True,
                expected_permission_context_source="prepared-action",
                expected_target_scope="scope:target/mvp/demo-enforced.txt",
                expected_requires_write=True,
                expected_doctor_bypass=False,
                expected_permission_context_applied=True,
                expected_permission_tier="TIER_1",
                expected_permission_policy="confirm",
                expected_permission_reason="write_scope_requires_confirmation",
                expected_permission_enforced=True,
                expected_action_allowed=True,
                expected_action_decision="allow",
                expected_action_reason="current_mvp_action_is_local_only",
                expected_allowed=False,
                expected_decision="confirm",
                expected_offline_ready=True,
                expected_degradation_mode="local_only_ok",
                expected_reason="write_scope_requires_confirmation",
            )

        steps = details.get("steps") or []

        if (
            not isinstance(steps, list)
            or len(steps) != 1
            or not isinstance(steps[0], dict)
        ):
            errors.append(
                "mvp-wrapper-demo-enforced-json missing isolated preflight step"
            )

        elif steps[0].get("action") != "preflight":
            errors.append(
                "mvp-wrapper-demo-enforced-json missing preflight step action"
            )

    details = assert_command_json_error(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "demo",
            "--task-id",
            "task-wrapper-demo-preflight-ai",
            "--output",
            "target/mvp/demo-preflight-ai.txt",
            "--preflight",
            "--preflight-action",
            "ai-reason",
            "--json",
        ],
        errors,
        "mvp-wrapper-demo-preflight-ai-json",
        "demo",
        expected_exit=1,
        expected_error_message_substring="failed step=preflight",
        expected_top_level_error_code="preflight-blocked",
        expected_top_level_error_reason="ERR_AI_PROVIDER_UNAVAILABLE",
        expected_top_level_error_error_code="ERR_AI_PROVIDER_UNAVAILABLE",
        expected_top_level_error_degradation_mode="provider_unavailable",
        expected_top_level_error_requires_model=True,
        expected_top_level_error_requires_sidecar=True,
        expected_top_level_error_requested_action="ai-reason",
        expected_code="preflight-blocked",
        expected_failed_step="preflight",
        expected_preflight_requested_action="ai-reason",
        expected_preflight_reason="ERR_AI_PROVIDER_UNAVAILABLE",
        expected_preflight_error_code="ERR_AI_PROVIDER_UNAVAILABLE",
        expected_preflight_summary_substring="action=ai-reason",
        expect_top_level_error_summary_matches_preflight=True,
    )

    if isinstance(details, dict):
        preflight_payload = details.get("preflight")

        if not isinstance(preflight_payload, dict):
            errors.append(
                "mvp-wrapper-demo-preflight-ai-json missing preflight payload"
            )

        else:
            assert_preflight_json_result(
                preflight_payload,
                errors,
                "mvp-wrapper-demo-preflight-ai-json preflight",
                expected_requested_action="ai-reason",
                expected_known=True,
                expected_action_class="ai-action",
                expected_tier="TIER_2",
                expected_writes_state=False,
                expected_permission_context_source="prepared-action",
                expected_target_scope="scope:target/mvp/demo-preflight-ai.txt",
                expected_requires_write=True,
                expected_doctor_bypass=False,
                expected_permission_context_applied=True,
                expected_permission_tier="TIER_1",
                expected_permission_policy="confirm",
                expected_permission_reason="write_scope_requires_confirmation",
                expected_permission_enforced=False,
                expected_action_allowed=False,
                expected_action_decision="deny",
                expected_action_reason="ERR_AI_PROVIDER_UNAVAILABLE",
                expected_allowed=False,
                expected_decision="deny",
                expected_offline_ready=False,
                expected_degradation_mode="provider_unavailable",
                expected_reason="ERR_AI_PROVIDER_UNAVAILABLE",
                expected_requires_model=True,
                expected_requires_sidecar=True,
                expected_error_code="ERR_AI_PROVIDER_UNAVAILABLE",
            )

        steps = details.get("steps") or []

        if (
            not isinstance(steps, list)
            or len(steps) != 1
            or not isinstance(steps[0], dict)
        ):
            errors.append(
                "mvp-wrapper-demo-preflight-ai-json missing isolated preflight step"
            )

        elif steps[0].get("action") != "preflight":
            errors.append(
                "mvp-wrapper-demo-preflight-ai-json missing preflight step action"
            )

    assert_command_json_error(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "demo", "--bogus", "--json"],
        errors,
        "mvp-wrapper-cmd-demo-fail-json",
        "demo",
        expected_failed_step="run",
        expected_code="invalid-argument",
        expected_details_message_substring="unknown argument",
        details_message_label="mvp-wrapper-cmd-demo-fail-json missing unknown argument",
        expected_remembered_session_task_id="task-wrapper-demo-json",
        remembered_session_label="mvp-wrapper-cmd-demo-fail-json missing task-wrapper-demo-json",
        reject_legacy_session=True,
        legacy_session_label="mvp-wrapper-cmd-demo-fail-json should not keep legacy session",
    )

    assert_command_json_error(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "demo",
            "--bogus",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-demo-fail-json",
        "demo",
        expected_failed_step="run",
        expected_code="invalid-argument",
        expected_details_message_substring="unknown argument",
        details_message_label="mvp-wrapper-ps1-demo-fail-json missing unknown argument",
        expected_remembered_session_task_id="task-wrapper-demo-json",
        remembered_session_label="mvp-wrapper-ps1-demo-fail-json missing task-wrapper-demo-json",
        reject_legacy_session=True,
        legacy_session_label="mvp-wrapper-ps1-demo-fail-json should not keep legacy session",
    )

    assert_command_json_error(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "demo", "--bogus", "--json"],
        errors,
        "mvp-wrapper-demo-fail-json",
        "demo",
        expected_failed_step="run",
        expected_code="invalid-argument",
        expected_details_message_substring="unknown argument",
        details_message_label="mvp-wrapper-demo-fail-json 缺少 wrapper 级 unknown argument",
        expected_remembered_session_task_id="task-wrapper-demo-json",
        remembered_session_label="mvp-wrapper-demo-fail-json remembered_session 缺少 task-wrapper-demo-json",
        reject_legacy_session=True,
        legacy_session_label="mvp-wrapper-demo-fail-json 不应继续返回旧 session 字段",
    )

    details = assert_command_json_error(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "demo",
            "--task-id",
            "task-wrapper-demo-underlying-fail",
            "--output",
            "target/mvp",
            "--json",
        ],
        errors,
        "mvp-wrapper-demo-underlying-fail-json",
        "demo",
        expected_exit=1,
        expected_error_message_substring="failed step=run",
        error_message_label="mvp-wrapper-demo-underlying-fail-json 缺少组合动作失败消息",
        expected_failed_step="run",
        expected_remembered_session_task_id="task-wrapper-demo-json",
        remembered_session_label="mvp-wrapper-demo-underlying-fail-json remembered_session 缺少 task-wrapper-demo-json",
        reject_legacy_session=True,
        legacy_session_label="mvp-wrapper-demo-underlying-fail-json 不应继续返回旧 session 字段",
    )

    if details is not None:
        assert_step_source_hints(
            details.get("steps"),
            errors,
            "mvp-wrapper-demo-underlying-fail-json",
            [
                (
                    "run",
                    {
                        "db": "default",
                        "output": "flag",
                        "owner_id": "default",
                        "task_context": "flag",
                    },
                )
            ],
        )

    wrapper_recover_demo = subprocess.run(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "recover-demo",
            "--task-id",
            "task-wrapper-recover-demo",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_recover_demo_output = (wrapper_recover_demo.stdout or "") + (
        wrapper_recover_demo.stderr or ""
    )

    if wrapper_recover_demo.returncode != 0:
        errors.append(
            f"mvp-wrapper-recover-demo 执行失败: exit={wrapper_recover_demo.returncode}"
        )

    elif "[mvp-wrapper] recover-demo => seed-crash" not in wrapper_recover_demo_output:
        errors.append("mvp-wrapper-recover-demo 输出缺少 seed-crash 标记")

    elif "[mvp-wrapper] recover-demo => recover" not in wrapper_recover_demo_output:
        errors.append("mvp-wrapper-recover-demo 输出缺少 recover 标记")

    elif "[mvp-wrapper] recover-demo => report" not in wrapper_recover_demo_output:
        errors.append("mvp-wrapper-recover-demo 输出缺少 report 标记")

    elif (
        "[mvp] report target => task=task-wrapper-recover-demo effect=effect-task-wrapper-recover-demo"
        not in wrapper_recover_demo_output
    ):
        errors.append(
            "mvp-wrapper-recover-demo 输出缺少 task-wrapper-recover-demo report 目标"
        )

    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "recover-demo",
            "--task-id",
            "task-wrapper-recover-demo-json",
            "--json",
        ],
        errors,
        "mvp-wrapper-recover-demo-json",
        "recover-demo",
    )

    if result is not None:
        steps = result.get("steps") or []

        session = result.get("session") or {}

        remembered_session = result.get("remembered_session") or {}

        if [step.get("action") for step in steps] != [
            "seed-crash",
            "recover",
            "report",
        ]:
            errors.append("mvp-wrapper-recover-demo-json 步骤序列不正确")

        elif remembered_session.get("task_id") != "task-wrapper-recover-demo-json":
            errors.append(
                "mvp-wrapper-recover-demo-json 缺少 remembered_session task-wrapper-recover-demo-json"
            )

        elif session.get("task_id") != "task-wrapper-recover-demo-json":
            errors.append(
                "mvp-wrapper-recover-demo-json 缺少兼容 session task-wrapper-recover-demo-json"
            )

        else:
            assert_matching_session_alias(
                result, errors, "mvp-wrapper-recover-demo-json"
            )

            assert_step_source_hints(
                steps,
                errors,
                "mvp-wrapper-recover-demo-json",
                [
                    (
                        "seed-crash",
                        {
                            "db": "default",
                            "output": "default",
                            "owner_id": "default",
                            "task_context": "flag",
                        },
                    ),
                    (
                        "recover",
                        {
                            "db": "session",
                            "output": "session",
                            "owner_id": "session",
                            "task_context": "flag",
                        },
                    ),
                    (
                        "report",
                        {
                            "db": "session",
                            "output": "session",
                            "owner_id": "session",
                            "task_context": "flag",
                        },
                    ),
                ],
            )

    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "recover-demo",
            "--task-id",
            "task-wrapper-recover-demo-json",
            "--output",
            "target/mvp/recover-demo-preflight-json.txt",
            "--preflight",
            "--json",
        ],
        errors,
        "mvp-wrapper-recover-demo-preflight-json",
        "recover-demo",
    )

    if result is not None:
        steps = result.get("steps") or []

        session = result.get("session") or {}

        remembered_session = result.get("remembered_session") or {}

        if [step.get("action") for step in steps] != [
            "preflight",
            "seed-crash",
            "recover",
            "report",
        ]:
            errors.append(
                "mvp-wrapper-recover-demo-preflight-json step sequence is incorrect"
            )

        elif remembered_session.get("task_id") != "task-wrapper-recover-demo-json":
            errors.append(
                "mvp-wrapper-recover-demo-preflight-json missing remembered_session task-wrapper-recover-demo-json"
            )

        elif session.get("task_id") != "task-wrapper-recover-demo-json":
            errors.append(
                "mvp-wrapper-recover-demo-preflight-json missing session alias task-wrapper-recover-demo-json"
            )

        else:
            assert_matching_session_alias(
                result, errors, "mvp-wrapper-recover-demo-preflight-json"
            )

            assert_step_source_hints(
                steps,
                errors,
                "mvp-wrapper-recover-demo-preflight-json",
                [
                    ("preflight", {"permission_context": "prepared-action"}),
                    (
                        "seed-crash",
                        {
                            "db": "default",
                            "output": "flag",
                            "owner_id": "default",
                            "task_context": "flag",
                        },
                    ),
                    (
                        "recover",
                        {
                            "db": "session",
                            "output": "flag",
                            "owner_id": "session",
                            "task_context": "flag",
                        },
                    ),
                    (
                        "report",
                        {
                            "db": "session",
                            "output": "flag",
                            "owner_id": "session",
                            "task_context": "flag",
                        },
                    ),
                ],
            )

        assert_preflight_json_result(
            None if result is None else result.get("preflight"),
            errors,
            "mvp-wrapper-recover-demo-preflight-json preflight",
            expected_requested_action="recover-demo",
            expected_known=True,
            expected_action_class="local-action",
            expected_tier="TIER_1",
            expected_writes_state=True,
            expected_permission_context_source="prepared-action",
            expected_target_scope="scope:target/mvp/recover-demo-preflight-json.txt",
            expected_requires_write=True,
            expected_doctor_bypass=False,
            expected_permission_context_applied=True,
            expected_permission_tier="TIER_1",
            expected_permission_policy="confirm",
            expected_permission_reason="write_scope_requires_confirmation",
            expected_permission_enforced=False,
            expected_action_allowed=True,
            expected_action_decision="allow",
            expected_action_reason="current_mvp_action_is_local_only",
            expected_allowed=True,
            expected_decision="allow",
            expected_offline_ready=True,
            expected_degradation_mode="local_only_ok",
            expected_reason="current_mvp_action_is_local_only",
        )

    assert_command_failure_output(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "recover-demo",
            "--bogus",
        ],
        errors,
        "mvp-wrapper-ps1-recover-demo-fail",
        expected_exit=2,
        expected_substring="[mvp-wrapper] recover-demo => failed step=seed-crash exit=2",
        missing_output_label="mvp-wrapper-ps1-recover-demo-fail missing failed step marker",
    )

    wrapper_recover_demo_fail = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "recover-demo", "--bogus"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_recover_demo_fail_output = (wrapper_recover_demo_fail.stdout or "") + (
        wrapper_recover_demo_fail.stderr or ""
    )

    if wrapper_recover_demo_fail.returncode != 2:
        errors.append(
            f"mvp-wrapper-recover-demo-fail 执行失败: exit={wrapper_recover_demo_fail.returncode}"
        )

    elif (
        "[mvp-wrapper] recover-demo => failed step=seed-crash exit=2"
        not in wrapper_recover_demo_fail_output
    ):
        errors.append("mvp-wrapper-recover-demo-fail 输出缺少组合动作失败承接提示")

    assert_command_json_error(
        [
            "cmd",
            "/c",
            "tools\mvp\safeclaw_mvp.cmd",
            "recover-demo",
            "--bogus",
            "--json",
        ],
        errors,
        "mvp-wrapper-cmd-recover-demo-fail-json",
        "recover-demo",
        expected_failed_step="seed-crash",
        expected_code="invalid-argument",
        expected_details_message_substring="unknown argument",
        details_message_label="mvp-wrapper-cmd-recover-demo-fail-json missing unknown argument",
        expected_remembered_session_task_id="task-wrapper-recover-demo-json",
        remembered_session_label="mvp-wrapper-cmd-recover-demo-fail-json missing task-wrapper-recover-demo-json",
        reject_legacy_session=True,
        legacy_session_label="mvp-wrapper-cmd-recover-demo-fail-json should not keep legacy session",
    )

    assert_command_json_error(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "recover-demo",
            "--bogus",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-recover-demo-fail-json",
        "recover-demo",
        expected_failed_step="seed-crash",
        expected_code="invalid-argument",
        expected_details_message_substring="unknown argument",
        details_message_label="mvp-wrapper-ps1-recover-demo-fail-json missing unknown argument",
        expected_remembered_session_task_id="task-wrapper-recover-demo-json",
        remembered_session_label="mvp-wrapper-ps1-recover-demo-fail-json missing task-wrapper-recover-demo-json",
        reject_legacy_session=True,
        legacy_session_label="mvp-wrapper-ps1-recover-demo-fail-json should not keep legacy session",
    )

    assert_command_json_error(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "recover-demo", "--bogus", "--json"],
        errors,
        "mvp-wrapper-recover-demo-fail-json",
        "recover-demo",
        expected_failed_step="seed-crash",
        expected_code="invalid-argument",
        expected_details_message_substring="unknown argument",
        details_message_label="mvp-wrapper-recover-demo-fail-json 缺少 wrapper 级 unknown argument",
        expected_remembered_session_task_id="task-wrapper-recover-demo-json",
        remembered_session_label="mvp-wrapper-recover-demo-fail-json remembered_session 缺少 task-wrapper-recover-demo-json",
        reject_legacy_session=True,
        legacy_session_label="mvp-wrapper-recover-demo-fail-json 不应继续返回旧 session 字段",
    )

    wrapper_retry_demo = subprocess.run(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "retry-demo",
            "--task-id",
            "task-wrapper-retry-demo",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_retry_demo_output = (wrapper_retry_demo.stdout or "") + (
        wrapper_retry_demo.stderr or ""
    )

    if wrapper_retry_demo.returncode != 0:
        errors.append(
            f"mvp-wrapper-retry-demo 执行失败: exit={wrapper_retry_demo.returncode}"
        )

    elif "[mvp-wrapper] retry-demo => seed-failed" not in wrapper_retry_demo_output:
        errors.append("mvp-wrapper-retry-demo 输出缺少 seed-failed 标记")

    elif "[mvp-wrapper] retry-demo => retry" not in wrapper_retry_demo_output:
        errors.append("mvp-wrapper-retry-demo 输出缺少 retry 标记")

    elif "[mvp-wrapper] retry-demo => report" not in wrapper_retry_demo_output:
        errors.append("mvp-wrapper-retry-demo 输出缺少 report 标记")

    elif (
        "[mvp] report target => task=task-wrapper-retry-demo effect=effect-task-wrapper-retry-demo"
        not in wrapper_retry_demo_output
    ):
        errors.append("mvp-wrapper-retry-demo 输出缺少 task-wrapper-retry-demo report 目标")

    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "retry-demo",
            "--task-id",
            "task-wrapper-retry-demo-json",
            "--json",
        ],
        errors,
        "mvp-wrapper-retry-demo-json",
        "retry-demo",
    )

    if result is not None:
        steps = result.get("steps") or []

        session = result.get("session") or {}

        remembered_session = result.get("remembered_session") or {}

        if [step.get("action") for step in steps] != ["seed-failed", "retry", "report"]:
            errors.append("mvp-wrapper-retry-demo-json 步骤序列不正确")

        elif remembered_session.get("task_id") != "task-wrapper-retry-demo-json":
            errors.append(
                "mvp-wrapper-retry-demo-json 缺少 remembered_session task-wrapper-retry-demo-json"
            )

        elif session.get("task_id") != "task-wrapper-retry-demo-json":
            errors.append(
                "mvp-wrapper-retry-demo-json 缺少兼容 session task-wrapper-retry-demo-json"
            )

        else:
            assert_matching_session_alias(result, errors, "mvp-wrapper-retry-demo-json")

            assert_step_source_hints(
                steps,
                errors,
                "mvp-wrapper-retry-demo-json",
                [
                    (
                        "seed-failed",
                        {
                            "db": "default",
                            "output": "default",
                            "owner_id": "default",
                            "task_context": "flag",
                        },
                    ),
                    (
                        "retry",
                        {
                            "db": "session",
                            "output": "session",
                            "owner_id": "session",
                            "task_context": "flag",
                        },
                    ),
                    (
                        "report",
                        {
                            "db": "session",
                            "output": "session",
                            "owner_id": "session",
                            "task_context": "flag",
                        },
                    ),
                ],
            )

    result = assert_command_json_result(
        [
            PYTHON,
            "tools/mvp/safeclaw_mvp.py",
            "retry-demo",
            "--task-id",
            "task-wrapper-retry-demo-json",
            "--output",
            "target/mvp/retry-demo-preflight-json.txt",
            "--preflight",
            "--json",
        ],
        errors,
        "mvp-wrapper-retry-demo-preflight-json",
        "retry-demo",
    )

    if result is not None:
        steps = result.get("steps") or []

        session = result.get("session") or {}

        remembered_session = result.get("remembered_session") or {}

        if [step.get("action") for step in steps] != [
            "preflight",
            "seed-failed",
            "retry",
            "report",
        ]:
            errors.append(
                "mvp-wrapper-retry-demo-preflight-json step sequence is incorrect"
            )

        elif remembered_session.get("task_id") != "task-wrapper-retry-demo-json":
            errors.append(
                "mvp-wrapper-retry-demo-preflight-json missing remembered_session task-wrapper-retry-demo-json"
            )

        elif session.get("task_id") != "task-wrapper-retry-demo-json":
            errors.append(
                "mvp-wrapper-retry-demo-preflight-json missing session alias task-wrapper-retry-demo-json"
            )

        else:
            assert_matching_session_alias(
                result, errors, "mvp-wrapper-retry-demo-preflight-json"
            )

            assert_step_source_hints(
                steps,
                errors,
                "mvp-wrapper-retry-demo-preflight-json",
                [
                    ("preflight", {"permission_context": "prepared-action"}),
                    (
                        "seed-failed",
                        {
                            "db": "default",
                            "output": "flag",
                            "owner_id": "default",
                            "task_context": "flag",
                        },
                    ),
                    (
                        "retry",
                        {
                            "db": "session",
                            "output": "flag",
                            "owner_id": "session",
                            "task_context": "flag",
                        },
                    ),
                    (
                        "report",
                        {
                            "db": "session",
                            "output": "flag",
                            "owner_id": "session",
                            "task_context": "flag",
                        },
                    ),
                ],
            )

        assert_preflight_json_result(
            None if result is None else result.get("preflight"),
            errors,
            "mvp-wrapper-retry-demo-preflight-json preflight",
            expected_requested_action="retry-demo",
            expected_known=True,
            expected_action_class="local-action",
            expected_tier="TIER_1",
            expected_writes_state=True,
            expected_permission_context_source="prepared-action",
            expected_target_scope="scope:target/mvp/retry-demo-preflight-json.txt",
            expected_requires_write=True,
            expected_doctor_bypass=False,
            expected_permission_context_applied=True,
            expected_permission_tier="TIER_1",
            expected_permission_policy="confirm",
            expected_permission_reason="write_scope_requires_confirmation",
            expected_permission_enforced=False,
            expected_action_allowed=True,
            expected_action_decision="allow",
            expected_action_reason="current_mvp_action_is_local_only",
            expected_allowed=True,
            expected_decision="allow",
            expected_offline_ready=True,
            expected_degradation_mode="local_only_ok",
            expected_reason="current_mvp_action_is_local_only",
        )

    assert_command_failure_output(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "retry-demo",
            "--bogus",
        ],
        errors,
        "mvp-wrapper-ps1-retry-demo-fail",
        expected_exit=2,
        expected_substring="[mvp-wrapper] retry-demo => failed step=seed-failed exit=2",
        missing_output_label="mvp-wrapper-ps1-retry-demo-fail missing failed step marker",
    )

    wrapper_retry_demo_fail = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "retry-demo", "--bogus"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    wrapper_retry_demo_fail_output = (wrapper_retry_demo_fail.stdout or "") + (
        wrapper_retry_demo_fail.stderr or ""
    )

    if wrapper_retry_demo_fail.returncode != 2:
        errors.append(
            f"mvp-wrapper-retry-demo-fail 执行失败: exit={wrapper_retry_demo_fail.returncode}"
        )

    elif (
        "[mvp-wrapper] retry-demo => failed step=seed-failed exit=2"
        not in wrapper_retry_demo_fail_output
    ):
        errors.append("mvp-wrapper-retry-demo-fail 输出缺少组合动作失败承接提示")

    assert_command_json_error(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "retry-demo", "--bogus", "--json"],
        errors,
        "mvp-wrapper-cmd-retry-demo-fail-json",
        "retry-demo",
        expected_failed_step="seed-failed",
        expected_code="invalid-argument",
        expected_details_message_substring="unknown argument",
        details_message_label="mvp-wrapper-cmd-retry-demo-fail-json missing unknown argument",
        expected_remembered_session_task_id="task-wrapper-retry-demo-json",
        remembered_session_label="mvp-wrapper-cmd-retry-demo-fail-json missing task-wrapper-retry-demo-json",
        reject_legacy_session=True,
        legacy_session_label="mvp-wrapper-cmd-retry-demo-fail-json should not keep legacy session",
    )

    assert_command_json_error(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "retry-demo",
            "--bogus",
            "--json",
        ],
        errors,
        "mvp-wrapper-ps1-retry-demo-fail-json",
        "retry-demo",
        expected_failed_step="seed-failed",
        expected_code="invalid-argument",
        expected_details_message_substring="unknown argument",
        details_message_label="mvp-wrapper-ps1-retry-demo-fail-json missing unknown argument",
        expected_remembered_session_task_id="task-wrapper-retry-demo-json",
        remembered_session_label="mvp-wrapper-ps1-retry-demo-fail-json missing task-wrapper-retry-demo-json",
        reject_legacy_session=True,
        legacy_session_label="mvp-wrapper-ps1-retry-demo-fail-json should not keep legacy session",
    )

    assert_command_json_error(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "retry-demo", "--bogus", "--json"],
        errors,
        "mvp-wrapper-retry-demo-fail-json",
        "retry-demo",
        expected_failed_step="seed-failed",
        expected_code="invalid-argument",
        expected_details_message_substring="unknown argument",
        details_message_label="mvp-wrapper-retry-demo-fail-json 缺少 wrapper 级 unknown argument",
        expected_remembered_session_task_id="task-wrapper-retry-demo-json",
        remembered_session_label="mvp-wrapper-retry-demo-fail-json remembered_session 缺少 task-wrapper-retry-demo-json",
        reject_legacy_session=True,
        legacy_session_label="mvp-wrapper-retry-demo-fail-json 不应继续返回旧 session 字段",
    )

    root_index = REPO_ROOT / "generated" / "index.json"

    if not root_index.exists():
        errors.append(f"缺少 codegen 产物: {root_index.relative_to(REPO_ROOT).as_posix()}")

    for target in ("rust", "python", "ts"):
        manifest_path = REPO_ROOT / "generated" / target / "manifest.json"

        stable_ids_path = REPO_ROOT / "generated" / target / "stable_ids.json"

        if not manifest_path.exists():
            errors.append(
                f"缺少 codegen 产物: {manifest_path.relative_to(REPO_ROOT).as_posix()}"
            )

        if not stable_ids_path.exists():
            errors.append(
                f"缺少 codegen 产物: {stable_ids_path.relative_to(REPO_ROOT).as_posix()}"
            )

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)

        old_path = temp_root / "old.json"

        new_path = temp_root / "new.json"

        json_out = temp_root / "diff.json"

        old_path.write_text(json.dumps({"version": "0.1.1", "a": 1}), encoding="utf-8")

        new_path.write_text(
            json.dumps({"version": "0.1.2", "a": 2, "b": 3}), encoding="utf-8"
        )

        json_run = subprocess.run(
            [
                PYTHON,
                "tools/schema_diff/main.py",
                str(old_path),
                str(new_path),
                "--json-out",
                str(json_out),
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        if json_run.returncode != 0:
            errors.append(f"schema-diff json 输出执行失败: exit={json_run.returncode}")

        elif not json_out.exists():
            errors.append("schema-diff 未生成 JSON 输出文件")

        else:
            payload = load_json_file_payload(json_out, errors, "schema-diff JSON 输出")

            if payload is not None:
                if payload.get("mode") != "file":
                    errors.append("schema-diff JSON 输出 mode 不正确")

                if "added_keys" not in payload or "changed_keys" not in payload:
                    errors.append("schema-diff JSON 输出缺少关键字段")

        fail_run = subprocess.run(
            [
                PYTHON,
                "tools/schema_diff/main.py",
                str(old_path),
                str(new_path),
                "--fail-on-diff",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        if fail_run.returncode == 0:
            errors.append("schema-diff 在存在差异时未按预期返回非 0")

    return errors


def _main() -> int:
    errors = collect_errors()

    if errors:
        print("Tooling smoke check failed:")

        for item in errors:
            print(f"- {item}")

        return 1

    print("Tooling smoke check passed.")

    return 0


def main() -> int:
    try:
        with acquire_mvp_state_lock("check_tooling_smoke"):
            return _main()

    except RuntimeError as error:
        print(f"Tooling smoke check failed: {error}")

        return 1


if __name__ == "__main__":
    raise SystemExit(main())
