import csv
import datetime
import io
from decimal import Decimal
from typing import List

from models.profiles import PractitionerProfile
from payments.models.constants import PROVIDER_CONTRACTS_EMAIL
from payments.models.contract_validator import (
    ContractValidator,
    EmitsFeesNotOppositeIsStaffException,
)
from payments.models.practitioner_contract import ContractType, PractitionerContract
from storage.connection import db
from utils.log import logger
from utils.mail import send_message

__all__ = ("PractitionerContractService",)

log = logger(__name__)


class PractitionerContractCSVSubmissionError(str):
    INVALID_CSV_HEADERS = "Invalid csv file, please check the file headers"
    INVALID_CSV_DATA = "Invalid data found in csv file"
    NOT_IN_CSV_FORMAT = "File does not appear to be in the csv format"
    NO_CONTRACTS_FOUND = "File does not contain practitioner contracts"
    EMPTY_CSV = "No data found in csv file"


PRACTITIONER_CONTRACT_CSV_HEADERS = [
    "created_by_id",
    "practitioner_id",
    "contract_type",
    "contract_start_date",
    "contract_end_date",
    "hourly_rate",
    "hours_per_week",
    "rate_per_overnight_appt",
    "hourly_appt_rate",
    "message_rate",
]


class PractitionerContractService:
    def get_practitioners_contracts(
        self, practitioner_id: int
    ) -> List[PractitionerContract]:
        # TODO: Create PractitionerContractRepository, KICK-1104
        return (
            db.session.query(PractitionerContract)
            .filter_by(practitioner_id=practitioner_id)
            .all()
        )

    def validate_inputs_to_create_contract(
        self,
        practitioner_id: int,
        created_by_user_id: int,
        contract_type_str: str,
        start_date: datetime.date,
        end_date: datetime.date,
        weekly_contracted_hours: Decimal,
        fixed_hourly_rate: Decimal,
        rate_per_overnight_appt: Decimal,
        hourly_appointment_rate: Decimal,
        non_standard_by_appointment_message_rate: Decimal,
    ) -> None:

        existing_contracts = self.get_practitioners_contracts(practitioner_id)

        contract_validator = ContractValidator(
            practitioner_id=practitioner_id,
            created_by_user_id=created_by_user_id,
            contract_type=ContractType[contract_type_str]  # type: ignore[arg-type] # Argument "contract_type" to "ContractValidator" has incompatible type "Optional[ContractType]"; expected "ContractType"
            if contract_type_str
            else None,
            start_date=start_date,
            end_date=end_date,
            weekly_contracted_hours=weekly_contracted_hours,  # type: ignore[arg-type] # Argument "weekly_contracted_hours" to "ContractValidator" has incompatible type "Decimal"; expected "float"
            fixed_hourly_rate=fixed_hourly_rate,  # type: ignore[arg-type] # Argument "fixed_hourly_rate" to "ContractValidator" has incompatible type "Decimal"; expected "float"
            rate_per_overnight_appt=rate_per_overnight_appt,  # type: ignore[arg-type] # Argument "rate_per_overnight_appt" to "ContractValidator" has incompatible type "Decimal"; expected "float"
            hourly_appointment_rate=hourly_appointment_rate,  # type: ignore[arg-type] # Argument "hourly_appointment_rate" to "ContractValidator" has incompatible type "Decimal"; expected "float"
            non_standard_by_appointment_message_rate=non_standard_by_appointment_message_rate,  # type: ignore[arg-type] # Argument "non_standard_by_appointment_message_rate" to "ContractValidator" has incompatible type "Decimal"; expected "float"
        )
        contract_validator.validate_all_rules(existing_contracts=existing_contracts)

    def validate_new_end_date(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self, contract: PractitionerContract, new_end_date: datetime.date
    ):

        existing_contracts = self.get_practitioners_contracts(contract.practitioner_id)

        contract_validator = ContractValidator(
            contract_id=contract.id,
            start_date=contract.start_date,
            end_date=new_end_date,
        )

        contract_validator.validate_end_date_is_last_day_of_month()

        contract_validator.validate_end_date_after_start_date()

        contract_validator.validate_contract_dates_do_not_conflict_with_existing_contracts(
            existing_contracts=existing_contracts
        )

    def validate_emits_fees_against_is_staff(self, practitioner_id, contract_type):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # method should be deprecated once is_staff is deprecated
        is_staff = PractitionerProfile.query.get(practitioner_id).is_staff
        emits_fees = True if contract_type == "BY_APPOINTMENT" else False
        if is_staff == emits_fees:
            log.warn(
                "upload practitioner contracts - emits_fees not opposite is_staff",
                practitioner_id=practitioner_id,
                is_staff=is_staff,
                contract_type=contract_type,
                emits_fees=emits_fees,
            )
            raise EmitsFeesNotOppositeIsStaffException

    def export_data_to_csv(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        log.info("Starting to export practitioner contracts")
        # Data Engineering requested that BY_APPOINTMENT contracts are not exported
        # They currently don't exist in the template they use so their Looker code doesn't know how to handle it
        contracts = (
            db.session.query(PractitionerContract)
            .filter(PractitionerContract.contract_type != ContractType.BY_APPOINTMENT)
            .all()
        )
        csv = self._generate_csv_data(contracts)
        send_message(
            to_email=PROVIDER_CONTRACTS_EMAIL,
            subject=f"Provider Contracts for {datetime.datetime.now().strftime('%B %Y')}",
            html="The monthly provider contract csv file is attached",
            internal_alert=True,
            production_only=True,
            csv_attachments=[("provider-contracts.csv", csv)],
        )
        log.info(
            "Monthly provider contracts email - sent", contracts_count=len(contracts)
        )

    def _generate_csv_data(self, contracts: List[PractitionerContract]) -> str:
        columns_map = {
            "practitioner_id": "practitioner_id",
            "practitioner_name": "practitioner.full_name",
            "practitioner_email": "practitioner.email",
            "dcw_start_date": "start_date",
            "dcw_end_date": "end_date",
            "payment_type": "contract_type",
            "dcw_hourly_rate": "fixed_hourly_rate",
            "dcw_weekly_hours": "weekly_contracted_hours",
            "dcw_by_appt_rate": "rate_per_overnight_appt",
            "dcw_by_appt_hourly": "hourly_appointment_rate",
            "dcw_by_appt_msg": "non_standard_by_appointment_message_rate",
        }

        csv_stream = io.StringIO()
        csv_writer = csv.writer(csv_stream, quoting=csv.QUOTE_NONNUMERIC)
        csv_writer.writerow(list(columns_map.keys()))
        for contract in contracts:
            row = []
            for _, field in columns_map.items():
                # Joined fields have to be hardcoded
                if field == "practitioner.full_name":
                    row.append(contract.practitioner.user.full_name)
                elif field == "practitioner.email":
                    row.append(contract.practitioner.user.email)
                # Attribute exists on model
                elif hasattr(contract, field):
                    value = getattr(contract, field)
                    # Convert contract_type to payment_type language
                    if field == "contract_type":
                        row.append(self._contract_type_to_payment_type(value))
                    else:
                        row.append(value)

                else:
                    row.append("")
            csv_writer.writerow(row)
        return csv_stream.getvalue()

    def _contract_type_to_payment_type(self, contract_type: ContractType) -> str:
        if contract_type == ContractType.BY_APPOINTMENT.value:
            return  # type: ignore[return-value] # Return value expected
        elif contract_type == ContractType.FIXED_HOURLY.value:
            return "dcw_hourly"
        elif contract_type == ContractType.FIXED_HOURLY_OVERNIGHT.value:
            return "dcw_both"
        elif contract_type == ContractType.HYBRID_1_0.value:
            return "hybrid"
        elif contract_type == ContractType.HYBRID_2_0.value:
            return "hybrid_20"
        elif contract_type == ContractType.W2.value:
            return "w2"
        elif contract_type == ContractType.NON_STANDARD_BY_APPOINTMENT.value:
            return "dcw_by_appt"
        else:
            return  # type: ignore[return-value] # Return value expected
