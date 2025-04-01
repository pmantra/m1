import datetime
import json
from unittest.mock import ANY, MagicMock, patch

import requests

from dosespot.services.dosespot_auth import DoseSpotAuth
from pytests.freezegun import freeze_time


def test_get_token_retries():
    auth_obj = DoseSpotAuth(clinic_key="clinic_key", clinic_id=1, user_id=1)
    with patch.object(DoseSpotAuth, "create_token") as create_token_mock:
        auth_obj.get_token()
        assert create_token_mock.call_count == 3


def test_get_token_when_expired():
    expiration_date_in_past = datetime.datetime.now() - datetime.timedelta(minutes=6)
    auth_obj = DoseSpotAuth(clinic_key="clinic_key", clinic_id=1, user_id=1)
    auth_obj.token = "abcd"
    auth_obj.token_expires = expiration_date_in_past
    with patch.object(DoseSpotAuth, "create_token") as create_token_mock:
        create_token_mock.return_value = "efgh"
        auth_obj.get_token()
        assert create_token_mock.called_once()


@freeze_time("2024-06-13T14:00:00")
def test_create_token():
    auth_obj = DoseSpotAuth(clinic_key="clinic_key", clinic_id=1, user_id=1)
    res = MagicMock()
    res.status_code = 200
    res.text = json.dumps({"expires_in": 599, "access_token": "abcd"})

    with patch.object(requests, "post") as post_mock:
        post_mock.return_value = res
        assert (auth_obj.create_token()) == "abcd"
        assert auth_obj.token_expires == datetime.datetime(2024, 6, 13, 14, 9, 59)

        expected_data = {
            "grant_type": "password",
            "client_id": 1,
            "client_secret": "clinic_key",
            "username": 1,
            "password": "clinic_key",
            "scope": "api",
        }
        expected_header = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Subscription-Key": ANY,
        }
        post_mock.assert_called_once_with(
            "https://my.staging.dosespot.com/webapi/v2/connect/token",
            data=expected_data,
            headers=expected_header,
        )


def test_create_token_failure_returns_none():
    auth_obj = DoseSpotAuth(clinic_key="clinic_key", clinic_id=1, user_id=1)
    res = MagicMock()
    res.status_code = 500
    res.text = json.dumps(
        {"Result": {"ResultCode": "ERROR", "ResultDescription": "sorry"}}
    )

    with patch.object(requests, "post") as post_mock:
        post_mock.return_value = res
        assert (auth_obj.create_token()) is None
