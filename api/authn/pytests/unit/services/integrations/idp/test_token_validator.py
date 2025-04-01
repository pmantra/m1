import os
from unittest import mock

import jwt
import pytest

from authn.services.integrations.idp import TokenValidationError, TokenValidator


class TestTokenValidation:
    @staticmethod
    def test_validate_token_succeeds(mock_jwk_client, mock_decode_jwt):
        # Given
        token = "Bearer abcd.abcd.abcd"
        validator = TokenValidator()
        user_id = 123
        email = "foo@example.com"
        sub = "auth0|abcd1234"
        identities = ["member"]
        sign_up_flow = False
        expected_token = {
            "user_id": user_id,
            "identities": identities,
            "email": email,
            "sub": sub,
            "sign_up_flow": sign_up_flow,
        }
        mock_decode_jwt.return_value = {
            validator.decoder.claims["user_id"]: user_id,
            validator.decoder.claims["identities"]: identities,
            validator.decoder.claims["email"]: email,
            validator.decoder.claims["sub"]: sub,
            validator.decoder.claims["sign_up_flow"]: sign_up_flow,
        }

        # When
        decoded = validator.decode_token(token)

        # Then
        assert decoded == expected_token

    @staticmethod
    def test_validate_token_missing(mock_jwk_client, mock_decode_jwt):
        # Given
        token = ""
        validator = TokenValidator()

        # When/Then
        with pytest.raises(TokenValidationError):
            validator.decode_token(token)

    @staticmethod
    def test_validate_token_invalid(mock_jwk_client, mock_decode_jwt):
        # Given
        token = "abcd"
        validator = TokenValidator()

        # When/Then
        with pytest.raises(TokenValidationError):
            validator.decode_token(token)

    @staticmethod
    def test_validate_token_local_dev():
        # Given
        user_id = 123
        encoded = jwt.encode({"maven_user_id": user_id}, "secret", algorithm="HS256")

        # When/Then
        with mock.patch.dict(os.environ, {"OFFLINE_AUTH_ENABLED": "True"}):
            validator = TokenValidator()
            decoded = validator.decode_token(f"Bearer {encoded}")

            # Then
            assert decoded["user_id"] == user_id
