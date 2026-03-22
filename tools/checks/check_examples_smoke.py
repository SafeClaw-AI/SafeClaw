from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECKS: list[tuple[str, list[str], list[str]]] = [
    (
        "full-lifecycle-demo",
        [
            "cargo",
            "run",
            "-p",
            "safeclaw-sqlite",
            "--example",
            "full_lifecycle_demo",
            "--quiet",
        ],
        [
            "[demo] persisted reconciled runtime",
            "[demo] snapshot after-complete => queued=0, active=0, completed=1",
        ],
    ),
    (
        "dispatch-batch-demo",
        [
            "cargo",
            "run",
            "-p",
            "safeclaw-sqlite",
            "--example",
            "worker_loop_dispatch_batch_demo",
            "--quiet",
        ],
        [
            "[demo] executed batch => count=3",
            "[demo] snapshot probe-batch-after-complete => queued=0, active=0, completed=4",
        ],
    ),
    (
        "dispatch-demo",
        [
            "cargo",
            "run",
            "-p",
            "safeclaw-sqlite",
            "--example",
            "worker_loop_dispatch_demo",
            "--quiet",
        ],
        [
            "[demo] fresh => task=task-worker-dispatch-demo-fresh worker=Succeeded effect=Executed completed=true",
            "[demo] snapshot probe-after-complete => queued=0, active=0, completed=4",
        ],
    ),
    (
        "empty-queue-demo",
        [
            "cargo",
            "run",
            "-p",
            "safeclaw-sqlite",
            "--example",
            "worker_loop_empty_queue_demo",
            "--quiet",
        ],
        [
            "[demo] claim_and_dispatch_until_empty on empty queue => count=0",
            "[demo] snapshot after-empty-dispatch-drain => queued=0, active=0, completed=0",
        ],
    ),
    (
        "network-demo",
        [
            "cargo",
            "run",
            "-p",
            "safeclaw-sqlite",
            "--example",
            "worker_loop_network_demo",
            "--quiet",
        ],
        [
            "[demo] execution summary => worker=Uncertain, effect=Uncertain",
            "[demo] final summary => worker=Succeeded, effect=Executed, completed=true",
        ],
    ),
    (
        "persisted-probe-demo",
        [
            "cargo",
            "run",
            "-p",
            "safeclaw-sqlite",
            "--example",
            "worker_loop_persisted_probe_demo",
            "--quiet",
        ],
        [
            "[demo] reclaim before expiry => true",
            "[demo] probe recovery => from=Uncertain, worker=Succeeded, effect=Executed, completed=true",
        ],
    ),
    (
        "orchestrator-read-fanout-demo",
        [
            "cargo",
            "run",
            "-p",
            "safeclaw-sqlite",
            "--example",
            "orchestrator_scope_read_fanout_demo",
            "--quiet",
        ],
        [
            "[demo] first read claim => task=task-shared-read-1",
            "[demo] snapshot after-two-read-claims => queued=0, active=2, completed=0",
        ],
    ),
    (
        "orchestrator-write-under-reads-demo",
        [
            "cargo",
            "run",
            "-p",
            "safeclaw-sqlite",
            "--example",
            "orchestrator_scope_write_under_reads_demo",
            "--quiet",
        ],
        [
            "[demo] write-under-reads claim => task=task-shared-write-after-reads",
            "[demo] snapshot after-three-claims => queued=0, active=3, completed=0",
        ],
    ),
    (
        "orchestrator-write-serial-demo",
        [
            "cargo",
            "run",
            "-p",
            "safeclaw-sqlite",
            "--example",
            "orchestrator_scope_write_serial_under_reads_demo",
            "--quiet",
        ],
        [
            "[demo] second write blocked while first write active => true",
            "[demo] snapshot after-second-write-claim => queued=0, active=3, completed=1",
        ],
    ),
    (
        "worker-read-fanout-demo",
        [
            "cargo",
            "run",
            "-p",
            "safeclaw-sqlite",
            "--example",
            "worker_loop_read_fanout_demo",
            "--quiet",
        ],
        [
            "[demo] second read outcome => worker=Succeeded, effect=Executed, completed=true",
            "[demo] snapshot after-second-read-complete => queued=0, active=1, completed=1",
        ],
    ),
    (
        "worker-write-under-reads-demo",
        [
            "cargo",
            "run",
            "-p",
            "safeclaw-sqlite",
            "--example",
            "worker_loop_write_under_reads_demo",
            "--quiet",
        ],
        [
            "[demo] write outcome => worker=Succeeded, effect=Executed, completed=true",
            "[demo] snapshot after-write-complete => queued=0, active=2, completed=1",
        ],
    ),
    (
        "worker-write-serial-demo",
        [
            "cargo",
            "run",
            "-p",
            "safeclaw-sqlite",
            "--example",
            "worker_loop_write_serial_under_reads_demo",
            "--quiet",
        ],
        [
            "[demo] second write blocked while first write active => true",
            "[demo] snapshot after-second-write-complete => queued=0, active=2, completed=2",
        ],
    ),
    (
        "worker-scope-conflict-demo",
        [
            "cargo",
            "run",
            "-p",
            "safeclaw-sqlite",
            "--example",
            "worker_loop_scope_conflict_demo",
            "--quiet",
        ],
        [
            "[demo] only conflicting task remains => true",
            "[demo] snapshot after-shared-task-complete => queued=0, active=0, completed=3",
        ],
    ),
    (
        "resume-demo",
        [
            "cargo",
            "run",
            "-p",
            "safeclaw-sqlite",
            "--example",
            "worker_loop_resume_demo",
            "--quiet",
        ],
        [
            "[demo] resume attempt => worker=Succeeded, effect=Executed, completed=true",
            "[demo] snapshot after-resume-complete => queued=0, active=0, completed=1",
        ],
    ),
    (
        "retry-demo",
        [
            "cargo",
            "run",
            "-p",
            "safeclaw-sqlite",
            "--example",
            "worker_loop_retry_demo",
            "--quiet",
        ],
        [
            "[demo] retry attempt => worker=Succeeded, effect=Executed, completed=true",
            "[demo] snapshot after-retry-complete => queued=0, active=0, completed=1",
        ],
    ),
    (
        "resume-missing-runtime-demo",
        [
            "cargo",
            "run",
            "-p",
            "safeclaw-sqlite",
            "--example",
            "worker_loop_resume_missing_runtime_demo",
            "--quiet",
        ],
        [
            "[demo] missing persisted runtime => task=task-worker-loop-missing-resume-demo effect=effect-worker-loop-missing-resume-demo",
            "[demo] snapshot after-missing-runtime-error => queued=0, active=1, completed=0",
        ],
    ),
    (
        "retry-missing-runtime-demo",
        [
            "cargo",
            "run",
            "-p",
            "safeclaw-sqlite",
            "--example",
            "worker_loop_retry_missing_runtime_demo",
            "--quiet",
        ],
        [
            "[demo] missing persisted runtime => task=task-worker-loop-missing-retry-demo effect=effect-worker-loop-missing-retry-demo",
            "[demo] snapshot after-missing-runtime-error => queued=0, active=1, completed=0",
        ],
    ),
    (
        "resume-conflict-demo",
        [
            "cargo",
            "run",
            "-p",
            "safeclaw-sqlite",
            "--example",
            "worker_loop_resume_conflict_demo",
            "--quiet",
        ],
        [
            "[demo] resume attempt => worker=Succeeded, effect=Executed, completed=true",
            "[demo] shared output exists => false",
        ],
    ),
    (
        "resume-release-demo",
        [
            "cargo",
            "run",
            "-p",
            "safeclaw-sqlite",
            "--example",
            "worker_loop_resume_release_demo",
            "--quiet",
        ],
        [
            "[demo] release attempt => worker=Succeeded, effect=Executed, completed=true",
            "[demo] shared output exists => true",
        ],
    ),
    (
        "retry-conflict-demo",
        [
            "cargo",
            "run",
            "-p",
            "safeclaw-sqlite",
            "--example",
            "worker_loop_retry_conflict_demo",
            "--quiet",
        ],
        [
            "[demo] retry attempt => worker=Succeeded, effect=Executed, completed=true",
            "[demo] shared output exists => false",
        ],
    ),
    (
        "retry-pre-exec-demo",
        [
            "cargo",
            "run",
            "-p",
            "safeclaw-sqlite",
            "--example",
            "worker_loop_retry_pre_exec_spawn_demo",
            "--quiet",
        ],
        [
            "[demo] retry spawn error => Sandbox(Executor(Spawn(Error { kind: NotFound, message: \"program not found\" })))",
            "[demo] resume completion => worker=Succeeded, effect=Executed, completed=true",
        ],
    ),
    (
        "retry-release-demo",
        [
            "cargo",
            "run",
            "-p",
            "safeclaw-sqlite",
            "--example",
            "worker_loop_retry_release_demo",
            "--quiet",
        ],
        [
            "[demo] release attempt => worker=Succeeded, effect=Executed, completed=true",
            "[demo] shared output exists => true",
        ],
    ),
    (
        "batch-demo",
        [
            "cargo",
            "run",
            "-p",
            "safeclaw-sqlite",
            "--example",
            "worker_loop_batch_demo",
            "--quiet",
        ],
        [
            "[demo] drained batch => count=2",
            "[demo] snapshot after-batch-complete => queued=0, active=0, completed=2",
        ],
    ),
    (
        "batch-conflict-demo",
        [
            "cargo",
            "run",
            "-p",
            "safeclaw-sqlite",
            "--example",
            "worker_loop_batch_conflict_demo",
            "--quiet",
        ],
        [
            "[demo] drained outcomes => 2",
            "[demo] shared output exists => false",
        ],
    ),
    (
        "batch-failure-demo",
        [
            "cargo",
            "run",
            "-p",
            "safeclaw-sqlite",
            "--example",
            "worker_loop_batch_failure_demo",
            "--quiet",
        ],
        [
            "[demo] batch short-circuit error => Sandbox(Executor(Spawn(Error { kind: NotFound, message: \"program not found\" })))",
            "[demo] restored runtimes => one=Succeeded/Executed, two=Executing/Prepared",
        ],
    ),
    (
        "batch-release-demo",
        [
            "cargo",
            "run",
            "-p",
            "safeclaw-sqlite",
            "--example",
            "worker_loop_batch_release_demo",
            "--quiet",
        ],
        [
            "[demo] release outcomes => 1",
            "[demo] shared output exists => true",
        ],
    ),
    (
        "worker-loop-demo",
        [
            "cargo",
            "run",
            "-p",
            "safeclaw-sqlite",
            "--example",
            "worker_loop_demo",
            "--quiet",
        ],
        [
            "[demo] final summary => worker=Succeeded, effect=Executed, completed=true",
            "[demo] snapshot after-complete => queued=0, active=0, completed=1",
        ],
    ),
    (
        "worker-renew-demo",
        [
            "cargo",
            "run",
            "-p",
            "safeclaw-sqlite",
            "--example",
            "worker_loop_renew_demo",
            "--quiet",
        ],
        [
            "[demo] reclaim before renewed expiry => true",
            "[demo] retry attempt => worker=Succeeded, effect=Executed, completed=true",
        ],
    ),
    (
        "worker-scope-read-demo",
        [
            "cargo",
            "run",
            "-p",
            "safeclaw-sqlite",
            "--example",
            "worker_loop_scope_read_demo",
            "--quiet",
        ],
        [
            "[demo] remaining write still blocked => true",
            "[demo] snapshot after-write-complete => queued=0, active=0, completed=3",
        ],
    ),
]


def collect_errors() -> list[str]:
    errors: list[str] = []

    for name, command, expected_markers in CHECKS:
        try:
            completed = subprocess.run(
                command,
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
        except OSError as error:
            errors.append(f"{name} 无法启动: {error}")
            continue

        output = ((completed.stdout or "") + (completed.stderr or "")).rstrip()
        if completed.returncode != 0:
            errors.append(f"{name} 执行失败: exit={completed.returncode}")
            continue
        for marker in expected_markers:
            if marker not in output:
                errors.append(f"{name} 输出缺少关键文本: {marker}")

    return errors


def main() -> int:
    errors = collect_errors()
    if errors:
        print("Example smoke check failed:")
        for item in errors:
            print(f"- {item}")
        return 1

    print("Example smoke check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
