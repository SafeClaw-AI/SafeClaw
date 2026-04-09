from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from tools.mvp.task_queue import (
    InMemoryTaskQueue,
    TaskQueueClaim,
    TaskQueueError,
    TaskQueueSnapshot,
    TaskQueueTask,
)

WorkerTaskHandler = Callable[[TaskQueueClaim], object]


@dataclass(frozen=True)
class WorkerRunOutcome:
    task_id: str
    owner_id: str
    lease_id: str
    fencing_token: int
    status: str
    result: object | None
    error: str


@dataclass(frozen=True)
class WorkerPoolSnapshot:
    queue: TaskQueueSnapshot
    registered_task_ids: tuple[str, ...]
    outcomes: tuple[WorkerRunOutcome, ...]


class WorkerPoolError(RuntimeError):
    def __init__(self, code: str, **details: object) -> None:
        self.code = code
        self.details = details
        super().__init__(code)


class InMemoryWorkerPool:
    def __init__(self, *, queue: InMemoryTaskQueue | None = None) -> None:
        self.queue = queue or InMemoryTaskQueue()
        self._handlers: dict[str, WorkerTaskHandler] = {}
        self._outcomes: list[WorkerRunOutcome] = []

    def submit(self, task: TaskQueueTask, handler: WorkerTaskHandler) -> None:
        if not callable(handler):
            raise TypeError("worker handler must be callable")
        self.queue.enqueue(task)
        self._handlers[task.task_id] = handler

    def run_next(self, owner_id: str, now_ms: int) -> WorkerRunOutcome | None:
        claim = self.queue.claim_next(owner_id, now_ms)
        if claim is None:
            return None

        handler = self._handlers.get(claim.task.task_id)
        if handler is None:
            raise WorkerPoolError(
                "handler_missing",
                task_id=claim.task.task_id,
                owner_id=owner_id,
            )

        try:
            result = handler(claim)
        except Exception as error:
            outcome = WorkerRunOutcome(
                task_id=claim.task.task_id,
                owner_id=owner_id,
                lease_id=claim.lease.lease_id,
                fencing_token=claim.lease.fencing_token,
                status="failed",
                result=None,
                error=str(error).strip() or error.__class__.__name__,
            )
            self._outcomes.append(outcome)
            return outcome

        self.queue.complete(claim.task.task_id, claim.lease.lease_id, owner_id)
        self._handlers.pop(claim.task.task_id, None)
        outcome = WorkerRunOutcome(
            task_id=claim.task.task_id,
            owner_id=owner_id,
            lease_id=claim.lease.lease_id,
            fencing_token=claim.lease.fencing_token,
            status="completed",
            result=result,
            error="",
        )
        self._outcomes.append(outcome)
        return outcome

    def drain_until_empty(
        self,
        owner_id: str,
        now_ms: int,
        *,
        step_ms: int = 1,
        max_steps: int = 100,
    ) -> tuple[WorkerRunOutcome, ...]:
        if max_steps < 1:
            raise WorkerPoolError("invalid_max_steps", max_steps=max_steps)

        outcomes: list[WorkerRunOutcome] = []
        for index in range(max_steps):
            outcome = self.run_next(owner_id, now_ms + (index * step_ms))
            if outcome is None:
                break
            outcomes.append(outcome)
        else:
            raise WorkerPoolError(
                "drain_max_steps_exceeded",
                max_steps=max_steps,
            )
        return tuple(outcomes)

    def snapshot(self) -> WorkerPoolSnapshot:
        return WorkerPoolSnapshot(
            queue=self.queue.snapshot(),
            registered_task_ids=tuple(sorted(self._handlers)),
            outcomes=tuple(self._outcomes),
        )
