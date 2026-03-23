from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_ROOT = REPO_ROOT / "safeclaw-sqlite" / "examples"
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
            "[demo] diagnostic uncertain => worker=Uncertain effect=Uncertain attempts=1 events=1 transitions=2 disposition=QueueForManualReview",
            "[demo] diagnostic reconciled => worker=Succeeded effect=Executed attempts=1 events=2 transitions=3 disposition=Resolved",
            "[demo] persisted reconciled runtime",
            "[demo] snapshot after-complete => queued=0, active=0, completed=1",
        ],
    ),
    (
        "worker-service-governance-demo",
        [
            "cargo",
            "run",
            "-p",
            "safeclaw-sqlite",
            "--example",
            "worker_service_governance_demo",
            "--quiet",
        ],
        [
            "[demo] service governance resolved => total=2 resolved=2 confirmation=0 manual_review=0",
            "[demo] service governance resolved tasks => task-worker-service-governance-a,task-worker-service-governance-b",
            "[demo] service governance confirmation => total=1 resolved=0 confirmation=1 manual_review=0",
            "[demo] service governance confirmation tasks => task-worker-service-governance-confirmation",
            "[demo] snapshot after-confirmation => queued=0, active=1, completed=2",
        ],
    ),
    (
        "safeclaw-mvp-entry",
        [
            "cargo",
            "run",
            "-p",
            "safeclaw-sqlite",
            "--example",
            "safeclaw_mvp_entry",
            "--quiet",
        ],
        [
            "[mvp] accepted task => task=task-safeclaw-mvp-",
            "[mvp] run report => polls=3 idle=2 executed=1 probed=0 parked=0",
            "[mvp] governance resolved => total=1 resolved=1 confirmation=0 manual_review=0",
            "[mvp] output exists => true",
            "[mvp] output content => safeclaw mvp entry\\n",
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
            "[demo] executed batch governance => total=3 resolved=3 confirmation=0 manual_review=0",
            "[demo] probe batch governance => total=1 resolved=1 confirmation=0 manual_review=0",
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


def collect_coverage_errors() -> list[str]:
    errors: list[str] = []
    configured_examples: dict[str, str] = {}

    for check_name, command, _ in CHECKS:
        try:
            example_flag_index = command.index("--example")
        except ValueError:
            errors.append(f"{check_name} smoke 命令缺少 --example 参数")
            continue
        if example_flag_index + 1 >= len(command):
            errors.append(f"{check_name} smoke 命令缺少 example 名称")
            continue

        example_name = command[example_flag_index + 1]
        previous = configured_examples.get(example_name)
        if previous is not None:
            errors.append(f"example smoke 重复注册: {example_name} ({previous}, {check_name})")
            continue
        configured_examples[example_name] = check_name

    on_disk_examples = {path.stem for path in EXAMPLES_ROOT.glob("*.rs")}
    for example_name in sorted(on_disk_examples - configured_examples.keys()):
        errors.append(f"新增 example 未纳入 smoke: safeclaw-sqlite/examples/{example_name}.rs")
    for example_name in sorted(configured_examples.keys() - on_disk_examples):
        errors.append(f"smoke 配置引用不存在的 example: {example_name}")

    return errors


def collect_errors() -> list[str]:
    errors = collect_coverage_errors()
    if errors:
        return errors

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
