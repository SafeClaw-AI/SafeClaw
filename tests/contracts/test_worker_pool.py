from __future__ import annotations

import unittest

from tools.mvp import skill_library
from tools.mvp import task_queue
from tools.mvp import worker_pool


class WorkerPoolTest(unittest.TestCase):
    def build_task(
        self,
        task_id: str,
        *,
        scope: str | None = None,
        enqueued_at_ms: int = 0,
        skill_id: str = "",
        task_kind: str = "",
    ) -> task_queue.TaskQueueTask:
        target_scope = scope or f"scope:/tmp/{task_id}.txt"
        return task_queue.TaskQueueTask.new(
            task_id,
            task_queue.TaskQueueIntent.write(target_scope),
            enqueued_at_ms,
            skill_id=skill_id,
            task_kind=task_kind,
        )

    def test_submit_and_run_next_complete_task(self) -> None:
        queue = task_queue.InMemoryTaskQueue()
        pool = worker_pool.InMemoryWorkerPool(queue=queue)
        handled: list[tuple[str, int]] = []

        pool.submit(
            self.build_task("task-1"),
            lambda claim: handled.append((claim.task.task_id, claim.lease.fencing_token))
            or {"status": "ok"},
        )

        outcome = pool.run_next("worker-a", 10)

        self.assertIsNotNone(outcome)
        assert outcome is not None
        self.assertEqual(outcome.status, "completed")
        self.assertEqual(outcome.task_id, "task-1")
        self.assertEqual(outcome.owner_id, "worker-a")
        self.assertEqual(outcome.fencing_token, 1)
        self.assertEqual(outcome.result, {"status": "ok"})
        self.assertEqual(outcome.error, "")
        self.assertEqual(handled, [("task-1", 1)])
        snapshot = pool.snapshot()
        self.assertEqual(snapshot.queue.completed_task_ids, ("task-1",))
        self.assertEqual(snapshot.registered_task_ids, ())
        self.assertEqual(len(snapshot.outcomes), 1)

    def test_drain_until_empty_preserves_fifo_order(self) -> None:
        queue = task_queue.InMemoryTaskQueue()
        pool = worker_pool.InMemoryWorkerPool(queue=queue)
        handled: list[str] = []

        pool.submit(
            self.build_task("task-1", enqueued_at_ms=0),
            lambda claim: handled.append(claim.task.task_id) or "first",
        )
        pool.submit(
            self.build_task("task-2", enqueued_at_ms=1),
            lambda claim: handled.append(claim.task.task_id) or "second",
        )

        outcomes = pool.drain_until_empty("worker-a", 10)

        self.assertEqual([outcome.task_id for outcome in outcomes], ["task-1", "task-2"])
        self.assertEqual([outcome.status for outcome in outcomes], ["completed", "completed"])
        self.assertEqual(handled, ["task-1", "task-2"])

    def test_run_next_returns_none_when_queue_idle(self) -> None:
        pool = worker_pool.InMemoryWorkerPool(queue=task_queue.InMemoryTaskQueue())
        self.assertIsNone(pool.run_next("worker-a", 0))
        self.assertEqual(pool.drain_until_empty("worker-a", 0), ())

    def test_handler_failure_keeps_task_for_retry_after_lease_expiry(self) -> None:
        queue = task_queue.InMemoryTaskQueue().with_lease_ttl_ms(10)
        pool = worker_pool.InMemoryWorkerPool(queue=queue)
        attempts: list[tuple[str, int]] = []

        def flaky_handler(claim: task_queue.TaskQueueClaim) -> str:
            attempts.append((claim.task.task_id, claim.lease.fencing_token))
            if len(attempts) == 1:
                raise RuntimeError("boom")
            return "recovered"

        pool.submit(self.build_task("task-retry"), flaky_handler)

        first = pool.run_next("worker-a", 0)
        self.assertIsNotNone(first)
        assert first is not None
        self.assertEqual(first.status, "failed")
        self.assertEqual(first.error, "boom")
        self.assertEqual(first.fencing_token, 1)
        self.assertEqual(len(pool.snapshot().queue.active_leases), 1)

        self.assertIsNone(pool.run_next("worker-b", 5))

        second = pool.run_next("worker-b", 11)
        self.assertIsNotNone(second)
        assert second is not None
        self.assertEqual(second.status, "completed")
        self.assertEqual(second.result, "recovered")
        self.assertEqual(second.fencing_token, 2)
        self.assertEqual(attempts, [("task-retry", 1), ("task-retry", 2)])
        self.assertEqual(pool.snapshot().queue.completed_task_ids, ("task-retry",))

    def test_submit_passes_through_duplicate_task_rejection(self) -> None:
        queue = task_queue.InMemoryTaskQueue()
        pool = worker_pool.InMemoryWorkerPool(queue=queue)
        task = self.build_task("task-dup")
        pool.submit(task, lambda claim: "ok")

        with self.assertRaises(task_queue.TaskQueueError) as error_context:
            pool.submit(task, lambda claim: "still-not-ok")
        self.assertEqual(error_context.exception.code, "task_already_queued")

    def test_run_next_can_resolve_handler_from_skill_id(self) -> None:
        queue = task_queue.InMemoryTaskQueue()
        library = skill_library.InMemorySkillLibrary()
        pool = worker_pool.InMemoryWorkerPool(queue=queue, skill_library=library)
        handled: list[tuple[str, int]] = []
        pool.register_skill(
            "skill.file.write",
            "file.write",
            lambda claim: handled.append((claim.task.task_id, claim.lease.fencing_token))
            or "skill-ok",
            description="skill-backed handler",
        )

        pool.submit(
            self.build_task(
                "task-skill",
                skill_id="skill.file.write",
                task_kind="file.write",
            )
        )

        outcome = pool.run_next("worker-a", 10)

        self.assertIsNotNone(outcome)
        assert outcome is not None
        self.assertEqual(outcome.status, "completed")
        self.assertEqual(outcome.result, "skill-ok")
        self.assertEqual(handled, [("task-skill", 1)])
        self.assertEqual(pool.snapshot().registered_skill_ids, ("skill.file.write",))

    def test_direct_handler_overrides_skill_resolution(self) -> None:
        queue = task_queue.InMemoryTaskQueue()
        library = skill_library.InMemorySkillLibrary()
        pool = worker_pool.InMemoryWorkerPool(queue=queue, skill_library=library)
        called: list[str] = []
        pool.register_skill(
            "skill.file.write",
            "file.write",
            lambda claim: called.append("skill") or "skill-path",
        )

        pool.submit(
            self.build_task(
                "task-direct",
                skill_id="skill.file.write",
                task_kind="file.write",
            ),
            lambda claim: called.append("direct") or "direct-path",
        )

        outcome = pool.run_next("worker-a", 0)

        self.assertIsNotNone(outcome)
        assert outcome is not None
        self.assertEqual(outcome.result, "direct-path")
        self.assertEqual(called, ["direct"])

    def test_submit_rejects_task_without_handler_or_skill_binding(self) -> None:
        pool = worker_pool.InMemoryWorkerPool(queue=task_queue.InMemoryTaskQueue())

        with self.assertRaises(worker_pool.WorkerPoolError) as error_context:
            pool.submit(self.build_task("task-unbound"))
        self.assertEqual(error_context.exception.code, "handler_or_skill_required")


if __name__ == "__main__":
    unittest.main()
