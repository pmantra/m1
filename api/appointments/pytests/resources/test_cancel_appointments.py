import datetime
from typing import Optional
from unittest.mock import MagicMock, patch

from appointments.models.appointment import Appointment
from appointments.models.cancellation_policy import CancellationPolicyName
from appointments.models.payments import Credit

now = datetime.datetime.utcnow()


def _capture_charge_mock(*args, **kwargs):
    charge = MagicMock()
    charge.stripe_id = "abcd"
    charge.amount = kwargs.get("amount_in_dollars", 0) * 100
    return charge


def _cancel_appointment(
    appointment: Appointment,
    cancelled_note: Optional[str] = None,
    as_practitioner: bool = False,
    admin_initiated: bool = False,
):
    user_id = appointment.practitioner.id if as_practitioner else appointment.member.id
    stripe_client_mock = MagicMock()
    with patch(
        "appointments.models.payments.StripeCustomerClient"
    ) as stripe_client_constructor_mock:
        stripe_client_constructor_mock.return_value = stripe_client_mock
        stripe_client_mock.capture_charge.side_effect = _capture_charge_mock
        appointment.cancel(
            user_id=user_id,
            cancelled_note=cancelled_note,
            admin_initiated=admin_initiated,
        )


def test_cancel(non_refundable_cancellable_appointment, patch_authorize_payment):
    """Basic cancel case."""
    appointment = non_refundable_cancellable_appointment

    appointment.authorize_payment()

    assert appointment.payment.amount == appointment.product.price

    _cancel_appointment(appointment)
    assert appointment.payment.captured_at
    assert float(round(appointment.payment.amount_captured, 2)) == float(
        round(0.7 * appointment.product.price, 2)
    )


def test_cancel_with_full_credit(
    factories, non_refundable_cancellable_appointment, patch_authorize_payment
):
    """Appointment was paid for exclusively with credit. Make sure credit is returned."""
    appointment = non_refundable_cancellable_appointment

    factories.CreditFactory(
        user_id=appointment.member.id,
        amount=appointment.product.price,
    )
    assert len(Credit.available_for_appointment(appointment)) == 1
    appointment.authorize_payment()
    assert len(Credit.available_for_appointment(appointment)) == 0

    assert not appointment.payment

    _cancel_appointment(appointment)
    assert not appointment.payment
    assert len(Credit.available_for_appointment(appointment)) == 1


def test_cancel_with_partial_credit(
    factories, non_refundable_cancellable_appointment, patch_authorize_payment
):
    """Appointment was paid for partially with credit."""
    appointment = non_refundable_cancellable_appointment

    factories.CreditFactory(
        user_id=appointment.member.id,
        amount=appointment.product.price / 2,
    )
    assert len(Credit.available_for_appointment(appointment)) == 1
    appointment.authorize_payment()
    assert len(Credit.available_for_appointment(appointment)) == 0

    assert appointment.payment

    _cancel_appointment(appointment)
    assert appointment.payment.captured_at
    assert float(round(appointment.payment.amount_captured, 2)) == float(
        round(0.2 * appointment.product.price, 2)
    )
    assert len(Credit.available_for_appointment(appointment)) == 0


def test_cancel_full_refund(factories, patch_authorize_payment):
    """Cancellation policy offers full refund."""
    cancellation_policy = factories.CancellationPolicyFactory.create(
        refund_48_hours=100
    )
    appointment = factories.AppointmentFactory.create(
        cancellation_policy=cancellation_policy,
        scheduled_start=now + datetime.timedelta(hours=50),
        created_at=now - datetime.timedelta(minutes=15),
    )

    appointment.authorize_payment()

    assert appointment.payment.amount == appointment.product.price

    _cancel_appointment(appointment)
    assert appointment.payment.cancelled_at


def test_cancel_full_refund_with_partial_payment(factories, patch_authorize_payment):
    """Cancellation policy offers full refund."""
    cancellation_policy = factories.CancellationPolicyFactory.create(
        refund_48_hours=100
    )
    appointment = factories.AppointmentFactory.create(
        cancellation_policy=cancellation_policy,
        scheduled_start=now + datetime.timedelta(hours=50),
        created_at=now - datetime.timedelta(minutes=15),
    )
    factories.CreditFactory(
        user_id=appointment.member.id,
        amount=appointment.product.price / 2,
    )

    assert len(Credit.available_for_appointment(appointment)) == 1
    appointment.authorize_payment()
    assert len(Credit.available_for_appointment(appointment)) == 0
    assert appointment.payment
    assert appointment.payment.amount == (appointment.product.price / 2)

    _cancel_appointment(appointment)
    assert appointment.payment.cancelled_at
    assert len(Credit.available_for_appointment(appointment)) == 1


def test_cancel_fifty_percent_refund(factories, patch_authorize_payment):
    """Cancellation policy offers 50% refund."""
    cancellation_policy = factories.CancellationPolicyFactory.create(refund_0_hours=50)
    appointment = factories.AppointmentFactory.create(
        cancellation_policy=cancellation_policy,
        scheduled_start=now + datetime.timedelta(hours=1),
        created_at=now - datetime.timedelta(minutes=15),
    )

    appointment.authorize_payment()
    assert appointment.payment.amount == appointment.product.price

    _cancel_appointment(appointment)
    assert appointment.payment
    assert appointment.payment.captured_at
    assert appointment.payment.amount_captured == (appointment.product.price / 2)


def test_cancel_member_no_show_full_refund(factories, patch_authorize_payment):
    """Cancellation policy offers full refund for member no-show."""
    cancellation_policy = factories.CancellationPolicyFactory.create(
        name=CancellationPolicyName.CONSERVATIVE
    )
    appointment = factories.AppointmentFactory.create(
        cancellation_policy=cancellation_policy,
        scheduled_start=now + datetime.timedelta(hours=1),
        created_at=now - datetime.timedelta(minutes=15),
    )

    appointment.authorize_payment()
    assert appointment.payment.amount == appointment.product.price

    _cancel_appointment(appointment, admin_initiated=True)
    assert appointment.payment
    assert appointment.payment.amount_captured == appointment.product.price


def test_cancel_with_cancellation_note(non_refundable_cancellable_appointment):
    """Cancelled with note, make sure the note persists."""
    appointment = non_refundable_cancellable_appointment

    cancelled_note = "This is a note"

    _cancel_appointment(appointment, cancelled_note=cancelled_note)
    assert appointment.json.get("cancelled_note") == cancelled_note


def test_cancel_practitioner(
    non_refundable_cancellable_appointment, patch_authorize_payment
):
    """Practitioner cancels the appointment."""
    appointment = non_refundable_cancellable_appointment

    appointment.authorize_payment()

    assert appointment.payment.amount == appointment.product.price

    _cancel_appointment(appointment, as_practitioner=True)
    assert appointment.payment.cancelled_at


def test_cancel_member_calls_update_member_cancellations(
    non_refundable_cancellable_appointment,
    patch_appointment_update_member_cancellations,
):
    """
    Tests when member cancels the appointment, update member cancellations is called.
    """
    appointment = non_refundable_cancellable_appointment
    appointment.authorize_payment()
    _cancel_appointment(appointment)
    patch_appointment_update_member_cancellations.assert_called()


def test_cancel_practitioner_does_not_call_update_member_cancellations(
    non_refundable_cancellable_appointment,
    patch_appointment_update_member_cancellations,
):
    """
    Tests when practitioner cancels the appointment, update member cancellations is not called.
    """
    appointment = non_refundable_cancellable_appointment
    appointment.authorize_payment()
    _cancel_appointment(appointment, as_practitioner=True)
    patch_appointment_update_member_cancellations.assert_not_called()
