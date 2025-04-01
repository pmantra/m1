import pytest
from werkzeug.exceptions import Unauthorized

from common.services.api import authenticate


class TestCommonAPI:
    @staticmethod
    def test_authenticate_user_id_header(
        app, default_user, mock_jwk_client, mock_decode_jwt
    ):
        # Given
        headers = {"X-Maven-User-ID": default_user.id}
        with app.test_request_context("/test", headers=headers):
            app.preprocess_request()

            # When
            authentication = authenticate(lambda x: x)("success")
            # Then
            assert authentication == "success"

    @staticmethod
    def test_authenticate_both_auth_methods(
        app, default_user, mock_idp_env, mock_jwk_client, mock_decode_jwt
    ):
        # Given
        headers = {
            "Authorization": "Bearer abcd.abcd.abcd",
            "X-Maven-User-ID": default_user.id,
        }
        email_key = mock_idp_env.get("AUTH0_AUDIENCE") + "/email"
        mock_decode_jwt.return_value = {email_key: default_user.email}
        with app.test_request_context("/test", headers=headers):
            app.preprocess_request()

            # When
            authentication = authenticate(lambda x: x)("success")
            # Then
            assert authentication == "success"

    @staticmethod
    def test_inactive_user(
        app, default_user, mock_idp_env, mock_jwk_client, mock_decode_jwt
    ):
        # Given
        headers = {"Authorization": "Bearer abcd.abcd.abcd"}
        email_key = mock_idp_env.get("AUTH0_AUDIENCE") + "/email"
        mock_decode_jwt.return_value = {email_key: default_user.email}
        default_user.active = False
        with app.test_request_context("/test", headers=headers):
            app.preprocess_request()

            # When/Then
            with pytest.raises(Unauthorized):
                authenticate(lambda x: x)("not success")
