from unittest import mock

import pytest

from payments.models.contract_validator import (
    ConflictWithExistingContractException,
    CreatedByUserIdCantBeNoneException,
    EmitsFeesNotOppositeIsStaffException,
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
from payments.pytests.factories import PractitionerContractFactory
from payments.services.practitioner_contract import PractitionerContractService


class TestValidateInputsToCreateContract:
    def test_validate_inputs_to_create_contract__start_date_is_not_first_of_month(
        self, jan_2nd_this_year
    ):
        # Then
        with pytest.raises(StartDateNotFirstOfMonthException):
            # When
            PractitionerContractService().validate_inputs_to_create_contract(
                practitioner_id=None,
                created_by_user_id=None,
                contract_type_str=None,
                start_date=jan_2nd_this_year,
                end_date=None,
                weekly_contracted_hours=None,
                fixed_hourly_rate=None,
                rate_per_overnight_appt=None,
                hourly_appointment_rate=None,
                non_standard_by_appointment_message_rate=None,
            )

    def test_validate_inputs_to_create_contract__end_date_is_not_last_of_month(
        self, jan_1st_this_year, jan_2nd_this_year
    ):
        # Then
        with pytest.raises(EndDateNotEndOfMonthException):
            # When
            PractitionerContractService().validate_inputs_to_create_contract(
                practitioner_id=None,
                created_by_user_id=None,
                contract_type_str=None,
                start_date=jan_1st_this_year,
                end_date=jan_2nd_this_year,
                weekly_contracted_hours=None,
                fixed_hourly_rate=None,
                rate_per_overnight_appt=None,
                hourly_appointment_rate=None,
                non_standard_by_appointment_message_rate=None,
            )

    def test_validate_inputs_to_create_contract__end_date_is_before_start_date(
        self, feb_1st_this_year, jan_31st_this_year
    ):
        # Then
        with pytest.raises(EndDateBeforeStartDateException):
            # When
            PractitionerContractService().validate_inputs_to_create_contract(
                practitioner_id=None,
                created_by_user_id=None,
                contract_type_str=None,
                start_date=feb_1st_this_year,
                end_date=jan_31st_this_year,
                weekly_contracted_hours=None,
                fixed_hourly_rate=None,
                rate_per_overnight_appt=None,
                hourly_appointment_rate=None,
                non_standard_by_appointment_message_rate=None,
            )

    @pytest.mark.parametrize(
        argnames="prac_id,created_by_user_id,exception",
        argvalues=[
            (None, None, PractitionerIdCantBeNoneException),
            ("invalid_prac_id", None, InvalidPractitionerIdException),
            ("practitioner_id", None, CreatedByUserIdCantBeNoneException),
            ("practitioner_id", "invalid_user_id", InvalidCreatedByUserIdException),
            ("practitioner_id", "invalid_user_id", InvalidCreatedByUserIdException),
        ],
    )
    def test_validate_inputs_to_create_contract__invalid_user_ids(
        self,
        prac_id,
        created_by_user_id,
        exception,
        request,
        jan_1st_this_year,
        jan_31st_this_year,
    ):
        # Restore values from fixture
        prac_id = request.getfixturevalue(prac_id) if prac_id else None
        created_by_user_id = (
            request.getfixturevalue(created_by_user_id) if created_by_user_id else None
        )

        # Then
        with pytest.raises(exception):
            # When
            PractitionerContractService().validate_inputs_to_create_contract(
                practitioner_id=prac_id,
                created_by_user_id=created_by_user_id,
                contract_type_str=None,
                start_date=jan_1st_this_year,
                end_date=jan_31st_this_year,
                weekly_contracted_hours=None,
                fixed_hourly_rate=None,
                rate_per_overnight_appt=None,
                hourly_appointment_rate=None,
                non_standard_by_appointment_message_rate=None,
            )

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
    def test_validate_inputs_to_create_contract__wrong_contract_details_for_contract_type(
        self,
        weekly_contracted_hours,
        fixed_hourly_rate,
        rate_per_overnight_appt,
        hourly_appointment_rate,
        non_standard_by_appointment_message_rate,
        contract_type,
        exception,
        default_user,
        practitioner_profile,
        jan_1st_this_year,
        jan_31st_this_year,
    ):

        # Then
        with pytest.raises(exception):
            # When
            PractitionerContractService().validate_inputs_to_create_contract(
                practitioner_id=practitioner_profile.user_id,
                created_by_user_id=default_user.id,
                contract_type_str=contract_type.name,
                start_date=jan_1st_this_year,
                end_date=jan_31st_this_year,
                weekly_contracted_hours=weekly_contracted_hours,
                fixed_hourly_rate=fixed_hourly_rate,
                rate_per_overnight_appt=rate_per_overnight_appt,
                hourly_appointment_rate=hourly_appointment_rate,
                non_standard_by_appointment_message_rate=non_standard_by_appointment_message_rate,
            )

    @pytest.mark.parametrize(
        argnames="existing_contract_start_date, existing_contract_end_date,new_contract_start_date,new_contract_end_date",
        argvalues=[
            # Conflict where both have no end date:
            # Existing contract: [start -
            # New contract:      [start -
            ("jan_1st_this_year", None, "jan_1st_this_year", None),
            # Existing contract: [start -
            # New contract:       [start -
            ("jan_1st_this_year", None, "feb_1st_this_year", None),
            # Existing contract:  [start -
            # New contract:      [start -
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
            # Existing contract:  [start-
            # New contract:       [start-end]
            ("jan_1st_this_year", None, "jan_1st_this_year", "jan_31st_this_year"),
            # Existing contract:  [start-
            # New contract:        [start-end]
            ("jan_1st_this_year", None, "feb_1st_this_year", "march_31st_this_year"),
            # Existing contract:  [start-
            # New contract:      [start-end]
            ("feb_1st_this_year", None, "jan_1st_this_year", "march_31st_this_year"),
            # Conflict when both have end date:
            # Existing contract:  [start-end]
            # New contract:       [start-end]
            (
                "jan_1st_this_year",
                "jan_31st_this_year",
                "jan_1st_this_year",
                "jan_31st_this_year",
            ),
            # Existing contract:  [start-end]
            # New contract:      [start---end]
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
    def test_validate_inputs_to_create_contract__contract_dates_conflict_with_existing_contract(
        self,
        new_contract_start_date,
        new_contract_end_date,
        existing_contract_start_date,
        existing_contract_end_date,
        request,
        default_user,
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

        # Then
        with pytest.raises(ConflictWithExistingContractException):
            # When
            PractitionerContractService().validate_inputs_to_create_contract(
                practitioner_id=practitioner_profile.user_id,
                created_by_user_id=default_user.id,
                contract_type_str=ContractType.BY_APPOINTMENT.name,
                start_date=new_contract_start_date,
                end_date=new_contract_end_date,
                weekly_contracted_hours=None,
                fixed_hourly_rate=None,
                rate_per_overnight_appt=None,
                hourly_appointment_rate=None,
                non_standard_by_appointment_message_rate=None,
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
            # New contract:                     [start-
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
            # Existing contract:                [start-end]
            # New contract:      [start-end]
            (
                "feb_1st_this_year",
                "march_31st_this_year",
                "jan_1st_this_year",
                "jan_31st_this_year",
            ),
        ],
    )
    def test_validate_inputs_to_create_contract__contract_dates_do_not_conflict_with_existing_contract(
        self,
        new_contract_start_date,
        new_contract_end_date,
        existing_contract_start_date,
        existing_contract_end_date,
        request,
        default_user,
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

        # When
        PractitionerContractService().validate_inputs_to_create_contract(
            practitioner_id=practitioner_profile.user_id,
            created_by_user_id=default_user.id,
            contract_type_str=ContractType.BY_APPOINTMENT.name,
            start_date=new_contract_start_date,
            end_date=new_contract_end_date,
            weekly_contracted_hours=None,
            fixed_hourly_rate=None,
            rate_per_overnight_appt=None,
            hourly_appointment_rate=None,
            non_standard_by_appointment_message_rate=None,
        )

        # No explicit assert - we are asserting that no exception is raised


class TestValidateNewEndDate:
    def test_validate_new_end_date__end_date_is_not_last_of_month(
        self, practitioner_contract, jan_2nd_this_year
    ):
        # Then
        with pytest.raises(EndDateNotEndOfMonthException):
            # When
            PractitionerContractService().validate_new_end_date(
                contract=practitioner_contract, new_end_date=jan_2nd_this_year
            )

    def test_validate_new_end_date__end_date_is_before_start_date(
        self, practitioner_contract, feb_1st_this_year, jan_31st_this_year
    ):
        # Given
        practitioner_contract.start_date = feb_1st_this_year
        # Then
        with pytest.raises(EndDateBeforeStartDateException):
            # When
            PractitionerContractService().validate_new_end_date(
                contract=practitioner_contract, new_end_date=jan_31st_this_year
            )

    def test_validate_new_end_date__end_date_conflicts_with_existing_contract(
        self,
        factories,
        default_user,
        jan_1st_this_year,
        jan_31st_this_year,
        feb_1st_this_year,
        march_31st_this_year,
    ):
        # Given 2 contracts that do not conflict
        prac_profile = factories.PractitionerProfileFactory.create(user=default_user)

        practitioner_contract1 = PractitionerContractFactory.create(
            practitioner=prac_profile
        )
        practitioner_contract1.start_date = jan_1st_this_year
        practitioner_contract1.end_date = jan_31st_this_year

        practitioner_contract2 = PractitionerContractFactory.create(
            practitioner=prac_profile
        )
        practitioner_contract2.start_date = feb_1st_this_year
        practitioner_contract2.end_date = march_31st_this_year

        # Then
        with pytest.raises(ConflictWithExistingContractException):
            # When, I update the end_date of the first contract to intersect with the second contract
            PractitionerContractService().validate_new_end_date(
                contract=practitioner_contract1, new_end_date=march_31st_this_year
            )

    def test_validate_new_end_date__successfully_updated_end_date_conflicts_with_existing_contract(
        self,
        factories,
        default_user,
        jan_1st_this_year,
        jan_31st_this_year,
        march_31st_this_year,
        apr_1st_this_year,
        apr_30th_this_year,
    ):
        # Given 2 contracts that do not conflict
        prac_profile = factories.PractitionerProfileFactory.create(user=default_user)

        practitioner_contract1 = PractitionerContractFactory.create(
            practitioner=prac_profile
        )
        practitioner_contract1.start_date = jan_1st_this_year
        practitioner_contract1.end_date = jan_31st_this_year

        practitioner_contract2 = PractitionerContractFactory.create(
            practitioner=prac_profile
        )
        practitioner_contract2.start_date = apr_1st_this_year
        practitioner_contract2.end_date = apr_30th_this_year

        # When, I update the end_date of the first contract and dos not intersect with the second contract
        PractitionerContractService().validate_new_end_date(
            contract=practitioner_contract1, new_end_date=march_31st_this_year
        )

        # Then no exception is raised


class TestValidateEmitsFeesAgainstIsStaff:
    def test_validate_emits_fees__exception_raised(self, practitioner_profile):
        # Given a practitioner with is_staff True and contract_type BY APPOINTMENT
        practitioner_profile.is_staff = True
        # Assert raised
        with pytest.raises(EmitsFeesNotOppositeIsStaffException):
            # When
            PractitionerContractService().validate_emits_fees_against_is_staff(
                practitioner_id=practitioner_profile.user_id,
                contract_type="BY_APPOINTMENT",
            )

    def test_validate_emits_fees__success_by_appointment(self, practitioner_profile):
        # Given a practitioner with is_staff False and contract_type BY APPOINTMENT
        practitioner_profile.is_staff = False
        # When
        PractitionerContractService().validate_emits_fees_against_is_staff(
            practitioner_id=practitioner_profile.user_id, contract_type="BY_APPOINTMENT"
        )
        # Assert nothing raised

    def test_validate_emits_fees__success_not_by_appointment(
        self, practitioner_profile
    ):
        # Given a practitioner with is_staff True and contract_type not BY APPOINTMENT
        practitioner_profile.is_staff = True
        # When
        PractitionerContractService().validate_emits_fees_against_is_staff(
            practitioner_id=practitioner_profile.user_id, contract_type="HYBRID_2_0"
        )
        # Assert nothing raised


class TestExportDataToCsv:
    @mock.patch("payments.services.practitioner_contract.log.info")
    def test_export_data_to_csv__two_contracts(
        self, mock_log_info, factories, jan_2nd_this_year
    ):
        # Given - 2 valid contracts
        expected_contracts_count = 2
        practitioner_1 = factories.PractitionerUserFactory()
        PractitionerContractFactory.create(
            practitioner=practitioner_1.practitioner_profile,
            start_date=jan_2nd_this_year,
            contract_type=ContractType.W2,
        )
        practitioner_2 = factories.PractitionerUserFactory()
        PractitionerContractFactory.create(
            practitioner=practitioner_2.practitioner_profile,
            start_date=jan_2nd_this_year,
            contract_type=ContractType.NON_STANDARD_BY_APPOINTMENT,
        )

        # When - our method is called
        PractitionerContractService().export_data_to_csv()

        # Then - the correct logs are emitted
        assert mock_log_info.call_count == 2
        mock_log_info.assert_called_with(
            "Monthly provider contracts email - sent",
            contracts_count=expected_contracts_count,
        )

    @mock.patch("payments.services.practitioner_contract.log.info")
    def test_export_data_to_csv__no_contracts(
        self,
        mock_log_info,
    ):
        # Given - no contracts
        expected_contracts_count = 0

        # When - our method is called
        PractitionerContractService().export_data_to_csv()

        # Then - the correct logs are emitted
        assert mock_log_info.call_count == 2
        mock_log_info.assert_called_with(
            "Monthly provider contracts email - sent",
            contracts_count=expected_contracts_count,
        )

    @mock.patch("payments.services.practitioner_contract.log.info")
    def test_export_data_to_csv__two_contracts_one_exported(
        self, mock_log_info, factories, jan_2nd_this_year
    ):
        # Given - 1 valid contract, 1 by_appointment (not exported)
        expected_contracts_count = 1
        practitioner_1 = factories.PractitionerUserFactory()
        PractitionerContractFactory.create(
            practitioner=practitioner_1.practitioner_profile,
            start_date=jan_2nd_this_year,
            contract_type=ContractType.W2,
        )
        practitioner_2 = factories.PractitionerUserFactory()
        PractitionerContractFactory.create(
            practitioner=practitioner_2.practitioner_profile,
            start_date=jan_2nd_this_year,
            contract_type=ContractType.BY_APPOINTMENT,
        )

        # When - our method is called
        PractitionerContractService().export_data_to_csv()

        # Then - the correct logs are emitted
        assert mock_log_info.call_count == 2
        mock_log_info.assert_called_with(
            "Monthly provider contracts email - sent",
            contracts_count=expected_contracts_count,
        )
