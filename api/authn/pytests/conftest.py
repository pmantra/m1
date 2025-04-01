from unittest import mock

import pytest

from authn.services.integrations import saml


@pytest.fixture(scope="module", autouse=True)
def auto_patch_jwt(patch_user_id_encoded_token):
    return patch_user_id_encoded_token


@pytest.fixture(scope="function")
def mock_org_identity_search():
    with mock.patch("eligibility.e9y.org_identity_search", autospec=True) as m:
        yield m


@pytest.fixture(scope="package")
def MockOneLoginAuth():
    with mock.patch(
        "onelogin.saml2.auth.OneLogin_Saml2_Auth",
        autospec=True,
    ) as m:
        yield m


@pytest.fixture(scope="package")
def MockOneLoginMetadataParser():
    with mock.patch(
        "onelogin.saml2.idp_metadata_parser.OneLogin_Saml2_IdPMetadataParser",
        autospec=True,
    ) as m:
        m.return_value.parse.return_value = {}
        yield m


@pytest.fixture
def mock_auth_object(MockOneLoginAuth):
    yield MockOneLoginAuth.return_value
    MockOneLoginAuth.reset_mock()


@pytest.fixture
def onelogin(
    app_context, MockOneLoginAuth, MockOneLoginMetadataParser
) -> saml.OneLoginSAMLVerificationService:
    saml_service = saml.OneLoginSAMLVerificationService()
    saml_service.idp_settings = {}
    return saml_service


@pytest.fixture(scope="package")
def MockOneLoginService():
    mock_onelogin = mock.MagicMock(
        spec=saml.OneLoginSAMLVerificationService, spec_set=True
    )
    return mock_onelogin


@pytest.fixture
def mock_onelogin_service(MockOneLoginService):
    yield MockOneLoginService.return_value
    MockOneLoginService.reset_mock()


@pytest.fixture
def mock_idp_auth_client():
    with mock.patch("authn.services.integrations.idp.AuthenticationClient") as m:
        yield m


@pytest.fixture(scope="function")
def mock_idp_management_client():
    with mock.patch("authn.services.integrations.idp.ManagementClient") as mock_client:
        yield mock_client()


@pytest.fixture(scope="package", autouse=True)
def mock_auth0_management():
    with mock.patch("auth0.management", autospec=True) as m:
        with mock.patch(
            "authn.services.integrations.idp.management_client.management", new=m
        ):
            m.Auth0.return_value = mock.MagicMock()
            yield m.Auth0("domain", "token")


@pytest.fixture(scope="package", autouse=True)
def mock_auth0_authentication():
    with mock.patch("auth0.authentication", autospec=True) as m:
        with mock.patch(
            "authn.services.integrations.idp.token_client.authentication", new=m
        ):
            yield m
