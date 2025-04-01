from __future__ import annotations

import functools

import sqlalchemy.orm.scoping

from care_advocates.models.assignable_advocates import AssignableAdvocate
from storage.repository import base


class AssignableAdvocateRepository(base.BaseRepository[AssignableAdvocate]):
    """A repository for managing Assignable Advocates"""

    model = AssignableAdvocate

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
    def instance_to_values(instance: model) -> dict:  # type: ignore[valid-type] # Variable "care_advocates.repository.assignable_advocate.AssignableAdvocateRepository.model" is not valid as a type
        return dict(
            practitioner_id=instance.practitioner_id,  # type: ignore[attr-defined] # model? has no attribute "practitioner_id"
            marketplace_allowed=instance.marketplace_allowed,  # type: ignore[attr-defined] # model? has no attribute "marketplace_allowed"
            vacation_started_at=instance.vacation_started_at,  # type: ignore[attr-defined] # model? has no attribute "vacation_started_at"
            vacation_ended_at=instance.vacation_ended_at,  # type: ignore[attr-defined] # model? has no attribute "vacation_ended_at"
            max_capacity=instance.max_capacity,  # type: ignore[attr-defined] # model? has no attribute "max_capacity"
            daily_intro_capacity=instance.daily_intro_capacity,  # type: ignore[attr-defined] # model? has no attribute "daily_intro_capacity"
        )

    def get_all_aa_ids(self) -> list[int]:
        all_existing_ca_ids = [
            ca_id_[0]
            for ca_id_ in self.session.query(AssignableAdvocate.practitioner_id).all()
        ]
        return all_existing_ca_ids

    def get_all_by_practitioner_ids(self, ids: list[int]) -> list[model]:  # type: ignore[valid-type] # Variable "care_advocates.repository.assignable_advocate.AssignableAdvocateRepository.model" is not valid as a type
        """Locate a list of AssignableAdvocate objects by practitioner_id."""
        where = self.table.c.practitioner_id.in_(ids)
        result = self.execute_select(where=where)
        rows = result.fetchall()
        return self.deserialize_list(rows)  # type: ignore[arg-type] # Argument 1 to "deserialize_list" of "BaseRepository" has incompatible type "List[RowProxy]"; expected "Optional[List[Mapping[str, Any]]]"
