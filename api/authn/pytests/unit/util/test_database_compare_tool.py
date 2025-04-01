from authn.pytests import factories
from authn.util.database_compare_tool import AuthnDataComparer
from common.authn_api.models import (
    GetIdentityProviderAllResponse,
    GetOrgAuthAllResponse,
    GetUserAllResponse,
    GetUserAuthAllResponse,
    GetUserExternalIdentityAllResponse,
)


def test_check_user_data(
    mock_sso_service, mock_user_service, mock_authn_service, mock_authnapi_client
):
    # Given
    comparer = AuthnDataComparer(
        sso_service=mock_sso_service,
        authn_service=mock_authn_service,
        user_service=mock_user_service,
        authnapi_client=mock_authnapi_client,
    )
    comparer.user_service.get_all_by_time_range.return_value = []
    comparer.authnapi_client.get_user_by_time_range.return_value = GetUserAllResponse(
        users=[]
    )
    # When
    result = comparer.check_user()
    # Then
    assert result


def test_check_user_data_with_diff(
    mock_sso_service, mock_user_service, mock_authn_service, mock_authnapi_client
):
    # Given
    user = factories.UserFactory.create()
    comparer = AuthnDataComparer(
        sso_service=mock_sso_service,
        authn_service=mock_authn_service,
        user_service=mock_user_service,
        authnapi_client=mock_authnapi_client,
    )
    comparer.user_service.get_all_by_time_range.return_value = [user]
    comparer.authnapi_client.get_user_by_time_range.return_value = GetUserAllResponse(
        users=[]
    )
    # When
    result = comparer.check_user()
    # Then
    assert not result


def test_check_user_auth_data(
    mock_sso_service, mock_user_service, mock_authn_service, mock_authnapi_client
):
    # Given
    comparer = AuthnDataComparer(
        sso_service=mock_sso_service,
        authn_service=mock_authn_service,
        user_service=mock_user_service,
        authnapi_client=mock_authnapi_client,
    )
    comparer.authn_service.get_user_auth_by_time_range.return_value = []
    comparer.authnapi_client.get_user_auth_by_time_range.return_value = (
        GetUserAuthAllResponse(user_auths=[])
    )
    # When
    result = comparer.check_user()
    # Then
    assert result


def test_check_user_auth_data_with_diff(
    mock_sso_service, mock_user_service, mock_authn_service, mock_authnapi_client
):
    # Given
    user_auth = factories.UserAuthFactory.create()
    comparer = AuthnDataComparer(
        sso_service=mock_sso_service,
        authn_service=mock_authn_service,
        user_service=mock_user_service,
        authnapi_client=mock_authnapi_client,
    )
    comparer.authn_service.get_user_auth_by_time_range.return_value = [user_auth]
    comparer.authnapi_client.get_user_auth_by_time_range.return_value = (
        GetUserAuthAllResponse(user_auths=[])
    )
    # When
    result = comparer.check_user_auth()
    # Then
    assert not result


def test_check_org_auth_data(
    mock_sso_service, mock_user_service, mock_authn_service, mock_authnapi_client
):
    # Given
    comparer = AuthnDataComparer(
        sso_service=mock_sso_service,
        authn_service=mock_authn_service,
        user_service=mock_user_service,
        authnapi_client=mock_authnapi_client,
    )
    comparer.authn_service.get_org_auth_by_time_range.return_value = []
    comparer.authnapi_client.get_org_auth_by_time_range.return_value = (
        GetOrgAuthAllResponse(org_auths=[])
    )
    # When
    result = comparer.check_org_auth()
    # Then
    assert result


def test_check_org_auth_data_with_diff(
    mock_sso_service, mock_user_service, mock_authn_service, mock_authnapi_client
):
    # Given
    org_auth = factories.OrganizationAuthFactory.create()
    comparer = AuthnDataComparer(
        sso_service=mock_sso_service,
        authn_service=mock_authn_service,
        user_service=mock_user_service,
        authnapi_client=mock_authnapi_client,
    )
    comparer.authn_service.get_org_auth_by_time_range.return_value = [org_auth]
    comparer.authnapi_client.get_org_auth_by_time_range.return_value = (
        GetOrgAuthAllResponse(org_auths=[])
    )
    # When
    result = comparer.check_org_auth()
    # Then
    assert not result


def test_check_identity_provider_data(
    mock_sso_service, mock_user_service, mock_authn_service, mock_authnapi_client
):
    # Given
    comparer = AuthnDataComparer(
        sso_service=mock_sso_service,
        authn_service=mock_authn_service,
        user_service=mock_user_service,
        authnapi_client=mock_authnapi_client,
    )
    comparer.sso_service.get_idps_by_time_range.return_value = []
    comparer.authnapi_client.get_identity_provider_by_time_range.return_value = (
        GetIdentityProviderAllResponse(identity_providers=[])
    )
    # When
    result = comparer.check_identity_provider()
    # Then
    assert result


def test_check_identity_provider_data_with_diff(
    mock_sso_service, mock_user_service, mock_authn_service, mock_authnapi_client
):
    # Given
    idp = factories.IdentityProviderFactory.create()
    comparer = AuthnDataComparer(
        sso_service=mock_sso_service,
        authn_service=mock_authn_service,
        user_service=mock_user_service,
        authnapi_client=mock_authnapi_client,
    )
    comparer.sso_service.get_idps_by_time_range.return_value = [idp]
    comparer.authnapi_client.get_identity_provider_by_time_range.return_value = (
        GetIdentityProviderAllResponse(identity_providers=[])
    )
    # When
    result = comparer.check_identity_provider()
    # Then
    assert not result


def test_check_user_external_identity_data(
    mock_sso_service, mock_user_service, mock_authn_service, mock_authnapi_client
):
    # Given
    comparer = AuthnDataComparer(
        sso_service=mock_sso_service,
        authn_service=mock_authn_service,
        user_service=mock_user_service,
        authnapi_client=mock_authnapi_client,
    )
    comparer.sso_service.get_identities_by_time_range.return_value = []
    comparer.authnapi_client.get_user_external_identity_by_time_range.return_value = (
        GetUserExternalIdentityAllResponse(user_external_identities=[])
    )
    # When
    result = comparer.check_user_external_identity()
    # Then
    assert result


def test_check_user_external_identity_data_with_diff(
    mock_sso_service, mock_user_service, mock_authn_service, mock_authnapi_client
):
    # Given
    identity = factories.UserExternalIdentityFactory.create()
    comparer = AuthnDataComparer(
        sso_service=mock_sso_service,
        authn_service=mock_authn_service,
        user_service=mock_user_service,
        authnapi_client=mock_authnapi_client,
    )
    comparer.sso_service.get_identities_by_time_range.return_value = [identity]
    comparer.authnapi_client.get_user_external_identity_by_time_range.return_value = (
        GetUserExternalIdentityAllResponse(user_external_identities=[])
    )
    # When
    result = comparer.check_user_external_identity()
    # Then
    assert not result
