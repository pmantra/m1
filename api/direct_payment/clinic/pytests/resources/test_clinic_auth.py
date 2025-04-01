from unittest.mock import MagicMock, patch

import pytest
from flask import Flask, request

from authn.models.user import User
from common.services.api import _USER_ID_HEADER, _VIEW_AS_HEADER
from direct_payment.clinic.resources.clinic_auth import ClinicAuthorizedResource


@pytest.mark.parametrize(
    [
        "user",
        "expected_status_code",
    ],
    [
        ("default_user", 401),
        ("active_fc_user", 204),
        ("inactive_fc_user", 401),
        ("suspended_fc_user", 401),
    ],
)
def test_clinic_check_access(client, api_helpers, request, user, expected_status_code):
    with patch("common.services.api._get_user") as mock_get_user:
        fc_user = request.getfixturevalue(user)
        given_user = (
            fc_user
            if isinstance(fc_user, User)
            else User(id=fc_user.user_id, active=True)
        )
        mock_get_user.return_value = given_user

        res = client.get(
            "/api/v1/direct_payment/clinic/check_access",
            headers=api_helpers.json_headers(user=given_user),
        )

    assert res.status_code == expected_status_code


app = Flask(__name__)


class TestClinicAuthorizedResource:
    @pytest.fixture
    def client(self):
        with app.test_request_context():
            yield app.test_client()

    def test_get_fc_user_profile_valid_user_id(self, client):
        headers = {_USER_ID_HEADER: "123"}
        with patch.object(request, "headers", create=True) as mock_headers:
            mock_headers.get = MagicMock(side_effect=lambda key: headers.get(key))
            resource = ClinicAuthorizedResource()
            with patch.object(resource, "repository", create=True) as mock_repo:
                mock_user = MagicMock()
                mock_repo.get_by_user_id.return_value = mock_user
                user = resource._get_fc_user_profile()
                assert user == mock_user
                mock_repo.get_by_user_id.assert_called_once_with(user_id=123)

    @pytest.mark.parametrize(
        "headers, request_method, request_path, expected_called_user_id",
        [
            (
                {_USER_ID_HEADER: "123", _VIEW_AS_HEADER: "456"},
                "GET",
                "/api/v1/users/me",
                456,
            ),
            (
                {_USER_ID_HEADER: "123", _VIEW_AS_HEADER: "BAD_VIEW_AS_ID"},
                "GET",
                "/api/v1/users/me",
                123,
            ),
            (
                {_USER_ID_HEADER: "123", _VIEW_AS_HEADER: "456"},
                "PUT",
                "/api/v1/users/me",
                123,
            ),
            (
                {_USER_ID_HEADER: "123", _VIEW_AS_HEADER: "456"},
                "GET",
                "/api/v1/not_in_allowlist",
                123,
            ),
        ],
    )
    def test_get_fc_user_profile_view_as(
        self, client, headers, request_method, request_path, expected_called_user_id
    ):
        with patch.object(
            request, "headers", create=True
        ) as mock_headers, patch.object(
            request, "method", request_method
        ), patch.object(
            request, "path", request_path
        ):
            mock_headers.get = MagicMock(side_effect=lambda key: headers.get(key))
            resource = ClinicAuthorizedResource()
            with patch.object(resource, "repository", create=True) as mock_repo:
                mock_user = MagicMock()
                mock_repo.get_by_user_id.return_value = mock_user
                user = resource._get_fc_user_profile()
                assert user == mock_user
                mock_repo.get_by_user_id.assert_called_once_with(
                    user_id=expected_called_user_id
                )
