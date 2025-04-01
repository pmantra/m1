from __future__ import annotations

import ddtrace.ext
import sqlalchemy.orm.scoping
from flask_restful import abort

from direct_payment.clinic.models.clinic import FertilityClinic
from storage import connection

trace_wrapper = ddtrace.tracer.wrap(span_type=ddtrace.ext.SpanTypes.SQL)


class FertilityClinicRepository:
    def __init__(self, session: sqlalchemy.orm.scoping.ScopedSession = None):  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
        self.session = session or connection.db.session

    @trace_wrapper
    def get(self, *, fertility_clinic_id: int) -> FertilityClinic | None:
        clinic = self.session.query(FertilityClinic).get(fertility_clinic_id)
        if not clinic:
            abort(404, message="Matching fertility clinic not found")
        return clinic

    @trace_wrapper
    def get_clinic_by_name(self, *, clinic_name: str) -> FertilityClinic | None:
        return (
            self.session.query(FertilityClinic)
            .filter(FertilityClinic.name == clinic_name)
            .one_or_none()
        )

    @trace_wrapper
    def put(
        self, *, fertility_clinic_id: int, payments_recipient_id: str
    ) -> FertilityClinic:
        fertility_clinic = self.get(fertility_clinic_id=fertility_clinic_id)
        fertility_clinic.payments_recipient_id = payments_recipient_id

        try:
            self.session.add(fertility_clinic)
            self.session.commit()
        except Exception as e:
            abort(400, message="Error updating the fertility clinic record", error=e)

        return fertility_clinic
