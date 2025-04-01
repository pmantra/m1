from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import Optional

from direct_payment.pharmacy.constants import (
    SCHEDULED_FILE_TYPE,
    SMP_AMOUNT_OWED,
    SMP_DRUG_DESCRIPTION,
    SMP_DRUG_NAME,
    SMP_FIRST_NAME,
    SMP_LAST_NAME,
    SMP_MAVEN_ID,
    SMP_NCPDP_NUMBER,
    SMP_NDC_NUMBER,
    SMP_RX_ORDER_ID,
    SMP_RX_RECEIVED_DATE,
    SMP_SCHEDULED_FILE_PREFIX,
    SMP_SCHEDULED_SHIP_DATE,
    SMP_UNIQUE_IDENTIFIER,
)
from direct_payment.pharmacy.models.pharmacy_prescription import (
    PrescriptionStatus,
    ScheduledPharmacyPrescriptionParams,
)
from direct_payment.pharmacy.tasks.libs.common import IS_INTEGRATIONS_K8S_CLUSTER
from direct_payment.pharmacy.tasks.libs.rx_file_processor import FileProcessor
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
    TreatmentProcedureStatus,
    TreatmentProcedureType,
)
from direct_payment.treatment_procedure.repository.treatment_procedures_needing_questionnaires_repository import (
    TreatmentProceduresNeedingQuestionnairesRepository,
)
from direct_payment.treatment_procedure.utils.procedure_helpers import (
    trigger_cost_breakdown,
)
from storage.connection import db
from utils.log import logger
from utils.payments import convert_dollars_to_cents

log = logger(__name__)

JOB_NAME = "smp_process_scheduled_file"

SCHEDULED_FILE_EXPECTED_FIELDS = [
    SMP_NCPDP_NUMBER,
    SMP_FIRST_NAME,
    SMP_LAST_NAME,
    SMP_MAVEN_ID,
    SMP_NDC_NUMBER,
    SMP_DRUG_NAME,
    SMP_AMOUNT_OWED,
    SMP_UNIQUE_IDENTIFIER,
    SMP_SCHEDULED_SHIP_DATE,
    SMP_DRUG_DESCRIPTION,
    SMP_RX_RECEIVED_DATE,
    SMP_RX_ORDER_ID,
]


class ScheduledFileProcessor(FileProcessor):
    def __init__(self, dry_run: bool = False):
        super().__init__(dry_run)
        self.file_type: Optional[str] = SCHEDULED_FILE_TYPE
        self.job_name: Optional[str] = JOB_NAME
        self.expected_fields: Optional[list] = SCHEDULED_FILE_EXPECTED_FIELDS

    def get_file_prefix(self) -> str:
        return SMP_SCHEDULED_FILE_PREFIX

    def get_benefit_id(self, row: dict) -> str:
        return row[SMP_MAVEN_ID]

    def handle_row(self, row: dict) -> None:
        benefit_id = self.get_benefit_id(row=row)
        existing_prescription = self.get_pharmacy_prescription(row=row)
        if existing_prescription:
            log.info(
                f"{self.job_name}: Found existing schedule Pharmacy Prescription",
                pharmacy_prescription_id=existing_prescription.id,
            )
            self.failed_rows.append(
                (
                    benefit_id,
                    row[SMP_UNIQUE_IDENTIFIER],
                    "Duplicate: Found existing schedule Pharmacy "
                    f"Prescription {existing_prescription.id}.",
                )
            )
            return

        wallet = self.validate_wallet(row)
        user = self.validate_user(row, wallet)
        org_settings = self.validate_org_settings(
            row=row, rx_enabled=True, wallet=wallet, user=user
        )

        if not wallet or not user or not org_settings:
            return

        clinic = self.validate_fertility_clinic(row)
        if not clinic:
            return

        global_procedure = self.validate_global_procedure(row)
        if not global_procedure:
            return

        category = self.validate_category(row, wallet)
        if category is None:
            return

        fee_schedule_id = clinic.fee_schedule_id
        cost = convert_dollars_to_cents(float(row[SMP_AMOUNT_OWED]))
        formatted_date = datetime.strptime(row[SMP_RX_RECEIVED_DATE], "%m/%d/%Y").date()
        try:
            treatment_procedure = TreatmentProcedure(
                member_id=user.id,
                reimbursement_wallet_id=wallet.id,
                reimbursement_request_category_id=category.id,
                fee_schedule_id=fee_schedule_id,
                global_procedure_id=global_procedure["id"],
                procedure_name=global_procedure["name"],
                fertility_clinic_id=clinic.id,
                fertility_clinic_location_id=clinic.locations[0].id,
                cost=cost,
                cost_credit=0,
                status=TreatmentProcedureStatus.SCHEDULED,
                start_date=formatted_date,
                end_date=formatted_date,
                procedure_type=TreatmentProcedureType.PHARMACY,
            )
            db.session.add(treatment_procedure)
            db.session.flush()
            TreatmentProceduresNeedingQuestionnairesRepository(
                db.session
            ).create_tpnq_from_treatment_procedure_id(
                treatment_procedure_id=treatment_procedure.id
            )
            db.session.commit()
            prescription_params = ScheduledPharmacyPrescriptionParams(
                treatment_procedure_id=treatment_procedure.id,
                maven_benefit_id=benefit_id,
                status=PrescriptionStatus.SCHEDULED,
                amount_owed=cost,
                scheduled_ship_date=datetime.strptime(
                    row[SMP_SCHEDULED_SHIP_DATE], "%m/%d/%Y"
                ),
                scheduled_json=row,
            )
            created_prescription = self.create_pharmacy_prescription(
                row=row,
                user_id=user.id,
                prescription_params=dataclasses.asdict(prescription_params),
            )
            log.info(
                f"{self.job_name}: Treatment Procedure and Pharmacy Prescription created.",
                treatment_procedure_id=treatment_procedure.id,
                pharmacy_prescription_id=created_prescription.id,
            )
        except Exception as e:
            log.exception(
                f"{self.job_name}: Exception saving data objects.",
                maven_member_id=benefit_id,
                error=e,
            )
            self.failed_rows.append(
                (
                    benefit_id,
                    row[SMP_UNIQUE_IDENTIFIER],
                    "Could not save object.",
                )
            )
            return
        try:
            trigger_cost_breakdown(
                treatment_procedure=treatment_procedure,
                new_procedure=True,
                use_async=False if IS_INTEGRATIONS_K8S_CLUSTER else True,
            )
            self.processed_row_count += 1
        except Exception as e:
            log.exception(
                f"{self.job_name}: Exception running cost breakdown on scheduled rx procedure. Cost breakdown failed.",
                treatment_procedure_id=treatment_procedure.id,
                exc_info=True,
                error=str(e),
            )
            self.failed_rows.append(
                (
                    benefit_id,
                    row[SMP_UNIQUE_IDENTIFIER],
                    f"Cost Breakdown for scheduled RX procedure failed with error: {e}",
                )
            )
