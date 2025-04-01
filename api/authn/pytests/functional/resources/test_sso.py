import base64
import json
import os
from unittest import mock

import pytest

from authn.domain import model
from authn.pytests import factories as auth_factories
from authn.services.integrations.idp import IDPUser
from pytests import factories


class TestSAMLComplete:
    @staticmethod
    def test_sso_login(client, mock_sso_service):
        # Given
        external_id = "auth0|abcd1234"
        identity = auth_factories.UserExternalIdentityFactory.create()
        mock_saml_user_data = {
            "idp_connection_name": "abc",
            "email": "x@mock.com",
            "first_name": "mock",
        }
        mock_sso_service.handle_sso_login.return_value = (
            True,
            identity,
            mock_saml_user_data,
        )
        headers = {"Authorization": "Bearer abcd1234"}

        # When/Then
        with mock.patch(
            "authn.services.integrations.idp.TokenValidator"
        ) as mock_validator:
            with mock.patch(
                "authn.resources.sso.TokenValidator",
                autospec=True,
                return_value=mock_validator,
            ):
                mock_validator.decode_token.return_value = {"sub": external_id}
                resp = client.post("/saml/consume/complete", headers=headers)

                assert resp.status_code == 200
                assert resp.json["connection_name"] == "abc"
                assert resp.json["email"] == "x@mock.com"
                assert resp.json["first_name"] == "mock"
                assert resp.json["is_new"] is True
                assert resp.json["external_id"] == base64.b64encode(
                    external_id.encode("utf-8")
                ).decode("utf-8")

    @staticmethod
    def test_sso_login_without_first_name(client, mock_sso_service):
        # Given
        external_id = "auth0|abcd1234"
        identity = auth_factories.UserExternalIdentityFactory.create()
        mock_saml_user_data = {
            "idp_connection_name": "abc",
            "email": "x@mock.com",
        }
        mock_sso_service.handle_sso_login.return_value = (
            True,
            identity,
            mock_saml_user_data,
        )
        headers = {"Authorization": "Bearer abcd1234"}

        # When/Then
        with mock.patch(
            "authn.services.integrations.idp.TokenValidator"
        ) as mock_validator:
            with mock.patch(
                "authn.resources.sso.TokenValidator",
                autospec=True,
                return_value=mock_validator,
            ):
                mock_validator.decode_token.return_value = {"sub": external_id}
                resp = client.post("/saml/consume/complete", headers=headers)

                assert resp.status_code == 200
                assert resp.json["connection_name"] == "abc"
                assert resp.json["email"] == "x@mock.com"
                assert resp.json["first_name"] == ""
                assert resp.json["is_new"] is True
                assert resp.json["external_id"] == base64.b64encode(
                    external_id.encode("utf-8")
                ).decode("utf-8")

    @staticmethod
    def test_sso_relinking_login(client, mock_sso_service):
        # Given
        external_id = "auth0|abcd1234"
        mock_saml_data = {
            "idp_connection_name": "abc",
            "email": "x@gmail.com",
            "first_name": "mock",
        }
        identity_provider = auth_factories.IdentityProviderFactory.create()
        user = auth_factories.UserFactory.create(id=101)
        identity: model.UserExternalIdentity = (
            auth_factories.UserExternalIdentityFactory.create(
                identity_provider_id=identity_provider.id,
                user_id=user.id,
            )
        )
        mock_sso_service.handle_sso_login.return_value = (
            True,
            identity,
            mock_saml_data,
        )
        headers = {"Authorization": "Bearer abcd1234"}

        # When/Then
        with mock.patch(
            "authn.services.integrations.idp.TokenValidator"
        ) as mock_validator:
            with mock.patch(
                "authn.resources.sso.TokenValidator",
                autospec=True,
                return_value=mock_validator,
            ):
                mock_validator.decode_token.return_value = {"sub": external_id}
                resp = client.post("/saml/consume/complete", headers=headers)

                assert resp.status_code == 200
                assert resp.json["connection_name"] == "abc"
                assert resp.json["is_new"] is True
                assert resp.json["external_id"] == base64.b64encode(
                    external_id.encode("utf-8")
                ).decode("utf-8")
                assert not resp.headers.get("X-User-Id")

    @staticmethod
    def test_sso_existing_user_login(client, mock_sso_service):
        # Given
        external_id = "auth0|abcd1234"
        mock_saml_data = {
            "idp_connection_name": "abc",
            "email": "x@gmail.com",
            "first_name": "mock",
        }
        identity_provider = auth_factories.IdentityProviderFactory.create()
        user = auth_factories.UserFactory.create(id=101)
        identity: model.UserExternalIdentity = (
            auth_factories.UserExternalIdentityFactory.create(
                identity_provider_id=identity_provider.id,
                user_id=user.id,
            )
        )

        mock_sso_service.handle_sso_login.return_value = (
            False,
            identity,
            mock_saml_data,
        )
        headers = {"Authorization": "Bearer abcd1234"}

        # When/Then
        with mock.patch(
            "authn.services.integrations.idp.TokenValidator"
        ) as mock_validator:
            with mock.patch(
                "authn.resources.sso.TokenValidator",
                autospec=True,
                return_value=mock_validator,
            ):
                mock_validator.decode_token.return_value = {"sub": external_id}
                resp = client.post("/saml/consume/complete", headers=headers)

                assert resp.status_code == 200
                assert resp.json["connection_name"] == "abc"
                assert resp.json["is_new"] is False
                assert resp.json["external_id"] == base64.b64encode(
                    external_id.encode("utf-8")
                ).decode("utf-8")
                assert resp.headers.get("X-User-Id") == str(user.id)

    @staticmethod
    def test_sso_login_with_none_identity(client, mock_sso_service):
        # Given
        external_id = "auth0|abcd1234"
        mock_saml_data = {
            "idp_connection_name": "abc",
            "email": "x@gmail.com",
            "first_name": "mock",
        }

        mock_sso_service.handle_sso_login.return_value = (
            False,
            None,
            mock_saml_data,
        )
        headers = {"Authorization": "Bearer abcd1234"}

        # When/Then
        with mock.patch(
            "authn.services.integrations.idp.TokenValidator"
        ) as mock_validator:
            with mock.patch(
                "authn.resources.sso.TokenValidator",
                autospec=True,
                return_value=mock_validator,
            ):
                mock_validator.decode_token.return_value = {"sub": external_id}
                resp = client.post("/saml/consume/complete", headers=headers)

                assert resp.status_code == 400

    @staticmethod
    def test_sso_login_with_none_identity_for_new_user(client, mock_sso_service):
        # Given
        external_id = "auth0|abcd1234"
        mock_saml_data = {
            "idp_connection_name": "abc",
            "email": "x@gmail.com",
            "first_name": "mock",
        }

        mock_sso_service.handle_sso_login.return_value = (
            True,
            None,
            mock_saml_data,
        )
        headers = {"Authorization": "Bearer abcd1234"}

        # When/Then
        with mock.patch(
            "authn.services.integrations.idp.TokenValidator"
        ) as mock_validator:
            with mock.patch(
                "authn.resources.sso.TokenValidator",
                autospec=True,
                return_value=mock_validator,
            ):
                mock_validator.decode_token.return_value = {"sub": external_id}
                resp = client.post("/saml/consume/complete", headers=headers)

                assert resp.status_code == 200
                assert resp.json["connection_name"] == "abc"
                assert resp.json["is_new"] is True
                assert resp.json["external_id"] == base64.b64encode(
                    external_id.encode("utf-8")
                ).decode("utf-8")

    @staticmethod
    def test_sso_login_with_none_saml_user_data(client, mock_sso_service):
        # Given
        external_id = "auth0|abcd1234"
        identity_provider = auth_factories.IdentityProviderFactory.create()
        user = auth_factories.UserFactory.create(id=101)
        identity: model.UserExternalIdentity = (
            auth_factories.UserExternalIdentityFactory.create(
                identity_provider_id=identity_provider.id,
                user_id=user.id,
            )
        )
        mock_sso_service.handle_sso_login.return_value = (
            False,
            identity,
            None,
        )
        headers = {"Authorization": "Bearer abcd1234"}

        # When/Then
        with mock.patch(
            "authn.services.integrations.idp.TokenValidator"
        ) as mock_validator:
            with mock.patch(
                "authn.resources.sso.TokenValidator",
                autospec=True,
                return_value=mock_validator,
            ):
                mock_validator.decode_token.return_value = {"sub": external_id}
                resp = client.post("/saml/consume/complete", headers=headers)

                assert resp.status_code == 400

    @staticmethod
    def test_sso_login_with_none_saml_user_data_for_new_user(client, mock_sso_service):
        # Given
        external_id = "auth0|abcd1234"
        identity_provider = auth_factories.IdentityProviderFactory.create()
        user = auth_factories.UserFactory.create(id=101)
        identity: model.UserExternalIdentity = (
            auth_factories.UserExternalIdentityFactory.create(
                identity_provider_id=identity_provider.id,
                user_id=user.id,
            )
        )
        mock_sso_service.handle_sso_login.return_value = (
            True,
            identity,
            None,
        )
        headers = {"Authorization": "Bearer abcd1234"}

        # When/Then
        with mock.patch(
            "authn.services.integrations.idp.TokenValidator"
        ) as mock_validator:
            with mock.patch(
                "authn.resources.sso.TokenValidator",
                autospec=True,
                return_value=mock_validator,
            ):
                mock_validator.decode_token.return_value = {"sub": external_id}
                resp = client.post("/saml/consume/complete", headers=headers)

                assert resp.status_code == 400


class TestSAMLRedirect:
    @staticmethod
    def test_redirects_to_authorization(client):
        with mock.patch.dict(
            os.environ,
            values={
                "AUTH0_DOMAIN": "domain",
                "BASE_URL": "localhost:3000",
                "AUTH0_AUDIENCE": "audience",
                "AUTH0_AUTH_CLIENT_ID": "client_id",
            },
        ):
            resp = client.post("/saml/consume/begin")
            assert resp.status_code == 302


@pytest.mark.parametrize(
    argnames="options,changes,expected_status",
    argvalues=[
        (
            {"email": "foo@bar.com", "password": ""},
            {"email": "bar@foo.com", "password": "Str0ngP@ss"},
            204,
        ),
        (
            {"email": "foo@bar.com", "password": ""},
            {"email": "bar@foo.com", "password": "weaak"},
            400,
        ),
    ],
    ids=[
        "change-email-password",
        "change-email-weak-password",
    ],
)
def test_setup_user(
    options: dict,
    changes: dict,
    expected_status: int,
    client,
    api_helpers,
    mock_idp_management_client,
):
    # Given
    user = factories.DefaultUserFactory.create(**options)
    url = f"/api/v1/users/{user.id}/setup"
    headers = api_helpers.json_headers(user)
    external_id = "auth0|abcd1234"
    mock_idp_user = IDPUser(user_id=external_id)
    mock_idp_management_client.get_user.return_value = mock_idp_user
    mock_idp_management_client.search_by_email.return_value = mock_idp_user
    mock_idp_management_client.update_user.return_value = mock_idp_user
    # When
    response = client.put(url, data=json.dumps(changes), headers=headers)
    # Then
    assert response.status_code == expected_status
