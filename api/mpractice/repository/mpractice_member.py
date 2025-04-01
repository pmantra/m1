from __future__ import annotations

import functools

import ddtrace.ext
import sqlalchemy.exc
import sqlalchemy.orm
import sqlalchemy.util

from appointments.utils import query_utils
from authn.models.user import User
from mpractice.error import QueryNotFoundError
from mpractice.models.appointment import MPracticeMember
from storage.repository.base import BaseRepository

__all__ = ("MPracticeMemberRepository",)

trace_wrapper = ddtrace.tracer.wrap(
    span_type=ddtrace.ext.SpanTypes.SQL,
)


class MPracticeMemberRepository(BaseRepository[MPracticeMember]):
    model = MPracticeMember

    def __init__(
        self,
        session: sqlalchemy.orm.scoping.ScopedSession = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
        is_in_uow: bool = False,
    ):
        super().__init__(session=session, is_in_uow=is_in_uow)
        queries = query_utils.load_queries_from_file(
            "mpractice/repository/queries/member.sql"
        )
        if len(queries) == 0:
            raise QueryNotFoundError()
        self.get_member_by_id_query = queries[0]

    def get_member_by_id(self, member_id: int) -> MPracticeMember | None:
        row = self.session.execute(
            self.get_member_by_id_query, {"member_id": member_id}
        ).first()
        return self.deserialize(row)

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
