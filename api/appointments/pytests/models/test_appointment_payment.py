import datetime

from payments.services.appointment_payments import AppointmentPaymentsService
from pytests.factories import ScheduleFactory
from storage.connection import db

now = datetime.datetime.utcnow()
today = now.date()


def test_fee_paid_all_credits(valid_appointment, new_credit):
    a = valid_appointment()
    new_credit(amount=a.product.price, user=a.member)

    a.authorize_payment()

    assert not a.payment
    assert a.fee_paid == 0
    assert not a.fee_paid_at

    AppointmentPaymentsService(db.session).complete_payment(
        appointment_id=a.id, product_price=a.product.price
    )
    assert a.fee_paid == a.product.price
    assert a.fee_paid_at


def test_pay_credits_with_decimal_value(
    valid_appointment, new_credit, patch_authorize_payment
):
    a = valid_appointment()
    new_credit(amount=0.01, user=a.member)

    a.authorize_payment()

    success, amt_captured = AppointmentPaymentsService(db.session).complete_payment(
        appointment_id=a.id, product_price=a.product.price
    )

    assert success
    assert amt_captured


def test_fee_paid_no_credits(
    valid_appointment_with_user,
    practitioner_user,
    enterprise_user,
    patch_authorize_payment,
):
    ca = practitioner_user()
    ms = ScheduleFactory.create(user=enterprise_user)
    a = valid_appointment_with_user(
        practitioner=ca,
        member_schedule=ms,
        purpose="birth_needs_assessment",
        scheduled_start=now + datetime.timedelta(minutes=10),
    )
    a.authorize_payment()

    assert a.payment.amount == a.product.price
    assert a.fee_paid == 0
    assert not a.fee_paid_at

    paid, _ = AppointmentPaymentsService(db.session).complete_payment(
        appointment_id=a.id, product_price=a.product.price
    )

    assert paid
    assert a.fee_paid == a.product.price
    assert a.fee_paid_at


def test_fee_paid_partial_credits(
    valid_appointment_with_user,
    practitioner_user,
    new_credit,
    enterprise_user,
    patch_authorize_payment,
):
    ca = practitioner_user()
    ms = ScheduleFactory.create(user=enterprise_user)
    a = valid_appointment_with_user(
        practitioner=ca,
        member_schedule=ms,
        purpose="birth_needs_assessment",
        scheduled_start=now + datetime.timedelta(minutes=10),
    )
    new_credit(amount=1, user=a.member)

    a.authorize_payment()

    assert a.payment.amount == a.product.price - 1
    assert a.fee_paid == 0
    assert not a.fee_paid_at

    paid, _ = AppointmentPaymentsService(db.session).complete_payment(
        appointment_id=a.id, product_price=a.product.price
    )

    assert paid
    assert a.fee_paid == a.product.price
    assert a.fee_paid_at
