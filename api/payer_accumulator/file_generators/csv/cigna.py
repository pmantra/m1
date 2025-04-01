from datetime import datetime
from decimal import Decimal
from typing import Optional

from cost_breakdown.models.cost_breakdown import CostBreakdown
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureType,
)
from payer_accumulator.common import DetailWrapper, OrganizationName, PayerName
from payer_accumulator.csv.csv_accumulation_file_generator import (
    CSV_DELIMITER,
    CSVAccumulationFileGenerator,
)
from utils.log import logger
from wallet.models.reimbursement_wallet import MemberHealthPlan

log = logger(__name__)

FILENAME_PREFIX = "Maven_Accum"


class AccumulationCSVFileGeneratorCigna(CSVAccumulationFileGenerator):
    def __init__(self, organization_name: Optional[OrganizationName] = None) -> None:
        super().__init__(
            payer_name=PayerName.CIGNA_TRACK_1, organization_name=organization_name
        )

    @property
    def file_name(self) -> str:
        file_datetime = self.get_run_datetime()
        if self.organization_name:
            return (
                f"{FILENAME_PREFIX}_{self.organization_name.value}_{file_datetime}.csv"
            )
        else:
            return f"{FILENAME_PREFIX}_{file_datetime}.csv"

    def _generate_header(self) -> str:
        return CSV_DELIMITER.join(
            [
                "Member ID",
                "Last Name",
                "First Name",
                "Date of Birth",
                "Date of Service",
                "Deductible Applied",
                "Coinsurance Applied",
            ]
        )

    def _generate_detail(
        self,
        record_id: int,
        record_type: TreatmentProcedureType,
        cost_breakdown: CostBreakdown,
        service_start_date: datetime,
        deductible: int,
        oop_applied: int,
        hra_applied: int,
        member_health_plan: MemberHealthPlan,
        is_reversal: bool,
        is_regeneration: bool,
        sequence_number: int,
    ) -> DetailWrapper:
        deductible = deductible if is_regeneration else cost_breakdown.deductible
        coinsurance_applied = (
            cost_breakdown.coinsurance
            if cost_breakdown.coinsurance > 0
            else cost_breakdown.copay
        )
        if is_reversal:
            deductible = -deductible
            coinsurance_applied = -coinsurance_applied
        timestamp = self.get_run_datetime(length=16)
        unique_id = f"{timestamp}{self.record_count:06}"
        return DetailWrapper(
            unique_id=unique_id,
            line=CSV_DELIMITER.join(
                [
                    member_health_plan.subscriber_insurance_id,
                    member_health_plan.patient_last_name,  # type: ignore[list-item] # List item 3 has incompatible type "str | None"; expected "str"
                    member_health_plan.patient_first_name,  # type: ignore[list-item] # List item 2 has incompatible type "str | None"; expected "str"
                    member_health_plan.patient_date_of_birth.strftime("%Y%m%d"),  # type: ignore[union-attr] # Item "None" of "date | None" has no attribute "strftime"
                    service_start_date.strftime("%Y%m%d"),
                    f"{float(Decimal(deductible) / Decimal(100)):.2f}",  # type: ignore[arg-type] # Argument 1 to "Decimal" has incompatible type "int | None"; expected "Decimal | float | str | tuple[int, Sequence[int], int]"
                    f"{float(Decimal(coinsurance_applied) / Decimal(100)):.2f}",  # type: ignore[arg-type] # Argument 1 to "Decimal" has incompatible type "int | None"; expected "Decimal | float | str | tuple[int, Sequence[int], int]"
                ]
            ),
        )
