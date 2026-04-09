from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.mvp.task_queue import TaskQueueIntent, TaskQueueTask
from tools.mvp.worker_pool import InMemoryWorkerPool

ACTION_NAME = "skill-dispatch-demo"
SCHEMA_VERSION = "skill-dispatch-demo.v1"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "target" / "mvp" / "skill-dispatch-demo" / "dispatch_result.txt"
DEFAULT_TASK_ID = "task-skill-dispatch-demo"
DEFAULT_OWNER_ID = "skill-demo-worker"
DEFAULT_CONTENT = "skill dispatch demo"
DEFAULT_SKILL_ID = "skill.demo.write-text"
DEFAULT_TASK_KIND = "demo.write-text"
SUPPORTED_BINDING_MODES = ("skill-id", "task-kind")


def normalize_binding_mode(binding_mode: str) -> str:
    normalized = str(binding_mode).strip().lower()
    if normalized not in SUPPORTED_BINDING_MODES:
        raise ValueError(f"unsupported binding mode: {binding_mode}")
    return normalized


def resolve_output_path(output_path: str | Path) -> Path:
    candidate = Path(output_path).expanduser()
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    return candidate.resolve(strict=False)


def build_demo_pool(output_path: Path, content: str) -> InMemoryWorkerPool:
    pool = InMemoryWorkerPool()

    def write_demo_output(claim) -> dict[str, object]:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        return {
            "task_id": claim.task.task_id,
            "written_content": content,
            "output_path": str(output_path),
        }

    pool.register_skill(
        DEFAULT_SKILL_ID,
        DEFAULT_TASK_KIND,
        write_demo_output,
        description="Write a tiny demo file through skill-library backed worker dispatch.",
    )
    return pool


def build_demo_task(
    task_id: str,
    output_path: Path,
    *,
    binding_mode: str,
) -> TaskQueueTask:
    normalized_mode = normalize_binding_mode(binding_mode)
    skill_id = DEFAULT_SKILL_ID if normalized_mode == "skill-id" else ""
    return TaskQueueTask.new(
        task_id,
        TaskQueueIntent.write(f"scope:{output_path.as_posix()}"),
        0,
        skill_id=skill_id,
        task_kind=DEFAULT_TASK_KIND,
    )


def build_queue_summary(pool: InMemoryWorkerPool) -> dict[str, int]:
    snapshot = pool.snapshot().queue
    return {
        "queued": len(snapshot.queued_tasks),
        "active": len(snapshot.active_leases),
        "completed": len(snapshot.completed_task_ids),
    }


def run_skill_dispatch_demo(
    *,
    task_id: str,
    output_path: str | Path,
    content: str,
    binding_mode: str = "skill-id",
    owner_id: str = DEFAULT_OWNER_ID,
) -> dict[str, object]:
    resolved_output_path = resolve_output_path(output_path)
    normalized_binding_mode = normalize_binding_mode(binding_mode)
    pool = build_demo_pool(resolved_output_path, content)
    task = build_demo_task(
        task_id.strip(),
        resolved_output_path,
        binding_mode=normalized_binding_mode,
    )
    pool.submit(task)
    outcome = pool.run_next(owner_id, 0)
    if outcome is None:
        raise RuntimeError("worker pool returned no outcome for queued demo task")

    snapshot = pool.snapshot()
    return {
        "task_id": task.task_id,
        "binding_mode": normalized_binding_mode,
        "skill_id": task.skill_id,
        "task_kind": task.task_kind,
        "owner_id": owner_id,
        "status": outcome.status,
        "output_path": str(resolved_output_path),
        "file_exists": resolved_output_path.exists(),
        "result": outcome.result,
        "error": outcome.error,
        "registered_skill_ids": list(snapshot.registered_skill_ids),
        "registered_task_ids": list(snapshot.registered_task_ids),
        "queue": build_queue_summary(pool),
    }


def emit_json_result(result: object, *, exit_code: int) -> int:
    payload = {
        "ok": exit_code == 0,
        "action": ACTION_NAME,
        "schema_version": SCHEMA_VERSION,
        "result": result,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return exit_code


def emit_json_error(
    *,
    message: str,
    exit_code: int,
    code: str,
    reason: str,
    details: object,
) -> int:
    payload = {
        "ok": False,
        "action": ACTION_NAME,
        "schema_version": SCHEMA_VERSION,
        "error": {
            "message": message,
            "exit_code": exit_code,
            "code": code,
            "reason": reason,
            "details": details,
        },
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return exit_code


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a minimal real skill-library -> worker-pool dispatch and write the result to disk."
    )
    parser.add_argument("--task-id", default=DEFAULT_TASK_ID)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--content", default=DEFAULT_CONTENT)
    parser.add_argument("--binding-mode", default="skill-id")
    parser.add_argument("--owner-id", default=DEFAULT_OWNER_ID)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        normalize_binding_mode(args.binding_mode)
    except ValueError:
        return emit_json_error(
            message="invalid binding mode",
            exit_code=2,
            code="invalid_binding_mode",
            reason="binding_mode_not_supported",
            details={
                "binding_mode": args.binding_mode,
                "supported_binding_modes": list(SUPPORTED_BINDING_MODES),
            },
        )

    result = run_skill_dispatch_demo(
        task_id=args.task_id,
        output_path=args.output,
        content=args.content,
        binding_mode=args.binding_mode,
        owner_id=args.owner_id,
    )
    exit_code = 0 if str(result.get("status")) == "completed" else 1
    return emit_json_result(result, exit_code=exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
