import os
from unittest import mock

import jwt
from zenpy.lib.api_objects import User as ZDUser


class TestAuthenticationViaZenDeskResource:
    def test_get__missing_env_var(self, default_user, client, api_helpers):

        # Given
        mocked_env_vars = {}

        # When
        with mock.patch.dict(os.environ, mocked_env_vars, clear=True):
            res = client.get(
                "/api/v1/zendesk/authentication",
                headers=api_helpers.json_headers(user=default_user),
            )

        # Then
        assert res.status_code == 400
        assert (
            api_helpers.load_json(res)["message"]
            == "ZENDESK_SSO_SECRET env var is missing"
        )

    @mock.patch.dict(
        os.environ,
        {
            "ZENDESK_SSO_SECRET": "A_ZENDESK_SSO_SECRET",
        },
        clear=True,
    )
    def test_get__invalid_zd_user_id(self, client, api_helpers, default_user):

        # Given invalid_user_id
        # When
        res = client.get(
            "/api/v1/zendesk/authentication",
            headers=api_helpers.json_headers(user=default_user),
        )

        # Then
        assert res.status_code == 400
        assert api_helpers.load_json(res)["message"] == "missing zendesk user"

    @mock.patch.dict(
        os.environ,
        {
            "ZENDESK_SSO_SECRET": "A_ZENDESK_SSO_SECRET",
        },
        clear=True,
    )
    @mock.patch("messaging.services.zendesk_client.ZendeskClient.get_zendesk_user")
    def test_get__success(
        self, mock_get_zenpy_user_from_zendesk, default_user, client, api_helpers
    ):
        mock_get_zenpy_user_from_zendesk.return_value = ZDUser(
            name="name", email="email@mavenclinic.com"
        )

        # When
        res = client.get(
            "/api/v1/zendesk/authentication",
            headers=api_helpers.json_headers(user=default_user),
        )

        # Then
        assert res.status_code == 200
        response_data = api_helpers.load_json(res)
        assert response_data["jwt"] is not None

        # Adjust the iat claim to avoid ImmatureSignatureError
        decoded_jwt = jwt.decode(
            response_data["jwt"],
            os.environ["ZENDESK_SSO_SECRET"],
            algorithms=["HS256"],
            options={"verify_iat": False},
        )
        assert decoded_jwt["name"] == "name"
        assert decoded_jwt["email"] == "email@mavenclinic.com"
