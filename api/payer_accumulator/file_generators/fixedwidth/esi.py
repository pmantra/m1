from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Dict, Optional, Tuple

from fixedwidth.fixedwidth import FixedWidth

from cost_breakdown.models.cost_breakdown import CostBreakdown
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureType,
)
from payer_accumulator import helper_functions
from payer_accumulator.common import DetailWrapper, PayerName
from payer_accumulator.errors import InvalidGroupIdError, InvalidPayerError
from payer_accumulator.file_generators.fixed_width_accumulation_file_generator import (
    FixedWidthAccumulationFileGenerator,
)
from payer_accumulator.models.payer_list import Payer
from utils.log import logger
from wallet.models.constants import (
    MemberHealthPlanPatientRelationship,
    MemberHealthPlanPatientSex,
)
from wallet.models.reimbursement_wallet import MemberHealthPlan

log = logger(__name__)


class ESIAccumulationFileGenerator(FixedWidthAccumulationFileGenerator):
    def __init__(self) -> None:
        super().__init__(payer_name=PayerName.ESI)

    def _get_header_required_fields(self) -> Dict:
        return {
            "file_type": self._get_environment(),
            "creation_date": self.get_run_date(),
            "creation_time": self.get_run_time(length=4),
        }

    def _get_trailer_required_fields(
        self, record_count: int, oop_total: int = 0
    ) -> Dict:
        return {"record_count": record_count}

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
        # Note: transmission_id format: CCYYMMDDHHMMSSLLL#<unique id>, max length 50.
        timestamp = self.get_run_datetime(length=17)
        transmission_id = f"{timestamp}#cb_{cost_breakdown.id}"

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

        transaction_id = str(record_id)
        detail_obj.update(
            transmission_date=self.get_run_date(),
            transmission_time=self.get_run_time(length=8),
            date_of_service=service_start_date.strftime("%Y%m%d"),
            transmission_id=transmission_id,
            transaction_id=transaction_id,
            cardholder_id=cardholder_id,
            group_id=self._get_rx_group_id(member_health_plan),
            patient_first_name=helper_functions.get_patient_first_name(
                member_health_plan
            ).upper(),
            patient_last_name=helper_functions.get_patient_last_name(
                member_health_plan
            ).upper(),
            cardholder_last_name=member_health_plan.subscriber_last_name.upper(),  # type: ignore[union-attr] # Item "None" of "Optional[str]" has no attribute "upper"
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
        # Set alternate since this is the policy id we care
        # Have to do this way since the key name is not kwarg friendly
        detail_obj.data["cardholder_id_(alternate)"] = cardholder_id

        return DetailWrapper(
            unique_id=transmission_id,
            line=detail_obj.line,
            transaction_id=transaction_id,
        )

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

    def _get_gender_code(self, patient_sex: str) -> str:
        mapping = {
            MemberHealthPlanPatientSex.MALE.value: "1",
            MemberHealthPlanPatientSex.FEMALE.value: "2",
        }
        return mapping.get(patient_sex, "0")

    def _get_relationship_code(
        self, patient_relationship: MemberHealthPlanPatientRelationship
    ) -> str:
        mapping = {
            MemberHealthPlanPatientRelationship.CARDHOLDER: "1",
            MemberHealthPlanPatientRelationship.SPOUSE: "2",
            MemberHealthPlanPatientRelationship.DOMESTIC_PARTNER: "8",
            MemberHealthPlanPatientRelationship.FORMER_SPOUSE: "7",
        }
        return mapping.get(patient_relationship, "3")

    @property
    def file_name(self) -> str:
        run_date, run_time = self.get_run_date(), self.get_run_time()
        return f"MAVN_MedAccum_{run_date}_{run_time}"

    @staticmethod
    def get_cardholder_id(member_health_plan: MemberHealthPlan) -> str:
        # For CIGNA, the insurance_id is 10 digit (U+10), where ESI only allows (U+8)
        payer = Payer.query.filter_by(
            id=member_health_plan.employer_health_plan.benefits_payer_id
        ).one_or_none()
        if not payer:
            raise InvalidPayerError("Payer not found for benefit_payer_id")

        if payer.payer_name == PayerName.Cigna:
            cardholder_id = member_health_plan.subscriber_insurance_id.upper()[:9]
        else:
            cardholder_id = member_health_plan.subscriber_insurance_id.upper()
        return cardholder_id

    @staticmethod
    def _get_rx_group_id(member_health_plan: MemberHealthPlan) -> str:
        employer_health_plan = member_health_plan.employer_health_plan

        if employer_health_plan.group_id:
            return employer_health_plan.group_id
        else:
            raise InvalidGroupIdError(
                "Group ID required for non rx integrated employer health plan"
            )

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
