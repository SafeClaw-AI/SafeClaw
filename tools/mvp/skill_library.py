from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from tools.mvp.task_queue import TaskQueueClaim, TaskQueueTask

SkillTaskHandler = Callable[[TaskQueueClaim], object]


@dataclass(frozen=True)
class SkillRegistration:
    skill_id: str
    task_kind: str
    description: str
    handler: SkillTaskHandler


@dataclass(frozen=True)
class SkillLibrarySnapshot:
    skill_ids: tuple[str, ...]
    task_kinds: tuple[str, ...]


class SkillLibraryError(RuntimeError):
    def __init__(self, code: str, **details: object) -> None:
        self.code = code
        self.details = details
        super().__init__(code)


class InMemorySkillLibrary:
    def __init__(self) -> None:
        self._skills_by_id: dict[str, SkillRegistration] = {}
        self._skill_ids_by_task_kind: dict[str, list[str]] = {}

    def register(
        self,
        skill_id: str,
        task_kind: str,
        handler: SkillTaskHandler,
        *,
        description: str = "",
    ) -> None:
        normalized_skill_id = self._normalize_required_value(skill_id, field_name="skill_id")
        normalized_task_kind = self._normalize_required_value(task_kind, field_name="task_kind")
        if not callable(handler):
            raise TypeError("skill handler must be callable")
        if normalized_skill_id in self._skills_by_id:
            raise SkillLibraryError(
                "duplicate_skill_id",
                skill_id=normalized_skill_id,
            )

        registration = SkillRegistration(
            skill_id=normalized_skill_id,
            task_kind=normalized_task_kind,
            description=str(description).strip(),
            handler=handler,
        )
        self._skills_by_id[normalized_skill_id] = registration
        self._skill_ids_by_task_kind.setdefault(normalized_task_kind, []).append(
            normalized_skill_id
        )
        self._skill_ids_by_task_kind[normalized_task_kind].sort()

    def resolve(self, skill_id: str) -> SkillRegistration:
        normalized_skill_id = self._normalize_required_value(skill_id, field_name="skill_id")
        registration = self._skills_by_id.get(normalized_skill_id)
        if registration is None:
            raise SkillLibraryError(
                "skill_not_found",
                skill_id=normalized_skill_id,
            )
        return registration

    def resolve_for_task_kind(self, task_kind: str) -> SkillRegistration:
        normalized_task_kind = self._normalize_required_value(task_kind, field_name="task_kind")
        skill_ids = tuple(self._skill_ids_by_task_kind.get(normalized_task_kind, ()))
        if not skill_ids:
            raise SkillLibraryError(
                "task_kind_not_registered",
                task_kind=normalized_task_kind,
            )
        if len(skill_ids) > 1:
            raise SkillLibraryError(
                "task_kind_ambiguous",
                task_kind=normalized_task_kind,
                skill_ids=skill_ids,
            )
        return self.resolve(skill_ids[0])

    def resolve_for_task(self, task: TaskQueueTask) -> SkillRegistration:
        if task.skill_id:
            registration = self.resolve(task.skill_id)
            if task.task_kind and registration.task_kind != task.task_kind:
                raise SkillLibraryError(
                    "skill_task_kind_mismatch",
                    task_id=task.task_id,
                    skill_id=task.skill_id,
                    task_kind=task.task_kind,
                    registered_task_kind=registration.task_kind,
                )
            return registration
        if task.task_kind:
            return self.resolve_for_task_kind(task.task_kind)
        raise SkillLibraryError(
            "task_not_skill_bound",
            task_id=task.task_id,
        )

    def snapshot(self) -> SkillLibrarySnapshot:
        return SkillLibrarySnapshot(
            skill_ids=tuple(sorted(self._skills_by_id)),
            task_kinds=tuple(sorted(self._skill_ids_by_task_kind)),
        )

    def _normalize_required_value(self, value: str, *, field_name: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise SkillLibraryError(
                "invalid_identifier",
                field=field_name,
                value=str(value),
            )
        return normalized
