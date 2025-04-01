from __future__ import annotations

import builtins

import ddtrace

from configuration import load_bool
from preferences import models, repository
from storage.unit_of_work import SQLAlchemyUnitOfWork

__all__ = (
    "get_preference_service",
    "PreferenceService",
    "PreferenceNotFoundError",
)


def get_preference_service() -> PreferenceService:
    return PreferenceService()


class PreferenceService:
    @staticmethod
    def uow() -> SQLAlchemyUnitOfWork[repository.PreferenceRepository]:
        return SQLAlchemyUnitOfWork(repository.PreferenceRepository)

    @ddtrace.tracer.wrap()
    def create(self, *, name: str, default_value: str, type: str) -> models.Preference:
        with self.uow() as uow:
            preference = uow.get_repo(repository.PreferenceRepository).create(
                instance=models.Preference(
                    name=name,
                    default_value=default_value,
                    type=type,
                )
            )
            uow.commit()
            return preference

    @ddtrace.tracer.wrap()
    def get(self, *, id: int) -> models.Preference | None:
        with self.uow() as uow:
            return uow.get_repo(repository.PreferenceRepository).get(id=id)

    @ddtrace.tracer.wrap()
    def get_by_name(self, *, name: str) -> models.Preference | None:
        with self.uow() as uow:
            return uow.get_repo(repository.PreferenceRepository).get_by_name(name=name)

    @ddtrace.tracer.wrap()
    def get_value(self, *, id: int, value: str = None):  # type: ignore[no-untyped-def,assignment] # Function is missing a return type annotation #type: ignore[assignment] # Incompatible default for argument "value" (default has type "None", argument has type "str")
        preference = self.get(id=id)

        if not preference:
            return

        # use the value if provided, otherwise use the preference's default_value
        value_ = value or preference.default_value

        if not value_:
            return

        # this will try to cast preference.type to one of the
        # builtin types (int, float, bool, str, ...)
        # but fall back to str if it isn't able to do the cast.
        # if preference.type is null, treat as str
        type_ = getattr(builtins, preference.type or "str", str)

        # bools are special because bool("something") will always return True
        # and the only way for a bool to return False when casting a string
        # is to pass it an empty string, which we don't want to do
        if type_ == bool:
            return load_bool(value_)
        return type_(value_)


class PreferenceNotFoundError(Exception):
    ...
