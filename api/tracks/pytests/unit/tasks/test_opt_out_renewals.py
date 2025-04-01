from datetime import datetime, timedelta
from unittest import mock

import pytest

from eligibility.pytests import factories as e9y_factories
from models.tracks import MemberTrack, TrackLifecycleError, TrackName
from storage.connection import db
from tracks.tasks.opt_out_renewals import find_tracks_qualified_for_opt_out_renewals


@pytest.fixture
def mock_get_last_login_date():
    with mock.patch(
        "activity.service.UserActivityService.get_last_login_date",
        autospec=True,
    ) as m:
        m.return_value = datetime.utcnow().date() - timedelta(days=15)
        yield m


def test_find_tracks_qualified_for_opt_out_renewals__track_not_renewable(factories):
    track: MemberTrack = factories.MemberTrackFactory.create(
        name=TrackName.PREGNANCY,
    )

    with mock.patch.object(MemberTrack, "get_scheduled_end_date") as mock_gsed:
        find_tracks_qualified_for_opt_out_renewals()

        mock_gsed.assert_not_called()
        assert track.qualified_for_optout is None


def test_find_tracks_qualified_for_opt_out_renewals__track_already_renewed(factories):
    ending_track = factories.MemberTrackFactory.create(
        name=TrackName.SURROGACY,
        anchor_date=datetime.utcnow().date() - timedelta(days=400),
    )
    user = ending_track.user

    scheduled_track = factories.MemberTrackFactory.create(
        user=user,
        name=TrackName.SURROGACY,
        start_date=datetime.utcnow().date(),
        previous_member_track_id=ending_track.id,
    )
    scheduled_track.activated_at = None
    db.session.refresh(user)

    assert len(user.active_tracks) == 1
    assert ending_track in user.active_tracks

    assert not user.inactive_tracks

    assert len(user.scheduled_tracks) == 1
    assert scheduled_track in user.scheduled_tracks

    find_tracks_qualified_for_opt_out_renewals()

    assert len(user.active_tracks) == 1
    assert ending_track in user.active_tracks
    assert ending_track.qualified_for_optout is None

    assert not user.inactive_tracks

    assert len(user.scheduled_tracks) == 1
    assert scheduled_track in user.scheduled_tracks


def test_find_tracks_qualified_for_opt_out_renewals__user_not_known_to_be_eligible(
    factories, mock_is_user_known_to_be_eligible_for_org
):
    track: MemberTrack = factories.MemberTrackFactory.create(name=TrackName.ADOPTION)
    track.start_date = (
        datetime.utcnow().date()
        - track.length()
        - track.grace_period()
        + timedelta(days=30)
    )
    track.set_anchor_date()

    user = track.user

    with mock.patch("tracks.tasks.opt_out_renewals.renew") as mock_renew:
        mock_is_user_known_to_be_eligible_for_org.return_value = False

        find_tracks_qualified_for_opt_out_renewals()

        db.session.expire_all()

        mock_renew.assert_not_called()
        assert track.qualified_for_optout is False
        assert len(user.scheduled_tracks) == 0


def test_find_tracks_qualified_for_opt_out_renewals__user_with_no_last_login(
    factories,
    mock_is_user_known_to_be_eligible_for_org,
    mock_get_last_login_date,
):
    track: MemberTrack = factories.MemberTrackFactory.create(name=TrackName.ADOPTION)
    track.start_date = (
        datetime.utcnow().date()
        - track.length()
        - track.grace_period()
        + timedelta(days=30)
    )
    track.set_anchor_date()

    user = track.user

    with mock.patch("tracks.tasks.opt_out_renewals.renew") as mock_renew:
        mock_get_last_login_date.return_value = None

        find_tracks_qualified_for_opt_out_renewals()

        db.session.expire_all()

        mock_renew.assert_not_called()
        assert track.qualified_for_optout is False
        assert len(user.scheduled_tracks) == 0


def test_find_tracks_qualified_for_opt_out_renewals__user_with_no_qualified_login(
    factories,
    mock_is_user_known_to_be_eligible_for_org,
    mock_get_last_login_date,
):
    track: MemberTrack = factories.MemberTrackFactory.create(name=TrackName.ADOPTION)
    track.start_date = (
        datetime.utcnow().date()
        - track.length()
        - track.grace_period()
        + timedelta(days=30)
    )
    track.set_anchor_date()

    user = track.user

    with mock.patch("tracks.tasks.opt_out_renewals.renew") as mock_renew:
        mock_get_last_login_date.return_value = datetime.utcnow().date() - timedelta(
            days=45
        )

        find_tracks_qualified_for_opt_out_renewals()

        db.session.expire_all()

        mock_renew.assert_not_called()
        assert track.qualified_for_optout is False
        assert len(user.scheduled_tracks) == 0


def test_find_tracks_qualified_for_opt_out_renewals__exception_during_renewal(
    factories,
    mock_is_user_known_to_be_eligible_for_org,
    mock_get_last_login_date,
):
    track: MemberTrack = factories.MemberTrackFactory.create(name=TrackName.ADOPTION)
    track.start_date = (
        datetime.utcnow().date()
        - track.length()
        - track.grace_period()
        + timedelta(days=30)
    )
    track.set_anchor_date()

    user = track.user

    with mock.patch("tracks.tasks.opt_out_renewals.renew") as mock_renew:
        mock_renew.side_effect = TrackLifecycleError()
        mock_is_user_known_to_be_eligible_for_org.return_value = True

        find_tracks_qualified_for_opt_out_renewals()

        db.session.expire_all()

        mock_renew.assert_called_once()

        assert track.qualified_for_optout is False
        assert len(user.scheduled_tracks) == 0


@pytest.fixture
def mock_get_verification_for_user():
    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user",
        autospec=True,
    ) as m:
        verification = e9y_factories.VerificationFactory.create()
        verification.effective_range.upper = datetime.utcnow().date() + timedelta(
            days=365
        )
        m.return_value = verification
        yield m


@pytest.fixture
def mock_get_sub_population_id_for_user_and_org():
    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_sub_population_id_for_user_and_org",
        autospec=True,
    ) as m:
        m.return_value = True
        yield m


def test_find_tracks_qualified_for_opt_out_renewals__success(
    factories,
    mock_is_user_known_to_be_eligible_for_org,
    mock_get_last_login_date,
    mock_get_verification_for_user,
    mock_get_sub_population_id_for_user_and_org,
):
    track: MemberTrack = factories.MemberTrackFactory.create(name=TrackName.ADOPTION)
    track.start_date = (
        datetime.utcnow().date()
        - track.length()
        - track.grace_period()
        + timedelta(days=30)
    )
    track.set_anchor_date()

    user = track.user

    with mock.patch(
        "tracks.repository.MemberTrackRepository.get",
    ) as mock_member_tracks_get:
        mock_member_tracks_get.return_value = track

        find_tracks_qualified_for_opt_out_renewals()

        db.session.expire_all()

        mock_is_user_known_to_be_eligible_for_org.assert_called_once()
        assert track.qualified_for_optout is True
        assert len(user.scheduled_tracks) == 1
