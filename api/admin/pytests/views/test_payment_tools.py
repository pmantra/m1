from unittest import mock
from unittest.mock import call

from admin.views.models.payments import MonthlyPaymentsView
from common.services.stripe import StripeConnectClient
from payments.models.constants import PROVIDER_PAYMENTS_EMAIL
from pytests.stripe_fixtures import verified_account


class TestPaymentToolsStartInvoiceTransfer:
    def test_payment_tools_start_invoice_transfer__fee_hash_code_empty(
        self, admin_client
    ):
        """
        This case shouldn't be allowed by the actual UI
        """
        with mock.patch("admin.blueprints.actions.flash") as flash:
            res = admin_client.post(
                "/admin/actions/start_invoice_transfers", data={"fee_hash": ""}
            )
        assert res.status_code == 302
        assert res.location == "/admin/payment_tools"
        assert flash.call_count == 1
        assert flash.call_args == call(
            "No fee hash code provided, please start transfers manually if required",
            category="error",
        )

    def test_payment_tools_start_invoice_transfer__fee_hash_code_provided(
        self, admin_client
    ):
        """
        Any fee hash code is accepted at this stage.
        """
        with mock.patch("admin.blueprints.actions.flash") as flash, mock.patch(
            "admin.blueprints.actions.start_invoice_transfers_job"
        ) as job:
            res = admin_client.post(
                "/admin/actions/start_invoice_transfers",
                data={"fee_hash": "abc123"},
            )
        assert res.status_code == 302
        assert res.location == "/admin/payment_tools"
        assert job.delay.call_count == 1
        assert flash.call_count == 1
        assert flash.call_args == call(
            "The Invoice Transfer job has been scheduled, a notification will be sent to {} when started and completed.",
            format(PROVIDER_PAYMENTS_EMAIL),
        )

    def test_accept_tos_post(self, admin_client, factories):
        practitioner = factories.PractitionerUserFactory.create()
        with mock.patch.object(
            StripeConnectClient, "get_connect_account_for_user"
        ) as get_acct, mock.patch.object(
            StripeConnectClient, "accept_terms_of_service"
        ) as accept_tos:
            res = admin_client.post(
                "/admin/monthly_payments/sign_stripe_tos",
                data={"practitioner_id": practitioner.id},
            )
            assert res.status_code == 302
            assert res.location == "/admin/practitioner_tools"
            assert get_acct.call_count == 1
            assert accept_tos.call_count == 1

    def test_accept_tos_post_no_tos_mock(self, admin_client, factories):
        practitioner = factories.PractitionerUserFactory.create()
        # TODO: when clearing out the final legacy tests, move the verified account fixture import
        with mock.patch.object(
            StripeConnectClient,
            "get_connect_account_for_user",
            return_value=verified_account,
        ):
            res = admin_client.post(
                "/admin/monthly_payments/sign_stripe_tos",
                data={"practitioner_id": practitioner.id},
            )
            assert res.status_code == 500

    def test_accept_tos(self, factories):
        mock_ip = "172.17.0.1"
        mpv = MonthlyPaymentsView()
        mpv.get_client_ip = mock.Mock(return_value=mock_ip)
        practitioner = factories.PractitionerUserFactory.create()
        with mock.patch.object(
            StripeConnectClient, "get_connect_account_for_user"
        ), mock.patch.object(
            StripeConnectClient, "accept_terms_of_service"
        ) as accept_tos:
            mpv.sign_stripe_tos_with_user_id(practitioner.id)
            # prev version of this test asserted that a mocked value was returned successfully
            # this is a *slightly* more useful assertion
            assert call(practitioner, mock_ip) == accept_tos.call_args
