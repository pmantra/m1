from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from random import randint

import pytest

from appointments.models.cancellation_policy import CancellationPolicyName


@pytest.fixture
def cancellation_policy(factories):
    def cancellation_policy_func(name: CancellationPolicyName):
        return factories.CancellationPolicyFactory.create(
            name=name,
            refund_0_hours=randint(0, 100),
            refund_2_hours=randint(0, 100),
            refund_6_hours=randint(0, 100),
            refund_12_hours=randint(0, 100),
            refund_24_hours=randint(0, 100),
            refund_48_hours=randint(0, 100),
        )

    return cancellation_policy_func


def calculate_refund(price, refund_percent):
    pay_percent = abs(100 - refund_percent)
    pay_amount = price * Decimal(pay_percent) / 100
    return pay_amount.quantize(Decimal(".01"), rounding=ROUND_HALF_UP)


@pytest.mark.parametrize(
    [
        "cancellation_policy_name",
        "appointment_start",
        "cancelled_at",
        "price",
        "expected_payout",
    ],
    [
        (
            CancellationPolicyName.FLEXIBLE,
            datetime.utcnow() - timedelta(minutes=10),
            None,
            Decimal(randint(3, 29)),
            lambda p, _: calculate_refund(p, 0),
        ),
        (
            CancellationPolicyName.FLEXIBLE,
            datetime.utcnow() + timedelta(minutes=10),
            datetime.utcnow() - timedelta(minutes=15),
            Decimal(randint(3, 29)),
            lambda p, x: calculate_refund(p, x.refund_0_hours),
        ),
        (
            CancellationPolicyName.FLEXIBLE,
            datetime.utcnow() + timedelta(hours=3),
            datetime.utcnow() - timedelta(minutes=15),
            Decimal(randint(3, 29)),
            lambda p, x: calculate_refund(p, x.refund_2_hours),
        ),
        (
            CancellationPolicyName.FLEXIBLE,
            datetime.utcnow() + timedelta(hours=9),
            datetime.utcnow() - timedelta(minutes=15),
            Decimal(randint(3, 29)),
            lambda p, x: calculate_refund(p, x.refund_6_hours),
        ),
        (
            CancellationPolicyName.FLEXIBLE,
            datetime.utcnow() + timedelta(hours=17),
            datetime.utcnow() - timedelta(minutes=15),
            Decimal(randint(3, 29)),
            lambda p, x: calculate_refund(p, x.refund_12_hours),
        ),
        (
            CancellationPolicyName.FLEXIBLE,
            datetime.utcnow() + timedelta(hours=37),
            datetime.utcnow() - timedelta(minutes=15),
            Decimal(randint(3, 29)),
            lambda p, x: calculate_refund(p, x.refund_24_hours),
        ),
        (
            CancellationPolicyName.FLEXIBLE,
            datetime.utcnow() + timedelta(hours=59),
            datetime.utcnow() - timedelta(minutes=15),
            Decimal(randint(3, 29)),
            lambda p, x: calculate_refund(p, x.refund_48_hours),
        ),
    ],
    ids=[
        "appointment already started",
        "cancelled outside cancellation window, starts in less than 2 hours",
        "cancelled outside cancellation window, starts in less than 6 hours but more than 2",
        "cancelled outside cancellation window, starts in less than 12 hours but more than 6",
        "cancelled outside cancellation window, starts in less than 24 hours but more than 12",
        "cancelled outside cancellation window, starts in less than 48 hours but more than 24",
        "cancelled outside cancellation window, starts in more than 48",
    ],
)
def test_payment_required_for_appointment(
    cancellation_policy,
    cancellable_appointment,
    cancellation_policy_name,
    appointment_start,
    cancelled_at,
    price,
    expected_payout,
):
    # Given
    policy = cancellation_policy(name=cancellation_policy_name)
    cancellable_appointment.product.practitioner.practitioner_profile.default_cancellation_policy = (
        policy
    )
    cancellable_appointment.product.price = price
    cancellable_appointment.scheduled_start = appointment_start
    cancellable_appointment.created_at = cancelled_at
    # When
    payment = policy.payment_required_for_appointment(cancellable_appointment)
    # Then
    assert payment == expected_payout(price, policy)
