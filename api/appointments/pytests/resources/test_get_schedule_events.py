import datetime
from unittest.mock import patch

import pytest

from pytests import freezegun

NOW = datetime.datetime.utcnow().replace(microsecond=0)


@pytest.mark.parametrize(
    argnames="recurring, flag_on",
    argvalues=[
        (True, True),
        (True, False),
        (False, True),
        (False, False),
    ],
    ids=[
        "default_recurring_flag_on",
        "default_recurring_flag_off",
        "recurring_false_flag_on",
        "recurring_false_flag_off",
    ],
)
def test_get_schedule_events_no_with_recurring_param(
    recurring: bool,
    flag_on: bool,
    api_helpers,
    client,
    schedule_recurring_block_events,
    factories,
):
    practitioner = factories.PractitionerUserFactory.create()
    practitioner.practitioner_profile.default_prep_buffer = 5
    ca = factories.AssignableAdvocateFactory.create_with_practitioner(
        practitioner=practitioner
    )

    recurring_block = schedule_recurring_block_events(
        practitioner=practitioner, starts_at=NOW
    )
    schedule_start = recurring_block.starts_at
    schedule_end = recurring_block.ends_at

    request = {
        "starts_at": schedule_start.isoformat(),
        "ends_at": schedule_end.isoformat(),
    }

    if not recurring:
        request["recurring"] = False

    with patch("maven.feature_flags.bool_variation", return_value=flag_on):
        res = client.get(
            f"/api/v1/practitioners/{practitioner.id}/schedules/events",
            headers=api_helpers.json_headers(user=practitioner),
            query_string=request,
        )

        assert res.status_code == 200
        assert res.json["meta"]["starts_at"] == schedule_start.isoformat()
        assert res.json["meta"]["ends_at"] == schedule_end.isoformat()

        assert (
            res.json["provider_scheduling_constraints"]["prep_buffer"]
            == practitioner.practitioner_profile.default_prep_buffer
        )
        assert (
            res.json["provider_scheduling_constraints"]["booking_buffer"]
            == practitioner.practitioner_profile.booking_buffer
        )
        assert (
            res.json["provider_scheduling_constraints"]["max_capacity"]
            == ca.max_capacity
        )
        assert (
            res.json["provider_scheduling_constraints"]["daily_intro_capacity"]
            == ca.daily_intro_capacity
        )

        if recurring:
            # assert all event ids are present in the response
            assert {event["id"] for event in res.json["data"]}.issubset(
                {event.id for event in recurring_block.schedule_events}
            )
        else:
            assert res.json["data"] == []


@freezegun.freeze_time("2022-04-06 00:17:10")
def test_get_schedule_events_defaults(
    api_helpers,
    client,
    schedule_recurring_block_events,
    factories,
):
    practitioner = factories.PractitionerUserFactory.create()
    practitioner.practitioner_profile.default_prep_buffer = 5

    now = datetime.datetime.utcnow()

    res = client.get(
        f"/api/v1/practitioners/{practitioner.id}/schedules/events",
        headers=api_helpers.json_headers(user=practitioner),
    )

    assert res.status_code == 200
    assert res.json["meta"]["starts_at"] == now.isoformat()
    assert res.json["meta"]["ends_at"] == (now + datetime.timedelta(days=7)).isoformat()


def test_get_schedule_events_maintenance_windows(
    api_helpers,
    client,
    schedule_recurring_block_events,
    factories,
):
    practitioner = factories.PractitionerUserFactory.create()
    practitioner.practitioner_profile.default_prep_buffer = 5

    recurring_block = schedule_recurring_block_events(
        practitioner=practitioner, starts_at=NOW
    )
    schedule_start = recurring_block.starts_at
    schedule_end = recurring_block.ends_at

    factories.ScheduledMaintenanceFactory.create(
        scheduled_start=schedule_start, scheduled_end=schedule_end
    )

    request = {
        "starts_at": schedule_start.isoformat(),
        "ends_at": schedule_end.isoformat(),
    }

    res = client.get(
        f"/api/v1/practitioners/{practitioner.id}/schedules/events",
        headers=api_helpers.json_headers(user=practitioner),
        query_string=request,
    )

    assert res.status_code == 200
    assert res.json["meta"]["starts_at"] == schedule_start.isoformat()
    assert res.json["meta"]["ends_at"] == schedule_end.isoformat()
    assert (
        res.json["maintenance_windows"][0]["scheduled_start"]
        == schedule_start.isoformat()
    )
    assert (
        res.json["maintenance_windows"][0]["scheduled_end"] == schedule_end.isoformat()
    )
