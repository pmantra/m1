from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from modules.util.scheduling_utils import (
    Schedule,
    _get_today_schedule_times,
    _is_within_window,
    should_run_task,
    task_scheduled_to_run,
)


def test_is_within_window():
    """Test the window time comparison logic"""
    base_time = datetime(2024, 1, 1, 18, 0)  # 18:00

    test_cases = [
        (base_time - timedelta(minutes=1), False),  # Just before window
        (base_time, True),  # Start of window
        (base_time + timedelta(minutes=10), True),  # Middle of window
        (base_time + timedelta(minutes=19), True),  # Just inside window
        (base_time + timedelta(minutes=20), True),  # End of window
        (base_time + timedelta(minutes=21), False),  # Just outside window
    ]

    for current_time, expected in test_cases:
        assert (
            _is_within_window(current_time, base_time) == expected
        ), f"Failed for time: {current_time}"


def test_get_today_schedule_times():
    """Test schedule time generation for different schedule types"""
    test_cases = [
        # Four times daily tests
        (
            datetime(2024, 1, 2, 12, 0),  # Non-special day
            Schedule.FOUR_TIMES_DAILY.value,
            [12, 15, 18, 21],
            [
                datetime(2024, 1, 2, 12, 0),
                datetime(2024, 1, 2, 15, 0),
                datetime(2024, 1, 2, 18, 0),
                datetime(2024, 1, 2, 21, 0),
            ],
        ),
        (
            datetime(2024, 1, 2, 12, 0),  # Test with fewer hours
            Schedule.FOUR_TIMES_DAILY.value,
            [12, 18],
            [datetime(2024, 1, 2, 12, 0), datetime(2024, 1, 2, 18, 0)],
        ),
        # Twice daily tests
        (
            datetime(2024, 1, 2, 12, 0),  # Multiple hours available
            Schedule.TWICE_DAILY.value,
            [0, 12, 18],
            [datetime(2024, 1, 2, 0, 0), datetime(2024, 1, 2, 18, 0)],
        ),
        (
            datetime(2024, 1, 2, 12, 0),  # Only one hour available
            Schedule.TWICE_DAILY.value,
            [18],
            [datetime(2024, 1, 2, 18, 0)],
        ),
        # Daily schedule tests - should use last hour
        (
            datetime(2024, 1, 1, 12, 0),  # Monday
            Schedule.DAILY.value,
            [12, 15, 18, 21],
            [datetime(2024, 1, 1, 21, 0)],
        ),
        (
            datetime(2024, 1, 1, 12, 0),  # Single hour
            Schedule.DAILY.value,
            [18],
            [datetime(2024, 1, 1, 18, 0)],
        ),
        # Weekly schedule tests - should only run on Mondays at last hour
        (
            datetime(2024, 1, 1, 12, 0),  # Monday
            Schedule.WEEKLY.value,
            [12, 15, 18, 21],
            [datetime(2024, 1, 1, 21, 0)],
        ),
        (
            datetime(2024, 1, 2, 12, 0),  # Tuesday - should not run
            Schedule.WEEKLY.value,
            [12, 15, 18, 21],
            [],
        ),
        # Biweekly schedule tests - should run on 1st, 15th, 29th at last hour
        (
            datetime(2024, 1, 1, 12, 0),  # 1st of month
            Schedule.BIWEEKLY.value,
            [12, 15, 18, 21],
            [datetime(2024, 1, 1, 21, 0)],
        ),
        (
            datetime(2024, 1, 15, 12, 0),  # 15th of month
            Schedule.BIWEEKLY.value,
            [12, 15, 18, 21],
            [datetime(2024, 1, 15, 21, 0)],
        ),
        (
            datetime(2024, 1, 2, 12, 0),  # Non-biweekly day
            Schedule.BIWEEKLY.value,
            [12, 15, 18, 21],
            [],
        ),
    ]

    for current_time, schedule_type, base_hours, expected_times in test_cases:
        result = _get_today_schedule_times(
            schedule_type, base_hours, reference_date=current_time
        )
        assert (
            result == expected_times
        ), f"Failed for {schedule_type} on {current_time} with hours {base_hours}"


@pytest.mark.parametrize(
    "current_time,schedule_type,dag_schedule,expected_result",
    [
        # FOUR_TIMES_DAILY tests
        (
            datetime(2024, 1, 1, 12, 0),
            Schedule.FOUR_TIMES_DAILY.value,
            "0 12,15,18,21 * * *",
            True,
        ),  # At first time
        (
            datetime(2024, 1, 1, 15, 0),
            Schedule.FOUR_TIMES_DAILY.value,
            "0 12,15,18,21 * * *",
            True,
        ),  # At second time
        (
            datetime(2024, 1, 1, 18, 0),
            Schedule.FOUR_TIMES_DAILY.value,
            "0 12,15,18,21 * * *",
            True,
        ),  # At third time
        (
            datetime(2024, 1, 1, 21, 0),
            Schedule.FOUR_TIMES_DAILY.value,
            "0 12,15,18,21 * * *",
            True,
        ),  # At fourth time
        (
            datetime(2024, 1, 1, 13, 0),
            Schedule.FOUR_TIMES_DAILY.value,
            "0 12,15,18,21 * * *",
            False,
        ),  # Between times
        # TWICE_DAILY tests with multiple hours
        (
            datetime(2024, 1, 1, 0, 0),
            Schedule.TWICE_DAILY.value,
            "0 0,12,18 * * *",
            True,
        ),  # At first time
        (
            datetime(2024, 1, 1, 18, 0),
            Schedule.TWICE_DAILY.value,
            "0 0,12,18 * * *",
            True,
        ),  # At last time
        (
            datetime(2024, 1, 1, 12, 0),
            Schedule.TWICE_DAILY.value,
            "0 0,12,18 * * *",
            False,
        ),  # At middle time (should not run)
        # TWICE_DAILY tests with single hour
        (
            datetime(2024, 1, 1, 18, 0),
            Schedule.TWICE_DAILY.value,
            "0 18 * * *",
            True,
        ),  # Single hour available
        # DAILY tests
        (
            datetime(2024, 1, 1, 21, 0),
            Schedule.DAILY.value,
            "0 12,15,18,21 * * *",
            True,
        ),  # At last hour
        (
            datetime(2024, 1, 1, 18, 0),
            Schedule.DAILY.value,
            "0 12,15,18,21 * * *",
            False,
        ),  # Not at last hour
        # WEEKLY tests
        (
            datetime(2024, 1, 1, 21, 0),  # Monday
            Schedule.WEEKLY.value,
            "0 12,15,18,21 * * *",
            True,
        ),  # Monday at last hour
        (
            datetime(2024, 1, 2, 21, 0),  # Tuesday
            Schedule.WEEKLY.value,
            "0 12,15,18,21 * * *",
            False,
        ),  # Not Monday
        # BIWEEKLY tests
        (
            datetime(2024, 1, 1, 21, 0),  # 1st of month
            Schedule.BIWEEKLY.value,
            "0 12,15,18,21 * * *",
            True,
        ),  # 1st at last hour
        (
            datetime(2024, 1, 2, 21, 0),  # 2nd of month
            Schedule.BIWEEKLY.value,
            "0 12,15,18,21 * * *",
            False,
        ),  # Not on 1st/15th/29th
    ],
)
def test_task_scheduled_to_run_parametrized(
    current_time, schedule_type, dag_schedule, expected_result
):
    """Test task_scheduled_to_run with various scenarios"""
    result = task_scheduled_to_run(
        schedule_type, dag_schedule, current_time=current_time
    )
    assert result == expected_result


def test_task_scheduled_to_run_invalid_schedule():
    """Test behavior with invalid schedule format"""
    test_time = datetime(2024, 1, 1, 0, 0)
    result = task_scheduled_to_run(
        Schedule.DAILY.value, "invalid schedule", current_time=test_time
    )
    assert result is False


def test_task_scheduled_to_run_window():
    """Test the time window functionality"""
    # Test daily schedule at last hour
    base_time = datetime(2024, 1, 1, 21, 0)  # Monday at 21:00

    test_times = [
        (base_time - timedelta(minutes=1), False),  # Just before window
        (base_time, True),  # Start of window
        (base_time + timedelta(minutes=10), True),  # Middle of window
        (base_time + timedelta(minutes=19), True),  # Just inside window
        (base_time + timedelta(minutes=20), True),  # End of window
        (base_time + timedelta(minutes=21), False),  # Just outside window
    ]

    for test_time, expected in test_times:
        result = task_scheduled_to_run(
            Schedule.DAILY.value, "0 12,15,18,21 * * *", current_time=test_time
        )
        assert result == expected, f"Failed for time: {test_time}"

    # Test daily schedule on different day
    next_day_time = datetime(2024, 1, 2, 21, 0)  # Tuesday at 21:00
    result = task_scheduled_to_run(
        Schedule.DAILY.value, "0 12,15,18,21 * * *", current_time=next_day_time
    )
    assert result is True, f"Should run on any day: {next_day_time}"

    # Test weekly schedule on non-Monday
    non_monday_time = datetime(2024, 1, 2, 21, 0)  # Tuesday at 21:00
    result = task_scheduled_to_run(
        Schedule.WEEKLY.value, "0 12,15,18,21 * * *", current_time=non_monday_time
    )
    assert (
        result is False
    ), f"Weekly schedule should not run on non-Monday: {non_monday_time}"


class TestShouldRunTask:
    """Tests for should_run_task function"""

    @pytest.fixture
    def mock_task_instance(self):
        class MockTaskInstance:
            def __init__(self, ld_config):
                self._ld_config = ld_config

            def xcom_pull(self, task_ids):
                assert task_ids == "get_launchdarkly_config"
                return self._ld_config

        return MockTaskInstance

    def test_payer_not_enabled_in_launch_darkly(self, mock_task_instance):
        """Test that function returns False when payer is not enabled in Launch Darkly"""
        ti = mock_task_instance({"enabled_payers": ["other_payer"]})
        test_time = datetime(2024, 1, 1, 18, 5)
        with patch("modules.util.scheduling_utils.datetime") as mock_dt:
            mock_dt.utcnow.return_value = test_time
            result = should_run_task(
                task_instance=ti,
                payer="test_payer",
                schedule=Schedule.DAILY.value,
                job_type="file_generation",
                default_payers=["test_payer", "other_payer"],
                dag=Mock(schedule_interval="0 12,15,18,21 * * *"),
                dag_run=Mock(conf={}),
            )
        assert result is False

    def test_not_scheduled_and_not_off_schedule(self, mock_task_instance):
        """Test that function returns False when not scheduled and not set to run off schedule"""
        ti = mock_task_instance({"enabled_payers": ["test_payer"]})
        test_time = datetime(2024, 1, 1, 12, 0)  # Not within schedule window
        with patch("modules.util.scheduling_utils.datetime") as mock_dt:
            mock_dt.utcnow.return_value = test_time
            result = should_run_task(
                task_instance=ti,
                payer="test_payer",
                schedule=Schedule.DAILY.value,
                job_type="file_generation",
                default_payers=["test_payer"],
                dag=Mock(schedule_interval="0 12,15,18,21 * * *"),
                dag_run=Mock(conf={"run_off_schedule": False}),
            )
        assert result is False

    def test_not_scheduled_but_off_schedule_allowed(self, mock_task_instance):
        """Test that function returns True when not scheduled but run_off_schedule is True"""
        ti = mock_task_instance({"enabled_payers": ["test_payer"]})
        test_time = datetime(2024, 1, 1, 12, 0)  # Not within schedule window
        with patch("modules.util.scheduling_utils.datetime") as mock_dt:
            mock_dt.utcnow.return_value = test_time
            result = should_run_task(
                task_instance=ti,
                payer="test_payer",
                schedule=Schedule.DAILY.value,
                job_type="file_generation",
                default_payers=["test_payer"],
                dag=Mock(schedule_interval="0 12,15,18,21 * * *"),
                dag_run=Mock(conf={"run_off_schedule": True}),
            )
        assert result is True

    def test_payer_not_in_payers_list(self, mock_task_instance):
        """Test that function returns False when payer is not in the specified payers list"""
        ti = mock_task_instance({"enabled_payers": ["test_payer"]})
        test_time = datetime(2024, 1, 1, 21, 5)  # Within schedule window
        with patch("modules.util.scheduling_utils.datetime") as mock_dt:
            mock_dt.utcnow.return_value = test_time
            result = should_run_task(
                task_instance=ti,
                payer="test_payer",
                schedule=Schedule.DAILY.value,
                job_type="file_generation",
                default_payers=["test_payer"],
                dag=Mock(schedule_interval="0 12,15,18,21 * * *"),
                dag_run=Mock(conf={"payers": ["other_payer"]}),
            )
        assert result is False

    def test_empty_payers_list_runs_all_enabled(self, mock_task_instance):
        """Test that function returns True for enabled payer when payers list is empty"""
        ti = mock_task_instance({"enabled_payers": ["test_payer"]})
        test_time = datetime(2024, 1, 1, 21, 5)  # Within schedule window
        with patch("modules.util.scheduling_utils.datetime") as mock_dt:
            mock_dt.utcnow.return_value = test_time
            result = should_run_task(
                task_instance=ti,
                payer="test_payer",
                schedule=Schedule.DAILY.value,
                job_type="file_generation",
                default_payers=["test_payer"],
                dag=Mock(schedule_interval="0 12,15,18,21 * * *"),
                dag_run=Mock(conf={}),  # Empty conf
            )
        assert result is True

    def test_scheduled_and_in_payers_list(self, mock_task_instance):
        """Test that function returns True when scheduled and payer is in payers list"""
        ti = mock_task_instance({"enabled_payers": ["test_payer"]})
        test_time = datetime(2024, 1, 1, 21, 5)  # Within schedule window
        with patch("modules.util.scheduling_utils.datetime") as mock_dt:
            mock_dt.utcnow.return_value = test_time
            result = should_run_task(
                task_instance=ti,
                payer="test_payer",
                schedule=Schedule.DAILY.value,
                job_type="file_generation",
                default_payers=["test_payer"],
                dag=Mock(schedule_interval="0 12,15,18,21 * * *"),
                dag_run=Mock(conf={"payers": ["test_payer"]}),
            )
        assert result is True

    def test_uses_default_payers_when_no_launch_darkly_config(self, mock_task_instance):
        """Test that function uses default_payers when Launch Darkly config is empty"""
        ti = mock_task_instance({})  # Empty LD config
        test_time = datetime(2024, 1, 1, 21, 5)
        with patch("modules.util.scheduling_utils.datetime") as mock_dt:
            mock_dt.utcnow.return_value = test_time
            result = should_run_task(
                task_instance=ti,
                payer="test_payer",
                schedule=Schedule.DAILY.value,
                job_type="file_generation",
                default_payers=["test_payer"],
                dag=Mock(schedule_interval="0 12,15,18,21 * * *"),
                dag_run=Mock(conf={}),
            )
        assert result is True
