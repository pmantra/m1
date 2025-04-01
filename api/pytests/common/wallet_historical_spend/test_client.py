import json
from unittest.mock import patch

import pytest
from requests import Response

from common import wallet_historical_spend
from common.wallet_historical_spend.client import WalletHistoricalSpendClientException


@pytest.fixture
def mock_response():
    mock_response = Response()
    mock_response.status_code = 200
    mock_response.encoding = "application/json"
    return mock_response


@pytest.fixture
def create_wallet_historical_spend_error_response():
    def create_error_response(status_code, body):
        mock_response = Response()
        mock_response.status_code = status_code
        mock_response.encoding = "application/json"
        mock_response._content = json.dumps(body).encode("utf-8")
        return mock_response

    return create_error_response


@pytest.fixture
def mock_request_body():
    return {
        "sort": {"direction": "ASC", "field": "created_at"},
        "limit": 1000,
        "file_id": ["3fa85f64-5717-4562-b3fc-2c963f66afa6"],
        "reimbursement_organization_settings_id": "org1243settings",
        "members": [
            {
                "first_name": "Jane",
                "last_name": "Doe",
                "date_of_birth": "2024-12-04",
            }
        ],
    }


@pytest.fixture
def raw_ledger_search_response():
    response = Response()
    response.status_code = 200
    response._content = json.dumps(
        {
            "next": None,
            "ledgers": [
                {
                    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "configuration_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "reimbursement_organization_settings_id": "12324452543",
                    "employee_id": "321",
                    "dependent_id": None,
                    "subscriber_id": None,
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "date_of_birth": "2024-12-04",
                    "dependent_first_name": None,
                    "dependent_last_name": None,
                    "dependent_date_of_birth": None,
                    "category": "fertility",
                    "balance_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "file_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "service_date": "2024-12-04",
                    "most_recent_auth_date": "2024-12-04",
                    "created_at": "2024-12-04T06:36:47.592",
                    "adjustment_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "calculated_spend": 9007199254740991,
                    "calculated_cycles": 9007199254740991,
                    "historical_spend": 90072,
                    "historical_cycles_used": 3,
                }
            ],
        }
    ).encode("utf-8")
    return response


@pytest.fixture
def raw_ledger_search_response_with_limits():
    response = Response()
    response.status_code = 200
    response._content = json.dumps(
        {
            "next": {
                "order": "-created_at",
                "limit": 100,
                "cursor": 1001,
            },
            "ledgers": [
                {
                    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "configuration_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "reimbursement_organization_settings_id": "12324452543",
                    "employee_id": "321",
                    "dependent_id": None,
                    "subscriber_id": None,
                    "first_name": "Sandy",
                    "last_name": "Day",
                    "date_of_birth": "2024-12-04",
                    "dependent_first_name": None,
                    "dependent_last_name": None,
                    "dependent_date_of_birth": None,
                    "category": "fertility",
                    "balance_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "file_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "service_date": "2024-12-04",
                    "most_recent_auth_date": "2024-12-04",
                    "created_at": "2024-12-04T06:36:47.592",
                    "adjustment_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "calculated_spend": 9007199254740991,
                    "calculated_cycles": 9007199254740991,
                    "historical_spend": 90072,
                    "historical_cycles_used": 3,
                }
            ],
        }
    ).encode("utf-8")
    return response


@pytest.fixture
def raw_ledger_search_response_empty():
    response = Response()
    response.status_code = 200
    response._content = json.dumps(
        {
            "next": {
                "order": "-created_at",
                "limit": 100,
                "cursor": 1001,
            },
            "ledgers": [],
        }
    ).encode("utf-8")
    return response


def test_make_request__success():
    mock_response = Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {}

    with patch("common.base_http_client.requests.request") as mock_request:
        mock_request.return_value = mock_response

        client = wallet_historical_spend.get_client("http://www.example.com")
        response = client.make_service_request("/foo")

    assert mock_request.call_args.kwargs["url"] == "http://www.example.com/foo"
    assert response is mock_response


def test_make_request__exception():
    with patch("common.base_http_client.requests.request") as mock_request:
        mock_request.side_effect = Exception("fubar")

        client = wallet_historical_spend.get_client("http://www.example.com")
        response = client.make_service_request("/foo")
    assert response.status_code == 400


def test_get_historic_spend_records__success(
    raw_ledger_search_response, mock_request_body
):
    with patch("common.base_http_client.requests.request") as mock_request:
        mock_request.return_value = raw_ledger_search_response

        client = wallet_historical_spend.get_client()
        ledger_entries = client.get_historic_spend_records(
            request_body=mock_request_body
        )

        assert ledger_entries[0].first_name == "Jane"
        assert ledger_entries[0].reimbursement_organization_settings_id == "12324452543"
        assert ledger_entries[0].dependent_first_name is None


def test_get_historic_spend_records_with_limits__success(
    raw_ledger_search_response,
    mock_request_body,
    raw_ledger_search_response_with_limits,
    raw_ledger_search_response_empty,
):
    with patch("common.base_http_client.requests.request") as mock_request:
        mock_request.side_effect = [
            raw_ledger_search_response_with_limits,
            raw_ledger_search_response,
            raw_ledger_search_response_empty,
        ]

        client = wallet_historical_spend.get_client()
        ledger_entries = client.get_historic_spend_records(
            request_body=mock_request_body, request_limit=1
        )

        assert len(ledger_entries) == 2
        assert ledger_entries[0].first_name == "Sandy"
        assert ledger_entries[0].reimbursement_organization_settings_id == "12324452543"
        assert ledger_entries[0].dependent_first_name is None


def test_get_historic_spend_records__invalid_data(mock_response, mock_request_body):
    mock_response._content = b"""
    {
        "foo": "bar"
    }
    """
    with patch(
        "common.base_http_client.requests.request"
    ) as mock_request, pytest.raises(KeyError):
        mock_request.return_value = mock_response

        client = wallet_historical_spend.get_client()
        client.get_historic_spend_records(request_body=mock_request_body)


def test_get_historic_spend_records__missing_required_data(
    mock_response, mock_request_body
):
    mock_response._content = b"""
    {
        "next": null,
        "ledgers": [
            {
              "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
              "configuration_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
              "employee_id": "321",
              "first_name": "Jane",
              "last_name": "Doe",
              "date_of_birth": "2024-12-04",
              "category": "fertility",
              "balance_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
              "file_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
              "service_date": "2024-12-04",
              "most_recent_auth_date": "2024-12-04",
              "created_at": "2024-12-04T06:36:47.592",
              "adjustment_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
              "calculated_spend": 9007199254740991,
              "calculated_cycles": 9007199254740991
            }
        ]
    }
    """

    with patch("common.base_http_client.requests.request") as mock_request:
        mock_request.return_value = mock_response

        client = wallet_historical_spend.get_client()
        ledger_entries = client.get_historic_spend_records(
            request_body=mock_request_body
        )

    assert ledger_entries == []


def test_get_historic_spend_records__request_exception(mock_request_body):
    with patch(
        "common.base_http_client.requests.request"
    ) as mock_request, pytest.raises(WalletHistoricalSpendClientException) as e:
        mock_request.side_effect = Exception("fubar")

        client = wallet_historical_spend.get_client()
        client.get_historic_spend_records(request_body=mock_request_body)

    assert e.value.code == 400
