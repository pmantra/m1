from __future__ import annotations

import ddtrace

from preferences import models, repository, service
from storage.unit_of_work import SQLAlchemyUnitOfWork

__all__ = (
    "get_member_preferences_service",
    "MemberPreferencesService",
    "MemberPreferenceNotFoundError",
)


def get_member_preferences_service() -> MemberPreferencesService:
    return MemberPreferencesService()


class MemberPreferencesService:
    @staticmethod
    def uow() -> SQLAlchemyUnitOfWork[repository.MemberPreferencesRepository]:
        return SQLAlchemyUnitOfWork(repository.MemberPreferencesRepository)

    @ddtrace.tracer.wrap()
    def create(
        self, *, member_id: int, preference_id: int, value: str
    ) -> models.MemberPreference:
        with self.uow() as uow:
            member_preference = uow.get_repo(
                repository.MemberPreferencesRepository
            ).create(
                instance=models.MemberPreference(
                    member_id=member_id,
                    preference_id=preference_id,
                    value=value,
                )
            )
            uow.commit()
            return member_preference

    @ddtrace.tracer.wrap()
    def get(self, *, id: int) -> models.MemberPreference | None:
        with self.uow() as uow:
            return uow.get_repo(repository.MemberPreferencesRepository).get(id=id)

    @ddtrace.tracer.wrap()
    def get_member_preferences(self, *, member_id: int) -> [models.MemberPreference]:  # type: ignore[valid-type] # Bracketed expression "[...]" is not valid as a type
        with self.uow() as uow:
            return uow.get_repo(
                repository.MemberPreferencesRepository
            ).get_by_member_id(member_id=member_id)

    @ddtrace.tracer.wrap()
    def get_by_preference_name(
        self, *, member_id: int, preference_name: str
    ) -> models.MemberPreference | None:
        with self.uow() as uow:
            return uow.get_repo(
                repository.MemberPreferencesRepository
            ).get_by_preference_name(
                member_id=member_id, preference_name=preference_name
            )

    @ddtrace.tracer.wrap()
    def get_value(self, *, id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        member_preference = self.get(id=id)
        if not member_preference:
            return

        preference_service = service.PreferenceService()
        return preference_service.get_value(
            id=member_preference.preference_id,
            value=member_preference.value,
        )

    @ddtrace.tracer.wrap()
    def update_value(
        self,
        *,
        id: int,
        value: str,
    ) -> models.MemberPreference:
        with self.uow() as uow:
            member_preference_repository = uow.get_repo(
                repository.MemberPreferencesRepository
            )

            member_preference = member_preference_repository.get(id=id)
            if member_preference is None:
                raise MemberPreferenceNotFoundError(
                    f"Couldn't find member_preference with id={id}"
                )

            member_preference.value = value
            updated = member_preference_repository.update(instance=member_preference)
            uow.commit()
            return updated


class MemberPreferenceNotFoundError(Exception):
    ...
