from __future__ import annotations

import ddtrace.ext
import sqlalchemy.orm

from appointments.models.v2.member_appointment import MemberAppointmentStruct
from appointments.utils import query_utils
from appointments.utils.errors import MissingQueryError, QueryNotFoundError

__all__ = ("MemberAppointmentRepository",)

trace_wrapper = ddtrace.tracer.wrap(
    span_type=ddtrace.ext.SpanTypes.SQL,
)


class MemberAppointmentRepository:
    model = MemberAppointmentStruct

    def __init__(self, session: sqlalchemy.orm.Session):
        self.session = session

        # Load queries
        queries = query_utils.load_queries_from_file(
            "appointments/repository/v2/queries/member_appointment.sql"
        )
        if len(queries) == 0:
            raise QueryNotFoundError()
        if len(queries) != 2:
            raise MissingQueryError()

        self._get_member_appointment_query = queries[0]
        self._get_current_or_next_appointment_query = queries[1]

    def get_by_id(
        self,
        appointment_id: int,
    ) -> MemberAppointmentStruct:
        query = self._get_member_appointment_query
        result = self.session.execute(
            query, {"appointment_id": appointment_id}
        ).fetchone()
        return self.deserialize(result)

    def get_current_or_next(self, member_id: int) -> MemberAppointmentStruct:
        query = self._get_current_or_next_appointment_query
        result = self.session.execute(query, {"member_id": member_id}).first()
        return self.deserialize(result)

    @classmethod
    def deserialize(cls, row):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if row is None:
            return
        return cls.model(**row)
