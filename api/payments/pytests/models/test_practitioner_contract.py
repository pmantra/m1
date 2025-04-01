import datetime

import pytest

from models.profiles import PractitionerProfile
from payments.models.practitioner_contract import ContractType, PractitionerContract
from payments.pytests.factories import PractitionerContractFactory
from storage.connection import db


class TestPractitionerContract:
    def test_active_property__active_with_start_date(
        self, practitioner_contract, yesterday
    ):
        # Given
        practitioner_contract.start_date = yesterday
        # Then
        assert practitioner_contract.active

    def test_active_property__active_with_start_and_end_date(
        self, practitioner_contract, yesterday, tomorrow
    ):
        # Given
        practitioner_contract.start_date = yesterday
        practitioner_contract.end_date = tomorrow
        # Then
        assert practitioner_contract.active

    def test_active_property__inactive_with_only_start_date(
        self, practitioner_contract, tomorrow
    ):
        # Given
        practitioner_contract.start_date = tomorrow
        # Then
        assert not practitioner_contract.active

    def test_active_property__inactive_with_start_and_end_date_in_past(
        self, practitioner_contract, yesterday
    ):
        # Given
        practitioner_contract.start_date = yesterday
        practitioner_contract.end_date = yesterday
        # Then
        assert not practitioner_contract.active

    def test_active_property__inactive_with_start_and_end_date_in_future(
        self, practitioner_contract, tomorrow
    ):
        # Given
        practitioner_contract.start_date = tomorrow
        practitioner_contract.end_date = tomorrow
        # Then
        assert not practitioner_contract.active

    def test_active_property__active_hybrid_property_can_be_used_in_sql(
        self, practitioner_contract, yesterday
    ):
        # Given
        practitioner_contract.start_date = yesterday
        # When
        pc = (
            db.session.query(PractitionerContract)
            .filter(PractitionerContract.active == True)
            .first()
        )
        # Then
        assert pc is not None

    def test_emits_fees__by_appointment(self, practitioner_contract):
        # Given
        practitioner_contract.contract_type = ContractType.BY_APPOINTMENT
        # Then
        assert practitioner_contract.emits_fees is True

    @pytest.mark.parametrize(
        argnames="contract_type",
        argvalues=[
            ContractType.FIXED_HOURLY,
            ContractType.FIXED_HOURLY_OVERNIGHT,
            ContractType.HYBRID_2_0,
            ContractType.W2,
        ],
    )
    def test_emits_fees__not_by_appointment(self, practitioner_contract, contract_type):
        # Given
        practitioner_contract.contract_type = contract_type
        # Then
        assert practitioner_contract.emits_fees is False

    @pytest.mark.parametrize(
        argnames="contract_type, expected_emits_fee",
        argvalues=[
            (ContractType.FIXED_HOURLY, False),
            (ContractType.FIXED_HOURLY_OVERNIGHT, False),
            (ContractType.HYBRID_2_0, False),
            (ContractType.W2, False),
            (ContractType.BY_APPOINTMENT, True),
        ],
    )
    def test_active_property__emits_fees_hybrid_property_can_be_used_in_sql(
        self, practitioner_contract, contract_type, expected_emits_fee
    ):
        # Given
        practitioner_contract.contract_type = contract_type
        # When
        pc = (
            db.session.query(PractitionerContract)
            .filter(PractitionerContract.emits_fees == expected_emits_fee)
            .first()
        )
        # Then
        assert pc is not None


class TestPractitionerProfile:
    def test_practitioner_profile_active_contract__active_contract_exists(
        self,
        practitioner_profile,
    ):
        # Given - we have a practitioner with 3 contracts, 1 active
        today = datetime.date.today()

        # Previous contract
        start_date_50_days_ago = today - datetime.timedelta(days=50)
        end_date_20_days_ago = today - datetime.timedelta(days=20)
        PractitionerContractFactory.create(
            practitioner=practitioner_profile,
            start_date=start_date_50_days_ago,
            end_date=end_date_20_days_ago,
        )

        # Current contract
        start_date_19_days_ago = today - datetime.timedelta(days=19)
        end_date_10_days = today + datetime.timedelta(days=10)
        current_contract = PractitionerContractFactory.create(
            practitioner=practitioner_profile,
            start_date=start_date_19_days_ago,
            end_date=end_date_10_days,
        )

        # Future contract
        start_date_19_days_ago = today + datetime.timedelta(days=11)
        end_date_no_date = None
        PractitionerContractFactory.create(
            practitioner=practitioner_profile,
            start_date=start_date_19_days_ago,
            end_date=end_date_no_date,
        )

        # When - we query the active_contract
        active_contract = PractitionerProfile.query.get(
            practitioner_profile.user_id
        ).active_contract

        # Then - the correct contract is returned
        assert current_contract.id == active_contract.id

    def test_practitioner_profile_active_contract__no_contract(
        self,
        practitioner_profile,
    ):
        # Given - we have a practitioner with no contract
        # When - we query the active_contract
        active_contract = PractitionerProfile.query.get(
            practitioner_profile.user_id
        ).active_contract

        # Then - no contract is returned
        assert active_contract is None
