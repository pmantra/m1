import datetime
from unittest.mock import patch

import pytest

from appointments.tasks.appointments import send_appointment_completion_event
from care_plans.care_plans_service import CarePlansService


@pytest.fixture()
def send_activity_occurred_mock():
    with patch.object(CarePlansService, "send_appointment_completed") as p:
        yield p


def test_send_appointment_completion_event(factories, db, send_activity_occurred_mock):
    current_utc_timestamp = datetime.datetime.utcnow()

    # 1 hour behind current time
    one_hour_previous = current_utc_timestamp - datetime.timedelta(hours=1)

    # 7.5 hours behind current time
    two_hour_previous = current_utc_timestamp - datetime.timedelta(hours=7.5)

    # > 9 hours behind current time
    three_hour_previous = current_utc_timestamp - datetime.timedelta(hours=9)

    db.session.add_all(
        [
            factories.AppointmentFactory.create(
                scheduled_end=one_hour_previous,
                member_started_at=current_utc_timestamp,
                practitioner_started_at=current_utc_timestamp,
            ),
            factories.AppointmentFactory.create(
                scheduled_end=two_hour_previous,
                member_started_at=current_utc_timestamp,
                practitioner_started_at=current_utc_timestamp,
            ),
            factories.AppointmentFactory.create(
                scheduled_end=three_hour_previous,
                member_started_at=current_utc_timestamp,
                practitioner_started_at=current_utc_timestamp,
            ),
        ]
    )

    db.session.commit()

    acknowledged_appointments = send_appointment_completion_event()

    # assert that only `scheduled_end` times that fall within the range of (n-8) - n, where n is the current timestamp/the time
    # that the cronjob ran; only 2 appointments left as one was 9 hours behind and therefore out of the (n-8) - n range
    assert acknowledged_appointments == 2
    assert send_activity_occurred_mock.call_count == 2


def test_send_event_missing_timestamps(factories, db, send_activity_occurred_mock):
    current_utc_timestamp = datetime.datetime.utcnow()
    one_hour_previous = current_utc_timestamp - datetime.timedelta(hours=1)

    # add 2 Appointment objects - both with valid timestamps but one without a member_started_at time
    db.session.add_all(
        [
            factories.AppointmentFactory.create(
                scheduled_end=one_hour_previous,
                member_started_at=current_utc_timestamp,
                practitioner_ended_at=current_utc_timestamp,
            ),
            factories.AppointmentFactory.create(scheduled_end=one_hour_previous),
        ]
    )

    db.session.commit()

    acknowledged_appointments = send_appointment_completion_event()

    assert acknowledged_appointments == 2
    send_activity_occurred_mock.assert_called_once()


def test_pagination(factories, db, send_activity_occurred_mock):
    current_utc_timestamp = datetime.datetime.utcnow()
    one_hour_previous = current_utc_timestamp - datetime.timedelta(hours=1)
    appointments = factories.AppointmentFactory.create_batch(
        size=8,
        scheduled_end=one_hour_previous,
        member_started_at=current_utc_timestamp,
        practitioner_ended_at=current_utc_timestamp,
    )

    db.session.add_all(appointments)
    db.session.commit()

    acknowledged_appointments = send_appointment_completion_event()

    assert acknowledged_appointments == 8
