from __future__ import annotations

import ddtrace.ext
from sqlalchemy import Column, DateTime, Integer, String

from activity import models
from storage.repository import abstract, base

__all__ = ("UserActivityRepository",)


trace_wrapper = ddtrace.tracer.wrap(
    span_type=ddtrace.ext.SpanTypes.SQL,
)


class UserActivityRepository(base.BaseRepository[models.UserActivity]):  # type: ignore[type-var] # Type argument "UserActivity" of "BaseRepository" must be a subtype of "Instance"
    model = models.UserActivity

    @classmethod
    def table_name(cls) -> str:
        return "user_activity"

    @staticmethod
    def table_columns() -> tuple[Column, ...]:
        return (
            Column("user_id", Integer),
            Column("activity_type", String),
            Column("activity_date", DateTime),
        )

    @staticmethod
    def instance_to_values(instance: abstract.InstanceT) -> dict:  # type: ignore[override] # Signature of "instance_to_values" incompatible with supertype "BaseRepository"
        return dict(
            id=instance.id,
            user_id=instance.user_id,  # type: ignore[attr-defined] # "abstract.InstanceT" has no attribute "user_id"
            activity_type=instance.activity_type,  # type: ignore[attr-defined] # "abstract.InstanceT" has no attribute "activity_type"
            activity_date=instance.activity_date,  # type: ignore[attr-defined] # "abstract.InstanceT" has no attribute "activity_date"
        )

    @trace_wrapper
    def get_by_user_id(self, *, user_id: int) -> list[models.UserActivity] | None:
        if user_id is None:
            return

        where = self.table.c.user_id == user_id
        result = self.execute_select(where=where)
        entries = [self.deserialize(row) for row in result.fetchall()]
        return entries  # type: ignore[return-value] # Incompatible return value type (got "List[Optional[UserActivity]]", expected "Optional[List[UserActivity]]")

    @trace_wrapper
    def get_by_activity_type(
        self, *, user_id: int, activity_type: str
    ) -> list[models.UserActivity] | None:
        if not user_id or not activity_type:
            return  # type: ignore[return-value] # Return value expected

        where = (self.table.c.user_id == user_id) & (
            self.table.c.activity_type == activity_type
        )
        result = self.execute_select(where=where)
        entries = [self.deserialize(row) for row in result.fetchall()]
        return entries  # type: ignore[return-value] # Incompatible return value type (got "List[Optional[UserActivity]]", expected "Optional[List[UserActivity]]")

    @trace_wrapper
    def delete_by_user_id(self, *, user_id: int) -> int | None:
        if user_id is None:
            return

        delete = self.table.delete(whereclause=self.table.c.user_id == user_id)
        result = self.session.execute(delete)
        if not self.is_in_uow:
            self.session.commit()
        affected: int = result.rowcount
        return affected
