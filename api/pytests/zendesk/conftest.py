from unittest.mock import MagicMock

import pytest
from zenpy import Zenpy

from messaging.services.zendesk import creds
from messaging.services.zendesk_client import ZendeskClient


@pytest.fixture()
def zendesk_client():
    class ZDTestableClient(ZendeskClient):
        def __init__(self):
            self.zenpy = MagicMock(spec_set=Zenpy(**creds))

    return ZDTestableClient()
