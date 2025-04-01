import datetime
import os
from unittest import mock
from unittest.mock import ANY

import pytest
import stripe

from braze.client import constants
from common.services.stripe import read_webhook_event
from payments.models.practitioner_contract import ContractType
from payments.pytests.factories import PractitionerContractFactory
from payments.resources.stripe_webhook import confirm_payout
from pytests.freezegun import freeze_time
from utils.mail import PROVIDER_FROM_EMAIL, PROVIDER_REPLY_EMAIL


# mocked stripe post to the webhook
@pytest.fixture(scope="function")
def stripe_payout_event():
    def _stripe_event(stripe_account_id, status, amount):

        return stripe.Event.construct_from(
            {
                "livemode": True,
                "account": stripe_account_id,
                "data": {
                    "object": {
                        "amount": amount,
                        "client_secret": "pi_1ITvI7KEGJDOxFwycCCqVb3h_secret_XZVxG9Mh9cL62HAAMz53eH3MB",
                        "confirmation_method": "automatic",
                        "currency": "usd",
                        "id": "some_id",
                        "metadata": {},
                        "object": "payout",
                        "payment_method_types": ["bank_account"],
                    }
                },
                "id": "evt_1ITvI9KEGJDOxFwy6Bf0gX7Y",
                "object": "event",
                "request": {"id": "req_UQhVFWWTxEwID6", "idempotency_key": ""},
                "type": f"payout.{status}",
            },
            "stripe_event",
        )

    return _stripe_event


def test_stripe_payment_webhook_success(client, stripe_payout_event):
    event = stripe_payout_event(10, "paid", 100)

    response = client.post(
        "/api/v1/vendor/stripe/webhooks",
        json=event,
    )

    assert response.status == "200 OK"


@mock.patch.dict(os.environ, {"STRIPE_SIGNATURE_SECRET_KEY": "SECRETSECRET"})
def test_stripe_payment_webhook_with_secret(client, stripe_payout_event):
    event = stripe_payout_event(10, "paid", 100)

    # if we don't patch this with a mock, it will try to execute stripe code with
    # the test password, and it will cause an error
    with mock.patch(
        "payments.resources.stripe_webhook.read_webhook_event"
    ) as webhook_event_mock:
        response = client.post(
            "/api/v1/vendor/stripe/webhooks",
            json=event,
            headers={"STRIPE_SIGNATURE": "SECRETSECRET"},
        )
    webhook_event_mock.assert_called_once_with(
        mock.ANY, mock.ANY, "SECRETSECRET", "SECRETSECRET"
    )
    assert response.status == "200 OK"


@mock.patch.dict(os.environ, {"STRIPE_SIGNATURE_SECRET_KEY": "SECRETSECRET"})
def test_stripe_payment_webhook_no_secret(client, stripe_payout_event):
    event = stripe_payout_event(10, "paid", 100)

    response = client.post(
        "/api/v1/vendor/stripe/webhooks",
        json=event,
    )

    assert response.status == "400 BAD REQUEST"


def test_stripe_payment_webhook_no_data(client):
    response = client.post(
        "/api/v1/vendor/stripe/webhooks",
    )

    assert response.status == "400 BAD REQUEST"


def test_stripe_payment_webhook_no_event(client, stripe_payout_event):
    event = stripe_payout_event(10, "paid", 100)

    # mock this to simulate read webhook event failing.
    with mock.patch(
        "payments.resources.stripe_webhook.read_webhook_event", return_value=None
    ):
        response = client.post(
            "/api/v1/vendor/stripe/webhooks",
            json=event,
            headers={"STRIPE_SIGNATURE": "SECRETSECRET"},
        )

    assert response.status == "400 BAD REQUEST"


@pytest.fixture
def started_invoices(factories):
    def _started_invoices(amounts_with_recipient):
        invoices = []
        for i, (amount, recipient) in enumerate(amounts_with_recipient):
            inv = factories.InvoiceFactory()
            inv.started_at = datetime.datetime.utcnow()
            inv.recipient_id = recipient
            inv.transfer_id = i
            fae = factories.FeeAccountingEntryFactory.create()
            fae.amount = amount
            inv.entries = [fae]

            invoices.append(inv)

        return invoices

    return _started_invoices


# create a provider
# create one invoice for provider
# process webhook event
# check that the invoice is marked as paid
@freeze_time("2021-01-01T00:00:00")
@mock.patch("braze.client.BrazeClient.send_email")
def test_should_complete_one_invoice__invoice_has_no_practitioner(
    mock_braze_send_email, factories, stripe_payout_event, started_invoices
):
    # Given an invoice that has no practitioner associated to it
    stripe_account_id = "10"
    provider = factories.PractitionerUserFactory.create()
    provider.practitioner_profile.stripe_account_id = stripe_account_id

    invoices = started_invoices([(100, stripe_account_id)])
    event_payload = stripe_payout_event(stripe_account_id, "paid", 100)
    event = read_webhook_event(event_payload, "")

    # When
    confirm_payout(event)

    # Then invoice is completed
    assert invoices[0].completed_at == datetime.datetime.utcnow()
    # And no notification is sent
    assert not mock_braze_send_email.called


class AnyStringWith(str):
    def __eq__(self, other):
        return self in other


@freeze_time("2021-01-01T00:00:00")
@mock.patch("braze.client.BrazeClient._make_request")
def test_should_complete_one_invoice__invoice_has_practitioner__fallback_is_staff(
    mock_braze_make_request,
    factories,
    stripe_payout_event,
    started_invoices,
):
    # Given an invoice for a practitioner with no contract but with is_staff False
    stripe_account_id = "10"
    provider = factories.PractitionerUserFactory.create()
    provider.practitioner_profile.stripe_account_id = stripe_account_id
    provider.practitioner_profile.is_staff = False

    invoices = started_invoices([(100, stripe_account_id)])
    invoices[0].entries[0].practitioner = provider

    event_payload = stripe_payout_event(stripe_account_id, "paid", 100)
    event = read_webhook_event(event_payload, "")

    # When
    confirm_payout(event)

    # Then invoice completed and email sent with description of the fees for each appointment/message
    assert invoices[0].completed_at == datetime.datetime.utcnow()
    mock_braze_make_request.assert_any_call(
        endpoint=constants.MESSAGE_SEND_ENDPOINT,
        data={
            "external_user_ids": [provider.esp_id],
            "messages": {
                "email": {
                    "from": PROVIDER_FROM_EMAIL,
                    "reply_to": PROVIDER_REPLY_EMAIL,
                    "subject": ANY,
                    "body": AnyStringWith("following"),
                    # "This payment is for the following appointments" is expected in the email
                    "plaintext_body": AnyStringWith("following"),
                    # "This payment was for the following appointments/messages (all appointment times are in UTC):" is expected to be in the email
                    "headers": {"X-MC-Template": "prac-2018|main-content"},
                }
            },
            "recipient_subscription_state": "all",
        },
        escape_html=False,
    )


@freeze_time("2021-01-01T00:00:00")
@mock.patch("braze.client.BrazeClient._make_request")
def test_should_complete_one_invoice__invoice_has_practitioner__with_contract_that_emits_fee(
    mock_braze_make_request,
    factories,
    stripe_payout_event,
    started_invoices,
):
    # Given an invoice for a practitioner with an active contract that emits fees
    stripe_account_id = "10"
    provider = factories.PractitionerUserFactory.create()
    provider.practitioner_profile.stripe_account_id = stripe_account_id

    invoices = started_invoices([(100, stripe_account_id)])
    invoices[0].entries[0].practitioner = provider

    PractitionerContractFactory.create(
        practitioner=provider.practitioner_profile,
        contract_type=ContractType.BY_APPOINTMENT,
        start_date=datetime.datetime.now() - datetime.timedelta(days=1),
    )

    event_payload = stripe_payout_event(stripe_account_id, "paid", 100)
    event = read_webhook_event(event_payload, "")

    # When
    confirm_payout(event)

    # Then invoice completed and email sent with description of the fees for each appointment/message
    assert invoices[0].completed_at == datetime.datetime.utcnow()
    mock_braze_make_request.assert_any_call(
        endpoint=constants.MESSAGE_SEND_ENDPOINT,
        data={
            "external_user_ids": [provider.esp_id],
            "messages": {
                "email": {
                    "from": PROVIDER_FROM_EMAIL,
                    "reply_to": PROVIDER_REPLY_EMAIL,
                    "subject": ANY,
                    "body": AnyStringWith("following"),
                    # "This payment is for the following appointments" is expected in the email
                    "plaintext_body": AnyStringWith("following"),
                    # "This payment was for the following appointments/messages (all appointment times are in UTC):" is expected to be in the email
                    "headers": {"X-MC-Template": "prac-2018|main-content"},
                }
            },
            "recipient_subscription_state": "all",
        },
        escape_html=False,
    )


@freeze_time("2021-01-01T00:00:00")
@mock.patch("braze.client.BrazeClient._make_request")
def test_should_complete_one_invoice__invoice_has_practitioner__with_contract_that_doesnt_emit_fee(
    mock_braze_make_request,
    factories,
    stripe_payout_event,
    started_invoices,
):
    # Given an invoice for a practitioner with an active contract that does not emits fees
    stripe_account_id = "10"
    provider = factories.PractitionerUserFactory.create()
    provider.practitioner_profile.stripe_account_id = stripe_account_id

    invoices = started_invoices([(100, stripe_account_id)])
    # Add practitioner to fee so its associated to invoice too, then we can assert notifications sent in transfer_complete()
    invoices[0].entries[0].practitioner = provider

    # Add a contract that does not emits fees to the practitioner
    PractitionerContractFactory.create(
        practitioner=provider.practitioner_profile,
        contract_type=ContractType.W2,
        start_date=datetime.datetime.now() - datetime.timedelta(days=1),
    )

    event_payload = stripe_payout_event(stripe_account_id, "paid", 100)
    event = read_webhook_event(event_payload, "")

    # When
    confirm_payout(event)

    # Then invoice completed and email sent with NO description of the fees for each appointment/message
    assert invoices[0].completed_at == datetime.datetime.utcnow()
    mock_braze_make_request.assert_any_call(
        endpoint=constants.MESSAGE_SEND_ENDPOINT,
        data={
            "external_user_ids": [provider.esp_id],
            "messages": {
                "email": {
                    "from": PROVIDER_FROM_EMAIL,
                    "reply_to": PROVIDER_REPLY_EMAIL,
                    "subject": ANY,
                    "body": AnyStringWith(
                        "during"
                    ),  # "This payment is for appointments and messages completed during the month of" is expected in the email
                    "plaintext_body": AnyStringWith(
                        "during"
                    ),  # "This payment is for appointments and messages completed during the month of" is expected to be in the email
                    "headers": {"X-MC-Template": "prac-2018|main-content"},
                }
            },
            "recipient_subscription_state": "all",
        },
        escape_html=False,
    )


# create a provider
# create several invoices that are all for provider in question
# process webhook event
# check that all the invoice that reach that total are marked as paid
@freeze_time("2021-01-01T00:00:00")
def test_should_complete_multiple_invoices(
    factories, stripe_payout_event, started_invoices
):
    stripe_account_id = "10"
    provider = factories.PractitionerUserFactory.create()
    provider.practitioner_profile.stripe_account_id = stripe_account_id

    invoices = started_invoices(
        [
            (1.0, stripe_account_id),
            (0.2, stripe_account_id),
            (0.3, stripe_account_id),
        ]  # amount is in dollars, will be converted to cents
    )
    event_payload = stripe_payout_event(
        stripe_account_id, "paid", 150
    )  # 150 cents -- $1.50
    event = read_webhook_event(event_payload, "")

    confirm_payout(event)

    now = datetime.datetime.utcnow()
    assert invoices[0].completed_at == now
    assert invoices[1].completed_at == now
    assert invoices[2].completed_at == now


# create a provider
# create several invoices that are all for provider in question
# process webhook event
# check that only the invoice with the right amount is marked as paid
@freeze_time("2021-01-01T00:00:00")
def test_should_complete_one_invoice_while_multiple_exists(
    factories, stripe_payout_event, started_invoices
):
    stripe_account_id = "10"
    provider = factories.PractitionerUserFactory.create()
    provider.practitioner_profile.stripe_account_id = stripe_account_id

    invoices = started_invoices(
        [(1.0, stripe_account_id), (0.2, stripe_account_id), (0.3, stripe_account_id)]
    )
    event_payload = stripe_payout_event(stripe_account_id, "paid", 20)
    event = read_webhook_event(event_payload, "")

    confirm_payout(event)

    assert invoices[0].completed_at is None
    assert invoices[1].completed_at == datetime.datetime.utcnow()
    assert invoices[2].completed_at is None


# create a provider
# create several invoices that are all for provider in question
# process webhook event with an amount that does not match up with current invoices
# check that the invoices are not marked as paid
@freeze_time("2021-01-01T00:00:00")
def test_should_not_invoice_weird_amount(
    factories, stripe_payout_event, started_invoices
):
    stripe_account_id = "10"
    provider = factories.PractitionerUserFactory.create()
    provider.practitioner_profile.stripe_account_id = stripe_account_id

    invoices = started_invoices(
        [
            (1.0, stripe_account_id),
            (7.2, stripe_account_id),
            (3.3, stripe_account_id),
        ]  # $10, $72, $33
    )
    event_payload = stripe_payout_event(stripe_account_id, "paid", 20)
    event = read_webhook_event(event_payload, "")

    confirm_payout(event)

    assert invoices[0].completed_at is None
    assert invoices[1].completed_at is None
    assert invoices[2].completed_at is None


# create a provider
# create several invoices, only one of which is for provider in question
# check that the provider's invoice is paid but the others are not.
@freeze_time("2021-01-01T00:00:00")
def test_should_complete_one_invoice_ignore_from_other_providers(
    factories, stripe_payout_event, started_invoices
):
    stripe_account_id = "10"
    provider = factories.PractitionerUserFactory.create()
    provider.practitioner_profile.stripe_account_id = stripe_account_id

    invoices = started_invoices(
        [(1.0, "30"), (0.2, "30"), (0.3, stripe_account_id)]
    )  # create a bunch of invoices
    event_payload = stripe_payout_event(stripe_account_id, "paid", 150)
    event = read_webhook_event(event_payload, "")

    confirm_payout(event)

    assert invoices[0].completed_at is None
    assert invoices[1].completed_at is None
    assert invoices[2].completed_at == datetime.datetime.utcnow()
