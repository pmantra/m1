from __future__ import annotations

from typing import List

import ddtrace.ext
import sqlalchemy.orm.scoping

from direct_payment.clinic.models.user import (
    AccountStatus,
    FertilityClinicUserProfile,
    FertilityClinicUserProfileFertilityClinic,
)
from storage import connection

trace_wrapper = ddtrace.tracer.wrap(span_type=ddtrace.ext.SpanTypes.SQL)


class FertilityClinicUserRepository:
    def __init__(self, session: sqlalchemy.orm.scoping.ScopedSession = None):  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
        self.session = session or connection.db.session

    @trace_wrapper
    def get(
        self, *, fertility_clinic_user_profile_id: int
    ) -> FertilityClinicUserProfile | None:
        return self.session.query(FertilityClinicUserProfile).get(
            fertility_clinic_user_profile_id
        )

    @trace_wrapper
    def get_by_user_id(self, *, user_id: int) -> FertilityClinicUserProfile | None:
        return (
            self.session.query(FertilityClinicUserProfile)
            .filter(FertilityClinicUserProfile.user_id == user_id)
            .one_or_none()
        )

    @trace_wrapper
    def get_by_fertility_clinic_id(
        self, *, fertility_clinic_id: int, status: AccountStatus = AccountStatus.ACTIVE
    ) -> List[FertilityClinicUserProfile]:
        return (
            self.session.query(FertilityClinicUserProfile)
            .join(FertilityClinicUserProfileFertilityClinic)
            .filter(
                FertilityClinicUserProfileFertilityClinic.fertility_clinic_id
                == fertility_clinic_id,
                FertilityClinicUserProfile.status == status,
            )
            .all()
        )
