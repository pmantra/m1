import asyncio
import json
from typing import Dict, Tuple
from unittest.mock import ANY, MagicMock, patch

import aiohttp
import pytest
import requests

from dosespot.models.common import Pagination
from dosespot.resources.dosespot_api import DoseSpotAPI
from dosespot.services.dosespot_auth import DoseSpotAuth


@patch.object(DoseSpotAuth, "get_token")
@patch.object(DoseSpotAuth, "create_token")
@pytest.mark.parametrize(
    ["expected_status_code", "response_text", "expected_result"],
    [
        (401, "Unauthorized", None),
        (
            404,
            json.dumps({"message": "Resource not found", "statusCode": 404}),
            {"message": "Resource not found", "statusCode": 404},
        ),
        (404, None, None),
        (500, json.dumps({}), {}),
        (200, "", None),
        (200, json.dumps({"Result": "Success"}), {"Result": "Success"}),
    ],
)
def test_api_request(
    get_token,
    create_token,
    expected_status_code,
    response_text,
    expected_result,
):

    get_token.return_value = "access_token"
    create_token.return_value = "access_token"

    ds = DoseSpotAPI(should_audit=False)

    res = MagicMock()
    res.status_code = expected_status_code
    res.text = response_text

    with patch.object(requests, "request") as request_mock:
        request_mock.return_value = res
        code, response = ds.api_request("")
        request_mock.assert_called_with(
            "POST",
            "https://my.staging.dosespot.com/webapi/v2/",
            data=None,
            params=None,
            headers={"Authorization": ANY, "Subscription-Key": ANY},
        )

    assert expected_status_code == code
    assert expected_result == response


def test_pharmacy_search_no_next_page():
    api = DoseSpotAPI(should_audit=False)
    with patch.object(DoseSpotAPI, "api_request_async") as mock_api_request:
        data = {
            "Items": [{"PharmacyId": 1}],
            "PageResult": {
                "CurrentPage": 1,
                "TotalPages": 1,
                "PageSize": 1,
                "TotalCount": 1,
                "HasPrevious": False,
                "HasNext": False,
            },
            "Result": {"ResultCode": "OK", "ResultDescription": ""},
        }
        mock_api_request.return_value = 200, data
        response = asyncio.run(api.pharmacy_search(zipcode="92103"))
        mock_api_request.assert_called_with(
            session=ANY,
            url="api/pharmacies/search",
            params={"zip": "92103", "pageNumber": 1},
            method="GET",
            endpoint="pharmacy_search",
        )
        assert response == [{"PharmacyId": 1}]


def test_pharmacy_search_has_next_page():
    api = DoseSpotAPI(should_audit=False)
    with patch.object(
        DoseSpotAPI, "api_request_async", side_effect=paginated_pharmacy_search_result
    ) as mock_api_request:
        response = asyncio.run(api.pharmacy_search(zipcode="92103"))
        assert mock_api_request.call_count == 2
        assert response == [{"PharmacyId": 1}, {"PharmacyId": 2}]


def test_pharmacy_search_return_data_none():
    api = DoseSpotAPI(should_audit=False)
    with patch.object(DoseSpotAPI, "api_request") as mock_api_request:
        mock_api_request.return_value = None, None
        pharmacies, pagination = api.paginated_pharmacy_search(
            page_number=1, zipcode="10013", pharmacy_name="test pharma"
        )
        mock_api_request.assert_called_once()
        assert pharmacies == []
        assert pagination == Pagination(
            current_page=0,
            total_pages=0,
            page_size=0,
            has_previous=False,
            has_next=False,
        )


def test_pharmacy_search_return_data_none_response_code_200():
    api = DoseSpotAPI(should_audit=False)
    with patch.object(DoseSpotAPI, "api_request") as mock_api_request:
        mock_api_request.return_value = 200, None
        pharmacies, pagination = api.paginated_pharmacy_search(
            page_number=1, zipcode="10013", pharmacy_name="test pharma"
        )
        assert pharmacies == []
        assert pagination == Pagination(
            current_page=0,
            total_pages=0,
            page_size=0,
            has_previous=False,
            has_next=False,
        )


def paginated_pharmacy_search_result(
    session: aiohttp.ClientSession, url: str, params: Dict, method: str, endpoint: str
) -> Tuple[int, Dict]:
    if params["pageNumber"] == 1:
        return 200, {
            "Items": [{"PharmacyId": 1}],
            "PageResult": {
                "CurrentPage": 1,
                "TotalPages": 2,
                "PageSize": 1,
                "TotalCount": 2,
                "HasPrevious": False,
                "HasNext": True,
            },
            "Result": {"ResultCode": "OK", "ResultDescription": ""},
        }
    else:
        return 200, {
            "Items": [{"PharmacyId": 2}],
            "PageResult": {
                "CurrentPage": 2,
                "TotalPages": 2,
                "PageSize": 1,
                "TotalCount": 2,
                "HasPrevious": True,
                "HasNext": False,
            },
            "Result": {"ResultCode": "OK", "ResultDescription": ""},
        }


def test_paginated_pharmacy_search():
    api = DoseSpotAPI(should_audit=False)
    with patch.object(DoseSpotAPI, "api_request") as mock_api_request:
        data = {
            "Items": [{"PharmacyId": "123"}],
            "Result": {"ResultCode": "OK", "ResultDescription": ""},
            "PageResult": {
                "CurrentPage": 1,
                "TotalPages": 1,
                "PageSize": 20,
                "HasPrevious": False,
                "HasNext": False,
            },
        }
        mock_api_request.return_value = 200, data
        pharmacies, pagination = api.paginated_pharmacy_search(
            page_number=1, zipcode="10013", pharmacy_name="test pharma"
        )
        mock_api_request.assert_called_once_with(
            url="api/pharmacies/search",
            params={"pageNumber": 1, "zip": "10013", "name": "test pharma"},
            method="GET",
            endpoint="pharmacy_search",
        )
        assert pharmacies == [{"PharmacyId": "123"}]
        assert pagination == Pagination(
            current_page=1,
            total_pages=1,
            page_size=20,
            has_previous=False,
            has_next=False,
        )
