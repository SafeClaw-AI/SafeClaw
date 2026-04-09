from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class TaskQueueIntent:
    target_scope: str
    requires_write: bool
    doctor_bypass: bool = False

    @classmethod
    def write(cls, target_scope: str) -> "TaskQueueIntent":
        return cls(target_scope=target_scope, requires_write=True)

    @classmethod
    def read(cls, target_scope: str) -> "TaskQueueIntent":
        return cls(target_scope=target_scope, requires_write=False)

    def with_doctor_bypass(self) -> "TaskQueueIntent":
        return replace(self, doctor_bypass=True)


@dataclass(frozen=True)
class TaskQueueTask:
    task_id: str
    intent: TaskQueueIntent
    enqueued_at_ms: int
    skill_id: str = ""
    task_kind: str = ""

    @classmethod
    def new(
        cls,
        task_id: str,
        intent: TaskQueueIntent,
        enqueued_at_ms: int,
        *,
        skill_id: str = "",
        task_kind: str = "",
    ) -> "TaskQueueTask":
        return cls(
            task_id=str(task_id).strip(),
            intent=intent,
            enqueued_at_ms=int(enqueued_at_ms),
            skill_id=str(skill_id).strip(),
            task_kind=str(task_kind).strip(),
        )


@dataclass(frozen=True)
class TaskQueueLease:
    lease_id: str
    task_id: str
    owner_id: str
    fencing_token: int
    ttl_ms: int
    expires_at_ms: int


@dataclass(frozen=True)
class TaskQueueClaim:
    task: TaskQueueTask
    lease: TaskQueueLease


@dataclass(frozen=True)
class TaskQueueSnapshot:
    queued_tasks: tuple[TaskQueueTask, ...]
    active_leases: tuple[TaskQueueLease, ...]
    completed_task_ids: tuple[str, ...]


class TaskQueueError(RuntimeError):
    def __init__(self, code: str, **details: object) -> None:
        self.code = code
        self.details = details
        super().__init__(code)


class InMemoryTaskQueue:
    def __init__(self, *, lease_ttl_ms: int = 30_000) -> None:
        self.lease_ttl_ms = int(lease_ttl_ms)
        self._next_lease_seq = 0
        self._queued_tasks: deque[TaskQueueTask] = deque()
        self._active_claims: dict[str, TaskQueueClaim] = {}
        self._completed_task_ids: list[str] = []
        self._next_fencing_token_by_task: dict[str, int] = {}

    def with_lease_ttl_ms(self, lease_ttl_ms: int) -> "InMemoryTaskQueue":
        self.lease_ttl_ms = int(lease_ttl_ms)
        return self

    def enqueue(self, task: TaskQueueTask) -> None:
        task_id = task.task_id
        if task_id in self._completed_task_ids:
            raise TaskQueueError("task_already_completed", task_id=task_id)
        if any(queued.task_id == task_id for queued in self._queued_tasks) or task_id in self._active_claims:
            raise TaskQueueError("task_already_queued", task_id=task_id)
        self._queued_tasks.append(task)

    def claim_next(self, owner_id: str, now_ms: int) -> TaskQueueClaim | None:
        self.reap_expired_leases(now_ms)
        if not self._queued_tasks:
            return None

        task = self._queued_tasks.popleft()
        next_fencing_token = self._next_fencing_token_by_task.get(task.task_id, 0) + 1
        self._next_fencing_token_by_task[task.task_id] = next_fencing_token
        self._next_lease_seq += 1

        claim = TaskQueueClaim(
            task=task,
            lease=TaskQueueLease(
                lease_id=f"{task.task_id}-lease-{self._next_lease_seq}",
                task_id=task.task_id,
                owner_id=owner_id,
                fencing_token=next_fencing_token,
                ttl_ms=self.lease_ttl_ms,
                expires_at_ms=int(now_ms) + self.lease_ttl_ms,
            ),
        )
        self._active_claims[task.task_id] = claim
        return claim

    def renew_lease(
        self,
        task_id: str,
        lease_id: str,
        owner_id: str,
        now_ms: int,
    ) -> TaskQueueLease:
        claim = self._require_active_claim(task_id, lease_id, owner_id)
        if int(now_ms) > claim.lease.expires_at_ms:
            raise TaskQueueError(
                "lease_expired",
                task_id=task_id,
                lease_id=lease_id,
                now_ms=int(now_ms),
                expires_at_ms=claim.lease.expires_at_ms,
            )
        renewed_lease = replace(
            claim.lease,
            expires_at_ms=int(now_ms) + claim.lease.ttl_ms,
        )
        self._active_claims[task_id] = replace(claim, lease=renewed_lease)
        return renewed_lease

    def reap_expired_leases(self, now_ms: int) -> tuple[TaskQueueLease, ...]:
        expired_task_ids = [
            task_id
            for task_id, claim in self._active_claims.items()
            if int(now_ms) > claim.lease.expires_at_ms
        ]
        expired: list[TaskQueueLease] = []
        for task_id in expired_task_ids:
            claim = self._active_claims.pop(task_id)
            expired.append(claim.lease)
            self._queued_tasks.append(claim.task)
        return tuple(expired)

    def complete(self, task_id: str, lease_id: str, owner_id: str) -> None:
        self._require_active_claim(task_id, lease_id, owner_id)
        self._active_claims.pop(task_id)
        if task_id not in self._completed_task_ids:
            self._completed_task_ids.append(task_id)

    def snapshot(self) -> TaskQueueSnapshot:
        active_leases = tuple(
            sorted(
                (claim.lease for claim in self._active_claims.values()),
                key=lambda lease: (lease.task_id, lease.fencing_token),
            )
        )
        return TaskQueueSnapshot(
            queued_tasks=tuple(self._queued_tasks),
            active_leases=active_leases,
            completed_task_ids=tuple(sorted(self._completed_task_ids)),
        )

    def _require_active_claim(
        self,
        task_id: str,
        lease_id: str,
        owner_id: str,
    ) -> TaskQueueClaim:
        claim = self._active_claims.get(task_id)
        if claim is None or claim.lease.lease_id != lease_id:
            raise TaskQueueError(
                "lease_not_found",
                task_id=task_id,
                lease_id=lease_id,
            )
        if claim.lease.owner_id != owner_id:
            raise TaskQueueError(
                "lease_not_owned",
                task_id=task_id,
                lease_id=lease_id,
                owner_id=owner_id,
            )
        return claim
