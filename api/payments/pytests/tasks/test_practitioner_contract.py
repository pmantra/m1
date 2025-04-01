import datetime
from unittest import mock

from models.verticals_and_specialties import CX_VERTICAL_NAME
from payments.models.constants import PROVIDER_CONTRACTS_EMAIL
from payments.pytests.factories import PractitionerContractFactory
from payments.services.practitioner_contract import PractitionerContractService
from payments.tasks.practitioner_contract import (
    export_practitioner_contracts,
    report_missing_or_expiring_contracts,
)


class TestExportPractitionerContracts:
    @mock.patch.object(PractitionerContractService, "export_data_to_csv")
    def test_export_data_to_csv_called(self, mock_export_data_to_csv):
        # When - we call export_practitioner_contracts
        export_practitioner_contracts()
        # Then - the class method is called
        mock_export_data_to_csv.assert_called_once()


class TestReportMissingOrExpiringContracts:
    @mock.patch("payments.tasks.practitioner_contract.send_message")
    def test_report_missing_or_expiring_contracts__none(
        self, mock_send_message, factories
    ):
        # Given - no qualifying practitioners or contracts
        ca_practitioner = factories.PractitionerUserFactory()
        ca_vertical = factories.VerticalFactory(name=CX_VERTICAL_NAME)
        ca_practitioner.practitioner_profile.verticals = [ca_vertical]
        inactive_practitioner = factories.PractitionerUserFactory()
        inactive_practitioner.practitioner_profile.active = False

        # When - we process report_missing_or_expiring_contracts
        report_missing_or_expiring_contracts()

        # Then - no report is sent
        mock_send_message.assert_not_called()

    @mock.patch("payments.tasks.practitioner_contract.send_message")
    def test_report_missing_or_expiring_contracts__no_end_date(
        self, mock_send_message, factories
    ):
        # Given - a contract with no end date
        practitioner = factories.PractitionerUserFactory()
        practitioner.practitioner_profile.verticals = [factories.VerticalFactory()]
        PractitionerContractFactory.create(
            practitioner=practitioner.practitioner_profile,
            start_date=datetime.date.today() - datetime.timedelta(days=30),
        )

        # When - we process report_missing_or_expiring_contracts
        report_missing_or_expiring_contracts()

        # Then - no report is sent
        mock_send_message.assert_not_called()

    @mock.patch("payments.tasks.practitioner_contract.send_message")
    def test_report_missing_or_expiring_contracts__future_end_date(
        self, mock_send_message, factories
    ):
        # Given - a contract with an end date farther in the future
        practitioner = factories.PractitionerUserFactory()
        practitioner.practitioner_profile.verticals = [factories.VerticalFactory()]
        PractitionerContractFactory.create(
            practitioner=practitioner.practitioner_profile,
            start_date=datetime.date.today() - datetime.timedelta(days=30),
            end_date=datetime.date.today() + datetime.timedelta(days=30),
        )

        # When - we process report_missing_or_expiring_contracts
        report_missing_or_expiring_contracts()

        # Then - no report is sent
        mock_send_message.assert_not_called()

    @mock.patch("payments.tasks.practitioner_contract.send_message")
    def test_report_missing_or_expiring_contracts__replacement_contract(
        self, mock_send_message, factories
    ):
        # Given - an expiring contract with a replacement
        practitioner = factories.PractitionerUserFactory()
        practitioner.practitioner_profile.verticals = [factories.VerticalFactory()]
        PractitionerContractFactory.create(
            practitioner=practitioner.practitioner_profile,
            start_date=datetime.date.today() - datetime.timedelta(days=30),
            end_date=datetime.date.today() + datetime.timedelta(days=2),
        )
        PractitionerContractFactory.create(
            practitioner=practitioner.practitioner_profile,
            start_date=datetime.date.today() + datetime.timedelta(days=3),
        )

        # When - we process report_missing_or_expiring_contracts
        report_missing_or_expiring_contracts()

        # Then - no report is sent
        mock_send_message.assert_not_called()

    @mock.patch("payments.tasks.practitioner_contract.send_message")
    def test_report_missing_or_expiring_contracts__missing_contract(
        self, mock_send_message, factories
    ):
        # Given - a practitioner without contract
        practitioner = factories.PractitionerUserFactory()
        practitioner.practitioner_profile.verticals = [factories.VerticalFactory()]

        # When - we process report_missing_or_expiring_contracts
        report_missing_or_expiring_contracts()

        # Then - report is sent with missing contract
        expected_report_text = (
            f"The following providers have no active contract: {[practitioner.id]}"
        )
        mock_send_message.assert_called_with(
            to_email=PROVIDER_CONTRACTS_EMAIL,
            subject="Providers with missing contracts",
            text=expected_report_text,
            internal_alert=True,
            production_only=True,
        )

    @mock.patch("payments.tasks.practitioner_contract.send_message")
    def test_report_missing_or_expiring_contracts__expiring_contract(
        self, mock_send_message, factories
    ):
        # Given - an expiring contract without a replacement
        practitioner = factories.PractitionerUserFactory()
        practitioner.practitioner_profile.verticals = [factories.VerticalFactory()]
        PractitionerContractFactory.create(
            practitioner=practitioner.practitioner_profile,
            start_date=datetime.date.today() - datetime.timedelta(days=30),
            end_date=datetime.date.today() + datetime.timedelta(days=2),
        )

        # When - we process report_missing_or_expiring_contracts
        report_missing_or_expiring_contracts()

        # Then - report is sent with expiring contract
        expected_report_text = f"The following providers have contracts that will expire soon: {[practitioner.id]}"
        mock_send_message.assert_called_with(
            to_email=PROVIDER_CONTRACTS_EMAIL,
            subject="Providers with expiring contracts",
            text=expected_report_text,
            internal_alert=True,
            production_only=True,
        )

    @mock.patch("payments.tasks.practitioner_contract.send_message")
    def test_report_missing_or_expiring_contracts__gap_after_expiring_contract(
        self, mock_send_message, factories
    ):
        # Given - a gap between the old and new contract
        practitioner = factories.PractitionerUserFactory()
        practitioner.practitioner_profile.verticals = [factories.VerticalFactory()]
        PractitionerContractFactory.create(
            practitioner=practitioner.practitioner_profile,
            start_date=datetime.date.today() - datetime.timedelta(days=30),
            end_date=datetime.date.today() + datetime.timedelta(days=2),
        )
        PractitionerContractFactory.create(
            practitioner=practitioner.practitioner_profile,
            start_date=datetime.date.today() + datetime.timedelta(days=5),
            end_date=datetime.date.today() + datetime.timedelta(days=60),
        )

        # When - we process report_missing_or_expiring_contracts
        report_missing_or_expiring_contracts()

        # Then - report is sent with expiring contract
        expected_report_text = f"The following providers have contracts that will expire soon: {[practitioner.id]}"
        mock_send_message.assert_called_with(
            to_email=PROVIDER_CONTRACTS_EMAIL,
            subject="Providers with expiring contracts",
            text=expected_report_text,
            internal_alert=True,
            production_only=True,
        )

    @mock.patch("payments.tasks.practitioner_contract.send_message")
    def test_report_missing_or_expiring_contracts__missing_and_expiring_contract(
        self, mock_send_message, factories
    ):
        # Given - a practitioner without contract
        practitioner_1 = factories.PractitionerUserFactory()
        practitioner_1.practitioner_profile.verticals = [factories.VerticalFactory()]

        # And a practitioner with expiring contract without a replacement
        practitioner_2 = factories.PractitionerUserFactory()
        practitioner_2.practitioner_profile.verticals = [factories.VerticalFactory()]
        PractitionerContractFactory.create(
            practitioner=practitioner_2.practitioner_profile,
            start_date=datetime.date.today() - datetime.timedelta(days=30),
            end_date=datetime.date.today() + datetime.timedelta(days=2),
        )

        # When - we process report_missing_or_expiring_contracts
        report_missing_or_expiring_contracts()

        # Then - report is sent with missing contract
        expected_report_text_1 = (
            f"The following providers have no active contract: {[practitioner_1.id]}"
        )
        expected_report_text_2 = f"The following providers have contracts that will expire soon: {[practitioner_2.id]}"
        expected_report_text = expected_report_text_1 + "\n" + expected_report_text_2
        mock_send_message.assert_called_with(
            to_email=PROVIDER_CONTRACTS_EMAIL,
            subject="Providers with missing and expiring contracts",
            text=expected_report_text,
            internal_alert=True,
            production_only=True,
        )
