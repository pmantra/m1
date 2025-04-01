from __future__ import annotations

import os
from unittest import mock

import pytest

from models.enterprise import ExternalIDPNames


@pytest.fixture
def patch_idp_environ(faker) -> tuple[str, str]:
    name, metadata = ExternalIDPNames.OKTA.name, faker.bs()
    with mock.patch.dict(os.environ, values={f"SAML_METADATA_{name}": metadata}):
        yield name, metadata
