from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from common.global_procedures.procedure import GlobalProcedure
from direct_payment.pharmacy.constants import (
    SHIPPED_FILE_TYPE,
    SMP_ACTUAL_SHIP_DATE,
    SMP_AMOUNT_OWED,
    SMP_DRUG_DESCRIPTION,
    SMP_DRUG_NAME,
    SMP_MAVEN_ID,
    SMP_NDC_NUMBER,
    SMP_RX_ADJUSTED,
    SMP_RX_RECEIVED_DATE,
    SMP_SCHEDULED_SHIP_DATE,
    SMP_SHIPPED_FILE_PREFIX,
    SMP_UNIQUE_IDENTIFIER,
)
from direct_payment.pharmacy.models.pharmacy_prescription import (
    PharmacyPrescription,
    PrescriptionStatus,
)
from direct_payment.pharmacy.tasks.libs.common import (
    IS_INTEGRATIONS_K8S_CLUSTER,
    get_or_create_rx_global_procedure,
)
from direct_payment.pharmacy.tasks.libs.rx_file_processor import FileProcessor
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
    TreatmentProcedureStatus,
)
from direct_payment.treatment_procedure.utils.procedure_helpers import (
    trigger_cost_breakdown,
)
from storage.connection import db
from utils.log import logger
from utils.payments import convert_dollars_to_cents

log = logger(__name__)

JOB_NAME = "smp_process_shipped_file"

SHIPPED_FILE_EXPECTED_FIELDS = [
    SMP_MAVEN_ID,
    SMP_AMOUNT_OWED,
    SMP_UNIQUE_IDENTIFIER,
    SMP_ACTUAL_SHIP_DATE,
    SMP_RX_ADJUSTED,
    SMP_NDC_NUMBER,
    SMP_DRUG_NAME,
    SMP_DRUG_DESCRIPTION,
    SMP_SCHEDULED_SHIP_DATE,
    SMP_RX_RECEIVED_DATE,
]


def _update_existing_prescription(
    row: dict, existing_prescription: PharmacyPrescription
) -> PharmacyPrescription:
    """Updates and existing prescription if the information within the shipped file changes."""
    existing_prescription.status = PrescriptionStatus.SHIPPED
    existing_prescription.actual_ship_date = datetime.strptime(
        row[SMP_ACTUAL_SHIP_DATE], "%m/%d/%Y"
    )
    existing_prescription.scheduled_ship_date = datetime.strptime(
        row[SMP_SCHEDULED_SHIP_DATE], "%m/%d/%Y"
    )
    existing_prescription.ndc_number = row[SMP_NDC_NUMBER]
    existing_prescription.rx_name = row[SMP_DRUG_NAME]
    existing_prescription.rx_description = row[SMP_DRUG_DESCRIPTION]
    existing_prescription.shipped_json = row
    return existing_prescription


def _complete_treatment_procedure(
    row: dict,
    treatment_procedure: TreatmentProcedure,
    global_procedure: GlobalProcedure | None,
    timestamp: datetime,
) -> TreatmentProcedure:
    """Updates Treatment Procedure"""
    rx_received_date = datetime.strptime(row[SMP_RX_RECEIVED_DATE], "%m/%d/%Y").date()

    treatment_procedure.status = TreatmentProcedureStatus.COMPLETED  # type: ignore[assignment]
    treatment_procedure.start_date = rx_received_date
    treatment_procedure.end_date = rx_received_date
    treatment_procedure.completed_date = timestamp
    if global_procedure:
        treatment_procedure.global_procedure_id = global_procedure["id"]
        treatment_procedure.procedure_name = global_procedure["name"]
    return treatment_procedure


class ShippedFileProcessor(FileProcessor):
    def __init__(self, dry_run: bool = False):
        super().__init__(dry_run)
        self.file_type: Optional[str] = SHIPPED_FILE_TYPE
        self.job_name: Optional[str] = JOB_NAME
        self.expected_fields: Optional[list] = SHIPPED_FILE_EXPECTED_FIELDS
        self.last_timestamp: Optional[datetime] = None

    def get_file_prefix(self) -> str:
        return SMP_SHIPPED_FILE_PREFIX

    def get_benefit_id(self, row: dict) -> Optional[str]:
        return row[SMP_MAVEN_ID]

    def get_next_timestamp(self) -> datetime:
        """Returns a timestamp that's guaranteed to be after the last one"""
        current = datetime.now(tz=timezone.utc)
        if self.last_timestamp and self.last_timestamp >= current:
            current = self.last_timestamp + timedelta(seconds=1)
        self.last_timestamp = current
        return current

    def handle_row(self, row: dict) -> None:
        existing_prescription = self.get_valid_pharmacy_prescription_from_file(row=row)
        if not existing_prescription:
            return

        if existing_prescription.status in [
            PrescriptionStatus.SHIPPED,
            PrescriptionStatus.CANCELLED,
        ]:
            log.error(
                f"{self.job_name}: Existing prescription found in processed status.",
                benefit_id=row[SMP_MAVEN_ID],
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

        updated_global_procedure = None
        if row[SMP_RX_ADJUSTED] == "Y":
            shipped_cost = convert_dollars_to_cents(float(row[SMP_AMOUNT_OWED]))
            if shipped_cost != treatment_procedure.cost:
                log.info(
                    f"{self.job_name}: SMP prescription cost adjusted.",
                    treatment_procedure_cost=treatment_procedure.cost,
                    shipped_cost=shipped_cost,
                )
                treatment_procedure.cost = shipped_cost
                existing_prescription.amount_owed = shipped_cost

            if row[SMP_NDC_NUMBER] != existing_prescription.ndc_number:
                log.info(
                    f"{self.job_name}: SMP Global Procedure changed. Updating Global Procedure."
                )
                effective_date = self.get_rx_received_date(row)

                updated_global_procedure = get_or_create_rx_global_procedure(
                    drug_name=row[SMP_DRUG_NAME],
                    ndc_number=row[SMP_NDC_NUMBER],
                    treatment_procedure=treatment_procedure,
                    start_date=effective_date,
                    end_date=effective_date,
                )
                if updated_global_procedure is None:
                    log.error(
                        f"{self.job_name}: Could not update with new Global Procedure.",
                        benefit_id=row[SMP_MAVEN_ID],
                        smp_unique_id=row[SMP_UNIQUE_IDENTIFIER],
                        prescription_id=existing_prescription.id,
                    )
                    self.failed_rows.append(
                        (
                            row[SMP_MAVEN_ID],
                            row[SMP_UNIQUE_IDENTIFIER],
                            "Failed to update record with new Global Procedure.",
                        )
                    )
                    return
        try:
            updated_prescription = _update_existing_prescription(
                row=row, existing_prescription=existing_prescription
            )
            updated_treatment_procedure = _complete_treatment_procedure(
                row=row,
                treatment_procedure=treatment_procedure,
                global_procedure=updated_global_procedure,
                timestamp=self.get_next_timestamp(),
            )
            db.session.add(updated_treatment_procedure)
            db.session.commit()
            self.pharmacy_prescription_service.update_pharmacy_prescription(
                instance=updated_prescription
            )
            log.info(
                f"{self.job_name}: Treatment Procedure completed.",
                treatment_procedure_id=updated_treatment_procedure.id,
            )
        except Exception as e:
            log.exception(
                f"{self.job_name}: Exception storing records to the database.",
                maven_member_id=row[SMP_MAVEN_ID],
                error=e,
            )
            self.failed_rows.append(
                (
                    row[SMP_MAVEN_ID],
                    row[SMP_UNIQUE_IDENTIFIER],
                    f"{self.job_name}: Failed to save records. {e}",
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
                f"{self.job_name}: Exception running cost breakdown on completed rx procedure. Cost breakdown failed.",
                treatment_procedure_id=treatment_procedure.id,
                exc_info=True,
                error=str(e),
            )
            self.failed_rows.append(
                (
                    row[SMP_MAVEN_ID],
                    row[SMP_UNIQUE_IDENTIFIER],
                    f"Cost breakdown for completed RX procedure failed with error: {e}",
                )
            )
