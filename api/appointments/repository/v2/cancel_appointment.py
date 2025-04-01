from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import ddtrace.ext
import sqlalchemy.orm

from appointments.models.v2.cancel_appointment import (
    CancelAppointmentStruct,
    CancellationPolicyStruct,
)
from appointments.utils import query_utils
from appointments.utils.errors import QueryError

__all__ = ("CancelAppointmentRepository",)

trace_wrapper = ddtrace.tracer.wrap(
    span_type=ddtrace.ext.SpanTypes.SQL,
)


class CancelAppointmentRepository:
    model = CancelAppointmentStruct

    def __init__(self, session: sqlalchemy.orm.Session):
        self.session = session
        queries = query_utils.load_queries_from_file(
            "appointments/repository/v2/queries/appointment_cancel.sql"
        )
        if len(queries) == 0 or len(queries) != 3:
            raise QueryError()
        self._get_cancel_appointment_struct_by_id_query = queries[0]
        self._update_appointment_for_cancel_query = queries[1]
        self._get_cancelled_by_user_id_query = queries[2]

    def get_cancel_appointment_struct_by_id(
        self,
        appointment_id: int,
    ) -> CancelAppointmentStruct | None:
        result = self.session.execute(
            self._get_cancel_appointment_struct_by_id_query,
            {"appointment_id": appointment_id},
        ).fetchone()

        if result is None:
            return None

        struct = CancelAppointmentStruct(**result)
        # product_price was casted into the float type in the previous line,
        # so we need to manually convert the type to Decimal here.
        struct.product_price = Decimal(struct.product_price)
        # TODO: check the fields are not None, handle the exception (only if the
        # code would break at somewhere else)
        return struct

    def update_appointment_for_cancel(
        self, appointment_id: int, user_id: int, json_str: str
    ) -> None:
        self.session.execute(
            self._update_appointment_for_cancel_query,
            {
                "appointment_id": appointment_id,
                "cancelled_at": datetime.utcnow(),
                "user_id": user_id,
                "json_str": json_str,
                "modified_at": datetime.utcnow(),
            },
        )

    def get_cancelled_by_user_id(self, appointment_id: int) -> int | None:
        result = self.session.execute(
            self._get_cancelled_by_user_id_query,
            {"appointment_id": appointment_id},
        ).first()

        if result:
            for cancelled_by_user_id in result:
                return cancelled_by_user_id
        return None


class MemberCancellationPolicyRepository:
    model = CancellationPolicyStruct

    def __init__(self, session: sqlalchemy.orm.Session):
        self.session = session
        queries = query_utils.load_queries_from_file(
            "appointments/repository/v2/queries/cancellation_policy.sql"
        )
        if len(queries) == 0:
            raise QueryError()
        self._get_cancellation_policy_by_product_id_query = queries[0]

    def get_cancellation_policy_struct(
        self, product_id: int
    ) -> CancellationPolicyStruct | None:
        result = self.session.execute(
            self._get_cancellation_policy_by_product_id_query,
            {"product_id": product_id},
        ).fetchone()
        if result is None:
            return None
        return CancellationPolicyStruct(**result)
