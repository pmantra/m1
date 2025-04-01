import json
from dataclasses import asdict
from unittest import mock
from unittest.mock import MagicMock

import pytest
from flask.testing import FlaskClient

from authn.models.user import User
from dosespot.models.common import Pagination
from utils.api_interaction_mixin import APIInteractionMixin


@pytest.fixture(scope="function")
def mock_dosespot_api() -> MagicMock:
    with mock.patch(
        "dosespot.resources.dosespot_api.DoseSpotAPI",
        autospec=True,
        spec_set=True,
    ) as m:
        with mock.patch(
            "views.prescription.DoseSpotAPI",
            autospec=True,
            return_value=m,
        ):
            yield m


class TestPharmacySearchResource:
    def test_pharmacy_search_v2_success(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
        default_user: User,
        mock_dosespot_api: MagicMock,
    ):
        pharmacies = [
            {
                "PharmacyId": "1",
                "StoreName": "999 Pharmacy",
                "Address1": "999 999th St",
                "Address2": "",
                "City": "NEW YORK",
                "State": "NY",
                "ZipCode": "10027",
                "PrimaryPhone": "555-555-5556",
                "PrimaryPhoneType": "Work",
                "PrimaryFax": "555-555-5555",
            }
        ]
        pagination = Pagination(
            current_page=1,
            total_pages=1,
            page_size=20,
            has_previous=False,
            has_next=False,
        )
        mock_dosespot_api.paginated_pharmacy_search.return_value = (
            pharmacies,
            pagination,
        )
        zipcode = "10013"
        pharmacy_name = "cvs"
        response = client.get(
            f"/api/v2/pharmacies/search?zip_code={zipcode}&pharmacy_name={pharmacy_name}",
            headers=api_helpers.json_headers(default_user),
        )
        assert response.status_code == 200
        response_json = json.loads(response.data)
        assert response_json["data"] == pharmacies
        assert response_json["pagination"] == asdict(pagination)
        mock_dosespot_api.paginated_pharmacy_search.assert_called_once_with(
            page_number=1, zipcode=zipcode, pharmacy_name=pharmacy_name
        )

    def test_pharmacy_search_v2_bad_request(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
        default_user: User,
    ):
        response = client.get(
            "/api/v2/pharmacies/search?zip_code=abc",
            headers=api_helpers.json_headers(default_user),
        )
        assert response.status_code == 400

    def test_pharmacy_search_v2_internal_error(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
        default_user: User,
        mock_dosespot_api: MagicMock,
    ):
        mock_dosespot_api.paginated_pharmacy_search.side_effect = Exception(
            "test error"
        )
        response = client.get(
            "/api/v2/pharmacies/search",
            headers=api_helpers.json_headers(default_user),
        )
        assert response.status_code == 500
        mock_dosespot_api.paginated_pharmacy_search.assert_called_once_with(
            page_number=1, zipcode=None, pharmacy_name=None
        )
