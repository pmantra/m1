import pytest

from payments.models.contract_validator import (
    ConflictWithExistingContractException,
    CreatedByUserIdCantBeNoneException,
    EndDateBeforeStartDateException,
    EndDateNotEndOfMonthException,
    FixedHourlyRateNoneException,
    FixedHourlyRateNotNoneException,
    HourlyAppointmentRateNoneException,
    HourlyAppointmentRateNotNoneException,
    InvalidCreatedByUserIdException,
    InvalidPractitionerIdException,
    NonStandardByAppointmentMessageRateNoneException,
    NonStandardByAppointmentMessageRateNotNoneException,
    PractitionerIdCantBeNoneException,
    RatePerOvernightApptNoneException,
    RatePerOvernightApptNotNoneException,
    StartDateNotFirstOfMonthException,
    WeeklyContractedHourNoneException,
    WeeklyContractedHourNotNoneException,
)
from payments.models.practitioner_contract import ContractType


class TestValidateStartDateIsFirstOfMonth:
    def test_validate_start_date_is_first_of_month__start_day_is_not_first_of_month(
        self, contract_validator, jan_2nd_this_year
    ):
        # Given
        contract_validator.start_date = jan_2nd_this_year

        # Then
        with pytest.raises(StartDateNotFirstOfMonthException):
            # When
            contract_validator.validate_start_date_is_first_of_month()

    def test_validate_start_date_is_first_of_month__start_day_is_first_of_month(
        self, contract_validator, jan_1st_this_year
    ):
        contract_validator.start_date = jan_1st_this_year

        # When
        contract_validator.validate_start_date_is_first_of_month()

        # Then no exception is raised


class TestValidateEndDateIsLastDayOfMonth:
    def test_validate_end_date_is_last_day_of_month__end_day_is_not_last_of_month(
        self, contract_validator, jan_2nd_this_year
    ):
        # Given
        contract_validator.end_date = jan_2nd_this_year

        # Then
        with pytest.raises(EndDateNotEndOfMonthException):
            # When
            contract_validator.validate_end_date_is_last_day_of_month()

    def test_validate_end_date_is_last_day_of_month__end_day_is_last_of_month(
        self, contract_validator, jan_31st_this_year
    ):
        # Given
        contract_validator.end_date = jan_31st_this_year

        # When
        contract_validator.validate_end_date_is_last_day_of_month()

        # Then no exception is raised


class TestValidateEndDateAfterStartDate:
    def test_validate_inputs_to_create_contract__end_day_is_before_start_date(
        self, contract_validator, feb_1st_this_year, jan_31st_this_year
    ):
        # Given
        contract_validator.start_date = feb_1st_this_year
        contract_validator.end_date = jan_31st_this_year

        # Then
        with pytest.raises(EndDateBeforeStartDateException):
            # When
            contract_validator.validate_end_date_after_start_date()

    def test_validate_inputs_to_create_contract__end_day_is_after_as_start_date(
        self, contract_validator, jan_1st_this_year, jan_31st_this_year
    ):
        # Given
        contract_validator.start_date = jan_1st_this_year
        contract_validator.end_date = jan_31st_this_year

        # When
        contract_validator.validate_end_date_after_start_date()

        # Then no exception is raised


class TestValidatePractitionerId:
    @pytest.mark.parametrize(
        argnames="prac_id,exception",
        argvalues=[
            (None, PractitionerIdCantBeNoneException),
            ("invalid_prac_id", InvalidPractitionerIdException),
        ],
    )
    def test_validate_practitioner_id__invalid_practitioner_id(
        self,
        prac_id,
        exception,
        request,
        contract_validator,
    ):
        # Restore values from fixture
        prac_id = request.getfixturevalue(prac_id) if prac_id else None

        # Given
        contract_validator.practitioner_id = prac_id

        # Then
        with pytest.raises(exception):
            # When
            contract_validator.validate_practitioner_id()

    def test_validate_practitioner_id__valid_practitioner_id(
        self, contract_validator, practitioner_profile
    ):
        # Given
        contract_validator.practitioner_id = practitioner_profile.user_id

        # When
        contract_validator.validate_practitioner_id()

        # Then no exception is raised


class TestValidateCreatedByUserId:
    @pytest.mark.parametrize(
        argnames="created_by_user_id,exception",
        argvalues=[
            (None, CreatedByUserIdCantBeNoneException),
            ("invalid_user_id", InvalidCreatedByUserIdException),
        ],
    )
    def test_validate_created_by_user_id__invalid_created_by_user_id(
        self, created_by_user_id, exception, request, contract_validator
    ):
        # Restore values from fixture
        created_by_user_id = (
            request.getfixturevalue(created_by_user_id) if created_by_user_id else None
        )

        # Given
        contract_validator.created_by_user_id = created_by_user_id

        # Then
        with pytest.raises(exception):
            # When
            contract_validator.validate_created_by_user_id()

    def test_validate_created_by_user_id__valid_created_by_user_id(
        self, default_user, contract_validator
    ):
        # Given
        contract_validator.created_by_user_id = default_user.id

        # When
        contract_validator.validate_created_by_user_id()

        # Then no exception is raised


class TestValidateContractDetailsMatchContractType:
    @pytest.mark.parametrize(
        argnames="contract_type,exception,weekly_contracted_hours,fixed_hourly_rate,rate_per_overnight_appt,hourly_appointment_rate,non_standard_by_appointment_message_rate",
        argvalues=[
            (
                ContractType.BY_APPOINTMENT,
                WeeklyContractedHourNotNoneException,
                1,
                None,
                None,
                None,
                None,
            ),
            (
                ContractType.BY_APPOINTMENT,
                FixedHourlyRateNotNoneException,
                None,
                1,
                None,
                None,
                None,
            ),
            (
                ContractType.BY_APPOINTMENT,
                RatePerOvernightApptNotNoneException,
                None,
                None,
                1,
                None,
                None,
            ),
            (
                ContractType.BY_APPOINTMENT,
                HourlyAppointmentRateNotNoneException,
                None,
                None,
                None,
                1,
                None,
            ),
            (
                ContractType.BY_APPOINTMENT,
                NonStandardByAppointmentMessageRateNotNoneException,
                None,
                None,
                None,
                None,
                1,
            ),
            (
                ContractType.W2,
                WeeklyContractedHourNoneException,
                None,
                1,
                None,
                None,
                None,
            ),
            (ContractType.W2, FixedHourlyRateNoneException, 1, None, None, None, None),
            (
                ContractType.W2,
                RatePerOvernightApptNotNoneException,
                1,
                1,
                1,
                None,
                None,
            ),
            (
                ContractType.W2,
                HourlyAppointmentRateNotNoneException,
                1,
                1,
                None,
                1,
                None,
            ),
            (
                ContractType.W2,
                NonStandardByAppointmentMessageRateNotNoneException,
                1,
                1,
                None,
                None,
                1,
            ),
            (
                ContractType.FIXED_HOURLY,
                WeeklyContractedHourNoneException,
                None,
                1,
                None,
                None,
                None,
            ),
            (
                ContractType.FIXED_HOURLY,
                FixedHourlyRateNoneException,
                1,
                None,
                None,
                None,
                None,
            ),
            (
                ContractType.FIXED_HOURLY,
                RatePerOvernightApptNotNoneException,
                1,
                1,
                1,
                None,
                None,
            ),
            (
                ContractType.FIXED_HOURLY,
                HourlyAppointmentRateNotNoneException,
                1,
                1,
                None,
                1,
                None,
            ),
            (
                ContractType.FIXED_HOURLY,
                NonStandardByAppointmentMessageRateNotNoneException,
                1,
                1,
                None,
                None,
                1,
            ),
            (
                ContractType.FIXED_HOURLY_OVERNIGHT,
                WeeklyContractedHourNoneException,
                None,
                1,
                1,
                None,
                None,
            ),
            (
                ContractType.FIXED_HOURLY_OVERNIGHT,
                FixedHourlyRateNoneException,
                1,
                None,
                1,
                None,
                None,
            ),
            (
                ContractType.FIXED_HOURLY_OVERNIGHT,
                RatePerOvernightApptNoneException,
                1,
                1,
                None,
                None,
                None,
            ),
            (
                ContractType.FIXED_HOURLY_OVERNIGHT,
                HourlyAppointmentRateNotNoneException,
                1,
                1,
                1,
                1,
                None,
            ),
            (
                ContractType.FIXED_HOURLY_OVERNIGHT,
                NonStandardByAppointmentMessageRateNotNoneException,
                1,
                1,
                1,
                None,
                1,
            ),
            (
                ContractType.HYBRID_2_0,
                WeeklyContractedHourNoneException,
                None,
                1,
                None,
                1,
                None,
            ),
            (
                ContractType.HYBRID_2_0,
                FixedHourlyRateNoneException,
                1,
                None,
                None,
                1,
                None,
            ),
            (
                ContractType.HYBRID_2_0,
                HourlyAppointmentRateNoneException,
                1,
                1,
                None,
                None,
                None,
            ),
            (
                ContractType.HYBRID_2_0,
                RatePerOvernightApptNotNoneException,
                1,
                1,
                1,
                1,
                None,
            ),
            (
                ContractType.HYBRID_2_0,
                NonStandardByAppointmentMessageRateNotNoneException,
                1,
                1,
                None,
                1,
                1,
            ),
            (
                ContractType.HYBRID_1_0,
                WeeklyContractedHourNoneException,
                None,
                1,
                None,
                1,
                None,
            ),
            (
                ContractType.HYBRID_1_0,
                FixedHourlyRateNoneException,
                1,
                None,
                None,
                1,
                None,
            ),
            (
                ContractType.HYBRID_1_0,
                HourlyAppointmentRateNoneException,
                1,
                1,
                None,
                None,
                None,
            ),
            (
                ContractType.HYBRID_1_0,
                RatePerOvernightApptNotNoneException,
                1,
                1,
                1,
                1,
                None,
            ),
            (
                ContractType.HYBRID_1_0,
                NonStandardByAppointmentMessageRateNotNoneException,
                1,
                1,
                None,
                1,
                1,
            ),
            (
                ContractType.NON_STANDARD_BY_APPOINTMENT,
                HourlyAppointmentRateNoneException,
                None,
                None,
                None,
                None,
                1,
            ),
            (
                ContractType.NON_STANDARD_BY_APPOINTMENT,
                NonStandardByAppointmentMessageRateNoneException,
                None,
                None,
                None,
                1,
                None,
            ),
            (
                ContractType.NON_STANDARD_BY_APPOINTMENT,
                WeeklyContractedHourNotNoneException,
                1,
                None,
                None,
                1,
                1,
            ),
            (
                ContractType.NON_STANDARD_BY_APPOINTMENT,
                FixedHourlyRateNotNoneException,
                None,
                1,
                None,
                1,
                1,
            ),
            (
                ContractType.NON_STANDARD_BY_APPOINTMENT,
                RatePerOvernightApptNotNoneException,
                None,
                None,
                1,
                1,
                1,
            ),
        ],
    )
    def test_validate_contract_details_match_contract_type__wrong_contract_details_for_contract_type(
        self,
        contract_type,
        exception,
        weekly_contracted_hours,
        fixed_hourly_rate,
        rate_per_overnight_appt,
        hourly_appointment_rate,
        non_standard_by_appointment_message_rate,
        contract_validator,
    ):
        # Given
        contract_validator.contract_type = contract_type
        contract_validator.weekly_contracted_hours = weekly_contracted_hours
        contract_validator.fixed_hourly_rate = fixed_hourly_rate
        contract_validator.rate_per_overnight_appt = rate_per_overnight_appt
        contract_validator.hourly_appointment_rate = hourly_appointment_rate
        contract_validator.non_standard_by_appointment_message_rate = (
            non_standard_by_appointment_message_rate
        )
        # Then
        with pytest.raises(exception):
            # When
            contract_validator.validate_contract_details_match_contract_type()

    @pytest.mark.parametrize(
        argnames="contract_type,weekly_contracted_hours,fixed_hourly_rate,rate_per_overnight_appt,hourly_appointment_rate,non_standard_by_appointment_message_rate",
        argvalues=[
            (
                ContractType.BY_APPOINTMENT,
                None,
                None,
                None,
                None,
                None,
            ),
            (ContractType.NON_STANDARD_BY_APPOINTMENT, None, None, None, 1, 1),
            (ContractType.W2, 1, 1, None, None, None),
            (ContractType.FIXED_HOURLY, 1, 1, None, None, None),
            (
                ContractType.FIXED_HOURLY_OVERNIGHT,
                1,
                1,
                1,
                None,
                None,
            ),
            (ContractType.HYBRID_2_0, 1, 1, None, 1, None),
            (ContractType.HYBRID_1_0, 1, 1, None, 1, None),
        ],
    )
    def test_validate_contract_details_match_contract_type__correct_contract_details_for_contract_type(
        self,
        contract_type,
        weekly_contracted_hours,
        fixed_hourly_rate,
        rate_per_overnight_appt,
        hourly_appointment_rate,
        non_standard_by_appointment_message_rate,
        contract_validator,
    ):
        # Given
        contract_validator.contract_type = contract_type
        contract_validator.weekly_contracted_hours = weekly_contracted_hours
        contract_validator.fixed_hourly_rate = fixed_hourly_rate
        contract_validator.rate_per_overnight_appt = rate_per_overnight_appt
        contract_validator.hourly_appointment_rate = hourly_appointment_rate
        contract_validator.non_standard_by_appointment_message_rate = (
            non_standard_by_appointment_message_rate
        )

        # When
        contract_validator.validate_contract_details_match_contract_type()

        # No exceptions raised


class TestValidateContractDatesDoNotConflictWithExistingContracts:
    @pytest.mark.parametrize(
        argnames="existing_contract_start_date, existing_contract_end_date,new_contract_start_date,new_contract_end_date",
        argvalues=[
            # Conflict where both have no end date:
            # Existing contract: [start-
            # New contract:      [start-
            ("jan_1st_this_year", None, "jan_1st_this_year", None),
            # Existing contract: [start-
            # New contract:       [start-
            ("jan_1st_this_year", None, "feb_1st_this_year", None),
            # Existing contract:  [start-
            # New contract:      [start-
            ("feb_1st_this_year", None, "jan_1st_this_year", None),
            # Conflict when only existing has end date:
            # Existing contract:  [start-end]
            # New contract:       [start-
            ("jan_1st_this_year", "jan_31st_this_year", "jan_1st_this_year", None),
            # Existing contract:  [start-end]
            # New contract:        [start-
            ("jan_1st_this_year", "march_31st_this_year", "feb_1st_this_year", None),
            # Existing contract:  [start-end]
            # New contract:      [start-
            ("feb_1st_this_year", "march_31st_this_year", "jan_1st_this_year", None),
            # Conflict when only new contract has end date:
            # Existing contract:  [start-end]
            # New contract:       [start-
            ("jan_1st_this_year", None, "jan_1st_this_year", "jan_31st_this_year"),
            # Existing contract:  [start-
            # New contract:        [start-end]
            ("jan_1st_this_year", None, "feb_1st_this_year", "march_31st_this_year"),
            # Existing contract:  [start-
            # New contract:      [start-end]
            ("feb_1st_this_year", None, "jan_1st_this_year", "march_31st_this_year"),
            # Conflict when both have end date:
            # Existing contract:  [start-]
            # New contract:       [start-end]
            (
                "jan_1st_this_year",
                "jan_31st_this_year",
                "jan_1st_this_year",
                "jan_31st_this_year",
            ),
            # Existing contract:  [start-end]
            # New contract:      [start----end]
            (
                "feb_1st_this_year",
                "march_31st_this_year",
                "jan_1st_this_year",
                "apr_30th_this_year",
            ),
            # Existing contract:  [start---end]
            # New contract:        [start-end]
            (
                "jan_1st_this_year",
                "apr_30th_this_year",
                "feb_1st_this_year",
                "march_31st_this_year",
            ),
            # Existing contract:  [start-end]
            # New contract:        [start-end]
            (
                "jan_1st_this_year",
                "march_31st_this_year",
                "feb_1st_this_year",
                "apr_30th_this_year",
            ),
            # Existing contract:  [start-end]
            # New contract:      [start-end]
            (
                "feb_1st_this_year",
                "apr_30th_this_year",
                "jan_1st_this_year",
                "march_31st_this_year",
            ),
        ],
    )
    def test_validate_contract_dates_do_not_conflict_with_existing_contracts__contract_dates_conflict_with_existing_contract(
        self,
        new_contract_start_date,
        new_contract_end_date,
        existing_contract_start_date,
        existing_contract_end_date,
        request,
        contract_validator,
        practitioner_profile,
        practitioner_contract,
    ):

        # Restore values from fixture
        new_contract_start_date = request.getfixturevalue(new_contract_start_date)
        new_contract_end_date = (
            request.getfixturevalue(new_contract_end_date)
            if new_contract_end_date
            else None
        )

        existing_contract_start_date = request.getfixturevalue(
            existing_contract_start_date
        )

        existing_contract_end_date = (
            request.getfixturevalue(existing_contract_end_date)
            if existing_contract_end_date
            else None
        )

        # Given
        practitioner_contract.practitioner = practitioner_profile  # Existing contract should be associated to same practitioner we are creating the new contract for
        practitioner_contract.start_date = existing_contract_start_date
        practitioner_contract.end_date = existing_contract_end_date

        contract_validator.practitioner_id = practitioner_contract.practitioner_id
        contract_validator.start_date = new_contract_start_date
        contract_validator.end_date = new_contract_end_date

        # Then
        with pytest.raises(ConflictWithExistingContractException):
            # When
            contract_validator.validate_contract_dates_do_not_conflict_with_existing_contracts(
                existing_contracts=[practitioner_contract]
            )

    @pytest.mark.parametrize(
        argnames="existing_contract_start_date, existing_contract_end_date,new_contract_start_date,new_contract_end_date",
        argvalues=[
            # No conflict when existing has no end date:
            # Existing contract:                [start-
            # New contract:       [start-end]
            ("feb_1st_this_year", None, "jan_1st_this_year", "jan_31st_this_year"),
            # No conflict when new has no end date:
            # Existing contract:  [start-end]
            # New contract:                      [start-
            (
                "jan_1st_this_year",
                "jan_31st_this_year",
                "feb_1st_this_year",
                None,
            ),
            # No conflict when both have end dates:
            # Existing contract:  [start-end]
            # New contract:                     [start-end]
            (
                "jan_1st_this_year",
                "jan_31st_this_year",
                "feb_1st_this_year",
                "march_31st_this_year",
            ),
            # Existing contract:             [start-end]
            # New contract:      [start-end]
            (
                "feb_1st_this_year",
                "march_31st_this_year",
                "jan_1st_this_year",
                "jan_31st_this_year",
            ),
        ],
    )
    def test_validate_contract_dates_do_not_conflict_with_existing_contracts__contract_dates_do_not_conflict_with_existing_contract(
        self,
        new_contract_start_date,
        new_contract_end_date,
        existing_contract_start_date,
        existing_contract_end_date,
        request,
        contract_validator,
        practitioner_profile,
        practitioner_contract,
    ):
        # Restore values from fixture
        new_contract_start_date = request.getfixturevalue(new_contract_start_date)
        new_contract_end_date = (
            request.getfixturevalue(new_contract_end_date)
            if new_contract_end_date
            else None
        )
        existing_contract_start_date = request.getfixturevalue(
            existing_contract_start_date
        )
        existing_contract_end_date = (
            request.getfixturevalue(existing_contract_end_date)
            if existing_contract_end_date
            else None
        )

        # Given
        practitioner_contract.practitioner = practitioner_profile  # Existing contract should be associated to same practitioner we are creating the new contract for
        practitioner_contract.start_date = existing_contract_start_date
        practitioner_contract.end_date = existing_contract_end_date

        contract_validator.practitioner_id = practitioner_contract.practitioner_id
        contract_validator.start_date = new_contract_start_date
        contract_validator.end_date = new_contract_end_date

        # When
        contract_validator.validate_contract_dates_do_not_conflict_with_existing_contracts(
            existing_contracts=[practitioner_contract]
        )

        # We are asserting that no exception was raised so doing no explicit assert here


# TODO: Write unit_tests for validate_inputs_to_create_contract
