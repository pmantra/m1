import calendar
from datetime import MAXYEAR, date
from typing import List

from authn.domain.service import UserService
from models.profiles import PractitionerProfile
from payments.models.practitioner_contract import ContractType, PractitionerContract
from storage.connection import db
from utils.log import logger

log = logger(__name__)


class InvalidPractitionerContractInputsException(Exception):
    ...


# TODO: Change for StartDate
class StartDateNotFirstOfMonthException(InvalidPractitionerContractInputsException):
    message = "Contract start date should be first day of the month"


class EndDateNotEndOfMonthException(InvalidPractitionerContractInputsException):
    message = "Contract end date should be last day of the month"


class EndDateBeforeStartDateException(InvalidPractitionerContractInputsException):
    message = "End date must be after start date"


class PractitionerIdCantBeNoneException(InvalidPractitionerContractInputsException):
    message = "Practitioner ID cant be none"


class InvalidPractitionerIdException(InvalidPractitionerContractInputsException):
    message = "Invalid Practitioner ID"


class CreatedByUserIdCantBeNoneException(InvalidPractitionerContractInputsException):
    message = "Created by User ID cant be none"


class InvalidCreatedByUserIdException(InvalidPractitionerContractInputsException):
    message = "Invalid Created by User ID"


class WeeklyContractedHourNoneException(InvalidPractitionerContractInputsException):
    message = "Weekly contracted hour must not be none for selected contract type"


class WeeklyContractedHourNotNoneException(InvalidPractitionerContractInputsException):
    message = "Weekly contracted hour must be none for selected contract type"


class FixedHourlyRateNoneException(InvalidPractitionerContractInputsException):
    message = "Fixed hourly rate must not be none for selected contract type"


class FixedHourlyRateNotNoneException(InvalidPractitionerContractInputsException):
    message = "Fixed hourly rate must be none for selected contract type"


class RatePerOvernightApptNoneException(InvalidPractitionerContractInputsException):
    message = (
        "Rate per overnight appointment must not be none for selected contract type"
    )


class RatePerOvernightApptNotNoneException(InvalidPractitionerContractInputsException):
    message = "Rate per overnight appointment must be none for selected contract type"


class HourlyAppointmentRateNoneException(InvalidPractitionerContractInputsException):
    message = "Hourly appointment rate must not be none for selected contract type"


class HourlyAppointmentRateNotNoneException(InvalidPractitionerContractInputsException):
    message = "Hourly appointment rate must be none for selected contract type"


class NonStandardByAppointmentMessageRateNoneException(
    InvalidPractitionerContractInputsException
):
    message = "Non-standard by appointment message rate must not be none for selected contract type"


class NonStandardByAppointmentMessageRateNotNoneException(
    InvalidPractitionerContractInputsException
):
    message = "Non-standard by appointment message rate must be none for selected contract type"


class ConflictWithExistingContractException(InvalidPractitionerContractInputsException):
    message = "Contract dates conflict with existing contracts"


class EmitsFeesNotOppositeIsStaffException(InvalidPractitionerContractInputsException):
    message = "Practitioner Contract emits_fees value is not opposite is_staff"


class ContractValidator:
    def __init__(
        self,
        contract_id: int = None,  # type: ignore[assignment] # Incompatible default for argument "contract_id" (default has type "None", argument has type "int")
        practitioner_id: int = None,  # type: ignore[assignment] # Incompatible default for argument "practitioner_id" (default has type "None", argument has type "int")
        created_by_user_id: int = None,  # type: ignore[assignment] # Incompatible default for argument "created_by_user_id" (default has type "None", argument has type "int")
        contract_type: ContractType = None,  # type: ignore[assignment] # Incompatible default for argument "contract_type" (default has type "None", argument has type "ContractType")
        start_date: date = None,  # type: ignore[assignment] # Incompatible default for argument "start_date" (default has type "None", argument has type "date")
        end_date: date = None,  # type: ignore[assignment] # Incompatible default for argument "end_date" (default has type "None", argument has type "date")
        weekly_contracted_hours: float = None,  # type: ignore[assignment] # Incompatible default for argument "weekly_contracted_hours" (default has type "None", argument has type "float")
        fixed_hourly_rate: float = None,  # type: ignore[assignment] # Incompatible default for argument "fixed_hourly_rate" (default has type "None", argument has type "float")
        rate_per_overnight_appt: float = None,  # type: ignore[assignment] # Incompatible default for argument "rate_per_overnight_appt" (default has type "None", argument has type "float")
        hourly_appointment_rate: float = None,  # type: ignore[assignment] # Incompatible default for argument "hourly_appointment_rate" (default has type "None", argument has type "float")
        non_standard_by_appointment_message_rate: float = None,  # type: ignore[assignment] # Incompatible default for argument "non_standard_by_appointment_message_rate" (default has type "None", argument has type "float")
    ):
        self.contract_id = contract_id
        self.practitioner_id = practitioner_id
        self.created_by_user_id = created_by_user_id
        self.contract_type = contract_type
        self.start_date = start_date
        self.end_date = end_date
        self.weekly_contracted_hours = weekly_contracted_hours
        self.fixed_hourly_rate = fixed_hourly_rate
        self.rate_per_overnight_appt = rate_per_overnight_appt
        self.hourly_appointment_rate = hourly_appointment_rate
        self.non_standard_by_appointment_message_rate = (
            non_standard_by_appointment_message_rate
        )

    @property
    def end_date_not_none(self) -> date:  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # If end_dates doesnt exist, we can replace it by max possible date
        return self.end_date if self.end_date else date(MAXYEAR, 12, 31)

    def _contract_is_by_appointment_or_non_standard_by_appointment(self) -> bool:  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.contract_type in (
            ContractType.BY_APPOINTMENT,
            ContractType.NON_STANDARD_BY_APPOINTMENT,
        )

    @property
    def _requires_weekly_contracted_hours(self) -> bool:  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return not self._contract_is_by_appointment_or_non_standard_by_appointment()

    @property
    def _requires_fixed_hourly_rate(self) -> bool:
        return not self._contract_is_by_appointment_or_non_standard_by_appointment()

    @property
    def _requires_rate_per_overnight_appt(self) -> bool:
        return self.contract_type == ContractType.FIXED_HOURLY_OVERNIGHT

    @property
    def _requires_hourly_appointment_rate(self) -> bool:  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.contract_type in (
            ContractType.HYBRID_1_0,
            ContractType.HYBRID_2_0,
            ContractType.NON_STANDARD_BY_APPOINTMENT,
        )

    @property
    def _requires_non_standard_by_appointment_message_rate(self) -> bool:  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.contract_type == ContractType.NON_STANDARD_BY_APPOINTMENT

    def validate_start_date_is_first_of_month(self) -> None:  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self.start_date.day != 1:
            exception = StartDateNotFirstOfMonthException()
            log.info(exception.message, start_date=self.start_date)
            raise exception

    def validate_end_date_is_last_day_of_month(self) -> None:  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self.end_date:
            _, n_days_in_month = calendar.monthrange(
                self.end_date.year, self.end_date.month
            )
            if self.end_date.day != n_days_in_month:
                exception = EndDateNotEndOfMonthException()
                log.info(exception.message, end_date=self.end_date)
                raise exception

    def validate_end_date_after_start_date(self) -> None:  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self.end_date:
            if self.end_date < self.start_date:
                exception = EndDateBeforeStartDateException()
                log.info(
                    exception.message,
                    start_date=self.start_date,
                    end_date=self.end_date,
                )
                raise exception

    def validate_practitioner_id(self) -> None:  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self.practitioner_id is None:
            exception = PractitionerIdCantBeNoneException()
            log.info(exception.message)
            raise exception

        practitioner = db.session.query(PractitionerProfile).get(self.practitioner_id)
        if practitioner is None:
            exception = InvalidPractitionerIdException()
            log.info(exception.message, practitioner_id=self.practitioner_id)
            raise exception

    def validate_created_by_user_id(self) -> None:  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self.created_by_user_id is None:
            exception = CreatedByUserIdCantBeNoneException()
            log.info(exception.message)
            raise exception

        user = UserService().get_user(user_id=self.created_by_user_id)
        if not user:
            exception = InvalidCreatedByUserIdException()
            log.info(exception.message, created_by_user_id=self.created_by_user_id)
            raise exception

    def _should_weekly_contracted_hours_and_fixed_hourly_rate_be_none(self) -> bool:  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.contract_type in (ContractType.BY_APPOINTMENT, ContractType.W2)

    def _get_any_conflicting_contract(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self, practitioner_contracts
    ) -> PractitionerContract:
        # To determine if two ranges conflict, we will
        # 1. Determine the latest of the two start dates and the earliest of the two end dates.
        # 2. Compute the timedelta by subtracting them.
        # 3. If the delta is positive, that is the number of days of overlap.
        # Reference: https://stackoverflow.com/a/9044111
        for practitioner_contract in practitioner_contracts:

            # If the contract_validator has a contract_id, it means we are using it to validate a contract that is being updated
            # If thats the case, we should not look for conflicts with itself
            if self.contract_id and self.contract_id == practitioner_contract.id:
                continue

            latest_start = max(practitioner_contract.start_date, self.start_date)

            earliest_end = min(
                practitioner_contract.end_date_not_none, self.end_date_not_none
            )
            delta = (earliest_end - latest_start).days + 1
            if delta > 0:
                return practitioner_contract

        return None  # type: ignore[return-value] # Incompatible return value type (got "None", expected "PractitionerContract")

    def validate_contract_dates_do_not_conflict_with_existing_contracts(
        self, existing_contracts: List[PractitionerContract]
    ) -> None:
        # New contract dates do not conflict with existing contracts
        conflicting_contract = self._get_any_conflicting_contract(existing_contracts)
        if conflicting_contract:
            exception = ConflictWithExistingContractException()
            log.info(
                exception.message,
                practitioner_id=self.practitioner_id,
                new_contract_start_date=self.start_date,
                new_contract_end_date=self.end_date,
                conflicting_contract_id=conflicting_contract.id,
                conflicting_contract_start_date=conflicting_contract.start_date,
                conflicting_contract_end_date=conflicting_contract.end_date,
            )
            exception.message += f". Conflict with Contract [{conflicting_contract.id}]"
            raise exception

    def _validate_weekly_contracted_hours(self) -> None:

        if (
            self._requires_weekly_contracted_hours
            and self.weekly_contracted_hours is None
        ):
            exception = WeeklyContractedHourNoneException()
            log.info(
                exception.message,
                contract_type=self.contract_type,
                weekly_contracted_hours=self.weekly_contracted_hours,
            )
            raise exception

        if (
            not self._requires_weekly_contracted_hours
            and self.weekly_contracted_hours is not None
        ):
            exception = WeeklyContractedHourNotNoneException()
            log.info(
                exception.message,
                contract_type=self.contract_type,
                weekly_contracted_hours=self.weekly_contracted_hours,
            )
            raise exception

    def _validate_fixed_hourly_rate(self) -> None:

        if self._requires_fixed_hourly_rate and self.fixed_hourly_rate is None:
            exception = FixedHourlyRateNoneException()
            log.info(
                exception.message,
                contract_type=self.contract_type,
                fixed_hourly_rate=self.fixed_hourly_rate,
            )
            raise exception

        if not self._requires_fixed_hourly_rate and self.fixed_hourly_rate is not None:
            exception = FixedHourlyRateNotNoneException()
            log.info(
                exception.message,
                contract_type=self.contract_type,
                fixed_hourly_rate=self.fixed_hourly_rate,
            )
            raise exception

    def _validate_rate_per_overnight_appt(self) -> None:
        if (
            self._requires_rate_per_overnight_appt
            and self.rate_per_overnight_appt is None
        ):
            exception = RatePerOvernightApptNoneException()
            log.info(
                exception.message,
                contract_type=self.contract_type,
            )
            raise exception

        if (
            not self._requires_rate_per_overnight_appt
            and self.rate_per_overnight_appt is not None
        ):
            exception = RatePerOvernightApptNotNoneException()
            log.info(
                exception.message,
                contract_type=self.contract_type,
                rate_per_overnight_appt=self.rate_per_overnight_appt,
            )
            raise exception

    def _validate_hourly_appointment_rate(self) -> None:
        if (
            self._requires_hourly_appointment_rate
            and self.hourly_appointment_rate is None
        ):
            exception = HourlyAppointmentRateNoneException()
            log.info(
                exception.message,
                contract_type=self.contract_type,
            )
            raise exception

        if (
            not self._requires_hourly_appointment_rate
            and self.hourly_appointment_rate is not None
        ):
            exception = HourlyAppointmentRateNotNoneException()
            log.info(
                exception.message,
                contract_type=self.contract_type,
                hourly_appointment_rate=self.hourly_appointment_rate,
            )
            raise exception

    def _validate_non_standard_by_appointment_message_rate(self) -> None:
        if (
            self._requires_non_standard_by_appointment_message_rate
            and self.non_standard_by_appointment_message_rate is None
        ):
            exception = NonStandardByAppointmentMessageRateNoneException()
            log.info(
                exception.message,
                contract_type=self.contract_type,
            )
            raise exception

        if (
            not self._requires_non_standard_by_appointment_message_rate
            and self.non_standard_by_appointment_message_rate is not None
        ):
            exception = NonStandardByAppointmentMessageRateNotNoneException()
            log.info(
                exception.message,
                contract_type=self.contract_type,
                non_standard_by_appointment_message_rate=self.non_standard_by_appointment_message_rate,
            )
            raise exception

    def validate_contract_details_match_contract_type(self) -> None:
        self._validate_weekly_contracted_hours()
        self._validate_fixed_hourly_rate()
        self._validate_rate_per_overnight_appt()
        self._validate_hourly_appointment_rate()
        self._validate_non_standard_by_appointment_message_rate()

    def validate_all_rules(
        self, existing_contracts: List[PractitionerContract]
    ) -> None:

        # Only allow start date to be on a 1st of a month and end date to be a last day of the month
        # This is a temporal constrain. Once removed, it would also be good to add some more test cases
        # For example, one where old contract ends the same day as new contract starts.

        self.validate_start_date_is_first_of_month()

        self.validate_end_date_is_last_day_of_month()

        self.validate_end_date_after_start_date()

        self.validate_practitioner_id()

        self.validate_created_by_user_id()

        self.validate_contract_details_match_contract_type()

        self.validate_contract_dates_do_not_conflict_with_existing_contracts(
            existing_contracts=existing_contracts
        )
