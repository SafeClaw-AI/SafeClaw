from __future__ import annotations

import unittest

from tools.mvp import task_queue


class TaskQueueTest(unittest.TestCase):
    def assert_queue_error(
        self,
        error_context: unittest.case._AssertRaisesContext[task_queue.TaskQueueError],
        *,
        expected_code: str,
    ) -> task_queue.TaskQueueError:
        error = error_context.exception
        self.assertEqual(error.code, expected_code)
        return error

    def test_claim_next_preserves_fifo_and_snapshot(self) -> None:
        queue = task_queue.InMemoryTaskQueue().with_lease_ttl_ms(25)
        queue.enqueue(
            task_queue.TaskQueueTask.new(
                "task-1",
                task_queue.TaskQueueIntent.write("scope:/tmp/task-1"),
                0,
            )
        )
        queue.enqueue(
            task_queue.TaskQueueTask.new(
                "task-2",
                task_queue.TaskQueueIntent.read("scope:/tmp/task-2"),
                1,
            )
        )

        claim = queue.claim_next("worker-a", 10)

        self.assertIsNotNone(claim)
        assert claim is not None
        self.assertEqual(claim.task.task_id, "task-1")
        self.assertEqual(claim.lease.owner_id, "worker-a")
        self.assertEqual(claim.lease.fencing_token, 1)
        self.assertEqual(claim.lease.expires_at_ms, 35)

        snapshot = queue.snapshot()
        self.assertEqual(len(snapshot.queued_tasks), 1)
        self.assertEqual(snapshot.queued_tasks[0].task_id, "task-2")
        self.assertEqual(len(snapshot.active_leases), 1)
        self.assertEqual(snapshot.active_leases[0].task_id, "task-1")

    def test_enqueue_rejects_duplicate_task_id_when_queued_or_active(self) -> None:
        queue = task_queue.InMemoryTaskQueue()
        task = task_queue.TaskQueueTask.new(
            "task-dup",
            task_queue.TaskQueueIntent.write("scope:/tmp/task-dup"),
            0,
        )
        queue.enqueue(task)

        with self.assertRaises(task_queue.TaskQueueError) as queued_error:
            queue.enqueue(task)
        self.assert_queue_error(queued_error, expected_code="task_already_queued")

        claim = queue.claim_next("worker-a", 0)
        self.assertIsNotNone(claim)
        with self.assertRaises(task_queue.TaskQueueError) as active_error:
            queue.enqueue(task)
        self.assert_queue_error(active_error, expected_code="task_already_queued")

    def test_renew_lease_rejects_expired_lease(self) -> None:
        queue = task_queue.InMemoryTaskQueue().with_lease_ttl_ms(10)
        queue.enqueue(
            task_queue.TaskQueueTask.new(
                "task-expired-renew",
                task_queue.TaskQueueIntent.write("scope:/tmp/task-expired-renew"),
                0,
            )
        )

        claim = queue.claim_next("worker-a", 0)
        self.assertIsNotNone(claim)
        assert claim is not None

        with self.assertRaises(task_queue.TaskQueueError) as error_context:
            queue.renew_lease(
                claim.task.task_id,
                claim.lease.lease_id,
                "worker-a",
                11,
            )
        error = self.assert_queue_error(
            error_context,
            expected_code="lease_expired",
        )
        self.assertEqual(error.details["task_id"], "task-expired-renew")

    def test_reap_expired_leases_requeues_task_and_increments_fencing_token(self) -> None:
        queue = task_queue.InMemoryTaskQueue().with_lease_ttl_ms(10)
        queue.enqueue(
            task_queue.TaskQueueTask.new(
                "task-expire",
                task_queue.TaskQueueIntent.write("scope:/tmp/task-expire"),
                0,
            )
        )

        claim = queue.claim_next("worker-a", 0)
        self.assertIsNotNone(claim)
        assert claim is not None

        expired = queue.reap_expired_leases(11)
        self.assertEqual(len(expired), 1)
        self.assertEqual(expired[0].task_id, "task-expire")

        reclaimed = queue.claim_next("worker-b", 12)
        self.assertIsNotNone(reclaimed)
        assert reclaimed is not None
        self.assertEqual(reclaimed.task.task_id, "task-expire")
        self.assertEqual(reclaimed.lease.owner_id, "worker-b")
        self.assertEqual(reclaimed.lease.fencing_token, 2)

    def test_complete_marks_task_done_and_blocks_reenqueue(self) -> None:
        queue = task_queue.InMemoryTaskQueue()
        task = task_queue.TaskQueueTask.new(
            "task-done",
            task_queue.TaskQueueIntent.write("scope:/tmp/task-done"),
            0,
        )
        queue.enqueue(task)

        claim = queue.claim_next("worker-a", 0)
        self.assertIsNotNone(claim)
        assert claim is not None

        with self.assertRaises(task_queue.TaskQueueError) as wrong_owner_error:
            queue.complete(claim.task.task_id, claim.lease.lease_id, "worker-b")
        self.assert_queue_error(wrong_owner_error, expected_code="lease_not_owned")

        queue.complete(claim.task.task_id, claim.lease.lease_id, "worker-a")
        self.assertIsNone(queue.claim_next("worker-c", 1))
        self.assertEqual(queue.snapshot().completed_task_ids, ("task-done",))

        with self.assertRaises(task_queue.TaskQueueError) as completed_error:
            queue.enqueue(task)
        self.assert_queue_error(completed_error, expected_code="task_already_completed")


if __name__ == "__main__":
    unittest.main()
