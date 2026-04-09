from __future__ import annotations

import unittest

from tools.mvp import skill_library
from tools.mvp import task_queue


class SkillLibraryTest(unittest.TestCase):
    def build_task(
        self,
        task_id: str,
        *,
        skill_id: str = "",
        task_kind: str = "",
    ) -> task_queue.TaskQueueTask:
        return task_queue.TaskQueueTask.new(
            task_id,
            task_queue.TaskQueueIntent.write(f"scope:/tmp/{task_id}.txt"),
            0,
            skill_id=skill_id,
            task_kind=task_kind,
        )

    def test_register_and_resolve_skill_by_id(self) -> None:
        library = skill_library.InMemorySkillLibrary()

        def write_handler(claim: task_queue.TaskQueueClaim) -> str:
            return f"handled:{claim.task.task_id}"

        library.register(
            "skill.file.write",
            "file.write",
            write_handler,
            description="handle file write tasks",
        )

        registered = library.resolve("skill.file.write")

        self.assertEqual(registered.skill_id, "skill.file.write")
        self.assertEqual(registered.task_kind, "file.write")
        self.assertEqual(registered.description, "handle file write tasks")
        self.assertIs(registered.handler, write_handler)

    def test_register_rejects_duplicate_skill_id(self) -> None:
        library = skill_library.InMemorySkillLibrary()
        library.register("skill.file.write", "file.write", lambda claim: "first")

        with self.assertRaises(skill_library.SkillLibraryError) as error_context:
            library.register("skill.file.write", "file.other", lambda claim: "second")
        self.assertEqual(error_context.exception.code, "duplicate_skill_id")

    def test_resolve_for_task_kind_uses_unique_skill(self) -> None:
        library = skill_library.InMemorySkillLibrary()
        library.register("skill.file.write", "file.write", lambda claim: "ok")

        resolved = library.resolve_for_task_kind("file.write")

        self.assertEqual(resolved.skill_id, "skill.file.write")

    def test_resolve_for_task_kind_rejects_ambiguous_task_kind(self) -> None:
        library = skill_library.InMemorySkillLibrary()
        library.register("skill.file.write", "file.write", lambda claim: "one")
        library.register("skill.file.write.alt", "file.write", lambda claim: "two")

        with self.assertRaises(skill_library.SkillLibraryError) as error_context:
            library.resolve_for_task_kind("file.write")
        self.assertEqual(error_context.exception.code, "task_kind_ambiguous")
        self.assertEqual(
            error_context.exception.details["skill_ids"],
            ("skill.file.write", "skill.file.write.alt"),
        )

    def test_resolve_for_task_prefers_skill_id_and_checks_task_kind_mismatch(self) -> None:
        library = skill_library.InMemorySkillLibrary()
        library.register("skill.file.write", "file.write", lambda claim: "ok")

        resolved = library.resolve_for_task(
            self.build_task(
                "task-1",
                skill_id="skill.file.write",
                task_kind="file.write",
            )
        )
        self.assertEqual(resolved.skill_id, "skill.file.write")

        with self.assertRaises(skill_library.SkillLibraryError) as error_context:
            library.resolve_for_task(
                self.build_task(
                    "task-2",
                    skill_id="skill.file.write",
                    task_kind="file.retry",
                )
            )
        self.assertEqual(error_context.exception.code, "skill_task_kind_mismatch")

    def test_resolve_for_task_rejects_missing_binding(self) -> None:
        library = skill_library.InMemorySkillLibrary()
        with self.assertRaises(skill_library.SkillLibraryError) as error_context:
            library.resolve_for_task(self.build_task("task-3"))
        self.assertEqual(error_context.exception.code, "task_not_skill_bound")


if __name__ == "__main__":
    unittest.main()
