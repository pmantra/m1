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
from payer_accumulator.errors import InvalidGroupIdError, InvalidSubscriberIdError
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
    "15": "Invalid Date of Service",
    "52": "Invalid Cardholder ID",
    "06": "Invalid Group ID",
    "210": "Invalid Transaction ID",
    "782": "Invalid SenderID",
    "786": "Invalid Transmission Date",
    "791": "Invalid Network Indicator",
    "792": "Duplicate Record",
}


class AccumulationFileGeneratorPremera(FixedWidthAccumulationFileGenerator):
    def __init__(self) -> None:
        super().__init__(payer_name=PayerName.PREMERA)

    def _get_trailer_required_fields(
        self, record_count: int, oop_total: int = 0
    ) -> Dict:
        return {
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

        timestamp = self.get_run_datetime(length=17)
        transmission_id = f"{timestamp}#cb_{cost_breakdown.id}"
        transaction_id = (
            f"cb_{cost_breakdown.id}" if cost_breakdown else f"rr_{record_id}"
        )

        (
            accumulator_balance_type_1,
            accumulator_applied_amount_1,
            action_code_1,
            accumulator_balance_type_2,
            accumulator_applied_amount_2,
            action_code_2,
            accumulator_balance_type_3,
            accumulator_applied_amount_3,
            action_code_3,
            accumulator_balance_count,
        ) = self._get_balance_details(deductible, oop_applied, hra_applied)

        detail_obj.update(
            transmission_date=self.get_run_date(delimiter="-"),
            transmission_time=self.get_run_time(length=8, delimiter=":"),
            date_of_service=service_start_date.strftime("%Y-%m-%d"),
            transmission_id=transmission_id,
            # Store our member_id in `sender_reference_number` for future troubleshooting purpose
            sender_reference_number=str(member_health_plan.member_id)
            if member_health_plan.member_id
            else "",
            transaction_id=transaction_id,
            cardholder_id=self.get_cardholder_id(member_health_plan),
            group_id=self.get_group_id(member_health_plan),
            patient_first_name=helper_functions.get_patient_first_name(
                member_health_plan
            ).upper(),
            patient_last_name=helper_functions.get_patient_last_name(
                member_health_plan
            ).upper(),
            patient_relationship_code=AccumulationFileGeneratorPremera._get_relationship_code(
                member_health_plan.patient_relationship  # type: ignore[arg-type] # Argument 1 to "_get_relationship_code" of "AccumulationFileGeneratorPremera" has incompatible type "str | None"; expected "MemberHealthPlanPatientRelationship"
            ),
            date_of_birth=member_health_plan.patient_date_of_birth.strftime("%Y-%m-%d"),  # type: ignore[union-attr] # Item "None" of "Optional[date]" has no attribute "strftime"
            patient_gender_code=AccumulationFileGeneratorPremera._get_gender_code(
                member_health_plan.patient_sex  # type: ignore[arg-type] # Argument 1 to "_get_gender_code" of "AccumulationFileGeneratorPremera" has incompatible type "str | None"; expected "str"
            ),
            cardholder_last_name=member_health_plan.subscriber_last_name.upper(),  # type: ignore[union-attr] # Item "None" of "Optional[str]" has no attribute "upper"
            patient_id=member_health_plan.subscriber_insurance_id,  # includes suffix
            accumulator_balance_count=accumulator_balance_count,
            accumulator_balance_type_1=accumulator_balance_type_1,
            accumulator_applied_amount_1=accumulator_applied_amount_1,
            action_code_1=action_code_1,
            accumulator_balance_type_2=accumulator_balance_type_2,
            accumulator_applied_amount_2=accumulator_applied_amount_2,
            action_code_2=action_code_2,
            accumulator_balance_type_3=accumulator_balance_type_3,
            accumulator_applied_amount_3=accumulator_applied_amount_3,
            action_code_3=action_code_3,
            accumulator_action_code="11" if is_reversal else "00",
        )
        return DetailWrapper(
            unique_id=transmission_id,
            line=detail_obj.line,
            transaction_id=transaction_id,
        )

    def _get_processor_routing_identification(self) -> str:
        return ""

    def _get_balance_details(
        self, deductible: int, oop_applied: int, hra_applied: int
    ) -> list:
        # Premera has indicated that Maven MUST send all values (deductible, OOP, and HRA)
        # even if they are zero.
        amount_to_benefit_types = [
            (deductible, "04"),
            (oop_applied, "05"),
            (hra_applied, "22"),
        ]
        details = []
        balance_count = 0
        for amount, benefit_type in amount_to_benefit_types:
            balance_count += 1
            details += [benefit_type, *self._get_value_and_sign_from_amount(amount)]
        details += (len(amount_to_benefit_types) - balance_count) * [
            "",
            *self._get_value_and_sign_from_amount(0),
        ]  # fill zeros
        return details + [str(balance_count).zfill(2)]

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
            MemberHealthPlanPatientSex.MALE.value: "M",
            MemberHealthPlanPatientSex.FEMALE.value: "F",
        }
        return mapping.get(patient_sex, "U")

    @staticmethod
    def _get_relationship_code(
        patient_relationship: MemberHealthPlanPatientRelationship,
    ) -> str:
        mapping = {
            MemberHealthPlanPatientRelationship.CARDHOLDER: "1",
            MemberHealthPlanPatientRelationship.SPOUSE: "2",
            MemberHealthPlanPatientRelationship.CHILD: "3",
        }
        return mapping.get(patient_relationship, "4")  # default to Other

    @property
    def file_name(self) -> str:
        run_date_time = self.get_run_datetime(14)
        env = "" if Environment.current() == Environment.PRODUCTION else "T_"
        return f"AccmMdSnd_{env}MAVENtoPBC_{run_date_time}"

    @staticmethod
    def get_cardholder_id(member_health_plan: MemberHealthPlan) -> str:
        subscriber_insurance_id = member_health_plan.subscriber_insurance_id
        if len(subscriber_insurance_id) != 11:
            raise InvalidSubscriberIdError(
                "Premera subscriber_insurance_id should be 11 digits."
            )
        return subscriber_insurance_id[:-2]

    @staticmethod
    def get_group_id(member_health_plan: MemberHealthPlan) -> str:
        employer_health_plan = member_health_plan.employer_health_plan

        if employer_health_plan.carrier_number:
            return employer_health_plan.carrier_number
        else:
            raise InvalidGroupIdError("Group ID required")

    # ----- Response Processing Methods -----

    # Format is: AccmMdRsp_[T_]PBCto[PBM]_CCYYMMDDHHMMSS.txt
    RESPONSE_FILENAME_PATTERN = re.compile(
        r"AccmMdRsp_(T_)?PBCtoMAVEN_(\d{8})(\d{6}).txt"
    )

    def match_response_filename(self, file_name: str) -> bool:
        return self.RESPONSE_FILENAME_PATTERN.match(file_name) is not None

    def get_response_file_date(self, file_name: str) -> Optional[str]:
        match = self.RESPONSE_FILENAME_PATTERN.match(file_name)
        if match:
            return match.group(2)
        return None

    def get_detail_metadata(self, detail_record: dict) -> DetailMetadata:
        is_response = False
        is_rejection = False
        should_update = False
        unique_id = detail_record["transmission_id"]
        response_status = detail_record["transaction_response_status"]
        reject_code = detail_record["reject_code"].strip()
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
            if detail_row[f"accumulator_balance_type_{accum}"] == balance_qualifier:
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
            if (
                row["record_type"] == "HD"
            ):  # detail rows are marked as header, no header rows
                detail_rows.append(row)
        return detail_rows
