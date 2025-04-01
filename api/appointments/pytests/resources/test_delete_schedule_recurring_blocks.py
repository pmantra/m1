import datetime
from unittest.mock import patch

import pytest

TEST_DATE = datetime.datetime(2024, 4, 1, 0, 0, 0)


@pytest.fixture
def schedule_recurring_block(schedule, factories):
    recurring_block = factories.ScheduleRecurringBlockFactory.create(
        schedule=schedule,
        starts_at=TEST_DATE,
        ends_at=TEST_DATE + datetime.timedelta(hours=2),
        until=TEST_DATE + datetime.timedelta(weeks=1),
    )
    factories.ScheduleRecurringBlockWeekdayIndexFactory.create(
        schedule_recurring_block=recurring_block,
    )
    factories.ScheduleRecurringBlockWeekdayIndexFactory.create(
        schedule_recurring_block=recurring_block,
        week_days_index=3,
    )
    return recurring_block


@pytest.fixture
def schedule_event(schedule, schedule_recurring_block, factories):
    return factories.ScheduleEventFactory.create(
        schedule=schedule,
        schedule_recurring_block=schedule_recurring_block,
        starts_at=TEST_DATE,
        ends_at=TEST_DATE + datetime.timedelta(hours=2),
    )


def test_delete_schedule_event_not_permitted(
    factories,
    client,
    api_helpers,
    practitioner_user,
    schedule_recurring_block,
    schedule_event,
):
    user = factories.EnterpriseUserFactory.create()
    res = client.delete(
        f"/api/v1/practitioners/{practitioner_user().id}/schedules/recurring_blocks/{schedule_recurring_block.id}",
        headers=api_helpers.json_headers(user),
    )

    assert res.status_code == 403


def test_delete_schedule_event_conflicting_appointment(
    factories,
    client,
    api_helpers,
    practitioner_user,
    schedule_recurring_block,
    schedule_event,
):
    practitioner = practitioner_user()

    with patch(
        "appointments.resources.schedule_recurring_block.delete_recurring_availability.delay"
    ) as mock_recurring_delete_job, patch(
        "appointments.services.recurring_schedule.RecurringScheduleAvailabilityService._get_count_existing_appointments_in_schedule_recurring_block"
    ) as mock_get_existing_appointments:
        mock_get_existing_appointments.return_value = 2
        res = client.delete(
            f"/api/v1/practitioners/{practitioner.id}/schedules/recurring_blocks/{schedule_recurring_block.id}",
            headers=api_helpers.json_headers(practitioner),
        )

    assert res.status_code == 400
    mock_recurring_delete_job.assert_not_called()


def test_delete_schedule_event(
    factories,
    client,
    api_helpers,
    practitioner_user,
    schedule_recurring_block,
    schedule_event,
):
    practitioner = practitioner_user()

    with patch(
        "appointments.resources.schedule_recurring_block.delete_recurring_availability.delay"
    ) as mock_recurring_delete_job:
        res = client.delete(
            f"/api/v1/practitioners/{practitioner.id}/schedules/recurring_blocks/{schedule_recurring_block.id}",
            headers=api_helpers.json_headers(practitioner),
        )

    assert res.status_code == 202
    mock_recurring_delete_job.assert_called_once()
