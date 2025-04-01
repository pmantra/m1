from unittest import mock

import pytest


@pytest.fixture(scope="function")
def mock_user_service():
    with mock.patch(
        "authn.domain.service.user.UserService", autospec=True, spec_set=True
    ) as m:
        yield m.return_value


@pytest.fixture(scope="function")
def mock_authn_service():
    with mock.patch(
        "authn.domain.service.authn.AuthenticationService", autospec=True
    ) as m:
        yield m.return_value


@pytest.fixture(scope="function")
def mock_sso_service():
    with mock.patch("authn.domain.service.sso.SSOService", autospec=True) as m:
        yield m.return_value


@pytest.fixture(scope="function")
def mock_authnapi_client():
    with mock.patch(
        "common.authn_api.internal_client.AuthnApiInternalClient",
        autospec=True,
        spec_set=True,
    ) as m:
        yield m.return_value
