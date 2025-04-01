import datetime
import json
from unittest import mock

import pytest
import pytz

from appointments.models.availability_notification_request import (
    AvailabilityNotificationRequest,
)
from appointments.models.availability_request_member_times import (
    AvailabilityRequestMemberTimes,
)
from messaging.models.messaging import Message
from pytests.freezegun import freeze_time

now = datetime.datetime.utcnow()
NY_TZ = pytz.timezone("America/New_York")
# tz offset for now, do not use for past or future dates!
NY_TZ_OFFSET = datetime.datetime.now(NY_TZ).utcoffset().total_seconds() / 60


@pytest.fixture
def availability():
    return {
        "start_time": str((now + datetime.timedelta(hours=1)).astimezone(NY_TZ).time()),
        "end_time": str((now + datetime.timedelta(hours=2)).astimezone(NY_TZ).time()),
        "start_date": str((now + datetime.timedelta(days=2)).astimezone(NY_TZ).date()),
        "end_date": str((now + datetime.timedelta(days=4)).astimezone(NY_TZ).date()),
    }


def test_create_request_bad_practitioner(
    client, api_helpers, member_with_add_appointment, availability
):
    data = {
        "practitioner_id": 28725,
        "availabilities": [availability],
        "member_timezone": "America/New_York",
    }
    res = client.post(
        "/api/v1/availability_request",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member_with_add_appointment),
    )
    assert res.status_code == 400
    assert api_helpers.load_json(res)["message"] == "Invalid Practitioner ID"


def test_create_request_no_practitioner(
    client, api_helpers, member_with_add_appointment, availability
):
    data = {
        "practitioner_id": None,
        "availabilities": [availability],
        "member_timezone": "America/New_York",
    }
    res = client.post(
        "/api/v1/availability_request",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member_with_add_appointment),
    )
    assert res.status_code == 400
    assert api_helpers.load_json(res)["message"] == "Invalid Practitioner ID"


def test_no_create_request_no_phone(
    client, api_helpers, member_with_add_appointment, availability, practitioner_user
):
    member_with_add_appointment.member_profile.phone_number = None
    data = {
        "practitioner_id": practitioner_user().id,
        "availabilities": [availability],
        "member_timezone": "America/New_York",
    }
    res = client.post(
        "/api/v1/availability_request",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member_with_add_appointment),
    )
    assert res.status_code == 400
    assert api_helpers.load_json(res)["message"] == "Set a phone number to notify with"


def test_no_create_request_bad_member_timezone(
    client, api_helpers, member_with_add_appointment, availability, practitioner_user
):
    # rejects missing member_timezone
    data = {"practitioner_id": practitioner_user().id, "availabilities": [availability]}
    res = client.post(
        "/api/v1/availability_request",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member_with_add_appointment),
    )
    assert res.status_code == 400

    # rejects bad timezone
    data["member_timezone"] = "America/Not_a_Timezone"
    res = client.post(
        "/api/v1/availability_request",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member_with_add_appointment),
    )
    assert res.status_code == 400
    assert (
        api_helpers.load_json(res)["message"] == "A valid member timezone is required"
    )

    data["member_timezone"] = ""
    res = client.post(
        "/api/v1/availability_request",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member_with_add_appointment),
    )
    assert res.status_code == 400
    assert (
        api_helpers.load_json(res)["message"] == "A valid member timezone is required"
    )


def test_no_create_request_no_availability(
    client, api_helpers, member_with_add_appointment, practitioner_user
):
    data = {
        "practitioner_id": practitioner_user().id,
        "availabilities": [],
        "member_timezone": "America/New_York",
    }
    res = client.post(
        "/api/v1/availability_request",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member_with_add_appointment),
    )
    assert res.status_code == 400
    assert (
        api_helpers.load_json(res)["message"]
        == "Member must provide at least one available time"
    )


def test_no_create_request_no_availability_object(
    client, api_helpers, member_with_add_appointment, practitioner_user
):
    data = {
        "practitioner_id": practitioner_user().id,
        "member_timezone": "America/New_York",
    }
    res = client.post(
        "/api/v1/availability_request",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member_with_add_appointment),
    )
    assert res.status_code == 400


@pytest.mark.parametrize("attr", ["start_time", "end_time", "start_date"])
def test_no_create_request_no_availability_object_date_or_time(
    client,
    api_helpers,
    member_with_add_appointment,
    practitioner_user,
    attr,
    availability,
):
    # assert request failure with null values
    availability[attr] = None
    data = {
        "practitioner_id": practitioner_user().id,
        "availabilities": [availability],
        "member_timezone": "America/New_York",
    }
    res = client.post(
        "/api/v1/availability_request",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member_with_add_appointment),
    )
    assert res.status_code == 400
    assert api_helpers.load_json(res)["message"] == "Available times are missing values"

    # assert request failure on missing attributes
    del availability[attr]
    data = {"practitioner_id": practitioner_user().id, "availabilities": [availability]}
    res = client.post(
        "/api/v1/availability_request",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member_with_add_appointment),
    )
    assert res.status_code == 400


def test_create_set_default_end_when_missing(
    client, api_helpers, member_with_add_appointment, practitioner_user, availability
):
    # Validate the end_date is set to the start_date when it's missing
    del availability["end_date"]
    data = {
        "practitioner_id": practitioner_user().id,
        "availabilities": [availability],
        "member_timezone": "America/New_York",
    }
    res = client.post(
        "/api/v1/availability_request",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member_with_add_appointment),
    )
    assert res.status_code == 201
    times = AvailabilityRequestMemberTimes.query.all()
    assert len(times) == 1
    assert times[0].end_date == times[0].start_date


def test_create_400_on_invalid_time_format(
    client, api_helpers, member_with_add_appointment, practitioner_user, availability
):
    # Validate we get a 400 if a time is misformatted
    availability["start_time"] = "3:00:00:000\u202fPM"
    data = {
        "practitioner_id": practitioner_user().id,
        "availabilities": [availability],
        "member_timezone": "America/New_York",
    }
    res = client.post(
        "/api/v1/availability_request",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member_with_add_appointment),
    )
    assert res.status_code == 400


def test_create_set_default_end_when_none(
    client, api_helpers, member_with_add_appointment, practitioner_user, availability
):
    # Validate the end_date is set to the start_date when it's None
    availability["end_date"] = None
    data = {
        "practitioner_id": practitioner_user().id,
        "availabilities": [availability],
        "member_timezone": "America/New_York",
    }
    res = client.post(
        "/api/v1/availability_request",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member_with_add_appointment),
    )
    assert res.status_code == 201
    times = AvailabilityRequestMemberTimes.query.all()
    assert len(times) == 1
    assert times[0].end_date == times[0].start_date


def test_no_create_avail_greater_than_8_days(
    client, api_helpers, member_with_add_appointment, practitioner_user, availability
):
    # Member available date provided must be within 7 days + 1 padding for timezones
    availability["end_date"] = str((now + datetime.timedelta(days=9)).date())
    data = {
        "practitioner_id": practitioner_user().id,
        "availabilities": [availability],
        "member_timezone": "America/New_York",
    }
    res = client.post(
        "/api/v1/availability_request",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member_with_add_appointment),
    )
    assert res.status_code == 400
    assert (
        api_helpers.load_json(res)["message"]
        == "Available times provided must be within the next 7 days"
    )


def test_no_create_avail_more_than_one_day_in_the_past(
    client, api_helpers, member_with_add_appointment, practitioner_user, availability
):
    # Member available date must not be more than one day in the past
    availability["start_date"] = str(
        (now - datetime.timedelta(days=1)).astimezone(NY_TZ).date()
    )
    availability["start_time"] = str(
        (now - datetime.timedelta(minutes=1)).astimezone(NY_TZ).time()
    )

    data = {
        "practitioner_id": practitioner_user().id,
        "availabilities": [availability],
        "member_timezone": "America/New_York",
    }
    res = client.post(
        "/api/v1/availability_request",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member_with_add_appointment),
    )
    assert res.status_code == 400
    assert (
        api_helpers.load_json(res)["message"]
        == "Available times provided cannot be in the past"
    )


def test_create_request_limit(
    factories,
    client,
    api_helpers,
    member_with_add_appointment,
    availability,
    practitioner_user,
):
    """
    Verify the request availability limit of 5
    """
    practitioner = practitioner_user()
    now = datetime.datetime.utcnow()
    data = {
        "practitioner_id": practitioner.id,
        "availabilities": [availability],
        "member_timezone": "America/New_York",
    }

    # 4 previous requests
    for i in range(0, 4):
        factories.AvailabilityNotificationRequestFactory.create(
            member=member_with_add_appointment,
            practitioner=practitioner,
            created_at=now - datetime.timedelta(hours=2, minutes=i),
        )

    # Fifth request of the day should pass
    res = client.post(
        "/api/v1/availability_request",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member_with_add_appointment),
    )
    assert res.status_code == 201

    # Sixth request of the day should fail
    res = client.post(
        "/api/v1/availability_request",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member_with_add_appointment),
    )
    assert res.status_code == 400
    assert (
        api_helpers.load_json(res)["message"]
        == "Daily availability request limit reached"
    )


def test_create_request_limit_daily(
    factories,
    client,
    api_helpers,
    member_with_add_appointment,
    availability,
    practitioner_user,
):
    """
    Verify the request availability limit is only for the past 24 hours
    """
    practitioner = practitioner_user()
    now = datetime.datetime.utcnow()
    data = {
        "practitioner_id": practitioner.id,
        "availabilities": [availability],
        "member_timezone": "America/New_York",
    }

    # Yesterday's requests
    for i in range(0, 5):
        factories.AvailabilityNotificationRequestFactory.create(
            member=member_with_add_appointment,
            practitioner=practitioner,
            created_at=now - datetime.timedelta(days=1, hours=1, minutes=i),
        )

    # Today's requests
    for i in range(0, 4):
        factories.AvailabilityNotificationRequestFactory.create(
            member=member_with_add_appointment,
            practitioner=practitioner,
            created_at=now - datetime.timedelta(hours=2, minutes=i),
        )

    # Fifth request of the day should pass
    res = client.post(
        "/api/v1/availability_request",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member_with_add_appointment),
    )
    assert res.status_code == 201

    # Sixth request of the day should fail
    res = client.post(
        "/api/v1/availability_request",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member_with_add_appointment),
    )
    assert res.status_code == 400
    assert (
        api_helpers.load_json(res)["message"]
        == "Daily availability request limit reached"
    )


@freeze_time("2022-08-25T08:00:00")
@mock.patch("tasks.notifications.notify_new_message.delay")
def test_create_request_correct_message(
    mock_notify_new_message,
    client,
    api_helpers,
    member_with_add_appointment,
    wellness_coach_user,
):
    practitioner = wellness_coach_user()

    data = {
        "practitioner_id": practitioner.id,
        "availabilities": [
            {
                "start_time": "12:00",
                "end_time": "13:00",
                "start_date": "2022-08-26",
                "end_date": "2022-08-28",
            },
            {
                "start_time": "12:00",
                "end_time": "13:00",
                "start_date": "2022-08-30",
                "end_date": "2022-08-30",
            },
        ],
        "member_timezone": "America/New_York",
    }

    res = client.post(
        "/api/v1/availability_request",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member_with_add_appointment),
    )

    assert res.status_code == 201
    response_json = api_helpers.load_json(res)
    assert response_json["channel_id"]
    assert response_json["message_id"]

    channel_id = response_json["channel_id"]

    notification_request = AvailabilityNotificationRequest.query.all()
    notification_request_id = notification_request[0].id

    expected_message = (
        f"Hi {practitioner.first_name},\n\n You have an appointment request!\n\n"
        "The member’s availability is as follows (in order of preference):\n\n"
        "Aug 26, 08:00AM-09:00AM, EDT\n"
        "Aug 27, 08:00AM-09:00AM, EDT\n"
        "Aug 28, 08:00AM-09:00AM, EDT\n"
        "Aug 30, 08:00AM-09:00AM, EDT\n\n"
        "If any of these dates/times work for you, please open the corresponding availability. "
        "To coordinate a new time, you can reply directly to this message.\n\n"
        "Need help? Reach out to providersupport@mavenclinic.com\n\n"
        "Thank you!\n\n"
        f"Reference ID: {notification_request_id}"
    )

    messages = Message.query.all()
    assert len(messages) == 1
    message = messages[0]
    assert message.body == expected_message

    res = client.get(
        f"/api/v1/channel/{channel_id}/messages",
        headers=api_helpers.json_headers(member_with_add_appointment),
    )
    assert res.status_code == 200
    res_data = api_helpers.load_json(res)["data"]
    assert len(res_data) == 1
    assert res_data[0]["body"] == expected_message
    mock_notify_new_message.assert_called_once()


@freeze_time("2022-11-04T08:00:00")
@mock.patch("tasks.notifications.notify_new_message.delay")
def test_create_request_correct_message_daylight_savings(
    mock_notify_new_message,
    client,
    api_helpers,
    member_with_add_appointment,
    wellness_coach_user,
):
    practitioner = wellness_coach_user()

    data = {
        "practitioner_id": practitioner.id,
        "availabilities": [
            {
                "start_time": "12:00",
                "end_time": "13:00",
                "start_date": "2022-11-05",
                "end_date": "2022-11-07",
            },
        ],
        "member_timezone": "America/New_York",
    }

    res = client.post(
        "/api/v1/availability_request",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member_with_add_appointment),
    )

    assert res.status_code == 201
    response_json = api_helpers.load_json(res)
    assert response_json["channel_id"]
    assert response_json["message_id"]

    channel_id = response_json["channel_id"]

    notification_request = AvailabilityNotificationRequest.query.all()
    notification_request_id = notification_request[0].id

    expected_message = (
        f"Hi {practitioner.first_name},\n\n You have an appointment request!\n\n"
        "The member’s availability is as follows (in order of preference):\n\n"
        "Nov 05, 08:00AM-09:00AM, EDT\n"
        "Nov 06, 07:00AM-08:00AM, EST\n"
        "Nov 07, 07:00AM-08:00AM, EST\n\n"
        "If any of these dates/times work for you, please open the corresponding availability. "
        "To coordinate a new time, you can reply directly to this message.\n\n"
        "Need help? Reach out to providersupport@mavenclinic.com\n\n"
        "Thank you!\n\n"
        f"Reference ID: {notification_request_id}"
    )

    messages = Message.query.all()
    assert len(messages) == 1
    message = messages[0]
    assert message.body == expected_message

    res = client.get(
        f"/api/v1/channel/{channel_id}/messages",
        headers=api_helpers.json_headers(member_with_add_appointment),
    )
    assert res.status_code == 200
    res_data = api_helpers.load_json(res)["data"]
    assert len(res_data) == 1
    assert res_data[0]["body"] == expected_message

    res = client.get(
        f"/api/v1/channel/{channel_id}/messages",
        headers=api_helpers.json_headers(practitioner),
    )
    assert res.status_code == 200
    res_data = api_helpers.load_json(res)["data"]
    assert len(res_data) == 1
    assert res_data[0]["body"] == expected_message
    assert (
        res_data[0]["author"]["avatar_url"]
        == "https://www.qa1.mvnapp.net/img/messages/Maven_Message-Avatar@2x.png"
    )
    mock_notify_new_message.assert_called_once()


def test_create_request_author_req_avail_bot(
    client, api_helpers, member_with_add_appointment, wellness_coach_user
):
    """
    Validate that after an availability request the author returns from /channel
    as the request availability bot
    """
    now = datetime.datetime.utcnow()
    tomorrow = now + datetime.timedelta(days=1)
    tomorrow_str = tomorrow.strftime("%Y-%m-%d")

    practitioner = wellness_coach_user()

    data = {
        "practitioner_id": practitioner.id,
        "availabilities": [
            {
                "start_time": "12:00",
                "end_time": "13:00",
                "start_date": tomorrow_str,
                "end_date": tomorrow_str,
            },
        ],
        "member_timezone": "America/New_York",
    }

    res = client.post(
        "/api/v1/availability_request",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member_with_add_appointment),
    )

    assert res.status_code == 201
    response_json = api_helpers.load_json(res)
    assert response_json["channel_id"]
    assert response_json["message_id"]

    channel_id = response_json["channel_id"]

    res = client.get(
        f"/api/v1/channel/{channel_id}/messages",
        headers=api_helpers.json_headers(member_with_add_appointment),
    )
    assert res.status_code == 200
    res_data = api_helpers.load_json(res)["data"]
    assert len(res_data) == 1

    # Assert that the message's author returns
    assert res_data[0]["author"]["email"] == "no-reply@mavenclinic.com"


@freeze_time("2022-08-25T08:00:00")
def test_create_request__null_response_when_cx(
    client, api_helpers, member_with_add_appointment, practitioner_user
):
    """
    Tests that the channel and message ids are null when the practitioner is a care advocate
    """
    practitioner = practitioner_user()  # default vertical is ca

    data = {
        "practitioner_id": practitioner.id,
        "availabilities": [
            {
                "start_time": "12:00",
                "end_time": "13:00",
                "start_date": "2022-08-26",
                "end_date": "2022-08-28",
            },
            {
                "start_time": "12:00",
                "end_time": "13:00",
                "start_date": "2022-08-30",
                "end_date": "2022-08-30",
            },
        ],
        "member_timezone": "America/New_York",
    }

    res = client.post(
        "/api/v1/availability_request",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member_with_add_appointment),
    )

    assert res.status_code == 201
    response_json = api_helpers.load_json(res)
    assert "channel_id" in response_json
    assert response_json["channel_id"] is None
    assert "message_id" in response_json
    assert response_json["message_id"] is None


@mock.patch("appointments.resources.availability_requests.feature_flags.bool_variation")
def test_no_create__practitioner_contract_invalid_type(
    mock_feature_flag,
    client,
    api_helpers,
    member_with_add_appointment,
    practitioner_and_contract,
    availability,
):
    practitioner, contract = practitioner_and_contract
    mock_feature_flag.return_value = True
    # Member available date provided must be within 7 days + 1 padding for timezones
    availability["end_date"] = str((now + datetime.timedelta(days=5)).date())
    data = {
        "practitioner_id": practitioner.id,
        "availabilities": [availability],
        "member_timezone": "America/New_York",
    }
    res = client.post(
        "/api/v1/availability_request",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member_with_add_appointment),
    )
    assert res.status_code == 400
    assert (
        api_helpers.load_json(res)["message"]
        == "Provider contract type does not allow availability requests"
    )
