import datetime
from unittest import mock

import pytest

from common.services.stripe import NoStripeAccountFoundException, StripeConnectClient
from common.services.stripe_constants import (
    PAYMENTS_STRIPE_API_KEY,
    STRIPE_ACTION_TYPES,
)
from pytests import stripe_fixtures as test_utils
from pytests.freezegun import freeze_time


@pytest.fixture
def practitioner_with_stripe(factories):
    user = factories.PractitionerUserFactory()
    user.practitioner_profile.stripe_account_id = test_utils.stripe_account_id
    return user


@pytest.fixture
def practitioner_without_stripe(factories):
    user = factories.PractitionerUserFactory()
    return user


class TestStripeConnectClient:
    @mock.patch.object(StripeConnectClient, "get_connect_account_for_user")
    def test_edit_connect_account_for_user__no_stripe_account(
        self,
        mock_get_connect_account,
        practitioner_without_stripe,
    ):
        # Given - a practitioner without stripe
        # When - We try to edit the stripe account
        mock_get_connect_account.return_value = None

        # Then - the correct exception occurs
        with pytest.raises(NoStripeAccountFoundException):
            stripe = StripeConnectClient(None)
            stripe.edit_connect_account_for_user(
                practitioner_without_stripe,
                None,
                None,
            )

    @mock.patch.object(StripeConnectClient, "get_connect_account_for_user")
    @mock.patch("stripe.Account.modify")
    def test_edit_connect_account_for_user__individual_account(
        self,
        mock_account_modify,
        mock_get_connect_account,
        practitioner_with_stripe,
    ):
        # Given - a practitioner with company-based stripe
        individual_legal_entity = {
            "dob": {"day": "06", "month": "08", "year": "1986"},
            "address": {
                "line1": "1234 Fake St",
                "city": "Brooklyn",
                "state": "NY",
                "postal_code": "11222",
            },
            "first_name": "Elizabeth",
            "last_name": "Blackwell",
            "ssn_last_4": "0000",
            "id_number": "000000000",
            "type": "individual",
        }
        company_legal_entity = None
        stripe_id = test_utils.verified_account.id

        # When - We edit the stripe account
        mock_get_connect_account.return_value = test_utils.verified_account
        stripe = StripeConnectClient(None)
        stripe.edit_connect_account_for_user(
            practitioner_with_stripe,
            individual_legal_entity,
            accept_tos_ip=None,
        )

        # Then - The update is called properly (individual not company)
        mock_account_modify.assert_called_with(
            stripe_id,
            individual=individual_legal_entity,
            company=company_legal_entity,
            tos_acceptance=None,
            api_key=PAYMENTS_STRIPE_API_KEY,
        )

    @mock.patch.object(StripeConnectClient, "get_connect_account_for_user")
    @mock.patch("stripe.Account.modify")
    def test_edit_connect_account_for_user__company_account(
        self,
        mock_account_modify,
        mock_get_connect_account,
        practitioner_with_stripe,
    ):
        # Given - a practitioner with company-based stripe
        company_legal_entity = {
            "address": {
                "line1": "1234 Fake St",
                "city": "Brooklyn",
                "state": "NY",
                "postal_code": "11222",
            },
            "id_number": "000000000",
            "type": "company",
            "name": "Test Company",
            "tax_id": "TEST0001",
        }
        individual_legal_entity = None
        stripe_id = test_utils.stripe_business_practitioner_account.id

        # When - We edit the stripe account
        mock_get_connect_account.return_value = (
            test_utils.stripe_business_practitioner_account
        )
        stripe = StripeConnectClient(None)
        stripe.edit_connect_account_for_user(
            practitioner_with_stripe,
            company_legal_entity,
            accept_tos_ip=None,
        )

        # Then - The update is called properly  (company not individual)
        mock_account_modify.assert_called_with(
            stripe_id,
            individual=individual_legal_entity,
            company=company_legal_entity,
            tos_acceptance=None,
            api_key=PAYMENTS_STRIPE_API_KEY,
        )

    @mock.patch.object(StripeConnectClient, "get_connect_account_for_user")
    @mock.patch("stripe.Account.modify")
    def test_edit_connect_account_for_user__accept_tos(
        self,
        mock_account_modify,
        mock_get_connect_account,
        practitioner_with_stripe,
    ):
        utcnow = datetime.datetime.utcnow()
        with freeze_time(utcnow):
            # Given - IP address passed to accept terms of service
            accept_tos_ip = "1.2.3.4"
            legal_entity = {
                "address": {
                    "line1": "1234 Fake St",
                    "city": "Brooklyn",
                    "state": "NY",
                    "postal_code": "11222",
                },
                "id_number": "000000000",
                "type": "company",
                "name": "Test Company",
                "tax_id": "TEST0001",
            }

            # When - We edit the stripe account
            stripe = StripeConnectClient(None)
            mock_get_connect_account.return_value = (
                test_utils.stripe_business_practitioner_account
            )
            stripe.edit_connect_account_for_user(
                practitioner_with_stripe,
                legal_entity,
                accept_tos_ip=accept_tos_ip,
            )

            # Then - update is called with new terms-of-service
            tos_acceptance = {
                "date": int(utcnow.timestamp()),
                "ip": accept_tos_ip,
                "user_agent": None,
            }
            mock_account_modify.assert_called_with(
                test_utils.stripe_business_practitioner_account.id,
                individual=None,
                company=legal_entity,
                tos_acceptance=tos_acceptance,
                api_key=PAYMENTS_STRIPE_API_KEY,
            )

    @mock.patch("common.services.stripe.log.info")
    def test_audit_logging(self, mock_log_info):
        # given
        given_action_type = STRIPE_ACTION_TYPES.card_creation_failed
        expected_call_args = mock.call(
            mock.ANY,
            audit_log_info={
                "user_id": None,
                "action_type": given_action_type,
                "action_target_type": "stripe",
                "modified_fields": [],
            },
        )
        # when
        StripeConnectClient.audit(STRIPE_ACTION_TYPES.card_creation_failed)

        # then
        assert mock_log_info.call_args == expected_call_args
