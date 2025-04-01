from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from appointments.models.constants import APPOINTMENT_STATES, PRIVACY_CHOICES
from mpractice.error import InvalidPrivacyError
from mpractice.utils import appointment_utils
from pytests import freezegun

TEST_TIME = datetime.utcnow()


@pytest.mark.parametrize(
    argnames="privacy,expected",
    argvalues=[
        (None, None),
        (PRIVACY_CHOICES.anonymous, PRIVACY_CHOICES.anonymous),
        (PRIVACY_CHOICES.basic, PRIVACY_CHOICES.basic),
        (PRIVACY_CHOICES.full_access, PRIVACY_CHOICES.full_access),
    ],
    ids=["no_privacy", "anonymous", "basic", "full_access"],
)
def test_validate_privacy_success(privacy: str, expected: str):
    assert appointment_utils.validate_privacy(privacy) == expected


def test_validate_privacy_failure():
    with pytest.raises(InvalidPrivacyError):
        appointment_utils.validate_privacy(privacy="invalid_privacy")


@pytest.mark.parametrize(
    argnames="member_started_at,practitioner_started_at,started_at",
    argvalues=[
        (None, None, None),
        (datetime(2024, 1, 1, 10, 0, 0), None, None),
        (None, datetime(2024, 1, 1, 10, 5, 0), None),
        (
            datetime(2024, 1, 1, 10, 0, 0),
            datetime(2024, 1, 1, 10, 5, 0),
            datetime(2024, 1, 1, 10, 5, 0),
        ),
    ],
    ids=[
        "no_member_started_at_and_no_practitioner_started_at",
        "has_member_started_at_no_practitioner_started_at",
        "no_member_started_at_has_practitioner_started_at",
        "has_member_started_at_and_practitioner_started_at",
    ],
)
def test_started_at(
    member_started_at: datetime | None,
    practitioner_started_at: datetime | None,
    started_at: datetime | None,
):
    result = appointment_utils.get_started_at(
        member_started_at=member_started_at,
        practitioner_started_at=practitioner_started_at,
    )
    assert result == started_at


@pytest.mark.parametrize(
    argnames="member_ended_at,practitioner_ended_at,ended_at",
    argvalues=[
        (None, None, None),
        (datetime(2024, 1, 1, 10, 55, 0), None, None),
        (None, datetime(2024, 1, 1, 10, 59, 0), None),
        (
            datetime(2024, 1, 1, 10, 55, 0),
            datetime(2024, 1, 1, 10, 59, 0),
            datetime(2024, 1, 1, 10, 55, 0),
        ),
    ],
    ids=[
        "no_member_ended_at_and_no_practitioner_ended_at",
        "has_member_ended_at_no_practitioner_ended_at",
        "no_member_ended_at_has_practitioner_ended_at",
        "has_member_ended_at_and_practitioner_ended_at",
    ],
)
def test_ended_at_when_started_at_is_not_none(
    member_ended_at: datetime | None,
    practitioner_ended_at: datetime | None,
    ended_at: datetime | None,
):
    result = appointment_utils.get_ended_at(
        member_started_at=datetime(2024, 1, 1, 10, 0, 0),
        practitioner_started_at=datetime(2024, 1, 1, 10, 5, 0),
        member_ended_at=member_ended_at,
        practitioner_ended_at=practitioner_ended_at,
    )
    assert result == ended_at


@pytest.mark.parametrize(
    argnames="member_ended_at,practitioner_ended_at,ended_at",
    argvalues=[
        (None, None, None),
        (datetime(2024, 1, 1, 10, 55, 0), None, None),
        (None, datetime(2024, 1, 1, 10, 59, 0), None),
        (datetime(2024, 1, 1, 10, 55, 0), datetime(2024, 1, 1, 10, 59, 0), None),
    ],
    ids=[
        "no_member_ended_at_and_no_practitioner_ended_at",
        "has_member_ended_at_no_practitioner_ended_at",
        "no_member_ended_at_has_practitioner_ended_at",
        "has_member_ended_at_and_practitioner_ended_at",
    ],
)
def test_ended_at_when_started_at_is_none(
    member_ended_at: datetime | None,
    practitioner_ended_at: datetime | None,
    ended_at: datetime | None,
):
    result = appointment_utils.get_ended_at(
        member_started_at=None,
        practitioner_started_at=None,
        member_ended_at=member_ended_at,
        practitioner_ended_at=practitioner_ended_at,
    )
    assert result == ended_at


@pytest.mark.parametrize(
    argnames="payment_captured_at,credit_latest_used_at,fee_paid_at",
    argvalues=[
        (None, None, None),
        (TEST_TIME, None, TEST_TIME),
        (None, TEST_TIME + timedelta(days=1), TEST_TIME + timedelta(days=1)),
        (TEST_TIME, TEST_TIME + timedelta(days=1), TEST_TIME + timedelta(days=1)),
    ],
    ids=[
        "no_payment_captured_at_no_credit_latest_used_at",
        "has_payment_captured_at_no_credit_latest_used_at",
        "no_payment_captured_at_has_credit_latest_used_at",
        "has_payment_captured_at_has_credit_latest_used_at",
    ],
)
def test_fee_paid_at(
    payment_captured_at: datetime | None,
    credit_latest_used_at: datetime | None,
    fee_paid_at: datetime | None,
):
    result = appointment_utils.get_fee_paid_at(
        payment_captured_at=payment_captured_at,
        credit_latest_used_at=credit_latest_used_at,
    )
    assert result == fee_paid_at


@pytest.mark.parametrize(
    argnames="json,payment_captured_at,payment_amount,total_used_credits,fee_paid",
    argvalues=[
        (None, None, None, None, 0),
        ('{"plan_cancellation_paid_amount": 100}', None, None, None, 100),
        (None, TEST_TIME, 200.2, None, 200.2),
        (None, None, None, 300.3, 300.3),
        ('{"plan_cancellation_paid_amount": 100}', TEST_TIME, 200.2, None, 300.2),
        ('{"plan_cancellation_paid_amount": 100}', None, None, 300.3, 400.3),
        (None, TEST_TIME, 200.2, 300.3, 500.5),
        ('{"plan_cancellation_paid_amount": 100}', TEST_TIME, 200.2, 300.3, 600.5),
    ],
    ids=[
        "no_json_no_payment_no_credit",
        "has_json_no_payment_no_credit",
        "no_json_has_payment_no_credit",
        "no_json_no_payment_has_credit",
        "has_json_has_payment_no_credit",
        "has_json_no_payment_has_credit",
        "no_json_has_payment_has_credit",
        "has_json_has_payment_has_credit",
    ],
)
def test_fee_paid(
    json: str,
    payment_captured_at: datetime,
    payment_amount: float,
    total_used_credits: float,
    fee_paid: float,
):
    result = appointment_utils.get_fee_paid(
        appointment_json=json,
        payment_captured_at=payment_captured_at,
        payment_amount=payment_amount,
        total_used_credits=total_used_credits,
    )
    assert result == fee_paid


def test_state_cancelled():
    result = appointment_utils.get_state(cancelled_at=datetime.utcnow())
    assert result == APPOINTMENT_STATES.cancelled


def test_state_disputed():
    result = appointment_utils.get_state(disputed_at=datetime.utcnow())
    assert result == APPOINTMENT_STATES.disputed


def test_state_payment_resolved_with_payment():
    end_time = TEST_TIME
    start_time = TEST_TIME - timedelta(hours=1)
    result = appointment_utils.get_state(
        scheduled_start=start_time,
        member_started_at=start_time,
        practitioner_started_at=start_time,
        scheduled_end=end_time,
        member_ended_at=end_time,
        practitioner_ended_at=end_time,
        payment_captured_at=TEST_TIME,
        payment_amount=100,
    )
    assert result == APPOINTMENT_STATES.payment_resolved


def test_state_payment_resolved_with_fee():
    end_time = TEST_TIME
    start_time = TEST_TIME - timedelta(hours=1)
    result = appointment_utils.get_state(
        scheduled_start=start_time,
        member_started_at=start_time,
        practitioner_started_at=start_time,
        scheduled_end=end_time,
        member_ended_at=end_time,
        practitioner_ended_at=end_time,
        fees_count=2,
    )
    assert result == APPOINTMENT_STATES.payment_resolved


def test_state_payment_pending():
    end_time = TEST_TIME
    start_time = TEST_TIME - timedelta(hours=1)
    result = appointment_utils.get_state(
        scheduled_start=start_time,
        member_started_at=start_time,
        practitioner_started_at=start_time,
        scheduled_end=end_time,
        member_ended_at=end_time,
        practitioner_ended_at=end_time,
    )
    assert result == APPOINTMENT_STATES.payment_pending


def test_state_occurring():
    now = datetime.utcnow()
    result = appointment_utils.get_state(
        scheduled_start=now,
        member_started_at=now,
        practitioner_started_at=now,
        scheduled_end=now + timedelta(hours=1),
    )
    assert result == APPOINTMENT_STATES.occurring


def test_state_overflowing():
    now = datetime.utcnow()
    result = appointment_utils.get_state(
        scheduled_start=now,
        member_started_at=now,
        practitioner_started_at=now,
        scheduled_end=now - timedelta(hours=1),
    )
    assert result == APPOINTMENT_STATES.overflowing


@pytest.mark.parametrize(
    argnames="member_ended_at,practitioner_ended_at",
    argvalues=[
        (datetime(2024, 1, 1, 11, 0, 0), None),
        (None, datetime(2024, 1, 1, 11, 0, 0)),
    ],
    ids=["has_member_ended_at", "has_practitioner_ended_at"],
)
@freezegun.freeze_time("2024-02-24T00:00:00")
def test_state_incomplete(
    member_ended_at: datetime | None,
    practitioner_ended_at: datetime | None,
):
    now = datetime.utcnow()
    result = appointment_utils.get_state(
        scheduled_start=now - timedelta(hours=1),
        member_started_at=now - timedelta(hours=1),
        practitioner_started_at=now - timedelta(hours=1),
        scheduled_end=now,
        member_ended_at=member_ended_at,
        practitioner_ended_at=practitioner_ended_at,
    )
    assert result == APPOINTMENT_STATES.incomplete


@freezegun.freeze_time("2024-02-24T00:00:00")
def test_get_state_overdue():
    result = appointment_utils.get_state(scheduled_start=datetime(2024, 2, 20, 0, 0, 0))
    assert result == APPOINTMENT_STATES.overdue


@pytest.mark.parametrize(
    argnames="scheduled_start",
    argvalues=[
        datetime(2024, 2, 24, 0, 0, 0),
        datetime(2024, 3, 1, 0, 0, 0),
    ],
    ids=[
        "scheduled_start_now",
        "scheduled_start_in_the_future",
    ],
)
@freezegun.freeze_time("2024-02-24T00:00:00")
def test_state_scheduled(scheduled_start: datetime):
    result = appointment_utils.get_state(scheduled_start=scheduled_start)
    assert result == APPOINTMENT_STATES.scheduled


@pytest.mark.parametrize(
    argnames="first_name,last_name,full_name",
    argvalues=[
        (None, None, ""),
        ("", "", ""),
        (None, "", ""),
        ("", None, ""),
        ("alice", None, "alice"),
        ("alice", "", "alice"),
        (None, "johnson", "johnson"),
        ("", "johnson", "johnson"),
        ("alice", "johnson", "alice johnson"),
    ],
)
def test_get_full_name(first_name: str | None, last_name: str | None, full_name: str):
    assert appointment_utils.get_full_name(first_name, last_name) == full_name


@pytest.mark.parametrize(
    argnames="privacy,member_first_name,member_last_name,expected_member_name",
    argvalues=[
        (PRIVACY_CHOICES.full_access, "Alice", "Johnson", "Alice Johnson"),
        (PRIVACY_CHOICES.anonymous, "Alice", "Johnson", "Anonymous"),
    ],
    ids=["non-anonymous", "anonymous"],
)
def test_get_member_name(
    privacy: str,
    member_first_name: str,
    member_last_name: str,
    expected_member_name: str,
):
    result = appointment_utils.get_member_name(
        privacy=privacy,
        member_first_name=member_first_name,
        member_last_name=member_last_name,
    )
    assert result == expected_member_name
