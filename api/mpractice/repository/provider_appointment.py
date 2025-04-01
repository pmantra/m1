from __future__ import annotations

import functools

import ddtrace.ext
import sqlalchemy.orm

from appointments.models.appointment import Appointment
from appointments.utils import query_utils
from mpractice.error import MissingQueryError, QueryNotFoundError
from mpractice.models.appointment import ProviderAppointment
from mpractice.models.note import SessionMetaInfo
from storage.repository.base import BaseRepository

__all__ = ("ProviderAppointmentRepository",)


trace_wrapper = ddtrace.tracer.wrap(
    span_type=ddtrace.ext.SpanTypes.SQL,
)


class ProviderAppointmentRepository(BaseRepository[ProviderAppointment]):
    model = ProviderAppointment

    def __init__(
        self,
        session: sqlalchemy.orm.scoping.ScopedSession = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
        is_in_uow: bool = False,
    ):
        super().__init__(session=session, is_in_uow=is_in_uow)
        queries = query_utils.load_queries_from_file(
            "mpractice/repository/queries/appointment.sql"
        )
        if len(queries) == 0:
            raise QueryNotFoundError()
        if len(queries) != 3:
            raise MissingQueryError()
        self._get_appointment_by_id_query = queries[0]
        self._get_latest_post_session_note_query = queries[1]

    def get_appointment_by_id(self, appointment_id: int) -> ProviderAppointment | None:
        row = self.session.execute(
            self._get_appointment_by_id_query, {"appointment_id": appointment_id}
        ).first()
        return self.deserialize(row)

    def get_latest_post_session_note(
        self, appointment_id: int
    ) -> SessionMetaInfo | None:
        row = self.session.execute(
            self._get_latest_post_session_note_query, {"appointment_id": appointment_id}
        ).first()
        if row is None:
            return None
        return SessionMetaInfo(**row)

    @classmethod
    @functools.lru_cache(maxsize=1)
    def make_table(cls) -> sqlalchemy.Table:
        return cls.appointment_table()

    @classmethod
    def table_columns(cls) -> tuple[sqlalchemy.sql.ColumnElement, ...]:  # type: ignore[override] # Return type "Tuple[ColumnElement[Any], ...]" of "table_columns" incompatible with return type "Tuple[Column[Any], ...]" in supertype "BaseRepository"
        return ()

    @classmethod
    @functools.lru_cache(maxsize=1)
    def appointment_table(cls) -> sqlalchemy.Table:
        return Appointment.__table__
