from __future__ import annotations

import dataclasses
from unittest import mock

import pytest

from authn.domain import service
from authn.pytests import factories
from authn.services.integrations.idp.models import AppMetadata, IDPIdentity, IDPUser
from authn.util.constants import SSO_HARD_CHECK_FF_KEY


@pytest.fixture
def saml_assertion(
    mock_onelogin_service,
    mock_idp_repository,
    mock_auth_object,
):
    expected_idp = factories.IdentityProviderFactory.create()
    expected_assertion = factories.SAMLAssertionFactory.create(idp=expected_idp.name)
    mock_onelogin_service.process_request.return_value = (
        expected_idp.name,
        mock_auth_object,
    )
    mock_onelogin_service.parse_auth_object.return_value = expected_assertion
    mock_idp_repository.all.return_value = [expected_idp]
    return expected_idp, expected_assertion


def test_parse_saml_request(saml_assertion, sso_service):
    # Given
    request = factories.SAMLRequestBodyFactory.create()
    expected_idp, expected_assertion = saml_assertion
    # When
    idp, assertion = sso_service.parse_saml_request(request=request)
    # Then
    assert (idp, assertion) == (expected_idp, expected_assertion)


def test_insert_uei_data_from_authn_api(sso_service):
    # Given
    uei = factories.UserExternalIdentityFactory.create()
    uei_dict: dict = uei.__dict__
    uei_dict["updated_at"] = uei_dict["modified_at"]
    uei_dict.pop("modified_at")
    # user_dict is the original data, it simulates the raw data from the authn-api
    # When
    sso_service.insert_uei_data_from_authn_api(data=uei_dict)
    # Then
    ret = sso_service.fetch_identities(user_id=uei.user_id)
    assert ret is not None


def test_update_uei_data_from_authn_api(sso_service):
    # Given
    uei = factories.UserExternalIdentityFactory.create()
    uei_dict: dict = uei.__dict__
    uei_dict["updated_at"] = uei_dict["modified_at"]
    uei_dict.pop("modified_at")
    # user_dict is the original data, it simulates the raw data from the authn-api
    sso_service.insert_uei_data_from_authn_api(data=uei_dict)
    update_data = uei_dict
    update_data["external_user_id"] = "test_update"
    uei_dict["updated_at"] = uei_dict["modified_at"]
    uei_dict.pop("modified_at")
    # When
    sso_service.update_uei_data_from_authn_api(data=update_data)
    # Then
    ret = sso_service.fetch_identities(user_id=uei.user_id)
    assert ret is not None


def test_insert_identity_provider_data_from_authn_api(sso_service):
    # Given
    idp = factories.IdentityProviderFactory.create()
    idp_dict: dict = idp.__dict__
    idp_dict["updated_at"] = idp_dict["modified_at"]
    idp_dict.pop("modified_at")
    # user_dict is the original data, it simulates the raw data from the authn-api
    # When
    sso_service.insert_identity_provider_data_from_authn_api(data=idp_dict)
    # Then
    ret = sso_service.fetch_idp(idp_id=idp.id)
    assert ret is not None


def test_update_identity_provider_data_from_authn_api(sso_service):
    # Given
    idp = factories.IdentityProviderFactory.create()
    idp_dict: dict = idp.__dict__
    idp_dict["updated_at"] = idp_dict["modified_at"]
    idp_dict.pop("modified_at")
    # user_dict is the original data, it simulates the raw data from the authn-api
    sso_service.insert_identity_provider_data_from_authn_api(data=idp_dict)
    update_data = idp_dict
    update_data["name"] = "test_update"
    idp_dict["updated_at"] = idp_dict["modified_at"]
    idp_dict.pop("modified_at")
    # When
    sso_service.update_identity_provider_data_from_authn_api(data=update_data)
    # Then
    ret = sso_service.fetch_idp(idp_id=idp.id)
    assert ret is not None


def test_retrieval_users_per_connection_from_maven(
    sso_service, mock_idp_repository, mock_user_external_identity_repository
):
    # Given
    idp = factories.IdentityProviderFactory.create(id=3)
    sso_service.idps = mock_idp_repository
    sso_service.identities = mock_user_external_identity_repository
    identities = factories.UserExternalIdentityFactory.create_batch(
        5, identity_provider_id=idp.id
    )
    mock_idp_repository.get_by_name.return_value = idp
    mock_user_external_identity_repository.get_by_idp_id.return_value = identities
    # When
    fetched = sso_service.retrieval_users_per_connection_from_maven(
        connection_name=idp.name
    )
    # Then
    assert len(fetched) == 5


def test_retrieval_users_per_connection_from_maven_with_invalid_connection(
    sso_service, mock_idp_repository, mock_user_external_identity_repository
):
    # Given
    sso_service.idps = mock_idp_repository
    sso_service.identities = mock_user_external_identity_repository

    mock_idp_repository.get_by_name.return_value = None
    # When
    fetched = sso_service.retrieval_users_per_connection_from_maven(
        connection_name="invalid"
    )
    # Then
    assert len(fetched) == 0


def test_fetch_identities(sso_service):
    # Given
    user = factories.UserFactory.create()
    identities = factories.UserExternalIdentityFactory.create_batch(10, user_id=user.id)
    sso_service.identities.get_by_user_id.return_value = identities
    # When
    fetched = sso_service.fetch_identities(user_id=user.id)
    # Then
    assert fetched == identities


def test_fetch_identity_by_idp_id_and_external_user_id(sso_service):
    # Given
    identity_provider = factories.IdentityProviderFactory.create()
    identity = factories.UserExternalIdentityFactory.create(
        external_user_id="mock123", identity_provider_id=identity_provider.id
    )
    sso_service.identities.get_by_idp_and_external_user_id.return_value = identity
    # When
    result = sso_service.fetch_identity_by_idp_and_external_user_id(
        idp_id=identity_provider.id, external_user_id="mock123"
    )
    # Then
    assert result == identity


def test_retrieval_idp_user(sso_service, mock_idp_management_client):
    # Given
    sso_service.identities.get_by_reporting_id.return_value = None
    idp_name = "test_idp"
    external_id = "samlp|abcd1234"
    sso_service.management_client = mock_idp_management_client
    idp_user = IDPUser(identities=[IDPIdentity(provider="samlp", connection=idp_name)])
    mock_idp_management_client.get_user.return_value = idp_user
    test_idp = factories.IdentityProviderFactory(name=idp_name, id=1)
    sso_service.idps.get_by_name.return_value = test_idp

    # When
    (
        actual_idp_user,
        actual_provider,
        actual_connection_name,
    ) = sso_service.retrieval_idp_user(external_id=external_id)

    # Then
    assert actual_idp_user == idp_user
    assert actual_provider is not None
    assert actual_connection_name == idp_name


def test_retrieval_idp_user_with_conflict(sso_service, mock_idp_management_client):
    # Given
    conflicting_identity = factories.UserExternalIdentityFactory.create()
    sso_service.identities.get_by_reporting_id.return_value = conflicting_identity
    idp_name = "test_idp"
    external_id = "samlp|abcd1234"
    sso_service.management_client = mock_idp_management_client
    mock_idp_management_client.get_user.return_value = IDPUser(
        identities=[IDPIdentity(provider="samlp", connection=idp_name)]
    )
    test_idp = factories.IdentityProviderFactory(name=idp_name, id=1)
    sso_service.idps.get_by_name.return_value = test_idp

    # When/Then
    with pytest.raises(service.SSOIdentityError):
        sso_service.retrieval_idp_user(external_id=external_id)


def test_update_external_user_id_link(sso_service):
    # Given
    user = factories.UserFactory.create()
    identities = factories.UserExternalIdentityFactory.create_batch(1, user_id=user.id)
    connection_name = "my_connection"
    idp_user = IDPUser(
        email="test@example.com",
        first_name="John",
        last_name="Doe",
        identities=[IDPIdentity(provider="samlp", connection=connection_name)],
    )
    sso_service.users.get_identities.return_value = identities
    external_id = "external-123"
    sso_service.management_client = mock.MagicMock()

    # When
    sso_service.update_external_user_id_link(
        external_id, user.id, connection_name, idp_user
    )

    # Then
    expected_app_metadata = {
        "maven_user_id": user.id,
        "maven_user_identities": identities,
        "original_email": "test@example.com",
        "original_first_name": "John",
        "original_last_name": "Doe",
    }
    sso_service.management_client.update_user.assert_called_once_with(
        external_id, connection_name=connection_name, app_metadata=expected_app_metadata
    )


def test_update_external_user_id_link_with_original_email(sso_service):
    # Given
    user = factories.UserFactory.create()
    identities = factories.UserExternalIdentityFactory.create_batch(1, user_id=user.id)
    connection_name = "my_connection"
    idp_user = IDPUser(
        email="test@example.com",
        first_name="John",
        last_name="Doe",
        identities=[IDPIdentity(provider="samlp", connection=connection_name)],
        app_metadata=AppMetadata(original_email="existing@example.com"),
    )
    sso_service.users.get_identities.return_value = identities
    external_id = "external-123"
    sso_service.management_client = mock.MagicMock()

    # When
    sso_service.update_external_user_id_link(
        external_id, user.id, connection_name, idp_user
    )

    # Then
    expected_app_metadata = {
        "maven_user_id": user.id,
        "maven_user_identities": identities,
    }
    sso_service.management_client.update_user.assert_called_once_with(
        external_id, connection_name=connection_name, app_metadata=expected_app_metadata
    )


class TestHandleSSOLoginLegacyFlow:
    @staticmethod
    def test_new_user(sso_service, mock_idp_management_client, mock_authn_service):
        # Given
        idp_name = "test_idp"
        external_id = "samlp|abcd1234"
        sso_service.management_client = mock_idp_management_client
        mock_idp_management_client.get_user.return_value = IDPUser(
            identities=[IDPIdentity(provider="samlp", connection=idp_name)],
            external_user_id="abc",
        )
        test_idp = factories.IdentityProviderFactory(name=idp_name, id=1)
        user_id = 1
        user = factories.UserFactory.create(id=user_id)
        roles = ["member"]

        sso_service.idps.get_by_name.return_value = test_idp
        sso_service.identities.get_by_reporting_id.return_value = None
        sso_service.identities.get_by_idp_and_external_user_id.return_value = None
        sso_service.users.users.get_by_email.return_value = None
        sso_service.users.create_user.return_value = user
        sso_service.users.get_identities.return_value = roles
        # When
        is_new, identity, saml_user_data = sso_service.handle_sso_login_legacy_flow(
            external_id=external_id
        )
        # Then
        assert is_new is True
        assert saml_user_data.get("idp_connection_name") == idp_name

    @staticmethod
    def test_user_without_external_user_id(
        sso_service, mock_idp_management_client, mock_authn_service
    ):
        # Given
        idp_name = "test_idp"
        external_id = "samlp|abcd1234"
        sso_service.management_client = mock_idp_management_client
        mock_idp_management_client.get_user.return_value = IDPUser(
            identities=[IDPIdentity(provider="samlp", connection=idp_name)]
        )
        test_idp = factories.IdentityProviderFactory(name=idp_name)
        user_id = 1
        user = factories.UserFactory.create(id=user_id)
        roles = ["member"]

        sso_service.idps.get_by_name.return_value = test_idp
        sso_service.identities.get_by_reporting_id.return_value = None
        sso_service.identities.get_by_idp_and_external_user_id.return_value = None
        sso_service.users.users.get_by_email.return_value = None
        sso_service.users.create_user.return_value = user
        sso_service.users.get_identities.return_value = roles
        # When/Then
        with pytest.raises(service.SSOLoginError):
            sso_service.handle_sso_login_legacy_flow(external_id=external_id)

    @staticmethod
    def test_existing_user(sso_service, mock_idp_management_client, mock_authn_service):
        # Given
        idp_name = "test_idp"
        external_id = "samlp|abcd1234"
        organization_external_id = ("org_id",)
        rewards_id = ("rewards_id",)
        sso_service.management_client = mock_idp_management_client
        test_idp = factories.IdentityProviderFactory(name=idp_name, id=1)

        assertion = service.sso.IDPAssertion(
            subject=external_id,
            email="email",
            first_name="first",
            last_name="last",
            organization_external_id=organization_external_id,
            rewards_id=rewards_id,
            employee_id="abcd1234",
            auth0_user_id="asdf",
        )
        sso_service.auth = mock_authn_service
        mock_idp_management_client.get_user.return_value = IDPUser(
            employee_id=assertion.employee_id,
            organization_external_id=organization_external_id,
            rewards_id=rewards_id,
            identities=[IDPIdentity(provider="samlp", connection=idp_name)],
            external_user_id="abc",
        )
        given_identity = factories.UserExternalIdentityFactory.create(
            external_user_id=assertion.subject,
            identity_provider_id=test_idp.id,
            unique_corp_id=assertion.employee_id,
        )
        sso_service.idps.get_by_name.return_value = test_idp
        sso_service.identities.get_by_reporting_id.return_value = None
        sso_service.identities.get_by_idp_and_external_user_id.return_value = (
            given_identity
        )
        expected_changes = dataclasses.replace(
            given_identity,
            external_organization_id=assertion.organization_external_id,
            reporting_id=assertion.rewards_id,
        )
        expected_call = mock.call(instance=expected_changes)
        # When
        is_new, identity, saml_user_data = sso_service.handle_sso_login_legacy_flow(
            external_id=external_id
        )
        # Then
        assert is_new is False
        assert saml_user_data.get("idp_connection_name") == idp_name
        assert sso_service.identities.update.call_args == expected_call

    @staticmethod
    def test_new_user_sso_relinking(
        sso_service, mock_idp_management_client, mock_authn_service
    ):
        # Given
        idp_name = "test_idp"
        external_id = "samlp|abcd1234"
        sso_service.management_client = mock_idp_management_client
        mock_idp_management_client.get_user.return_value = IDPUser(
            identities=[IDPIdentity(provider="samlp", connection=idp_name)],
            external_user_id="abc",
        )
        test_idp = factories.IdentityProviderFactory(name=idp_name, id=1)

        sso_service.idps.get_by_name.return_value = test_idp
        sso_service.identities.get_by_reporting_id.return_value = None
        sso_service.identities.get_by_idp_and_external_user_id.return_value = None
        sso_service.users.users.get_by_email.return_value = None
        # When
        is_new, identity, saml_user_data = sso_service.handle_sso_login_legacy_flow(
            external_id=external_id
        )
        # Then
        assert is_new is True
        assert saml_user_data.get("idp_connection_name") == idp_name
        assert not identity
        sso_service.users.create_user.assert_not_called()
        sso_service.identities.create.assert_not_called()

    @staticmethod
    def test_optum_existing_user(
        sso_service, mock_idp_management_client, mock_authn_service
    ):
        # Given
        idp_name = "Optum-Web"
        external_id = "samlp|abcd1234"
        sso_service.management_client = mock_idp_management_client
        test_idp = factories.IdentityProviderFactory(name=idp_name, id=1)

        assertion = service.sso.IDPAssertion(
            auth0_user_id="abc",
            subject=external_id,
            email="email",
            first_name="first",
            last_name="last",
            organization_external_id="",
            rewards_id="",
            employee_id="",
        )
        sso_service.auth = mock_authn_service
        mock_idp_management_client.get_user.return_value = IDPUser(
            employee_id=assertion.employee_id,
            organization_external_id="",
            rewards_id="",
            identities=[IDPIdentity(provider="samlp", connection=idp_name)],
            external_user_id="abc",
        )
        given_identity = factories.UserExternalIdentityFactory.create(
            external_user_id=assertion.subject,
            identity_provider_id=test_idp.id,
            unique_corp_id=assertion.employee_id,
        )
        sso_service.idps.get_by_name.return_value = test_idp
        sso_service.identities.get_by_reporting_id.return_value = None
        sso_service.identities.get_by_idp_and_external_user_id.return_value = (
            given_identity
        )
        expected_changes = dataclasses.replace(
            given_identity,
            external_organization_id=assertion.organization_external_id,
            reporting_id=assertion.rewards_id,
        )
        expected_call = mock.call(instance=expected_changes)
        # When
        is_new, identity, saml_user_data = sso_service.handle_sso_login_legacy_flow(
            external_id=external_id
        )
        # Then
        assert is_new is False
        assert saml_user_data.get("idp_connection_name") == idp_name
        assert sso_service.identities.update.call_args == expected_call


class TestHandleSSOLogin:
    @staticmethod
    def test_non_idp_user(sso_service, mock_idp_management_client):
        # Given
        sso_service.management_client = mock_idp_management_client
        mock_idp_management_client.get_user.return_value = None
        # When / Then
        with pytest.raises(service.SSOLoginError):
            sso_service.handle_sso_login(external_id="a")

    @staticmethod
    def test_new_handle_sso_login(
        sso_service,
        mock_idp_management_client,
        mock_user_external_identity_repository,
        mock_feature_flag_on,
    ):
        # Given
        mock_idp_user = IDPUser(
            user_id="auth0|abc",
            identities=[IDPIdentity(provider="samlp", connection="abc")],
            external_user_id="abc",
            first_name="fn",
            last_name="ln",
            email="mock@idp.com",
        )
        mock_token = {"key": "value"}
        idp_name = "Virgin-Pulse"
        test_idp = factories.IdentityProviderFactory(name=idp_name, id=1)
        sso_service.management_client = mock_idp_management_client
        mock_idp_management_client.get_user.return_value = mock_idp_user
        sso_service.idps.get_by_name.return_value = test_idp
        sso_service.identities = mock_user_external_identity_repository
        mock_user_external_identity_repository.get_by_auth0_user_id.return_value = None
        mock_user_external_identity_repository.get_by_idp_and_external_user_id.return_value = (
            None
        )
        mock_user_external_identity_repository.get_by_reporting_id.return_value = None
        # When
        is_new, model_result, saml_dict = sso_service.handle_sso_login(
            external_id="abc", token_data=mock_token
        )
        # Then
        assert is_new is True
        assert model_result is None

    @staticmethod
    def test_legacy_handle_sso_login(
        sso_service,
        mock_idp_management_client,
        mock_user_external_identity_repository,
        mock_feature_flag_off,
    ):
        # Given
        mock_idp_user = IDPUser(
            user_id="auth0|abc",
            identities=[IDPIdentity(provider="samlp", connection="abc")],
            external_user_id="abc",
            first_name="fn",
            last_name="ln",
            email="mock@idp.com",
        )
        mock_token = {"key": "value"}
        idp_name = "Virgin-Pulse"
        test_idp = factories.IdentityProviderFactory(name=idp_name, id=1)
        sso_service.management_client = mock_idp_management_client
        mock_idp_management_client.get_user.return_value = mock_idp_user
        sso_service.idps.get_by_name.return_value = test_idp
        sso_service.identities = mock_user_external_identity_repository
        mock_user_external_identity_repository.get_by_auth0_user_id.return_value = None
        mock_user_external_identity_repository.get_by_reporting_id.return_value = None
        mock_user_external_identity_repository.get_by_idp_and_external_user_id.return_value = (
            None
        )
        # When
        is_new, model_result, saml_dict = sso_service.handle_sso_login(
            external_id="abc", token_data=mock_token
        )
        # Then
        assert is_new is True
        assert model_result is None


class TestHandleSSOLoginWithDataCheck:
    @staticmethod
    def test_non_token_dict(sso_service, mock_idp_management_client):
        # Given
        mock_idp_user = IDPUser(
            user_id="auth0|abc",
            identities=[IDPIdentity(provider="samlp", connection="abc")],
            external_user_id="abc",
            first_name="fn",
            last_name="ln",
            email="mock@idp.com",
        )
        # When / Then
        with pytest.raises(service.SSOLoginError):
            sso_service.handle_sso_login_with_data_check(idp_user=mock_idp_user)

    @staticmethod
    def test_non_provider(sso_service, mock_idp_management_client):
        # Given
        mock_idp_user = IDPUser(
            user_id="auth0|abc",
            identities=[IDPIdentity(provider="samlp", connection="abc")],
            external_user_id="abc",
            first_name="fn",
            last_name="ln",
            email="mock@idp.com",
        )
        mock_token = {"key": "value"}
        sso_service.idps.get_by_name.return_value = None
        # When / Then
        with pytest.raises(service.SSOLoginError):
            sso_service.handle_sso_login_with_data_check(
                idp_user=mock_idp_user, token_data=mock_token
            )

    @staticmethod
    def test_non_identity_from_auth0_user(sso_service, mock_idp_management_client):
        # Given
        mock_idp_user = IDPUser(
            user_id="auth0|abc",
            external_user_id="abc",
            first_name="fn",
            last_name="ln",
            email="mock@idp.com",
        )
        mock_token = {"key": "value"}
        sso_service.idps.get_by_name.return_value = None
        # When / Then
        with pytest.raises(service.SSOLoginError):
            sso_service.handle_sso_login_with_data_check(
                idp_user=mock_idp_user, token_data=mock_token
            )

    @staticmethod
    def test_non_external_user_id(sso_service, mock_idp_management_client):
        # Given
        mock_idp_user = IDPUser(
            user_id="auth0|abc",
            identities=[IDPIdentity(provider="samlp", connection="abc")],
            first_name="fn",
            last_name="ln",
            email="mock@idp.com",
        )
        test_idp = factories.IdentityProviderFactory(name="test", id=1)
        mock_token = {"key": "value"}
        sso_service.idps.get_by_name.return_value = test_idp
        # When / Then
        with pytest.raises(service.SSOLoginError):
            sso_service.handle_sso_login_with_data_check(
                idp_user=mock_idp_user, token_data=mock_token
            )

    @staticmethod
    def test_happy_new_user_case_ff_off(
        mock_feature_flag_off,
        sso_service,
        mock_idp_management_client,
        mock_authn_service,
        mock_user_external_identity_repository,
    ):
        # Given
        sso_service.management_client = mock_idp_management_client
        sso_service.identities = mock_user_external_identity_repository
        idp_name = "Virgin-Pulse"
        mock_idp_user = IDPUser(
            user_id="auth0|abc",
            identities=[IDPIdentity(provider="samlp", connection=idp_name)],
            external_user_id="abc",
            first_name="fn",
            last_name="ln",
            email="mock@idp.com",
        )
        test_idp = factories.IdentityProviderFactory(name=idp_name, id=1)
        mock_token = {"key": "value"}
        sso_service.idps.get_by_name.return_value = test_idp
        mock_user_external_identity_repository.get_by_auth0_user_id.return_value = None
        mock_user_external_identity_repository.get_by_idp_and_external_user_id.return_value = (
            None
        )
        mock_user_external_identity_repository.get_by_reporting_id.return_value = None

        # When
        is_new, model_result, saml_dict = sso_service.handle_sso_login_with_data_check(
            idp_user=mock_idp_user, token_data=mock_token
        )
        # Then
        assert is_new is True
        assert model_result is None

    @staticmethod
    def test_happy_new_user_case_ff_on(
        mock_feature_flag_on,
        sso_service,
        mock_idp_management_client,
        mock_authn_service,
        mock_user_external_identity_repository,
    ):
        # Given
        sso_service.management_client = mock_idp_management_client
        sso_service.identities = mock_user_external_identity_repository
        idp_name = "Virgin-Pulse"
        mock_idp_user = IDPUser(
            user_id="auth0|abc",
            identities=[IDPIdentity(provider="samlp", connection=idp_name)],
            external_user_id="abc",
            first_name="fn",
            last_name="ln",
            email="mock@idp.com",
        )
        test_idp = factories.IdentityProviderFactory(name=idp_name, id=1)
        mock_token = {"key": "value"}
        sso_service.idps.get_by_name.return_value = test_idp
        mock_user_external_identity_repository.get_by_auth0_user_id.return_value = None
        mock_user_external_identity_repository.get_by_idp_and_external_user_id.return_value = (
            None
        )
        mock_user_external_identity_repository.get_by_reporting_id.return_value = None

        # When
        is_new, model_result, saml_dict = sso_service.handle_sso_login_with_data_check(
            idp_user=mock_idp_user, token_data=mock_token
        )
        # Then
        assert is_new is True
        assert model_result is None

    @staticmethod
    def test_new_user_case_fail_case_1(
        sso_service,
        mock_idp_management_client,
        mock_authn_service,
        mock_feature_flag_on,
        mock_user_external_identity_repository,
    ):
        # Given
        sso_service.management_client = mock_idp_management_client
        sso_service.identities = mock_user_external_identity_repository
        idp_name = "Virgin-Pulse"
        mock_idp_user = IDPUser(
            user_id="auth0|abc",
            identities=[IDPIdentity(provider="samlp", connection=idp_name)],
            external_user_id="abc",
            first_name="fn",
            last_name="ln",
            email="mock@idp.com",
        )
        test_idp = factories.IdentityProviderFactory(name=idp_name, id=1)
        mock_token = {"key": "value"}
        sso_service.idps.get_by_name.return_value = test_idp
        mock_identities = factories.UserExternalIdentityFactory.create()
        mock_user_external_identity_repository.get_by_auth0_user_id.return_value = (
            mock_identities
        )

        # When / Then
        with pytest.raises(service.SSOError):
            sso_service.handle_sso_login_with_data_check(
                idp_user=mock_idp_user, token_data=mock_token
            )

    @staticmethod
    def test_new_user_case_fail_case_2(
        sso_service,
        mock_idp_management_client,
        mock_authn_service,
        mock_feature_flag_on,
        mock_user_external_identity_repository,
    ):
        # Given
        sso_service.management_client = mock_idp_management_client
        sso_service.identities = mock_user_external_identity_repository
        idp_name = "Virgin-Pulse"
        mock_idp_user = IDPUser(
            user_id="auth0|abc",
            identities=[IDPIdentity(provider="samlp", connection=idp_name)],
            external_user_id="abc",
            first_name="fn",
            last_name="ln",
            email="mock@idp.com",
        )
        test_idp = factories.IdentityProviderFactory(name=idp_name, id=1)
        mock_token = {"key": "value"}
        sso_service.idps.get_by_name.return_value = test_idp
        mock_identities = factories.UserExternalIdentityFactory.create()
        mock_user_external_identity_repository.get_by_auth0_user_id.return_value = None
        mock_user_external_identity_repository.get_by_idp_and_external_user_id.return_value = (
            mock_identities
        )

        # When / Then
        with pytest.raises(service.SSOIdentityError):
            sso_service.handle_sso_login_with_data_check(
                idp_user=mock_idp_user, token_data=mock_token
            )

    @staticmethod
    def test_happy_existing_user_case_with_ff_off(
        sso_service,
        mock_idp_management_client,
        mock_authn_service,
        mock_user_external_identity_repository,
        mock_user_service,
        mock_feature_flag_off,
    ):
        # Given
        sso_service.management_client = mock_idp_management_client
        sso_service.identities = mock_user_external_identity_repository
        sso_service.users = mock_user_service

        idp_name = "test_idp"
        external_id = "samlp|abcd1234"
        mock_email = "mock@idp.com"
        mock_first_name = "fn"
        mock_last_name = "ln"
        mock_employee_id = "mock_ee_id"
        mock_idp_user = IDPUser(
            user_id="mock",
            identities=[IDPIdentity(provider="samlp", connection=idp_name)],
            external_user_id="abc",
            first_name=mock_first_name,
            last_name=mock_last_name,
            email=mock_email,
            employee_id=mock_employee_id,
            rewards_id="mock_rewards",
        )
        test_idp = factories.IdentityProviderFactory(name=idp_name, id=1)
        mock_token = {"user_id": "123"}
        mock_identities = factories.UserExternalIdentityFactory.create(
            user_id=123,
            sso_email=mock_email,
            auth0_user_id=external_id,
            sso_user_first_name=mock_first_name,
            sso_user_last_name=mock_last_name,
            unique_corp_id=mock_employee_id,
        )
        sso_service.idps.get_by_name.return_value = test_idp
        mock_user_external_identity_repository.get_by_auth0_user_id.return_value = (
            mock_identities
        )
        mock_user_external_identity_repository.get_by_idp_and_external_user_id.return_value = (
            mock_identities
        )
        sso_service.identities.get_by_reporting_id.return_value = None

        expected_changes = dataclasses.replace(
            mock_identities,
            reporting_id=mock_idp_user.rewards_id,
            external_organization_id=mock_idp_user.organization_external_id,
        )
        expected_call = mock.call(instance=expected_changes)
        mock_user_service.get_identities.return_value = "member"
        mock_idp_management_client.update_user.return_value = None
        # When
        is_new, model_result, saml_dict = sso_service.handle_sso_login_with_data_check(
            idp_user=mock_idp_user, token_data=mock_token
        )
        # Then
        assert is_new is False
        assert model_result.id == mock_identities.id
        assert sso_service.identities.update.call_args == expected_call
        assert model_result.sso_email == mock_email
        assert model_result.reporting_id == "mock_rewards"

    @staticmethod
    def test_happy_existing_user_case_with_ff_on(
        sso_service,
        mock_idp_management_client,
        mock_authn_service,
        mock_user_external_identity_repository,
        mock_idp_repository,
        mock_user_service,
        mock_feature_flag_on,
    ):
        # Given
        sso_service.management_client = mock_idp_management_client
        sso_service.identities = mock_user_external_identity_repository
        sso_service.idps = mock_idp_repository
        sso_service.users = mock_user_service

        idp_name = "test_idp"
        external_id = "samlp|abcd1234"
        mock_email = "mock@idp.com"
        mock_first_name = "fn"
        mock_last_name = "ln"
        mock_employee_id = "mock_ee_id"
        mock_idp_user = IDPUser(
            user_id="mock",
            identities=[IDPIdentity(provider="samlp", connection=idp_name)],
            external_user_id="abc",
            first_name=mock_first_name,
            last_name=mock_last_name,
            email=mock_email,
            employee_id=mock_employee_id,
            rewards_id="mock_rewards",
        )
        test_idp = factories.IdentityProviderFactory(name=idp_name, id=1)
        mock_token = {"user_id": "123"}
        mock_identities = factories.UserExternalIdentityFactory.create(
            user_id=123,
            sso_email=mock_email,
            auth0_user_id=external_id,
            sso_user_first_name=mock_first_name,
            sso_user_last_name=mock_last_name,
            unique_corp_id=mock_employee_id,
        )
        mock_idp_repository.get_by_name.return_value = test_idp
        mock_user_external_identity_repository.get_by_auth0_user_id.return_value = (
            mock_identities
        )
        mock_user_external_identity_repository.get_by_idp_and_external_user_id.return_value = (
            mock_identities
        )
        mock_user_external_identity_repository.get_by_reporting_id.return_value = None

        expected_changes = dataclasses.replace(
            mock_identities,
            reporting_id=mock_idp_user.rewards_id,
            external_organization_id=mock_idp_user.organization_external_id,
        )
        expected_call = mock.call(instance=expected_changes)
        mock_user_service.get_identities.return_value = "member"
        mock_idp_management_client.update_user.return_value = None
        # When
        is_new, model_result, saml_dict = sso_service.handle_sso_login_with_data_check(
            idp_user=mock_idp_user, token_data=mock_token
        )
        # Then
        assert is_new is False
        assert model_result.id == mock_identities.id
        assert sso_service.identities.update.call_args == expected_call
        assert model_result.sso_email == mock_email
        assert model_result.reporting_id == "mock_rewards"

    @staticmethod
    def test_existing_user_case_fail_case_1(
        sso_service,
        mock_idp_management_client,
        mock_authn_service,
        mock_feature_flag_on,
        mock_user_external_identity_repository,
        mock_idp_repository,
        mock_user_service,
    ):
        # Given
        sso_service.management_client = mock_idp_management_client
        sso_service.identities = mock_user_external_identity_repository
        sso_service.idps = mock_idp_repository
        sso_service.users = mock_user_service

        idp_name = "test_idp"
        mock_email = "mock@idp.com"
        mock_first_name = "fn"
        mock_last_name = "ln"
        mock_employee_id = "mock_ee_id"
        mock_idp_user = IDPUser(
            user_id="mock",
            identities=[IDPIdentity(provider="samlp", connection=idp_name)],
            external_user_id="abc",
            first_name=mock_first_name,
            last_name=mock_last_name,
            email=mock_email,
            employee_id=mock_employee_id,
        )
        test_idp = factories.IdentityProviderFactory(name=idp_name, id=1)
        mock_token = {"user-id": "123"}
        mock_idp_repository.get_by_name.return_value = test_idp
        mock_user_external_identity_repository.get_by_auth0_user_id.return_value = None

        # When / Then
        with pytest.raises(service.SSOIdentityError):
            sso_service.handle_sso_login_with_data_check(
                idp_user=mock_idp_user, token_data=mock_token
            )

    @staticmethod
    def test_existing_user_case_fail_case_2(
        sso_service,
        mock_idp_management_client,
        mock_authn_service,
        mock_feature_flag_on,
        mock_user_external_identity_repository,
        mock_idp_repository,
        mock_user_service,
    ):
        # Given
        sso_service.management_client = mock_idp_management_client
        sso_service.identities = mock_user_external_identity_repository
        sso_service.idps = mock_idp_repository
        sso_service.users = mock_user_service

        idp_name = "test_idp"
        external_id = "samlp|abcd1234"
        mock_email = "mock@idp.com"
        mock_first_name = "fn"
        mock_last_name = "ln"
        mock_employee_id = "mock_ee_id"
        mock_idp_user = IDPUser(
            user_id="mock",
            identities=[IDPIdentity(provider="samlp", connection=idp_name)],
            external_user_id="abc",
            first_name=mock_first_name,
            last_name=mock_last_name,
            email=mock_email,
            employee_id=mock_employee_id,
        )
        test_idp = factories.IdentityProviderFactory(name=idp_name, id=1)
        mock_token = {"user_id": "123"}
        mock_identities = factories.UserExternalIdentityFactory.create(
            user_id=111,
            sso_email=mock_email,
            auth0_user_id=external_id,
            sso_user_first_name=mock_first_name,
            sso_user_last_name=mock_last_name,
            unique_corp_id=mock_employee_id,
        )
        mock_idp_repository.get_by_name.return_value = test_idp
        mock_user_external_identity_repository.get_by_auth0_user_id.return_value = (
            mock_identities
        )

        # When / Then
        with pytest.raises(service.SSOIdentityError):
            sso_service.handle_sso_login_with_data_check(
                idp_user=mock_idp_user, token_data=mock_token
            )

    @staticmethod
    def test_existing_user_case_fail_case_2_with_identity_missing_and_hard_check_off(
        sso_service,
        mock_idp_management_client,
        mock_authn_service,
        mock_feature_flag_on,
        mock_user_external_identity_repository,
        mock_idp_repository,
        mock_user_service,
    ):
        # Given
        mock_feature_flag_on.side_effect = lambda flag_name, *args, **kwargs: {
            SSO_HARD_CHECK_FF_KEY: False
        }.get(flag_name, True)
        sso_service.management_client = mock_idp_management_client
        sso_service.identities = mock_user_external_identity_repository
        sso_service.idps = mock_idp_repository
        sso_service.users = mock_user_service

        idp_name = "test_idp"
        external_id = "samlp|abcd1234"
        mock_email = "mock@idp.com"
        mock_first_name = "fn"
        mock_last_name = "ln"
        mock_employee_id = "mock_ee_id"
        mock_idp_user = IDPUser(
            user_id="mock",
            identities=[IDPIdentity(provider="samlp", connection=idp_name)],
            external_user_id="abc",
            first_name=mock_first_name,
            last_name=mock_last_name,
            email=mock_email,
            employee_id=mock_employee_id,
        )
        test_idp = factories.IdentityProviderFactory(name=idp_name, id=1)
        mock_token = {"user_id": "123"}
        mock_identities = factories.UserExternalIdentityFactory.create(
            user_id=111,
            sso_email=mock_email,
            auth0_user_id=external_id,
            sso_user_first_name=mock_first_name,
            sso_user_last_name=mock_last_name,
            unique_corp_id=mock_employee_id,
        )
        mock_idp_repository.get_by_name.return_value = test_idp
        mock_user_external_identity_repository.get_by_auth0_user_id.return_value = (
            mock_identities
        )
        mock_user_external_identity_repository.get_by_idp_and_external_user_id.return_value = (
            None
        )
        mock_user_external_identity_repository.get_by_reporting_id.return_value = None

        # When
        is_new, model_result, saml_dict = sso_service.handle_sso_login_with_data_check(
            idp_user=mock_idp_user, token_data=mock_token
        )
        # Then
        assert is_new is True
        assert model_result is None

    @staticmethod
    def test_existing_user_case_fail_case_2_with_identity_missing_and_hard_check_off_with_conflict(
        sso_service,
        mock_idp_management_client,
        mock_authn_service,
        mock_feature_flag_on,
        mock_user_external_identity_repository,
        mock_idp_repository,
        mock_user_service,
    ):
        # Given
        mock_feature_flag_on.side_effect = lambda flag_name, *args, **kwargs: {
            SSO_HARD_CHECK_FF_KEY: False
        }.get(flag_name, True)
        sso_service.management_client = mock_idp_management_client
        sso_service.identities = mock_user_external_identity_repository
        sso_service.idps = mock_idp_repository
        sso_service.users = mock_user_service

        idp_name = "test_idp"
        external_id = "samlp|abcd1234"
        mock_email = "mock@idp.com"
        mock_first_name = "fn"
        mock_last_name = "ln"
        mock_employee_id = "mock_ee_id"
        mock_idp_user = IDPUser(
            user_id="mock",
            identities=[IDPIdentity(provider="samlp", connection=idp_name)],
            external_user_id="abc",
            first_name=mock_first_name,
            last_name=mock_last_name,
            email=mock_email,
            employee_id=mock_employee_id,
        )
        test_idp = factories.IdentityProviderFactory(name=idp_name, id=1)
        mock_token = {"user_id": "123"}
        mock_identities = factories.UserExternalIdentityFactory.create(
            user_id=111,
            sso_email=mock_email,
            auth0_user_id=external_id,
            sso_user_first_name=mock_first_name,
            sso_user_last_name=mock_last_name,
            unique_corp_id=mock_employee_id,
        )
        mock_idp_repository.get_by_name.return_value = test_idp
        mock_user_external_identity_repository.get_by_auth0_user_id.return_value = (
            mock_identities
        )
        mock_user_external_identity_repository.get_by_idp_and_external_user_id.return_value = (
            None
        )
        mock_user_external_identity_repository.get_by_reporting_id.return_value = (
            mock_identities
        )

        # When / Then
        with pytest.raises(service.SSOIdentityError):
            sso_service.handle_sso_login_with_data_check(
                idp_user=mock_idp_user, token_data=mock_token
            )

    @staticmethod
    def test_existing_user_case_fail_case_2_with_identity_missing_and_enable_hard_check(
        sso_service,
        mock_idp_management_client,
        mock_authn_service,
        mock_feature_flag_off,
        mock_user_external_identity_repository,
        mock_idp_repository,
        mock_user_service,
    ):
        # Given
        mock_feature_flag_off.side_effect = lambda flag_name, *args, **kwargs: {
            SSO_HARD_CHECK_FF_KEY: True
        }.get(flag_name, False)
        sso_service.management_client = mock_idp_management_client
        sso_service.identities = mock_user_external_identity_repository
        sso_service.idps = mock_idp_repository
        sso_service.users = mock_user_service

        idp_name = "test_idp"
        mock_email = "mock@idp.com"
        mock_first_name = "fn"
        mock_last_name = "ln"
        mock_employee_id = "mock_ee_id"
        mock_idp_user = IDPUser(
            user_id="mock",
            identities=[IDPIdentity(provider="samlp", connection=idp_name)],
            external_user_id="abc",
            first_name=mock_first_name,
            last_name=mock_last_name,
            email=mock_email,
            employee_id=mock_employee_id,
        )
        test_idp = factories.IdentityProviderFactory(name=idp_name, id=1)
        mock_token = {"user_id": "123"}
        mock_idp_repository.return_value = test_idp
        mock_user_external_identity_repository.get_by_auth0_user_id.return_value = None
        mock_user_external_identity_repository.get_by_idp_and_external_user_id.return_value = (
            None
        )
        # When / Then
        with pytest.raises(service.SSOError):
            sso_service.handle_sso_login_with_data_check(
                idp_user=mock_idp_user, token_data=mock_token
            )

    @staticmethod
    def test_existing_user_case_fail_case_3(
        sso_service,
        mock_idp_management_client,
        mock_authn_service,
        mock_feature_flag_on,
        mock_user_external_identity_repository,
        mock_idp_repository,
        mock_user_service,
    ):
        # Given
        sso_service.management_client = mock_idp_management_client
        sso_service.identities = mock_user_external_identity_repository
        sso_service.idps = mock_idp_repository
        sso_service.users = mock_user_service

        idp_name = "test_idp"
        external_id = "samlp|abcd1234"
        mock_email = "mock@idp.com"
        mock_first_name = "fn"
        mock_last_name = "ln"
        mock_employee_id = "mock_ee_id"
        mock_idp_user = IDPUser(
            user_id="mock",
            identities=[IDPIdentity(provider="samlp", connection=idp_name)],
            external_user_id="abc",
            first_name=mock_first_name,
            last_name=mock_last_name,
            email=mock_email,
            employee_id=mock_employee_id,
        )
        test_idp = factories.IdentityProviderFactory(name=idp_name, id=1)
        mock_token = {"user_id": "123"}
        mock_identities = factories.UserExternalIdentityFactory.create(
            user_id=123,
            sso_email=mock_email,
            auth0_user_id=external_id,
            sso_user_first_name=mock_first_name,
            sso_user_last_name=mock_last_name,
            unique_corp_id=mock_employee_id,
        )
        mock_idp_repository.get_by_name.return_value = test_idp
        mock_user_external_identity_repository.get_by_auth0_user_id.return_value = (
            mock_identities
        )
        mock_user_external_identity_repository.get_by_idp_and_external_user_id.return_value = (
            None
        )

        # When / Then
        with pytest.raises(service.SSOError):
            sso_service.handle_sso_login_with_data_check(
                idp_user=mock_idp_user, token_data=mock_token
            )

    @staticmethod
    def test_existing_user_case_fail_case_4_ff_off(
        sso_service,
        mock_idp_management_client,
        mock_authn_service,
        mock_feature_flag_off,
        mock_user_external_identity_repository,
        mock_idp_repository,
        mock_user_service,
    ):
        # Given
        sso_service.management_client = mock_idp_management_client
        sso_service.identities = mock_user_external_identity_repository
        sso_service.idps = mock_idp_repository
        sso_service.users = mock_user_service

        idp_name = "test_idp"
        external_id = "samlp|abcd1234"
        mock_email = "mock@idp.com"
        mock_first_name = "fn"
        mock_last_name = "ln"
        mock_employee_id = "mock_ee_id"
        mock_idp_user = IDPUser(
            user_id="mock",
            identities=[IDPIdentity(provider="samlp", connection=idp_name)],
            external_user_id="abc",
            first_name=mock_first_name,
            last_name=mock_last_name,
            email=mock_email,
            employee_id=mock_employee_id,
            rewards_id="mock_rewards",
        )
        test_idp = factories.IdentityProviderFactory(name=idp_name, id=1)
        mock_token = {"user_id": "123"}
        mock_identities = factories.UserExternalIdentityFactory.create(
            user_id=123,
            sso_email="abc@idp.com",
            auth0_user_id=external_id,
            sso_user_first_name=mock_first_name,
            sso_user_last_name=mock_last_name,
            unique_corp_id=mock_employee_id,
        )
        mock_idp_repository.get_by_name.return_value = test_idp
        mock_user_external_identity_repository.get_by_auth0_user_id.return_value = (
            mock_identities
        )
        mock_user_external_identity_repository.get_by_idp_and_external_user_id.return_value = (
            mock_identities
        )
        expected_changes = dataclasses.replace(
            mock_identities,
            reporting_id=mock_idp_user.rewards_id,
            external_organization_id=mock_idp_user.organization_external_id,
        )
        expected_call = mock.call(instance=expected_changes)
        mock_user_service.get_identities.return_value = "member"
        mock_idp_management_client.update_user.return_value = None
        # When
        is_new, model_result, saml_dict = sso_service.handle_sso_login_with_data_check(
            idp_user=mock_idp_user, token_data=mock_token
        )
        # Then
        assert is_new is False
        assert model_result.id == mock_identities.id
        assert sso_service.identities.update.call_args == expected_call
        assert model_result.sso_email == "abc@idp.com"
        assert model_result.sso_email != mock_email
        assert model_result.reporting_id == "mock_rewards"

    @staticmethod
    def test_existing_user_case_fail_case_4_ff_on_with_disable_hard_check(
        sso_service,
        mock_idp_management_client,
        mock_authn_service,
        mock_feature_flag_on,
        mock_user_external_identity_repository,
        mock_idp_repository,
        mock_user_service,
    ):
        # Given
        mock_feature_flag_on.side_effect = lambda flag_name, *args, **kwargs: {
            SSO_HARD_CHECK_FF_KEY: False
        }.get(flag_name, True)
        sso_service.management_client = mock_idp_management_client
        sso_service.identities = mock_user_external_identity_repository
        sso_service.idps = mock_idp_repository
        sso_service.users = mock_user_service

        idp_name = "test_idp"
        external_id = "samlp|abcd1234"
        mock_email = "mock@idp.com"
        mock_first_name = "fn"
        mock_last_name = "ln"
        mock_employee_id = "mock_ee_id"
        mock_idp_user = IDPUser(
            user_id="mock",
            identities=[IDPIdentity(provider="samlp", connection=idp_name)],
            external_user_id="abc",
            first_name=mock_first_name,
            last_name=mock_last_name,
            email=mock_email,
            employee_id=mock_employee_id,
            rewards_id="mock_rewards",
        )
        test_idp = factories.IdentityProviderFactory(name=idp_name, id=1)
        mock_token = {"user_id": "123"}
        mock_identities = factories.UserExternalIdentityFactory.create(
            user_id=123,
            sso_email="abc@idp.com",
            auth0_user_id=external_id,
            sso_user_first_name=mock_first_name,
            sso_user_last_name=mock_last_name,
            unique_corp_id=mock_employee_id,
        )
        mock_idp_repository.get_by_name.return_value = test_idp
        mock_user_external_identity_repository.get_by_auth0_user_id.return_value = (
            mock_identities
        )
        mock_user_external_identity_repository.get_by_idp_and_external_user_id.return_value = (
            mock_identities
        )
        expected_changes = dataclasses.replace(
            mock_identities,
            reporting_id=mock_idp_user.rewards_id,
            external_organization_id=mock_idp_user.organization_external_id,
        )
        expected_call = mock.call(instance=expected_changes)
        mock_user_service.get_identities.return_value = "member"
        mock_idp_management_client.update_user.return_value = None
        # When
        is_new, model_result, saml_dict = sso_service.handle_sso_login_with_data_check(
            idp_user=mock_idp_user, token_data=mock_token
        )
        # Then
        assert is_new is False
        assert model_result.id == mock_identities.id
        assert sso_service.identities.update.call_args == expected_call
        assert model_result.sso_email == "abc@idp.com"
        assert model_result.sso_email != mock_email
        assert model_result.reporting_id == "mock_rewards"

    @staticmethod
    def test_existing_user_case_fail_case_4_1(
        sso_service,
        mock_idp_management_client,
        mock_authn_service,
        mock_feature_flag_on,
        mock_user_external_identity_repository,
        mock_idp_repository,
        mock_user_service,
    ):
        # Given
        sso_service.management_client = mock_idp_management_client
        sso_service.identities = mock_user_external_identity_repository
        sso_service.idps = mock_idp_repository
        sso_service.users = mock_user_service

        idp_name = "test_idp"
        external_id = "samlp|abcd1234"
        mock_email = "mock@idp.com"
        mock_first_name = "fn"
        mock_last_name = "ln"
        mock_employee_id = "mock_ee_id"
        mock_idp_user = IDPUser(
            user_id="mock",
            identities=[IDPIdentity(provider="samlp", connection=idp_name)],
            external_user_id="abc",
            first_name=mock_first_name,
            last_name=mock_last_name,
            email=mock_email,
            employee_id=mock_employee_id,
        )
        test_idp = factories.IdentityProviderFactory(name=idp_name, id=1)
        mock_token = {"user_id": "123"}
        mock_identities = factories.UserExternalIdentityFactory.create(
            user_id=123,
            sso_email="abc@idp.com",
            auth0_user_id=external_id,
            sso_user_first_name=mock_first_name,
            sso_user_last_name=mock_last_name,
            unique_corp_id=mock_employee_id,
        )
        mock_idp_repository.get_by_name.return_value = test_idp
        mock_user_external_identity_repository.get_by_auth0_user_id.return_value = (
            mock_identities
        )
        mock_user_external_identity_repository.get_by_idp_and_external_user_id.return_value = (
            mock_identities
        )

        # When / Then
        with pytest.raises(service.SSOIdentityError):
            sso_service.handle_sso_login_with_data_check(
                idp_user=mock_idp_user, token_data=mock_token
            )

    @staticmethod
    def test_existing_user_case_fail_case_4_2(
        sso_service,
        mock_idp_management_client,
        mock_authn_service,
        mock_feature_flag_on,
        mock_user_external_identity_repository,
        mock_idp_repository,
        mock_user_service,
    ):
        # Given
        sso_service.management_client = mock_idp_management_client
        sso_service.identities = mock_user_external_identity_repository
        sso_service.idps = mock_idp_repository
        sso_service.users = mock_user_service

        idp_name = "test_idp"
        external_id = "samlp|abcd1234"
        mock_email = "mock@idp.com"
        mock_first_name = "fn"
        mock_last_name = "ln"
        mock_employee_id = "mock_ee_id"
        mock_idp_user = IDPUser(
            user_id="mock",
            identities=[IDPIdentity(provider="samlp", connection=idp_name)],
            external_user_id="abc",
            first_name=mock_first_name,
            last_name=mock_last_name,
            email=mock_email,
            employee_id=mock_employee_id,
        )
        test_idp = factories.IdentityProviderFactory(name=idp_name, id=1)
        mock_token = {"user_id": "123"}
        mock_identities = factories.UserExternalIdentityFactory.create(
            user_id=123,
            sso_email=mock_email,
            auth0_user_id=external_id,
            sso_user_first_name="wrong_name",
            sso_user_last_name=mock_last_name,
            unique_corp_id=mock_employee_id,
        )
        mock_idp_repository.return_value = test_idp
        mock_user_external_identity_repository.get_by_auth0_user_id.return_value = (
            mock_identities
        )
        mock_user_external_identity_repository.get_by_idp_and_external_user_id.return_value = (
            mock_identities
        )

        # When / Then
        with pytest.raises(service.SSOIdentityError):
            sso_service.handle_sso_login_with_data_check(
                idp_user=mock_idp_user, token_data=mock_token
            )

    @staticmethod
    def test_existing_user_case_fail_case_4_3(
        sso_service,
        mock_idp_management_client,
        mock_authn_service,
        mock_feature_flag_on,
        mock_user_external_identity_repository,
        mock_idp_repository,
        mock_user_service,
    ):
        # Given
        sso_service.management_client = mock_idp_management_client
        sso_service.identities = mock_user_external_identity_repository
        sso_service.idps = mock_idp_repository
        sso_service.users = mock_user_service

        idp_name = "test_idp"
        external_id = "samlp|abcd1234"
        mock_email = "mock@idp.com"
        mock_first_name = "fn"
        mock_last_name = "ln"
        mock_employee_id = "mock_ee_id"
        mock_idp_user = IDPUser(
            user_id="mock",
            identities=[IDPIdentity(provider="samlp", connection=idp_name)],
            external_user_id="abc",
            first_name=mock_first_name,
            last_name=mock_last_name,
            email=mock_email,
            employee_id=mock_employee_id,
        )
        test_idp = factories.IdentityProviderFactory(name=idp_name, id=1)
        mock_token = {"user_id": "123"}
        mock_identities = factories.UserExternalIdentityFactory.create(
            user_id=123,
            sso_email=mock_email,
            auth0_user_id=external_id,
            sso_user_first_name=mock_first_name,
            sso_user_last_name="wrong name",
            unique_corp_id=mock_employee_id,
        )
        mock_idp_repository.get_by_name.return_value = test_idp
        mock_user_external_identity_repository.get_by_auth0_user_id.return_value = (
            mock_identities
        )
        mock_user_external_identity_repository.get_by_idp_and_external_user_id.return_value = (
            mock_identities
        )

        # When / Then
        with pytest.raises(service.SSOIdentityError):
            sso_service.handle_sso_login_with_data_check(
                idp_user=mock_idp_user, token_data=mock_token
            )


class TestExecuteAssertionMatchingIdentity:
    @staticmethod
    def test_success(
        saml_assertion,
        sso_service,
    ):
        # Given
        request = factories.SAMLRequestBodyFactory.create()
        expected_idp, expected_assertion = saml_assertion
        given_identity = factories.UserExternalIdentityFactory.create(
            external_user_id=expected_assertion.subject,
            identity_provider_id=expected_idp.id,
            unique_corp_id=expected_assertion.employee_id,
        )
        (
            sso_service.identities.get_by_idp_and_external_user_id.return_value
        ) = given_identity
        expected_changes = dataclasses.replace(
            given_identity,
            external_organization_id=expected_assertion.organization_external_id,
            reporting_id=expected_assertion.rewards_id,
        )
        expected_call = mock.call(instance=expected_changes)
        # When
        sso_service.execute_assertion(request=request)
        # Then
        assert sso_service.identities.update.call_args == expected_call

    @staticmethod
    def test_conflict(
        saml_assertion,
        sso_service,
    ):
        # Given
        request = factories.SAMLRequestBodyFactory.create()
        expected_idp, expected_assertion = saml_assertion
        given_identity = factories.UserExternalIdentityFactory.create(
            external_user_id=expected_assertion.subject,
            identity_provider_id=expected_idp.id,
            unique_corp_id="Excelsior!",  # corp id doesn't match employee id!
        )
        (
            sso_service.identities.get_by_idp_and_external_user_id.return_value
        ) = given_identity
        # When/Then
        with pytest.raises(service.SSOIdentityError):
            sso_service.execute_assertion(request=request)


class TestExecuteAssertionNewIdentity:
    @staticmethod
    def test_conflicting_identity(
        saml_assertion,
        sso_service,
    ):
        # Given
        request = factories.SAMLRequestBodyFactory.create()
        idp, assertion = saml_assertion
        conflicting_identity = factories.UserExternalIdentityFactory.create(
            reporting_id=assertion.rewards_id,
        )
        sso_service.identities.get_by_reporting_id.return_value = conflicting_identity
        # When/Then
        with pytest.raises(service.SSOIdentityError):
            sso_service.execute_assertion(request=request)
