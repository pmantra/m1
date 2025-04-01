from unittest import mock

import pytest


@pytest.fixture(scope="module", autouse=True)
def mock_twilio():
    with mock.patch("authn.services.integrations.twilio", autospec=True) as mock_twilio:
        yield mock_twilio


@pytest.fixture(scope="package", autouse=True)
def mock_jwt():
    with mock.patch("authn.services.integrations.mfa.jwt") as mjwt:
        mjwt.encode.return_value = b"It's pronounced J-WOT."
        mjwt.decode.return_value = {"exp": 123456}
        yield mjwt
        mjwt.reset_mock()


@pytest.fixture(scope="function", autouse=True)
def mock_authn_service():
    with mock.patch("authn.domain.service.authn", autospec=True) as m:
        with mock.patch("authn.resources.user.authn", new=m):
            with mock.patch("authn.resources.auth.authn", new=m):
                svc = m.AuthenticationService(is_in_uow=True)
                svc.update_password.return_value = "mock_password"
                yield svc


@pytest.fixture(scope="function")
def mock_mfa_service():
    with mock.patch("authn.domain.service.MFAService", autospec=True) as m:
        with mock.patch(
            "authn.resources.auth.mfa.MFAService", autospec=True, return_value=m
        ):
            yield m


@pytest.fixture(scope="function", autouse=True)
def mock_sso_service():
    with mock.patch("authn.domain.service.SSOService") as m:
        with mock.patch(
            "authn.resources.sso.service.SSOService", autospec=True, return_value=m
        ):
            yield m


@pytest.fixture(scope="function")
def mock_user_service():
    with mock.patch("authn.domain.service.user") as m:
        with mock.patch(
            "authn.resources.auth.user.UserService", autospec=True, return_value=m
        ):
            yield m


@pytest.fixture(scope="function")
def mock_token_validator():
    with mock.patch("authn.resources.auth.TokenValidator") as m:
        yield m()


@pytest.fixture(scope="function")
def mock_user_resource():
    with mock.patch("authn.resources.user.UsersResource") as m:
        yield m


@pytest.fixture(scope="function")
def mock_feature_flag_on():
    with mock.patch("maven.feature_flags.bool_variation", return_value=True) as ff:
        yield ff


@pytest.fixture(scope="function")
def mock_feature_flag_off():
    with mock.patch("maven.feature_flags.bool_variation", return_value=False) as ff:
        yield ff
