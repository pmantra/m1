from datetime import datetime
from typing import Optional

import ddtrace.ext
from sqlalchemy.orm.scoping import ScopedSession

from appointments.models.v2.member_appointment_video_timestamp import (
    AppointmentVideoTimestampStruct,
)
from appointments.utils import query_utils
from appointments.utils.errors import MissingQueryError, QueryNotFoundError

trace_wrapper = ddtrace.tracer.wrap(
    span_type=ddtrace.ext.SpanTypes.SQL,
)

__all__ = ("AppointmentVideoTimestampRepository",)


class AppointmentVideoTimestampRepository:
    model = AppointmentVideoTimestampStruct

    def __init__(self, session: ScopedSession):
        self.session = session

        # Load queries
        queries = query_utils.load_queries_from_file(
            "appointments/repository/v2/queries/appointment_video_timestamp.sql"
        )
        if len(queries) == 0:
            raise QueryNotFoundError()
        if len(queries) != 2:
            raise MissingQueryError()

        self._get_appointment_video_timestamp = queries[0]
        self._set_appointment_json = queries[1]

    def get_appointment_video_timestamp(
        self, appointment_id: int
    ) -> AppointmentVideoTimestampStruct:
        query = self._get_appointment_video_timestamp

        result = self.session.execute(
            query,
            {"appointment_id": appointment_id},
        ).fetchone()
        return self.deserialize(result)

    def set_appointment_video_timestamp(
        self,
        appointment_id: int,
        member_started_at: Optional[datetime] = None,
        member_ended_at: Optional[datetime] = None,
        practitioner_started_at: Optional[datetime] = None,
        practitioner_ended_at: Optional[datetime] = None,
        phone_call_at: Optional[datetime] = None,
        json_str: Optional[str] = None,
    ) -> None:
        query = self._set_appointment_json

        self.session.execute(
            query,
            {
                "appointment_id": appointment_id,
                "member_started_at": member_started_at,
                "member_ended_at": member_ended_at,
                "practitioner_started_at": practitioner_started_at,
                "practitioner_ended_at": practitioner_ended_at,
                "phone_call_at": phone_call_at,
                "json_str": json_str,
                "modified_at": datetime.utcnow(),
            },
        )

    @classmethod
    def deserialize(cls, row):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if row is None:
            return
        return cls.model(**row)
