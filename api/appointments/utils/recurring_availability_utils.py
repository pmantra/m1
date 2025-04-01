import datetime
from typing import Tuple

from utils.log import logger

log = logger(__name__)

EVENT_TYPE_START = 1
# value of EVNET_TYPE_END needs to be smaller than EVENT_TYPE_START so that
# if two events have the same timestamp, event end happens first
EVNET_TYPE_END = -1


def check_conflicts_between_two_event_series(
    event_series_a: list[Tuple[datetime.datetime, datetime.datetime]],
    event_series_b: list[Tuple[datetime.datetime, datetime.datetime]],
) -> bool:
    """
    Given two lists of intervals containing Tuple[start time, end time], return if there exists any overlap

    This functions uses the line sweep algorithm to check for overlaps between two time intervals.
    Each time point can be considered an event, ex., start event, end event.
    These events are sorted based on timestamps with ascending order.
    We iterate through these events while keeping track of current count of open events.
    If we find a start event, increment current_count_of_concurrent_event by 1;
    if we find an end event, decrease current_count_of_concurrent_event by 1.
    If current_count_of_concurrent_event is larger than 1 at any moment, it means at least two events
    have time overlap.
    """

    current_count_of_concurrent_event = 0
    events: list[tuple] = []

    for start, end in event_series_a:
        events.append((start, EVENT_TYPE_START))
        events.append((end, EVNET_TYPE_END))

    for start, end in event_series_b:
        events.append((start, EVENT_TYPE_START))
        events.append((end, EVNET_TYPE_END))

    events.sort(key=lambda x: (x[0], x[1]))

    for _, event_type in events:
        if event_type == EVENT_TYPE_START:
            current_count_of_concurrent_event += 1
            if current_count_of_concurrent_event > 1:
                return True
        else:
            current_count_of_concurrent_event -= 1

    return False
