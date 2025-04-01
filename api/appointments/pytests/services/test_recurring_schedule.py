import datetime
from unittest.mock import MagicMock, call, patch

import pytest

from appointments.models.constants import ScheduleFrequencies, ScheduleStates
from appointments.models.provider_schedules import (
    ProviderScheduleEvent,
    ProviderScheduleRecurringBlock,
)
from appointments.services.recurring_schedule import (
    RecurringScheduleAvailabilityService,
)

TEST_DATE = datetime.datetime(
    2024, 4, 1, 10, 0, 0, tzinfo=datetime.timezone.utc
).replace(tzinfo=None)


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


@pytest.fixture
def provider_schedule_recurring_block(
    schedule_recurring_block, provider_schedule_event
):
    return ProviderScheduleRecurringBlock(
        id=schedule_recurring_block.id,
        schedule_id=schedule_recurring_block.schedule.id,
        starts_at=TEST_DATE,
        ends_at=TEST_DATE + datetime.timedelta(hours=2),
        frequency=ScheduleFrequencies.WEEKLY.value,
        week_days_index=[1, 3],
        until=TEST_DATE + datetime.timedelta(weeks=1),
        schedule_events=[provider_schedule_event],
    )


class TestRecurringScheduleAvailabilityService:
    def test_get_schedule_recurring_block_by_user_and_date_range_no_result(
        self,
        recurring_schedule_service: RecurringScheduleAvailabilityService,
        mock_schedule_recurring_block_repo: MagicMock,
        mock_schedule_event_repo: MagicMock,
        schedule_recurring_block,
        schedule_event,
        provider_schedule_recurring_block,
    ):
        mock_schedule_recurring_block_repo.get_schedule_recurring_blocks.return_value = (
            []
        )
        result = recurring_schedule_service.get_schedule_recurring_block_by_user_and_date_range(
            user_id=schedule_event.schedule.user_id,
            starts_at=TEST_DATE,
            until=TEST_DATE + datetime.timedelta(weeks=1),
        )
        assert result == []

    def test_get_schedule_recurring_block_by_user_and_date_range_result(
        self,
        recurring_schedule_service: RecurringScheduleAvailabilityService,
        mock_schedule_recurring_block_repo: MagicMock,
        mock_schedule_event_repo: MagicMock,
        schedule_recurring_block,
        schedule_event,
        provider_schedule_recurring_block,
    ):
        mock_schedule_recurring_block_repo.get_schedule_recurring_blocks.return_value = [
            provider_schedule_recurring_block
        ]
        result = recurring_schedule_service.get_schedule_recurring_block_by_user_and_date_range(
            user_id=schedule_event.schedule.user_id,
            starts_at=TEST_DATE,
            until=TEST_DATE + datetime.timedelta(weeks=1),
        )
        assert len(result) == 1
        result = result[0]
        assert result.id == provider_schedule_recurring_block.id
        assert result.schedule_id == provider_schedule_recurring_block.schedule_id
        assert result.starts_at == provider_schedule_recurring_block.starts_at
        assert result.ends_at == provider_schedule_recurring_block.ends_at
        assert result.frequency == provider_schedule_recurring_block.frequency
        assert (
            result.week_days_index == provider_schedule_recurring_block.week_days_index
        )
        assert result.until == provider_schedule_recurring_block.until

    def test_get_exact_schedule_recurring_block_by_user_and_date_range_no_result(
        self,
        recurring_schedule_service: RecurringScheduleAvailabilityService,
        mock_schedule_recurring_block_repo: MagicMock,
        mock_schedule_event_repo: MagicMock,
        schedule_recurring_block,
        schedule_event,
        provider_schedule_recurring_block,
    ):
        mock_schedule_recurring_block_repo.get_schedule_recurring_block.return_value = (
            None
        )
        result = recurring_schedule_service.get_exact_schedule_recurring_block_by_user_and_date_range(
            user_id=schedule_event.schedule.user_id,
            starts_at=TEST_DATE,
            ends_at=TEST_DATE + datetime.timedelta(hours=2),
            until=TEST_DATE + datetime.timedelta(weeks=1),
        )
        assert result is None

    def test_get_exact_schedule_recurring_block_by_user_and_date_range_range_result(
        self,
        recurring_schedule_service: RecurringScheduleAvailabilityService,
        mock_schedule_recurring_block_repo: MagicMock,
        mock_schedule_event_repo: MagicMock,
        schedule_recurring_block,
        schedule_event,
        provider_schedule_recurring_block,
    ):
        mock_schedule_recurring_block_repo.get_schedule_recurring_block.return_value = (
            provider_schedule_recurring_block
        )
        result = recurring_schedule_service.get_exact_schedule_recurring_block_by_user_and_date_range(
            user_id=schedule_event.schedule.user_id,
            starts_at=TEST_DATE,
            ends_at=TEST_DATE + datetime.timedelta(hours=2),
            until=TEST_DATE + datetime.timedelta(weeks=1),
        )
        assert result.id == provider_schedule_recurring_block.id
        assert result.schedule_id == provider_schedule_recurring_block.schedule_id
        assert result.starts_at == provider_schedule_recurring_block.starts_at
        assert result.ends_at == provider_schedule_recurring_block.ends_at
        assert result.frequency == provider_schedule_recurring_block.frequency
        assert (
            result.week_days_index == provider_schedule_recurring_block.week_days_index
        )
        assert result.until == provider_schedule_recurring_block.until

    @patch("appointments.services.recurring_schedule.abort")
    def test_detect_booked_appointments_in_block(
        self,
        mock_abort,
        recurring_schedule_service: RecurringScheduleAvailabilityService,
        mock_schedule_recurring_block_repo: MagicMock,
        schedule_recurring_block,
    ):
        mock_schedule_recurring_block_repo._get_count_existing_appointments_in_schedule_recurring_block.return_value = (
            1
        )

        second_event_start_datetime = datetime.datetime(2024, 4, 3, 10, 0, 0)
        mock_event = ProviderScheduleEvent(
            id=55555,
            state=ScheduleStates.available,
            starts_at=second_event_start_datetime,
            ends_at=second_event_start_datetime + datetime.timedelta(hours=2),
        )
        mock_block = ProviderScheduleRecurringBlock(
            id=12345,
            schedule_id=schedule_recurring_block.schedule.id,
            starts_at=TEST_DATE,
            ends_at=TEST_DATE + datetime.timedelta(hours=2),
            frequency=ScheduleFrequencies.WEEKLY.value,
            week_days_index=[1, 3],
            until=TEST_DATE + datetime.timedelta(weeks=1),
            schedule_events=[mock_event],
            latest_date_events_created=TEST_DATE + datetime.timedelta(hours=2),
        )
        mock_schedule_recurring_block_repo.get_schedule_recurring_block_by_id.return_value = (
            mock_block
        )

        recurring_schedule_service.detect_booked_appointments_in_block(
            schedule_recurring_block_id=schedule_recurring_block.id,
            user_id=schedule_recurring_block.schedule.user_id,
        )
        assert mock_abort.called_once()

    @patch("appointments.services.schedule.abort")
    def test_detect_schedule_recurring_block_conflict(
        self,
        mock_abort,
        recurring_schedule_service: RecurringScheduleAvailabilityService,
        schedule,
        schedule_event,
        schedule_recurring_block,
        mock_schedule_recurring_block_repo: MagicMock,
    ):
        ends_at = TEST_DATE + datetime.timedelta(hours=2)
        until = TEST_DATE + datetime.timedelta(weeks=1)
        schedule_id = schedule.id
        frequency = ScheduleFrequencies.WEEKLY.value
        week_days_index = [0]
        member_timezone = "America/New_York"

        mock_schedule_recurring_block_repo.create.return_value = (
            provider_schedule_recurring_block
        )
        expected_occurrences = [
            (TEST_DATE, ends_at),
            (
                TEST_DATE + datetime.timedelta(days=7),
                ends_at + datetime.timedelta(days=7),
            ),
        ]

        with patch(
            "appointments.services.recurring_schedule.RecurringScheduleAvailabilityService._occurrences",
            return_value=expected_occurrences,
        ):
            recurring_schedule_service.create_schedule_recurring_block(
                starts_at=TEST_DATE,
                ends_at=ends_at,
                frequency=frequency,
                until=until,
                schedule_id=schedule_id,
                week_days_index=week_days_index,
                member_timezone=member_timezone,
                user_id=schedule.user_id,
            )
        assert mock_abort.called_once()

    def test_create_schedule_recurring_block(
        self,
        recurring_schedule_service: RecurringScheduleAvailabilityService,
        schedule,
        mock_schedule_recurring_block_repo: MagicMock,
    ):
        mock_schedule_recurring_block_repo.get_schedule_recurring_block.return_value = (
            None
        )
        ends_at = TEST_DATE + datetime.timedelta(hours=2)
        until = TEST_DATE + datetime.timedelta(weeks=1)
        schedule_id = schedule.id
        frequency = ScheduleFrequencies.WEEKLY.value
        week_days_index = [0]
        member_timezone = "America/New_York"
        last_start_dt = TEST_DATE + datetime.timedelta(days=7)
        last_end_dt = ends_at + datetime.timedelta(days=7)

        mock_event = ProviderScheduleEvent(
            id=55555,
            state=ScheduleStates.available,
            starts_at=TEST_DATE,
            ends_at=TEST_DATE + datetime.timedelta(hours=2),
        )
        mock_block = ProviderScheduleRecurringBlock(
            id=12345,
            schedule_id=schedule.id,
            starts_at=TEST_DATE,
            ends_at=TEST_DATE + datetime.timedelta(hours=2),
            frequency=ScheduleFrequencies.WEEKLY.value,
            week_days_index=[1, 3],
            until=TEST_DATE + datetime.timedelta(weeks=1),
            schedule_events=[mock_event],
        )
        mock_schedule_recurring_block_repo.create.return_value = mock_block
        expected_occurrences = [
            (TEST_DATE, ends_at),
            (
                last_start_dt,
                last_end_dt,
            ),
        ]
        with patch(
            "appointments.services.recurring_schedule.RecurringScheduleAvailabilityService._occurrences",
            return_value=expected_occurrences,
        ), patch(
            "appointments.repository.schedules.ScheduleRecurringBlockRepository.update_latest_date_events_created",
        ) as mock_update_latest_date_events_created:
            result_id = recurring_schedule_service.create_schedule_recurring_block(
                starts_at=TEST_DATE,
                ends_at=ends_at,
                frequency=frequency,
                until=until,
                schedule_id=schedule_id,
                week_days_index=week_days_index,
                member_timezone=member_timezone,
                user_id=schedule.user_id,
            )
            assert result_id == mock_block.id

            expected_calls = [
                call(
                    starts_at=TEST_DATE,
                    ends_at=ends_at,
                    schedule_recurring_block_id=result_id,
                ),
                call(
                    starts_at=last_start_dt,
                    ends_at=last_end_dt,
                    schedule_recurring_block_id=result_id,
                ),
            ]
            recurring_schedule_service.schedule_event_repo.create.assert_has_calls(
                expected_calls, any_order=True
            )
            mock_update_latest_date_events_created.assert_called_with(
                schedule_recurring_block_id=mock_block.id,
                date=last_end_dt,
            )

    def test_create_schedule_recurring_block_partially_ran_creation(
        self,
        recurring_schedule_service: RecurringScheduleAvailabilityService,
        schedule,
        schedule_recurring_block,
        mock_schedule_recurring_block_repo: MagicMock,
    ):
        ends_at = TEST_DATE + datetime.timedelta(hours=2)
        until = TEST_DATE + datetime.timedelta(weeks=1)
        schedule_id = schedule.id
        frequency = ScheduleFrequencies.WEEKLY.value
        week_days_index = [1, 3]
        member_timezone = "America/New_York"
        schedule_recurring_block.latest_date_events_created = ends_at

        second_event_start_datetime = datetime.datetime(2024, 4, 3, 10, 0, 0)
        mock_event = ProviderScheduleEvent(
            id=55555,
            state=ScheduleStates.available,
            starts_at=second_event_start_datetime,
            ends_at=second_event_start_datetime + datetime.timedelta(hours=2),
        )
        mock_block = ProviderScheduleRecurringBlock(
            id=12345,
            schedule_id=schedule.id,
            starts_at=TEST_DATE,
            ends_at=TEST_DATE + datetime.timedelta(hours=2),
            frequency=ScheduleFrequencies.WEEKLY.value,
            week_days_index=[1, 3],
            until=TEST_DATE + datetime.timedelta(weeks=1),
            schedule_events=[mock_event],
            latest_date_events_created=TEST_DATE + datetime.timedelta(hours=2),
        )
        mock_schedule_recurring_block_repo.get_schedule_recurring_block.return_value = (
            mock_block
        )
        with patch(
            "appointments.services.recurring_schedule.RecurringScheduleAvailabilityService._occurrences",
        ) as mock_occurrences:
            recurring_schedule_service.create_schedule_recurring_block(
                starts_at=TEST_DATE,
                ends_at=ends_at,
                frequency=frequency,
                until=until,
                schedule_id=schedule_id,
                week_days_index=week_days_index,
                member_timezone=member_timezone,
                user_id=schedule.user_id,
            )
            mock_occurrences.assert_called_with(
                starts_at=TEST_DATE,
                ends_at=ends_at,
                start_range=ends_at,
                until_range=until,
                week_days_index=week_days_index,
                frequency=frequency,
                member_timezone=member_timezone,
            )
            mock_schedule_recurring_block_repo.create.assert_not_called()

    @patch("appointments.services.schedule.abort")
    def test_create_schedule_recurring_block_aborts_on_conflict(
        self,
        mock_abort,
        recurring_schedule_service: RecurringScheduleAvailabilityService,
        schedule,
        mock_schedule_recurring_block_repo: MagicMock,
        provider_schedule_recurring_block,
        schedule_event,
    ):
        ends_at = TEST_DATE + datetime.timedelta(hours=2)
        until = TEST_DATE + datetime.timedelta(weeks=1)
        schedule_id = schedule.id
        frequency = ScheduleFrequencies.WEEKLY.value
        week_days_index = [0]
        member_timezone = "America/New_York"

        mock_schedule_recurring_block_repo.create.return_value = (
            provider_schedule_recurring_block
        )

        expected_occurrences = [
            (TEST_DATE, ends_at),
            (
                TEST_DATE + datetime.timedelta(days=7),
                ends_at + datetime.timedelta(days=7),
            ),
        ]
        with patch(
            "appointments.services.recurring_schedule.RecurringScheduleAvailabilityService._occurrences",
            return_value=expected_occurrences,
        ):
            recurring_schedule_service.create_schedule_recurring_block(
                starts_at=TEST_DATE,
                ends_at=ends_at,
                frequency=frequency,
                until=until,
                schedule_id=schedule_id,
                week_days_index=week_days_index,
                member_timezone=member_timezone,
                user_id=schedule.user_id,
            )
            assert mock_abort.called_once()

    def test_occurrences_daily(
        self,
        recurring_schedule_service: RecurringScheduleAvailabilityService,
    ):
        starts_at = TEST_DATE
        ends_at = starts_at + datetime.timedelta(hours=2)
        until_range = starts_at + datetime.timedelta(days=3)
        member_timezone = "America/New_York"

        expected_occurrences = [
            (
                starts_at + datetime.timedelta(days=i),
                ends_at + datetime.timedelta(days=i),
            )
            for i in range(4)
        ]
        # Convert expected occurrences to UTC for comparison
        expected_occurrences = [(start, end) for start, end in expected_occurrences]

        results = recurring_schedule_service._occurrences(
            starts_at=starts_at,
            ends_at=ends_at,
            start_range=TEST_DATE,
            until_range=until_range,
            week_days_index=[],
            frequency=ScheduleFrequencies.DAILY.value,
            member_timezone=member_timezone,
        )
        results = [(start, end) for start, end in results]
        assert results == expected_occurrences

    def test_occurrences_weekly_specific_days(
        self,
        recurring_schedule_service: RecurringScheduleAvailabilityService,
    ):
        starts_at = TEST_DATE
        ends_at = starts_at + datetime.timedelta(hours=2)
        until_range = starts_at + datetime.timedelta(
            weeks=2
        )  # Three Mondays in this range
        member_timezone = "America/New_York"

        result = recurring_schedule_service._occurrences(
            starts_at=starts_at,
            ends_at=ends_at,
            start_range=TEST_DATE,
            until_range=until_range,
            week_days_index=[0, 4],  # 0 == Monday, 4 == Friday
            frequency=ScheduleFrequencies.WEEKLY.value,
            member_timezone=member_timezone,
        )
        first_friday = datetime.datetime(2024, 4, 5, 10, 0, 0)
        next_monday = datetime.datetime(2024, 4, 8, 10, 0, 0)
        next_friday = datetime.datetime(2024, 4, 12, 10, 0, 0)
        last_monday = datetime.datetime(2024, 4, 15, 10, 0, 0)
        expected_occurrences = [
            (TEST_DATE, TEST_DATE + datetime.timedelta(hours=2)),
            (first_friday, first_friday + datetime.timedelta(hours=2)),
            (next_monday, next_monday + datetime.timedelta(hours=2)),
            (next_friday, next_friday + datetime.timedelta(hours=2)),
            (last_monday, last_monday + datetime.timedelta(hours=2)),
        ]
        expected_occurrences = [(start, end) for start, end in expected_occurrences]
        assert result == expected_occurrences

    def test_occurrences_weekly_on_daylight_savings(
        self,
        recurring_schedule_service: RecurringScheduleAvailabilityService,
    ):
        """
        Testing daylight savings handling.

        Daylight savings happens 3/10/24 in NY
        """
        # Setup the parameters for testing weekly occurrences on Mondays and Fridays
        DST_DATE = datetime.datetime(2024, 3, 10, 4, 0, 0)
        starts_at = DST_DATE
        ends_at = DST_DATE + datetime.timedelta(hours=6)
        until_range = DST_DATE + datetime.timedelta(days=3)
        member_timezone = "America/New_York"

        result = recurring_schedule_service._occurrences(
            starts_at=starts_at,
            ends_at=ends_at,
            start_range=DST_DATE,
            until_range=until_range,
            week_days_index=[],
            frequency=ScheduleFrequencies.DAILY.value,
            member_timezone=member_timezone,
        )
        second = datetime.datetime(2024, 3, 11, 4, 0, 0)
        third = datetime.datetime(2024, 3, 12, 4, 0, 0)
        fourth = datetime.datetime(2024, 3, 13, 4, 0, 0)
        # date handling is because only the very first start time is in -5 offset
        # the rest are -4
        expected_occurrences = [
            (DST_DATE, DST_DATE + datetime.timedelta(hours=5)),
            (
                second - datetime.timedelta(hours=1),
                second + datetime.timedelta(hours=5),
            ),
            (third - datetime.timedelta(hours=1), third + datetime.timedelta(hours=5)),
            (
                fourth - datetime.timedelta(hours=1),
                fourth + datetime.timedelta(hours=5),
            ),
        ]
        expected_occurrences = [(start, end) for start, end in expected_occurrences]
        assert result == expected_occurrences

    def test_delete_schedule_recurring_block(
        self,
        recurring_schedule_service: RecurringScheduleAvailabilityService,
        mock_schedule_recurring_block_repo: MagicMock,
    ):
        mock_schedule_recurring_block_repo.delete.return_value = 123

        recurring_schedule_service.delete_schedule_recurring_block(
            schedule_recurring_block_id=123,
            user_id=12345,
        )

        mock_schedule_recurring_block_repo.delete.assert_called_once_with(id=123)
