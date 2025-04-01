from __future__ import annotations

import functools
from typing import List

import ddtrace.ext
import sqlalchemy.orm

from appointments.utils import query_utils
from authn.models.user import User
from mpractice.error import MissingQueryError, QueryNotFoundError
from mpractice.models.appointment import MPracticePractitioner, Vertical
from storage.repository.base import BaseRepository

__all__ = ("MPracticePractitionerRepository",)

trace_wrapper = ddtrace.tracer.wrap(
    span_type=ddtrace.ext.SpanTypes.SQL,
)


class MPracticePractitionerRepository(BaseRepository[MPracticePractitioner]):
    model = MPracticePractitioner

    def __init__(
        self,
        session: sqlalchemy.orm.scoping.ScopedSession = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
        is_in_uow: bool = False,
    ):
        super().__init__(session=session, is_in_uow=is_in_uow)
        queries = query_utils.load_queries_from_file(
            "mpractice/repository/queries/practitioner.sql"
        )
        if len(queries) == 0:
            raise QueryNotFoundError()
        if len(queries) != 4:
            raise MissingQueryError()

        self._get_practitioner_by_id_query = queries[0]
        self._get_practitioner_subdivision_codes_query = queries[1]
        self._get_practitioner_verticals_query = queries[2]
        self._get_practitioner_states_query = queries[3]

    def get_practitioner_by_id(
        self, practitioner_id: int
    ) -> MPracticePractitioner | None:
        row = self.session.execute(
            self._get_practitioner_by_id_query, {"practitioner_id": practitioner_id}
        ).first()
        return self.deserialize(row)

    def get_practitioner_subdivision_codes(self, practitioner_id: int) -> List[str]:
        rows = self.session.execute(
            self._get_practitioner_subdivision_codes_query,
            {"practitioner_id": practitioner_id},
        ).fetchall()
        if rows is None:
            return []
        return [row.subdivision_code for row in rows]

    def get_practitioner_verticals(self, practitioner_id: int) -> List[Vertical]:
        rows = self.session.execute(
            self._get_practitioner_verticals_query, {"practitioner_id": practitioner_id}
        ).fetchall()
        if rows is None:
            return []
        return [Vertical(**row) for row in rows]

    def get_practitioner_states(self, practitioner_id: int) -> List[str]:
        rows = self.session.execute(
            self._get_practitioner_states_query, {"practitioner_id": practitioner_id}
        ).fetchall()
        if rows is None:
            return []
        return [row.abbreviation for row in rows]

    @classmethod
    @functools.lru_cache(maxsize=1)
    def make_table(cls) -> sqlalchemy.Table:
        return cls.user_table()

    @classmethod
    @functools.lru_cache(maxsize=1)
    def table_columns(cls) -> tuple[sqlalchemy.sql.ColumnElement, ...]:  # type: ignore[override] # Signature of "table_columns" incompatible with supertype "BaseRepository"
        return ()

    @classmethod
    @functools.lru_cache(maxsize=1)
    def user_table(cls) -> sqlalchemy.Table:
        return User.__table__
