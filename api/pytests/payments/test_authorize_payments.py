import datetime
from unittest.mock import patch

import pytest

from appointments.models.payments import PaymentAccountingEntry


@pytest.fixture
def upcoming_appointment(factories):
    now = datetime.datetime.utcnow()
    appointment = factories.AppointmentFactory.create(
        scheduled_start=now + datetime.timedelta(hours=1), product__price=10
    )
    return appointment


class TestAuthorizePayment:
    def test_can_pay_with_credit(self, factories, upcoming_appointment):
        factories.CreditFactory.create(
            user_id=upcoming_appointment.member.id,
            amount=upcoming_appointment.product.price,
        )
        payment = upcoming_appointment.authorize_payment()
        assert payment is True

    def test_not_enough_credit(self, factories, upcoming_appointment):
        factories.CreditFactory.create(
            user_id=upcoming_appointment.member.id,
            amount=(upcoming_appointment.product.price / 2),
        )
        payment = upcoming_appointment.authorize_payment()
        assert payment is None

    def test_cannot_pay_with_credit_auth_failure(self, upcoming_appointment):
        payment = upcoming_appointment.authorize_payment()
        assert payment is None

    def test_can_pay_with_stripe(self, upcoming_appointment):
        mock_payment = PaymentAccountingEntry(
            amount=upcoming_appointment.product.price,
            appointment_id=upcoming_appointment.id,
        )
        with patch(
            "common.services.stripe.StripeCustomerClient.list_cards",
            return_value=["Fake Card"],
        ), patch(
            "common.services.stripe.StripeCustomerClient.create_charge",
            return_value=mock_payment,
        ):
            payment = upcoming_appointment.authorize_payment()
        assert isinstance(payment, PaymentAccountingEntry)
