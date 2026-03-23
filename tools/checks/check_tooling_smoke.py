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
            if payload.get("cargo", {}).get("ok") is not True:
                errors.append("mvp-wrapper-doctor-json 输出缺少 cargo ok")
            elif payload.get("toolchain", {}).get("ok") is not True:
                errors.append("mvp-wrapper-doctor-json 输出缺少 toolchain ok")
            elif payload.get("linker", {}).get("ok") is not True:
                errors.append("mvp-wrapper-doctor-json 输出缺少 linker ok")

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
            if payload.get("task_id") != "task-wrapper-b" or payload.get("effect_id") != "effect-task-wrapper-b":
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
            rows = payload.get("rows") or []
            if not rows or rows[0].get("task_id") != "task-wrapper-b":
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
            if payload.get("task_id") != "task-wrapper-b" or payload.get("source") != "index:0":
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
            if payload.get("forgot") is not False or payload.get("path") != "target\\mvp\\last_session.json":
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
