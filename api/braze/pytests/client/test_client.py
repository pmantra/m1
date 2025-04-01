import datetime
import os
from unittest.mock import ANY, Mock, patch

import pytest
import requests
from dateutil.parser import parse

from braze import client
from braze.client import constants
from pytests.freezegun import freeze_time


def _user_attribute_maker(n: int = 100):
    return [
        client.BrazeUserAttributes(
            external_id=str(i),
            attributes={"foo": "bar"},
        )
        for i in range(n)
    ]


def _user_event_maker(n: int = 100):
    return [
        client.BrazeEvent(
            external_id=str(i),
            name="my_super_kool_event",
        )
        for i in range(n)
    ]


class TestBrazeClientMakeRequest:
    @patch.dict(os.environ, {}, clear=True)
    def test_make_request__flag_disabled(self, logs, launch_darkly_test_data):
        launch_darkly_test_data.update(
            launch_darkly_test_data.flag(
                "kill-switch-braze-api-requests"
            ).variation_for_all(False)
        )
        expected_error = "Skipping Braze API request in when `kill-switch-braze-api-requests` flag is disabled."
        braze_client = client.BrazeClient(api_key="API_KEY")

        response = braze_client._make_request(
            endpoint=constants.USER_TRACK_ENDPOINT,
            data={"attributes": [{"external_id": "123"}]},
            retry_on_failure=False,
        )
        log = next((r for r in logs if expected_error in r["event"]), None)

        assert response is None
        assert log is not None

    @patch.dict(os.environ, {"TESTING": "true"}, clear=True)
    def test_make_request__testing(self, logs, launch_darkly_test_data):
        """
        This test simulates the default branch of the variation where the system
        could not connect to LaunchDarkly.
        """
        braze_client = client.BrazeClient(api_key="API_KEY")
        expected_error = "Skipping Braze API request in when `kill-switch-braze-api-requests` flag is disabled."
        response = braze_client._make_request(
            endpoint=constants.USER_TRACK_ENDPOINT,
            data={"attributes": [{"external_id": "123"}]},
            retry_on_failure=False,
        )

        log = next((r for r in logs if expected_error in r["event"]), None)

        assert response is None
        assert log is not None

    @patch.dict(os.environ, {}, clear=True)
    def test_make_request__no_api_key(self, logs):
        braze_client = client.BrazeClient(api_key=None)
        expected_error = "Skipping Braze API request in environment without an api key."
        response = braze_client._make_request(
            endpoint=constants.USER_TRACK_ENDPOINT,
            data={"attributes": [{"external_id": "123"}]},
            retry_on_failure=False,
        )

        log = next((r for r in logs if expected_error in r["event"]), None)

        assert response is None
        assert log is not None

    @patch.dict(os.environ, {}, clear=True)
    def test_make_request__invalid_method(self, logs):
        braze_client = client.BrazeClient(api_key="API_KEY")
        api_error_msg = "Braze API request failed."
        method_error_msg = "INVALID is not supported"
        response = braze_client._make_request(
            endpoint=constants.USER_TRACK_ENDPOINT,
            data={"attributes": [{"external_id": "123"}]},
            method="INVALID",
            retry_on_failure=False,
        )
        api_log = next((r for r in logs if api_error_msg in r["event"]), None)
        assert response is not None
        assert response.text == method_error_msg
        assert method_error_msg in str(api_log["exception"])

    @patch.dict(os.environ, {}, clear=True)
    @patch("braze.client.braze_client.requests.post")
    def test_make_request__4xx(self, mock_post):
        mock_response = requests.Response()
        mock_response.status_code = 400
        mock_response.json = lambda: {}

        mock_post.return_value = mock_response
        braze_client = client.BrazeClient(api_key="API_KEY")

        response = braze_client._make_request(
            endpoint=constants.USER_TRACK_ENDPOINT,
            data={"attributes": [{"external_id": "123"}]},
            retry_on_failure=True,
        )

        assert response == mock_response
        assert mock_post.call_count == 1  # don't retry 4xx status codes

    @patch.dict(os.environ, {}, clear=True)
    @patch("braze.client.braze_client.requests.post")
    def test_make_request__5xx(self, mock_post):
        mock_response = requests.Response()
        mock_response.status_code = 500
        mock_response.json = lambda: {}

        mock_post.return_value = mock_response
        braze_client = client.BrazeClient(api_key="API_KEY")

        response = braze_client._make_request(
            endpoint=constants.USER_TRACK_ENDPOINT,
            data={"attributes": [{"external_id": "123"}]},
            retry_on_failure=True,
        )

        assert response == mock_response
        assert mock_post.call_count == 2  # allow retry for 5xx status codes

    @patch.dict(os.environ, {}, clear=True)
    @patch("braze.client.braze_client.requests.post")
    def test_make_request__5xx_successful_retry(self, mock_post):
        mock_fail_response = requests.Response()
        mock_fail_response.status_code = 500
        mock_fail_response.json = lambda: {}

        mock_success_response = requests.Response()
        mock_success_response.status_code = 200
        mock_success_response.json = lambda: {}

        mock_post.side_effect = [mock_fail_response, mock_success_response]
        braze_client = client.BrazeClient(api_key="API_KEY")

        response = braze_client._make_request(
            endpoint=constants.USER_TRACK_ENDPOINT,
            data={"attributes": [{"external_id": "123"}]},
            retry_on_failure=True,
        )

        assert mock_post.call_count == 2  # allow retry for 5xx status codes
        assert response is not None
        assert response.status_code == 200

    @patch.dict(os.environ, {}, clear=True)
    @patch("braze.client.braze_client.requests.post")
    def test_make_request__timeout(self, mock_post):
        mock_error = requests.exceptions.Timeout("TIMEOUT")
        mock_error.response = requests.Response()
        mock_error.response.json = lambda: {}

        mock_post.side_effect = mock_error
        braze_client = client.BrazeClient(api_key="API_KEY")

        response = braze_client._make_request(
            endpoint=constants.USER_TRACK_ENDPOINT,
            data={"attributes": [{"external_id": "123"}]},
            retry_on_failure=True,
        )

        assert mock_post.call_count == 2  # these errors are allowed to be retried
        assert response is not None
        assert response.text == "TIMEOUT"

    @patch.dict(os.environ, {}, clear=True)
    @patch("braze.client.braze_client.requests.post")
    def test_make_request__connection_reset(self, mock_post):
        mock_error = ConnectionResetError("CONNECTION_RESET")

        mock_post.side_effect = mock_error
        braze_client = client.BrazeClient(api_key="API_KEY")

        response = braze_client._make_request(
            endpoint=constants.USER_TRACK_ENDPOINT,
            data={"attributes": [{"external_id": "123"}]},
            retry_on_failure=True,
        )

        assert mock_post.call_count == 2  # these errors are allowed to be retried
        assert response is not None
        assert response.text == "CONNECTION_RESET"

    @patch.dict(os.environ, {}, clear=True)
    @patch("braze.client.braze_client.requests.post")
    def test_make_request__requests_connection_error(self, mock_post):
        mock_error = requests.ConnectionError("CONNECTION_ERROR")

        mock_post.side_effect = mock_error
        braze_client = client.BrazeClient(api_key="API_KEY")

        response = braze_client._make_request(
            endpoint=constants.USER_TRACK_ENDPOINT,
            data={"attributes": [{"external_id": "123"}]},
            retry_on_failure=True,
        )

        assert mock_post.call_count == 2  # these errors are allowed to be retried
        assert response is not None
        assert response.text == "CONNECTION_ERROR"

    @patch.dict(os.environ, {}, clear=True)
    @patch("braze.client.braze_client.requests.post")
    def test_make_request__exception(self, mock_post):
        mock_error = Exception("EXCEPTION TEXT")
        mock_error.response = requests.Response()
        mock_error.response.json = lambda: {}

        mock_post.side_effect = mock_error
        braze_client = client.BrazeClient(api_key="API_KEY")

        response = braze_client._make_request(
            endpoint=constants.USER_TRACK_ENDPOINT,
            data={"attributes": [{"external_id": "123"}]},
            retry_on_failure=True,
        )

        assert response is not None
        assert response.text == "EXCEPTION TEXT"

    @patch.dict(os.environ, {}, clear=True)
    @patch("braze.client.braze_client.requests.post")
    def test_make_request__success(self, mock_post):
        mock_response = requests.Response()
        mock_response.status_code = 200
        mock_response.json = lambda: {}

        mock_post.return_value = mock_response
        braze_client = client.BrazeClient(api_key="API_KEY")

        response = braze_client._make_request(
            endpoint=constants.USER_TRACK_ENDPOINT,
            data={"attributes": [{"external_id": "123"}]},
            retry_on_failure=True,
        )

        assert response is not None
        assert response.status_code == 200

    @pytest.mark.parametrize(
        argnames="data,expected_payload",
        argvalues=[
            (
                {"key": "<h1>value</h1>"},
                '{"key": "&lt;h1&gt;value&lt;/h1&gt;"}',
            ),
            (
                {"key": ["<h1>value</h1>"]},
                '{"key": ["&lt;h1&gt;value&lt;/h1&gt;"]}',
            ),
            (
                {"key": {"subkey": "<h1>value</h1>"}},
                '{"key": {"subkey": "&lt;h1&gt;value&lt;/h1&gt;"}}',
            ),
            (
                {"key": {"subkey": {"subsubkey": "<h1>value</h1>"}}},
                '{"key": {"subkey": {"subsubkey": "&lt;h1&gt;value&lt;/h1&gt;"}}}',
            ),
            (
                {"key": client.RawBrazeString("<h1>unescaped header</h1>")},
                '{"key": "<h1>unescaped header</h1>"}',
            ),
        ],
        ids=[
            "top level string escaped",
            "string in list escaped",
            "string in dict escaped",
            "nested two levels escaped",
            "RawBrazeString not escaped",
        ],
    )
    @patch.dict(os.environ, {}, clear=True)
    @patch("braze.client.braze_client.requests.post")
    def test_make_request__escape_html(self, mock_post, data, expected_payload):
        braze_client = client.BrazeClient(api_key="API_KEY")

        braze_client._make_request(
            endpoint=constants.USER_TRACK_ENDPOINT,
            data=data,
            retry_on_failure=True,
        )

        mock_post.assert_called_once_with(
            constants.USER_TRACK_ENDPOINT,
            data=expected_payload,
            headers={
                "Content-type": "application/json",
                "Authorization": "Bearer API_KEY",
            },
            timeout=15,
        )


class TestBrazeClientTrackUser:
    @patch("braze.client.BrazeClient.track_users")
    def test_track_user(self, mock_track_users):
        braze_client = client.BrazeClient(api_key="API_KEY")

        braze_user = client.BrazeUserAttributes(
            external_id="123",
            attributes={"foo": "bar"},
        )
        braze_event = client.BrazeEvent(
            external_id="123",
            name="my_super_kool_event",
        )
        braze_client.track_user(
            user_attributes=braze_user,
            events=[braze_event],
        )

        mock_track_users.assert_called_once_with(
            user_attributes=[braze_user],
            events=[braze_event],
        )

    @freeze_time(datetime.datetime.utcnow())
    @patch("braze.client.BrazeClient._make_request")
    def test_track_users(self, mock_request):
        now = datetime.datetime.utcnow()

        braze_client = client.BrazeClient(api_key="API_KEY")
        braze_user = client.BrazeUserAttributes(
            external_id="123",
            attributes={"foo": "bar"},
        )
        braze_event = client.BrazeEvent(
            external_id="123",
            name="my_super_kool_event",
            time=now,
        )
        braze_client.track_users(
            user_attributes=[braze_user],
            events=[braze_event],
        )

        mock_request.assert_called_once_with(
            endpoint=constants.USER_TRACK_ENDPOINT,
            data={
                "attributes": [{"external_id": "123", "foo": "bar"}],
                "events": [
                    {
                        "external_id": "123",
                        "name": "my_super_kool_event",
                        "time": now.isoformat(),
                        "properties": None,
                    }
                ],
            },
        )

    @pytest.mark.parametrize(
        argnames="users,events,expected_call_count",
        argvalues=(
            (
                _user_attribute_maker(n=100),
                _user_event_maker(n=constants.TRACK_USER_ENDPOINT_LIMIT),
                2,
            ),
            (
                _user_attribute_maker(n=constants.TRACK_USER_ENDPOINT_LIMIT),
                _user_event_maker(n=100),
                2,
            ),
            (None, None, 0),
            (_user_attribute_maker(n=100), None, 2),
            (None, _user_event_maker(n=constants.TRACK_USER_ENDPOINT_LIMIT), 1),
            (None, _user_event_maker(n=100), 2),
            (_user_attribute_maker(n=constants.TRACK_USER_ENDPOINT_LIMIT), None, 1),
            (_user_attribute_maker(n=constants.TRACK_USER_ENDPOINT_LIMIT * 3), None, 3),
        ),
    )
    @freeze_time(datetime.datetime.utcnow())
    @patch("braze.client.BrazeClient._make_request")
    def test_track_users__in_batches(
        self, mock_request, users, events, expected_call_count
    ):
        mock_response = requests.Response()
        mock_response.status_code = 200
        mock_response.json = lambda: {}

        mock_request.return_value = mock_response

        braze_client = client.BrazeClient(api_key="API_KEY")
        braze_client.track_users(user_attributes=users, events=events)

        assert mock_request.call_count == expected_call_count

    @patch("braze.client.BrazeClient._make_request")
    def test_track_users__no_events_or_user_attributes(self, mock_request, logs):
        braze_client = client.BrazeClient(api_key="API_KEY")
        error_msg = "No data to send to Braze. Skipping request"
        braze_client.track_users()
        log = next((r for r in logs if error_msg in r["event"]), None)
        assert mock_request.call_count == 0
        assert log is not None

    @patch("braze.client.BrazeClient._make_request")
    def test_track_users__no_events(self, mock_request):
        braze_client = client.BrazeClient(api_key="API_KEY")

        braze_user = client.BrazeUserAttributes(
            external_id="123",
            attributes={"foo": "bar"},
        )
        braze_client.track_users(user_attributes=[braze_user])

        mock_request.assert_called_once_with(
            endpoint=constants.USER_TRACK_ENDPOINT,
            data={"attributes": [{"external_id": "123", "foo": "bar"}]},
        )

    @patch("braze.client.BrazeClient._make_request")
    def test_track_users__no_events_empty_user_attributes(
        self,
        mock_request,
        logs,
    ):
        braze_client = client.BrazeClient(api_key="API_KEY")
        error_msg = "No data to send to Braze. Skipping request"
        braze_user = client.BrazeUserAttributes(
            external_id="123",
            attributes={"foo": None},
        )
        braze_client.track_users(user_attributes=[braze_user])
        log = next((r for r in logs if error_msg in r["event"]), None)
        assert mock_request.call_count == 0
        assert log is not None

    @freeze_time(datetime.datetime.utcnow())
    @patch("braze.client.BrazeClient._make_request")
    def test_track_users__no_user_attributes(self, mock_request):
        now = datetime.datetime.utcnow()

        braze_client = client.BrazeClient(api_key="API_KEY")
        braze_event = client.BrazeEvent(
            external_id="123",
            name="my_super_kool_event",
            time=now,
        )
        braze_client.track_users(events=[braze_event])

        mock_request.assert_called_once_with(
            endpoint=constants.USER_TRACK_ENDPOINT,
            data={
                "events": [
                    {
                        "external_id": "123",
                        "name": "my_super_kool_event",
                        "time": now.isoformat(),
                        "properties": None,
                    }
                ]
            },
        )

    @freeze_time(datetime.datetime.utcnow())
    @patch("braze.client.BrazeClient._make_request")
    def test_track_users__empty_user_attributes(self, mock_request):
        now = datetime.datetime.utcnow()

        braze_client = client.BrazeClient(api_key="API_KEY")
        braze_user = client.BrazeUserAttributes(
            external_id="123",
            attributes={"foo": None},
        )
        braze_event = client.BrazeEvent(
            external_id="123",
            name="my_super_kool_event",
            time=now,
        )
        braze_client.track_users(
            user_attributes=[braze_user],
            events=[braze_event],
        )

        mock_request.assert_called_once_with(
            endpoint=constants.USER_TRACK_ENDPOINT,
            data={
                "events": [
                    {
                        "external_id": "123",
                        "name": "my_super_kool_event",
                        "time": now.isoformat(),
                        "properties": None,
                    }
                ]
            },
        )


class TestBrazeClientDeleteUser:
    @patch("braze.client.BrazeClient.delete_users")
    def test_delete_user(self, mock_delete_users):
        braze_client = client.BrazeClient(api_key="API_KEY")
        braze_client.delete_user(external_id="123")

        mock_delete_users.assert_called_once_with(
            external_ids=["123"],
        )

    @patch("braze.client.BrazeClient._make_request")
    def test_delete_users(self, mock_request):
        braze_client = client.BrazeClient(api_key="API_KEY")
        braze_client.delete_users(external_ids=["123"])

        mock_request.assert_called_once_with(
            endpoint=constants.USER_DELETE_ENDPOINT,
            data={"external_ids": ["123"]},
        )


class TestBrazeClientUpdateSubscriptionStatus:
    @patch("braze.client.BrazeClient.update_email_subscription_status")
    def test_unsubscribe_email(self, mock_update):
        email = "unsubscribe@email.com"
        braze_client = client.BrazeClient(api_key="API_KEY")
        braze_client.unsubscribe_email(email=email)

        mock_update.called_once_with(
            email=email,
            subscription_state=client.BrazeSubscriptionState.UNSUBSCRIBED,
        )

    @patch("braze.client.BrazeClient.update_email_subscription_status")
    def test_opt_in_email(self, mock_update):
        email = "opt.in@email.com"
        braze_client = client.BrazeClient(api_key="API_KEY")
        braze_client.opt_in_email(email=email)

        mock_update.called_once_with(
            email=email,
            subscription_state=client.BrazeSubscriptionState.OPTED_IN,
        )

    @patch("braze.client.BrazeClient.update_email_subscription_statuses")
    def test_update_email_subscription_status(self, mock_update):
        email = "test@email.com"
        braze_client = client.BrazeClient(api_key="API_KEY")
        braze_client.update_email_subscription_status(
            email=email,
            subscription_state=client.BrazeSubscriptionState.UNSUBSCRIBED,
        )

        mock_update.called_once_with(
            emails=[email],
            subscription_state=client.BrazeSubscriptionState.UNSUBSCRIBED,
        )

    @patch("braze.client.BrazeClient._make_request")
    def test_update_email_subscription_statuses(self, mock_request):
        emails = ["a@email.com", "b@email.com"]
        braze_client = client.BrazeClient(api_key="API_KEY")
        braze_client.update_email_subscription_statuses(
            emails=emails,
            subscription_state=client.BrazeSubscriptionState.UNSUBSCRIBED,
        )

        mock_request.called_once_with(
            endpoint=constants.EMAIL_SUBSCRIBE_ENDPOINT,
            data={
                "email": emails,
                "subscription_state": client.BrazeSubscriptionState.UNSUBSCRIBED.value,
            },
        )


class TestBrazeClientSendEmail:
    @patch("braze.client.BrazeClient._make_request")
    def test_send_email(self, mock_request):
        # Given an email to be sent
        mock_response = requests.Response()
        mock_response.status_code = 200
        mock_response.json = lambda: {"dispatch_id": "DISPATCH_ID"}

        mock_request.return_value = mock_response

        braze_client = client.BrazeClient(api_key="API_KEY")
        braze_email = client.BrazeEmail(
            external_ids=["123"],
            from_="from@email.com",
            reply_to="reply@email.com",
            subject="SUBJECT",
            body="<h1>Hello</h1>",
            plaintext_body="plaintext",
            headers={"X-HEADER": "header"},
        )

        # When we call send_email
        dispatch_id = braze_client.send_email(email=braze_email)

        # Then the braze request is executed
        mock_request.assert_called_once_with(
            endpoint=constants.MESSAGE_SEND_ENDPOINT,
            data={
                "external_user_ids": ["123"],
                "messages": {
                    "email": {
                        "from": "from@email.com",
                        "reply_to": "reply@email.com",
                        "subject": "SUBJECT",
                        "body": "<h1>Hello</h1>",
                        "plaintext_body": "plaintext",
                        "headers": {"X-HEADER": "header"},
                    }
                },
                "recipient_subscription_state": "subscribed",
            },
            escape_html=False,
        )
        assert dispatch_id == "DISPATCH_ID"

    @pytest.mark.parametrize(
        argnames="recipient_subscription_state",
        argvalues=[
            "opted_in",
            "subscribed",
            "all",
        ],
    )
    @patch("braze.client.BrazeClient._make_request")
    def test_send_email__with_valid_recipient_subscription_state(
        self, mock_request, recipient_subscription_state
    ):
        # Given an email to be sent
        mock_response = requests.Response()
        mock_response.status_code = 200
        mock_response.json = lambda: {"dispatch_id": "DISPATCH_ID"}

        mock_request.return_value = mock_response

        braze_client = client.BrazeClient(api_key="API_KEY")
        braze_email = client.BrazeEmail(
            external_ids=["123"],
            from_="from@email.com",
            reply_to="reply@email.com",
            subject="SUBJECT",
            body="<h1>Hello</h1>",
            plaintext_body="plaintext",
            headers={"X-HEADER": "header"},
        )

        # When we call send_email with a valid recipient_subscription_state
        dispatch_id = braze_client.send_email(
            email=braze_email, recipient_subscription_state=recipient_subscription_state
        )

        # Then the braze request is executed with that valid recipient_subscription_state
        mock_request.assert_called_once_with(
            endpoint=constants.MESSAGE_SEND_ENDPOINT,
            data={
                "external_user_ids": ["123"],
                "messages": {
                    "email": {
                        "from": "from@email.com",
                        "reply_to": "reply@email.com",
                        "subject": "SUBJECT",
                        "body": "<h1>Hello</h1>",
                        "plaintext_body": "plaintext",
                        "headers": {"X-HEADER": "header"},
                    }
                },
                "recipient_subscription_state": recipient_subscription_state,
            },
            escape_html=False,
        )
        assert dispatch_id == "DISPATCH_ID"

    @patch.dict(os.environ, {}, clear=True)
    @patch("braze.client.BrazeClient._make_request")
    def test_send_email__with_invalid_recipient_subscription_state(self, mock_request):
        # Given an email to be sent
        mock_response = requests.Response()
        mock_response.status_code = 200
        mock_response.json = lambda: {"dispatch_id": "DISPATCH_ID"}

        mock_request.return_value = mock_response

        braze_client = client.BrazeClient(api_key="API_KEY")
        braze_email = client.BrazeEmail(
            external_ids=["123"],
            from_="from@email.com",
            reply_to="reply@email.com",
            subject="SUBJECT",
            body="<h1>Hello</h1>",
            plaintext_body="plaintext",
            headers={"X-HEADER": "header"},
        )

        # When we call send_email with an invalid recipient_subscription_state
        dispatch_id = braze_client.send_email(
            email=braze_email,
            recipient_subscription_state="invalid_recipient_subscription_state",
        )

        # Then the braze request is executed with recipient_subscription_state equal to subscribed (default value)
        mock_request.assert_called_once_with(
            endpoint=constants.MESSAGE_SEND_ENDPOINT,
            data={
                "external_user_ids": ["123"],
                "messages": {
                    "email": {
                        "from": "from@email.com",
                        "reply_to": "reply@email.com",
                        "subject": "SUBJECT",
                        "body": "<h1>Hello</h1>",
                        "plaintext_body": "plaintext",
                        "headers": {"X-HEADER": "header"},
                    }
                },
                "recipient_subscription_state": "subscribed",
            },
            escape_html=False,
        )
        assert dispatch_id == "DISPATCH_ID"

    @patch("braze.client.braze_client.requests.post")
    def test_send_email__failure(self, mock_post):
        # Given a failed response from Braze
        mock_response = requests.Response()
        mock_response.status_code = 400
        mock_response.json = lambda: {}

        mock_post.return_value = mock_response

        braze_client = client.BrazeClient(api_key="API_KEY")
        braze_email = client.BrazeEmail(
            external_ids=["123"],
            from_="from@email.com",
            reply_to="reply@email.com",
            subject="SUBJECT",
            body="<h1>Hello</h1>",
            plaintext_body="plaintext",
            headers={"X-HEADER": "header"},
        )

        # When calling send_email
        dispatch_id = braze_client.send_email(email=braze_email)

        # Then no dispatch_id is returned
        assert dispatch_id is None

    @patch.dict(os.environ, {}, clear=True)
    @patch("braze.client.BrazeClient._make_request")
    def test_send_email__body_missing_when_required(self, mock_request):
        # Given an email with missing body
        braze_client = client.BrazeClient(api_key="API_KEY")
        braze_email = client.BrazeEmail(
            external_ids=["123"],
            from_="from@email.com",
        )
        # Then exception is raised
        with pytest.raises(client.BrazeEmailBodyMissingError):
            # When calling send_email
            braze_client.send_email(email=braze_email)

    @patch("braze.client.BrazeClient._make_request")
    def test_send_email__body_missing_but_okay(self, mock_request):
        # Given an email with missing body but with email_template_id
        braze_client = client.BrazeClient(api_key="API_KEY")
        braze_email = client.BrazeEmail(
            external_ids=["123"],
            from_="from@email.com",
            email_template_id="email_template_id",
        )
        # When calling send_email
        braze_client.send_email(email=braze_email)

        # Then the send email braze request is executed
        mock_request.assert_called_once()


class TestBrazeClientGetUnsubscribes:
    @patch("braze.client.BrazeClient._make_request")
    def test_get_unsubscribes(self, mock_request):
        mock_response = requests.Response()
        mock_response.status_code = 200
        mock_response.json = lambda: {
            "emails": [
                {"email": "a@email.com", "unsubscribed_at": "time_1"},
                {"email": "b@email.com", "unsubscribed_at": "time_2"},
            ]
        }

        mock_request.return_value = mock_response

        today = datetime.date.today()
        last_year = today - datetime.timedelta(days=365)

        braze_client = client.BrazeClient(api_key="API_KEY")
        emails = braze_client.get_unsubscribes(
            start_date=last_year,
            end_date=today,
            offset=123,
        )

        mock_request.assert_called_once_with(
            endpoint=constants.UNSUBSCRIBES_ENDPOINT,
            data={
                "limit": constants.UNSUBSCRIBES_ENDPOINT_LIMIT,
                "offset": 123,
                "start_date": last_year.isoformat(),
                "end_date": today.isoformat(),
                "sort_direction": "asc",
            },
            method=client.SupportedMethods.GET,
        )

        assert len(emails) == 2

    @patch("braze.client.BrazeClient._make_request")
    def test_get_unsubscribes__no_emails(self, mock_request, logs):
        mock_response = requests.Response()
        mock_response.status_code = 200
        mock_response.json = lambda: {"emails": []}
        mock_request.return_value = mock_response
        error_msg = "Could not retrieve unsubscribes"
        today = datetime.date.today()
        last_year = today - datetime.timedelta(days=365)

        braze_client = client.BrazeClient(api_key="API_KEY")
        emails = braze_client.get_unsubscribes(
            start_date=last_year,
            end_date=today,
            offset=123,
        )
        log = next((r for r in logs if error_msg in r["event"]), None)
        mock_request.assert_called_once_with(
            endpoint=constants.UNSUBSCRIBES_ENDPOINT,
            data={
                "limit": constants.UNSUBSCRIBES_ENDPOINT_LIMIT,
                "offset": 123,
                "start_date": last_year.isoformat(),
                "end_date": today.isoformat(),
                "sort_direction": "asc",
            },
            method=client.SupportedMethods.GET,
        )

        assert len(emails) == 0
        assert log is None

    @patch("braze.client.BrazeClient._make_request")
    def test_get_unsubscribes__request_failure(self, mock_request, logs):
        mock_response = requests.Response()
        mock_response.status_code = 400
        mock_response.json = lambda: {}
        mock_request.return_value = mock_response
        error_msg = "Could not retrieve unsubscribes"
        today = datetime.date.today()
        last_year = today - datetime.timedelta(days=365)

        braze_client = client.BrazeClient(api_key="API_KEY")
        emails = braze_client.get_unsubscribes(
            start_date=last_year,
            end_date=today,
            offset=123,
        )
        log = next((r for r in logs if error_msg in r["event"]), None)
        mock_request.assert_called_once_with(
            endpoint=constants.UNSUBSCRIBES_ENDPOINT,
            data={
                "limit": constants.UNSUBSCRIBES_ENDPOINT_LIMIT,
                "offset": 123,
                "start_date": last_year.isoformat(),
                "end_date": today.isoformat(),
                "sort_direction": "asc",
            },
            method=client.SupportedMethods.GET,
        )

        assert len(emails) == 0
        assert log is not None


class TestBrazeUserAttributes:
    def test_as_dict__with_datetime(self):
        datetime_val = datetime.datetime.now()
        braze_user_attributes = client.BrazeUserAttributes(
            external_id="123", attributes={"my_datetime": datetime_val}
        )

        attributes_json = braze_user_attributes.as_dict()

        assert attributes_json["external_id"] == "123"
        assert attributes_json["my_datetime"] == datetime_val.isoformat()

    def test_as_dict__with_date(self):
        date_val = datetime.date.today()
        braze_user_attributes = client.BrazeUserAttributes(
            external_id="123", attributes={"my_date": date_val}
        )

        attributes_json = braze_user_attributes.as_dict()

        assert attributes_json["external_id"] == "123"
        assert attributes_json["my_date"] == (
            datetime.datetime(date_val.year, date_val.month, date_val.day).isoformat()
        )

    def test_total_data_points(self):
        braze_user_attributes = client.BrazeUserAttributes(
            external_id="123",
            attributes={"a": 1, "b": [2, 3], "c": {"aa": 11, "bb": [2, 2]}},
        )

        data_points = braze_user_attributes.total_data_points()

        assert data_points == 4


class TestBrazeEvent:
    def test_as_dict__with_datetime(self):
        datetime_val = datetime.datetime.now()
        braze_event = client.BrazeEvent(
            external_id="123",
            name="my_super_kool_event",
            properties={"my_datetime": datetime_val},
        )

        event_json = braze_event.as_dict()

        assert event_json["external_id"] == "123"
        assert event_json["properties"]["my_datetime"] == datetime_val.isoformat()

    def test_as_dict__with_date(self):
        date_val = datetime.date.today()
        braze_event = client.BrazeEvent(
            external_id="123",
            name="my_super_kool_event",
            properties={"my_date": date_val},
        )

        event_json = braze_event.as_dict()

        assert event_json["external_id"] == "123"
        assert event_json["properties"]["my_date"] == (
            datetime.datetime(date_val.year, date_val.month, date_val.day).isoformat()
        )

    def test_total_data_points(self):
        braze_event = client.BrazeEvent(
            external_id="123",
            name="my_super_kool_event",
            properties={"a": 1, "b": [2, 3], "c": {"aa": 11, "bb": [2, 2]}},
        )

        data_points = braze_event.total_data_points()

        assert data_points == 5


class TestBrazeClientGetMauCount:
    @patch("braze.client.BrazeClient._make_request")
    def test_get_mau_count(self, mock_request):
        mock_response = requests.Response()
        mock_response.status_code = 200
        mock_response.json = lambda: {
            "data": [
                {
                    "time": "2024-02-07",
                    "mau": 10_000,
                }
            ],
            "message": "success",
        }

        mock_request.return_value = mock_response

        braze_client = client.BrazeClient(api_key="API_KEY")
        mau_count = braze_client.get_mau_count()

        mock_request.assert_called_once_with(
            endpoint=constants.MAU_ENDPOINT,
            method=client.SupportedMethods.GET,
            data=dict(length=1, ending_at=ANY),
        )

        assert mau_count == 10_000

    @patch("braze.client.BrazeClient._make_request")
    def test_get_mau_count__request_failure(self, mock_request):
        mock_response = requests.Response()
        mock_response.status_code = 400
        mock_response.json = lambda: {}

        mock_request.return_value = mock_response

        braze_client = client.BrazeClient(api_key="API_KEY")
        mau_count = braze_client.get_mau_count()

        mock_request.assert_called_once_with(
            endpoint=constants.MAU_ENDPOINT,
            method=client.SupportedMethods.GET,
            data=dict(length=1, ending_at=ANY),
        )

        assert mau_count is None


class TestBrazeClientGetDauCount:
    @patch("braze.client.BrazeClient._make_request")
    def test_get_dau_count(self, mock_request):
        mock_response = requests.Response()
        mock_response.status_code = 200
        mock_response.json = lambda: {
            "data": [
                {
                    "time": "2024-02-07",
                    "dau": 100,
                }
            ],
            "message": "success",
        }

        mock_request.return_value = mock_response

        braze_client = client.BrazeClient(api_key="API_KEY")
        dau_count = braze_client.get_dau_count()

        mock_request.assert_called_once_with(
            endpoint=constants.DAU_ENDPOINT,
            method=client.SupportedMethods.GET,
            data=dict(length=1, ending_at=ANY),
        )

        assert dau_count == 100

    @patch("braze.client.BrazeClient._make_request")
    def test_get_dau_count__request_failure(self, mock_request):
        mock_response = requests.Response()
        mock_response.status_code = 400
        mock_response.json = lambda: {}

        mock_request.return_value = mock_response

        braze_client = client.BrazeClient(api_key="API_KEY")
        dau_count = braze_client.get_dau_count()

        mock_request.assert_called_once_with(
            endpoint=constants.DAU_ENDPOINT,
            method=client.SupportedMethods.GET,
            data=dict(length=1, ending_at=ANY),
        )

        assert dau_count is None


class TestBrazeClientFetchUser:
    @patch("braze.client.BrazeClient.fetch_users")
    def test_fetch_user(self, mock_fetch_users):
        external_id = "123"

        braze_client = client.BrazeClient(api_key="API_KEY")
        braze_client.fetch_user(external_id=external_id)

        mock_fetch_users.assert_called_once_with(external_ids=[external_id])

    @patch("braze.client.BrazeClient.fetch_users")
    def test_fetch_user_by_email(self, mock_fetch_users):
        email = "test@email.com"

        braze_client = client.BrazeClient(api_key="API_KEY")
        braze_client.fetch_user_by_email(email=email)

        mock_fetch_users.assert_called_once_with(email=email)

    @patch("braze.client.BrazeClient._make_request")
    def test_fetch_users(self, mock_request):
        mock_response = requests.Response()
        mock_response.status_code = 200
        mock_response.json = lambda: {"message": "success", "users": []}

        mock_request.return_value = mock_response

        external_id = "123"
        email = "test@email.com"

        braze_client = client.BrazeClient(api_key="API_KEY")
        braze_client.fetch_users(external_ids=[external_id], email=email)

        mock_request.assert_called_once_with(
            endpoint=constants.USER_EXPORT_ENDPOINT,
            method=client.SupportedMethods.POST,
            data={
                "external_ids": [external_id],
                "email_address": email,
            },
        )

    @patch("braze.client.BrazeClient._make_request")
    def test_fetch_users__parses_response(self, mock_request, mock_braze_user_profile):
        mock_response = requests.Response()
        mock_response.status_code = 200
        mock_response.json = lambda: {
            "message": "success",
            "users": [mock_braze_user_profile],
        }

        mock_request.return_value = mock_response

        braze_client = client.BrazeClient(api_key="API_KEY")
        users = braze_client.fetch_users(external_ids=["123"])

        assert len(users) == 1


class TestBrazeExportedUser:
    def test_braze_exported_user(self, mock_braze_user_profile):
        braze_exported_user = client.BrazeExportedUser(**mock_braze_user_profile)

        assert len(braze_exported_user.user_aliases) == 1
        assert isinstance(braze_exported_user.user_aliases[0], client.BrazeUserAlias)
        assert braze_exported_user.user_aliases[0].alias_name == "user_123"
        assert braze_exported_user.user_aliases[0].alias_label == "some_label"

        assert isinstance(braze_exported_user.created_at, datetime.datetime)

        assert len(braze_exported_user.custom_events) == 1
        assert isinstance(
            braze_exported_user.custom_events[0], client.BrazeCustomEventResponse
        )
        assert isinstance(braze_exported_user.custom_events[0].first, datetime.datetime)
        assert isinstance(braze_exported_user.custom_events[0].last, datetime.datetime)

    def test_braze_exported_user__from_dict__excludes_unknown_fields(
        self, mock_braze_user_profile
    ):
        """
        Assert that we can successfully create a BrazeExportedUser from a dictionary
        that includes unknown fields.
        """
        data = {**mock_braze_user_profile, **{"unknown_field": "value"}}
        client.BrazeExportedUser.from_dict(data)

    def test_braze_exported_user__as_dict(self, mock_braze_user_profile):
        expected_values = {
            "created_at": parse("2020-07-10T15:00:00.000Z", ignoretz=True),
            "external_id": "123",
            "user_aliases": [{"alias_name": "user_123", "alias_label": "some_label"}],
            "braze_id": "5fbd99bac125ca40511f2cb1",
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "example@braze.com",
            "country": "US",
            "language": "en",
            "time_zone": "Eastern Time (US & Canada)",
            "email_subscribe": "subscribed",
            "Registration date": "2021-06-28T15:00:00.000Z",  # custom attribute
            "state": "NY",  # custom attribute
            "onboarding_state": "assessments",  # custom attribute
            "custom_events": [
                {
                    "name": "password_reset",
                    "first": parse("2021-06-28T17:02:43.032Z"),
                    "last": parse("2021-06-28T17:02:43.032Z"),
                    "count": 1,
                },
            ],
        }
        braze_exported_user = client.BrazeExportedUser.from_dict(
            mock_braze_user_profile
        )

        actual = braze_exported_user.as_dict()

        assert actual == expected_values


class TestBrazeClientError:
    @patch.dict(os.environ, {}, clear=True)
    @patch("braze.client.braze_client.log")
    @patch("braze.client.braze_client.requests.post")
    def test_make_request__timeout(self, mock_post, mock_log):
        def create_mock_http_error(status_code, reason):
            mock_response = Mock(spec=requests.Response)
            mock_response.status_code = status_code
            mock_response.reason = reason
            mock_response.text = '{"error": "Server Error"}'

            mock_error = requests.exceptions.HTTPError(
                f"HTTP {status_code} Error occurred"
            )
            mock_error.response = mock_response
            return mock_error

        mock_error = create_mock_http_error(400, "Bad Request")
        mock_post.side_effect = mock_error
        braze_client = client.BrazeClient(api_key="API_KEY")

        braze_client._make_request(
            endpoint=constants.USER_TRACK_ENDPOINT,
            data={"attributes": [{"external_id": "123"}]},
            retry_on_failure=False,
        )

        mock_log.error.assert_called_once_with(
            "Braze API request failed.",
            braze_endpoint=constants.USER_TRACK_ENDPOINT,
            response='{"error": "Server Error"}',
            exception=mock_error,
            will_retry=False,
        )
