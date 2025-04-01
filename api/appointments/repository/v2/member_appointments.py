from __future__ import annotations

from datetime import datetime

import ddtrace.ext
from dateutil.relativedelta import relativedelta
from sqlalchemy.orm.scoping import ScopedSession

from appointments.models.v2.member_appointments import MemberAppointmentsListElement
from appointments.schemas.v2.member_appointments import OrderDirections
from appointments.utils import query_utils
from appointments.utils.errors import MissingQueryError, QueryNotFoundError

__all__ = ("MemberAppointmentsListRepository",)

trace_wrapper = ddtrace.tracer.wrap(
    span_type=ddtrace.ext.SpanTypes.SQL,
)


class MemberAppointmentsListRepository:
    model = MemberAppointmentsListElement

    def __init__(self, session: ScopedSession):
        self.session = session

        # Load queries
        queries = query_utils.load_queries_from_file(
            "appointments/repository/v2/queries/member_appointments.sql"
        )
        if len(queries) == 0:
            raise QueryNotFoundError()
        if len(queries) != 4:
            raise MissingQueryError()

        self._get_member_appointments_asc = queries[0]
        self._get_member_appointments_desc = queries[1]
        self._get_member_appointments_count = queries[2]
        self._get_payment_pending_appointment_ids = queries[3]

    def list_member_appointments(
        self,
        member_id: int,
        scheduled_start: datetime,
        scheduled_end: datetime,
        order_direction: str = OrderDirections.desc,
        limit: int = 10,
        offset: int = 0,
    ) -> list[MemberAppointmentsListElement]:

        if order_direction == OrderDirections.asc:
            query = self._get_member_appointments_asc
        else:
            query = self._get_member_appointments_desc

        # We have to join on schedule here, but in triforce this wont be needed
        # as we will have member_id in the appointment table
        result = self.session.execute(
            query,
            {
                "member_id": member_id,
                "scheduled_start": scheduled_start.isoformat(),
                "scheduled_end": scheduled_end.isoformat(),
                "limit": limit,
                "offset": offset,
            },
        ).fetchall()
        return self.deserialize_list(result)

    def count_member_appointments(
        self,
        member_id: int,
        scheduled_start: datetime,
        scheduled_end: datetime,
    ) -> int:
        result = self.session.execute(
            self._get_member_appointments_count,
            {
                "member_id": member_id,
                "scheduled_start": scheduled_start.isoformat(),
                "scheduled_end": scheduled_end.isoformat(),
            },
        )
        return next(result)[0]

    def get_payment_pending_appointment_ids(
        self,
        num_days: int = 14,
    ) -> list[int]:
        results = list(
            self.session.execute(
                self._get_payment_pending_appointment_ids,
                {
                    "scheduled_start_cutoff": datetime.utcnow()
                    - relativedelta(days=num_days),
                },
            )
        )
        # The returned format is like [(1,), ...] and we want to unwrap it to [1, ...]
        return [result[0] for result in results]

    @classmethod
    def deserialize_list(cls, rows) -> list[MemberAppointmentsListElement]:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        if rows is None:
            return []
        return [cls.model(**row) for row in rows]
