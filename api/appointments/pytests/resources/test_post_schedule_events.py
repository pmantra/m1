import datetime
import json

import pytest

from appointments.models.constants import ScheduleStates

now = datetime.datetime.utcnow().replace(microsecond=0)


@pytest.fixture
def practitioner(factories, practitioner_user):
    user = practitioner_user()
    c = factories.CapabilityFactory.create(object_type="schedule_event", method="post")
    r = factories.RoleFactory.create(name="care_coordinator", capabilities=[c])
    user.practitioner_profile.role = r
    return user


@pytest.fixture
def schedule_event_with_appointments(
    factories,
    valid_appointment_with_user,
    practitioner,
    enterprise_user,
):
    ms = factories.ScheduleFactory.create(user=enterprise_user)

    schedule_start = now + datetime.timedelta(hours=1)
    schedule_end = schedule_start + datetime.timedelta(hours=8)

    event = factories.ScheduleEventFactory.create(
        schedule=practitioner.schedule,
        starts_at=schedule_start,
        ends_at=schedule_end,
    )
    valid_appointment_with_user(
        practitioner=practitioner,
        member_schedule=ms,
        purpose="birth_needs_assessment",
        scheduled_start=now + datetime.timedelta(hours=2),
    )
    valid_appointment_with_user(
        practitioner=practitioner,
        member_schedule=ms,
        purpose="follow_up",
        scheduled_start=now + datetime.timedelta(hours=4),
    )
    valid_appointment_with_user(
        practitioner=practitioner,
        member_schedule=ms,
        purpose="third_appointment",
        scheduled_start=now + datetime.timedelta(hours=6),
    )

    return event


def test_post_schedule_event(
    api_helpers,
    client,
    practitioner,
):
    schedule_start = now
    schedule_end = schedule_start + datetime.timedelta(days=2)

    payload = {
        "starts_at": schedule_start.isoformat(),
        "ends_at": schedule_end.isoformat(),
        "state": ScheduleStates.available,
    }

    res = client.post(
        f"/api/v1/practitioners/{practitioner.id}/schedules/events",
        headers=api_helpers.json_headers(user=practitioner),
        data=json.dumps(payload),
    )

    assert res.status_code == 201
    assert res.json["starts_at"] == schedule_start.isoformat()
    assert res.json["ends_at"] == schedule_end.isoformat()


def test_post_schedule_event_appointment_conflict(
    api_helpers,
    client,
    practitioner,
    schedule_event_with_appointments,
):
    event = schedule_event_with_appointments

    expected_start = (event.starts_at + datetime.timedelta(minutes=90)).isoformat()
    expected_end = (event.ends_at - datetime.timedelta(minutes=90)).isoformat()

    payload = {
        "starts_at": expected_start,
        "ends_at": expected_end,
        "state": ScheduleStates.available,
    }

    res = client.post(
        f"/api/v1/practitioners/{practitioner.id}/schedules/events",
        headers=api_helpers.json_headers(user=practitioner),
        data=json.dumps(payload),
    )

    assert res.status_code == 400
