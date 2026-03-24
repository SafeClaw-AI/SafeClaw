from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON = sys.executable
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
        [PYTHON, "tools/schema_diff/main.py", "specs/schemas/action_tiers.json", "specs/schemas/action_tiers.json"],
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
    except json.JSONDecodeError:
        errors.append(f"{name} 输出不是合法 JSON")
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


def assert_doctor_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    expected_db_path: str,
    expected_output_path: str,
) -> None:
    if result is None:
        return
    python_info = result.get("python") or {}
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
    elif result.get("db", {}).get("path") != expected_db_path:
        errors.append(f"{name} missing db path={expected_db_path}")
    elif result.get("db", {}).get("source") != "flag":
        errors.append(f"{name} missing db source=flag")
    elif result.get("output", {}).get("path") != expected_output_path:
        errors.append(f"{name} missing output path={expected_output_path}")
    elif result.get("output", {}).get("source") != "flag":
        errors.append(f"{name} missing output source=flag")


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
    normalized_saved_output = str(saved_session.get("output") or "").replace("/", chr(92))
    normalized_expected_db = None if expected_db_path is None else expected_db_path.replace("/", chr(92))
    normalized_expected_output = None if expected_output_path is None else expected_output_path.replace("/", chr(92))
    if not isinstance(saved_session, dict) or saved_session.get("task_id") != expected_task_id:
        errors.append(f"{name} missing saved_session task_id={expected_task_id}")
    elif normalized_expected_db is not None and normalized_saved_db != normalized_expected_db:
        errors.append(f"{name} missing saved_session db={expected_db_path}")
    elif normalized_expected_output is not None and normalized_saved_output != normalized_expected_output:
        errors.append(f"{name} missing saved_session output={expected_output_path}")
    elif not isinstance(remembered_session, dict) or remembered_session != saved_session:
        errors.append(f"{name} missing remembered_session mirror")
    elif not isinstance(source_hints, dict) or source_hints.get("db") != expected_db_source:
        errors.append(f"{name} missing source_hints.db={expected_db_source}")
    elif source_hints.get("output") != expected_output_source:
        errors.append(f"{name} missing source_hints.output={expected_output_source}")
    elif source_hints.get("owner_id") != expected_owner_source:
        errors.append(f"{name} missing source_hints.owner_id={expected_owner_source}")
    elif source_hints.get("task_context") != expected_task_context_source:
        errors.append(f"{name} missing source_hints.task_context={expected_task_context_source}")
    elif normalized_expected_db is not None and normalized_expected_db not in captured_output:
        errors.append(f"{name} missing captured db path")
    elif normalized_expected_output is not None and normalized_expected_output not in captured_output:
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
    if result.get("task_id") != expected_task_id or result.get("source") != expected_source:
        errors.append(f"{name} missing task_id/source")
    elif result.get("db_source") != "session":
        errors.append(f"{name} missing db_source=session")
    elif result.get("output_source") != "session":
        errors.append(f"{name} missing output_source=session")
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
    elif not isinstance(remembered_session, dict) or remembered_session.get("task_id") != expected_task_id:
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
    elif not isinstance(current_session, dict) or current_session.get("task_id") != expected_current_task_id:
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


def load_json_file_payload(path: Path, errors: list[str], name: str) -> dict[str, object] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        errors.append(f"{name} 读取失败: {exc}")
        return None
    except json.JSONDecodeError:
        errors.append(f"{name} 输出不是合法 JSON")
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
    expected_code: str | None = None,
    expected_failed_step: str | None = None,
    expected_details_message_substring: str | None = None,
    details_message_field: str = "error_message",
    details_message_label: str | None = None,
    expected_remembered_session_task_id: str | None = None,
    remembered_session_label: str | None = None,
    expect_no_remembered_session: bool = False,
) -> None:
    if error is None:
        return
    if expected_error_message_substring is not None:
        if expected_error_message_substring not in str(error.get("message", "")):
            errors.append(error_message_label or f"{name} 输出缺少错误信息")
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
        if expected_details_message_substring not in str(details.get(details_message_field, "")):
            errors.append(details_message_label or f"{name} 缺少错误明细")
            return
    if expect_no_remembered_session:
        if details.get("remembered_session") is not None:
            errors.append(f"{name} remembered_session 预期为空")
            return
    if expected_remembered_session_task_id is not None:
        remembered_session = details.get("remembered_session") or {}
        if not isinstance(remembered_session, dict) or remembered_session.get("task_id") != expected_remembered_session_task_id:
            errors.append(remembered_session_label or f"{name} remembered_session 缺少 {expected_remembered_session_task_id}")


def run_wrapper_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True)


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
) -> None:
    payload = load_json_payload(run_wrapper_command(command), errors, name, expected_exit)
    if payload is None:
        return
    error, details = extract_json_error(payload, errors, name, action)
    assert_json_error_fields(error, details, errors, name, **error_expectations)
    if reject_legacy_session and details is not None and details.get("session") is not None:
        errors.append(legacy_session_label or f"{name} should not keep legacy session")


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


def collect_errors() -> list[str]:
    errors: list[str] = []

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

    wrapper_help = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    wrapper_help_output = (wrapper_help.stdout or "") + (wrapper_help.stderr or "")
    if wrapper_help.returncode != 0:
        errors.append(f"mvp-wrapper-help 执行失败: exit={wrapper_help.returncode}")
    elif "[mvp-wrapper] usage => tools\\mvp\\safeclaw_mvp.cmd <action> [flags]" not in wrapper_help_output:
        errors.append("mvp-wrapper-help 输出缺少包装入口说明")
    elif "[mvp-wrapper] local actions => demo, recover-demo, retry-demo, session, sessions, use, forget, doctor" not in wrapper_help_output:
        errors.append("mvp-wrapper-help 输出缺少本地动作列表")
    elif "[mvp-wrapper] examples => demo | recover-demo | retry-demo | session | sessions --limit 5 | use --index 0 | use --task-id task-demo | status --task-id task-demo | report --task-id task-demo | forget | doctor" not in wrapper_help_output:
        errors.append("mvp-wrapper-help 输出缺少 task-id/status/report 示例提示")
    elif "[mvp-wrapper] demo flows => demo=run->status->report；recover-demo=seed-crash->recover->report；retry-demo=seed-failed->retry->report" not in wrapper_help_output:
        errors.append("mvp-wrapper-help 输出缺少 demo 链路提示")
    elif "[mvp-wrapper] failure flows => run 直接执行到完成；seed-crash/recover 演示 uncertain 恢复；seed-failed/retry 演示失败态重试" not in wrapper_help_output:
        errors.append("mvp-wrapper-help 输出缺少异常链提示")
    elif "[mvp-wrapper] json => demo/recover-demo/retry-demo/run/report/status/seed-crash/recover/seed-failed/retry/session/sessions/use/forget/doctor 支持 --json，统一返回 {ok, action, schema_version, result|error} 信封" not in wrapper_help_output:
        errors.append("mvp-wrapper-help 输出缺少 JSON 信封提示")
    elif "[mvp-wrapper] errors => invalid-argument / missing-task-context；组合动作 JSON 失败会额外附带 failed_step / code / error_message" not in wrapper_help_output:
        errors.append("mvp-wrapper-help 输出缺少 JSON 错误码提示")
    elif "[mvp-wrapper] error hints => invalid-argument 多为未知参数或 flag 缺值；missing-task-context 时请传 --task-id，或先 use/run/seed-crash/seed-failed 建立上下文" not in wrapper_help_output:
        errors.append("mvp-wrapper-help 输出缺少错误码解释提示")
    elif "[mvp-wrapper] error message => error.message 是稳定的 wrapper 级消息；脚本无需解析底层 cargo 文案" not in wrapper_help_output:
        errors.append("mvp-wrapper-help 输出缺少稳定 error.message 提示")
    elif "[mvp-wrapper] error session => 包装层错误 JSON 若当前存在 remembered session；会在 error.details.remembered_session 附带它" not in wrapper_help_output:
        errors.append("mvp-wrapper-help 输出缺少错误 remembered_session 提示")
    elif "[mvp-wrapper] session => session 显示当前记忆的最近成功会话；sessions/use/forget 管理 remembered session；status/report/recover/retry/doctor 会尽量复用它" not in wrapper_help_output:
        errors.append("mvp-wrapper-help 输出缺少 session 最近成功会话提示")
    elif "[mvp-wrapper] status/report => status 默认查看当前 remembered session，也可显式传 --task-id；report 查看指定 task/effect 的治理视图" not in wrapper_help_output:
        errors.append("mvp-wrapper-help 输出缺少 status/report 语义提示")
    elif "[mvp-wrapper] doctor => 文本模式会检查包装入口、cargo/toolchain/linker、remembered session 路径，并给出 db/output 来源；--json 会额外返回 status 与 failing_checks" not in wrapper_help_output:
        errors.append("mvp-wrapper-help 输出缺少 doctor 检查项提示")
    elif "[mvp-wrapper] source hints => status/report/recover/retry --json 会额外返回 result.source_hints；可直接看到 db/output/owner_id/task_context 来源" not in wrapper_help_output:
        errors.append("mvp-wrapper-help 输出缺少 source_hints 提示")
    elif "[mvp-wrapper] combo source hints => demo/recover-demo/retry-demo --json 的 result.steps[*] / error.details.steps[*] 也会带 source_hints" not in wrapper_help_output:
        errors.append("mvp-wrapper-help 输出缺少组合动作 source_hints 提示")
    elif "[mvp-wrapper] combo session => demo/recover-demo/retry-demo --json 会返回 result.remembered_session；result.session 仅作兼容别名，脚本应优先读取 remembered_session" not in wrapper_help_output:
        errors.append("mvp-wrapper-help 输出缺少组合动作 remembered_session 提示")
    elif "[mvp-wrapper] session list => sessions 会列出当前 db 的最近任务快照；use 可按 --index / --task-id 激活其中一条" not in wrapper_help_output:
        errors.append("mvp-wrapper-help 输出缺少 sessions 快照提示")
    elif "[mvp-wrapper] session selectors => status 可显式传 --task-id；use 支持 --index / --task-id 选择历史会话" not in wrapper_help_output:
        errors.append("mvp-wrapper-help 输出缺少 session 选择方式提示")
    elif "[mvp-wrapper] session sources => sessions 默认优先复用 remembered session 的 db，文本/JSON 都会标 source；use 文本/JSON 都会标选择来源与 db/output/owner 来源，--json 会返回 source/db_source/output_source/owner_id_source" not in wrapper_help_output:
        errors.append("mvp-wrapper-help 输出缺少 use 来源提示")
    elif "[mvp-wrapper] session paths => session 文本输出会带 remembered session 文件路径；forget 文本/JSON 会显式给出 reason/path，且不删除 db/output 文件" not in wrapper_help_output:
        errors.append("mvp-wrapper-help 输出缺少 forget 保留文件提示")
    elif "[mvp-wrapper] session repair => remembered session 文件损坏时会自动丢弃并回退为 session => none" not in wrapper_help_output:
        errors.append("mvp-wrapper-help 输出缺少 session repair 提示")

    wrapper_cmd_help = subprocess.run(
        ["cmd", "/c", "tools\\mvp\\safeclaw_mvp.cmd", "help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    wrapper_cmd_help_output = (wrapper_cmd_help.stdout or "") + (wrapper_cmd_help.stderr or "")
    if wrapper_cmd_help.returncode != 0:
        errors.append(f"mvp-wrapper-cmd-help 执行失败: exit={wrapper_cmd_help.returncode}")
    elif "[mvp-wrapper] usage => tools\\mvp\\safeclaw_mvp.cmd <action> [flags]" not in wrapper_cmd_help_output:
        errors.append("mvp-wrapper-cmd-help 输出缺少 usage")

    wrapper_ps1_help = subprocess.run(
        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", "tools\\mvp\\safeclaw_mvp.ps1", "help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    wrapper_ps1_help_output = (wrapper_ps1_help.stdout or "") + (wrapper_ps1_help.stderr or "")
    if wrapper_ps1_help.returncode != 0:
        errors.append(f"mvp-wrapper-ps1-help 执行失败: exit={wrapper_ps1_help.returncode}")
    elif "[mvp-wrapper] usage => tools\\mvp\\safeclaw_mvp.cmd <action> [flags]" not in wrapper_ps1_help_output:
        errors.append("mvp-wrapper-ps1-help 输出缺少 usage")

    wrapper_cmd_doctor_json = subprocess.run(
        [
            "cmd",
            "/c",
            "tools\mvp\safeclaw_mvp.cmd",
            "doctor",
            "--db",
            "target\mvp\doctor-wrapper-cmd.db",
            "--output",
            "target\mvp\doctor-wrapper-cmd.txt",
            "--json",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    payload = load_json_payload(wrapper_cmd_doctor_json, errors, "mvp-wrapper-cmd-doctor-json", expected_exit=0)
    if payload is not None:
        result = extract_json_result(payload, errors, "mvp-wrapper-cmd-doctor-json", "doctor")
        assert_doctor_json_result(
            result,
            errors,
            "mvp-wrapper-cmd-doctor-json",
            expected_db_path="target\mvp\doctor-wrapper-cmd.db",
            expected_output_path="target\mvp\doctor-wrapper-cmd.txt",
        )

    wrapper_ps1_doctor_json = subprocess.run(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\mvp\safeclaw_mvp.ps1",
            "doctor",
            "--db",
            "target\mvp\doctor-wrapper-ps1.db",
            "--output",
            "target\mvp\doctor-wrapper-ps1.txt",
            "--json",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    payload = load_json_payload(wrapper_ps1_doctor_json, errors, "mvp-wrapper-ps1-doctor-json", expected_exit=0)
    if payload is not None:
        result = extract_json_result(payload, errors, "mvp-wrapper-ps1-doctor-json", "doctor")
        assert_doctor_json_result(
            result,
            errors,
            "mvp-wrapper-ps1-doctor-json",
            expected_db_path="target\mvp\doctor-wrapper-ps1.db",
            expected_output_path="target\mvp\doctor-wrapper-ps1.txt",
        )

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
    elif "[mvp-wrapper] doctor entry => ok cmd=tools\\mvp\\safeclaw_mvp.cmd ps1=tools\\mvp\\safeclaw_mvp.ps1 py=tools\\mvp\\safeclaw_mvp.py" not in wrapper_doctor_output:
        errors.append("mvp-wrapper-doctor 输出缺少入口检查")
    elif "[mvp-wrapper] doctor cargo => ok" not in wrapper_doctor_output:
        errors.append("mvp-wrapper-doctor 输出缺少 cargo 检查")
    elif "[mvp-wrapper] doctor toolchain => ok" not in wrapper_doctor_output:
        errors.append("mvp-wrapper-doctor 输出缺少 toolchain 检查")
    elif "[mvp-wrapper] doctor linker => ok" not in wrapper_doctor_output:
        errors.append("mvp-wrapper-doctor 输出缺少 linker 检查")
    elif "[mvp-wrapper] doctor session_path => target\\mvp\\last_session.json" not in wrapper_doctor_output:
        errors.append("mvp-wrapper-doctor 输出缺少 session_path")
    elif "[mvp-wrapper] doctor source => db=flag output=flag" not in wrapper_doctor_output:
        errors.append("mvp-wrapper-doctor 输出缺少来源提示")
    elif "[mvp-wrapper] doctor summary => ready" not in wrapper_doctor_output:
        errors.append("mvp-wrapper-doctor 输出缺少聚合状态提示")

    wrapper_doctor_json = subprocess.run(
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
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    payload = load_json_payload(wrapper_doctor_json, errors, "mvp-wrapper-doctor-json", expected_exit=0)
    if payload is not None:
        result = extract_json_result(payload, errors, "mvp-wrapper-doctor-json", "doctor")
        assert_doctor_json_result(
            result,
            errors,
            "mvp-wrapper-doctor-json",
            expected_db_path="target\mvp\doctor-check.db",
            expected_output_path="target\mvp\doctor-check.txt",
        )

    space_wrapper_dir = REPO_ROOT / "target" / "mvp" / "space wrapper"
    space_wrapper_dir.mkdir(parents=True, exist_ok=True)

    wrapper_cmd_run_json = subprocess.run(
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
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    payload = load_json_payload(wrapper_cmd_run_json, errors, "mvp-wrapper-cmd-run-json", expected_exit=0)
    if payload is not None:
        result = extract_json_result(payload, errors, "mvp-wrapper-cmd-run-json", "run")
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

    wrapper_ps1_run_json = subprocess.run(
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
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    payload = load_json_payload(wrapper_ps1_run_json, errors, "mvp-wrapper-ps1-run-json", expected_exit=0)
    if payload is not None:
        result = extract_json_result(payload, errors, "mvp-wrapper-ps1-run-json", "run")
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

    wrapper_run_json = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "run", "--reset", "--task-id", "task-wrapper-json", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    payload = load_json_payload(wrapper_run_json, errors, "mvp-wrapper-run-json", expected_exit=0)
    if payload is not None:
        result = extract_json_result(payload, errors, "mvp-wrapper-run-json", "run")
        assert_run_json_result(
            result,
            errors,
            "mvp-wrapper-run-json",
            expected_task_id="task-wrapper-json",
            expected_db_source="default",
            expected_output_source="default",
        )

    wrapper_run_a = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "run", "--reset", "--task-id", "task-wrapper-a"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    wrapper_run_a_output = (wrapper_run_a.stdout or "") + (wrapper_run_a.stderr or "")
    if wrapper_run_a.returncode != 0:
        errors.append(f"mvp-wrapper-run-a 执行失败: exit={wrapper_run_a.returncode}")
    elif "[mvp] accepted task => task=task-wrapper-a effect=effect-task-wrapper-a" not in wrapper_run_a_output:
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
    elif "[mvp] accepted task => task=task-wrapper-b effect=effect-task-wrapper-b" not in wrapper_run_b_output:
        errors.append("mvp-wrapper-run-b 输出缺少 task-wrapper-b")

    wrapper_status = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "status"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    wrapper_status_output = (wrapper_status.stdout or "") + (wrapper_status.stderr or "")
    if wrapper_status.returncode != 0:
        errors.append(f"mvp-wrapper-status 执行失败: exit={wrapper_status.returncode}")
    elif "[mvp] status target => task=task-wrapper-b effect=effect-task-wrapper-b" not in wrapper_status_output:
        errors.append("mvp-wrapper-status 输出缺少当前会话 task-wrapper-b")

    wrapper_status_json = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "status", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    payload = load_json_payload(wrapper_status_json, errors, "mvp-wrapper-status-json", expected_exit=0)
    if payload is not None:
        result = extract_json_result(payload, errors, "mvp-wrapper-status-json", "status")
        if result is not None:
            prepared = result.get("prepared") or []
            source_hints = result.get("source_hints") or {}
            if not prepared or prepared[0] != "status":
                errors.append("mvp-wrapper-status-json 缺少 prepared status")
            elif "task-wrapper-b" not in (result.get("captured_output") or ""):
                errors.append("mvp-wrapper-status-json 缺少当前会话 task-wrapper-b 输出")
            elif source_hints.get("task_context") != "session":
                errors.append("mvp-wrapper-status-json 缺少 task_context=session")

    wrapper_cmd_status_fail_json = subprocess.run(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "status", "--bogus", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    payload = load_json_payload(wrapper_cmd_status_fail_json, errors, "mvp-wrapper-cmd-status-fail-json", expected_exit=2)
    if payload is not None:
        error, details = extract_json_error(payload, errors, "mvp-wrapper-cmd-status-fail-json", "status")
        assert_json_error_fields(
            error,
            details,
            errors,
            "mvp-wrapper-cmd-status-fail-json",
            expected_error_message_substring="unknown argument",
            error_message_label="mvp-wrapper-cmd-status-fail-json missing unknown argument",
            expected_code="invalid-argument",
            expected_remembered_session_task_id="task-wrapper-b",
            remembered_session_label="mvp-wrapper-cmd-status-fail-json missing task-wrapper-b",
        )

    wrapper_ps1_status_missing_db_json = subprocess.run(
        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", "tools\mvp\safeclaw_mvp.ps1", "status", "--db", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    payload = load_json_payload(wrapper_ps1_status_missing_db_json, errors, "mvp-wrapper-ps1-status-missing-db-json", expected_exit=2)
    if payload is not None:
        error, details = extract_json_error(payload, errors, "mvp-wrapper-ps1-status-missing-db-json", "status")
        assert_json_error_fields(
            error,
            details,
            errors,
            "mvp-wrapper-ps1-status-missing-db-json",
            expected_error_message_substring="missing value after --db",
            error_message_label="mvp-wrapper-ps1-status-missing-db-json missing value after --db",
            expected_code="invalid-argument",
            expected_remembered_session_task_id="task-wrapper-b",
            remembered_session_label="mvp-wrapper-ps1-status-missing-db-json missing task-wrapper-b",
        )

    wrapper_status_fail_json = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "status", "--bogus", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    payload = load_json_payload(wrapper_status_fail_json, errors, "mvp-wrapper-status-fail-json", expected_exit=2)
    if payload is not None:
        error, details = extract_json_error(payload, errors, "mvp-wrapper-status-fail-json", "status")
        assert_json_error_fields(
            error,
            details,
            errors,
            "mvp-wrapper-status-fail-json",
            expected_error_message_substring="unknown argument",
            error_message_label="mvp-wrapper-status-fail-json 缺少 wrapper 级 unknown argument",
            expected_code="invalid-argument",
            expected_remembered_session_task_id="task-wrapper-b",
            remembered_session_label="mvp-wrapper-status-fail-json remembered_session 缺少 task-wrapper-b",
        )

    wrapper_status_missing_db_json = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "status", "--db", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    payload = load_json_payload(wrapper_status_missing_db_json, errors, "mvp-wrapper-status-missing-db-json", expected_exit=2)
    if payload is not None:
        error, details = extract_json_error(payload, errors, "mvp-wrapper-status-missing-db-json", "status")
        assert_json_error_fields(
            error,
            details,
            errors,
            "mvp-wrapper-status-missing-db-json",
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
    wrapper_session_output = (wrapper_session.stdout or "") + (wrapper_session.stderr or "")
    if wrapper_session.returncode != 0:
        errors.append(f"mvp-wrapper-session 执行失败: exit={wrapper_session.returncode}")
    elif "[mvp-wrapper] session => task=task-wrapper-b effect=effect-task-wrapper-b" not in wrapper_session_output:
        errors.append("mvp-wrapper-session 输出缺少当前会话 task-wrapper-b")
    elif "path=target\\mvp\\last_session.json" not in wrapper_session_output:
        errors.append("mvp-wrapper-session 输出缺少 remembered session 路径")

    wrapper_session_json = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "session", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    wrapper_session_json_output = (wrapper_session_json.stdout or "") + (wrapper_session_json.stderr or "")
    payload = load_json_payload(wrapper_session_json, errors, "mvp-wrapper-session-json", expected_exit=0)
    if payload is not None:
        result = extract_json_result(payload, errors, "mvp-wrapper-session-json", "session")
        if result is not None:
            if result.get("task_id") != "task-wrapper-b" or result.get("effect_id") != "effect-task-wrapper-b":
                errors.append("mvp-wrapper-session-json 输出缺少当前会话 task-wrapper-b")

    wrapper_sessions = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "sessions"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    wrapper_sessions_output = (wrapper_sessions.stdout or "") + (wrapper_sessions.stderr or "")
    if wrapper_sessions.returncode != 0:
        errors.append(f"mvp-wrapper-sessions 执行失败: exit={wrapper_sessions.returncode}")
    elif "[mvp-wrapper] sessions => db=target\\mvp\\session.db limit=5 source=session" not in wrapper_sessions_output:
        errors.append("mvp-wrapper-sessions 输出缺少 db source=session")
    elif "[mvp-wrapper] recent[0] => task=task-wrapper-b effect=effect-task-wrapper-b" not in wrapper_sessions_output:
        errors.append("mvp-wrapper-sessions 输出缺少最近任务 task-wrapper-b")
    elif "[mvp-wrapper] recent[1] => task=task-wrapper-a effect=effect-task-wrapper-a" not in wrapper_sessions_output:
        errors.append("mvp-wrapper-sessions 输出缺少旧任务 task-wrapper-a")

    wrapper_sessions_json = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "sessions", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    payload = load_json_payload(wrapper_sessions_json, errors, "mvp-wrapper-sessions-json", expected_exit=0)
    if payload is not None:
        result = extract_json_result(payload, errors, "mvp-wrapper-sessions-json", "sessions")
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
    wrapper_cmd_session_output = (wrapper_cmd_session.stdout or "") + (wrapper_cmd_session.stderr or "")
    if wrapper_cmd_session.returncode != 0:
        errors.append(f"mvp-wrapper-cmd-session failed: exit={wrapper_cmd_session.returncode}")
    elif "[mvp-wrapper] session => task=task-wrapper-b effect=effect-task-wrapper-b" not in wrapper_cmd_session_output:
        errors.append("mvp-wrapper-cmd-session missing current session task-wrapper-b")
    elif "path=target\mvp\last_session.json" not in wrapper_cmd_session_output:
        errors.append("mvp-wrapper-cmd-session missing remembered session path")

    wrapper_ps1_session_json = subprocess.run(
        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", "tools\mvp\safeclaw_mvp.ps1", "session", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    payload = load_json_payload(wrapper_ps1_session_json, errors, "mvp-wrapper-ps1-session-json", expected_exit=0)
    if payload is not None:
        result = extract_json_result(payload, errors, "mvp-wrapper-ps1-session-json", "session")
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
    wrapper_cmd_sessions_output = (wrapper_cmd_sessions.stdout or "") + (wrapper_cmd_sessions.stderr or "")
    if wrapper_cmd_sessions.returncode != 0:
        errors.append(f"mvp-wrapper-cmd-sessions failed: exit={wrapper_cmd_sessions.returncode}")
    elif "[mvp-wrapper] sessions => db=target\mvp\session.db limit=5 source=session" not in wrapper_cmd_sessions_output:
        errors.append("mvp-wrapper-cmd-sessions missing db source=session")
    elif "[mvp-wrapper] current => task=task-wrapper-b effect=effect-task-wrapper-b current_db=true" not in wrapper_cmd_sessions_output:
        errors.append("mvp-wrapper-cmd-sessions missing task-wrapper-b row")
    elif "[mvp-wrapper] recent[0] => task=task-wrapper-b effect=effect-task-wrapper-b" not in wrapper_cmd_sessions_output:
        errors.append("mvp-wrapper-cmd-sessions missing task-wrapper-b row")
    elif "[mvp-wrapper] recent[1] => task=task-wrapper-a effect=effect-task-wrapper-a" not in wrapper_cmd_sessions_output:
        errors.append("mvp-wrapper-cmd-sessions missing task-wrapper-a row")

    wrapper_ps1_sessions_json = subprocess.run(
        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", "tools\mvp\safeclaw_mvp.ps1", "sessions", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    payload = load_json_payload(wrapper_ps1_sessions_json, errors, "mvp-wrapper-ps1-sessions-json", expected_exit=0)
    if payload is not None:
        result = extract_json_result(payload, errors, "mvp-wrapper-ps1-sessions-json", "sessions")
        assert_sessions_json_result(
            result,
            errors,
            "mvp-wrapper-ps1-sessions-json",
            expected_current_task_id="task-wrapper-b",
            expected_previous_task_id="task-wrapper-a",
        )

    wrapper_cmd_use_json = subprocess.run(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "use", "--index", "1", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    payload = load_json_payload(wrapper_cmd_use_json, errors, "mvp-wrapper-cmd-use-json", expected_exit=0)
    if payload is not None:
        result = extract_json_result(payload, errors, "mvp-wrapper-cmd-use-json", "use")
        assert_use_json_result(
            result,
            errors,
            "mvp-wrapper-cmd-use-json",
            expected_task_id="task-wrapper-a",
            expected_source="index:1",
        )

    wrapper_ps1_status_json = subprocess.run(
        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", "tools\mvp\safeclaw_mvp.ps1", "status", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    payload = load_json_payload(wrapper_ps1_status_json, errors, "mvp-wrapper-ps1-status-json", expected_exit=0)
    if payload is not None:
        result = extract_json_result(payload, errors, "mvp-wrapper-ps1-status-json", "status")
        assert_session_passthrough_json_result(
            result,
            errors,
            "mvp-wrapper-ps1-status-json",
            action="status",
            expected_task_id="task-wrapper-a",
        )

    wrapper_ps1_use_json = subprocess.run(
        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", "tools\mvp\safeclaw_mvp.ps1", "use", "--index", "0", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    payload = load_json_payload(wrapper_ps1_use_json, errors, "mvp-wrapper-ps1-use-json", expected_exit=0)
    if payload is not None:
        result = extract_json_result(payload, errors, "mvp-wrapper-ps1-use-json", "use")
        assert_use_json_result(
            result,
            errors,
            "mvp-wrapper-ps1-use-json",
            expected_task_id="task-wrapper-b",
            expected_source="index:0",
        )

    wrapper_cmd_report_json = subprocess.run(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "report", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    payload = load_json_payload(wrapper_cmd_report_json, errors, "mvp-wrapper-cmd-report-json", expected_exit=0)
    if payload is not None:
        result = extract_json_result(payload, errors, "mvp-wrapper-cmd-report-json", "report")
        assert_session_passthrough_json_result(
            result,
            errors,
            "mvp-wrapper-cmd-report-json",
            action="report",
            expected_task_id="task-wrapper-b",
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
    elif "[mvp-wrapper] activated => task=task-wrapper-a effect=effect-task-wrapper-a" not in wrapper_use_output:
        errors.append("mvp-wrapper-use 输出缺少切回 task-wrapper-a")
    elif "source=index:1 db_source=session output_source=session owner_source=session" not in wrapper_use_output:
        errors.append("mvp-wrapper-use 输出缺少来源说明")

    wrapper_session_after_use = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "session"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    wrapper_session_after_use_output = (wrapper_session_after_use.stdout or "") + (wrapper_session_after_use.stderr or "")
    if wrapper_session_after_use.returncode != 0:
        errors.append(f"mvp-wrapper-session-after-use 执行失败: exit={wrapper_session_after_use.returncode}")
    elif "[mvp-wrapper] session => task=task-wrapper-a effect=effect-task-wrapper-a" not in wrapper_session_after_use_output:
        errors.append("mvp-wrapper-session-after-use 输出缺少已切换 task-wrapper-a")
    elif "path=target\\mvp\\last_session.json" not in wrapper_session_after_use_output:
        errors.append("mvp-wrapper-session-after-use 输出缺少 remembered session 路径")

    wrapper_status_after_use = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "status"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    wrapper_status_after_use_output = (wrapper_status_after_use.stdout or "") + (wrapper_status_after_use.stderr or "")
    if wrapper_status_after_use.returncode != 0:
        errors.append(f"mvp-wrapper-status-after-use 执行失败: exit={wrapper_status_after_use.returncode}")
    elif "[mvp] status target => task=task-wrapper-a effect=effect-task-wrapper-a" not in wrapper_status_after_use_output:
        errors.append("mvp-wrapper-status-after-use 输出缺少已切换 task-wrapper-a")

    wrapper_use_json = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "use", "--index", "0", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    payload = load_json_payload(wrapper_use_json, errors, "mvp-wrapper-use-json", expected_exit=0)
    if payload is not None:
        result = extract_json_result(payload, errors, "mvp-wrapper-use-json", "use")
        if result is not None:
            if result.get("task_id") != "task-wrapper-b" or result.get("source") != "index:0":
                errors.append("mvp-wrapper-use-json 输出缺少切回 task-wrapper-b")
            elif result.get("db_source") != "session":
                errors.append("mvp-wrapper-use-json 输出缺少 db_source=session")
            elif result.get("output_source") != "session":
                errors.append("mvp-wrapper-use-json 输出缺少 output_source=session")
            elif result.get("owner_id_source") != "session":
                errors.append("mvp-wrapper-use-json 输出缺少 owner_id_source=session")

    wrapper_report_json = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "report", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    payload = load_json_payload(wrapper_report_json, errors, "mvp-wrapper-report-json", expected_exit=0)
    if payload is not None:
        result = extract_json_result(payload, errors, "mvp-wrapper-report-json", "report")
        if result is not None:
            prepared = result.get("prepared") or []
            source_hints = result.get("source_hints") or {}
            if not prepared or prepared[0] != "report":
                errors.append("mvp-wrapper-report-json 缺少 prepared report")
            elif "task-wrapper-b" not in (result.get("captured_output") or ""):
                errors.append("mvp-wrapper-report-json 缺少当前会话 task-wrapper-b 输出")
            elif (result.get("remembered_session") or {}).get("task_id") != "task-wrapper-b":
                errors.append("mvp-wrapper-report-json 缺少 remembered session task-wrapper-b")
            elif source_hints.get("task_context") != "session":
                errors.append("mvp-wrapper-report-json 缺少 task_context=session")

    wrapper_cmd_forget = subprocess.run(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "forget"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    wrapper_cmd_forget_output = (wrapper_cmd_forget.stdout or "") + (wrapper_cmd_forget.stderr or "")
    if wrapper_cmd_forget.returncode != 0:
        errors.append(f"mvp-wrapper-cmd-forget failed: exit={wrapper_cmd_forget.returncode}")
    elif "[mvp-wrapper] forgot => reason=removed path=target\mvp\last_session.json" not in wrapper_cmd_forget_output:
        errors.append("mvp-wrapper-cmd-forget missing removed path")

    wrapper_ps1_session_after_cmd_forget_json = subprocess.run(
        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", "tools\mvp\safeclaw_mvp.ps1", "session", "--json"],
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
    assert_json_null_result(payload, errors, "mvp-wrapper-ps1-session-after-cmd-forget-json", "session")

    wrapper_restore_after_cmd_forget = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "use", "--task-id", "task-wrapper-b"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    wrapper_restore_after_cmd_forget_output = (wrapper_restore_after_cmd_forget.stdout or "") + (wrapper_restore_after_cmd_forget.stderr or "")
    if wrapper_restore_after_cmd_forget.returncode != 0:
        errors.append(f"mvp-wrapper-restore-after-cmd-forget failed: exit={wrapper_restore_after_cmd_forget.returncode}")
    elif "[mvp-wrapper] activated => task=task-wrapper-b effect=effect-task-wrapper-b" not in wrapper_restore_after_cmd_forget_output:
        errors.append("mvp-wrapper-restore-after-cmd-forget missing task-wrapper-b")

    wrapper_forget = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "forget"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    wrapper_forget_output = (wrapper_forget.stdout or "") + (wrapper_forget.stderr or "")
    if wrapper_forget.returncode != 0:
        errors.append(f"mvp-wrapper-forget 执行失败: exit={wrapper_forget.returncode}")
    elif "[mvp-wrapper] forgot => reason=removed path=target\\mvp\\last_session.json" not in wrapper_forget_output:
        errors.append("mvp-wrapper-forget 输出缺少会话清空标记")

    wrapper_forget_json = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "forget", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    payload = load_json_payload(wrapper_forget_json, errors, "mvp-wrapper-forget-json", expected_exit=0)
    if payload is not None:
        result = extract_json_result(payload, errors, "mvp-wrapper-forget-json", "forget")
        if result is not None:
            if result.get("forgot") is not False or result.get("path") != "target\\mvp\\last_session.json":
                errors.append("mvp-wrapper-forget-json 输出不符合预期")
            elif result.get("reason") != "none":
                errors.append("mvp-wrapper-forget-json 输出缺少 reason=none")

    wrapper_session_after_forget = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "session"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    wrapper_session_after_forget_output = (wrapper_session_after_forget.stdout or "") + (wrapper_session_after_forget.stderr or "")
    if wrapper_session_after_forget.returncode != 0:
        errors.append(f"mvp-wrapper-session-after-forget 执行失败: exit={wrapper_session_after_forget.returncode}")
    elif "[mvp-wrapper] session => none path=target\\mvp\\last_session.json" not in wrapper_session_after_forget_output:
        errors.append("mvp-wrapper-session-after-forget 输出缺少 none/path")

    wrapper_ps1_report_without_session_json = subprocess.run(
        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", "tools\mvp\safeclaw_mvp.ps1", "report", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    payload = load_json_payload(
        wrapper_ps1_report_without_session_json,
        errors,
        "mvp-wrapper-ps1-report-without-session-json",
        2,
    )
    if payload is not None:
        error, details = extract_json_error(
            payload,
            errors,
            "mvp-wrapper-ps1-report-without-session-json",
            "report",
        )
        assert_json_error_fields(
            error,
            details,
            errors,
            "mvp-wrapper-ps1-report-without-session-json",
            expected_error_message_substring="missing task context",
            error_message_label="mvp-wrapper-ps1-report-without-session-json missing wrapper error",
            expected_code="missing-task-context",
            expect_no_remembered_session=True,
        )

    wrapper_report_without_session_json = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "report", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    payload = load_json_payload(
        wrapper_report_without_session_json,
        errors,
        "mvp-wrapper-report-without-session-json",
        2,
    )
    if payload is not None:
        error, details = extract_json_error(
            payload,
            errors,
            "mvp-wrapper-report-without-session-json",
            "report",
        )
        assert_json_error_fields(
            error,
            details,
            errors,
            "mvp-wrapper-report-without-session-json",
            expected_error_message_substring="missing task context",
            error_message_label="mvp-wrapper-report-without-session-json 缺少 wrapper 级错误消息",
            expected_code="missing-task-context",
            expect_no_remembered_session=True,
        )

    wrapper_cmd_recover_without_session_json = subprocess.run(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "recover", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    payload = load_json_payload(
        wrapper_cmd_recover_without_session_json,
        errors,
        "mvp-wrapper-cmd-recover-without-session-json",
        2,
    )
    if payload is not None:
        error, details = extract_json_error(
            payload,
            errors,
            "mvp-wrapper-cmd-recover-without-session-json",
            "recover",
        )
        assert_json_error_fields(
            error,
            details,
            errors,
            "mvp-wrapper-cmd-recover-without-session-json",
            expected_error_message_substring="missing task context",
            error_message_label="mvp-wrapper-cmd-recover-without-session-json missing wrapper error",
            expected_code="missing-task-context",
            expect_no_remembered_session=True,
        )

    wrapper_recover_without_session_json = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "recover", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    payload = load_json_payload(
        wrapper_recover_without_session_json,
        errors,
        "mvp-wrapper-recover-without-session-json",
        2,
    )
    if payload is not None:
        error, details = extract_json_error(
            payload,
            errors,
            "mvp-wrapper-recover-without-session-json",
            "recover",
        )
        assert_json_error_fields(
            error,
            details,
            errors,
            "mvp-wrapper-recover-without-session-json",
            expected_error_message_substring="missing task context",
            error_message_label="mvp-wrapper-recover-without-session-json 缺少 wrapper 级错误消息",
            expected_code="missing-task-context",
            expect_no_remembered_session=True,
        )

    wrapper_ps1_retry_without_session_json = subprocess.run(
        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", "tools\mvp\safeclaw_mvp.ps1", "retry", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    payload = load_json_payload(
        wrapper_ps1_retry_without_session_json,
        errors,
        "mvp-wrapper-ps1-retry-without-session-json",
        2,
    )
    if payload is not None:
        error, details = extract_json_error(
            payload,
            errors,
            "mvp-wrapper-ps1-retry-without-session-json",
            "retry",
        )
        assert_json_error_fields(
            error,
            details,
            errors,
            "mvp-wrapper-ps1-retry-without-session-json",
            expected_error_message_substring="missing task context",
            error_message_label="mvp-wrapper-ps1-retry-without-session-json missing wrapper error",
            expected_code="missing-task-context",
            expect_no_remembered_session=True,
        )

    wrapper_retry_without_session_json = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "retry", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    payload = load_json_payload(
        wrapper_retry_without_session_json,
        errors,
        "mvp-wrapper-retry-without-session-json",
        2,
    )
    if payload is not None:
        error, details = extract_json_error(
            payload,
            errors,
            "mvp-wrapper-retry-without-session-json",
            "retry",
        )
        assert_json_error_fields(
            error,
            details,
            errors,
            "mvp-wrapper-retry-without-session-json",
            expected_error_message_substring="missing task context",
            error_message_label="mvp-wrapper-retry-without-session-json 缺少 wrapper 级错误消息",
            expected_code="missing-task-context",
            expect_no_remembered_session=True,
        )

    wrapper_invalid_json_base = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "run", "--reset", "--task-id", "task-wrapper-invalid-json-base"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    wrapper_invalid_json_base_output = (wrapper_invalid_json_base.stdout or "") + (wrapper_invalid_json_base.stderr or "")
    if wrapper_invalid_json_base.returncode != 0:
        errors.append(f"mvp-wrapper-invalid-json-base 执行失败: exit={wrapper_invalid_json_base.returncode}")
    elif "[mvp] accepted task => task=task-wrapper-invalid-json-base effect=effect-task-wrapper-invalid-json-base" not in wrapper_invalid_json_base_output:
        errors.append("mvp-wrapper-invalid-json-base 输出缺少基座会话 task-wrapper-invalid-json-base")

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
        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", "tools\mvp\safeclaw_mvp.ps1", "recover", "--bogus", "--json"],
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
        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", "tools\mvp\safeclaw_mvp.ps1", "doctor", "--db", "--json"],
        errors,
        "mvp-wrapper-ps1-invalid-doctor-json",
        "doctor",
        expected_error_message_substring="missing value after --db",
    )

    assert_command_json_error(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "sessions", "--limit", "bad", "--json"],
        errors,
        "mvp-wrapper-cmd-invalid-sessions-json",
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
    wrapper_passthrough_fail_output = (wrapper_passthrough_fail.stdout or "") + (wrapper_passthrough_fail.stderr or "")
    if wrapper_passthrough_fail.returncode == 0:
        errors.append("mvp-wrapper-passthrough-fail 未按预期返回非 0")
    elif "[mvp-wrapper] cargo => failed action=not-real-action exit=1" not in wrapper_passthrough_fail_output:
        errors.append("mvp-wrapper-passthrough-fail 输出缺少透传失败承接提示")

    assert_command_failure_output(
        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", "tools\mvp\safeclaw_mvp.ps1", "demo", "--bogus"],
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
    wrapper_demo_fail_output = (wrapper_demo_fail.stdout or "") + (wrapper_demo_fail.stderr or "")
    if wrapper_demo_fail.returncode != 2:
        errors.append(f"mvp-wrapper-demo-fail 执行失败: exit={wrapper_demo_fail.returncode}")
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
    wrapper_session_after_corrupt_output = (wrapper_session_after_corrupt.stdout or "") + (wrapper_session_after_corrupt.stderr or "")
    if wrapper_session_after_corrupt.returncode != 0:
        errors.append(f"mvp-wrapper-session-after-corrupt 执行失败: exit={wrapper_session_after_corrupt.returncode}")
    elif "[mvp-wrapper] session repair => dropped invalid target\\mvp\\last_session.json" not in wrapper_session_after_corrupt_output:
        errors.append("mvp-wrapper-session-after-corrupt 输出缺少损坏会话修复提示")
    elif "[mvp-wrapper] session => none path=target\\mvp\\last_session.json" not in wrapper_session_after_corrupt_output:
        errors.append("mvp-wrapper-session-after-corrupt 输出缺少 none/path")
    elif wrapper_session_file.exists():
        errors.append("mvp-wrapper-session-after-corrupt 未移除损坏会话文件")

    wrapper_session_file.write_text("{broken", encoding="utf-8")

    wrapper_ps1_session_after_corrupt_json = subprocess.run(
        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", "tools\mvp\safeclaw_mvp.ps1", "session", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    wrapper_ps1_session_after_corrupt_output = (
        (wrapper_ps1_session_after_corrupt_json.stdout or "")
        + (wrapper_ps1_session_after_corrupt_json.stderr or "")
    )
    payload = load_json_payload(
        wrapper_ps1_session_after_corrupt_json,
        errors,
        "mvp-wrapper-ps1-session-after-corrupt-json",
        expected_exit=0,
    )
    assert_json_null_result(payload, errors, "mvp-wrapper-ps1-session-after-corrupt-json", "session")
    if "[mvp-wrapper] session repair => dropped invalid target\mvp\last_session.json" not in wrapper_ps1_session_after_corrupt_output:
        errors.append("mvp-wrapper-ps1-session-after-corrupt-json missing repair notice")
    elif wrapper_session_file.exists():
        errors.append("mvp-wrapper-ps1-session-after-corrupt-json did not remove invalid file")

    wrapper_cmd_session_after_ps1_repair = subprocess.run(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "session"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    wrapper_cmd_session_after_ps1_repair_output = (
        (wrapper_cmd_session_after_ps1_repair.stdout or "")
        + (wrapper_cmd_session_after_ps1_repair.stderr or "")
    )
    if wrapper_cmd_session_after_ps1_repair.returncode != 0:
        errors.append(f"mvp-wrapper-cmd-session-after-ps1-repair failed: exit={wrapper_cmd_session_after_ps1_repair.returncode}")
    elif "[mvp-wrapper] session => none path=target\mvp\last_session.json" not in wrapper_cmd_session_after_ps1_repair_output:
        errors.append("mvp-wrapper-cmd-session-after-ps1-repair missing none/path")

    wrapper_seed_crash_json = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "seed-crash", "--reset", "--task-id", "task-wrapper-seed-crash-json", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    payload = load_json_payload(wrapper_seed_crash_json, errors, "mvp-wrapper-seed-crash-json", expected_exit=0)
    if payload is not None:
        result = extract_json_result(payload, errors, "mvp-wrapper-seed-crash-json", "seed-crash")
        if result is not None:
            prepared = result.get("prepared") or []
            session = result.get("saved_session") or {}
            if not prepared or prepared[0] != "seed-crash":
                errors.append("mvp-wrapper-seed-crash-json 缺少 prepared seed-crash")
            elif session.get("task_id") != "task-wrapper-seed-crash-json":
                errors.append("mvp-wrapper-seed-crash-json 缺少保存后的 task-wrapper-seed-crash-json 会话")
            elif "task-wrapper-seed-crash-json" not in (result.get("captured_output") or ""):
                errors.append("mvp-wrapper-seed-crash-json 缺少 task-wrapper-seed-crash-json 输出")

    wrapper_recover_json = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "recover", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    payload = load_json_payload(wrapper_recover_json, errors, "mvp-wrapper-recover-json", expected_exit=0)
    if payload is not None:
        result = extract_json_result(payload, errors, "mvp-wrapper-recover-json", "recover")
        if result is not None:
            prepared = result.get("prepared") or []
            source_hints = result.get("source_hints") or {}
            if not prepared or prepared[0] != "recover":
                errors.append("mvp-wrapper-recover-json 缺少 prepared recover")
            elif "task-wrapper-seed-crash-json" not in (result.get("captured_output") or ""):
                errors.append("mvp-wrapper-recover-json 缺少当前会话 task-wrapper-seed-crash-json 输出")
            elif (result.get("remembered_session") or {}).get("task_id") != "task-wrapper-seed-crash-json":
                errors.append("mvp-wrapper-recover-json 缺少 remembered session task-wrapper-seed-crash-json")
            elif source_hints.get("task_context") != "session":
                errors.append("mvp-wrapper-recover-json 缺少 task_context=session")

    wrapper_seed_failed_json = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "seed-failed", "--reset", "--task-id", "task-wrapper-seed-failed-json", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    payload = load_json_payload(wrapper_seed_failed_json, errors, "mvp-wrapper-seed-failed-json", expected_exit=0)
    if payload is not None:
        result = extract_json_result(payload, errors, "mvp-wrapper-seed-failed-json", "seed-failed")
        if result is not None:
            prepared = result.get("prepared") or []
            session = result.get("saved_session") or {}
            if not prepared or prepared[0] != "seed-failed":
                errors.append("mvp-wrapper-seed-failed-json 缺少 prepared seed-failed")
            elif session.get("task_id") != "task-wrapper-seed-failed-json":
                errors.append("mvp-wrapper-seed-failed-json 缺少保存后的 task-wrapper-seed-failed-json 会话")
            elif "task-wrapper-seed-failed-json" not in (result.get("captured_output") or ""):
                errors.append("mvp-wrapper-seed-failed-json 缺少 task-wrapper-seed-failed-json 输出")

    wrapper_retry_json = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "retry", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    payload = load_json_payload(wrapper_retry_json, errors, "mvp-wrapper-retry-json", expected_exit=0)
    if payload is not None:
        result = extract_json_result(payload, errors, "mvp-wrapper-retry-json", "retry")
        if result is not None:
            prepared = result.get("prepared") or []
            source_hints = result.get("source_hints") or {}
            if not prepared or prepared[0] != "retry":
                errors.append("mvp-wrapper-retry-json 缺少 prepared retry")
            elif "task-wrapper-seed-failed-json" not in (result.get("captured_output") or ""):
                errors.append("mvp-wrapper-retry-json 缺少当前会话 task-wrapper-seed-failed-json 输出")
            elif (result.get("remembered_session") or {}).get("task_id") != "task-wrapper-seed-failed-json":
                errors.append("mvp-wrapper-retry-json 缺少 remembered session task-wrapper-seed-failed-json")
            elif source_hints.get("task_context") != "session":
                errors.append("mvp-wrapper-retry-json 缺少 task_context=session")

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
    elif "[mvp] report target => task=task-wrapper-demo effect=effect-task-wrapper-demo" not in wrapper_demo_output:
        errors.append("mvp-wrapper-demo 输出缺少 task-wrapper-demo report 目标")

    wrapper_demo_json = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "demo", "--task-id", "task-wrapper-demo-json", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    payload = load_json_payload(wrapper_demo_json, errors, "mvp-wrapper-demo-json", expected_exit=0)
    if payload is not None:
        result = extract_json_result(payload, errors, "mvp-wrapper-demo-json", "demo")
        if result is not None:
            steps = result.get("steps") or []
            session = result.get("session") or {}
            remembered_session = result.get("remembered_session") or {}
            if [step.get("action") for step in steps] != ["run", "status", "report"]:
                errors.append("mvp-wrapper-demo-json 步骤序列不正确")
            elif remembered_session.get("task_id") != "task-wrapper-demo-json":
                errors.append("mvp-wrapper-demo-json 缺少 remembered_session task-wrapper-demo-json")
            elif session.get("task_id") != "task-wrapper-demo-json":
                errors.append("mvp-wrapper-demo-json 缺少兼容 session task-wrapper-demo-json")
            else:
                assert_matching_session_alias(result, errors, "mvp-wrapper-demo-json")
                assert_step_source_hints(
                    steps,
                    errors,
                    "mvp-wrapper-demo-json",
                    [
                        ("run", {"db": "default", "output": "default", "owner_id": "default", "task_context": "flag"}),
                        ("status", {"db": "session", "output": "session", "owner_id": "session", "task_context": "flag"}),
                        ("report", {"db": "session", "output": "session", "owner_id": "session", "task_context": "flag"}),
                    ],
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

    wrapper_demo_fail_json = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "demo", "--bogus", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    payload = load_json_payload(wrapper_demo_fail_json, errors, "mvp-wrapper-demo-fail-json", expected_exit=2)
    if payload is not None:
        error, details = extract_json_error(payload, errors, "mvp-wrapper-demo-fail-json", "demo")
        assert_json_error_fields(
            error,
            details,
            errors,
            "mvp-wrapper-demo-fail-json",
            expected_failed_step="run",
            expected_code="invalid-argument",
            expected_details_message_substring="unknown argument",
            details_message_label="mvp-wrapper-demo-fail-json 缺少 wrapper 级 unknown argument",
            expected_remembered_session_task_id="task-wrapper-demo-json",
            remembered_session_label="mvp-wrapper-demo-fail-json remembered_session 缺少 task-wrapper-demo-json",
        )
        if details is not None and details.get("session") is not None:
            errors.append("mvp-wrapper-demo-fail-json 不应继续返回旧 session 字段")

    wrapper_demo_underlying_fail_json = subprocess.run(
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
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    payload = load_json_payload(
        wrapper_demo_underlying_fail_json,
        errors,
        "mvp-wrapper-demo-underlying-fail-json",
        expected_exit=1,
    )
    if payload is not None:
        error, details = extract_json_error(
            payload,
            errors,
            "mvp-wrapper-demo-underlying-fail-json",
            "demo",
        )
        assert_json_error_fields(
            error,
            details,
            errors,
            "mvp-wrapper-demo-underlying-fail-json",
            expected_error_message_substring="failed step=run",
            error_message_label="mvp-wrapper-demo-underlying-fail-json 缺少组合动作失败消息",
            expected_failed_step="run",
            expected_remembered_session_task_id="task-wrapper-demo-json",
            remembered_session_label="mvp-wrapper-demo-underlying-fail-json remembered_session 缺少 task-wrapper-demo-json",
        )
        if details is not None:
            if details.get("session") is not None:
                errors.append("mvp-wrapper-demo-underlying-fail-json 不应继续返回旧 session 字段")
            assert_step_source_hints(
                details.get("steps"),
                errors,
                "mvp-wrapper-demo-underlying-fail-json",
                [("run", {"db": "default", "output": "flag", "owner_id": "default", "task_context": "flag"})],
            )

    wrapper_recover_demo = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "recover-demo", "--task-id", "task-wrapper-recover-demo"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    wrapper_recover_demo_output = (wrapper_recover_demo.stdout or "") + (wrapper_recover_demo.stderr or "")
    if wrapper_recover_demo.returncode != 0:
        errors.append(f"mvp-wrapper-recover-demo 执行失败: exit={wrapper_recover_demo.returncode}")
    elif "[mvp-wrapper] recover-demo => seed-crash" not in wrapper_recover_demo_output:
        errors.append("mvp-wrapper-recover-demo 输出缺少 seed-crash 标记")
    elif "[mvp-wrapper] recover-demo => recover" not in wrapper_recover_demo_output:
        errors.append("mvp-wrapper-recover-demo 输出缺少 recover 标记")
    elif "[mvp-wrapper] recover-demo => report" not in wrapper_recover_demo_output:
        errors.append("mvp-wrapper-recover-demo 输出缺少 report 标记")
    elif "[mvp] report target => task=task-wrapper-recover-demo effect=effect-task-wrapper-recover-demo" not in wrapper_recover_demo_output:
        errors.append("mvp-wrapper-recover-demo 输出缺少 task-wrapper-recover-demo report 目标")

    wrapper_recover_demo_json = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "recover-demo", "--task-id", "task-wrapper-recover-demo-json", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    payload = load_json_payload(wrapper_recover_demo_json, errors, "mvp-wrapper-recover-demo-json", expected_exit=0)
    if payload is not None:
        result = extract_json_result(payload, errors, "mvp-wrapper-recover-demo-json", "recover-demo")
        if result is not None:
            steps = result.get("steps") or []
            session = result.get("session") or {}
            remembered_session = result.get("remembered_session") or {}
            if [step.get("action") for step in steps] != ["seed-crash", "recover", "report"]:
                errors.append("mvp-wrapper-recover-demo-json 步骤序列不正确")
            elif remembered_session.get("task_id") != "task-wrapper-recover-demo-json":
                errors.append("mvp-wrapper-recover-demo-json 缺少 remembered_session task-wrapper-recover-demo-json")
            elif session.get("task_id") != "task-wrapper-recover-demo-json":
                errors.append("mvp-wrapper-recover-demo-json 缺少兼容 session task-wrapper-recover-demo-json")
            else:
                assert_matching_session_alias(result, errors, "mvp-wrapper-recover-demo-json")
                assert_step_source_hints(
                    steps,
                    errors,
                    "mvp-wrapper-recover-demo-json",
                    [
                        ("seed-crash", {"db": "default", "output": "default", "owner_id": "default", "task_context": "flag"}),
                        ("recover", {"db": "session", "output": "session", "owner_id": "session", "task_context": "flag"}),
                        ("report", {"db": "session", "output": "session", "owner_id": "session", "task_context": "flag"}),
                    ],
                )

    assert_command_failure_output(
        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", "tools\mvp\safeclaw_mvp.ps1", "recover-demo", "--bogus"],
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
    wrapper_recover_demo_fail_output = (wrapper_recover_demo_fail.stdout or "") + (wrapper_recover_demo_fail.stderr or "")
    if wrapper_recover_demo_fail.returncode != 2:
        errors.append(f"mvp-wrapper-recover-demo-fail 执行失败: exit={wrapper_recover_demo_fail.returncode}")
    elif "[mvp-wrapper] recover-demo => failed step=seed-crash exit=2" not in wrapper_recover_demo_fail_output:
        errors.append("mvp-wrapper-recover-demo-fail 输出缺少组合动作失败承接提示")

    assert_command_json_error(
        ["cmd", "/c", "tools\mvp\safeclaw_mvp.cmd", "recover-demo", "--bogus", "--json"],
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

    wrapper_recover_demo_fail_json = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "recover-demo", "--bogus", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    payload = load_json_payload(wrapper_recover_demo_fail_json, errors, "mvp-wrapper-recover-demo-fail-json", expected_exit=2)
    if payload is not None:
        error, details = extract_json_error(payload, errors, "mvp-wrapper-recover-demo-fail-json", "recover-demo")
        assert_json_error_fields(
            error,
            details,
            errors,
            "mvp-wrapper-recover-demo-fail-json",
            expected_failed_step="seed-crash",
            expected_code="invalid-argument",
            expected_details_message_substring="unknown argument",
            details_message_label="mvp-wrapper-recover-demo-fail-json 缺少 wrapper 级 unknown argument",
            expected_remembered_session_task_id="task-wrapper-recover-demo-json",
            remembered_session_label="mvp-wrapper-recover-demo-fail-json remembered_session 缺少 task-wrapper-recover-demo-json",
        )
        if details is not None and details.get("session") is not None:
            errors.append("mvp-wrapper-recover-demo-fail-json 不应继续返回旧 session 字段")

    wrapper_retry_demo = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "retry-demo", "--task-id", "task-wrapper-retry-demo"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    wrapper_retry_demo_output = (wrapper_retry_demo.stdout or "") + (wrapper_retry_demo.stderr or "")
    if wrapper_retry_demo.returncode != 0:
        errors.append(f"mvp-wrapper-retry-demo 执行失败: exit={wrapper_retry_demo.returncode}")
    elif "[mvp-wrapper] retry-demo => seed-failed" not in wrapper_retry_demo_output:
        errors.append("mvp-wrapper-retry-demo 输出缺少 seed-failed 标记")
    elif "[mvp-wrapper] retry-demo => retry" not in wrapper_retry_demo_output:
        errors.append("mvp-wrapper-retry-demo 输出缺少 retry 标记")
    elif "[mvp-wrapper] retry-demo => report" not in wrapper_retry_demo_output:
        errors.append("mvp-wrapper-retry-demo 输出缺少 report 标记")
    elif "[mvp] report target => task=task-wrapper-retry-demo effect=effect-task-wrapper-retry-demo" not in wrapper_retry_demo_output:
        errors.append("mvp-wrapper-retry-demo 输出缺少 task-wrapper-retry-demo report 目标")

    wrapper_retry_demo_json = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "retry-demo", "--task-id", "task-wrapper-retry-demo-json", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    payload = load_json_payload(wrapper_retry_demo_json, errors, "mvp-wrapper-retry-demo-json", expected_exit=0)
    if payload is not None:
        result = extract_json_result(payload, errors, "mvp-wrapper-retry-demo-json", "retry-demo")
        if result is not None:
            steps = result.get("steps") or []
            session = result.get("session") or {}
            remembered_session = result.get("remembered_session") or {}
            if [step.get("action") for step in steps] != ["seed-failed", "retry", "report"]:
                errors.append("mvp-wrapper-retry-demo-json 步骤序列不正确")
            elif remembered_session.get("task_id") != "task-wrapper-retry-demo-json":
                errors.append("mvp-wrapper-retry-demo-json 缺少 remembered_session task-wrapper-retry-demo-json")
            elif session.get("task_id") != "task-wrapper-retry-demo-json":
                errors.append("mvp-wrapper-retry-demo-json 缺少兼容 session task-wrapper-retry-demo-json")
            else:
                assert_matching_session_alias(result, errors, "mvp-wrapper-retry-demo-json")
                assert_step_source_hints(
                    steps,
                    errors,
                    "mvp-wrapper-retry-demo-json",
                    [
                        ("seed-failed", {"db": "default", "output": "default", "owner_id": "default", "task_context": "flag"}),
                        ("retry", {"db": "session", "output": "session", "owner_id": "session", "task_context": "flag"}),
                        ("report", {"db": "session", "output": "session", "owner_id": "session", "task_context": "flag"}),
                    ],
                )

    assert_command_failure_output(
        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", "tools\mvp\safeclaw_mvp.ps1", "retry-demo", "--bogus"],
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
    wrapper_retry_demo_fail_output = (wrapper_retry_demo_fail.stdout or "") + (wrapper_retry_demo_fail.stderr or "")
    if wrapper_retry_demo_fail.returncode != 2:
        errors.append(f"mvp-wrapper-retry-demo-fail 执行失败: exit={wrapper_retry_demo_fail.returncode}")
    elif "[mvp-wrapper] retry-demo => failed step=seed-failed exit=2" not in wrapper_retry_demo_fail_output:
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

    wrapper_retry_demo_fail_json = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "retry-demo", "--bogus", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    payload = load_json_payload(wrapper_retry_demo_fail_json, errors, "mvp-wrapper-retry-demo-fail-json", expected_exit=2)
    if payload is not None:
        error, details = extract_json_error(payload, errors, "mvp-wrapper-retry-demo-fail-json", "retry-demo")
        assert_json_error_fields(
            error,
            details,
            errors,
            "mvp-wrapper-retry-demo-fail-json",
            expected_failed_step="seed-failed",
            expected_code="invalid-argument",
            expected_details_message_substring="unknown argument",
            details_message_label="mvp-wrapper-retry-demo-fail-json 缺少 wrapper 级 unknown argument",
            expected_remembered_session_task_id="task-wrapper-retry-demo-json",
            remembered_session_label="mvp-wrapper-retry-demo-fail-json remembered_session 缺少 task-wrapper-retry-demo-json",
        )
        if details is not None and details.get("session") is not None:
            errors.append("mvp-wrapper-retry-demo-fail-json 不应继续返回旧 session 字段")

    root_index = REPO_ROOT / "generated" / "index.json"
    if not root_index.exists():
        errors.append(f"缺少 codegen 产物: {root_index.relative_to(REPO_ROOT).as_posix()}")

    for target in ("rust", "python", "ts"):
        manifest_path = REPO_ROOT / "generated" / target / "manifest.json"
        stable_ids_path = REPO_ROOT / "generated" / target / "stable_ids.json"
        if not manifest_path.exists():
            errors.append(f"缺少 codegen 产物: {manifest_path.relative_to(REPO_ROOT).as_posix()}")
        if not stable_ids_path.exists():
            errors.append(f"缺少 codegen 产物: {stable_ids_path.relative_to(REPO_ROOT).as_posix()}")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        old_path = temp_root / "old.json"
        new_path = temp_root / "new.json"
        json_out = temp_root / "diff.json"
        old_path.write_text(json.dumps({"version": "0.1.1", "a": 1}), encoding="utf-8")
        new_path.write_text(json.dumps({"version": "0.1.2", "a": 2, "b": 3}), encoding="utf-8")

        json_run = subprocess.run(
            [PYTHON, "tools/schema_diff/main.py", str(old_path), str(new_path), "--json-out", str(json_out)],
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
            [PYTHON, "tools/schema_diff/main.py", str(old_path), str(new_path), "--fail-on-diff"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        if fail_run.returncode == 0:
            errors.append("schema-diff 在存在差异时未按预期返回非 0")

    return errors


def main() -> int:
    errors = collect_errors()
    if errors:
        print("Tooling smoke check failed:")
        for item in errors:
            print(f"- {item}")
        return 1

    print("Tooling smoke check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


