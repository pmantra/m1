import datetime
from unittest import mock

import pytest
from stripe.api_resources.abstract.createable_api_resource import CreateableAPIResource

from admin.views.base import AdminCategory
from admin.views.models.payments import InvoiceView
from appointments.models.payments import StartTransferErrorMsg
from tasks.payments import PROVIDER_PAYMENTS_EMAIL, start_invoices


@pytest.fixture
def invoice_with_no_entries(factories):
    invoice = factories.InvoiceFactory()
    return invoice


@pytest.fixture
def invoice_with_no_recipients(factories):
    invoice = factories.InvoiceFactory.create()
    fee_accounting_entry = factories.FeeAccountingEntryFactory.create()
    invoice.entries = [fee_accounting_entry]
    return invoice


@pytest.fixture
def invoice_with_recipient(factories):
    invoice = factories.InvoiceFactory.create()
    fee_accounting_entry = factories.FeeAccountingEntryFactory.create()

    # Create an appointment associated to a recipient with stripe id
    appointment = factories.AppointmentFactory.create()
    appointment.product.practitioner.practitioner_profile.stripe_account_id = (
        "fake_stripe_account_id"
    )

    # Link appointment with fee entry, and fee with invoice
    fee_accounting_entry.appointment = appointment
    invoice.entries = [fee_accounting_entry]

    # Set invoice recipient id to fees recipient id for consistency
    invoice.recipient_id = fee_accounting_entry.stripe_recipient_id

    return invoice


@pytest.fixture
def invoice_view():
    invoice_view = InvoiceView.factory(category=AdminCategory.PAY.value)
    return invoice_view


class TestInvoiceModelStartTransfer:
    def test_no_entries(self, invoice_with_no_entries):
        with pytest.raises(Exception) as e:
            invoice_with_no_entries.start_transfer()

        assert str(e.value) == StartTransferErrorMsg.NO_ENTRIES.value

    def test_no_recipients(self, invoice_with_no_recipients):
        with pytest.raises(Exception) as e:
            invoice_with_no_recipients.start_transfer()

        assert str(e.value) == StartTransferErrorMsg.NO_RECIPIENTS.value

    def test_inconsistent_stripe_id(self, invoice_with_recipient):
        # Set inconsistency between invoice strip id and fee's strip ids
        invoice_with_recipient.recipient_id = (
            "x" + invoice_with_recipient.entries[0].stripe_recipient_id
        )

        with pytest.raises(  # noqa  B017  TODO:  `assertRaises(Exception)` and `pytest.raises(Exception)` should be considered evil. They can lead to your test passing even if the code being tested is never executed due to a typo. Assert for a more specific exception (builtin or custom), or use `assertRaisesRegex` (if using `assertRaises`), or add the `match` keyword argument (if using `pytest.raises`), or use the context manager form with a target.
            Exception
        ):
            invoice_with_recipient.start_transfer()

        # We should expect the invoices recipient id to get updated to solve the inconsistency
        assert (
            invoice_with_recipient.recipient_id
            == invoice_with_recipient.entries[0].stripe_recipient_id
        )

    def test_value_is_zero(self, invoice_with_recipient):
        invoice_with_recipient.entries[0].amount = 0

        with pytest.raises(Exception) as e:
            invoice_with_recipient.start_transfer()

        assert str(e.value) == StartTransferErrorMsg.VALUE_IS_ZERO.value

    def test_value_is_negative(self, invoice_with_recipient):
        invoice_with_recipient.entries[0].amount = -10

        with pytest.raises(Exception) as e:
            invoice_with_recipient.start_transfer()

        assert str(e.value) == StartTransferErrorMsg.VALUE_IS_NEGATIVE.value

    def test_existing_transfer_id(self, invoice_with_recipient):
        invoice_with_recipient.transfer_id = "fake_transfer_id"

        with pytest.raises(Exception) as e:
            invoice_with_recipient.start_transfer()

        assert str(e.value) == StartTransferErrorMsg.EXISTING_TRANSFER_ID.value

    def test_invoice_already_started(self, invoice_with_recipient):
        invoice_with_recipient.started_at = datetime.datetime.now()

        with pytest.raises(Exception) as e:
            invoice_with_recipient.start_transfer()

        assert str(e.value) == StartTransferErrorMsg.INVOICE_ALREADY_STARTED.value

    def test_invoice_already_failed(self, invoice_with_recipient):
        invoice_with_recipient.failed_at = datetime.datetime.now()

        with pytest.raises(Exception) as e:
            invoice_with_recipient.start_transfer()

        assert str(e.value) == StartTransferErrorMsg.INVOICE_ALREADY_FAILED.value

    def test_invoice_already_completed(self, invoice_with_recipient):
        invoice_with_recipient.completed_at = datetime.datetime.now()

        with pytest.raises(Exception) as e:
            invoice_with_recipient.start_transfer()

        assert str(e.value) == StartTransferErrorMsg.INVOICE_ALREADY_COMPLETED.value

    def test_unsuccessful_stripe_transfer(self, invoice_with_recipient):
        with pytest.raises(Exception) as e:
            with mock.patch(
                "common.services.stripe.StripeTransferClient.start_transfer"
            ) as stripe_start_transfer:
                stripe_start_transfer.return_value = None
                invoice_with_recipient.start_transfer()

        assert str(e.value) == StartTransferErrorMsg.UNSUCCESSFUL_STRIPE_TRANSFER.value

    def test_successful_stripe_transfer(self, api_helpers, invoice_with_recipient):
        fake_transfer = CreateableAPIResource()
        fake_transfer.id = "1"
        fake_transfer.amount = invoice_with_recipient.value

        with mock.patch(
            "common.services.stripe.StripeTransferClient.start_transfer"
        ) as stripe_start_transfer:
            stripe_start_transfer.return_value = fake_transfer
            invoice_with_recipient.start_transfer()

            stripe_start_transfer.assert_called_once_with(
                stripe_account_id=invoice_with_recipient.recipient_id,
                amount_in_dollars=invoice_with_recipient.value,
                user_id=invoice_with_recipient.practitioner.id,
                invoice_id=invoice_with_recipient.id,
            )
            assert invoice_with_recipient.transfer_id == fake_transfer.id
            assert invoice_with_recipient.started_at is not None
            assert invoice_with_recipient.json[
                "transfer_at_creation"
            ] == api_helpers.json_data(fake_transfer)


class TestInvoiceViewStartTransfers:
    @mock.patch("flask_login.current_user")
    def test_successful_transfer(
        self, mock_current_user, invoice_view, invoice_with_recipient
    ):
        fake_transfer = CreateableAPIResource()
        fake_transfer.id = "1"
        fake_transfer.amount = invoice_with_recipient.value

        with mock.patch(
            "common.services.stripe.StripeTransferClient.start_transfer"
        ) as stripe_start_transfer:
            stripe_start_transfer.return_value = fake_transfer

            invoices = [invoice_with_recipient]
            result = invoice_view.start_transfers([i.id for i in invoices])
            assert result is None

    @mock.patch("flask_login.current_user")
    def test_unsuccessful_transfers(
        self,
        mock_current_user,
        invoice_with_no_entries,
        invoice_with_no_recipients,
        invoice_with_recipient,
        invoice_view,
    ):
        with mock.patch(
            "common.services.stripe.StripeTransferClient.start_transfer"
        ) as stripe_start_transfer:
            stripe_start_transfer.return_value = None

            invoices = [
                invoice_with_no_entries,
                invoice_with_no_recipients,
                invoice_with_recipient,
            ]

            result = invoice_view.start_transfers([i.id for i in invoices])

            expected_exceptions = {
                invoices[0].id: StartTransferErrorMsg.NO_ENTRIES.value,
                invoices[1].id: StartTransferErrorMsg.NO_RECIPIENTS.value,
                invoices[
                    2
                ].id: StartTransferErrorMsg.UNSUCCESSFUL_STRIPE_TRANSFER.value,
            }
            expected_result = f"Error when starting transfer. Errors per invoice id: {expected_exceptions}"

            assert result == expected_result


class TestStartInvoicesJob:
    def test_start_invoices_job__successful_transfer(self, invoice_with_recipient):
        fake_transfer = CreateableAPIResource()
        fake_transfer.id = "1"
        fake_transfer.amount = invoice_with_recipient.value

        with mock.patch(
            "common.services.stripe.StripeTransferClient.start_transfer"
        ) as stripe_start_transfer, mock.patch(
            "tasks.payments.send_message"
        ) as send_message:
            stripe_start_transfer.return_value = fake_transfer

            invoices = [invoice_with_recipient]
            invoice_ids = [i.id for i in invoices]
            start_invoices(invoice_ids)

            send_message.assert_called_once_with(
                to_email=PROVIDER_PAYMENTS_EMAIL,
                subject="Successfully started invoice transfers",
                text=f"Successfully started invoice transfers for these invoice ids: {invoice_ids}",
                internal_alert=True,
                production_only=True,
            )

    def test_start_invoices_job__unsuccessful_transfers(
        self,
        invoice_with_no_entries,
        invoice_with_no_recipients,
        invoice_with_recipient,
        invoice_view,
    ):
        with mock.patch(
            "common.services.stripe.StripeTransferClient.start_transfer"
        ) as stripe_start_transfer, mock.patch(
            "tasks.payments.send_message"
        ) as send_message:
            stripe_start_transfer.return_value = None

            invoices = [
                invoice_with_no_entries,
                invoice_with_no_recipients,
                invoice_with_recipient,
            ]
            invoice_ids = [i.id for i in invoices]
            start_invoices(invoice_ids)

            expected_transfer_errors = {
                invoices[0].id: StartTransferErrorMsg.NO_ENTRIES.value,
                invoices[1].id: StartTransferErrorMsg.NO_RECIPIENTS.value,
                invoices[
                    2
                ].id: StartTransferErrorMsg.UNSUCCESSFUL_STRIPE_TRANSFER.value,
            }
            expected_email_text = f"Error starting invoice transfers. Errors per invoice id: {expected_transfer_errors}"

            send_message.assert_called_once_with(
                to_email=PROVIDER_PAYMENTS_EMAIL,
                subject="Could not start invoice transfers",
                text=expected_email_text,
                internal_alert=True,
                production_only=True,
            )
