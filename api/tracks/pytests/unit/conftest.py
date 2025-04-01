from typing import List
from unittest import mock

import pytest

from models.enterprise import Organization
from models.tracks import ClientTrack, TrackConfig, TrackName
from pytests import factories


@pytest.fixture()
def all_client_tracks() -> List[ClientTrack]:
    org: Organization = factories.OrganizationFactory()
    return [
        factories.ClientTrackFactory.create(track=t, organization=org)
        for t in TrackName
    ]


@pytest.fixture()
def all_track_configs() -> List[TrackConfig]:
    return [TrackConfig.from_name(t) for t in TrackName]


@pytest.fixture
def mock_is_user_known_to_be_eligible_for_org():
    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.is_user_known_to_be_eligible_for_org",
        autospec=True,
    ) as m:
        m.return_value = True
        yield m
