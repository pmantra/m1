import dataclasses
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_DOWN, Decimal, getcontext
from typing import List, Optional, Tuple, Type, Union

from direct_payment.pharmacy.constants import (
    ESI_DATE_OF_SERVICE_PATTERN,
    ESI_REJECTION_ERROR_CODE_TO_REASON_MAP,
)
from direct_payment.pharmacy.models.health_plan_ytd_spend import (
    HealthPlanYearToDateSpend,
    Source,
)
from direct_payment.pharmacy.tasks.esi_parser.converter import Converter
from direct_payment.pharmacy.tasks.esi_parser.schema_extractor import FixedWidthSchema
from utils.log import logger
from utils.payments import convert_dollars_to_cents

PARENTHESES_PATTERN = re.compile(r"[()]")
SLASH_DASH_PATTERN = re.compile(r"[ /-]+")


log = logger(__name__)


class D2(Converter):
    def __init__(self, name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.name = name
        getcontext().prec = 10

    def convert(self, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not value:
            return Decimal("0.00")
        converted = Decimal(value) / Decimal("100")
        return converted.quantize(Decimal("0.00"), rounding=ROUND_DOWN)


class D3(Converter):
    def __init__(self, name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.name = name
        getcontext().prec = 10

    def convert(self, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        converted = Decimal(value) / Decimal("1000")
        return converted.quantize(Decimal("0.000"), rounding=ROUND_DOWN)


def normalize_key(key: str) -> str:
    """
    Normalize key into snake case format
    """
    # Interesting edge case - Less than ideal but since there's only one I will take it
    if key == "Therapeutic Class Code – Specific":
        return "therapeutic_class_code_specific"
    normalized = SLASH_DASH_PATTERN.sub("_", key)
    normalized = PARENTHESES_PATTERN.sub("", normalized)
    return normalized.lower()


def get_type(raw_type: str) -> Type[Union[int, str, D2, D3]]:
    if raw_type == "N":
        return int
    elif raw_type == "AN":
        return str
    elif raw_type == "D2":
        return D2
    elif raw_type == "D3":
        return D3
    else:
        raise ValueError(f"Unsupported type: {raw_type}")


def create_dataclasses(class_name: str, schema: List[FixedWidthSchema]) -> type:
    """
    Dynamically create a dataclass for a specific vendor
    """
    kclass = type(
        class_name,
        (object,),
        {
            "__annotations__": {
                normalize_key(item.name): get_type(item.data_type) for item in schema
            },
        },
    )
    return dataclass(kclass, frozen=True)  # type: ignore[call-overload] # No overload variant of "dataclass" matches argument types "type", "bool"


@dataclass
class ESIRecord:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    date_of_service: str
    transmission_id: str
    cardholder_id: str
    cardholder_id_alternate: str
    accumulator_action_code: str
    patient_first_name: str
    patient_last_name: str
    date_of_birth: str
    accumulator_balance_benefit_type: str
    accumulator_balance_count: str
    benefit_type: str = "D"
    in_network_indicator: str = ""
    transaction_id: str = ""
    # Fields related to DR status not used in internal Maven records
    transmission_file_type: str = ""
    transaction_response_status: str = ""
    reject_code: str = ""
    # Details around amount
    accumulator_balance_qualifier_1: str = ""
    accumulator_applied_amount_1: D2 = ""  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", variable has type "D2")
    accumulator_network_indicator_1: str = "1"
    action_code_1: str = ""
    accumulator_balance_qualifier_2: str = ""
    accumulator_network_indicator_2: str = ""
    accumulator_applied_amount_2: D2 = ""  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", variable has type "D2")
    action_code_2: str = ""
    sender_reference_number: str = ""


def convert(record) -> ESIRecord:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    """
    Simply convert raw record into an intermediate representation of ESI record
    the conversion only does name normalization and byte => str
    """
    valid_keys = {f.name for f in dataclasses.fields(ESIRecord)}
    filtered_record = {}
    for k, v in record.items():
        try:
            normalized_name = normalize_key(k.name)
            if normalized_name in valid_keys and normalized_name not in filtered_record:
                filtered_record[normalized_name] = v[0].decode("utf-8")
        except (TypeError, UnicodeDecodeError):
            log.error("Failed to convert raw record to ESIRecord", exc_info=True)
            raise

    return ESIRecord(**filtered_record)


def check_record_status(record) -> Tuple[bool, Optional[str]]:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    if record.transmission_file_type == "DR":
        if record.transaction_response_status == "R":
            if record.reject_code:
                # Return the rejection description if it's valid in our reason mapping, otherwise return
                # the reject_code directly
                return True, ESI_REJECTION_ERROR_CODE_TO_REASON_MAP.get(
                    record.reject_code, record.reject_code
                )
        elif record.transaction_response_status == "E":
            return True, "Duplicate Record"
        elif record.transaction_response_status == "A":
            return True, None
    return False, None


def year_converter(date_of_service):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if date_of_service and not ESI_DATE_OF_SERVICE_PATTERN.match(date_of_service):
        raise ValueError(f"Invalid date of service: {date_of_service}")
    try:
        datetime.strptime(date_of_service, "%Y%m%d")
        return int(date_of_service[:4])
    except ValueError:
        raise ValueError(f"Invalid date format: {date_of_service}")


def convert_to_health_plan_ytd_spend(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    esi_record, transaction_filename: str, is_dr_record: bool = False
) -> HealthPlanYearToDateSpend:

    result = HealthPlanYearToDateSpend(
        policy_id=esi_record.cardholder_id_alternate,
        first_name=esi_record.patient_first_name,
        last_name=esi_record.patient_last_name,
        transmission_id=esi_record.transmission_id,
        year=year_converter(esi_record.date_of_service),
        source=Source.MAVEN if is_dr_record else Source.ESI,
        transaction_filename=transaction_filename,
    )

    def deductible_and_oop_converter(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        accumulator_balance_qualifier_1,
        accumulator_applied_amount_1,
        action_code_1,
        accumulator_balance_qualifier_2,
        accumulator_applied_amount_2,
        action_code_2,
    ):
        """
        ESI will send us the amount in following manner:

        if there's deductible, then accumulator_balance_qualifier1 (and it's subsequent fields) will
        represent deductible amount(with 04) accumulator_balance_qualifier2 will be used for OOP

        if there's no deductible, then accumulator_balance_qualifier1 will be used to represent OOP
        with code "05"
        """
        amount = D2("accumulator_applied_amount1").convert(accumulator_applied_amount_1)
        if action_code_1 == "-":
            amount = amount * -1
        # 04 means Deductible
        if accumulator_balance_qualifier_1 == "04":
            result.deductible_applied_amount += convert_dollars_to_cents(amount)
            if accumulator_balance_qualifier_2 == "05":
                oop_amount = D2("accumulator_applied_amount2").convert(
                    accumulator_applied_amount_2
                )
                if action_code_2 == "-":
                    oop_amount = oop_amount * -1
                result.oop_applied_amount += convert_dollars_to_cents(oop_amount)
        # 05 means oop
        elif accumulator_balance_qualifier_1 == "05":
            result.oop_applied_amount += convert_dollars_to_cents(amount)
        else:
            raise ValueError(
                f"Unsupported qualifier type: {accumulator_balance_qualifier_1}"
            )

    deductible_and_oop_converter(
        esi_record.accumulator_balance_qualifier_1,
        esi_record.accumulator_applied_amount_1,
        esi_record.action_code_1,
        esi_record.accumulator_balance_qualifier_2,
        esi_record.accumulator_applied_amount_2,
        esi_record.action_code_2,
    )
    return result
