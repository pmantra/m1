import datetime

import pytest

from appointments.models.schedule_event import ScheduleEvent, ScheduleEventNotFoundError

now = datetime.datetime.utcnow().replace(second=0, microsecond=0)


def test_get_schedule_event_from_timestamp__event_contains(
    factories,
    practitioner_user,
):
    """
    Tests the function returns the event when searching for a timestamp contained therein.
    """
    practitioner = practitioner_user()

    event_1 = factories.ScheduleEventFactory.create(
        schedule=practitioner.schedule,
        starts_at=now,
        ends_at=now + datetime.timedelta(hours=4),
    )

    result = ScheduleEvent.get_schedule_event_from_timestamp(
        practitioner.schedule,
        now + datetime.timedelta(hours=1),
    )

    assert result == event_1


def test_get_schedule_event_from_timestamp__not_contained(
    factories,
    practitioner_user,
):
    """
    Tests the function raises an error when searching for a timestamp
    that does not overlap any events.
    """
    practitioner = practitioner_user()

    factories.ScheduleEventFactory.create(
        schedule=practitioner.schedule,
        starts_at=now + datetime.timedelta(hours=1),
        ends_at=now + datetime.timedelta(hours=2),
    )

    # Timestamp before event
    with pytest.raises(ScheduleEventNotFoundError):
        ScheduleEvent.get_schedule_event_from_timestamp(
            practitioner.schedule,
            now + datetime.timedelta(minutes=30),
        )

    # Timestamp after event
    with pytest.raises(ScheduleEventNotFoundError):
        ScheduleEvent.get_schedule_event_from_timestamp(
            practitioner.schedule,
            now + datetime.timedelta(minutes=150),
        )
