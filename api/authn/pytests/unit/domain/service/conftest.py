import os
from unittest import mock

import pytest


@pytest.fixture(scope="function")
def mock_e2e_env():
    values = {
        "AUTH_TEST_POOL_ENABLED": "True",
        "AUTH_TEST_POOL_EMAIL": "test\+mvnqa-.+@mavenclinic.com",
    }
    with mock.patch.dict(os.environ, values=values) as m:
        yield m


@pytest.fixture
def mock_user_activity_service():
    with mock.patch(
        "activity.service.UserActivityService", autospec=True, spec_set=True
    ) as m:
        yield m.return_value


@pytest.fixture(scope="function")
def mock_authn_service():
    with mock.patch("authn.domain.service.authn", autospec=True) as m:
        yield m.AuthenticationService(is_in_uow=True)


@pytest.fixture(scope="function")
def mock_sso_service():
    with mock.patch("authn.domain.service.sso", autospec=True) as m:
        yield m.SSOService(is_in_uow=True)


@pytest.fixture(scope="module")
def mock_management_client():
    with mock.patch("authn.services.integrations.idp.ManagementClient") as mock_client:
        yield mock_client()


@pytest.fixture(scope="function")
def mock_feature_flag_on():
    with mock.patch("maven.feature_flags.bool_variation", return_value=True) as ff:
        yield ff


@pytest.fixture(scope="function")
def mock_feature_flag_off():
    with mock.patch("maven.feature_flags.bool_variation", return_value=False) as ff:
        yield ff
