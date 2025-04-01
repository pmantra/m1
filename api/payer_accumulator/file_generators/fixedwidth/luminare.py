import json
import re
from datetime import date, datetime
from typing import Dict, Optional

from fixedwidth.fixedwidth import FixedWidth
from maven import feature_flags

from cost_breakdown.models.cost_breakdown import CostBreakdown
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureType,
)
from payer_accumulator import helper_functions
from payer_accumulator.common import DetailWrapper, PayerName
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
    MemberHealthPlanPatientRelationship.DOMESTIC_PARTNER: "2",
    MemberHealthPlanPatientRelationship.FORMER_SPOUSE: "2",
    MemberHealthPlanPatientRelationship.CHILD: "3",
    MemberHealthPlanPatientRelationship.OTHER: "4",
}

PATIENT_SEX_TO_CODE = {
    MemberHealthPlanPatientSex.UNKNOWN: "U",
    MemberHealthPlanPatientSex.MALE: "M",
    MemberHealthPlanPatientSex.FEMALE: "F",
}


REJECT_CODE_TO_REASON_MAP = {
    # Header Codes
    "101": "RECORD TYPE IS NOT VALID",
    "102": "UNIQUE RECORD IDENTIFIER IS BLANK",
    "105": "TRANSMISSION TYPE IS NOT VALID",
    "111": "DATA FILE RECEIVER ID DOES NOT EXIST",
    "112": "DATA FILE RECEIVER NAME HAS AN INVALID FORMAT",
    "206": "DUPLICATE FILE - FILE WAS NOT PROCESSED",
    # Detail Codes"
    # "102":  "UNIQUE RECORD IDENTIFIER IS BLANK",
    "104": "CLAIM SOURCE IS NOT VALID",
    # "105":  "TRANSMISSION TYPE IS NOT VALID",
    "106": "RECORD RESPONSE STATUS CODE CANNOT BE BLANK",
    "107": "PRODUCTION OR TEST DATA IS NOT VALID",
    "118": "PATIENT'S GENDER IS NOT VALID",
    "119": "PATIENT'S RELATIONSHIP CODE IS NOT VALID",
    "125": "CLAIM TRANSACTION TYPE IS NOT VALID",
    "126": "CLAIM DATE OF SERVICE HAS AN INVALID FORMAT",
    "129": "DOLLARS OR FLAG INDICATOR IS NOT VALID",
    "152": "CLAIM SOURCE IS BLANK",
    "153": "TRANSMISSION TYPE IS BLANK",
    "159": "DATA FILE SENDER NAME IS BLANK",
    "161": "DATA FILE RECEIVER NAME IS BLANK",
    "163": "PATIENT ID IS BLANK",
    "164": "PATIENT'S DATE OF BIRTH IS BLANK",
    "165": "PATIENT'S FIRST NAME IS BLANK",
    "166": "PATIENT'S LAST NAME IS BLANK",
    "167": "PATIENT'S GENDER IS BLANK",
    "169": "CLAIM ID IS BLANK",
    "170": "CLAIM TRANSACTION TYPE IS BLANK",
    "172": "CLAIM POST DATE IS BLANK",
    "174": "DOLLAR OR FLAG INDICATOR IS BLANK",
    "303": "DUPLICATE PAID/CAPTURED CLAIM",
    "304": "UN-MATCHED MEMBER",
}


class AccumulationFileGeneratorLuminare(FixedWidthAccumulationFileGenerator):
    """
    This class is responsible for generating the base payer accumulation file for SFTP and consumption by Luminaire.
    It is not responsible for anything other than assembling the file contents (like encryption)
    """

    def __init__(self) -> None:
        super().__init__(payer_name=PayerName.LUMINARE)

    def _get_header_required_fields(self) -> Dict:
        return {
            "unique_batch_file_identifier": self.get_batch_number(),
            "file_creation_date": self.get_run_date(),
            "file_creation_time": self.get_run_time(length=10),
            "processing_period_start_date": self.run_time.strftime("%Y0101"),
            "processing_period_end_date": self.get_run_date(),
        }

    def _get_trailer_required_fields(
        self, record_count: int, oop_total: int = 0
    ) -> Dict:
        return {
            "total_oop_amount_sign": AccumulationFileGeneratorLuminare.get_amount_sign(
                oop_total
            ),
            "total_oop_amount": str(oop_total),
            "control_record_count": str(record_count),
        }

    def _update_trailer_with_record_counts(
        self, trailer_data: Dict, record_count: int, oop_total: int = 0
    ) -> Dict:
        trailer_data.update(
            total_oop_amount_sign=AccumulationFileGeneratorLuminare.get_amount_sign(
                oop_total
            ),
            total_oop_amount=str(oop_total),
            control_record_count=str(record_count),
        )
        return trailer_data

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
        unique_record_id = self.get_unique_record_id(record_id)
        detail_obj.update(
            unique_record_identifier=unique_record_id,
            patient_id=self.get_cardholder_id(member_health_plan),
            patient_date_of_birth=member_health_plan.patient_date_of_birth.strftime("%Y%m%d"),  # type: ignore[union-attr] # Item "None" of "Optional[date]" has no attribute "strftime"
            patient_first_name=helper_functions.get_patient_first_name(
                member_health_plan
            ),
            patient_last_name=helper_functions.get_patient_last_name(
                member_health_plan
            ),
            patient_gender=self.get_patient_gender(member_health_plan),
            patient_relationship_code=self.get_patient_relationship_code(
                member_health_plan
            ),
            carrier_number=member_health_plan.employer_health_plan.carrier_number,
            group_number=member_health_plan.employer_health_plan.carrier_number,
            claim_id=str(record_id),
            claim_sequence_number=str(sequence_number % 1000).zfill(3),
            claim_transaction_type="R" if is_reversal else "P",
            claim_date_of_service=service_start_date.strftime("%Y%m%d"),
            claim_post_date=service_start_date.strftime("%Y%m%d"),
            claim_post_time=service_start_date.strftime("%H%M%S%f")[:-2],
            deductible_amount_sign=self.get_amount_sign(deductible),
            deductible_amount=str(abs(deductible)),
            out_of_pocket_amount_sign=self.get_amount_sign(oop_applied),
            out_of_pocket_amount=str(abs(oop_applied)),
        )
        calc_config = cost_breakdown.calc_config
        if isinstance(calc_config, str):
            try:
                calc_config = json.loads(cost_breakdown.calc_config)
            except (TypeError, json.JSONDecodeError) as e:
                log.error(
                    f"Malformed calc_config in cost breakdown ({cost_breakdown.id}) for luminare accumulation on record: {record_id}",
                    error=e,
                )
                raise Exception(
                    f"Malformed calc_config in cost breakdown ({cost_breakdown.id}) for luminare accumulation on record: {record_id}"
                )
        if not calc_config or not calc_config.get("tier"):
            raise Exception(
                f"Missing Tier information in cost breakdown ({cost_breakdown.id}) for luminare accumulation on record: {record_id}"
            )
        tier = calc_config["tier"]
        detail_obj.update(network=str(tier))
        return DetailWrapper(unique_id=unique_record_id, line=detail_obj.line)

    @property
    def file_name(self) -> str:
        dt = self.get_run_datetime()
        return f"Maven_Luminare_Accumulator_File_{dt}"

    def get_unique_record_id(self, source_id: int) -> str:
        tp_id_str = str(source_id)
        timestamp = self.get_run_datetime()
        return tp_id_str + timestamp

    @staticmethod
    def get_patient_gender(member_health_plan) -> str:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        patient_sex = member_health_plan.patient_sex
        return PATIENT_SEX_TO_CODE[patient_sex]

    @staticmethod
    def get_patient_relationship_code(member_health_plan) -> str:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        patient_relationship = member_health_plan.patient_relationship
        return PATIENT_RELATION_TO_CODE[patient_relationship]

    @staticmethod
    def get_amount_sign(number: int) -> str:
        if number >= 0:
            return "+"
        else:
            return "-"

    @staticmethod
    def get_cardholder_id(member_health_plan: MemberHealthPlan) -> str:
        return member_health_plan.subscriber_insurance_id.upper()

    # ----- Response Processing Methods -----

    # Format is: Maven_Luminare_Accumulator_File_DR_CCYYMMDD_HHMMSS
    RESPONSE_FILENAME_PATTERN = re.compile(
        r"Maven_Luminare_Accumulator_File_DR_(\d{8})_(\d{6})"
    )

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
        response_status = detail_record["record_response_status_code"]
        reject_reason = ""
        reject_code = detail_record["claim_reject_code"]
        member_id = ""

        if detail_record["transmission_type"] == "DR":
            is_response = True
            if response_status == "F":
                is_rejection = True
                should_update = True
                reject_reason = REJECT_CODE_TO_REASON_MAP.get(reject_code, reject_code)
        # get member_id
        service_date = datetime.strptime(
            detail_record["claim_date_of_service"], "%Y%m%d"
        )
        if (
            feature_flags.str_variation(HEALTH_PLAN_YOY_FLAG, default=OLD_BEHAVIOR)
            != OLD_BEHAVIOR
        ):
            member_health_plan = self.health_plan_repo.get_member_plan_by_demographics(
                subscriber_id=detail_record["patient_id"],
                patient_first_name=detail_record["patient_first_name"],
                patient_last_name=detail_record["patient_last_name"],
                effective_date=service_date,
            )
        else:
            member_health_plan = MemberHealthPlan.query.filter(
                MemberHealthPlan.subscriber_insurance_id == detail_record["patient_id"],
                MemberHealthPlan.patient_first_name
                == detail_record["patient_first_name"],
                MemberHealthPlan.patient_last_name
                == detail_record["patient_last_name"],
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
            response_status=response_status,
            response_code=reject_code,
            response_reason=reject_reason,
        )

    def get_response_reason_for_code(self, response_code: str) -> Optional[str]:
        return REJECT_CODE_TO_REASON_MAP.get(response_code)

    # ----- Reconciliation Methods -----
    @staticmethod
    def get_cardholder_id_from_detail_dict(detail_row_dict: dict) -> Optional[str]:
        return detail_row_dict.get("patient_id")

    def get_dob_from_report_row(self, detail_row_dict: dict) -> date:
        date_str = detail_row_dict["patient_date_of_birth"]
        return datetime.strptime(date_str, "%Y%m%d").date()

    @staticmethod
    def get_detail_rows(report_rows: list) -> list:
        detail_rows = []
        for row in report_rows:
            if row["record_type"] == "DTL":
                detail_rows.append(row)
        return detail_rows

    def get_deductible_from_row(self, detail_row: dict) -> int:
        sign = detail_row["deductible_amount_sign"]
        amount = int(detail_row["deductible_amount"])
        if sign == "+":
            return amount
        else:
            return amount * -1

    def get_oop_from_row(self, detail_row: dict) -> int:
        sign = detail_row["out_of_pocket_amount_sign"]
        amount = int(detail_row["out_of_pocket_amount"])
        if sign == "+":
            return amount
        else:
            return amount * -1
