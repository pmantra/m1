from __future__ import annotations

from datetime import datetime
from typing import Optional

import pytz

from direct_payment.pharmacy.constants import (
    CANCELLED_FILE_TYPE,
    SMP_CANCELED_FILE_PREFIX,
    SMP_MAVEN_ID,
    SMP_RX_CANCELED_DATE,
    SMP_UNIQUE_IDENTIFIER,
)
from direct_payment.pharmacy.models.pharmacy_prescription import PrescriptionStatus
from direct_payment.pharmacy.tasks.libs.common import IS_INTEGRATIONS_K8S_CLUSTER
from direct_payment.pharmacy.tasks.libs.rx_file_processor import FileProcessor
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureStatus,
)
from direct_payment.treatment_procedure.utils.procedure_helpers import (
    trigger_cost_breakdown,
)
from storage.connection import db
from utils.log import logger

log = logger(__name__)

JOB_NAME = "smp_process_cancelled_file"

CANCELLED_FILE_EXPECTED_FIELDS = [
    SMP_MAVEN_ID,
    SMP_UNIQUE_IDENTIFIER,
]


class CancelledFileProcessor(FileProcessor):
    def __init__(self, dry_run: bool = False):
        super().__init__(dry_run)
        self.file_type: Optional[str] = CANCELLED_FILE_TYPE
        self.job_name: Optional[str] = JOB_NAME
        self.expected_fields: Optional[list] = CANCELLED_FILE_EXPECTED_FIELDS

    def get_file_prefix(self) -> str:
        return SMP_CANCELED_FILE_PREFIX

    def get_benefit_id(self, row: dict) -> Optional[str]:
        return row[SMP_MAVEN_ID]

    def handle_row(self, row: dict) -> None:
        """Ingests SMP cancelled file to update a RX treatment procedure"""

        benefit_id = row[SMP_MAVEN_ID]
        existing_prescription = self.get_valid_pharmacy_prescription_from_file(
            row=row,
        )
        if existing_prescription is None:
            return

        if existing_prescription.status == PrescriptionStatus.CANCELLED:
            log.error(
                f"{self.job_name}: Existing prescription found in cancelled status.",
                benefit_id=benefit_id,
                smp_unique_id=row[SMP_UNIQUE_IDENTIFIER],
                status=existing_prescription.status,
            )
            return

        treatment_procedure = self.get_treatment_procedure(
            row=row,
            prescription=existing_prescription,
        )
        if treatment_procedure is None:
            return

        now = datetime.now(pytz.timezone("America/New_York"))
        treatment_procedure.cancelled_date = now
        treatment_procedure.status = TreatmentProcedureStatus.CANCELLED  # type: ignore[assignment] # Incompatible types in assignment (expression has type "TreatmentProcedureStatus", variable has type "str")

        existing_prescription.cancelled_json = row
        existing_prescription.status = PrescriptionStatus.CANCELLED
        existing_prescription.cancelled_date = datetime.strptime(
            row[SMP_RX_CANCELED_DATE], "%m/%d/%Y"
        )
        try:
            db.session.add(treatment_procedure)
            db.session.commit()
            self.pharmacy_prescription_service.update_pharmacy_prescription(
                instance=existing_prescription
            )
            log.info(
                f"{self.job_name}: Treatment Procedure cancelled.",
                treatment_procedure_id=treatment_procedure.id,
            )
        except Exception as e:
            log.exception(
                f"{self.job_name}: Exception persisting records to the database.",
                maven_member_id=benefit_id,
                error=e,
            )
            self.failed_rows.append(
                (
                    benefit_id,
                    row[SMP_UNIQUE_IDENTIFIER],
                    "Failed to save records.",
                )
            )
            return
        try:
            trigger_cost_breakdown(
                treatment_procedure=treatment_procedure,
                new_procedure=False,
                use_async=False if IS_INTEGRATIONS_K8S_CLUSTER else True,
            )
            self.processed_row_count += 1
        except Exception as e:
            log.exception(
                f"{self.job_name}: Exception running cost breakdown on cancelled rx procedure. Cost breakdown failed.",
                treatment_procedure_id=treatment_procedure.id,
                error=e,
            )
            self.failed_rows.append(
                (
                    benefit_id,
                    row[SMP_UNIQUE_IDENTIFIER],
                    "Cost breakdown for cancelling RX procedure failed.",
                )
            )
