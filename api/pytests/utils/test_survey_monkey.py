from unittest.mock import patch

import requests

from utils.survey_monkey import (
    get_survey_ids,
    get_webhook_id,
    update_webhook_survey_ids,
)


def test_get_survey_ids__success():
    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {
        "data": [
            {
                "id": "1234",
                "title": "My Survey",
            },
            {
                "id": "1235",
                "title": "My New Survey",
            },
        ]
    }
    with patch("utils.survey_monkey.requests.get") as mock_get:
        mock_get.return_value = mock_response
        survey_ids = get_survey_ids()

    assert survey_ids == ["1234", "1235"]


def test_get_survey_ids__failure():
    mock_response = requests.Response()
    mock_response.status_code = 404
    mock_response.json = lambda: {
        "error": {
            "id": 1020,
            "name": "Resource Not Found",
            "docs": "https://developer.surveymonkey.com/api/v3/#error-codes",
            "message": "There was an error retrieving the requested resource.",
            "http_status_code": 404,
        }
    }
    with patch("utils.survey_monkey.requests.get") as mock_get:
        mock_get.return_value = mock_response
        survey_ids = get_survey_ids()

    assert not survey_ids


def test_get_webhook_id():
    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {
        "data": [
            {
                "id": "1234",
                "name": "My Webhook",
                "href": "https://api.surveymonkey.com/v3/webhooks/123",
            }
        ],
    }
    with patch("utils.survey_monkey.requests.get") as mock_get:
        mock_get.return_value = mock_response
        webhook_id = get_webhook_id()

        assert webhook_id == 1234


def test_get_webhook_id__failure():
    mock_response = requests.Response()
    mock_response.status_code = 404
    mock_response.json = lambda: {
        "error": {
            "id": 1020,
            "name": "Resource Not Found",
            "docs": "https://developer.surveymonkey.com/api/v3/#error-codes",
            "message": "There was an error retrieving the requested resource.",
            "http_status_code": 404,
        }
    }
    with patch("utils.survey_monkey.requests.get") as mock_get:
        mock_get.return_value = mock_response
        webhook_id = get_webhook_id()

    assert not webhook_id


def test_update_webhook_survey_ids__success():
    mock_response = requests.Response()
    mock_response.status_code = 201
    with patch("utils.survey_monkey.get_survey_ids", return_value=["1"]):
        with patch("utils.survey_monkey.get_webhook_id", return_value=1):
            with patch("utils.survey_monkey.requests.patch") as mock_patch:
                mock_patch.return_value = mock_response
                webhook_success = update_webhook_survey_ids()

    assert webhook_success is True


def test_update_webhook_survey_ids_no_id__failure():
    with patch("utils.survey_monkey.get_webhook_id", return_value=None):
        with patch("utils.survey_monkey.get_survey_ids", return_value=["1"]):
            with patch("utils.survey_monkey.requests.patch") as mock_patch:
                webhook_success = update_webhook_survey_ids()

    assert webhook_success is False
    assert mock_patch.call_count == 0


def test_update_webhook_survey_ids__failure():
    mock_response = requests.Response()
    mock_response.status_code = 401
    with patch("utils.survey_monkey.get_webhook_id", return_value=1):
        with patch("utils.survey_monkey.get_survey_ids", return_value=["1"]):
            with patch("utils.survey_monkey.requests.patch") as mock_patch:
                mock_patch.return_value = mock_response
                webhook_success = update_webhook_survey_ids()

    assert webhook_success is False
    assert mock_patch.call_count == 1
