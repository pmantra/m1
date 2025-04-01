from __future__ import annotations

import ddtrace.ext
import sqlalchemy.orm.scoping
from sqlalchemy.orm import joinedload

from direct_payment.clinic.models.clinic import FertilityClinicLocation
from storage import connection

trace_wrapper = ddtrace.tracer.wrap(span_type=ddtrace.ext.SpanTypes.SQL)


class FertilityClinicLocationRepository:
    def __init__(self, session: sqlalchemy.orm.scoping.ScopedSession = None):  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
        self.session = session or connection.db.session

    @trace_wrapper
    def get(
        self, *, fertility_clinic_location_id: int
    ) -> FertilityClinicLocation | None:
        clinic_location = self.session.query(FertilityClinicLocation).get(
            fertility_clinic_location_id
        )
        if not clinic_location:
            return  # type: ignore[return-value] # Return value expected
        return clinic_location

    @trace_wrapper
    def get_by_clinic_id(
        self, *, fertility_clinic_id: int
    ) -> list[FertilityClinicLocation] | None:
        clinic_locations = (
            self.session.query(FertilityClinicLocation)
            .filter_by(fertility_clinic_id=fertility_clinic_id)
            .all()
        )
        if not clinic_locations:
            return  # type: ignore[return-value] # Return value expected
        return clinic_locations

    def get_with_clinic(
        self, fertility_clinic_location_id: int
    ) -> FertilityClinicLocation | None:
        clinic_location = (
            self.session.query(FertilityClinicLocation)
            .join(FertilityClinicLocation.fertility_clinic)
            .options(joinedload(FertilityClinicLocation.fertility_clinic))
            .filter(FertilityClinicLocation.id == fertility_clinic_location_id)
            .first()
        )
        return clinic_location
