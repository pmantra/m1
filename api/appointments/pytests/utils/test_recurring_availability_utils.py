from datetime import datetime

import pytest

from appointments.utils.recurring_availability_utils import (
    check_conflicts_between_two_event_series,
)


@pytest.mark.parametrize(
    "event_series_a, event_series_b, expected, test_name",
    [
        (
            [
                (datetime(2024, 7, 29, 14, 20), datetime(2024, 7, 29, 16, 20)),
                (datetime(2024, 8, 2, 14, 20), datetime(2024, 8, 2, 16, 20)),
            ],
            [
                (datetime(2024, 8, 3, 14, 20), datetime(2024, 8, 3, 16, 20)),
                (datetime(2024, 8, 5, 14, 20), datetime(2024, 8, 5, 16, 20)),
            ],
            False,
            "no overlap",
        ),
        (
            [
                (datetime(2024, 7, 29, 14, 20), datetime(2024, 7, 29, 16, 20)),
                (datetime(2024, 8, 2, 14, 20), datetime(2024, 8, 2, 16, 20)),
            ],
            [
                (datetime(2024, 7, 29, 16, 20), datetime(2024, 7, 29, 18, 20)),
                (datetime(2024, 8, 5, 14, 20), datetime(2024, 8, 5, 16, 20)),
            ],
            False,
            "event A last time equals event B start time",
        ),
        (
            [
                (datetime(2024, 7, 29, 14, 20), datetime(2024, 7, 29, 16, 20)),
            ],
            [
                (datetime(2024, 7, 29, 12, 20), datetime(2024, 7, 29, 16, 20)),
            ],
            True,
            "overlap small range",
        ),
        (
            [
                (datetime(2024, 7, 29, 10, 20), datetime(2024, 7, 29, 18, 20)),
                (datetime(2024, 8, 2, 14, 20), datetime(2024, 8, 2, 16, 20)),
            ],
            [
                (datetime(2024, 7, 29, 12, 20), datetime(2024, 7, 29, 16, 20)),
            ],
            True,
            "overlap large range all inclusive",
        ),
        (
            [],
            [
                (datetime(2024, 7, 29, 12, 20), datetime(2024, 7, 29, 16, 20)),
            ],
            False,
            "empty series A",
        ),
        (
            [
                (datetime(2024, 7, 29, 10, 20), datetime(2024, 7, 29, 18, 20)),
                (datetime(2024, 8, 2, 14, 20), datetime(2024, 8, 2, 16, 20)),
            ],
            [],
            False,
            "empty series B",
        ),
        (
            [],
            [],
            False,
            "empty series for both",
        ),
        (
            [
                (datetime(2024, 7, 29, 10, 20), datetime(2024, 7, 29, 18, 20)),
                (datetime(2024, 7, 29, 19, 20), datetime(2024, 7, 29, 20, 20)),
            ],
            [
                (datetime(2024, 7, 29, 18, 20), datetime(2024, 7, 29, 19, 20)),
            ],
            False,
            "tight fit close events",
        ),
        (
            [
                (datetime(2024, 7, 29, 10, 20), datetime(2024, 7, 29, 18, 20)),
                (datetime(2024, 7, 29, 19, 20), datetime(2024, 7, 29, 20, 20)),
            ],
            [
                (datetime(2024, 7, 29, 18, 20), datetime(2024, 7, 29, 19, 21)),
            ],
            True,
            "overlap with one minute diff",
        ),
        (
            [
                (datetime(2024, 7, 29, 1, 20), datetime(2024, 7, 29, 2, 20)),
                (datetime(2024, 7, 29, 2, 20), datetime(2024, 7, 29, 3, 20)),
                (datetime(2024, 7, 29, 3, 20), datetime(2024, 7, 29, 4, 20)),
                (datetime(2024, 7, 29, 4, 20), datetime(2024, 7, 29, 5, 20)),
                (datetime(2024, 7, 29, 6, 20), datetime(2024, 7, 29, 7, 20)),
                (datetime(2024, 7, 29, 7, 20), datetime(2024, 7, 29, 8, 20)),
                (datetime(2024, 7, 29, 8, 20), datetime(2024, 7, 29, 9, 20)),
                (datetime(2024, 7, 29, 9, 20), datetime(2024, 7, 29, 10, 20)),
            ],
            [
                (datetime(2024, 7, 29, 1, 20), datetime(2024, 7, 29, 2, 20)),
                (datetime(2024, 7, 29, 2, 20), datetime(2024, 7, 29, 2, 50)),
                (datetime(2024, 7, 29, 3, 20), datetime(2024, 7, 29, 4, 20)),
                (datetime(2024, 7, 29, 4, 20), datetime(2024, 7, 29, 5, 20)),
                (datetime(2024, 7, 29, 6, 20), datetime(2024, 7, 29, 7, 20)),
                (datetime(2024, 7, 29, 7, 20), datetime(2024, 7, 29, 8, 20)),
                (datetime(2024, 7, 29, 8, 20), datetime(2024, 7, 29, 9, 20)),
                (datetime(2024, 7, 29, 9, 20), datetime(2024, 7, 29, 10, 20)),
            ],
            True,
            "many events",
        ),
        (
            [
                (datetime(2024, 7, 29, 10, 20), datetime(2024, 7, 29, 18, 20)),
                (datetime(2024, 7, 29, 19, 20), datetime(2024, 7, 29, 20, 20)),
            ],
            [
                (datetime(2024, 7, 29, 10, 20), datetime(2024, 7, 29, 18, 20)),
                (datetime(2024, 7, 29, 19, 20), datetime(2024, 7, 29, 20, 20)),
            ],
            True,
            "exactly the same intervals",
        ),
    ],
)
def test_check_conflicts_between_two_event_series(
    event_series_a, event_series_b, expected, test_name
):
    assert (
        check_conflicts_between_two_event_series(event_series_a, event_series_b)
        == expected
    ), f"Failed on: {test_name}"
