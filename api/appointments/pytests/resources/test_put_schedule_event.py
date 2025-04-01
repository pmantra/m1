import datetime
import json

import pytest

now = datetime.datetime.utcnow().replace(microsecond=0)


@pytest.fixture
def practitioner(practitioner_user):
    return practitioner_user()


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


def test_put_schedule_event(
    api_helpers,
    client,
    practitioner,
    schedule_event_with_appointments,
):
    event = schedule_event_with_appointments
    schedule_start = event.starts_at
    schedule_end = event.ends_at

    payload = {
        "starts_at": schedule_start.isoformat(),
        "ends_at": schedule_end.isoformat(),
    }

    res = client.put(
        f"/api/v1/practitioners/{practitioner.id}/schedules/events/{event.id}",
        headers=api_helpers.json_headers(user=practitioner),
        data=json.dumps(payload),
    )

    assert res.status_code == 200
    assert res.json["starts_at"] == schedule_start.isoformat()
    assert res.json["ends_at"] == schedule_end.isoformat()


def test_put_schedule_event_expand_times(
    api_helpers,
    client,
    practitioner,
    schedule_event_with_appointments,
):
    event = schedule_event_with_appointments

    expected_start = (event.starts_at - datetime.timedelta(minutes=30)).isoformat()
    expected_end = (event.ends_at + datetime.timedelta(minutes=30)).isoformat()

    payload = {
        "starts_at": expected_start,
        "ends_at": expected_end,
    }

    res = client.put(
        f"/api/v1/practitioners/{practitioner.id}/schedules/events/{event.id}",
        headers=api_helpers.json_headers(user=practitioner),
        data=json.dumps(payload),
    )

    assert res.status_code == 200
    assert res.json["starts_at"] == expected_start
    assert res.json["ends_at"] == expected_end


def test_put_schedule_event_shrink_times(
    api_helpers,
    client,
    practitioner,
    schedule_event_with_appointments,
):
    event = schedule_event_with_appointments

    expected_start = (event.starts_at + datetime.timedelta(minutes=30)).isoformat()
    expected_end = (event.ends_at - datetime.timedelta(minutes=30)).isoformat()

    payload = {
        "starts_at": expected_start,
        "ends_at": expected_end,
    }

    res = client.put(
        f"/api/v1/practitioners/{practitioner.id}/schedules/events/{event.id}",
        headers=api_helpers.json_headers(user=practitioner),
        data=json.dumps(payload),
    )

    assert res.status_code == 200
    assert res.json["starts_at"] == expected_start
    assert res.json["ends_at"] == expected_end


def test_put_schedule_event_shrink_times_appointment_conflict(
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
    }

    res = client.put(
        f"/api/v1/practitioners/{practitioner.id}/schedules/events/{event.id}",
        headers=api_helpers.json_headers(user=practitioner),
        data=json.dumps(payload),
    )

    assert res.status_code == 400
