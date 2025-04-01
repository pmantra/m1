import json
from datetime import datetime, timedelta
from unittest import mock
from unittest.mock import patch

import requests

from authn.models.user import User
from pytests.freezegun import freeze_time
from utils import zoom

TODAY = datetime.now()
YESTERDAY = TODAY - timedelta(days=1)
TOMORROW = TODAY + timedelta(days=1)

PAST_WEBINARS = [
    {
        "agenda": "TEST WEBINAR 1",
        "created_at": "2021-06-23T11:48:26Z",
        "duration": 30,
        "host_id": "S4JWnAqnSEqM3XxtbsKPbQ",
        "id": 88087800615,
        "join_url": "https://us02web.zoom.us/j/88087800615",
        "start_time": YESTERDAY.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "timezone": "America/Chicago",
        "topic": "Maven for Centro",
        "type": 5,
        "uuid": "1234567890",
    }
]

UPCOMING_WEBINARS = [
    {
        "agenda": "TEST_WEBINAR 2",
        "created_at": "2021-06-28T22:24:39Z",
        "duration": 60,
        "host_id": "S4JWnAqnSEqM3XxtbsKPbQ",
        "id": 83152434971,
        "join_url": "https://us02web.zoom.us/j/83152434971",
        "start_time": TOMORROW.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "timezone": "America/New_York",
        "topic": "Infant CPR 101",
        "type": 5,
        "uuid": "9876543210",
    }
]

WEBINARS = PAST_WEBINARS + UPCOMING_WEBINARS

USER_1_EMAIL = "test+user_1@mavenclinic.com"
USER_2_EMAIL = "test+user_2@mavenclinic.com"

REGISTRANTS = [
    {"id": "1234567890", "name": "TEST USER 1", "email": USER_1_EMAIL},
    {"id": "9876543210", "name": "TEST USER 2", "email": USER_2_EMAIL},
]

PARTICIPANTS = [
    {"id": "1234567890", "name": "TEST USER 1", "user_email": USER_1_EMAIL},
    {"id": "9876543210", "name": "TEST USER 2", "user_email": USER_2_EMAIL},
]


@patch("utils.zoom.get_webinars")
def test_get_upcoming_webinars(get_webinars):
    get_webinars.return_value = WEBINARS
    webinars = zoom.get_upcoming_webinars()
    assert len(webinars) == 1
    assert webinars[0] == WEBINARS[-1]


@patch("utils.zoom.get_webinars")
def test_get_upcoming_webinars__none_found(get_webinars):
    get_webinars.return_value = PAST_WEBINARS
    webinars = zoom.get_upcoming_webinars()
    assert len(webinars) == 0


@freeze_time("2023-04-20 12:00:00")
def test_get_webinars_since_days_ago_no_webinars(db):
    assert len(zoom.get_webinars_since_days_ago(1)) == 0


@freeze_time("2023-04-20 12:00:00")
def test_get_webinars_since_days_ago_no_recent_webinars(factories):
    factories.DefaultWebinarFactory.create(
        start_time=datetime(2023, 3, 14, 12), duration=60
    )
    assert len(zoom.get_webinars_since_days_ago(1)) == 0


@freeze_time("2023-04-20 12:00:00")
def test_get_webinars_since_days_ago_webinar_ongoing(factories):
    factories.DefaultWebinarFactory.create(
        start_time=datetime(2023, 4, 20, 11, 30), duration=60
    )
    assert len(zoom.get_webinars_since_days_ago(1)) == 0


@freeze_time("2023-04-20 12:00:00")
def test_get_webinars_since_days_ago_webinar_in_future(factories):
    factories.DefaultWebinarFactory.create(
        start_time=datetime(2023, 4, 21, 12), duration=60
    )
    assert len(zoom.get_webinars_since_days_ago(1)) == 0


@freeze_time("2023-04-20 12:00:00")
def test_get_webinars_since_days_ago_webinar_recent_webinar(db, factories):
    webinar = factories.DefaultWebinarFactory.create(
        start_time=datetime(2023, 4, 20, 10), duration=60
    )
    webinars = zoom.get_webinars_since_days_ago(1)

    assert len(webinars) == 1
    assert webinars[0].id == webinar.id


@patch("utils.zoom.get_past_webinar_participants")
def test_get_users_who_participated_in_webinar__no_participants(
    get_past_webinar_participants,
):
    get_past_webinar_participants.return_value = []
    users = zoom.get_users_who_participated_in_webinar(PAST_WEBINARS[0]["id"])
    assert len(users) == 0


@patch("utils.zoom.get_past_webinar_participants")
def test_get_users_who_participated_in_webinar__with_participants_none_map_to_maven_user(
    get_past_webinar_participants,
):
    get_past_webinar_participants.return_value = PARTICIPANTS

    with patch("authn.models.user.User.query") as user_query_mock:
        user_query_mock.filter.return_value.all.return_value = []

        users = zoom.get_users_who_participated_in_webinar(PAST_WEBINARS[0]["id"])
        assert len(users) == 0


@patch("utils.zoom.get_past_webinar_participants")
def test_get_users_who_participated_in_webinar__with_participants_some_map_to_maven_user(
    get_past_webinar_participants,
):
    get_past_webinar_participants.return_value = PARTICIPANTS

    with patch("authn.models.user.User.query") as user_query_mock:
        user_query_mock.filter.return_value.all.return_value = [
            User(email=PARTICIPANTS[0]["user_email"])
        ]

        users = zoom.get_users_who_participated_in_webinar(PAST_WEBINARS[0]["id"])
        assert len(users) == 1


@patch("utils.zoom.get_past_webinar_participants")
def test_get_users_who_participated_in_webinar__with_participants_all_map_to_maven_user(
    get_past_webinar_participants,
):
    get_past_webinar_participants.return_value = PARTICIPANTS

    with patch("authn.models.user.User.query") as user_query_mock:
        user_query_mock.filter.return_value.all.return_value = [
            User(email=PARTICIPANTS[0]["user_email"]),
            User(email=PARTICIPANTS[1]["user_email"]),
        ]

        users = zoom.get_users_who_participated_in_webinar(PAST_WEBINARS[0]["id"])
        assert len(users) == len(PARTICIPANTS)


@patch("utils.zoom.get_past_webinar_absentees")
def test_get_users_who_missed_webinar__no_participants(get_past_webinar_absentees):
    get_past_webinar_absentees.return_value = []
    users = zoom.get_users_who_missed_webinar(PAST_WEBINARS[0]["id"])
    assert len(users) == 0


@patch("utils.zoom.get_past_webinar_absentees")
def test_get_users_who_missed_webinar__with_participants_none_map_to_maven_user(
    get_past_webinar_absentees,
):
    get_past_webinar_absentees.return_value = REGISTRANTS

    with patch("authn.models.user.User.query") as user_query_mock:
        user_query_mock.filter.return_value.all.return_value = []

        users = zoom.get_users_who_missed_webinar(PAST_WEBINARS[0]["id"])
        assert len(users) == 0


@patch("utils.zoom.get_past_webinar_absentees")
def test_get_users_who_missed_webinar__with_participants_some_map_to_maven_user(
    get_past_webinar_absentees,
):
    get_past_webinar_absentees.return_value = REGISTRANTS

    with patch("authn.models.user.User.query") as user_query_mock:
        user_query_mock.filter.return_value.all.return_value = [
            User(email=REGISTRANTS[0]["email"])
        ]

        users = zoom.get_users_who_missed_webinar(PAST_WEBINARS[0]["id"])
        assert len(users) == 1


@patch("utils.zoom.get_past_webinar_absentees")
def test_get_users_who_missed_webinar__with_participants_all_map_to_maven_user(
    get_past_webinar_absentees,
):
    get_past_webinar_absentees.return_value = REGISTRANTS

    with patch("authn.models.user.User.query") as user_query_mock:
        user_query_mock.filter.return_value.all.return_value = [
            User(email=REGISTRANTS[0]["email"]),
            User(email=REGISTRANTS[1]["email"]),
        ]

        users = zoom.get_users_who_missed_webinar(PAST_WEBINARS[0]["id"])
        assert len(users) == len(REGISTRANTS)


@patch("utils.zoom.ZOOM_API_ACCOUNT_ID", "FOO")
@patch("utils.zoom.ZOOM_SERVER_TO_SERVER_OAUTH_CLIENT_ID", "BAR")
@patch("utils.zoom.ZOOM_SERVER_TO_SERVER_OAUTH_SECRET", "FUBAR")
@patch("utils.zoom.requests.request")
def test_make_zoom_request_no_access_token_data(request_mock):
    token = "🪙"
    token_response = mock.Mock()
    token_response.json.return_value = {
        "access_token": token,
        "expires_in": TOMORROW.timestamp(),
    }
    actual_response = mock.Mock()
    request_mock.side_effect = [token_response, actual_response]
    endpoint = "webinars/1"

    result = zoom.make_zoom_request(endpoint=endpoint)

    assert result == actual_response
    get_token_call = mock.call(
        "POST",
        zoom.ZOOM_OAUTH_TOKEN_URL,
        params={
            "grant_type": zoom.ZOOM_OAUTH_TOKEN_GRANT_TYPE,
            "account_id": "FOO",
        },
        auth=("BAR", "FUBAR"),
    )
    actual_call = mock.call(
        "GET",
        f"{zoom.ZOOM_API_URL}/{endpoint}",
        data={},
        params={},
        headers={
            "Content-type": zoom.CONTENT_TYPE_HEADER,
            "Authorization": "Bearer " + token,
        },
        timeout=zoom.TIMEOUT,
    )
    request_mock.assert_has_calls([get_token_call, actual_call])


@patch("utils.zoom.ZOOM_API_ACCOUNT_ID", "FOO")
@patch("utils.zoom.ZOOM_SERVER_TO_SERVER_OAUTH_CLIENT_ID", "BAR")
@patch("utils.zoom.ZOOM_SERVER_TO_SERVER_OAUTH_SECRET", "FUBAR")
@patch("utils.zoom.access_token_data")
@patch("utils.zoom.requests.request")
def test_make_zoom_request_token_expired(request_mock, token_data_mock):
    token_data_mock.token_expiration_timestamp = YESTERDAY
    token = "🪙"
    token_response = mock.Mock()
    token_response.json.return_value = {"access_token": token, "expires_in": 99999}
    actual_response = mock.Mock()
    request_mock.side_effect = [token_response, actual_response]
    endpoint = "webinars/1"

    result = zoom.make_zoom_request(endpoint=endpoint)

    assert result == actual_response
    get_token_call = mock.call(
        "POST",
        zoom.ZOOM_OAUTH_TOKEN_URL,
        params={
            "grant_type": zoom.ZOOM_OAUTH_TOKEN_GRANT_TYPE,
            "account_id": "FOO",
        },
        auth=("BAR", "FUBAR"),
    )
    actual_call = mock.call(
        "GET",
        f"{zoom.ZOOM_API_URL}/{endpoint}",
        data={},
        params={},
        headers={
            "Content-type": zoom.CONTENT_TYPE_HEADER,
            "Authorization": "Bearer " + token,
        },
        timeout=zoom.TIMEOUT,
    )
    request_mock.assert_has_calls([get_token_call, actual_call])


@patch("utils.zoom.ZOOM_API_ACCOUNT_ID", "FOO")
@patch("utils.zoom.ZOOM_SERVER_TO_SERVER_OAUTH_CLIENT_ID", "BAR")
@patch("utils.zoom.ZOOM_SERVER_TO_SERVER_OAUTH_SECRET", "FUBAR")
@patch("utils.zoom.log")
@patch("utils.zoom.requests.request")
def test_make_zoom_request_get_token_error(request_mock, log_mock):
    error = requests.HTTPError()
    error.response = mock.Mock()
    error_json = '{"error": "oh no"}'
    error.response.json.return_value = error_json
    request_mock.side_effect = error
    endpoint = "webinars/1"

    result = zoom.make_zoom_request(endpoint=endpoint)

    assert result == error.response
    log_mock.error.assert_called_with(
        "Zoom API request failed.",
        zoom_endpoint=endpoint,
        exception=error,
        response=error_json,
        exc_info=True,
    )


@patch("utils.zoom.ZOOM_API_ACCOUNT_ID", "FOO")
@patch("utils.zoom.ZOOM_SERVER_TO_SERVER_OAUTH_CLIENT_ID", "BAR")
@patch("utils.zoom.ZOOM_SERVER_TO_SERVER_OAUTH_SECRET", "FUBAR")
@patch("utils.zoom.access_token_data")
@patch("utils.zoom.requests.request")
def test_make_zoom_request_existing_token_success(request_mock, token_data_mock):
    token_data_mock.token_expiration_timestamp = TOMORROW
    token = "🪙"
    token_data_mock.access_token = token

    endpoint_response = mock.Mock()
    request_mock.return_value = endpoint_response
    endpoint = "webinars/1/registrants"
    method = "POST"
    data = {"email": "kat@dachshu.nd"}

    result = zoom.make_zoom_request(endpoint=endpoint, method=method, data=data)

    assert result == endpoint_response
    request_mock.assert_called_with(
        method,
        f"{zoom.ZOOM_API_URL}/{endpoint}",
        data=json.dumps(data),
        params={},
        headers={
            "Content-type": zoom.CONTENT_TYPE_HEADER,
            "Authorization": "Bearer " + token,
        },
        timeout=zoom.TIMEOUT,
    )
