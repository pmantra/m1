from typing import List, Optional

import sqlalchemy.orm

from direct_payment.clinic.repository.clinic import FertilityClinicRepository
from storage.connection import db


class FertilityClinicService:
    def __init__(self, session: sqlalchemy.orm.scoping.ScopedSession):
        self.clinics = FertilityClinicRepository(session=session or db.session)

    def get_global_procedure_ids_and_costs_for_clinic(  # type: ignore[return] # Missing return statement
        self, *, fertility_clinic_id: int
    ) -> Optional[List[dict]]:
        """
        Get all of the GlobalProcedures from a clinic's FeeSchedule
        """
        clinic = self.clinics.get(fertility_clinic_id=fertility_clinic_id)
        if clinic and clinic.fee_schedule:
            return [
                {"procedure_id": fs_gp.global_procedure_id, "cost": fs_gp.cost}
                for fs_gp in clinic.fee_schedule.fee_schedule_global_procedures
                if fs_gp.global_procedure_id is not None
            ]

    def get_recipient_id_by_clinic_name(self, *, clinic_name: str) -> Optional[str]:
        clinic = self.clinics.get_clinic_by_name(clinic_name=clinic_name)
        if clinic:
            return clinic.payments_recipient_id
        return None
