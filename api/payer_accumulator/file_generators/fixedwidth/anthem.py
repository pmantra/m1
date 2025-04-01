from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, Optional, Tuple

from fixedwidth.fixedwidth import FixedWidth

from common.constants import Environment
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

log = logger(__name__)

REJECT_CODE_TO_REASON_MAP = {
    "005": "Accumulation Overapply",
    "006": "Accumulations Amount Exceeded The Limit",
    "081": "Subscriber ID Spaces or Zeros in File",
    "082": "Deductible and OOP Amount Spaces or Zeros in File",
    "083": "DOB Spaces or Zeros in File",
    "084": "Service Date Spaces or Zeros in Files",
    "085": "Patient Not Found - DOB Mismatch",
    "086": "Subscriber ID Not Found",
    "091": "Health Care ID Spaces",
    "093": "Plan Code Not Found",
    "097": "Duplicate Record Found",
    "099": "Accumulation Load Failed",
}


class AccumulationFileGeneratorAnthem(FixedWidthAccumulationFileGenerator):
    def __init__(self) -> None:
        super().__init__(payer_name=PayerName.ANTHEM)

    def _get_header_required_fields(self) -> Dict:
        return {
            "processor_routing_identification": self._get_processor_routing_identification(),
            "file_type": self._get_environment(),
            "creation_date": self.get_run_date(),
            "creation_time": self.get_run_time(length=4),
        }

    def _get_trailer_required_fields(
        self, record_count: int, oop_total: int = 0
    ) -> Dict:
        return {
            "processor_routing_identification": self._get_processor_routing_identification(),
            "record_count": record_count,
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
        detail_obj: FixedWidth = FixedWidth(self.detail_config)

        # Note: transmission_id format: CCYYMMDDHHMMSSLL<...count>, max length 50.
        timestamp = self.get_run_datetime(length=16)
        detail_count = (
            self.record_count + 1
        )  # record_count is one behind (incremented after the row is added to the file)
        transmission_id = f"{timestamp}{detail_count:06}"
        transaction_id = f"cb_{cost_breakdown.id}"

        (
            accumulator_balance_qualifier_1,
            accumulator_applied_amount_1,
            action_code_1,
            accumulator_balance_qualifier_2,
            accumulator_applied_amount_2,
            action_code_2,
            accumulator_balance_count,
        ) = self._get_balance_details(deductible, oop_applied)

        cardholder_id = self.get_cardholder_id(member_health_plan)

        detail_obj.update(
            processor_routing_identification=self._get_processor_routing_identification(),
            transmission_date=self.get_run_date(),
            transmission_time=self.get_run_time(length=8),
            date_of_service=service_start_date.strftime("%Y%m%d"),
            transmission_id=transmission_id,
            transaction_id=transaction_id,
            cardholder_id=cardholder_id,
            patient_first_name=helper_functions.get_patient_first_name(
                member_health_plan
            ).upper(),
            patient_last_name=helper_functions.get_patient_last_name(
                member_health_plan
            ).upper(),
            cardholder_last_name=member_health_plan.subscriber_last_name.upper(),  # type: ignore[union-attr] # Item "None" of "Optional[str]" has no attribute "upper"
            client_pass_through="LOREAL",
            family_id=cardholder_id,
            patient_relationship_code=self._get_relationship_code(
                member_health_plan.patient_relationship  # type: ignore[arg-type] # Argument 1 to "_get_relationship_code" of "ESIAccumulationFileGenerator" has incompatible type "Optional[str]"; expected "MemberHealthPlanPatientRelationship"
            ),
            date_of_birth=member_health_plan.patient_date_of_birth.strftime("%Y%m%d"),  # type: ignore[union-attr] # Item "None" of "Optional[date]" has no attribute "strftime"
            patient_gender_code=self._get_gender_code(member_health_plan.patient_sex),  # type: ignore[arg-type] # Argument 1 to "_get_gender_code" of "ESIAccumulationFileGenerator" has incompatible type "Optional[str]"; expected "str"
            # Store our member_id in `sender_reference_number` for future troubleshooting purpose
            sender_reference_number=str(member_health_plan.member_id)
            if member_health_plan.member_id
            else "",
            accumulator_balance_qualifier_1=accumulator_balance_qualifier_1,
            accumulator_applied_amount_1=accumulator_applied_amount_1,
            action_code_1=action_code_1,
            accumulator_balance_qualifier_2=accumulator_balance_qualifier_2,
            accumulator_applied_amount_2=accumulator_applied_amount_2,
            action_code_2=action_code_2,
            accumulator_balance_count=accumulator_balance_count,
            accumulator_action_code="11" if is_reversal else "00",
        )
        return DetailWrapper(
            unique_id=transmission_id,
            line=detail_obj.line,
            transaction_id=transaction_id,
        )

    def _get_processor_routing_identification(self) -> str:
        return "MAVN" + self.run_time.strftime("%m%d%Y%H%M%S")

    def _get_balance_details(
        self, deductible: int, oop_applied: int
    ) -> Tuple[str, str, str, str, str, str, str]:
        if deductible == 0:
            balance_qualifier_1 = "05"
            applied_amount_1, action_code_1 = self._get_value_and_sign_from_amount(
                oop_applied
            )
            balance_qualifier_2 = ""
            applied_amount_2, action_code_2 = self._get_value_and_sign_from_amount(0)
        else:
            balance_qualifier_1 = "04"
            applied_amount_1, action_code_1 = self._get_value_and_sign_from_amount(
                deductible
            )
            balance_qualifier_2 = "05"
            applied_amount_2, action_code_2 = self._get_value_and_sign_from_amount(
                oop_applied
            )
        if not balance_qualifier_2:
            balance_count = "01"
        else:
            balance_count = "02"
        return (
            balance_qualifier_1,
            applied_amount_1,
            action_code_1,
            balance_qualifier_2,
            applied_amount_2,
            action_code_2,
            balance_count,
        )

    @staticmethod
    def _get_value_and_sign_from_amount(amount: int) -> Tuple[str, str]:
        dec_amount = Decimal(amount)
        if dec_amount < 0:
            return str(abs(dec_amount)), "-"
        else:
            return str(dec_amount), "+"

    @staticmethod
    def _get_gender_code(patient_sex: str) -> str:
        mapping = {
            MemberHealthPlanPatientSex.MALE.value: "1",
            MemberHealthPlanPatientSex.FEMALE.value: "2",
        }
        return mapping.get(patient_sex, "0")

    @staticmethod
    def _get_relationship_code(
        patient_relationship: MemberHealthPlanPatientRelationship,
    ) -> str:
        mapping = {
            MemberHealthPlanPatientRelationship.CARDHOLDER: "1",
            MemberHealthPlanPatientRelationship.SPOUSE: "2",
            MemberHealthPlanPatientRelationship.DOMESTIC_PARTNER: "8",
            MemberHealthPlanPatientRelationship.FORMER_SPOUSE: "7",
        }
        return mapping.get(patient_relationship, "3")  # default to child code

    @property
    def file_name(self) -> str:
        run_date, run_time = self.get_run_date(), self.get_run_time()
        env = "PROD" if Environment.current() == Environment.PRODUCTION else "TEST"
        return f"MVX_EH_MED_ACCUM_{env}_{run_date}_{run_time}.TXT"

    @staticmethod
    def get_cardholder_id(member_health_plan: MemberHealthPlan) -> str:
        return member_health_plan.subscriber_insurance_id.upper()

    # ----- Response Processing Methods -----

    # Format is: RESP_MVX_EH_MED_ACCUM_EEEE_YYYYMMDD_HHMMSS.TXT (EEEE=PROD|TEST)
    RESPONSE_FILENAME_PATTERN = re.compile(
        r"^RESP_MVX_EH_MED_ACCUM_(\w{4})_(\d{8})_(\d{6})\.TXT(\.PGP)?"
    )

    def match_response_filename(self, file_name: str) -> bool:
        return self.RESPONSE_FILENAME_PATTERN.match(file_name.upper()) is not None

    def get_response_file_date(self, file_name: str) -> Optional[str]:
        match = self.RESPONSE_FILENAME_PATTERN.match(file_name.upper())
        if match:
            return match.group(2)
        return None

    def get_detail_metadata(self, detail_record: dict) -> DetailMetadata:
        is_response = False
        is_rejection = False
        should_update = False
        unique_id = detail_record["transmission_id"]
        response_status = detail_record["transaction_response_status"]
        reject_code = detail_record["reject_code"]
        reject_reason = ""

        if detail_record["transmission_file_type"] == "DR":
            is_response = True
            if response_status == "R":
                is_rejection = True
                should_update = True  # take reject_code into account as needed
                if reject_code:
                    # Return the rejection description if it's valid in our reason mapping, otherwise return
                    # the reject_code directly
                    reject_reason = REJECT_CODE_TO_REASON_MAP.get(
                        reject_code, reject_code
                    )

        return DetailMetadata(
            is_response=is_response,
            is_rejection=is_rejection,
            should_update=should_update,
            unique_id=unique_id,
            member_id=detail_record["sender_reference_number"],
            response_status=response_status,
            response_code=reject_code,
            response_reason=reject_reason,
        )

    def get_response_reason_for_code(self, response_code: str) -> Optional[str]:
        return REJECT_CODE_TO_REASON_MAP.get(response_code)

    # ----- Reconciliation Methods -----

    def get_deductible_from_row(self, detail_row: dict) -> int:
        return self._get_accumulation_sum_from_row(
            detail_row=detail_row, balance_qualifier="04"
        )

    def get_oop_from_row(self, detail_row: dict) -> int:
        return self._get_accumulation_sum_from_row(
            detail_row=detail_row, balance_qualifier="05"
        )

    @staticmethod
    def _get_accumulation_sum_from_row(detail_row: dict, balance_qualifier: str) -> int:
        accum_sum = 0
        for accum in range(1, int(detail_row["accumulator_balance_count"]) + 1):
            if (
                detail_row[f"accumulator_balance_qualifier_{accum}"]
                == balance_qualifier
            ):
                accum_sum += int(detail_row[f"accumulator_applied_amount_{accum}"])
        return accum_sum

    @staticmethod
    def get_cardholder_id_from_detail_dict(detail_row_dict: dict) -> Optional[str]:
        return detail_row_dict.get("cardholder_id")

    def get_dob_from_report_row(self, detail_row_dict: dict) -> date:
        date_str = detail_row_dict["date_of_birth"]
        return datetime.strptime(date_str, "%Y%m%d").date()

    @staticmethod
    def get_detail_rows(report_rows: list) -> list:
        detail_rows = []
        for row in report_rows:
            if row["record_type"] == "DT":
                detail_rows.append(row)
        return detail_rows
