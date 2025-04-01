import datetime
from unittest import mock

import pytest

from eligibility.utils import sub_populations
from pytests import factories


@pytest.fixture
def mock_get_sub_population_id_for_user():
    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_sub_population_id_for_user_and_org"
    ) as mocked_get_sub_pop:
        mocked_get_sub_pop.return_value = 42
        yield mocked_get_sub_pop


@pytest.fixture
def mock_member_tracks():
    organization = factories.OrganizationFactory.create(
        id=1,
    )
    client_track = factories.ClientTrackFactory.create(
        organization=organization,
        organization_id=organization.id,
    )
    return factories.MemberTrackFactory.create_batch(
        size=10,
        client_track_id=client_track.id,
        client_track=client_track,
        sub_population_id=None,
        activated_at=datetime.datetime.now(tz=datetime.timezone.utc)
        - datetime.timedelta(days=7),
        ended_at=None,
    )


@pytest.fixture(autouse=True)
def backfill_test_setup(mock_get_sub_population_id_for_user, mock_member_tracks):
    for i in range(5):
        mock_member_tracks[i].sub_population_id = 38


def test_backfill_org_sub_populations():
    # Given test setup of 10 MemberTracks w/ 5 sub_population_id is None
    # When
    sub_pop_map_1 = sub_populations.backfill_org_sub_populations(
        organization_id=1,
    )
    sub_pop_map_2 = sub_populations.backfill_org_sub_populations(
        organization_id=1,
    )
    # Then
    # There were 5 MemberTracks w/ None sub_population_id values
    assert len(sub_pop_map_1) == 5
    # There were still 5 MemberTracks w/ None sub_population_id values
    assert len(sub_pop_map_2) == 5


def test_backfill_org_sub_populations_no_op_disabled():
    # Given test setup of 10 MemberTracks w/ 5 sub_population_id is None
    # When
    sub_pop_map_1 = sub_populations.backfill_org_sub_populations(
        organization_id=1,
        no_op=False,
    )
    sub_pop_map_2 = sub_populations.backfill_org_sub_populations(
        organization_id=1,
    )
    # Then
    # There were 5 MemberTracks w/ None sub_population_id values
    assert len(sub_pop_map_1) == 5
    # There were no MemberTracks w/ None sub_population_id values because they were overwritten
    assert len(sub_pop_map_2) == 0


def test_backfill_org_sub_populations_overwrite_all():
    # Given test setup of 10 MemberTracks w/ 5 sub_population_id is None
    # When
    sub_pop_map_1 = sub_populations.backfill_org_sub_populations(
        organization_id=1,
        overwrite_all=True,
    )
    sub_pop_map_2 = sub_populations.backfill_org_sub_populations(
        organization_id=1,
    )
    # Then
    # There were 10 MemberTracks regardless of sub_population_id values
    assert len(sub_pop_map_1) == 10
    # There were 5 MemberTracks w/ None sub_population_id values
    assert len(sub_pop_map_2) == 5


def test_backfill_org_sub_populations_overwrite_all_no_op_disabled():
    # Given test setup of 10 MemberTracks w/ 5 sub_population_id is None
    # When
    sub_pop_map_1 = sub_populations.backfill_org_sub_populations(
        organization_id=1,
        overwrite_all=True,
        no_op=False,
    )
    sub_pop_map_2 = sub_populations.backfill_org_sub_populations(
        organization_id=1,
    )
    # Then
    # There were 10 MemberTracks regardless of sub_population_id values
    assert len(sub_pop_map_1) == 10
    # There were no MemberTracks w/ None sub_population_id values because they were overwritten
    assert len(sub_pop_map_2) == 0


def test_backfill_org_sub_populations_user_id_zero_ignored(mock_member_tracks):
    # Given all 10 MemberTracks have a user ID of 0
    for track in mock_member_tracks:
        track.user_id = 0

    # When
    sub_pop_map_1 = sub_populations.backfill_org_sub_populations(
        organization_id=1,
    )
    # Then
    # The MemberTracks were ignored due to having a 0-value user ID
    assert len(sub_pop_map_1) == 0
