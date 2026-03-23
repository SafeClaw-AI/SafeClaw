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
    elif "[mvp-wrapper] doctor cargo => ok" not in wrapper_doctor_output:
        errors.append("mvp-wrapper-doctor 输出缺少 cargo 检查")
    elif "[mvp-wrapper] doctor toolchain => ok" not in wrapper_doctor_output:
        errors.append("mvp-wrapper-doctor 输出缺少 toolchain 检查")
    elif "[mvp-wrapper] doctor linker => ok" not in wrapper_doctor_output:
        errors.append("mvp-wrapper-doctor 输出缺少 linker 检查")

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
    if wrapper_doctor_json.returncode != 0:
        errors.append(f"mvp-wrapper-doctor-json 执行失败: exit={wrapper_doctor_json.returncode}")
    else:
        try:
            payload = json.loads(wrapper_doctor_json.stdout)
        except json.JSONDecodeError:
            errors.append("mvp-wrapper-doctor-json 输出不是合法 JSON")
        else:
            result = payload.get("result") or {}
            if payload.get("ok") is not True or payload.get("action") != "doctor":
                errors.append("mvp-wrapper-doctor-json 输出缺少统一信封")
            elif result.get("cargo", {}).get("ok") is not True:
                errors.append("mvp-wrapper-doctor-json 输出缺少 cargo ok")
            elif result.get("toolchain", {}).get("ok") is not True:
                errors.append("mvp-wrapper-doctor-json 输出缺少 toolchain ok")
            elif result.get("linker", {}).get("ok") is not True:
                errors.append("mvp-wrapper-doctor-json 输出缺少 linker ok")

    wrapper_run_json = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "run", "--reset", "--task-id", "task-wrapper-json", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if wrapper_run_json.returncode != 0:
        errors.append(f"mvp-wrapper-run-json 执行失败: exit={wrapper_run_json.returncode}")
    else:
        try:
            payload = json.loads(wrapper_run_json.stdout)
        except json.JSONDecodeError:
            errors.append("mvp-wrapper-run-json 输出不是合法 JSON")
        else:
            result = payload.get("result") or {}
            session = result.get("saved_session") or {}
            if payload.get("ok") is not True or payload.get("action") != "run":
                errors.append("mvp-wrapper-run-json 输出缺少统一信封")
            elif session.get("task_id") != "task-wrapper-json":
                errors.append("mvp-wrapper-run-json 缺少保存后的 task-wrapper-json 会话")

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
    if wrapper_status_json.returncode != 0:
        errors.append(f"mvp-wrapper-status-json 执行失败: exit={wrapper_status_json.returncode}")
    else:
        try:
            payload = json.loads(wrapper_status_json.stdout)
        except json.JSONDecodeError:
            errors.append("mvp-wrapper-status-json 输出不是合法 JSON")
        else:
            result = payload.get("result") or {}
            prepared = result.get("prepared") or []
            if payload.get("ok") is not True or payload.get("action") != "status":
                errors.append("mvp-wrapper-status-json 输出缺少统一信封")
            elif not prepared or prepared[0] != "status":
                errors.append("mvp-wrapper-status-json 缺少 prepared status")
            elif "task-wrapper-b" not in (result.get("captured_output") or ""):
                errors.append("mvp-wrapper-status-json 缺少当前会话 task-wrapper-b 输出")

    wrapper_status_fail_json = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "status", "--bogus", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if wrapper_status_fail_json.returncode == 0:
        errors.append("mvp-wrapper-status-fail-json 未按预期返回非 0")
    else:
        try:
            payload = json.loads(wrapper_status_fail_json.stdout)
        except json.JSONDecodeError:
            errors.append("mvp-wrapper-status-fail-json 输出不是合法 JSON")
        else:
            error = payload.get("error") or {}
            details = error.get("details") or {}
            if payload.get("ok") is not False or payload.get("action") != "status":
                errors.append("mvp-wrapper-status-fail-json 输出缺少统一错误信封")
            elif "unknown argument" not in (details.get("captured_output") or ""):
                errors.append("mvp-wrapper-status-fail-json 缺少底层错误输出")

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

    wrapper_session_json = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "session", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    wrapper_session_json_output = (wrapper_session_json.stdout or "") + (wrapper_session_json.stderr or "")
    if wrapper_session_json.returncode != 0:
        errors.append(f"mvp-wrapper-session-json 执行失败: exit={wrapper_session_json.returncode}")
    else:
        try:
            payload = json.loads(wrapper_session_json.stdout)
        except json.JSONDecodeError:
            errors.append("mvp-wrapper-session-json 输出不是合法 JSON")
        else:
            result = payload.get("result") or {}
            if payload.get("ok") is not True or payload.get("action") != "session":
                errors.append("mvp-wrapper-session-json 输出缺少统一信封")
            elif result.get("task_id") != "task-wrapper-b" or result.get("effect_id") != "effect-task-wrapper-b":
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
    if wrapper_sessions_json.returncode != 0:
        errors.append(f"mvp-wrapper-sessions-json 执行失败: exit={wrapper_sessions_json.returncode}")
    else:
        try:
            payload = json.loads(wrapper_sessions_json.stdout)
        except json.JSONDecodeError:
            errors.append("mvp-wrapper-sessions-json 输出不是合法 JSON")
        else:
            result = payload.get("result") or {}
            rows = result.get("rows") or []
            if payload.get("ok") is not True or payload.get("action") != "sessions":
                errors.append("mvp-wrapper-sessions-json 输出缺少统一信封")
            elif not rows or rows[0].get("task_id") != "task-wrapper-b":
                errors.append("mvp-wrapper-sessions-json 输出缺少最近任务 task-wrapper-b")
            elif len(rows) < 2 or rows[1].get("task_id") != "task-wrapper-a":
                errors.append("mvp-wrapper-sessions-json 输出缺少旧任务 task-wrapper-a")

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
    if wrapper_use_json.returncode != 0:
        errors.append(f"mvp-wrapper-use-json 执行失败: exit={wrapper_use_json.returncode}")
    else:
        try:
            payload = json.loads(wrapper_use_json.stdout)
        except json.JSONDecodeError:
            errors.append("mvp-wrapper-use-json 输出不是合法 JSON")
        else:
            result = payload.get("result") or {}
            if payload.get("ok") is not True or payload.get("action") != "use":
                errors.append("mvp-wrapper-use-json 输出缺少统一信封")
            elif result.get("task_id") != "task-wrapper-b" or result.get("source") != "index:0":
                errors.append("mvp-wrapper-use-json 输出缺少切回 task-wrapper-b")

    wrapper_forget = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "forget"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    wrapper_forget_output = (wrapper_forget.stdout or "") + (wrapper_forget.stderr or "")
    if wrapper_forget.returncode != 0:
        errors.append(f"mvp-wrapper-forget 执行失败: exit={wrapper_forget.returncode}")
    elif "[mvp-wrapper] forgot => target\\mvp\\last_session.json" not in wrapper_forget_output:
        errors.append("mvp-wrapper-forget 输出缺少会话清空标记")

    wrapper_forget_json = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "forget", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if wrapper_forget_json.returncode != 0:
        errors.append(f"mvp-wrapper-forget-json 执行失败: exit={wrapper_forget_json.returncode}")
    else:
        try:
            payload = json.loads(wrapper_forget_json.stdout)
        except json.JSONDecodeError:
            errors.append("mvp-wrapper-forget-json 输出不是合法 JSON")
        else:
            result = payload.get("result") or {}
            if payload.get("ok") is not True or payload.get("action") != "forget":
                errors.append("mvp-wrapper-forget-json 输出缺少统一信封")
            elif result.get("forgot") is not False or result.get("path") != "target\\mvp\\last_session.json":
                errors.append("mvp-wrapper-forget-json 输出不符合预期")

    wrapper_session_after_forget = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "session"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    wrapper_session_after_forget_output = (wrapper_session_after_forget.stdout or "") + (wrapper_session_after_forget.stderr or "")
    if wrapper_session_after_forget.returncode != 0:
        errors.append(f"mvp-wrapper-session-after-forget 执行失败: exit={wrapper_session_after_forget.returncode}")
    elif "[mvp-wrapper] session => none" not in wrapper_session_after_forget_output:
        errors.append("mvp-wrapper-session-after-forget 输出缺少 none")

    wrapper_invalid_session_json = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "session", "--bogus", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if wrapper_invalid_session_json.returncode != 2:
        errors.append(f"mvp-wrapper-invalid-session-json 执行失败: exit={wrapper_invalid_session_json.returncode}")
    else:
        try:
            payload = json.loads(wrapper_invalid_session_json.stdout)
        except json.JSONDecodeError:
            errors.append("mvp-wrapper-invalid-session-json 输出不是合法 JSON")
        else:
            error = payload.get("error") or {}
            if payload.get("ok") is not False or payload.get("action") != "session":
                errors.append("mvp-wrapper-invalid-session-json 输出缺少统一错误信封")
            elif "unknown argument" not in error.get("message", ""):
                errors.append("mvp-wrapper-invalid-session-json 输出缺少错误信息")

    wrapper_invalid_doctor_json = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "doctor", "--db", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if wrapper_invalid_doctor_json.returncode != 2:
        errors.append(f"mvp-wrapper-invalid-doctor-json 执行失败: exit={wrapper_invalid_doctor_json.returncode}")
    else:
        try:
            payload = json.loads(wrapper_invalid_doctor_json.stdout)
        except json.JSONDecodeError:
            errors.append("mvp-wrapper-invalid-doctor-json 输出不是合法 JSON")
        else:
            error = payload.get("error") or {}
            if payload.get("ok") is not False or payload.get("action") != "doctor":
                errors.append("mvp-wrapper-invalid-doctor-json 输出缺少统一错误信封")
            elif "missing value after --db" not in error.get("message", ""):
                errors.append("mvp-wrapper-invalid-doctor-json 输出缺少错误信息")

    wrapper_invalid_sessions_json = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "sessions", "--limit", "bad", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if wrapper_invalid_sessions_json.returncode != 2:
        errors.append(f"mvp-wrapper-invalid-sessions-json 执行失败: exit={wrapper_invalid_sessions_json.returncode}")
    else:
        try:
            payload = json.loads(wrapper_invalid_sessions_json.stdout)
        except json.JSONDecodeError:
            errors.append("mvp-wrapper-invalid-sessions-json 输出不是合法 JSON")
        else:
            error = payload.get("error") or {}
            if payload.get("ok") is not False or payload.get("action") != "sessions":
                errors.append("mvp-wrapper-invalid-sessions-json 输出缺少统一错误信封")
            elif "invalid --limit" not in error.get("message", ""):
                errors.append("mvp-wrapper-invalid-sessions-json 输出缺少错误信息")

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

    wrapper_demo_fail = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "demo", "--bogus"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    wrapper_demo_fail_output = (wrapper_demo_fail.stdout or "") + (wrapper_demo_fail.stderr or "")
    if wrapper_demo_fail.returncode == 0:
        errors.append("mvp-wrapper-demo-fail 未按预期返回非 0")
    elif "[mvp-wrapper] demo => failed step=run exit=1" not in wrapper_demo_fail_output:
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
    elif "[mvp-wrapper] session => none" not in wrapper_session_after_corrupt_output:
        errors.append("mvp-wrapper-session-after-corrupt 输出缺少 none")
    elif wrapper_session_file.exists():
        errors.append("mvp-wrapper-session-after-corrupt 未移除损坏会话文件")

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
    if wrapper_demo_json.returncode != 0:
        errors.append(f"mvp-wrapper-demo-json 执行失败: exit={wrapper_demo_json.returncode}")
    else:
        try:
            payload = json.loads(wrapper_demo_json.stdout)
        except json.JSONDecodeError:
            errors.append("mvp-wrapper-demo-json 输出不是合法 JSON")
        else:
            result = payload.get("result") or {}
            steps = result.get("steps") or []
            session = result.get("session") or {}
            if payload.get("ok") is not True or payload.get("action") != "demo":
                errors.append("mvp-wrapper-demo-json 输出缺少统一信封")
            elif [step.get("action") for step in steps] != ["run", "status", "report"]:
                errors.append("mvp-wrapper-demo-json 步骤序列不正确")
            elif session.get("task_id") != "task-wrapper-demo-json":
                errors.append("mvp-wrapper-demo-json 缺少当前会话 task-wrapper-demo-json")

    wrapper_demo_fail_json = subprocess.run(
        [PYTHON, "tools/mvp/safeclaw_mvp.py", "demo", "--bogus", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if wrapper_demo_fail_json.returncode == 0:
        errors.append("mvp-wrapper-demo-fail-json 未按预期返回非 0")
    else:
        try:
            payload = json.loads(wrapper_demo_fail_json.stdout)
        except json.JSONDecodeError:
            errors.append("mvp-wrapper-demo-fail-json 输出不是合法 JSON")
        else:
            error = payload.get("error") or {}
            details = error.get("details") or {}
            if payload.get("ok") is not False or payload.get("action") != "demo":
                errors.append("mvp-wrapper-demo-fail-json 输出缺少统一错误信封")
            elif details.get("failed_step") != "run":
                errors.append("mvp-wrapper-demo-fail-json 缺少失败步骤 run")

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
    if wrapper_recover_demo_json.returncode != 0:
        errors.append(f"mvp-wrapper-recover-demo-json 执行失败: exit={wrapper_recover_demo_json.returncode}")
    else:
        try:
            payload = json.loads(wrapper_recover_demo_json.stdout)
        except json.JSONDecodeError:
            errors.append("mvp-wrapper-recover-demo-json 输出不是合法 JSON")
        else:
            result = payload.get("result") or {}
            steps = result.get("steps") or []
            session = result.get("session") or {}
            if payload.get("ok") is not True or payload.get("action") != "recover-demo":
                errors.append("mvp-wrapper-recover-demo-json 输出缺少统一信封")
            elif [step.get("action") for step in steps] != ["seed-crash", "recover", "report"]:
                errors.append("mvp-wrapper-recover-demo-json 步骤序列不正确")
            elif session.get("task_id") != "task-wrapper-recover-demo-json":
                errors.append("mvp-wrapper-recover-demo-json 缺少当前会话 task-wrapper-recover-demo-json")

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
    if wrapper_retry_demo_json.returncode != 0:
        errors.append(f"mvp-wrapper-retry-demo-json 执行失败: exit={wrapper_retry_demo_json.returncode}")
    else:
        try:
            payload = json.loads(wrapper_retry_demo_json.stdout)
        except json.JSONDecodeError:
            errors.append("mvp-wrapper-retry-demo-json 输出不是合法 JSON")
        else:
            result = payload.get("result") or {}
            steps = result.get("steps") or []
            session = result.get("session") or {}
            if payload.get("ok") is not True or payload.get("action") != "retry-demo":
                errors.append("mvp-wrapper-retry-demo-json 输出缺少统一信封")
            elif [step.get("action") for step in steps] != ["seed-failed", "retry", "report"]:
                errors.append("mvp-wrapper-retry-demo-json 步骤序列不正确")
            elif session.get("task_id") != "task-wrapper-retry-demo-json":
                errors.append("mvp-wrapper-retry-demo-json 缺少当前会话 task-wrapper-retry-demo-json")

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
            payload = json.loads(json_out.read_text(encoding="utf-8"))
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
