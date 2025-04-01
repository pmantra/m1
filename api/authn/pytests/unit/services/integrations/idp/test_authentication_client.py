import pytest
import requests
from auth0 import exceptions
from maven.data_access import errors

from authn.errors.idp.client_error import ClientError, IdentityClientError
from authn.services.integrations import idp


class TestAuthenticationClient:
    @staticmethod
    def test_create_token(mock_auth0_authentication):
        # Given
        expected_token = "my_token"
        token = mock_auth0_authentication.GetToken.return_value
        token.login.return_value = expected_token

        # When
        token = idp.AuthenticationClient().create_token(
            username="username", password="password"
        )

        # Then
        assert token == expected_token

    @staticmethod
    def test_create_token_auth_code(mock_auth0_authentication):
        # Given
        expected_token = "my_token"
        token = mock_auth0_authentication.GetToken.return_value
        token.authorization_code.return_value = expected_token

        # When
        token = idp.AuthenticationClient().create_token(
            code="code", redirect_uri="https://qa2.mvnapp.net/app/saml/callback"
        )

        # Then
        assert token == expected_token

    @staticmethod
    def test_create_token_error(mock_auth0_authentication):
        # Given
        token = mock_auth0_authentication.GetToken.return_value
        token.login.side_effect = exceptions.Auth0Error(403, "Failed", "Bad Login")
        # When/Then
        with pytest.raises(ClientError):
            idp.AuthenticationClient().create_token(
                username="username", password="password"
            )

    @staticmethod
    def test_create_token_auth0_server_error(mock_auth0_authentication):
        # Given
        token = mock_auth0_authentication.GetToken.return_value
        token.login.side_effect = exceptions.Auth0Error(503, "Failed", "Bad Login")
        # When/Then
        with pytest.raises(IdentityClientError):
            idp.AuthenticationClient().create_token(
                username="username", password="password"
            )

    @staticmethod
    def test_create_token_transit_error(mock_auth0_authentication):
        # Given
        token = mock_auth0_authentication.GetToken.return_value
        token.login.side_effect = requests.ReadTimeout()
        # When/Then
        with pytest.raises(errors.TransientRepositoryError):
            idp.AuthenticationClient().create_token(
                username="username", password="password"
            )

    @staticmethod
    def test_refresh_token(mock_auth0_authentication):
        # Given
        expected_token = "my_token"
        token = mock_auth0_authentication.GetToken.return_value
        token.refresh_token.return_value = expected_token

        # When
        token = idp.AuthenticationClient().refresh_token(refresh_token="abcd1234")

        # Then
        assert token == expected_token

    @staticmethod
    def test_refresh_token_error(mock_auth0_authentication):
        # Given
        token = mock_auth0_authentication.GetToken.return_value
        token.refresh_token.side_effect = exceptions.Auth0Error(
            403, "Failed", "Bad Login"
        )
        # When/Then
        with pytest.raises(ClientError):
            idp.AuthenticationClient().refresh_token(refresh_token="abcd1234")

    @staticmethod
    def test_refresh_token__with_auth0_server_error(mock_auth0_authentication):
        # Given
        token = mock_auth0_authentication.GetToken.return_value
        token.refresh_token.side_effect = exceptions.Auth0Error(
            503, "Failed", "Bad Login"
        )
        # When/Then
        with pytest.raises(IdentityClientError):
            idp.AuthenticationClient().refresh_token(refresh_token="abcd1234")

    @staticmethod
    def test_refresh_token_transit_error(mock_auth0_authentication):
        # Given
        token = mock_auth0_authentication.GetToken.return_value
        token.refresh_token.side_effect = requests.ReadTimeout()
        # When/Then
        with pytest.raises(errors.TransientRepositoryError):
            idp.AuthenticationClient().refresh_token(refresh_token="abcd1234")

    @staticmethod
    def test_revoke_token(mock_auth0_authentication):
        # When
        resp = idp.AuthenticationClient().revoke_token(refresh_token="abcd1234")

        # Then
        assert resp is None

    @staticmethod
    def test_revoke_token_error(mock_auth0_authentication):
        # Given
        revoker = mock_auth0_authentication.RevokeToken.return_value
        revoker.revoke_refresh_token.side_effect = exceptions.Auth0Error(
            400, "Failed", "Invalid request"
        )
        # When/Then
        with pytest.raises(ClientError):
            idp.AuthenticationClient().revoke_token(refresh_token="abcd1234")

    @staticmethod
    def test_revoke_token_with_auth0_server_error(mock_auth0_authentication):
        # Given
        revoker = mock_auth0_authentication.RevokeToken.return_value
        revoker.revoke_refresh_token.side_effect = exceptions.Auth0Error(
            500, "Failed", "Invalid request"
        )
        # When/Then
        with pytest.raises(IdentityClientError):
            idp.AuthenticationClient().revoke_token(refresh_token="abcd1234")

    @staticmethod
    def test_revoke_token_transit_error(mock_auth0_authentication):
        # Given
        revoker = mock_auth0_authentication.RevokeToken.return_value
        revoker.revoke_refresh_token.side_effect = requests.ReadTimeout()
        # When/Then
        with pytest.raises(errors.TransientRepositoryError):
            idp.AuthenticationClient().revoke_token(refresh_token="abcd1234")
