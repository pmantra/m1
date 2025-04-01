import json
import time
from urllib.parse import quote

import pytest

from authn.domain import model
from authn.domain.service.mfa import (
    MFAEnforcementReason,
    UserMFAError,
    UserMFAIntegrationError,
    UserMFARateLimitError,
)
from authn.errors.idp.client_error import (
    REQUEST_TIMEOUT_ERROR,
    ClientError,
    IdentityClientError,
    RateLimitError,
    RequestsError,
)
from authn.models.user import MFAState
from authn.pytests import factories
from authn.resources.auth import (
    BAD_REQUEST_STATUS,
    FORBIDDEN_STATUS,
    INVALID_CREDENTIALS,
    INVALID_REFRESH_TOKEN,
    UNAUTHORIZED,
    UNAUTHORIZED_STATUS,
)
from authn.services.integrations.idp import (
    IDPUser,
    TokenExpiredError,
    TokenValidationError,
)
from authn.util.constants import (
    REFRESH_TOKEN_EXPIRE_AT_KEY,
    SECONDS_FIVE_MIN,
    SECONDS_SEVEN_DAYS,
)


class TestOauthTokenResource:
    @staticmethod
    def test_create_token_resource_flow(
        client,
        api_helpers,
        mock_authn_service,
        mock_user_service,
        mock_mfa_service,
        mock_token_validator,
    ):
        # Given
        user: model.User = factories.UserFactory.create(active=True)
        access_token = "abc.def.ghi"
        mock_authn_service.create_token.return_value = {"access_token": access_token}
        mock_token_validator.get_token_expires_at.return_value = 123
        mock_user_service.get_by_email.return_value = user
        mock_mfa_service.get.return_value = None
        mock_mfa_service.get_user_mfa_status.return_value = (
            False,
            MFAEnforcementReason.NOT_REQUIRED,
        )
        # When
        response = client.post(
            "/api/v1/oauth/token",
            data=json.dumps({"email": user.email, "password": "myPassword123"}),
            headers=api_helpers.json_headers(None),
        )
        # Then
        assert response.status_code == 200
        assert response.json["access_token"] == access_token
        assert response.json["expires_at"] == 123
        now = int(time.time())
        assert response.json[REFRESH_TOKEN_EXPIRE_AT_KEY] is not None
        assert (
            int(response.json[REFRESH_TOKEN_EXPIRE_AT_KEY]) - SECONDS_SEVEN_DAYS
            <= now - SECONDS_FIVE_MIN
        )
        assert (
            int(response.json[REFRESH_TOKEN_EXPIRE_AT_KEY]) - SECONDS_SEVEN_DAYS
            > now - 10 - SECONDS_FIVE_MIN
        )
        assert mock_authn_service.update_user_roles.called

    @staticmethod
    def test_create_token_resource_flow_with_client_error(
        client,
        api_helpers,
        mock_authn_service,
        mock_user_service,
        mock_mfa_service,
        mock_token_validator,
    ):
        # Given
        user: model.User = factories.UserFactory.create(active=True)
        mock_authn_service.create_token.side_effect = ClientError(
            code=403, message="mock error"
        )
        # When
        response = client.post(
            "/api/v1/oauth/token",
            data=json.dumps({"email": user.email, "password": "myPassword123"}),
            headers=api_helpers.json_headers(None),
        )
        # Then
        assert response.status_code == 403

    @staticmethod
    def test_create_token_auth_code_flow(
        client,
        api_helpers,
        mock_authn_service,
        mock_user_service,
        mock_mfa_service,
        mock_token_validator,
    ):
        # Given
        user: model.User = factories.UserFactory.create(active=True)
        access_token = "abc.def.ghi"
        auth_user = factories.UserAuthFactory.create(user_id=user.id, external_id="aaa")
        mock_authn_service.create_token.return_value = {"access_token": access_token}
        mock_authn_service.get_user_auth_by_external_id.return_value = auth_user
        mock_token_validator.decode_token.return_value = {
            "sub": "aaa",
            "user_id": user.id,
        }
        mock_token_validator.get_token_expires_at.return_value = 123
        mock_user_service.get_by_email.return_value = user
        mock_mfa_service.get.return_value = None
        mock_mfa_service.get_user_mfa_status.return_value = (
            False,
            MFAEnforcementReason.NOT_REQUIRED,
        )
        # When
        response = client.post(
            "/api/v1/oauth/token",
            data=json.dumps(
                {
                    "code": "abcd1234",
                    "redirect_uri": "https://qa2.mvnapp.net/app/saml/callback",
                    "is_sso": True,
                }
            ),
            headers=api_helpers.json_headers(None),
        )
        # Then
        assert response.status_code == 200
        assert response.json["access_token"] == access_token
        assert response.json["expires_at"] == 123
        now = int(time.time())
        assert response.json[REFRESH_TOKEN_EXPIRE_AT_KEY] is not None
        assert (
            int(response.json[REFRESH_TOKEN_EXPIRE_AT_KEY]) - SECONDS_SEVEN_DAYS
            <= now - SECONDS_FIVE_MIN
        )
        assert (
            int(response.json[REFRESH_TOKEN_EXPIRE_AT_KEY]) - SECONDS_SEVEN_DAYS
            > now - 10 - SECONDS_FIVE_MIN
        )

    @staticmethod
    def test_create_token_auth_code_flow_with_client_error(
        client,
        api_helpers,
        mock_authn_service,
        mock_user_service,
        mock_mfa_service,
        mock_token_validator,
    ):
        # Given
        mock_authn_service.create_token.side_effect = ClientError(
            code=403, message="mock error"
        )
        # When
        response = client.post(
            "/api/v1/oauth/token",
            data=json.dumps(
                {
                    "code": "abcd1234",
                    "redirect_uri": "https://qa2.mvnapp.net/app/saml/callback",
                    "is_sso": True,
                }
            ),
            headers=api_helpers.json_headers(None),
        )
        # Then
        assert response.status_code == 403

    @staticmethod
    def test_create_token_mfa_enabled(
        client,
        api_helpers,
        mock_authn_service,
        mock_user_service,
        mock_mfa_service,
        mock_token_validator,
    ):
        # Given
        user: model.User = factories.UserFactory.create(active=True)
        user_mfa: model.UserMFA = factories.UserMFAFactory.create(
            user_id=user.id, mfa_state=MFAState.ENABLED
        )
        access_token = "abc.def.ghi"
        mock_authn_service.create_token.return_value = {"access_token": access_token}
        mock_token_validator.get_token_expires_at.return_value = 123
        mock_user_service.get_by_email.return_value = user
        mock_mfa_service.get.return_value = user_mfa
        mock_mfa_service.get_user_mfa_status.return_value = (
            True,
            MFAEnforcementReason.REQUIRED_BY_USER,
        )
        # When
        response = client.post(
            "/api/v1/oauth/token",
            data=json.dumps({"email": user.email, "password": "myPassword123"}),
            headers=api_helpers.json_headers(None),
        )
        # Then
        assert response.status_code == 200
        assert "Enter the code" in response.json["mfa"]["message"]
        assert (
            response.json["mfa"]["enforcement_reason"]
            == MFAEnforcementReason.REQUIRED_BY_USER.name
        )

    @staticmethod
    @pytest.mark.parametrize(
        argnames="user_mfa_state",
        argvalues=[MFAState.DISABLED, MFAState.PENDING_VERIFICATION],
    )
    def test_create_token_mfa_required_but_not_enrolled(
        client,
        api_helpers,
        mock_authn_service,
        mock_user_service,
        mock_mfa_service,
        user_mfa_state,
        mock_token_validator,
    ):
        # Given
        user: model.User = factories.UserFactory.create(id=101, active=True)
        user_mfa: model.UserMFA = factories.UserMFAFactory.create(
            user_id=user.id, mfa_state=user_mfa_state
        )
        mock_user_service.get_by_email.return_value = user
        mock_mfa_service.get.return_value = user_mfa
        mock_mfa_service.get_user_mfa_status.return_value = (
            True,
            MFAEnforcementReason.REQUIRED_BY_ORGANIZATION,
        )
        # When
        response = client.post(
            "/api/v1/oauth/token",
            data=json.dumps({"email": user.email, "password": "myPassword123"}),
            headers=api_helpers.json_headers(None),
        )
        # Then
        assert response.status_code == 200
        assert response.json["access_token"] == "It's pronounced J-WOT."
        assert response.json["expires_at"] == 123456
        assert response.json["mfa_enrollment_required"] is True
        assert (
            response.json["mfa_enforcement_reason"]
            == MFAEnforcementReason.REQUIRED_BY_ORGANIZATION.name
        )
        assert response.json["user_id"] == user.id

    @staticmethod
    def test_create_token_mfa_required_but_missing_user_mfa(
        client,
        api_helpers,
        mock_authn_service,
        mock_user_service,
        mock_mfa_service,
        mock_token_validator,
    ):
        # Given
        user: model.User = factories.UserFactory.create(id=102, active=True)
        mock_user_service.get_by_email.return_value = user
        mock_mfa_service.get_user_mfa_status.return_value = (
            True,
            MFAEnforcementReason.REQUIRED_BY_USER,
        )
        mock_mfa_service.get.return_value = None
        # When
        response = client.post(
            "/api/v1/oauth/token",
            data=json.dumps({"email": user.email, "password": "myPassword123"}),
            headers=api_helpers.json_headers(None),
        )
        # Then
        assert response.status_code == 200
        assert response.json["access_token"] == "It's pronounced J-WOT."
        assert response.json["expires_at"] == 123456
        assert response.json["mfa_enrollment_required"] is True
        assert (
            response.json["mfa_enforcement_reason"]
            == MFAEnforcementReason.REQUIRED_BY_USER.name
        )
        assert response.json["user_id"] == user.id

    @staticmethod
    @pytest.mark.parametrize(
        argnames="mfa_error,expected_status,expected_message",
        argvalues=[
            (UserMFAIntegrationError, 403, "Error sending verification code via SMS"),
            (UserMFARateLimitError, 429, "Too many requests"),
        ],
        ids=[
            "forbidden",
            "too-many-requests",
        ],
    )
    def test_create_token_mfa_enabled_when_mfa_enrollment_fails(
        mfa_error: UserMFAError,
        expected_status: int,
        expected_message: str,
        client,
        api_helpers,
        mock_authn_service,
        mock_user_service,
        mock_mfa_service,
        mock_token_validator,
    ):
        # Given
        user: model.User = factories.UserFactory.create(active=True)
        user_mfa: model.UserMFA = factories.UserMFAFactory.create(
            user_id=user.id, mfa_state=MFAState.ENABLED
        )
        access_token = "abc.def.ghi"
        mock_authn_service.create_token.return_value = {"access_token": access_token}
        mock_token_validator.get_token_expires_at.return_value = 123
        mock_user_service.get_by_email.return_value = user
        mock_mfa_service.get.return_value = user_mfa
        mock_mfa_service.get_user_mfa_status.return_value = (
            True,
            MFAEnforcementReason.REQUIRED_BY_USER,
        )
        mock_mfa_service.send_challenge.side_effect = mfa_error
        # When
        response = client.post(
            "/api/v1/oauth/token",
            data=json.dumps({"email": user.email, "password": "myPassword123"}),
            headers=api_helpers.json_headers(None),
        )
        # Then
        assert response.status_code == expected_status
        assert expected_message in response.json["message"]

    @staticmethod
    def test_create_token_with_requests_timeout(
        client, api_helpers, mock_authn_service, mock_user_service
    ):
        # Given
        user: model.User = factories.UserFactory.create(active=True)
        mock_user_service.get_by_email.return_value = user

        mock_authn_service.create_token.side_effect = RequestsError(
            UNAUTHORIZED_STATUS, REQUEST_TIMEOUT_ERROR
        )

        # When
        response = client.post(
            "/api/v1/oauth/token",
            data=json.dumps({"email": user.email, "password": "myPassword123"}),
            headers=api_helpers.json_headers(None),
        )
        # Then
        assert response.status_code == 401
        assert response.json["message"] == "Request timed out, please try again later"

    @staticmethod
    def test_create_token_with_rate_limiting(
        client, api_helpers, mock_authn_service, mock_user_service
    ):
        # Given
        user: model.User = factories.UserFactory.create(active=True)
        mock_user_service.get_by_email.return_value = user

        mock_authn_service.create_token.side_effect = RateLimitError()

        # When
        response = client.post(
            "/api/v1/oauth/token",
            data=json.dumps({"email": user.email, "password": "myPassword123"}),
            headers=api_helpers.json_headers(None),
        )
        # Then
        assert response.status_code == 429
        assert response.json["message"] == "Too many requests, try again later"

    @staticmethod
    def test_create_token_wrong_combo(client, api_helpers, mock_authn_service):
        # Given
        mock_authn_service.create_token.return_value = None
        # When
        response = client.post(
            "/api/v1/oauth/token",
            data=json.dumps({"email": "foo@bar.com", "password": "myPassword123"}),
            headers=api_helpers.json_headers(None),
        )
        # Then
        assert response.status_code == UNAUTHORIZED_STATUS
        assert response.json["message"] == INVALID_CREDENTIALS

    @staticmethod
    def test_create_token_missing_token(client, api_helpers, mock_authn_service):
        # Given
        mock_authn_service.create_token.return_value = {"scope": "some_scope"}
        # When
        response = client.post(
            "/api/v1/oauth/token",
            data=json.dumps({"email": "foo@bar.com", "password": "myPassword123"}),
            headers=api_helpers.json_headers(None),
        )
        # Then
        assert response.status_code == UNAUTHORIZED_STATUS
        assert response.json["message"] == INVALID_CREDENTIALS

    @staticmethod
    def test_create_token_universal_login(
        client,
        api_helpers,
        mock_authn_service,
        mock_token_validator,
    ):
        # Given
        user: model.User = factories.UserFactory.create(active=True)
        access_token = "abc.def.ghi"
        auth_user = factories.UserAuthFactory.create(user_id=user.id, external_id="aaa")
        client_id = "mock_client_id"

        mock_authn_service.create_token.return_value = {"access_token": access_token}
        mock_authn_service.get_user_auth_by_external_id.return_value = auth_user
        mock_token_validator.decode_token.return_value = {
            "sub": "aaa",
            "user_id": user.id,
        }
        mock_token_validator.get_token_expires_at.return_value = 123

        # When
        response = client.post(
            "/api/v1/oauth/token",
            data=json.dumps(
                {
                    "code": "abcd1234",
                    "redirect_uri": "https://qa2.mvnapp.net/app/oauth/callback",
                    "is_sso": False,
                    "is_universal_login": "true",
                    "client_id": client_id,
                }
            ),
            headers=api_helpers.json_headers(None),
        )
        # Then
        assert response.status_code == 200
        assert response.json["access_token"] == access_token
        now = int(time.time())
        assert response.json["expires_at"] == 123
        assert response.json[REFRESH_TOKEN_EXPIRE_AT_KEY] is not None
        assert (
            int(response.json[REFRESH_TOKEN_EXPIRE_AT_KEY]) - SECONDS_SEVEN_DAYS
            <= now - SECONDS_FIVE_MIN
        )
        assert (
            int(response.json[REFRESH_TOKEN_EXPIRE_AT_KEY]) - SECONDS_SEVEN_DAYS
            > now - 10 - SECONDS_FIVE_MIN
        )
        assert mock_authn_service.update_user_roles.called

    @staticmethod
    def test_create_token_universal_login_with_client_error(
        client,
        api_helpers,
        mock_authn_service,
        mock_token_validator,
    ):
        # Given
        client_id = "mock_client_id"

        mock_authn_service.create_token.side_effect = ClientError(
            code=403, message="mock error"
        )
        # When
        response = client.post(
            "/api/v1/oauth/token",
            data=json.dumps(
                {
                    "code": "abcd1234",
                    "redirect_uri": "https://qa2.mvnapp.net/app/oauth/callback",
                    "is_sso": False,
                    "is_universal_login": "true",
                    "client_id": client_id,
                }
            ),
            headers=api_helpers.json_headers(None),
        )
        # Then
        assert response.status_code == 403

    @staticmethod
    def test_create_token_universal_signup(
        client,
        api_helpers,
        mock_authn_service,
        mock_token_validator,
        mock_user_resource,
    ):
        # Given
        user: model.User = factories.UserFactory.create(active=True)
        access_token = "abc.def.ghi"
        client_id = "mock_client_id"
        mock_authn_service.create_token.return_value = {"access_token": access_token}
        mock_authn_service.get_user_auth_by_external_id.return_value = None
        mock_token_validator.decode_token.return_value = {
            "sub": "aaa",
            "user_id": user.id,
        }
        mock_token_validator.get_token_expires_at.return_value = 123
        idp_user = IDPUser()
        idp_user.email = "aaa@gmail.com"
        mock_authn_service.get_idp_user_by_external_id.return_value = idp_user
        mock_user_resource.signup_flow.return_value = {"id": user.id}
        mock_authn_service.refresh_token.return_value = {"access_token": access_token}
        # When
        response = client.post(
            "/api/v1/oauth/token",
            data=json.dumps(
                {
                    "code": "abcd1234",
                    "redirect_uri": "https://qa2.mvnapp.net/app/oauth/callback",
                    "is_sso": False,
                    "is_universal_login": "true",
                    "client_id": client_id,
                }
            ),
            headers=api_helpers.json_headers(None),
        )
        # Then
        assert response.status_code == 200
        assert response.json["access_token"] == access_token
        assert response.json["flow"] == "signup"
        assert response.json["expires_at"] == 123
        now = int(time.time())
        assert response.json[REFRESH_TOKEN_EXPIRE_AT_KEY] is not None
        assert (
            int(response.json[REFRESH_TOKEN_EXPIRE_AT_KEY]) - SECONDS_SEVEN_DAYS
            <= now - SECONDS_FIVE_MIN
        )
        assert (
            int(response.json[REFRESH_TOKEN_EXPIRE_AT_KEY]) - SECONDS_SEVEN_DAYS
            > now - 10 - SECONDS_FIVE_MIN
        )
        assert mock_authn_service.update_user_roles.called

    @staticmethod
    def test_create_token_universal_login_sso(
        client,
        api_helpers,
        mock_authn_service,
        mock_token_validator,
    ):
        # Given
        user: model.User = factories.UserFactory.create(active=True)
        access_token = "abc.def.ghi"
        auth_user = factories.UserAuthFactory.create(user_id=user.id, external_id="aaa")
        client_id = "mock_client_id"

        mock_authn_service.create_token.return_value = {"access_token": access_token}
        mock_authn_service.get_user_auth_by_external_id.return_value = auth_user
        mock_token_validator.decode_token.return_value = {
            "sub": "aaa",
            "user_id": user.id,
        }
        mock_token_validator.get_token_expires_at.return_value = 123

        # When
        response = client.post(
            "/api/v1/oauth/token",
            data=json.dumps(
                {
                    "code": "abcd1234",
                    "redirect_uri": "https://qa2.mvnapp.net/app/oauth/callback",
                    "is_sso": True,
                    "is_universal_login": "true",
                    "client_id": client_id,
                }
            ),
            headers=api_helpers.json_headers(None),
        )
        # Then
        assert response.status_code == 200
        assert response.json["access_token"] == access_token
        assert response.json["expires_at"] == 123
        now = int(time.time())
        assert response.json[REFRESH_TOKEN_EXPIRE_AT_KEY] is not None
        assert (
            int(response.json[REFRESH_TOKEN_EXPIRE_AT_KEY]) - SECONDS_SEVEN_DAYS
            <= now - SECONDS_FIVE_MIN
        )
        assert (
            int(response.json[REFRESH_TOKEN_EXPIRE_AT_KEY]) - SECONDS_SEVEN_DAYS
            > now - 10 - SECONDS_FIVE_MIN
        )


class TestRefreshOauthTokenResource:
    @staticmethod
    def test_create_token(
        client, api_helpers, mock_authn_service, mock_token_validator
    ):
        # Given
        access_token = "abc.def.ghi"
        mock_authn_service.refresh_token.return_value = {"access_token": access_token}
        mock_token_validator.get_token_expires_at.return_value = 123
        refresh_token = "abcd1234"
        # When
        response = client.post(
            "/api/v1/oauth/token/refresh",
            data=json.dumps({"refresh_token": refresh_token}),
            headers=api_helpers.json_headers(None),
        )
        # Then
        assert response.status_code == 200
        assert response.json["access_token"] == access_token
        assert response.json["expires_at"] == 123

    @staticmethod
    def test_create_token_with_client_error(
        client, api_helpers, mock_authn_service, mock_token_validator
    ):
        # Given
        mock_authn_service.refresh_token.side_effect = ClientError(
            code=403, message="mock error"
        )
        refresh_token = "abcd1234"
        # When
        response = client.post(
            "/api/v1/oauth/token/refresh",
            data=json.dumps({"refresh_token": refresh_token}),
            headers=api_helpers.json_headers(None),
        )
        # Then
        assert response.status_code == 403

    @staticmethod
    def test_create_token_invalid_refresh_token(
        client, api_helpers, mock_authn_service
    ):
        # Given
        mock_authn_service.refresh_token.return_value = None
        refresh_token = "abcd1234"
        # When
        response = client.post(
            "/api/v1/oauth/token/refresh",
            data=json.dumps({"refresh_token": refresh_token}),
            headers=api_helpers.json_headers(None),
        )
        # Then
        assert response.status_code == FORBIDDEN_STATUS
        assert response.json["message"] == INVALID_REFRESH_TOKEN

    @staticmethod
    def test_create_token_missing_token(client, api_helpers, mock_authn_service):
        # Given
        mock_authn_service.refresh_token.return_value = {"scope": "some_scope"}
        refresh_token = "abcd1234"
        # When
        response = client.post(
            "/api/v1/oauth/token/refresh",
            data=json.dumps({"refresh_token": refresh_token}),
            headers=api_helpers.json_headers(None),
        )
        # Then
        assert response.status_code == FORBIDDEN_STATUS
        assert response.json["message"] == INVALID_REFRESH_TOKEN

    @staticmethod
    def test_refresh_token_with_request_timeout(
        client, api_helpers, mock_authn_service
    ):
        # Given
        refresh_token = "abcd1234"
        mock_authn_service.refresh_token.side_effect = RequestsError(
            UNAUTHORIZED_STATUS, REQUEST_TIMEOUT_ERROR
        )
        # When
        response = client.post(
            "/api/v1/oauth/token/refresh",
            data=json.dumps({"refresh_token": refresh_token}),
            headers=api_helpers.json_headers(None),
        )
        # Then
        assert response.status_code == 401
        assert response.json["message"] == "Request timed out, please try again later"


class TestValidateOauthTokenResource:
    @staticmethod
    def test_validate_token(client, mock_user_service, mock_token_validator):
        # Given
        identities = ["member"]
        user: model.User = factories.UserFactory.create(active=True)
        mock_user_service.get_user.return_value = user
        mock_token_validator.decode_token.return_value = {
            "user_id": user.id,
            "identities": identities,
        }
        # When
        response = client.post(
            "/api/v1/oauth/token/validate",
            data=json.dumps({}),
            headers={"Authorization": "Bearer abcd"},
        )
        # Then
        assert response.status_code == 200
        assert response.json["user_id"] == user.id
        assert response.json["identities"] == identities

    @staticmethod
    def test_validate_expired_token(client, mock_token_validator):
        # Given
        expired_message = "token is expired"
        mock_token_validator.decode_token.side_effect = TokenExpiredError(
            expired_message
        )
        # When
        response = client.post(
            "/api/v1/oauth/token/validate",
            data=json.dumps({}),
            headers={"Authorization": "Bearer abcd"},
        )
        # Then
        assert response.status_code == UNAUTHORIZED_STATUS
        assert response.json["message"] == expired_message

    @staticmethod
    def test_validate_invalid_token(client, mock_token_validator):
        # Given
        invalid_message = "token is invalid"
        mock_token_validator.decode_token.side_effect = TokenValidationError(
            invalid_message
        )
        # When
        response = client.post(
            "/api/v1/oauth/token/validate",
            data=json.dumps({}),
            headers={"Authorization": "Bearer abcd"},
        )
        # Then
        assert response.status_code == FORBIDDEN_STATUS
        assert response.json["message"] == invalid_message

    @staticmethod
    def test_validate_user_not_found(client, mock_token_validator, mock_user_service):
        # Given
        mock_user_service.get_user.return_value = None
        mock_token_validator.decode_token.return_value = {"user_id": 999}
        # When
        response = client.post(
            "/api/v1/oauth/token/validate",
            data=json.dumps({}),
            headers={"Authorization": "Bearer abcd"},
        )
        # Then
        assert response.status_code == FORBIDDEN_STATUS
        assert response.json["message"] == UNAUTHORIZED

    @staticmethod
    def test_validate_user_inactive(client, mock_token_validator, mock_user_service):
        # Given
        user: model.User = factories.UserFactory.create(active=False)
        mock_user_service.get_user.return_value = user
        mock_token_validator.decode_token.return_value = {"user_id": user.id}
        # When
        response = client.post(
            "/api/v1/oauth/token/validate",
            data=json.dumps({}),
            headers={"Authorization": "Bearer abcd"},
        )
        # Then
        assert response.status_code == FORBIDDEN_STATUS
        assert response.json["message"] == UNAUTHORIZED


class TestRevokeOauthTokenResource:
    @staticmethod
    def test_revoke_token(client, api_helpers, mock_authn_service):
        # Given
        mock_authn_service.revoke_token.return_value = None
        refresh_token = "abcd1234"
        # When
        response = client.post(
            "/api/v1/oauth/token/revoke",
            data=json.dumps({"refresh_token": refresh_token}),
            headers=api_helpers.json_headers(None),
        )
        # Then
        assert response.status_code == 200

    @staticmethod
    def test_revoke_token_with_client_error(client, api_helpers, mock_authn_service):
        # Given
        mock_authn_service.revoke_token.side_effect = ClientError(
            code=403, message="mock error"
        )
        refresh_token = "abcd1234"
        # When
        response = client.post(
            "/api/v1/oauth/token/revoke",
            data=json.dumps({"refresh_token": refresh_token}),
            headers=api_helpers.json_headers(None),
        )
        # Then
        assert response.status_code == 403

    @staticmethod
    def test_revoke_token_error(client, api_helpers, mock_authn_service):
        # Given
        mock_authn_service.revoke_token.side_effect = IdentityClientError(
            500, "bad request"
        )
        refresh_token = "abcd1234"
        # When
        response = client.post(
            "/api/v1/oauth/token/revoke",
            data=json.dumps({"refresh_token": refresh_token}),
            headers=api_helpers.json_headers(None),
        )
        # Then
        assert response.status_code == BAD_REQUEST_STATUS


class TestAuthorizationResource:
    @staticmethod
    def test_authorize_for_login(client):
        # Given
        client_id = "mock_client_id"
        # When
        response = client.get(f"/api/v1/oauth/authorize?client_id={client_id}")
        # Then
        location = response.headers.get("Location")
        assert f"authorize?response_type=code&client_id={client_id}" in location
        assert "prompt=login" in location
        assert response.status_code == 302

    @staticmethod
    def test_authorize_for_signup(client):
        # Given
        client_id = "mock_client_id"
        # When
        response = client.get(
            f"/api/v1/oauth/authorize?client_id={client_id}&screen_hint=signup"
        )
        # Then
        location = response.headers.get("Location")
        assert f"authorize?response_type=code&client_id={client_id}" in location
        assert "screen_hint=signup" in location
        assert response.status_code == 302

    @staticmethod
    def test_authorize_with_url_parameters(client):
        # Given
        client_id = "mock_client_id"
        # When
        response = client.get(
            f"/api/v1/oauth/authorize?client_id={client_id}&plan_invite_id=planId&referral_code=bonusCode"
        )
        # Then
        location = response.headers.get("Location")
        assert (
            "state=%7B%22client_id%22:%20%22mock_client_id%22,%20%22plan_invite_id%22:%20%22planId%22,"
            "%20%22referral_code%22:%20%22bonusCode%22%7D"
        ) in location
        assert response.status_code == 302

    @staticmethod
    def test_authorize_with_ui_locales(client):
        # Given
        client_id = "mock_client_id"
        # When
        response = client.get(
            f"/api/v1/oauth/authorize?client_id={client_id}&screen_hint=signup&ui_locales=es"
        )
        # Then
        location = response.headers.get("Location")
        assert f"authorize?response_type=code&client_id={client_id}" in location
        assert "ui_locales=es" in location
        assert response.status_code == 302

    @staticmethod
    def test_authorize_with_target_base_uri_parameter(client):
        # Given
        client_id = "mock_client_id"
        target_base_uri = "https://www.example.com"
        redirect_uri = f"{target_base_uri}/app/oauth/callback"
        # When
        response = client.get(
            f"/api/v1/oauth/authorize?client_id={client_id}&target_base_uri={target_base_uri}"
        )
        # Then
        location = response.headers.get("Location")
        assert f"authorize?response_type=code&client_id={client_id}" in location
        assert f"redirect_uri={redirect_uri}" in location
        assert response.status_code == 302

    @staticmethod
    def test_authorize_with_qa_email_parameter(client):
        # Given
        client_id = "mock_client_id"
        qa_email = "test+email@mavenclinic.com"
        encoded_qa_email = quote(qa_email)
        # When
        response = client.get(
            f"/api/v1/oauth/authorize?client_id={client_id}&qa_email={encoded_qa_email}"
        )
        # Then
        location = response.headers.get("Location")
        assert f"authorize?response_type=code&client_id={client_id}" in location
        assert f"login_hint={encoded_qa_email}" in location
        assert response.status_code == 302

    @staticmethod
    def test_authorize_with_app_root_path_parameter(client):
        # Given
        client_id = "mock_client_id"
        target_base_uri = "https://www.example.com"
        app_root_path = "mpractice"
        redirect_uri = f"{target_base_uri}/mpractice/oauth/callback"
        # When
        response = client.get(
            f"/api/v1/oauth/authorize?client_id={client_id}&target_base_uri={target_base_uri}&app_root_path={app_root_path}"
        )
        # Then
        location = response.headers.get("Location")
        assert f"authorize?response_type=code&client_id={client_id}" in location
        assert f"redirect_uri={redirect_uri}" in location
        assert response.status_code == 302

    @staticmethod
    def test_authorize_with_default_app_root_path_parameter(client):
        # Given
        client_id = "mock_client_id"
        target_base_uri = "https://www.example.com"
        redirect_uri = f"{target_base_uri}/app/oauth/callback"
        # When
        response = client.get(
            f"/api/v1/oauth/authorize?client_id={client_id}&target_base_uri={target_base_uri}"
        )
        # Then
        location = response.headers.get("Location")
        assert f"authorize?response_type=code&client_id={client_id}" in location
        assert f"redirect_uri={redirect_uri}" in location
        assert response.status_code == 302


class TestLogoutResource:
    @staticmethod
    def test_logout(client):
        # Given
        client_id = "mock_client_id"
        return_to = "mock_url"
        # When
        response = client.get(
            f"/api/v1/oauth/logout?client_id={client_id}&return_to={return_to}"
        )
        # Then
        location = response.headers.get("Location")
        assert f"/v2/logout?client_id={client_id}&returnTo={return_to}" in location
        assert response.status_code == 302


class TestSignupResource:
    @staticmethod
    def test_signup(client, api_helpers, mock_authn_service, mock_user_resource):
        # Given
        user: model.User = factories.UserFactory.create(active=True)
        idp_user = IDPUser()
        idp_user.email = "aaa@gmail.com"
        mock_authn_service.get_idp_user_by_external_id.return_value = idp_user
        mock_user_resource.signup_flow.return_value = {"id": user.id}

        # When
        response = client.post(
            "/api/v1/oauth/signup",
            data=json.dumps({"id": "externalID"}),
            headers=api_helpers.json_headers(None),
        )
        # Then
        assert response.status_code == 200
        assert "is_sign_up" in response.json

    @staticmethod
    def test_signup_no_request_body(client, api_helpers):
        # When
        response = client.post(
            "/api/v1/oauth/signup",
            headers=api_helpers.json_headers(None),
        )
        # Then
        assert response.status_code == 400

    @staticmethod
    def test_signup_no_id(client, api_helpers):
        # When
        response = client.post(
            "/api/v1/oauth/signup",
            data=json.dumps({"no_id": "externalID"}),
            headers=api_helpers.json_headers(None),
        )
        # Then
        assert response.status_code == 400
