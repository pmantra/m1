import enum
import re
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from fixedwidth.fixedwidth import FixedWidth
from maven import feature_flags

from cost_breakdown.models.cost_breakdown import CostBreakdown
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureType,
)
from payer_accumulator import helper_functions
from payer_accumulator.common import DetailWrapper, PayerName
from payer_accumulator.errors import SkipAccumulationDueToMissingInfo
from payer_accumulator.file_generators.fixed_width_accumulation_file_generator import (
    DetailMetadata,
    FixedWidthAccumulationFileGenerator,
)
from utils.log import logger
from wallet.models.constants import (
    MemberHealthPlanPatientRelationship,
    MemberHealthPlanPatientSex,
)
from wallet.models.reimbursement_wallet import MemberHealthPlan
from wallet.repository.health_plan import HEALTH_PLAN_YOY_FLAG, OLD_BEHAVIOR

log = logger(__name__)

PATIENT_RELATION_TO_CODE = {
    MemberHealthPlanPatientRelationship.CARDHOLDER: "1",
    MemberHealthPlanPatientRelationship.SPOUSE: "2",
    MemberHealthPlanPatientRelationship.CHILD: "3",
}

PATIENT_SEX_TO_CODE = {
    MemberHealthPlanPatientSex.MALE: "1",
    MemberHealthPlanPatientSex.FEMALE: "2",
    MemberHealthPlanPatientSex.UNKNOWN: "3",
}

IN_NETWORK_COVERAGE_TYPE = "1"

ACKNOWLEDGEMENT_CODE_TO_REASON_MAP = {
    "20": "PENDING",
    "30": "Eligibility issues",
    "31": "Duplicate record received",
    "32": "No paid claim for reversal exists",
    "40": "Invalid Record Type",
    "41": "Invalid Transaction Type",
    "42": "Invalid Sender ID",
    "43": "Invalid Receiver ID",
    "44": "Invalid Benefit Type",
    "45": "Invalid Member SSN",
    "46": "Invalid Member Relationship Code",
    "47": "Invalid Patient Name",
    "48": "Invalid Patient Date of Birth",
    "49": "Invalid Patient Gender",
    "50": "Invalid Claim Number",
    "51": "Invalid Service from Date",
    "52": "Invalid Accum Type",
    "53": "Invalid Coverage Type",
    "54": "Invalid Accumulator Amount",
    "55": "Invalid Service to Date",
    "99": "Other error encountered",
}

APPROVAL_CODES = (
    "10",  # Accepted
    "20",  # Pending
)


class AccumulatorTypeValues(enum.Enum):
    DEDUCTIBLE = "1"
    COINSURANCE = "2"
    COPAY = "3"
    OUT_OF_POCKET = "4"


class AccumulationFileGeneratorCredence(FixedWidthAccumulationFileGenerator):
    """
    This class is responsible for generating the base payer accumulation file for SFTP and consumption by Credence.
    It is not responsible for anything other than assembling the file contents (like encryption)
    """

    def __init__(self) -> None:
        super().__init__(payer_name=PayerName.CREDENCE)

    def _get_header_required_fields(self) -> Dict:
        file_date = self.get_run_date()
        file_time = self.get_run_time()
        return {
            "file_date": file_date,
            "file_time": file_time,
            "unique_file_id": f"MAVEN_ACCUM_{file_date}_{file_time}",
        }

    def _get_trailer_required_fields(
        self, record_count: int, oop_total: int = 0
    ) -> Dict:
        return {
            "record_count": str(2 + record_count),
            "file_date": self.get_run_date(),
            "file_time": self.get_run_time(),
            "transaction_count": str(record_count),
        }

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
        is_reversal: bool = False,
        is_regeneration: bool = False,
        sequence_number: int = 0,
    ) -> DetailWrapper:
        detail_obj = FixedWidth(self.detail_config)
        unique_record_id = self.get_unique_record_id(record_id, cost_breakdown.id)

        detail_obj.update(
            unique_record_identifier=unique_record_id,
            subscriber_last_name=member_health_plan.subscriber_last_name,
            relationship_code=self.get_patient_relationship_code(member_health_plan),
            patient_first_name=helper_functions.get_patient_first_name(
                member_health_plan
            ),
            patient_last_name=helper_functions.get_patient_last_name(
                member_health_plan
            ),
            patient_date_of_birth=member_health_plan.patient_date_of_birth.strftime("%Y%m%d"),  # type: ignore[union-attr] # Item "None" of "Optional[date]" has no attribute "strftime"
            patient_gender=self.get_patient_gender(member_health_plan),
            claim_number=str(record_id),
            claim_start_date=service_start_date.strftime("%Y%m%d"),
            claim_end_date=service_start_date.strftime("%Y%m%d"),
            contract_number=self.get_cardholder_id(member_health_plan),
        )
        # insert non-zero accumulation amounts into detail dict
        accumulations = self._get_accumulation_balances(
            deductible, oop_applied, cost_breakdown, is_reversal
        )
        for i, accumulation in enumerate(accumulations, start=1):
            type_of_accumulation_key = f"type_of_accumulator_{i}"
            type_of_coverage_key = f"type_of_coverage_{i}"
            accumulator_amount_key = f"accumulator_amount_{i}"
            accumulation_args = {
                type_of_accumulation_key: accumulation[0],
                type_of_coverage_key: accumulation[1],
                accumulator_amount_key: accumulation[2],
            }
            detail_obj.update(**accumulation_args)
        return DetailWrapper(unique_id=unique_record_id, line=detail_obj.line)

    @property
    def file_name(self) -> str:
        return f"MAVEN_ACCUM_{self.get_run_date()}_{self.get_run_time()}.txt"

    def get_unique_record_id(
        self, source_id: int, cost_breakdown_id: Optional[int]
    ) -> str:
        if cost_breakdown_id:
            source_id_str = f"cb_{cost_breakdown_id}"
        else:
            source_id_str = f"rr_{source_id}"
        timestamp = self.get_run_datetime()
        return f"{timestamp}#{source_id_str}"

    @staticmethod
    def get_patient_gender(member_health_plan) -> str:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        patient_sex = member_health_plan.patient_sex
        return PATIENT_SEX_TO_CODE[patient_sex]

    @staticmethod
    def get_patient_relationship_code(member_health_plan) -> str:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        patient_relationship = member_health_plan.patient_relationship
        relationship_code = PATIENT_RELATION_TO_CODE.get(patient_relationship)
        if not relationship_code:
            raise SkipAccumulationDueToMissingInfo(
                f"Invalid patient relationship for member health plan {member_health_plan.id}"
            )
        return relationship_code

    @staticmethod
    def get_cardholder_id(member_health_plan: MemberHealthPlan) -> str:
        return member_health_plan.subscriber_insurance_id.upper()

    @staticmethod
    def _get_coinsurance_amount(
        cost_breakdown: CostBreakdown, is_reversal: bool
    ) -> Optional[Tuple]:
        if cost_breakdown.coinsurance:
            accumulator_type = AccumulatorTypeValues.COINSURANCE.value
            amount = cost_breakdown.coinsurance
        else:
            accumulator_type = AccumulatorTypeValues.COPAY.value
            amount = cost_breakdown.copay
        return accumulator_type, -amount if is_reversal else amount

    def _get_accumulation_balances(
        self,
        deductible: int,
        oop_applied: int,
        cost_breakdown: CostBreakdown,
        is_reversal: bool,
    ) -> List[Tuple]:
        """
        Returns a list of accumulations if they are non-zero.
        """
        accumulations = []
        coinsurance_or_copay = self._get_coinsurance_amount(cost_breakdown, is_reversal)
        if deductible:
            accumulations.append(
                (
                    AccumulatorTypeValues.DEDUCTIBLE.value,
                    IN_NETWORK_COVERAGE_TYPE,
                    self.add_signed_overpunch(deductible),
                )
            )
        if oop_applied:
            accumulations.append(
                (
                    AccumulatorTypeValues.OUT_OF_POCKET.value,
                    IN_NETWORK_COVERAGE_TYPE,
                    self.add_signed_overpunch(oop_applied),
                )
            )
        # If there is a coinsurance or copay amount then add the accumulation
        if coinsurance_or_copay:
            accumulations.append(
                (
                    coinsurance_or_copay[0],
                    IN_NETWORK_COVERAGE_TYPE,
                    self.add_signed_overpunch(coinsurance_or_copay[1]),
                )
            )
        return accumulations

    # ----- Response Processing Methods -----

    # Format is: Maven_Luminare_Accumulator_File_DR_CCYYMMDD_HHMMSS
    RESPONSE_FILENAME_PATTERN = re.compile(r"MAVEN_MED_ACK_(\d{8})_(\d{6})$")

    def match_response_filename(self, file_name: str) -> bool:
        return self.RESPONSE_FILENAME_PATTERN.match(file_name) is not None

    def get_response_file_date(self, file_name: str) -> Optional[str]:
        match = self.RESPONSE_FILENAME_PATTERN.match(file_name)
        if match:
            return match.group(1)
        return None

    def get_detail_metadata(self, detail_record: dict) -> DetailMetadata:
        is_response = False
        is_rejection = False
        should_update = False
        unique_id = detail_record["unique_record_identifier"]
        acknowledgement_code = detail_record["acknowledgement_code"]
        reject_reason = ""
        member_id = ""

        if detail_record["transaction_type"] == "01":
            is_response = True
            if acknowledgement_code not in APPROVAL_CODES:
                is_rejection = True
                should_update = True
                reject_reason = ACKNOWLEDGEMENT_CODE_TO_REASON_MAP.get(
                    acknowledgement_code, acknowledgement_code
                )

        # get member_id
        service_date = datetime.strptime(detail_record["claim_start_date"], "%Y%m%d")
        if (
            feature_flags.str_variation(HEALTH_PLAN_YOY_FLAG, default=OLD_BEHAVIOR)
            != OLD_BEHAVIOR
        ):
            member_health_plan = self.health_plan_repo.get_member_plan_by_demographics(
                subscriber_last_name=detail_record["subscriber_last_name"],
                subscriber_id=detail_record["contract_number"],
                patient_first_name=detail_record["patient_first_name"],
                patient_last_name=detail_record["patient_last_name"],
                effective_date=service_date,
            )
        else:
            member_health_plan = MemberHealthPlan.query.filter(
                MemberHealthPlan.subscriber_insurance_id
                == detail_record["contract_number"],
                MemberHealthPlan.patient_first_name
                == detail_record["patient_first_name"],
                MemberHealthPlan.patient_last_name
                == detail_record["patient_last_name"],
                MemberHealthPlan.subscriber_last_name
                == detail_record["subscriber_last_name"],
                MemberHealthPlan.plan_start_at <= service_date,
                MemberHealthPlan.plan_end_at >= service_date,
            ).first()
        if member_health_plan:
            member_id = str(member_health_plan.member_id)

        return DetailMetadata(
            is_response=is_response,
            is_rejection=is_rejection,
            should_update=should_update,
            unique_id=unique_id,
            member_id=member_id,
            response_status="",  # Credence doesn't return a seperate status field
            response_code=acknowledgement_code,
            response_reason=reject_reason,
        )

    def get_response_reason_for_code(self, response_code: str) -> Optional[str]:
        return ACKNOWLEDGEMENT_CODE_TO_REASON_MAP.get(response_code)

    # ----- Reconciliation Methods -----
    @staticmethod
    def get_cardholder_id_from_detail_dict(detail_row_dict: dict) -> Optional[str]:
        return detail_row_dict.get("contract_number")

    def get_dob_from_report_row(self, detail_row_dict: dict) -> date:
        date_str = detail_row_dict["patient_date_of_birth"]
        return datetime.strptime(date_str, "%Y%m%d").date()

    @staticmethod
    def get_detail_rows(report_rows: list) -> list:
        detail_rows = []
        for row in report_rows:
            if row["record_type"] == "01":
                detail_rows.append(row)
        return detail_rows

    def get_deductible_from_row(self, detail_row: dict) -> int:
        return helper_functions.get_cents_from_overpunch(
            detail_row["accumulator_amount_1"]
        )

    def get_oop_from_row(self, detail_row: dict) -> int:
        return helper_functions.get_cents_from_overpunch(
            detail_row["accumulator_amount_2"]
        )
