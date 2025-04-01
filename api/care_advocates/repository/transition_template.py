from __future__ import annotations

import functools

import ddtrace
import sqlalchemy.orm.scoping
from sqlalchemy import asc
from typing_extensions import Literal

from care_advocates.models.transitions import CareAdvocateMemberTransitionTemplate
from storage.repository import base


class CareAdvocateMemberTransitionTemplateRepository(
    base.BaseRepository[CareAdvocateMemberTransitionTemplate]
):
    """A repository for managing CA-Member Transition Templates"""

    model = CareAdvocateMemberTransitionTemplate

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
    def instance_to_values(instance: model) -> dict:  # type: ignore[valid-type] # Variable "care_advocates.repository.transition_template.CareAdvocateMemberTransitionTemplateRepository.model" is not valid as a type
        return dict(
            id=instance.id,  # type: ignore[attr-defined] # model? has no attribute "id"
            message_type=instance.message_type,  # type: ignore[attr-defined] # model? has no attribute "message_type"
            message_description=instance.message_description,  # type: ignore[attr-defined] # model? has no attribute "message_description"
            message_body=instance.message_body,  # type: ignore[attr-defined] # model? has no attribute "message_body"
        )

    @ddtrace.tracer.wrap()
    def all(
        self, sort_column: _SortColumnT = "message_type"
    ) -> list[CareAdvocateMemberTransitionTemplate]:

        transition_templates = (
            self.session.query(CareAdvocateMemberTransitionTemplate)
            .order_by(asc(getattr(CareAdvocateMemberTransitionTemplate, sort_column)))
            .all()
        )

        return transition_templates


_SortColumnT = Literal["message_type"]
