from unittest.mock import patch

import requests

from common.health_data_collection.base_api import make_hdc_request

test_hdc_url = "https://hdc-test.test"


def test_make_hdc_request__200():
    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {}

    with patch(
        "common.health_data_collection.base_api.requests.request"
    ) as mock_request:
        mock_request.return_value = mock_response

        response = make_hdc_request(url=test_hdc_url)

        assert response.status_code == 200


def test_make_hdc_request__HTTPError():
    mock_error = requests.HTTPError()
    mock_error.response = requests.Response()
    mock_error.response.status_code = 400
    mock_error.response.json = lambda: {}

    with patch(
        "common.health_data_collection.base_api.requests.request"
    ) as mock_request:
        mock_request().raise_for_status.side_effect = mock_error

        response = make_hdc_request(url=test_hdc_url)

        assert response.status_code == 400


def test_make_hdc_request__exception():
    mock_error = Exception()
    mock_error.response = requests.Response()
    mock_error.response.json = lambda: {}

    with patch(
        "common.health_data_collection.base_api.requests.request"
    ) as mock_request:
        mock_request().raise_for_status.side_effect = mock_error

        response = make_hdc_request(url=test_hdc_url)

        assert response.status_code == 400
