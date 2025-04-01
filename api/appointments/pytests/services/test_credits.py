import datetime

import pytest

from appointments.models.payments import Credit
from appointments.services.credit import calculate_total_available_credits
from pytests.factories import CreditFactory

now = datetime.datetime.utcnow()
seven_days = now + datetime.timedelta(days=7)


@pytest.fixture
def create_credits():
    def make_credits(amounts, user_id):
        for amount in amounts:
            CreditFactory.create(
                user_id=user_id,
                amount=amount[0],
                expires_at=amount[1],
                activated_at=amount[2],
                used_at=amount[3],
            )

    return make_credits


def test_total_unused_credit(create_credits, valid_appointment):
    amounts = [
        (100, None, None, None),
        (200, None, None, None),
        (8, None, None, None),
        (1500, None, None, now - datetime.timedelta(minutes=30)),
        (3500, None, None, None),
    ]
    a = valid_appointment()
    create_credits(amounts=amounts, user_id=a.member.id)
    # use a credit for an appointment
    all_credits = Credit.query.all()
    all_credits[0].appointment_id = a.id
    used_credits = amounts[3][0] + all_credits[0].amount
    total = calculate_total_available_credits(user=a.member, start_date=now)
    assert total == sum(a[0] for a in amounts) - used_credits


def test_total_credit_excluding_expired(create_credits, enterprise_user):
    amounts = [
        (100, seven_days + datetime.timedelta(minutes=10), None, None, 0),
        (200, now - datetime.timedelta(minutes=10), None, None, 0),
        (8, None, None, None, 0),
    ]
    create_credits(amounts=amounts, user_id=enterprise_user.id)
    total = calculate_total_available_credits(user=enterprise_user, start_date=now)
    credit_expired = amounts[1][0]
    assert total == sum(a[0] for a in amounts) - credit_expired


def test_total_credit_excluding_not_yet_active(create_credits, enterprise_user):
    amounts = [
        (100, seven_days + datetime.timedelta(minutes=10), None, None),
        (200, now - datetime.timedelta(minutes=10), None, None),
        (8, None, now + datetime.timedelta(minutes=10), None),
        (1500, None, None, None),
    ]
    create_credits(amounts=amounts, user_id=enterprise_user.id)
    total = calculate_total_available_credits(user=enterprise_user, start_date=now)
    credit_expired = amounts[1][0]
    credit_not_yet_active = amounts[2][0]
    assert total == sum(a[0] for a in amounts) - credit_expired - credit_not_yet_active


def test_no_credits(enterprise_user):
    total = calculate_total_available_credits(user=enterprise_user, start_date=now)
    assert total == 0
