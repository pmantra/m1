from datetime import date, datetime
from typing import Dict, Optional

from fixedwidth.fixedwidth import FixedWidth

from cost_breakdown.models.cost_breakdown import CostBreakdown
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureType,
)
from payer_accumulator import helper_functions
from payer_accumulator.common import DetailWrapper, PayerName
from payer_accumulator.errors import InvalidTreatmentProcedureTypeError
from payer_accumulator.file_generators.fixed_width_accumulation_file_generator import (
    FixedWidthAccumulationFileGenerator,
)
from utils.log import logger
from wallet.models.constants import (
    MemberHealthPlanPatientRelationship,
    MemberHealthPlanPatientSex,
)
from wallet.models.reimbursement_wallet import MemberHealthPlan

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
    MemberHealthPlanPatientSex.UNKNOWN: "0",
    MemberHealthPlanPatientSex.MALE: "1",
    MemberHealthPlanPatientSex.FEMALE: "2",
}

TREATMENT_PROCEDURE_TO_RECORD_TYPE_CODE = {
    TreatmentProcedureType.PHARMACY: "1",
    TreatmentProcedureType.MEDICAL: "2",
}


class AccumulationFileGeneratorUHC(FixedWidthAccumulationFileGenerator):
    """
    This class is responsible for generating the base payer accumulation file for SFTP and consumption by UHC.
    It is not responsible for anything other than assembling the file contents (like encryption)
    """

    def __init__(self) -> None:
        super().__init__(payer_name=PayerName.UHC)

    def _get_header_required_fields(self) -> Dict:
        return {
            "file_content_type": self._get_environment(),
            "run_date": self.get_run_date(),
            "run_time": self.get_run_time(length=8, delimiter=":"),
        }

    def _get_trailer_required_fields(
        self, record_count: int, oop_total: int = 0
    ) -> Dict:
        return {
            "transaction_count": str(record_count),
            "total_record_count": str(
                record_count + self._get_header_trailer_row_count()
            ),
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

        #  Transaction ID will be 20 chars long.
        timestamp = self.get_run_datetime(length=14)
        detail_count = (
            self.record_count + 1
        )  # record_count is one behind (incremented after the row is added to the file)
        transaction_id = f"{timestamp}{detail_count:06}"

        detail_obj.update(
            batch_number=self.get_batch_number(),
            transaction_id=transaction_id,
            record_type_code=self.get_record_type_code(record_type),
            carrier_number=member_health_plan.employer_health_plan.carrier_number,
            adjudication_date=self.get_run_date(),
            first_date_of_service=service_start_date.strftime("%Y%m%d"),
            last_date_of_service=service_start_date.strftime("%Y%m%d"),
            cardholder_id=self.get_cardholder_id(member_health_plan=member_health_plan),
            patient_first_name=helper_functions.get_patient_first_name(
                member_health_plan
            ),
            patient_last_name=helper_functions.get_patient_last_name(
                member_health_plan
            ),
            patient_gender=self.get_patient_gender(member_health_plan),
            patient_dob=member_health_plan.patient_date_of_birth.strftime("%Y%m%d"),  # type: ignore[union-attr] # Item "None" of "Optional[date]" has no attribute "strftime"
            patient_relationship_code=self.get_patient_relationship_code(
                member_health_plan
            ),
            deductible_apply_amount=self.add_signed_overpunch(deductible),
            oop_apply_amount=self.add_signed_overpunch(oop_applied),
            plan_year=service_start_date.strftime("%Y%m%d"),
        )
        return DetailWrapper(
            unique_id=transaction_id,
            line=detail_obj.line,
            transaction_id=transaction_id,
        )

    @property
    def file_name(self) -> str:
        return f"Maven_{self.payer_name.name}_Accumulator_File_{self.get_run_date()}_{self.get_run_time()}"

    @staticmethod
    def get_record_type_code(treatment_procedure_type: TreatmentProcedureType) -> str:
        if treatment_procedure_type not in TREATMENT_PROCEDURE_TO_RECORD_TYPE_CODE:
            raise InvalidTreatmentProcedureTypeError(
                f"Invalid treatment procedure type {treatment_procedure_type}"
            )
        return TREATMENT_PROCEDURE_TO_RECORD_TYPE_CODE[treatment_procedure_type]

    @staticmethod
    def get_patient_gender(member_health_plan) -> str:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        patient_sex = member_health_plan.patient_sex
        return PATIENT_SEX_TO_CODE[patient_sex]

    @staticmethod
    def get_patient_relationship_code(member_health_plan) -> str:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        patient_relationship = member_health_plan.patient_relationship
        return PATIENT_RELATION_TO_CODE[patient_relationship]

    @staticmethod
    def get_cardholder_id(member_health_plan: MemberHealthPlan) -> str:
        return member_health_plan.subscriber_insurance_id.upper()

    # ----- Reconciliation Methods -----
    @staticmethod
    def get_cardholder_id_from_detail_dict(detail_row_dict: dict) -> Optional[str]:
        return detail_row_dict.get("cardholder_id")

    def get_dob_from_report_row(self, detail_row_dict: dict) -> date:
        date_str = detail_row_dict["patient_dob"]
        return datetime.strptime(date_str, "%Y%m%d").date()

    @staticmethod
    def get_detail_rows(report_rows: list) -> list:
        detail_rows = []
        for row in report_rows:
            if row["record_code"] == "4":
                detail_rows.append(row)
        return detail_rows

    def get_deductible_from_row(self, detail_row: dict) -> int:
        return helper_functions.get_cents_from_overpunch(
            detail_row["deductible_apply_amount"]
        )

    def get_oop_from_row(self, detail_row: dict) -> int:
        return helper_functions.get_cents_from_overpunch(detail_row["oop_apply_amount"])
