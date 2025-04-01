import datetime
from unittest import mock
from unittest.mock import patch

import pytest

from eligibility.pytests import factories as e9y_factories
from eligibility.pytests.factories import VerificationFactory
from models import tracks
from models.tracks import TrackName
from pytests.freezegun import freeze_time
from storage.connection import db

ALLOWED_TRACKS = [
    TrackName.PREGNANCY,
    TrackName.POSTPARTUM,
    TrackName.PARENTING_AND_PEDIATRICS,
]


def test_multitrack_onboarding(factories, db, track_service):
    user = factories.DefaultUserFactory.create()
    org = factories.OrganizationFactory.create(allowed_tracks=ALLOWED_TRACKS)

    client_track_1 = factories.ClientTrackFactory.create(
        organization=org, track=TrackName.PREGNANCY
    )
    verification = e9y_factories.VerificationFactory.create(
        user_id=user.id, organization_id=org.id, active_effective_range=True
    )
    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ), mock.patch(
        "eligibility.service.EnterpriseVerificationService.is_verification_active",
        return_value=True,
    ), mock.patch(
        "tracks.service.tracks.TrackSelectionService.validate_initiation",
        return_value=client_track_1,
    ):
        first_track = tracks.initiate(
            user=user, track=TrackName.PREGNANCY, eligibility_organization_id=org.id
        )
        db.session.expire(user)
        available_tracks = track_service.get_enrollable_tracks_for_org(
            user_id=user.id, organization_id=org.id
        )
        assert set(user.active_tracks) == {first_track}
        assert TrackName.PARENTING_AND_PEDIATRICS in [
            config.name for config in available_tracks
        ]

        client_track_2 = factories.ClientTrackFactory.create(
            organization=org, track=TrackName.PARENTING_AND_PEDIATRICS
        )
        with mock.patch(
            "tracks.service.tracks.TrackSelectionService.validate_initiation",
            return_value=client_track_2,
        ):
            second_track = tracks.initiate(
                user=user,
                track=TrackName.PARENTING_AND_PEDIATRICS,
                eligibility_organization_id=org.id,
            )
            db.session.expire(user)
            re_available_tracks = track_service.get_enrollable_tracks_for_org(
                user_id=user.id, organization_id=org.id
            )
            assert set(user.active_tracks) == {first_track, second_track}
            assert len(re_available_tracks) == 0


@pytest.mark.parametrize(
    argnames="track_names",
    argvalues=[
        [TrackName.PREGNANCY, TrackName.PARENTING_AND_PEDIATRICS],
        [TrackName.PARENTING_AND_PEDIATRICS, TrackName.PREGNANCY],
    ],
)
def test_multitrack_transitions(factories, db, track_names):
    """
    Test pregnancy->postpartum transitions for users in multitrack, regardless of which
    track was started first.
    """
    user = factories.DefaultUserFactory.create()
    org = factories.OrganizationFactory.create(allowed_tracks=ALLOWED_TRACKS)

    for track_name in track_names:
        client_track_1 = factories.ClientTrackFactory.create(
            organization=org, track=track_name
        )
        with mock.patch(
            "tracks.service.tracks.TrackSelectionService.validate_initiation",
            return_value=client_track_1,
        ):
            tracks.initiate(
                user=user,
                track=track_name,
                eligibility_organization_id=org.id,
            )
            db.session.expire(user)
    pregnancy_track = next(
        t for t in user.active_tracks if t.name == TrackName.PREGNANCY
    )
    user.health_profile.add_a_child(datetime.date.today())
    db.session.expire(user)
    tracks.initiate_transition(pregnancy_track, TrackName.POSTPARTUM)
    db.session.expire(user)
    tracks.finish_transition(pregnancy_track)
    db.session.expire(user)
    assert {t.name for t in user.active_tracks} == {
        TrackName.POSTPARTUM,
        TrackName.PARENTING_AND_PEDIATRICS,
    }


def test_multitrack_onboarding_fails_when_pnp_not_one_of_the_tracks(factories, db):
    user = factories.DefaultUserFactory.create()
    org = factories.OrganizationFactory.create()
    for track in ALLOWED_TRACKS:
        factories.ClientTrackFactory.create(organization=org, track=track)

    verification = e9y_factories.VerificationFactory.create(
        user_id=user.id, organization_id=org.id, active_effective_range=True
    )

    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user",
        return_value=verification,
    ), mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ):
        tracks.initiate(
            user=user,
            track=TrackName.PREGNANCY,
            eligibility_organization_id=org.id,
        )
        db.session.expire(user)
        db.session.flush()

    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user",
        return_value=verification,
    ), mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ), pytest.raises(
        tracks.IncompatibleTrackError
    ):
        tracks.initiate(
            user=user,
            track=TrackName.POSTPARTUM,
            eligibility_organization_id=org.id,
        )


@freeze_time("2021-02-05T10:16:00")
def test_multitrack_termination_deletes_credits_only_when_no_tracks_left(factories):
    first_track = factories.MemberTrackFactory.create()
    second_track = factories.MemberTrackFactory.create(
        user=first_track.user,
        name=next(t for t in [*TrackName] if t.value != first_track.name),
    )
    future_date = datetime.datetime.now() + datetime.timedelta(days=100)
    enterprise_credit = factories.CreditFactory.create(
        user_id=first_track.user.id,
        expires_at=future_date,
        eligibility_verification_id=1,
    )
    marketplace_credit = factories.CreditFactory.create(
        user_id=first_track.user.id,
    )

    tracks.terminate(track=first_track, expire_credits=True)
    db.session.flush()
    assert enterprise_credit.expires_at == future_date
    assert marketplace_credit.expires_at is None

    tracks.terminate(track=second_track)
    db.session.flush()
    assert enterprise_credit.expires_at.isoformat() == "2021-02-05T10:16:00"
    assert marketplace_credit.expires_at is None


def test_multitrack_with_exclusively_claimed_employee(factories, db):
    first_track = factories.MemberTrackFactory.create(
        name=TrackName.PARENTING_AND_PEDIATRICS,
    )
    first_track.organization.employee_only = True
    db.session.flush()

    client_track_1 = factories.ClientTrackFactory.create(
        organization=first_track.client_track.organization, track=TrackName.PREGNANCY
    )
    verification = VerificationFactory.create(
        user_id=first_track.user.id,
        organization_id=first_track.organization.id,
        active_effective_range=True,
    )

    with mock.patch(
        "tracks.service.tracks.TrackSelectionService.validate_initiation",
        return_value=client_track_1,
    ), patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ), patch(
        "eligibility.service.EnterpriseVerificationService.is_verification_active",
        return_value=True,
    ):
        second_track = tracks.initiate(
            user=first_track.user,
            track=TrackName.PREGNANCY,
            eligibility_organization_id=first_track.organization.id,
        )
        assert second_track
