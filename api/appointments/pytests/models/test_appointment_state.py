import datetime

import pytest

from appointments.models.constants import APPOINTMENT_STATES
from pytests.freezegun import freeze_time

FREEZE_TIME_STR = "2024-03-01T12:00:00"

states = APPOINTMENT_STATES


@pytest.fixture()
@freeze_time(FREEZE_TIME_STR)
def fixture_now():
    return datetime.datetime.utcnow()


@freeze_time(FREEZE_TIME_STR)
def test_cancelled(fixture_now, valid_appointment):
    a = valid_appointment()
    a.cancelled_at = fixture_now
    assert a.state == states.cancelled

    a.member_started_at = fixture_now
    assert a.state == states.cancelled


@freeze_time(FREEZE_TIME_STR)
def test_disputed(fixture_now, valid_appointment):
    a = valid_appointment()
    a.disputed_at = fixture_now
    assert a.state == states.disputed


@freeze_time(FREEZE_TIME_STR)
def test_scheduled(fixture_now, valid_appointment):
    in_five_minutes = fixture_now + datetime.timedelta(minutes=5)
    a = valid_appointment(scheduled_start=in_five_minutes)
    assert a.state == states.scheduled


@freeze_time(FREEZE_TIME_STR)
def test_occurring(fixture_now, valid_appointment):
    a = valid_appointment()
    a.member_started_at = fixture_now
    a.practitioner_started_at = fixture_now
    assert a.state == states.occurring


@freeze_time(FREEZE_TIME_STR)
def test_both_missing_is_overdue(fixture_now, valid_appointment):
    five_minutes_ago = fixture_now - datetime.timedelta(minutes=5)
    a = valid_appointment(scheduled_start=five_minutes_ago)
    assert a.state == states.overdue


@freeze_time(FREEZE_TIME_STR)
def test_member_only_is_overdue(fixture_now, valid_appointment):
    in_one_minute = fixture_now - datetime.timedelta(minutes=1)
    a = valid_appointment(scheduled_start=in_one_minute)
    a.member_started_at = fixture_now
    assert a.state == states.overdue


@freeze_time(FREEZE_TIME_STR)
def test_practitioner_only_is_overdue(fixture_now, valid_appointment):
    in_one_minute = fixture_now - datetime.timedelta(minutes=1)
    a = valid_appointment(scheduled_start=in_one_minute)
    a.practitioner_started_at = fixture_now
    assert a.state == states.overdue


@freeze_time(FREEZE_TIME_STR)
def test_practitioner_never_leaves(fixture_now, valid_appointment):
    a = valid_appointment()
    a.member_started_at = fixture_now
    a.practitioner_started_at = fixture_now
    a.member_ended_at = fixture_now + datetime.timedelta(minutes=4)
    assert a.state == states.incomplete


@freeze_time(FREEZE_TIME_STR)
def test_member_never_leaves(fixture_now, valid_appointment):
    a = valid_appointment()
    a.member_started_at = fixture_now
    a.practitioner_started_at = fixture_now
    a.practitioner_ended_at = fixture_now + datetime.timedelta(minutes=4)
    assert a.state == states.incomplete


@freeze_time(FREEZE_TIME_STR)
def test_payment_pending(fixture_now, valid_appointment):
    a = valid_appointment()
    a.member_started_at = fixture_now
    a.practitioner_started_at = fixture_now
    a.member_ended_at = fixture_now + datetime.timedelta(minutes=4)
    a.practitioner_ended_at = fixture_now + datetime.timedelta(minutes=4)
    assert a.state == states.payment_pending


@freeze_time(FREEZE_TIME_STR)
def test_fee_paid_at_incomplete(fixture_now, valid_appointment):
    a = valid_appointment()
    a.member_started_at = fixture_now
    a.practitioner_started_at = fixture_now
    a.member_ended_at = fixture_now + datetime.timedelta(minutes=4)
    a.practitioner_ended_at = fixture_now + datetime.timedelta(minutes=4)
    a.captured_at = fixture_now + datetime.timedelta(minutes=4)
    assert a.state == states.payment_pending


@freeze_time(FREEZE_TIME_STR)
def test_fee_paid(fixture_now, valid_appointment, appointment_payment):
    one_minute_ago = fixture_now - datetime.timedelta(minutes=1)
    a = valid_appointment(scheduled_start=one_minute_ago)
    a.member_started_at = fixture_now
    a.practitioner_started_at = fixture_now
    a.member_ended_at = fixture_now + datetime.timedelta(minutes=4)
    a.practitioner_ended_at = fixture_now + datetime.timedelta(minutes=4)

    p = appointment_payment(appointment=a)
    p.captured_at = fixture_now + datetime.timedelta(minutes=4)
    p.amount = 10.00
    assert a.state == states.payment_resolved


@freeze_time(FREEZE_TIME_STR)
def test_overflowing_appointment(fixture_now, factories):
    start = fixture_now - datetime.timedelta(minutes=40)
    # Appointment has no ended_at, but scheduled_end is in the past
    overflowing_appointment = factories.AppointmentFactory.create(
        scheduled_start=start,
        scheduled_end=fixture_now - datetime.timedelta(minutes=5),
        member_started_at=start,
        practitioner_started_at=start,
    )
    assert overflowing_appointment.state == states.overflowing
