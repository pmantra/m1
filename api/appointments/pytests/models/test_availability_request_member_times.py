import datetime

import pytest

from appointments.models.availability_notification_request import (
    AvailabilityNotificationRequest,
)
from appointments.models.availability_request_member_times import (
    AvailabilityRequestMemberTimes,
)

now = datetime.datetime.utcnow()


@pytest.fixture
def new_request(member_with_add_appointment, practitioner_user):
    def make_new_request():
        args = {
            "practitioner_id": practitioner_user().id,
            "availabilities": [
                {
                    "start_time": now.time(),
                    "end_time": (now + datetime.timedelta(hours=1)).time(),
                    "start_date": datetime.date.today(),
                    "end_date": datetime.date.today() + datetime.timedelta(days=3),
                },
                {
                    "start_time": now.time(),
                    "end_time": (now + datetime.timedelta(hours=1)).time(),
                    "start_date": datetime.date.today(),
                    "end_date": None,
                },
            ],
        }
        new_notification_request = AvailabilityNotificationRequest(
            member_id=member_with_add_appointment.id,
            practitioner_id=args["practitioner_id"],
        )
        return args, new_notification_request

    return make_new_request


def test_create_availability_request_member_times(new_request):
    args, new_notification_request = new_request()
    member_times = []
    for a in args["availabilities"]:
        member_times.append(
            AvailabilityRequestMemberTimes(
                availability_notification_request_id=new_notification_request.id,
                start_time=a["start_time"],
                end_time=a["end_time"],
                start_date=a["start_date"],
                end_date=a["end_date"],
            )
        )

    assert len(member_times) == 2
    assert not member_times[1].end_date


def test_separate_by_day_single_day():
    a = {
        "start_time": "09:00AM",
        "end_time": "11:00AM",
        "start_date": (now + datetime.timedelta(days=1)).date(),
        "end_date": (now + datetime.timedelta(days=1)).date(),
    }

    armt = AvailabilityRequestMemberTimes(
        availability_notification_request_id=1,
        start_time=a["start_time"],
        end_time=a["end_time"],
        start_date=a["start_date"],
        end_date=a["end_date"],
    )

    actual = armt.separate_by_day()

    assert len(actual) == 1
    assert actual[0].start_time == a["start_time"]
    assert actual[0].end_time == a["end_time"]
    assert actual[0].start_date == a["start_date"]
    assert actual[0].end_date == a["end_date"]


def test_separate_by_day_span():
    first_day = (now + datetime.timedelta(days=1)).date()
    second_day = (now + datetime.timedelta(days=2)).date()
    third_day = (now + datetime.timedelta(days=3)).date()
    a = {
        "start_time": "09:00AM",
        "end_time": "11:00AM",
        "start_date": first_day,
        "end_date": third_day,
    }

    armt = AvailabilityRequestMemberTimes(
        availability_notification_request_id=1,
        start_time=a["start_time"],
        end_time=a["end_time"],
        start_date=a["start_date"],
        end_date=a["end_date"],
    )

    actual = armt.separate_by_day()

    assert len(actual) == 3
    assert actual[0].start_time == a["start_time"]
    assert actual[0].end_time == a["end_time"]
    assert actual[0].start_date == first_day
    assert actual[0].end_date == first_day

    assert actual[1].start_time == a["start_time"]
    assert actual[1].end_time == a["end_time"]
    assert actual[1].start_date == second_day
    assert actual[1].end_date == second_day

    assert actual[2].start_time == a["start_time"]
    assert actual[2].end_time == a["end_time"]
    assert actual[2].start_date == third_day
    assert actual[2].end_date == third_day
