import pytest

from authn.services.integrations import idp


@pytest.fixture
def management_client():
    yield idp.ManagementClient()
