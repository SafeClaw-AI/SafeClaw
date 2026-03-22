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
