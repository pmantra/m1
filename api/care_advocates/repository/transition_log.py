from __future__ import annotations

import functools

import ddtrace
import sqlalchemy.orm.scoping
from typing_extensions import Literal

from care_advocates.models.transitions import CareAdvocateMemberTransitionLog
from storage.repository import base


class CareAdvocateMemberTransitionLogRepository(
    base.BaseRepository[CareAdvocateMemberTransitionLog]
):
    """A repository for managing CA-Member Transition Logs"""

    model = CareAdvocateMemberTransitionLog

    # Overriding some functions of BaseRepository given that it was designed not to work with SQLAlchemy models with already instantiated tables
    @classmethod
    @functools.lru_cache(maxsize=1)
    def make_table(cls) -> sqlalchemy.Table:
        return cls.model.__table__

    @classmethod
    def table_name(cls) -> str:
        return cls.model.__tablename__

    @staticmethod
    def table_columns() -> tuple[sqlalchemy.Column, ...]:
        # This function is only used during BaseRepository.make_table, which is being overriden here, so there is no need implement table_columns()
        return ()

    @staticmethod
    def instance_to_values(instance: model) -> dict:  # type: ignore[valid-type] # Variable "care_advocates.repository.transition_log.CareAdvocateMemberTransitionLogRepository.model" is not valid as a type
        return dict(
            id=instance.id,  # type: ignore[attr-defined] # model? has no attribute "id"
            user_id=instance.user_id,  # type: ignore[attr-defined] # model? has no attribute "user_id"
            date_completed=instance.date_completed,  # type: ignore[attr-defined] # model? has no attribute "date_completed"
            date_scheduled=instance.date_scheduled,  # type: ignore[attr-defined] # model? has no attribute "date_scheduled"
            uploaded_filename=instance.uploaded_filename,  # type: ignore[attr-defined] # model? has no attribute "uploaded_filename"
            uploaded_content=instance.uploaded_content,  # type: ignore[attr-defined] # model? has no attribute "uploaded_content"
        )

    @ddtrace.tracer.wrap()
    def all(
        self, sort_column: _SortColumnT = "date_transition"
    ) -> list[CareAdvocateMemberTransitionLog]:
        transition_logs = self.session.query(CareAdvocateMemberTransitionLog).all()

        # We would like to do the sorting in the db with order_by, but we cannot given that date_transition is a property, not a field
        if sort_column == "created_at":
            transition_logs.sort(key=lambda x: x.created_at, reverse=True)
        elif sort_column == "date_transition":
            transition_logs.sort(key=lambda x: x.date_transition, reverse=True)  # type: ignore[arg-type,return-value] # Argument "key" to "sort" of "list" has incompatible type "Callable[[CareAdvocateMemberTransitionLog], DateTime]"; expected "Callable[[CareAdvocateMemberTransitionLog], Union[SupportsDunderLT[Any], SupportsDunderGT[Any]]]" #type: ignore[return-value] # Incompatible return value type (got "DateTime", expected "Union[SupportsDunderLT[Any], SupportsDunderGT[Any]]")

        return transition_logs


_SortColumnT = Literal["created_at", "date_transition"]
