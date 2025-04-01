from datetime import datetime
from decimal import Decimal

from common.constants import Environment
from cost_breakdown.models.cost_breakdown import CostBreakdown
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureType,
)
from payer_accumulator.common import DetailWrapper, PayerName
from payer_accumulator.csv.csv_accumulation_file_generator import (
    CSV_DELIMITER,
    CSVAccumulationFileGenerator,
)
from payer_accumulator.errors import UnsupportedRelationshipCodeError
from utils.log import logger
from wallet.models.constants import MemberHealthPlanPatientRelationship
from wallet.models.reimbursement_wallet import MemberHealthPlan

log = logger(__name__)

POLICY_GROUP_ID = "78800722"


class AccumulationFileGeneratorSurest(CSVAccumulationFileGenerator):
    def __init__(self) -> None:
        super().__init__(payer_name=PayerName.SUREST)

    @property
    def file_name(self) -> str:
        return f"maven_surest_infertilityclaimspaid_{Environment.current().name.lower()}_{self.get_run_datetime(16)}.csv"

    def _generate_header(self) -> str:
        return CSV_DELIMITER.join(
            [
                "Policy/Group",
                "Member ID",
                "First Name",
                "Last Name",
                "Date of Birth",
                "Relationship Code",
                "Maven Claim Number",
                "Date of Service",
                "Network",
                "OOP Applied",
                "Claim Status",
                "Accumulator Type",
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
        timestamp = self.get_run_datetime(length=16)
        unique_id = f"{timestamp}{self.record_count:06}"
        return DetailWrapper(
            unique_id=unique_id,
            line=CSV_DELIMITER.join(
                [
                    POLICY_GROUP_ID,
                    member_health_plan.subscriber_insurance_id.replace("-", ""),
                    member_health_plan.patient_first_name,  # type: ignore[list-item] # List item 2 has incompatible type "str | None"; expected "str"
                    member_health_plan.patient_last_name,  # type: ignore[list-item] # List item 3 has incompatible type "str | None"; expected "str"
                    member_health_plan.patient_date_of_birth.strftime("%Y%m%d"),  # type: ignore[union-attr] # Item "None" of "date | None" has no attribute "strftime"
                    self._get_relationship_code(member_health_plan.patient_relationship),  # type: ignore[arg-type] # Argument 1 to "_get_relationship_code" of "AccumulationFileGeneratorSurest" has incompatible type "str | None"; expected "MemberHealthPlanPatientRelationship"
                    unique_id,
                    service_start_date.strftime("%Y%m%d"),
                    "IN",
                    f"{float(Decimal(oop_applied) / Decimal(100)):.2f}",  # type: ignore[arg-type] # Argument 1 to "Decimal" has incompatible type "int | None"; expected "Decimal | float | str | tuple[int, Sequence[int], int]"
                    "00" if not is_reversal else "11",
                    "INFERTILITY",
                ]
            ),
        )

    @staticmethod
    def _get_relationship_code(code: MemberHealthPlanPatientRelationship) -> str:
        if code == MemberHealthPlanPatientRelationship.CARDHOLDER:
            return "18"
        elif code == MemberHealthPlanPatientRelationship.SPOUSE:
            return "01"
        elif code == MemberHealthPlanPatientRelationship.CHILD:
            return "19"
        elif code == MemberHealthPlanPatientRelationship.DOMESTIC_PARTNER:
            return "53"
        log.error("Relationship code is not supported by Surest", code=code)
        raise UnsupportedRelationshipCodeError(
            "Relationship code is not supported by Surest"
        )
