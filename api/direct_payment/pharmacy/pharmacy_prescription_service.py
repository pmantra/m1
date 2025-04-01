from __future__ import annotations

from sqlalchemy.orm.scoping import scoped_session

from direct_payment.pharmacy.models.pharmacy_prescription import (
    PharmacyPrescription,
    PrescriptionStatus,
)
from direct_payment.pharmacy.repository.pharmacy_prescription import (
    PharmacyPrescriptionRepository,
)


class PharmacyPrescriptionService:
    def __init__(
        self, session: scoped_session = None, is_in_uow: bool = True  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
    ):
        self.pharmacy_prescription_repo = PharmacyPrescriptionRepository(
            session=session, is_in_uow=is_in_uow
        )

    def create_pharmacy_prescription(
        self, *, instance: PharmacyPrescription
    ) -> PharmacyPrescription:
        """
        Method to create a Pharmacy Prescription object and insert it in the DB
        """
        return self.pharmacy_prescription_repo.create(instance=instance)

    def update_pharmacy_prescription(
        self,
        *,
        instance: PharmacyPrescription,
    ) -> PharmacyPrescription:
        """Update an existing Pharmacy Prescription"""

        prescription = self.pharmacy_prescription_repo.update(instance=instance)
        return prescription

    def get_prescription_by_unique_id_status(
        self,
        rx_unique_id: str,
        status: PrescriptionStatus | None = None,
    ) -> PharmacyPrescription | None:
        """
        Retrieve Pharmacy Prescription by a combination of search parameters.
        """
        return self.pharmacy_prescription_repo.get_by_rx_unique_id(
            rx_unique_id=rx_unique_id, status=status
        )

    def get_by_procedure_ids(self, procedure_ids: list[int]) -> list:
        return self.pharmacy_prescription_repo.get_by_procedure_ids(procedure_ids)

    def get_by_reimbursement_request_ids(
        self, reimbursement_request_ids: list[str]
    ) -> list:
        return self.pharmacy_prescription_repo.get_by_reimbursement_request_ids(
            reimbursement_request_ids=reimbursement_request_ids
        )
