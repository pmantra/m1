import pytest

from authn.models.user import User
from models.tracks import TrackName
from storage.connection import db


@pytest.mark.parametrize(argnames="n", argvalues=range(10))
def test_default_user_factory(factories, n):
    user: User = factories.DefaultUserFactory.create()
    assert user.id
    assert User.query.count() == 1
    assert db.session.query(User).count() == 1


def test_enterprise_user_factory(factories):
    user: User = factories.EnterpriseUserFactory.create()
    assert user.id
    # TODO: [multitrack] assert user.active_tracks
    assert user.current_member_track
    assert user.current_member_track.current_phase


@pytest.mark.parametrize(argnames="week", argvalues=[4, 5, 38, 39])
def test_enterprise_user_factory_with_pregancy_phase(factories, week):
    track_name = "pregnancy"
    phase_name = f"week-{week}"
    user: User = factories.EnterpriseUserFactory.create(
        tracks__name=track_name, tracks__current_phase=phase_name
    )
    # TODO: [multitrack] assert using active_tracks[0]
    assert user.current_member_track.name == track_name
    assert user.current_member_track.current_phase.name == phase_name


@pytest.mark.parametrize(argnames="week", argvalues=[40, 62, 63])
def test_enterprise_user_factory_with_postpartum_phase(factories, week):
    track_name = "postpartum"
    phase_name = f"week-{week}"
    user: User = factories.EnterpriseUserFactory.create(
        tracks__name=track_name, tracks__current_phase=phase_name
    )
    # TODO: [multitrack] assert using active_tracks[0]
    assert user.current_member_track.name == track_name
    assert user.current_member_track.current_phase.name == phase_name


def test_organization_client_tracks(factories):
    # Given
    enabled = {TrackName.ADOPTION, TrackName.BREAST_MILK_SHIPPING}
    # When
    org = factories.OrganizationFactory.create(allowed_tracks=enabled)
    assert {ct.track for ct in org.client_tracks} == enabled
