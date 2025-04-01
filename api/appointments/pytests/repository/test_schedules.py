from __future__ import annotations

import datetime

import pytest

from appointments.models.constants import ScheduleFrequencies
from appointments.models.provider_schedules import (
    ProviderScheduleEvent,
    ProviderScheduleRecurringBlock,
)
from appointments.repository.schedules import (
    ScheduleEventRepository,
    ScheduleRecurringBlockRepository,
)

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


@pytest.fixture
def provider_schedule_event(schedule_event):
    return ProviderScheduleEvent(
        id=schedule_event.id,
        state=schedule_event.state,
        starts_at=schedule_event.starts_at,
        ends_at=schedule_event.ends_at,
    )


class TestScheduleRecurringBlockRepository:
    def test_get_schedule_recurring_blocks_no_data(
        self,
        schedule_repo: ScheduleRecurringBlockRepository,
    ):
        result = schedule_repo.get_schedule_recurring_blocks(
            user_id=123,
            starts_at=TEST_DATE,
            until=(TEST_DATE + datetime.timedelta(weeks=2)),
        )
        assert result == []

    def test_get_schedule_recurring_blocks(
        self,
        schedule_repo: ScheduleRecurringBlockRepository,
        schedule,
        schedule_recurring_block,
        provider_schedule_event,
    ):
        expected = ProviderScheduleRecurringBlock(
            id=schedule_recurring_block.id,
            schedule_id=schedule.id,
            starts_at=TEST_DATE,
            ends_at=TEST_DATE + datetime.timedelta(hours=2),
            frequency=ScheduleFrequencies.WEEKLY.value,
            week_days_index=[1, 3],
            until=TEST_DATE + datetime.timedelta(weeks=1),
            schedule_events=[provider_schedule_event],
        )
        result = schedule_repo.get_schedule_recurring_blocks(
            user_id=schedule.user_id,
            starts_at=TEST_DATE,
            until=(TEST_DATE + datetime.timedelta(weeks=2)),
        )
        assert result == [expected]

    def test_get_schedule_recurring_block_no_data(
        self,
        schedule_repo: ScheduleRecurringBlockRepository,
    ):
        result = schedule_repo.get_schedule_recurring_block(
            user_id=123,
            starts_at=TEST_DATE,
            ends_at=TEST_DATE + datetime.timedelta(hours=2),
            until=(TEST_DATE + datetime.timedelta(weeks=2)),
        )
        assert result is None

    def test_get_schedule_recurring_block(
        self,
        schedule_repo: ScheduleRecurringBlockRepository,
        schedule,
        schedule_recurring_block,
        provider_schedule_event,
    ):
        expected = ProviderScheduleRecurringBlock(
            id=schedule_recurring_block.id,
            schedule_id=schedule.id,
            starts_at=TEST_DATE,
            ends_at=TEST_DATE + datetime.timedelta(hours=2),
            frequency=ScheduleFrequencies.WEEKLY.value,
            week_days_index=[1, 3],
            until=TEST_DATE + datetime.timedelta(weeks=1),
            schedule_events=[provider_schedule_event],
        )
        result = schedule_repo.get_schedule_recurring_block(
            user_id=schedule.user_id,
            starts_at=TEST_DATE,
            ends_at=TEST_DATE + datetime.timedelta(hours=2),
            until=(TEST_DATE + datetime.timedelta(weeks=1)),
        )
        assert result == expected

    def test_get_schedule_recurring_block_by_id_no_data(
        self,
        schedule_repo: ScheduleRecurringBlockRepository,
    ):
        result = schedule_repo.get_schedule_recurring_block_by_id(
            schedule_recurring_block_id=12345,
        )
        assert result is None

    def test_get_schedule_recurring_block_by_id(
        self,
        schedule_repo: ScheduleRecurringBlockRepository,
        schedule,
        schedule_recurring_block,
        provider_schedule_event,
    ):
        expected = ProviderScheduleRecurringBlock(
            id=schedule_recurring_block.id,
            schedule_id=schedule.id,
            starts_at=TEST_DATE,
            ends_at=TEST_DATE + datetime.timedelta(hours=2),
            frequency=ScheduleFrequencies.WEEKLY.value,
            week_days_index=[1, 3],
            until=TEST_DATE + datetime.timedelta(weeks=1),
            schedule_events=[provider_schedule_event],
        )
        result = schedule_repo.get_schedule_recurring_block_by_id(
            schedule_recurring_block_id=schedule_recurring_block.id,
        )
        assert result == expected

    def test_get_schedule_recurring_block_by_schedule_event_no_data(
        self,
        schedule_repo: ScheduleRecurringBlockRepository,
    ):
        result = schedule_repo.get_schedule_recurring_block_by_schedule_event(
            schedule_event_id=12345,
        )
        assert result == []

    def test_get_schedule_recurring_block_by_schedule_event(
        self,
        schedule_repo: ScheduleRecurringBlockRepository,
        schedule,
        schedule_event,
        schedule_recurring_block,
        provider_schedule_event,
        factories,
    ):
        event_2 = factories.ScheduleEventFactory.create(
            schedule=schedule,
            schedule_recurring_block=schedule_recurring_block,
            starts_at=TEST_DATE + datetime.timedelta(days=1),
            ends_at=TEST_DATE
            + datetime.timedelta(days=1)
            + datetime.timedelta(hours=2),
        )
        event_2_schedule_event = ProviderScheduleEvent(
            id=event_2.id,
            state=event_2.state,
            starts_at=event_2.starts_at,
            ends_at=event_2.ends_at,
        )

        expected = ProviderScheduleRecurringBlock(
            id=schedule_recurring_block.id,
            schedule_id=schedule.id,
            starts_at=TEST_DATE,
            ends_at=TEST_DATE + datetime.timedelta(hours=2),
            frequency=ScheduleFrequencies.WEEKLY.value,
            week_days_index=[1, 3],
            until=TEST_DATE + datetime.timedelta(weeks=1),
            schedule_events=[provider_schedule_event, event_2_schedule_event],
        )
        result = schedule_repo.get_schedule_recurring_block_by_schedule_event(
            schedule_event_id=schedule_event.id,
        )
        assert result == [expected]

        result = schedule_repo.get_schedule_recurring_block_by_schedule_event(
            schedule_event_id=event_2.id,
        )
        assert result == [expected]

    def test_get_count_existing_appointments_in_schedule_recurring_block_no_match(
        self,
        schedule_repo: ScheduleRecurringBlockRepository,
        schedule,
        factories,
    ):
        now = datetime.datetime.utcnow()
        user = schedule.user
        factories.PractitionerProfileFactory.create(user_id=user.id)
        result = (
            schedule_repo.get_count_existing_appointments_in_schedule_recurring_block(
                user_id=schedule.user_id,
                starts_at=now,
                ends_at=now + datetime.timedelta(minutes=30),
            )
        )
        assert result == 0

    def test_get_count_existing_appointments_in_schedule_recurring_block(
        self,
        schedule_repo: ScheduleRecurringBlockRepository,
        schedule_recurring_block,
        valid_appointment_with_user,
        factories,
    ):
        now = datetime.datetime.utcnow()
        user = schedule_recurring_block.schedule.user
        factories.PractitionerProfileFactory.create(user_id=user.id)
        valid_appointment_with_user(
            practitioner=schedule_recurring_block.schedule.user,
            scheduled_start=now,
            scheduled_end=now + datetime.timedelta(minutes=30),
        )
        result = (
            schedule_repo.get_count_existing_appointments_in_schedule_recurring_block(
                user_id=schedule_recurring_block.schedule.user_id,
                starts_at=schedule_recurring_block.starts_at,
                ends_at=now + datetime.timedelta(minutes=30),
            )
        )
        assert result == 1

    def test_create(
        self,
        schedule_repo: ScheduleRecurringBlockRepository,
        schedule,
    ):
        result = schedule_repo.create(
            starts_at=TEST_DATE,
            ends_at=TEST_DATE + datetime.timedelta(hours=2),
            frequency=ScheduleFrequencies.WEEKLY,
            until=TEST_DATE + datetime.timedelta(weeks=1),
            schedule_id=schedule.id,
            week_days_index=[3, 5],
        )
        expected = ProviderScheduleRecurringBlock(
            id=result.id,
            schedule_id=schedule.id,
            starts_at=TEST_DATE,
            ends_at=TEST_DATE + datetime.timedelta(hours=2),
            frequency=ScheduleFrequencies.WEEKLY.value,
            week_days_index=[3, 5],
            until=TEST_DATE + datetime.timedelta(weeks=1),
        )
        assert result == expected

    def test_update_latest_date_events_created(
        self,
        schedule_repo: ScheduleRecurringBlockRepository,
        schedule,
        schedule_recurring_block,
    ):
        result = schedule_repo.update_latest_date_events_created(
            schedule_recurring_block_id=schedule_recurring_block.id,
            date=TEST_DATE + datetime.timedelta(hours=2),
        )
        expected = ProviderScheduleRecurringBlock(
            id=result.id,
            schedule_id=schedule.id,
            starts_at=TEST_DATE,
            ends_at=TEST_DATE + datetime.timedelta(hours=2),
            frequency=ScheduleFrequencies.WEEKLY.value,
            week_days_index=[1, 3],
            until=TEST_DATE + datetime.timedelta(weeks=1),
            latest_date_events_created=TEST_DATE + datetime.timedelta(hours=2),
        )
        assert result == expected


class TestScheduleEventRepository:
    def test_create(
        self,
        schedule_event_repo: ScheduleEventRepository,
        schedule,
        schedule_recurring_block,
    ):
        result = schedule_event_repo.create(
            starts_at=TEST_DATE,
            ends_at=TEST_DATE + datetime.timedelta(hours=2),
            schedule_recurring_block_id=schedule_recurring_block.id,
        )
        expected = ProviderScheduleEvent(
            id=result.id,
            starts_at=TEST_DATE,
            ends_at=TEST_DATE + datetime.timedelta(hours=2),
            schedule_recurring_block_id=schedule_recurring_block.id,
        )
        assert result == expected
