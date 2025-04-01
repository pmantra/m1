import datetime
from unittest import mock

import pytest
from dateutil.relativedelta import relativedelta

from payments.models.constants import PROVIDER_CONTRACTS_EMAIL
from payments.models.practitioner_contract import ContractType
from payments.pytests.factories import PractitionerContractFactory
from payments.services.practitioner_contract import PractitionerContractService


@pytest.fixture
def practitioner_1(factories):
    return factories.PractitionerUserFactory()


@pytest.fixture
def practitioner_2(factories):
    return factories.PractitionerUserFactory()


@pytest.fixture
def prac_hourly_contract(factories):
    prac = factories.PractitionerUserFactory()
    return PractitionerContractFactory.create(
        practitioner=prac.practitioner_profile,
        start_date=datetime.date.today() - relativedelta(months=1),
        end_date=datetime.date.today() + relativedelta(months=1),
        contract_type=ContractType.FIXED_HOURLY,
        fixed_hourly_rate=1,
        weekly_contracted_hours=2,
        rate_per_overnight_appt=3,
        hourly_appointment_rate=4,
        non_standard_by_appointment_message_rate=5,
    )


@pytest.fixture
def prac_hybrid_contract(factories):
    prac = factories.PractitionerUserFactory()
    return PractitionerContractFactory.create(
        practitioner=prac.practitioner_profile,
        start_date=datetime.date.today() - relativedelta(months=2),
        # No end date
        contract_type=ContractType.HYBRID_1_0,
        fixed_hourly_rate=6,
        weekly_contracted_hours=7,
        rate_per_overnight_appt=8,
        hourly_appointment_rate=9,
        non_standard_by_appointment_message_rate=10,
    )


@pytest.fixture
def today():
    return datetime.date.today()


class TestPractitionerContractServiceExportDataToCsv:
    @mock.patch("payments.services.practitioner_contract.send_message")
    @mock.patch(
        "payments.services.practitioner_contract.PractitionerContractService._generate_csv_data"
    )
    def test_export_data_to_csv__one_contract_no_by_appt(
        self,
        mock__generate_csv_data,
        mock_send_message,
        today,
        practitioner_1,
        practitioner_2,
    ):

        # Given - one valid contract to export and one by appt contract (which are not exported)
        valid_contract = PractitionerContractFactory.create(
            practitioner=practitioner_1.practitioner_profile,
            start_date=today,
            contract_type=ContractType.HYBRID_2_0,
        )
        PractitionerContractFactory.create(
            practitioner=practitioner_2.practitioner_profile,
            start_date=today,
            contract_type=ContractType.BY_APPOINTMENT,
        )

        # Mock the return of _generate_csv_data
        csv_filename = "provider-contracts.csv"
        mocked_return_of_generate_csv_data = []
        mock__generate_csv_data.return_value = mocked_return_of_generate_csv_data

        # When - we run the export
        PractitionerContractService().export_data_to_csv()

        # Then - only the valid contract is passed
        mock__generate_csv_data.assert_called_with([valid_contract])

        # And send_message is called
        mock_send_message.assert_called_once_with(
            to_email=PROVIDER_CONTRACTS_EMAIL,
            subject=mock.ANY,
            html="The monthly provider contract csv file is attached",
            internal_alert=True,
            production_only=True,
            csv_attachments=[(csv_filename, mocked_return_of_generate_csv_data)],
        )

    @mock.patch("payments.services.practitioner_contract.send_message")
    @mock.patch(
        "payments.services.practitioner_contract.PractitionerContractService._generate_csv_data"
    )
    def test_export_data_to_csv__three_contracts(
        self,
        mock__generate_csv_data,
        mock_send_message,
        today,
        practitioner_1,
        practitioner_2,
    ):

        # Given - three valid contracts, some active some expired
        valid_contracts = []
        valid_contracts.append(
            PractitionerContractFactory.create(
                practitioner=practitioner_1.practitioner_profile,
                start_date=today,
                contract_type=ContractType.HYBRID_2_0,
            )
        )
        valid_contracts.append(
            PractitionerContractFactory.create(
                practitioner=practitioner_2.practitioner_profile,
                start_date=today - relativedelta(year=1),
                end_date=today - relativedelta(day=1),
                contract_type=ContractType.FIXED_HOURLY,
            )
        )
        valid_contracts.append(
            PractitionerContractFactory.create(
                practitioner=practitioner_2.practitioner_profile,
                start_date=today,
                contract_type=ContractType.HYBRID_2_0,
            )
        )

        # Mock the return of _generate_csv_data
        csv_filename = "provider-contracts.csv"
        mocked_return_of_generate_csv_data = []
        mock__generate_csv_data.return_value = mocked_return_of_generate_csv_data

        # When - we run the export
        PractitionerContractService().export_data_to_csv()

        # Then - all contracts are passed
        mock__generate_csv_data.assert_called_with(valid_contracts)

        # And send_message is called
        mock_send_message.assert_called_once_with(
            to_email=PROVIDER_CONTRACTS_EMAIL,
            subject=mock.ANY,
            html="The monthly provider contract csv file is attached",
            internal_alert=True,
            production_only=True,
            csv_attachments=[(csv_filename, mocked_return_of_generate_csv_data)],
        )


class TestPractitionerContractServiceGenerateCsvData:
    def test__generate_csv_data__headers_only(
        self,
    ):
        # Given - we don't have any contracts, just the headers
        contracts = []
        expected_csv_data = '"practitioner_id","practitioner_name","practitioner_email","dcw_start_date","dcw_end_date","payment_type","dcw_hourly_rate","dcw_weekly_hours","dcw_by_appt_rate","dcw_by_appt_hourly","dcw_by_appt_msg"\r\n'

        # When - we generate the csv data
        csv_data = PractitionerContractService()._generate_csv_data(contracts)

        # Then - the headers are returned and match
        assert csv_data == expected_csv_data

    def test__generate_csv_data__one_contract(
        self,
        prac_hourly_contract,
    ):
        # Given - we add 1 contract
        prac_hourly_contract_payment_type = "dcw_hourly"
        prac_hourly_contract_user = prac_hourly_contract.practitioner.user
        expected_csv_data = (
            '"practitioner_id","practitioner_name","practitioner_email","dcw_start_date","dcw_end_date","payment_type","dcw_hourly_rate","dcw_weekly_hours","dcw_by_appt_rate","dcw_by_appt_hourly","dcw_by_appt_msg"\r\n'
            + f'{prac_hourly_contract_user.id},"{prac_hourly_contract_user.full_name}","{prac_hourly_contract_user.email}","{prac_hourly_contract.start_date}","{prac_hourly_contract.end_date}","{prac_hourly_contract_payment_type}",{prac_hourly_contract.fixed_hourly_rate},{prac_hourly_contract.weekly_contracted_hours},{prac_hourly_contract.rate_per_overnight_appt},{prac_hourly_contract.hourly_appointment_rate},{prac_hourly_contract.non_standard_by_appointment_message_rate}\r\n'
        )

        # When - we generate the csv data
        csv_data = PractitionerContractService()._generate_csv_data(
            [prac_hourly_contract]
        )

        # Then - the results match our expected results
        assert csv_data == expected_csv_data

    def test__generate_csv_data__two_contracts(
        self,
        prac_hourly_contract,
        prac_hybrid_contract,
    ):
        # Given - we add 2 contracts
        prac_hourly_contract_payment_type = "dcw_hourly"
        prac_hourly_contract_user = prac_hourly_contract.practitioner.user
        prac_hybrid_contract_payment_type = "hybrid"
        prac_hybrid_contract_user = prac_hybrid_contract.practitioner.user

        expected_csv_data = (
            '"practitioner_id","practitioner_name","practitioner_email","dcw_start_date","dcw_end_date","payment_type","dcw_hourly_rate","dcw_weekly_hours","dcw_by_appt_rate","dcw_by_appt_hourly","dcw_by_appt_msg"\r\n'
            + f'{prac_hourly_contract_user.id},"{prac_hourly_contract_user.full_name}","{prac_hourly_contract_user.email}","{prac_hourly_contract.start_date}","{prac_hourly_contract.end_date}","{prac_hourly_contract_payment_type}",{prac_hourly_contract.fixed_hourly_rate},{prac_hourly_contract.weekly_contracted_hours},{prac_hourly_contract.rate_per_overnight_appt},{prac_hourly_contract.hourly_appointment_rate},{prac_hourly_contract.non_standard_by_appointment_message_rate}\r\n'
            + f'{prac_hybrid_contract_user.id},"{prac_hybrid_contract_user.full_name}","{prac_hybrid_contract_user.email}","{prac_hybrid_contract.start_date}","","{prac_hybrid_contract_payment_type}",{prac_hybrid_contract.fixed_hourly_rate},{prac_hybrid_contract.weekly_contracted_hours},{prac_hybrid_contract.rate_per_overnight_appt},{prac_hybrid_contract.hourly_appointment_rate},{prac_hybrid_contract.non_standard_by_appointment_message_rate}\r\n'
        )

        # When - we generate the csv data
        csv_data = PractitionerContractService()._generate_csv_data(
            [prac_hourly_contract, prac_hybrid_contract]
        )

        # Then - the results match our expected results
        assert csv_data == expected_csv_data


class TestPractitionerContractServiceContractTypeToPaymentType:
    @pytest.mark.parametrize(
        "types",
        [
            (ContractType.FIXED_HOURLY, "dcw_hourly"),
            (ContractType.FIXED_HOURLY_OVERNIGHT, "dcw_both"),
            (ContractType.HYBRID_1_0, "hybrid"),
            (ContractType.HYBRID_2_0, "hybrid_20"),
            (ContractType.W2, "w2"),
            (ContractType.NON_STANDARD_BY_APPOINTMENT, "dcw_by_appt"),
        ],
    )
    def test__contract_type_to_payment_type__valid(
        self,
        types,
    ):
        # Given - A valid contract_type and payment_type pair
        contract_type, payment_type = types

        # When - we pass the contract type
        result = PractitionerContractService()._contract_type_to_payment_type(
            contract_type
        )

        # Then - the result matches the payment type
        assert result == payment_type

    @pytest.mark.parametrize("contract_type", [ContractType.BY_APPOINTMENT, None])
    def test__contract_type_to_payment_type__invalid(
        self,
        contract_type,
    ):
        # Given - An invalid contract_type

        # When - we pass the contract type
        result = PractitionerContractService()._contract_type_to_payment_type(
            contract_type
        )

        # Then - we get nothing back
        assert result is None
