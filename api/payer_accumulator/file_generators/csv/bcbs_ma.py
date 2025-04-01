import difflib
import re
from datetime import datetime
from decimal import Decimal
from typing import Optional

from cost_breakdown.models.cost_breakdown import CostBreakdown
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureType,
)
from payer_accumulator.common import DetailMetadata, DetailWrapper, PayerName
from payer_accumulator.csv.csv_accumulation_file_generator import (
    CSV_DELIMITER,
    CSVAccumulationFileGenerator,
)
from utils.log import logger
from wallet.models.reimbursement_wallet import MemberHealthPlan

log = logger(__name__)

FILENAME_PREFIX = "Maven"


class AccumulationCSVFileGeneratorBCBSMA(CSVAccumulationFileGenerator):
    def __init__(self, health_plan_name: Optional[str] = None) -> None:
        super().__init__(
            payer_name=PayerName.BCBS_MA, health_plan_name=health_plan_name
        )
        self.record_count = 0

    @property
    def file_name(self) -> str:
        file_datetime = self.get_run_datetime()
        if self.health_plan_name:
            return f"{FILENAME_PREFIX}_{self.health_plan_name}{file_datetime}.csv"
        else:
            return f"{FILENAME_PREFIX}_{file_datetime}.csv"

    # Format is: Outbound Claims Response – MavenMMDDYYYY
    RESPONSE_FILENAME_PATTERN = re.compile(
        r"Outbound Claims Response – Maven(\d{8}).csv"
    )

    def get_response_file_date(self, file_name: str) -> str:
        """Extract date from response file name."""
        match = self.RESPONSE_FILENAME_PATTERN.match(file_name)
        if match:
            return match.group(1)
        # If we can't extract the date from the filename, return today's date
        return datetime.utcnow().strftime("%Y%m%d")

    def _generate_header(self) -> str:
        return CSV_DELIMITER.join(
            [
                "MemberID",
                "MemberFirstName",
                "MemberLastName",
                "MemberDateofBirth",
                "CalendarYearOfAccum",
                "DateOfService",
                '"InNetworkIndividualDeductibleAppliedby""Vendor"""',
                '"InNetworkFamilyDeductibleAppliedby""Vendor"""',
                '"InNetworkIndividualOOPAppliedby""Vendor"""',
                '"InNetworkFamilyOOPAppliedby""Vendor"""',
                '"OutOfNetworkIndividualDeductibleAppliedby""Vendor"""',
                '"OutOfNetworkFamilyDeductibleAppliedby""Vendor"""',
                '"OutOfNetworkIndividualOOPAppliedby""Vendor"""',
                '"OutOfNetworkFamilyOOPAppliedby""Vendor"""',
                "Notes",
                "TypeOfClaim",
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
        # Handle reversals
        if is_reversal:
            deductible = -deductible
            oop_applied = -oop_applied

        # Format amounts as dollars and cents
        deductible_str = f"{float(Decimal(deductible) / Decimal(100)):.2f}"  # type: ignore[arg-type]
        oop_str = f"{float(Decimal(oop_applied) / Decimal(100)):.2f}"  # type: ignore[arg-type]

        # Get current year for calendar year field
        calendar_year = service_start_date.year

        # Format service date as YYYYMMDD
        parsed_service_date = service_start_date.strftime("%Y%m%d")
        unique_id = f"{member_health_plan.subscriber_insurance_id}-{parsed_service_date}-{deductible}-{oop_applied}"
        self.record_count += 1

        # Format date of birth as MM/DD/YYYY
        dob_str = member_health_plan.patient_date_of_birth.strftime("%m/%d/%Y")  # type: ignore[union-attr]
        # Format service date as MM/DD/YYYY
        service_date_str = service_start_date.strftime("%m/%d/%Y")

        return DetailWrapper(
            unique_id=unique_id,
            line=CSV_DELIMITER.join(
                [
                    member_health_plan.subscriber_insurance_id,  # MemberID
                    member_health_plan.patient_first_name,  # type: ignore[list-item]
                    member_health_plan.patient_last_name,  # type: ignore[list-item]
                    dob_str,
                    str(calendar_year),
                    service_date_str,
                    deductible_str,  # In-network individual deductible
                    "",  # N/A In-network family deductible
                    oop_str,  # In-network individual OOP
                    "",  # N/A In-network family OOP
                    "",  # N/A Out-of-network individual deductible
                    "",  # N/A Out-of-network family deductible
                    "",  # N/A Out-of-network individual OOP
                    "",  # N/A Out-of-network family OOP
                    "",  # Notes
                    "New" if not is_reversal else "Reversal",  # TypeOfClaim
                ]
            ),
        )

    def get_detail_metadata(self, detail_record: dict[str, str]) -> DetailMetadata:
        """Extract detail_metadata from a CSV response record."""
        # fuzzy match on column names in case they are changed by bcbs-ma
        status = self.fuzzy_get(detail_record, "Status").strip()
        member_id = self.fuzzy_get(detail_record, "MemberID").strip()
        service_date = self.fuzzy_get(detail_record, "DateOfService").strip()
        deductible = self.fuzzy_get(
            detail_record, 'InNetworkIndividualDeductibleAppliedby"Vendor"'
        ).strip()
        oop = self.fuzzy_get(
            detail_record, 'InNetworkIndividualOOPAppliedby"Vendor"'
        ).strip()
        type_of_claim = self.fuzzy_get(detail_record, "Type of Claim").strip()
        cost_share_posted = self.fuzzy_get(detail_record, "Cost Share posted").strip()
        adjustment_needed = self.fuzzy_get(detail_record, "Adjustment Needed").strip()
        adjustment_reason = self.fuzzy_get(detail_record, "Adjustment Reason").strip()
        reprocess = self.fuzzy_get(detail_record, "Reprocess").strip()
        cost_share_type = self.fuzzy_get(detail_record, "Cost Share Type").strip()
        notes = self.fuzzy_get(detail_record, "Notes").strip()
        response_code = f"cost_share_posted: {cost_share_posted}<br>adjustment_needed: {adjustment_needed}<br>adjustment_reason: {adjustment_reason})<br>reprocess: {reprocess}<br>cost_share_type: {cost_share_type}<br>notes: {notes}"

        # format service date as YYYYMMDD
        service_date = datetime.strptime(service_date, "%m/%d/%Y").strftime("%Y%m%d")
        # recreate the unique_id since it is not sent in the file
        formatted_deductible = int(float(deductible) * 100) if deductible else 0
        formatted_oop = int(float(oop) * 100) if oop else 0
        unique_id = f"{member_id}-{service_date}-{formatted_deductible}-{formatted_oop}"

        is_response = type_of_claim == "New"
        is_rejection = is_response and status != "Completed"
        should_update = is_rejection

        return DetailMetadata(
            is_response=is_response,
            is_rejection=is_rejection,
            should_update=should_update,
            member_id=member_id,
            unique_id=unique_id,
            response_status=status,
            response_code=response_code,
            response_reason=notes,
        )

    def fuzzy_get(self, dict_obj: dict, search_key: str) -> str:
        substring_matches = [key for key in dict_obj.keys() if search_key in str(key)]
        matching_key = substring_matches[0] if substring_matches else ""
        if not matching_key:
            closest_matches = difflib.get_close_matches(
                search_key, dict_obj.keys(), n=1
            )
            matching_key = closest_matches[0] if closest_matches else ""
            if not matching_key:
                # log monitor https://app.datadoghq.com/monitors/166769796
                log.error(
                    "Matching key not found for fuzzy get in accumulation response processing. Returning empty string.",
                    search_key=search_key,
                )
                return ""
        return dict_obj[matching_key]
