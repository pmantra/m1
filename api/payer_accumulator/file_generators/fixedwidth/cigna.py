import enum
from copy import deepcopy
from datetime import date, datetime
from io import StringIO
from typing import Dict, List

import overpunch
from fixedwidth.fixedwidth import FixedWidth

from cost_breakdown.models.cost_breakdown import CostBreakdown
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureType,
)
from payer_accumulator import helper_functions
from payer_accumulator.common import DetailWrapper, PayerName
from payer_accumulator.errors import InvalidPatientSexError, InvalidSubscriberIdError
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


class AccumulatorType(enum.Enum):
    DEDUCTIBLE = "D"
    OOP = "O"


class MemberFamilyCode(enum.Enum):
    FAMILY = "F"
    MEMBER = "M"


MEMBER_SEX_TO_CODE = {
    MemberHealthPlanPatientSex.FEMALE: "F",
    MemberHealthPlanPatientSex.MALE: "M",
}

PATIENT_RELATIONSHIP_TO_CODE = {
    MemberHealthPlanPatientRelationship.CARDHOLDER: "EE",
    MemberHealthPlanPatientRelationship.SPOUSE: "SP",
    MemberHealthPlanPatientRelationship.CHILD: "CH",
    MemberHealthPlanPatientRelationship.DOMESTIC_PARTNER: "DP",
    MemberHealthPlanPatientRelationship.FORMER_SPOUSE: "FP",
    MemberHealthPlanPatientRelationship.OTHER: "OT",
}

SOURCE_SYSTEM_TO_CODE = {
    TreatmentProcedureType.MEDICAL: "M",
    TreatmentProcedureType.PHARMACY: "P",
}


class AccumulationFileGeneratorCigna(FixedWidthAccumulationFileGenerator):
    """
    This class is responsible for generating the base payer accumulation file for SFTP and consumption by Cigna.
    It is not responsible for anything other than assembling the file contents (like encryption)
    """

    FILENAME_PREFIX = "QXJ1000__qxj0001i.93827"
    FILENAME_SUFFIX = "edi"

    def __init__(self) -> None:
        super().__init__(payer_name=PayerName.Cigna)
        self.accumulation_config = deepcopy(self.config.ACCUMULATION_SEGMENT)
        self.DETAIL_END_POSITION = self.config.DETAIL_SEGMENT_LENGTH
        self.ACCUMULATION_SEGMENT_LENGTH = self.config.ACCUMULATION_SEGMENT_LENGTH

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
        row_prefix = self._generate_row_prefix(
            record_type,
            member_health_plan,
            service_start_date,
        )
        row_accumulations = self._generate_row_accumulations(
            deductible,
            oop_applied,
        )
        line = row_prefix + row_accumulations + "\r\n"

        timestamp = self.get_run_datetime(length=16)
        unique_id = f"{timestamp}#cb_{cost_breakdown.id}"

        return DetailWrapper(unique_id=unique_id, line=line)

    def _generate_row_prefix(
        self,
        procedure_type: TreatmentProcedureType,
        member_health_plan: MemberHealthPlan,
        service_start_date: datetime,
    ) -> str:
        detail_obj = FixedWidth(self.detail_config, line_end="")
        detail_obj.update(
            member_pid=self.get_cardholder_id(member_health_plan),
            member_first_name=helper_functions.get_patient_first_name(
                member_health_plan
            ).upper(),
            member_last_name=helper_functions.get_patient_last_name(
                member_health_plan
            ).upper(),
            member_dob=member_health_plan.patient_date_of_birth.strftime("%Y-%m-%d"),  # type: ignore[union-attr] # Item "None" of "Optional[date]" has no attribute "strftime"
            member_sex=self.get_member_sex(member_health_plan.patient_sex),  # type: ignore[arg-type] # Argument 1 to "get_member_sex" of "AccumulationFileGeneratorCigna" has incompatible type "Optional[str]"; expected "MemberHealthPlanPatientSex"
            relationship_code=PATIENT_RELATIONSHIP_TO_CODE[
                member_health_plan.patient_relationship  # type: ignore[index] # Invalid index type "Optional[str]" for "Dict[MemberHealthPlanPatientRelationship, str]"; expected type "MemberHealthPlanPatientRelationship"
            ],
            date_of_service=service_start_date.strftime("%Y%m%d"),
            message_date=self.get_run_date(),
            message_time=self.get_run_time(length=8),
            source_system=SOURCE_SYSTEM_TO_CODE[procedure_type],
            accumulation_counter="2",
        )
        return detail_obj.line

    @staticmethod
    def get_cardholder_id(member_health_plan: MemberHealthPlan) -> str:
        subscriber_insurance_id = member_health_plan.subscriber_insurance_id
        if len(subscriber_insurance_id) != 11:
            raise InvalidSubscriberIdError(
                "Cigna subscriber_insurance_id should be 11 digits."
            )
        return subscriber_insurance_id[:-2].upper()

    @staticmethod
    def get_oop_to_submit(deductible: int, oop_applied: int) -> int:
        # Cigna only needs the OOP applied amount when the patient has met deductible.
        # When patient still has deductible left, Cigna automatically applies deductible to the OOP in their system.
        return max(0, oop_applied - deductible)

    def _generate_row_accumulations(
        self,
        deductible: int = 0,
        oop_applied: int = 0,
    ) -> str:
        if deductible is None:
            deductible = 0
        if oop_applied is None:
            oop_applied = 0

        row_accumulations = ""
        row_accumulations += self._generate_row_accumulation(
            AccumulatorType.DEDUCTIBLE,
            deductible / 100,
        )
        row_accumulations += self._generate_row_accumulation(
            AccumulatorType.OOP, oop_applied / 100
        )

        return row_accumulations

    def _generate_row_accumulation(
        self,
        accumulator_type: AccumulatorType,
        amount: float,
    ) -> str:
        accumulation_obj = FixedWidth(self.accumulation_config, line_end="")
        accumulation_obj.update(
            accumulator_type=accumulator_type.value,
            amount=overpunch.format(amount),
        )
        return accumulation_obj.line

    @property
    def file_name(self) -> str:
        file_datetime = f"{self.get_run_date()}_{self.get_run_time()}"
        return f"{self.FILENAME_PREFIX}.{file_datetime}.{self.FILENAME_SUFFIX}"

    @staticmethod
    def get_member_sex(patient_sex: MemberHealthPlanPatientSex) -> str:
        if patient_sex not in MEMBER_SEX_TO_CODE:
            raise InvalidPatientSexError("Patient sex must be female or male for Cigna")
        return MEMBER_SEX_TO_CODE[patient_sex]

    @staticmethod
    def get_amount() -> str:
        return overpunch.format(1234)

    def file_contents_to_dicts(self, file_contents: str) -> List[Dict]:
        rows = []
        file_rows = file_contents.splitlines()
        num_rows = len(file_rows)

        # detail rows
        for i in range(num_rows):
            row_dict = self._cigna_process_file_row_to_dict(file_rows[i])
            rows.append(row_dict)
        return rows

    def _cigna_process_file_row_to_dict(self, row: str) -> Dict:
        # Process each row. Each row contains general information, and repeating section of transactions.
        # See cigna_fixed_width_config.py for details on formatting
        row_dict = {}

        # Fill in detail information
        detail_obj = FixedWidth(self.detail_config)
        detail_length = self.config.DETAIL_SEGMENT_LENGTH
        detail_obj.line = row[:detail_length]
        row_dict.update(detail_obj.data)
        row_dict["accumulations"] = []

        # Fill in accumulations into row dictionary
        accumulation_obj = FixedWidth(self.accumulation_config)
        accumulation_length = self.config.ACCUMULATION_SEGMENT_LENGTH
        accumulations = row[detail_length:]
        num_accumulations = int(len(accumulations) / accumulation_length)
        for i in range(num_accumulations):
            accumulation_obj.line = accumulations[
                i * accumulation_length : (i + 1) * accumulation_length
            ]
            row_dict["accumulations"].append(accumulation_obj.data)
        return row_dict

    def detail_to_dict(self, detail_line: str) -> Dict:
        return self._cigna_process_file_row_to_dict(detail_line)

    def generate_file_contents_from_json(self, report_data: List[Dict]) -> StringIO:
        # gather metadata
        num_rows = len(report_data)

        buffer = StringIO()

        # generate detail rows
        detail_obj = FixedWidth(self.detail_config)
        for i in range(num_rows):
            row_dict = report_data[i]
            detail_segment = deepcopy(row_dict)
            detail_segment.pop("accumulations")
            self.validate_json_against_config(detail_segment, i, self.detail_config)
            detail_obj.update(**detail_segment)
            detail_res = detail_obj.line.replace("\r\n", "")
            # load accumulation data
            accumulations_res = ""
            accumulation_obj = FixedWidth(self.accumulation_config)
            for a_dict in row_dict["accumulations"]:
                accumulation_obj.update(**a_dict)
                res = accumulation_obj.line.replace("\r\n", "")
                accumulations_res += res
            result = detail_res + accumulations_res + "\r\n"
            buffer.write(result)
        return buffer

    # ----- Reconciliation Methods -----
    @staticmethod
    def get_cardholder_id_from_detail_dict(detail_row_dict: dict) -> str:
        return detail_row_dict["member_pid"]

    def get_dob_from_report_row(self, detail_row_dict: dict) -> date:
        date_str = detail_row_dict["member_dob"]
        return datetime.strptime(date_str, "%Y-%m-%d").date()

    def get_deductible_from_row(self, detail_row: dict) -> int:
        return self._get_accumulation_sum_from_row(
            detail_row=detail_row, accumulator_type=AccumulatorType.DEDUCTIBLE
        )

    def get_oop_from_row(self, detail_row: dict) -> int:
        return self._get_accumulation_sum_from_row(
            detail_row=detail_row, accumulator_type=AccumulatorType.OOP
        )

    @staticmethod
    def _get_accumulation_sum_from_row(
        detail_row: dict, accumulator_type: AccumulatorType
    ) -> int:
        accum_sum = 0
        for accumulation in detail_row["accumulations"]:
            if accumulation["accumulator_type"] == accumulator_type.value:
                accum_sum += helper_functions.get_cents_from_overpunch(
                    accumulation["amount"]
                )
        return accum_sum

    @staticmethod
    def get_detail_rows(report_rows: list) -> list:
        return report_rows
