import datetime
import json
from unittest.mock import patch

import pytest
from dateutil.relativedelta import relativedelta

from appointments.models.constants import ScheduleFrequencies
from appointments.resources.schedule_recurring_blocks import (
    RECURRING_AVAILABILITY_NOW_UNTIL_TIME_MAX_DIFFERENCE_IN_MONTHS,
    RECURRING_AVAILABILITY_START_UNTIL_TIME_MAX_DIFFERENCE_IN_MONTHS,
)

NOW = datetime.datetime.utcnow().replace(microsecond=0)


def test_post_schedule_recurring_blocks_not_allowed(
    api_helpers,
    client,
    schedule_recurring_block_events,
    factories,
):
    practitioner = factories.PractitionerUserFactory.create()
    recurring_block = schedule_recurring_block_events(
        practitioner=practitioner, starts_at=NOW
    )
    schedule_start = recurring_block.starts_at
    schedule_until = recurring_block.until

    request = {
        "starts_at": schedule_start.isoformat(),
        "until": schedule_until.isoformat(),
    }

    res = client.post(
        "/api/v1/practitioners/12345/schedules/recurring_blocks",
        headers=api_helpers.json_headers(user=practitioner),
        query_string=request,
    )

    assert res.status_code == 403


def test_post_schedule_recurring_blocks(
    api_helpers,
    client,
    factories,
):
    practitioner = factories.PractitionerUserFactory.create()
    c = factories.CapabilityFactory.create(object_type="schedule_event", method="post")
    r = factories.RoleFactory.create(name="care_coordinator", capabilities=[c])
    practitioner.practitioner_profile.role = r

    request_body = {
        "starts_at": NOW.isoformat(),
        "ends_at": (NOW + datetime.timedelta(hours=2)).isoformat(),
        "frequency": ScheduleFrequencies.WEEKLY.value,
        "until": (NOW + datetime.timedelta(weeks=1)).isoformat(),
        "week_days_index": [1, 3],
        "member_timezone": "America/New_York",
    }

    with patch(
        "appointments.resources.schedule_recurring_blocks.create_recurring_availability.delay"
    ) as mock_recurring_create_job:
        res = client.post(
            f"/api/v1/practitioners/{practitioner.id}/schedules/recurring_blocks",
            headers=api_helpers.json_headers(user=practitioner),
            data=json.dumps(request_body),
        )

    assert res.status_code == 202
    mock_recurring_create_job.assert_called_once()


def test_post_schedule_recurring_blocks_incorrect_end_time(
    api_helpers,
    client,
    factories,
):
    practitioner = factories.PractitionerUserFactory.create()
    c = factories.CapabilityFactory.create(object_type="schedule_event", method="post")
    r = factories.RoleFactory.create(name="care_coordinator", capabilities=[c])
    practitioner.practitioner_profile.role = r

    request_body = {
        "starts_at": NOW.isoformat(),
        "ends_at": (NOW + datetime.timedelta(hours=24)).isoformat(),
        "frequency": ScheduleFrequencies.WEEKLY.value,
        "until": (NOW + datetime.timedelta(weeks=1)).isoformat(),
        "week_days_index": [1, 3],
        "member_timezone": "America/New_York",
    }

    res = client.post(
        f"/api/v1/practitioners/{practitioner.id}/schedules/recurring_blocks",
        headers=api_helpers.json_headers(user=practitioner),
        data=json.dumps(request_body),
    )

    assert res.status_code == 400


def test_post_schedule_recurring_blocks_series_too_long(
    api_helpers,
    client,
    factories,
):
    practitioner = factories.PractitionerUserFactory.create()
    c = factories.CapabilityFactory.create(object_type="schedule_event", method="post")
    r = factories.RoleFactory.create(name="care_coordinator", capabilities=[c])
    practitioner.practitioner_profile.role = r

    request_body = {
        "starts_at": NOW.isoformat(),
        "ends_at": (NOW + datetime.timedelta(hours=1)).isoformat(),
        "frequency": ScheduleFrequencies.WEEKLY.value,
        "until": (
            NOW
            + relativedelta(
                months=RECURRING_AVAILABILITY_START_UNTIL_TIME_MAX_DIFFERENCE_IN_MONTHS
            )
            + datetime.timedelta(days=1)
        ).isoformat(),
        "week_days_index": [1, 3],
        "member_timezone": "America/New_York",
    }

    res = client.post(
        f"/api/v1/practitioners/{practitioner.id}/schedules/recurring_blocks",
        headers=api_helpers.json_headers(user=practitioner),
        data=json.dumps(request_body),
    )

    assert res.status_code == 400
    assert (
        res.json["message"]
        == f"Until time needs to be within {RECURRING_AVAILABILITY_START_UNTIL_TIME_MAX_DIFFERENCE_IN_MONTHS} months of start time"
    )


def test_post_schedule_recurring_blocks_series_not_too_long(
    api_helpers,
    client,
    factories,
):
    practitioner = factories.PractitionerUserFactory.create()
    c = factories.CapabilityFactory.create(object_type="schedule_event", method="post")
    r = factories.RoleFactory.create(name="care_coordinator", capabilities=[c])
    practitioner.practitioner_profile.role = r

    request_body = {
        "starts_at": NOW.isoformat(),
        "ends_at": (NOW + datetime.timedelta(hours=1)).isoformat(),
        "frequency": ScheduleFrequencies.WEEKLY.value,
        "until": (
            NOW
            + relativedelta(
                months=RECURRING_AVAILABILITY_START_UNTIL_TIME_MAX_DIFFERENCE_IN_MONTHS
            )
        ).isoformat(),
        "week_days_index": [1, 3],
        "member_timezone": "America/New_York",
    }

    res = client.post(
        f"/api/v1/practitioners/{practitioner.id}/schedules/recurring_blocks",
        headers=api_helpers.json_headers(user=practitioner),
        data=json.dumps(request_body),
    )

    assert res.status_code == 202


def test_post_schedule_recurring_blocks_too_far_into_the_future(
    api_helpers,
    client,
    factories,
):
    practitioner = factories.PractitionerUserFactory.create()
    c = factories.CapabilityFactory.create(object_type="schedule_event", method="post")
    r = factories.RoleFactory.create(name="care_coordinator", capabilities=[c])
    practitioner.practitioner_profile.role = r

    future_start_time = NOW + relativedelta(
        months=RECURRING_AVAILABILITY_NOW_UNTIL_TIME_MAX_DIFFERENCE_IN_MONTHS
    )

    request_body = {
        "starts_at": future_start_time.isoformat(),
        "ends_at": (future_start_time + datetime.timedelta(hours=2)).isoformat(),
        "frequency": ScheduleFrequencies.WEEKLY.value,
        "until": (future_start_time + datetime.timedelta(days=1)).isoformat(),
        "week_days_index": [1, 3],
        "member_timezone": "America/New_York",
    }

    res = client.post(
        f"/api/v1/practitioners/{practitioner.id}/schedules/recurring_blocks",
        headers=api_helpers.json_headers(user=practitioner),
        data=json.dumps(request_body),
    )

    assert res.status_code == 400
    assert (
        res.json["message"]
        == f"Until time needs to be within {RECURRING_AVAILABILITY_NOW_UNTIL_TIME_MAX_DIFFERENCE_IN_MONTHS} months of current time"
    )


def test_post_schedule_recurring_blocks_without_week_days_index(
    api_helpers,
    client,
    factories,
):
    practitioner = factories.PractitionerUserFactory.create()
    c = factories.CapabilityFactory.create(object_type="schedule_event", method="post")
    r = factories.RoleFactory.create(name="care_coordinator", capabilities=[c])
    practitioner.practitioner_profile.role = r

    request_body = {
        "starts_at": NOW.isoformat(),
        "ends_at": (NOW + datetime.timedelta(hours=2)).isoformat(),
        "frequency": ScheduleFrequencies.WEEKLY.value,
        "until": (NOW + datetime.timedelta(weeks=1)).isoformat(),
        "member_timezone": "America/New_York",
    }

    with patch(
        "appointments.resources.schedule_recurring_blocks.create_recurring_availability.delay"
    ) as mock_recurring_create_job:
        res = client.post(
            f"/api/v1/practitioners/{practitioner.id}/schedules/recurring_blocks",
            headers=api_helpers.json_headers(user=practitioner),
            data=json.dumps(request_body),
        )

    assert res.status_code == 202
    mock_recurring_create_job.assert_called_once()


def test_post_schedule_recurring_blocks_conflict_identical_intervals(
    api_helpers,
    client,
    schedule_recurring_block_events,
    factories,
):
    practitioner = factories.PractitionerUserFactory.create()
    c = factories.CapabilityFactory.create(object_type="schedule_event", method="post")
    r = factories.RoleFactory.create(name="care_coordinator", capabilities=[c])
    practitioner.practitioner_profile.role = r

    recurring_block = schedule_recurring_block_events(
        practitioner=practitioner, starts_at=NOW
    )
    schedule_start = recurring_block.starts_at
    schedule_end = recurring_block.ends_at
    schedule_until = recurring_block.until

    request_body = {
        "starts_at": schedule_start.isoformat(),
        "ends_at": schedule_end.isoformat(),
        "frequency": ScheduleFrequencies.WEEKLY.value,
        "until": schedule_until.isoformat(),
        "member_timezone": "America/New_York",
    }

    with patch(
        "appointments.resources.schedule_recurring_blocks.create_recurring_availability.delay"
    ) as mock_recurring_create_job:
        res = client.post(
            f"/api/v1/practitioners/{practitioner.id}/schedules/recurring_blocks",
            headers=api_helpers.json_headers(user=practitioner),
            data=json.dumps(request_body),
        )

    assert res.status_code == 400
    assert res.json["message"] == "Conflict with existing availability!"
    mock_recurring_create_job.assert_not_called()


def test_post_schedule_recurring_blocks_conflict_overlapping_intervals(
    api_helpers,
    client,
    schedule_recurring_block_events,
    factories,
):
    practitioner = factories.PractitionerUserFactory.create()
    c = factories.CapabilityFactory.create(object_type="schedule_event", method="post")
    r = factories.RoleFactory.create(name="care_coordinator", capabilities=[c])
    practitioner.practitioner_profile.role = r

    recurring_block = schedule_recurring_block_events(
        practitioner=practitioner, starts_at=NOW
    )
    schedule_start = recurring_block.starts_at
    schedule_end = recurring_block.ends_at
    schedule_until = recurring_block.until

    request_body = {
        "starts_at": (schedule_start + datetime.timedelta(minutes=10)).isoformat(),
        "ends_at": (schedule_end + datetime.timedelta(minutes=10)).isoformat(),
        "frequency": ScheduleFrequencies.WEEKLY.value,
        "until": schedule_until.isoformat(),
        "member_timezone": "America/New_York",
    }

    with patch(
        "appointments.resources.schedule_recurring_blocks.create_recurring_availability.delay"
    ) as mock_recurring_create_job:
        res = client.post(
            f"/api/v1/practitioners/{practitioner.id}/schedules/recurring_blocks",
            headers=api_helpers.json_headers(user=practitioner),
            data=json.dumps(request_body),
        )

    assert res.status_code == 400
    assert res.json["message"] == "Conflict with existing availability!"
    mock_recurring_create_job.assert_not_called()


@pytest.mark.parametrize(
    argnames=("week_days_index", "timezone", "error_message"),
    argvalues=[
        (
            [1, 8],
            "America/New_York",
            "Invalid week_day_index! Must be between 0-6!",
        ),
        (
            [1, 3],
            "America/Pizza",
            "Incorrect timezone passed!",
        ),
    ],
    ids=[
        "week_days_index_error",
        "timezone_error",
    ],
)
def test_post_schedule_recurring_blocks_errors(
    week_days_index,
    timezone,
    error_message,
    api_helpers,
    client,
    schedule_recurring_block_events,
    factories,
):
    practitioner = factories.PractitionerUserFactory.create()
    c = factories.CapabilityFactory.create(object_type="schedule_event", method="post")
    r = factories.RoleFactory.create(name="care_coordinator", capabilities=[c])
    practitioner.practitioner_profile.role = r

    recurring_block = schedule_recurring_block_events(
        practitioner=practitioner, starts_at=NOW
    )
    schedule_start = recurring_block.starts_at
    schedule_end = recurring_block.ends_at
    schedule_until = recurring_block.until

    request_body = {
        "starts_at": schedule_start.isoformat(),
        "ends_at": schedule_end.isoformat(),
        "frequency": ScheduleFrequencies.WEEKLY.value,
        "until": schedule_until.isoformat(),
        "week_days_index": week_days_index,
        "member_timezone": timezone,
    }

    with patch(
        "appointments.resources.schedule_recurring_blocks.create_recurring_availability.delay"
    ) as mock_recurring_create_job, patch(
        "appointments.services.schedule.abort"
    ) as mock_abort:
        res = client.post(
            f"/api/v1/practitioners/{practitioner.id}/schedules/recurring_blocks",
            headers=api_helpers.json_headers(user=practitioner),
            data=json.dumps(request_body),
        )

        mock_abort.called_once()
        assert error_message in str(res.json["message"])
        mock_recurring_create_job.assert_not_called()
