from __future__ import annotations

import ddtrace
from sqlalchemy import Column, ForeignKey, Integer, String

from preferences import models, repository
from storage.repository import abstract, base

__all__ = ("MemberPreferencesRepository",)


class MemberPreferencesRepository(base.BaseRepository[models.MemberPreference]):  # type: ignore[type-var] # Type argument "MemberPreference" of "BaseRepository" must be a subtype of "Instance"
    model = models.MemberPreference

    @classmethod
    def table_name(cls) -> str:
        return "member_preferences"

    @staticmethod
    def table_columns() -> tuple[Column, ...]:
        return (
            Column("member_id", Integer, ForeignKey("member_profile.user_id")),
            Column("preference_id", Integer, ForeignKey("preference.id")),
            Column("value", String),
        )

    @staticmethod
    def instance_to_values(instance: abstract.InstanceT) -> dict:  # type: ignore[override] # Signature of "instance_to_values" incompatible with supertype "BaseRepository"
        return dict(
            id=instance.id,
            member_id=instance.member_id,  # type: ignore[attr-defined] # "abstract.InstanceT" has no attribute "member_id"
            preference_id=instance.preference_id,  # type: ignore[attr-defined] # "abstract.InstanceT" has no attribute "preference_id"
            value=instance.value,  # type: ignore[attr-defined] # "abstract.InstanceT" has no attribute "value"
        )

    @ddtrace.tracer.wrap()
    def get_by_member_id(self, *, member_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        where = self.table.c.member_id == member_id
        result = self.execute_select(where=where)
        entries = [self.deserialize(row) for row in result.fetchall()]
        return entries

    @ddtrace.tracer.wrap()
    def delete_by_member_id(self, *, member_id: int) -> int:
        if member_id is None:
            return

        delete = self.table.delete(whereclause=self.table.c.member_id == member_id)
        result = self.session.execute(delete)
        if not self.is_in_uow:
            self.session.commit()
        affected: int = result.rowcount
        return affected

    @ddtrace.tracer.wrap()
    def get_by_preference_id(
        self, *, member_id: int, preference_id: int
    ) -> models.MemberPreference | None:
        where = (self.table.c.preference_id == preference_id) & (
            self.table.c.member_id == member_id
        )
        result = self.execute_select(where=where)
        row = result.first()
        return self.deserialize(row)

    @ddtrace.tracer.wrap()
    def get_by_preference_name(
        self, *, member_id: int, preference_name: str
    ) -> models.MemberPreference | None:
        preference_repository: repository.PreferenceRepository = (
            repository.PreferenceRepository()
        )
        preference: models.Preference = preference_repository.get_by_name(
            name=preference_name
        )

        if not preference:
            return  # type: ignore[return-value] # Return value expected

        where = (self.table.c.preference_id == preference.id) & (
            self.table.c.member_id == member_id
        )
        result = self.execute_select(where=where)
        row = result.first()
        return self.deserialize(row)
