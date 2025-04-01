from datetime import date, datetime, timedelta
from unittest import mock
from unittest.mock import patch

import pytest
from google.protobuf.wrappers_pb2 import Int64Value
from maven.feature_flags import TestData
from sqlalchemy import event

from appointments.models.appointment import Appointment
from appointments.models.constants import APPOINTMENT_STATES
from appointments.models.payments import Credit
from authn.util.constants import COMPANY_MFA_SYNC_LAUNCH_DARKLY_KEY
from eligibility.e9y import EligibilityVerification
from eligibility.e9y import model as e9y_model
from eligibility.pytests import factories as e9y_factories
from models import tracks
from models.tracks import PregnancyMemberTrack, TrackName, lifecycle
from models.tracks.client_track import ClientTrack, TrackModifiers
from models.tracks.lifecycle import (
    MismatchedOrganizationError,
    MissingClientTrackError,
    MissingVerificationError,
    prepare_user_for_auto_transition,
)
from models.tracks.member_track import ChangeReason, MemberTrackPhaseReporting
from models.verticals_and_specialties import VerticalAccessByTrack
from storage.connection import db
from tracks import service as track_service


class TestDBException(Exception):
    pass


# TODO: [multitrack] This file makes extensive use of current_member_track for
#  assertions, use active_tracks instead


@patch("eligibility.EnterpriseVerificationService.get_verification_for_user_and_org")
def test_initiate__inactive_e9y_verification(
    patch_get_verification_for_user_and_org,
    mock_org_with_track,
    default_user,
    factories,
):
    verification = e9y_factories.VerificationFactory.create(
        user_id=default_user.id,
        organization_id=mock_org_with_track.id,
        active_effective_range=True,
    )
    verification.effective_range.upper = datetime.utcnow().date() - timedelta(days=30)
    patch_get_verification_for_user_and_org.return_value = verification

    with pytest.raises(lifecycle.IncompatibleTrackError):
        lifecycle.initiate(
            user=default_user,
            track=TrackName.ADOPTION,
            eligibility_organization_id=verification.organization_id,
        )


def test_initiate__active_e9y_verification(
    default_user, factories, mock_org_with_track
):
    # Given
    verification = e9y_factories.VerificationFactory.create(
        user_id=default_user.id,
        organization_id=mock_org_with_track.id,
        active_effective_range=True,
    )

    with mock.patch(
        "eligibility.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ):
        lifecycle.initiate(
            user=default_user,
            track=TrackName.ADOPTION,
            eligibility_organization_id=verification.organization_id,
        )
    # Then
    current_track = default_user.current_member_track
    # TODO: [multitrack] use default_user.active_tracks
    assert current_track.name == TrackName.ADOPTION
    assert (
        db.session.query(MemberTrackPhaseReporting)
        .filter_by(member_track_id=current_track.id)
        .one()
    )
    assert current_track.activated_at == current_track.created_at
    assert current_track.sub_population_id is None


def test_initiate(default_user, mock_org_with_track, factories, ff_test_data):
    member_1_id = 1
    member_2_id = 1001
    member_2_version = 1000
    verification_2_id = 10011
    # Given
    verification = e9y_factories.VerificationFactory.create(
        user_id=default_user.id,
        organization_id=mock_org_with_track.id,
        eligibility_member_id=member_1_id,
        active_effective_range=True,
    )
    verification.verification_1_id = verification.verification_id
    verification.verification_2_id = verification_2_id
    verification.eligibility_member_2_id = member_2_id
    verification.eligibility_member_2_version = member_2_version

    ff_test_data.update(
        ff_test_data.flag(COMPANY_MFA_SYNC_LAUNCH_DARKLY_KEY).variation_for_all(True)
    )

    with mock.patch(
        "eligibility.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ), mock.patch(
        "tasks.enterprise.update_single_user_company_mfa.delay", return_value=None
    ) as mock_update_user_company_mfa_call:
        # When
        lifecycle.initiate(
            user=default_user,
            track=TrackName.ADOPTION,
            eligibility_organization_id=verification.organization_id,
        )
        # Then
        current_track = default_user.current_member_track
        # TODO: [multitrack] use default_user.active_tracks
        assert current_track.name == TrackName.ADOPTION
        assert current_track.organization.id == verification.organization_id
        assert (
            db.session.query(MemberTrackPhaseReporting)
            .filter_by(member_track_id=current_track.id)
            .one()
        )
        assert current_track.activated_at == current_track.created_at
        assert current_track.sub_population_id is None

        force_ca_replacement = len(default_user.member_tracks) > 1
        assert (
            not force_ca_replacement
        ), "CA reassignment should not be enforced with only one track."
        assert mock_update_user_company_mfa_call.call_count == 1

        credit_obj = (
            db.session.query(Credit)
            .filter_by(
                user_id=default_user.id,
                eligibility_verification_id=verification.verification_id,
            )
            .first()
        )
        assert credit_obj.eligibility_member_id == member_1_id
        assert credit_obj.eligibility_member_2_id == member_2_id
        assert credit_obj.eligibility_member_2_version == member_2_version
        assert credit_obj.eligibility_verification_id == verification.verification_id
        assert credit_obj.eligibility_verification_2_id == verification_2_id


def test_initiate_with_sub_population(
    default_user, factories, verification_service, mock_org_with_track
):
    # Given
    client_track = factories.ClientTrackFactory.create(
        organization=mock_org_with_track, track=TrackName.ADOPTION
    )

    verification_service.e9y.grpc.get_sub_population_id_for_user_and_org.return_value = Int64Value(
        value=7357
    )
    verification_service.e9y.grpc.get_eligible_features_for_user_and_org.return_value = e9y_model.EligibleFeaturesForUserResponse(
        features=[client_track.id],
        has_population=True,
    )

    verification = e9y_factories.VerificationFactory.create(
        user_id=default_user.id,
        organization_id=mock_org_with_track.id,
        active_effective_range=True,
    )
    # When
    with mock.patch(
        "eligibility.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ):
        lifecycle.initiate(
            user=default_user,
            track=TrackName.ADOPTION,
            eligibility_organization_id=mock_org_with_track.id,
        )

    # Then
    current_track = default_user.current_member_track
    # TODO: [multitrack] use default_user.active_tracks
    assert current_track.name == TrackName.ADOPTION
    assert (
        db.session.query(MemberTrackPhaseReporting)
        .filter_by(member_track_id=current_track.id)
        .one()
    )
    assert current_track.activated_at == current_track.created_at
    assert current_track.sub_population_id == 7357


def test_initiate_assigns_care_team(default_user, factories):
    org = factories.OrganizationFactory.create()
    client_track = factories.ClientTrackFactory.create(
        organization=org, track=TrackName.PARENTING_AND_PEDIATRICS
    )

    with mock.patch(
        "tracks.service.tracks.TrackSelectionService.validate_initiation",
        return_value=client_track,
    ), mock.patch(
        "provider_matching.services.care_team_assignment.replace_care_team_members_during_transition"
    ) as assign_method:
        tracks.initiate(
            user=default_user,
            track=client_track.track,
            eligibility_organization_id=org.id,
        )
        assert assign_method.called_with(default_user)


def test_initiate_sends_track_length_braze_event(default_user, factories):
    org = factories.OrganizationFactory.create(allowed_tracks=[TrackName.POSTPARTUM])
    client_track = org.client_tracks[0]

    with mock.patch(
        "tracks.service.tracks.TrackSelectionService.validate_initiation",
        return_value=client_track,
    ), mock.patch("utils.braze_events.braze.send_event") as send_event_mock:
        tracks.initiate(
            user=default_user,
            track=client_track.track,
            eligibility_organization_id=org.id,
        )
        assert send_event_mock.called_with(
            user=default_user,
            event_name="track_length_in_days",
            user_attributes={"track_length_in_days": client_track.length_in_days},
        )


class TestValidateInitiation:
    track_svc: track_service.TrackSelectionService = (
        track_service.TrackSelectionService()
    )
    user_id = 1
    organization_id = 11
    verification = e9y_factories.VerificationFactory.create(
        user_id=user_id, organization_id=organization_id, active_effective_range=True
    )

    def test_when_missing_organization_id(self):
        with pytest.raises(lifecycle.MissingEmployeeError):
            # When
            self.track_svc.validate_initiation(
                track=TrackName.ADOPTION,
                user_id=self.user_id,
                organization_id=None,
            )

    def test_when_no_verification(self):
        with mock.patch(
            "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
            return_value=None,
        ), pytest.raises(lifecycle.MissingEmployeeError):
            # When
            self.track_svc.validate_initiation(
                track=TrackName.ADOPTION,
                user_id=self.user_id,
                organization_id=self.organization_id,
            )

    def test_when_organization_not_active(self, factories):
        inactive_org = factories.OrganizationFactory.create(
            id=self.organization_id,
            activated_at=datetime.combine(
                date.today() + timedelta(days=10), datetime.min.time()
            ),
        )

        with mock.patch(
            "eligibility.EnterpriseVerificationService.get_verification_for_user_and_org",
            return_value=self.verification,
        ), mock.patch(
            "models.enterprise.Organization.query.get",
            return_value=inactive_org,
        ), pytest.raises(
            lifecycle.InvalidOrganizationError
        ):
            # When
            self.track_svc.validate_initiation(
                track=TrackName.ADOPTION,
                user_id=self.user_id,
                organization_id=self.organization_id,
            )

    def test_when_no_client_track(self, factories):
        active_org = factories.OrganizationFactory.create(
            id=self.organization_id,
            activated_at=datetime.combine(
                date.today() - timedelta(days=10), datetime.min.time()
            ),
        )
        with mock.patch(
            "eligibility.EnterpriseVerificationService.get_verification_for_user_and_org",
            return_value=self.verification,
        ), mock.patch(
            "models.enterprise.Organization.query.get",
            return_value=active_org,
        ), mock.patch(
            "tracks.repository.TracksRepository.get_client_track", return_value=None
        ), pytest.raises(
            lifecycle.MissingClientTrackError
        ):
            # When
            self.track_svc.validate_initiation(
                track=TrackName.ADOPTION,
                user_id=1,
                organization_id=11,
            )

    def test_when_client_track_not_enrollable(self, factories):
        active_org = factories.OrganizationFactory.create(
            id=self.organization_id,
            activated_at=datetime.combine(
                date.today() - timedelta(days=10), datetime.min.time()
            ),
        )
        client_track_1 = factories.ClientTrackFactory.create(
            track=TrackName.ADOPTION,
            organization=active_org,
        )
        client_track_2 = factories.ClientTrackFactory.create(
            track=TrackName.FERTILITY,
            organization=active_org,
        )

        with mock.patch(
            "eligibility.EnterpriseVerificationService.get_verification_for_user_and_org",
            return_value=self.verification,
        ), mock.patch(
            "models.enterprise.Organization.query.get",
            return_value=active_org,
        ), mock.patch(
            "tracks.repository.TracksRepository.get_client_track",
            return_value=client_track_1,
        ), mock.patch(
            "tracks.service.TrackSelectionService.get_enrollable_tracks_for_org",
            return_value=[client_track_2],
        ), pytest.raises(
            lifecycle.IncompatibleTrackError
        ):
            # When
            self.track_svc.validate_initiation(
                track=TrackName.ADOPTION,
                user_id=1,
                organization_id=11,
            )


def test_initiate_write_eligibility_ids(
    default_user,
    mock_org_with_track,
    factories,
):
    # Given
    verification = e9y_factories.VerificationFactory.create(
        user_id=default_user.id,
        organization_id=mock_org_with_track.id,
        active_effective_range=True,
    )
    # When
    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ):
        lifecycle.initiate(
            user=default_user,
            track=TrackName.ADOPTION,
            eligibility_organization_id=mock_org_with_track.id,
        )
    # Then
    current_track = default_user.current_member_track
    assert current_track.eligibility_member_id == verification.eligibility_member_id
    assert current_track.eligibility_verification_id == verification.verification_id


def test_initiate_write_eligibility_ids_v2(
    default_user,
    mock_org_with_track,
    factories,
):
    member_1_id = 1
    member_2_id = 1001
    member_2_version = 1000
    verification_2_id = 10011
    # Given
    verification = e9y_factories.VerificationFactory.create(
        user_id=default_user.id,
        organization_id=mock_org_with_track.id,
        eligibility_member_id=member_1_id,
        active_effective_range=True,
    )
    verification.verification_1_id = verification.verification_id
    verification.verification_2_id = verification_2_id
    verification.eligibility_member_2_id = member_2_id
    verification.eligibility_member_2_version = member_2_version
    # When
    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ):
        lifecycle.initiate(
            user=default_user,
            track=TrackName.ADOPTION,
            eligibility_organization_id=mock_org_with_track.id,
        )
    # Then
    current_track = default_user.current_member_track
    assert current_track.eligibility_member_id == verification.eligibility_member_id
    assert current_track.eligibility_verification_id == verification.verification_id
    assert current_track.eligibility_member_2_version == member_2_version
    assert current_track.eligibility_verification_id == verification.verification_id
    assert current_track.eligibility_verification_2_id == verification_2_id


def test_terminate(factories):
    # Given
    target_name = TrackName.PREGNANCY
    user = factories.EnterpriseUserFactory.create(
        tracks__name=TrackName.FERTILITY, enabled_tracks=[target_name]
    )
    # When
    with mock.patch("maven.feature_flags.bool_variation", return_value=True):
        with mock.patch(
            "tasks.enterprise.update_single_user_company_mfa.delay", return_value=None
        ) as mock_update_user_company_mfa_call:
            old_track = user.current_member_track
            lifecycle.terminate(old_track)
            # Then
            assert user.current_member_track is None
            assert not db.session.query(
                db.session.query(Credit).filter_by(user_id=user.id).exists()
            ).scalar()
            assert (
                db.session.query(MemberTrackPhaseReporting)
                .filter_by(
                    member_track_id=old_track.id, name=old_track.final_phase.name
                )
                .one()
            )
            assert mock_update_user_company_mfa_call.call_count == 1


def test_terminate_expires_all_enterprise_credits(factories, default_user):
    track = factories.MemberTrackFactory(user=default_user)
    factories.CreditFactory.create(user_id=default_user.id, amount=1)
    factories.CreditFactory.create(
        user_id=default_user.id,
        eligibility_member_id=1,
        amount=1,
    )
    factories.CreditFactory.create(
        user_id=default_user.id,
        eligibility_verification_id=1,
        amount=1,
    )

    lifecycle.terminate(track)

    assert track.ended_at is not None

    users_credits = (
        db.session.query(Credit)
        .filter_by(
            user_id=default_user.id,
        )
        .all()
    )
    assert len([c for c in users_credits if c.expires_at is None]) == 1
    assert len([c for c in users_credits if c.expires_at is not None]) == 2


def test_terminate_credit_expiry_with_remaining_tracks_and_renewals(
    factories, default_user
):
    """
    Test different scenarios for credit expiration when terminating a track:
    - When there are remaining active tracks
    - When there's a scheduled renewal of the same track
    - When neither of the above conditions are met
    """
    first_track = factories.MemberTrackFactory(
        user=default_user, name=TrackName.PREGNANCY
    )
    second_track = factories.MemberTrackFactory(
        user=default_user, name=TrackName.PARENTING_AND_PEDIATRICS
    )
    eligibility_verification_id = 1
    credit1 = factories.CreditFactory.create(
        user_id=default_user.id,
        eligibility_verification_id=eligibility_verification_id,
        amount=1,
    )
    credit2 = factories.CreditFactory.create(
        user_id=default_user.id,
        eligibility_verification_id=eligibility_verification_id,
        amount=1,
    )

    # Test Case 1: Terminate a track when there are other active tracks
    # Credits should not be expired
    lifecycle.terminate(first_track)

    db.session.refresh(credit1)
    db.session.refresh(credit2)

    # Credits should not be expired because there are remaining active tracks
    assert credit1.expires_at is None
    assert credit2.expires_at is None

    # Test Case 2: Create a renewal for the second track using the lifecycle.renew function
    renewal_track = lifecycle.renew(second_track)

    assert len(default_user.active_tracks) == 1
    assert len(default_user.scheduled_tracks) == 1
    assert default_user.scheduled_tracks[0].id == renewal_track.id
    assert renewal_track.activated_at is None
    assert renewal_track.previous_member_track_id == second_track.id

    lifecycle.terminate(second_track)

    db.session.refresh(credit1)
    db.session.refresh(credit2)

    # Credits should not be expired because there's a scheduled renewal
    assert credit1.expires_at is None
    assert credit2.expires_at is None

    # Test Case 3: Terminate the renewal track (which leaves no active tracks or renewals)
    lifecycle.terminate(renewal_track)

    db.session.refresh(credit1)
    db.session.refresh(credit2)

    # Now credits should be expired since there are no remaining tracks or renewals
    assert credit1.expires_at is not None
    assert credit2.expires_at is not None


def test_terminate_with_expire_credits_false(factories, default_user):
    """
    Test that when expire_credits=False, credits are not expired
    even when there are no remaining tracks or renewals.
    This is typically used during transitions.
    """
    track = factories.MemberTrackFactory(user=default_user, name=TrackName.PREGNANCY)

    credit = factories.CreditFactory.create(
        user_id=default_user.id,
        eligibility_verification_id=1,
        amount=1,
    )

    lifecycle.terminate(track, expire_credits=False)

    db.session.refresh(credit)

    assert credit.expires_at is None

    assert track.ended_at is not None


def test_transition(factories):
    # Given
    target_name = TrackName.PREGNANCY
    org = factories.OrganizationFactory.create()
    factories.ClientTrackFactory.create(organization=org, track=target_name)
    fertility_client_track = factories.ClientTrackFactory.create(
        organization=org, track=TrackName.FERTILITY
    )
    user = factories.DefaultUserFactory.create()
    factories.MemberTrackFactory.create(
        user=user, client_track=fertility_client_track, name=TrackName.FERTILITY
    )
    verification = e9y_factories.VerificationFactory.create(
        user_id=user.id,
        organization_id=org.id,
        active_effective_range=True,
    )
    # When
    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ):
        lifecycle.transition(user.current_member_track, target=target_name)
        # Then
        assert user.current_member_track.name == target_name
        assert (
            user.current_member_track.previous_member_track_id
            == user.inactive_tracks[0].id
        )
        assert user.current_member_track.bucket_id == user.inactive_tracks[0].bucket_id
        assert (
            user.current_member_track.organization.id
            == user.inactive_tracks[0].organization.id
        )
        assert user.inactive_tracks[0].ended_at
        assert (
            user.inactive_tracks[0].final_phase.ended_at
            == user.inactive_tracks[0].ended_at.date()
        )
        assert db.session.query(
            db.session.query(Credit)
            .filter_by(
                user_id=user.id,
                eligibility_verification_id=verification.verification_id,
            )
            .exists()
        ).scalar()


def test_transition_send_braze_event(factories, patch_braze_send_event):
    # Given
    target_name = TrackName.PREGNANCY
    org = factories.OrganizationFactory.create()
    factories.ClientTrackFactory.create(organization=org, track=target_name)
    fertility_client_track = factories.ClientTrackFactory.create(
        organization=org, track=TrackName.FERTILITY
    )
    user = factories.DefaultUserFactory.create()
    factories.MemberTrackFactory.create(
        user=user, client_track=fertility_client_track, name=TrackName.FERTILITY
    )
    verification = e9y_factories.VerificationFactory.create(
        user_id=user.id,
        organization_id=org.id,
        active_effective_range=True,
    )
    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ):
        # When
        lifecycle.transition(user.current_member_track, target=target_name)
        # Then
        assert patch_braze_send_event.called_once_with(
            user, TrackName.FERTILITY, TrackName.PREGNANCY, False
        )


def test_transition_is_employee(factories):
    # Given
    target_name = TrackName.PREGNANCY
    org = factories.OrganizationFactory.create()
    factories.ClientTrackFactory.create(organization=org, track=target_name)
    fertility_client_track = factories.ClientTrackFactory.create(
        organization=org, track=TrackName.FERTILITY
    )
    user = factories.DefaultUserFactory.create()
    factories.MemberTrackFactory.create(
        user=user, client_track=fertility_client_track, name=TrackName.FERTILITY
    )
    verification = e9y_factories.VerificationFactory.create(
        user_id=user.id,
        organization_id=org.id,
        active_effective_range=True,
    )
    user.current_member_track.is_employee = False
    db.session.commit()
    # When
    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ):
        lifecycle.transition(user.current_member_track, target=target_name)
        # Then
        assert user.current_member_track.is_employee is False


def test_transition_validate(factories):
    # Given
    target_name = TrackName.GENERAL_WELLNESS
    user = factories.EnterpriseUserFactory.create(tracks__name=TrackName.ADOPTION)
    # When
    with pytest.raises(lifecycle.TransitionNotConfiguredError):
        lifecycle.transition(user.current_member_track, target_name)


@patch(
    "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
)
def test_transition_validate_eligibility_no_verification_bypass_e9y_check(
    patch_get_verification_for_user_and_org, factories
):
    # Given (allow listed e9y bypass transition)
    target_name = TrackName.POSTPARTUM
    user = factories.EnterpriseUserFactory.create(
        tracks__name=TrackName.PREGNANCY, enabled_tracks=[target_name]
    )
    patch_get_verification_for_user_and_org.return_value = None
    # When
    result = lifecycle.transition(user.current_member_track, target_name)
    # Then
    assert result is not None
    assert result.organization.id == user.inactive_tracks[0].organization.id


@patch(
    "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
)
def test_transition_validate_eligibility_no_verification(
    patch_get_verification_for_user, factories
):
    # Given
    target_name = TrackName.PREGNANCY
    user = factories.EnterpriseUserFactory.create(
        tracks__name=TrackName.FERTILITY, enabled_tracks=[target_name]
    )
    patch_get_verification_for_user.return_value = None
    # When
    with pytest.raises(lifecycle.MissingVerificationError):
        lifecycle.transition(user.current_member_track, target_name)


@patch(
    "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
)
def test_transition_validate_eligibility_inactive_verification(
    patch_get_verification_for_user, factories
):
    # Given
    target_name = TrackName.PREGNANCY
    user = factories.EnterpriseUserFactory.create(
        tracks__name=TrackName.FERTILITY, enabled_tracks=[target_name]
    )
    verification: EligibilityVerification = e9y_factories.VerificationFactory.create()
    patch_get_verification_for_user.return_value = verification
    # When
    with pytest.raises(lifecycle.InactiveVerificationError):
        lifecycle.transition(user.current_member_track, target_name)


@patch(
    "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
)
def test_transition_validate_eligibility_wrong_org_verification(
    patch_get_verification_for_user, mock_valid_verification, factories
):
    # Given
    target_name = TrackName.PREGNANCY
    user = factories.EnterpriseUserFactory.create(
        tracks__name=TrackName.FERTILITY, enabled_tracks=[target_name]
    )
    patch_get_verification_for_user.return_value = mock_valid_verification
    # When
    with pytest.raises(lifecycle.EligibleForWrongOrgError):
        lifecycle.transition(user.current_member_track, target_name)


def test_initiate_transition(factories):
    # Given
    target_name = TrackName.PREGNANCY
    org = factories.OrganizationFactory.create()
    factories.ClientTrackFactory.create(organization=org, track=target_name)
    fertility_client_track = factories.ClientTrackFactory.create(
        organization=org, track=TrackName.FERTILITY
    )
    user = factories.DefaultUserFactory.create()
    factories.MemberTrackFactory.create(
        user=user, client_track=fertility_client_track, name=TrackName.FERTILITY
    )
    verification = e9y_factories.VerificationFactory.create(
        user_id=user.id,
        organization_id=org.id,
        active_effective_range=True,
    )
    # When
    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ):
        # When
        lifecycle.initiate_transition(user.current_member_track, target_name)
        assert user.current_member_track.transitioning_to == target_name


def test_finish_transition(factories):
    # Given
    target_name = TrackName.PREGNANCY
    org = factories.OrganizationFactory.create()
    factories.ClientTrackFactory.create(organization=org, track=target_name)
    fertility_client_track = factories.ClientTrackFactory.create(
        organization=org, track=TrackName.FERTILITY
    )
    user = factories.DefaultUserFactory.create()
    factories.MemberTrackFactory.create(
        user=user, client_track=fertility_client_track, name=TrackName.FERTILITY
    )
    verification = e9y_factories.VerificationFactory.create(
        user_id=user.id,
        organization_id=org.id,
        active_effective_range=True,
    )
    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ):
        lifecycle.initiate_transition(user.current_member_track, target_name)
        # When
        lifecycle.finish_transition(user.current_member_track)
        # Then
        assert user.current_member_track.name == target_name
        assert (
            user.current_member_track.previous_member_track_id
            == user.inactive_tracks[0].id
        )
        assert user.current_member_track.bucket_id == user.inactive_tracks[0].bucket_id
        assert user.inactive_tracks[0].ended_at
        assert db.session.query(
            db.session.query(Credit)
            .filter_by(
                user_id=user.id,
                eligibility_verification_id=verification.verification_id,
            )
            .exists()
        ).scalar()


def test_cancel_transition(factories):
    # Given
    target_name = TrackName.PREGNANCY
    org = factories.OrganizationFactory.create()
    factories.ClientTrackFactory.create(organization=org, track=target_name)
    fertility_client_track = factories.ClientTrackFactory.create(
        organization=org, track=TrackName.FERTILITY
    )
    user = factories.DefaultUserFactory.create()
    factories.MemberTrackFactory.create(
        user=user, client_track=fertility_client_track, name=TrackName.FERTILITY
    )
    verification = e9y_factories.VerificationFactory.create(
        user_id=user.id,
        organization_id=org.id,
        active_effective_range=True,
    )
    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ):
        # When
        lifecycle.initiate_transition(user.current_member_track, target_name)
        lifecycle.cancel_transition(user.current_member_track)
        assert user.current_member_track.transitioning_to is None


@pytest.mark.parametrize(
    "from_track,to_track",
    [
        (TrackName.PREGNANCY, TrackName.PREGNANCYLOSS),
        (TrackName.PREGNANCY, TrackName.POSTPARTUM),
        (TrackName.PARTNER_PREGNANT, TrackName.PARTNER_NEWPARENT),
    ],
)
def test_transition_clears_due_date(factories, from_track, to_track):
    # Given
    user = factories.EnterpriseUserFactory.create(
        tracks__name=from_track,
        enabled_tracks=[to_track],
        health_profile__due_date=date.today() + timedelta(days=80),
    )
    user.health_profile.add_a_child(date.today() - timedelta(days=1))
    lifecycle.initiate_transition(user.current_member_track, to_track)
    assert user.health_profile.due_date is not None
    # When
    lifecycle.finish_transition(user.current_member_track)
    # Then
    assert user.health_profile.due_date is None


def test_fertility_to_pregnancy(factories):
    # Given
    target_name = TrackName.PREGNANCY
    org = factories.OrganizationFactory.create()
    factories.ClientTrackFactory.create(organization=org, track=target_name)
    fertility_client_track = factories.ClientTrackFactory.create(
        organization=org, track=TrackName.FERTILITY
    )
    user = factories.DefaultUserFactory.create()
    factories.MemberTrackFactory.create(
        user=user, client_track=fertility_client_track, name=TrackName.FERTILITY
    )
    verification = e9y_factories.VerificationFactory.create(
        user_id=user.id,
        organization_id=org.id,
        active_effective_range=True,
    )
    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ):
        # When
        shim = lifecycle.transition(user.current_member_track, target_name)
        track = shim.user.current_member_track
        # Then
        assert user.current_member_track == shim
        assert shim.name == track.name == target_name


@mock.patch("models.tracks.client_track.should_enable_doula_only_track")
def test_transition__member_transitions_to_doula_only_track(
    should_enable_doula_only_track, factories
):
    # Given
    target_name = TrackName.PREGNANCY
    org = factories.OrganizationFactory.create()
    factories.ClientTrackFactory.create(
        organization=org, track=target_name, track_modifiers="doula_only"
    )
    fertility_client_track = factories.ClientTrackFactory.create(
        organization=org, track=TrackName.FERTILITY
    )
    user = factories.DefaultUserFactory.create()
    factories.MemberTrackFactory.create(
        user=user, client_track=fertility_client_track, name=TrackName.FERTILITY
    )
    verification = e9y_factories.VerificationFactory.create(
        user_id=user.id,
        organization_id=org.id,
        active_effective_range=True,
    )

    assert len(user.active_tracks) == 1
    assert user.active_tracks[0].name == TrackName.FERTILITY

    # When
    with mock.patch(
        "eligibility.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ):
        lifecycle.transition(user.current_member_track, target=target_name)
        # Then

        assert len(user.active_tracks) == 1
        assert user.active_tracks[0].name == target_name
        assert user.active_tracks[0].track_modifiers == [TrackModifiers.DOULA_ONLY]


@pytest.mark.parametrize("is_doula_provider", [True, False])
@mock.patch("appointments.services.common.log.info")
@mock.patch("models.tracks.client_track.should_enable_doula_only_track")
def test_transition__member_transitions_to_doula_only_track__preexisting_appointments(
    mock_should_enable_doula_only_track, mock_log_info, is_doula_provider, factories
):
    # Given
    target_name = TrackName.PREGNANCY
    org = factories.OrganizationFactory.create()
    pregnancy_client_track = factories.ClientTrackFactory.create(
        organization=org, track=target_name, track_modifiers="doula_only"
    )
    fertility_client_track = factories.ClientTrackFactory.create(
        organization=org, track=TrackName.FERTILITY
    )
    user = factories.DefaultUserFactory.create()
    factories.MemberTrackFactory.create(
        user=user, client_track=fertility_client_track, name=TrackName.FERTILITY
    )
    verification = e9y_factories.VerificationFactory.create(
        user_id=user.id,
        organization_id=org.id,
        active_effective_range=True,
    )

    ca_vertical = (
        factories.VerticalFactory.create(name="Doula And Childbirth Educator")
        if is_doula_provider
        else factories.VerticalFactory.create(name="Fertility Awareness Educator")
    )
    ca = factories.PractitionerUserFactory(
        practitioner_profile__verticals=[ca_vertical]
    )

    client_track_id = pregnancy_client_track.id
    allowed_verticals_by_track = VerticalAccessByTrack(
        client_track_id=client_track_id,
        vertical_id=ca_vertical.id,
        track_modifiers=[TrackModifiers.DOULA_ONLY] if is_doula_provider else None,
    )

    db.session.add(allowed_verticals_by_track)
    db.session.commit()

    utcnow = datetime.utcnow().replace(second=0, microsecond=0)
    one_hour_from_now = utcnow + timedelta(hours=1)

    member_schedule = factories.ScheduleFactory.create(user=user)
    appointment = factories.AppointmentFactory.create_with_practitioner(
        member_schedule=member_schedule,
        practitioner=ca,
        scheduled_start=one_hour_from_now,
    )

    appointment_id = appointment.id

    # When
    with mock.patch(
        "eligibility.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ):
        lifecycle.transition(user.current_member_track, target=target_name)

    # Then
    assert len(user.active_tracks) == 1
    assert user.active_tracks[0].name == target_name
    assert user.active_tracks[0].track_modifiers == [TrackModifiers.DOULA_ONLY]

    # we only expect to be informed about a cancelled appointment if the provider is non-doula
    if is_doula_provider:
        mock_log_info.assert_not_called()
    else:
        mock_log_info.assert_called_once_with(
            "Cancelled existing appointments booked with unsupported providers",
            member_id=user.id,
            invalid_appointment_ids=[appointment_id],
        )

        # assert that the appointment has been cancelled
        appointment = (
            db.session.query(Appointment).filter_by(id=appointment_id).one_or_none()
        )
        assert appointment.state == APPOINTMENT_STATES.cancelled


def test_check_track_state_pregnancy_due_date_change(factories):
    # Given
    target_name = TrackName.PREGNANCY
    user = factories.EnterpriseUserFactory.create(
        tracks__name=target_name,
        enabled_tracks=[target_name],
        health_profile__due_date=date.today() + timedelta(days=1),
    )
    user.health_profile.json.pop("children")
    # When
    due_date = date.today() - timedelta(days=1)
    anchor_date = due_date - PregnancyMemberTrack.PREGNANCY_DURATION
    user.health_profile.due_date = due_date
    lifecycle.check_track_state(user.current_member_track)
    # Then
    assert user.current_member_track.name == target_name
    assert user.current_member_track.anchor_date == anchor_date


def test_check_track_state_pregnancy_uses_anchor_date_as_childs_birthdate(factories):
    user = factories.EnterpriseUserFactory.create(
        tracks__name=TrackName.PREGNANCY,
        enabled_tracks=[TrackName.PREGNANCY, TrackName.POSTPARTUM],
        health_profile__due_date=date.today() + timedelta(days=1),
    )

    expected_due_date = date.today() - timedelta(days=30)

    anchor_date = expected_due_date - PregnancyMemberTrack.PREGNANCY_DURATION
    user.active_tracks[0].anchor_date = anchor_date
    user.health_profile.due_date = None

    lifecycle.check_track_state(user.current_member_track)

    assert user.health_profile.last_child_birthday == expected_due_date


@pytest.mark.parametrize(
    "due_date,should_add_child",
    [
        (date.today() - timedelta(days=10), True),  # Should add child
        (date.today() - timedelta(days=365), False),  # Too far in past
        (date.today() + timedelta(days=1), False),  # Due date in future
        (None, False),  # Due date not set
    ],
)
def test_prepare_for_auto_transition(factories, due_date, should_add_child):
    track = factories.MemberTrackFactory.create(name=TrackName.PREGNANCY)
    track.user.health_profile.json["children"].pop()
    track.user.health_profile.due_date = due_date
    assert track.user.health_profile.last_child_birthday is None
    prepare_user_for_auto_transition(track)
    if should_add_child:
        assert track.user.health_profile.last_child_birthday == due_date
    else:
        assert track.user.health_profile.last_child_birthday is None


@pytest.mark.parametrize(
    "birthday,should_update",
    [
        # Birthday too long ago, should get updated to user's due date
        (date.today() - timedelta(days=180), True),
        # Birthday recent enough, should not get updated to user's due date
        (date.today() - timedelta(days=30), False),  # Too far in past
    ],
)
def test_prepare_for_auto_transition_with_child(factories, birthday, should_update):
    track = factories.MemberTrackFactory.create(name=TrackName.PREGNANCY)
    health_profile = track.user.health_profile
    health_profile.json["children"].pop()
    due_date = date.today() - timedelta(days=5)
    health_profile.due_date = due_date
    health_profile.add_a_child(birthday)
    prepare_user_for_auto_transition(track)
    if should_update:
        assert health_profile.last_child_birthday == due_date
    else:
        assert health_profile.last_child_birthday == birthday


def test_auto_transition_from_due_date(factories):
    # Given
    target_name = TrackName.POSTPARTUM
    user = factories.EnterpriseUserFactory.create(
        tracks__name=TrackName.PREGNANCY,
        enabled_tracks=[target_name],
        health_profile__due_date=date.today() + timedelta(days=1),
    )
    user.health_profile.json.pop("children")
    # When
    anchor_date = date.today() - timedelta(weeks=3, days=1)
    user.health_profile.due_date = anchor_date
    lifecycle.check_track_state(user.current_member_track)
    track = user.current_member_track
    # Then
    assert track.name == target_name
    assert track.anchor_date == anchor_date
    assert track.auto_transitioned
    assert track.user.health_profile.last_child_birthday == anchor_date


def test_auto_transition_from_birthday(factories):
    # Given
    target_name = TrackName.POSTPARTUM
    user = factories.EnterpriseUserFactory.create(
        tracks__name=TrackName.PREGNANCY,
        enabled_tracks=[target_name],
        health_profile__due_date=date.today() + timedelta(days=1),
    )

    # When
    anchor_date = date.today()
    due_date = anchor_date - timedelta(weeks=3, days=1)
    user.health_profile.due_date = due_date
    user.health_profile.add_a_child(anchor_date)
    lifecycle.check_track_state(user.current_member_track)
    track = user.current_member_track
    # Then
    assert track.name == target_name
    assert track.anchor_date == anchor_date
    assert track.auto_transitioned


@pytest.mark.parametrize(
    argnames="track,json,error",
    argvalues=[
        # Need a due-date.
        (TrackName.PREGNANCY, {}, lifecycle.MissingInformationError),
        # Due-date should be in the future.
        (
            TrackName.PREGNANCY,
            {"due_date": "1970-01-01"},
            lifecycle.TrackConfigurationError,
        ),
        # Due-date shouldn't be too far in the future.
        (
            TrackName.PREGNANCY,
            {"due_date": "2100-01-01"},
            lifecycle.TrackConfigurationError,
        ),
        # Need a birthday.
        (TrackName.POSTPARTUM, {}, lifecycle.MissingInformationError),
        (
            TrackName.POSTPARTUM,
            # Birthday shouldn't be in the future.
            {"children": [{"birthday": "3000-01-01"}]},
            lifecycle.TrackConfigurationError,
        ),
        (
            TrackName.POSTPARTUM,
            # Birthday shouldn't be far in the past.
            {"children": [{"birthday": "1970-01-01"}]},
            lifecycle.TrackConfigurationError,
        ),
    ],
)
def test_check_required_information(track, json, error, factories):
    # Given
    user = factories.EnterpriseUserFactory.create(tracks__name=track)
    # When
    user.health_profile.json = json
    # Then
    with pytest.raises(error):
        lifecycle.check_required_information(user.current_member_track)


def test_transition_flush_event(factories):
    # Given
    target_name = TrackName.POSTPARTUM
    user = factories.EnterpriseUserFactory.create(
        tracks__name=TrackName.PREGNANCY, enabled_tracks=[target_name]
    )

    def side_effect(*args, **kwargs):
        print(f"CALLED WITH: {args}, {kwargs}")

    mt = user.current_member_track

    mock_flush = mock.MagicMock(side_effect=side_effect)
    event.listens_for(db.session, "after_flush")(mock_flush)
    # When
    with mock.patch("utils.braze_events.braze.send_event"):
        lifecycle.transition(mt, target=target_name)
    # Then
    assert mock_flush.call_count == 2


def test_terminate_flush_event(factories):
    # Given
    target_name = TrackName.PREGNANCY
    user = factories.EnterpriseUserFactory.create(
        tracks__name=TrackName.FERTILITY, enabled_tracks=[target_name]
    )
    mock_flush = mock.MagicMock()
    mt = user.current_member_track
    event.listens_for(db.session, "after_flush")(mock_flush)
    # When
    lifecycle.terminate(mt)
    # Then
    assert mock_flush.call_count == 1


def test_initiate_flush_event(factories, default_user):
    # Given
    org = factories.OrganizationFactory.create()
    client_track = factories.ClientTrackFactory.create(
        organization=org, track=TrackName.ADOPTION
    )

    mock_flush = mock.MagicMock()
    event.listens_for(db.session, "after_flush")(mock_flush)

    with mock.patch(
        "tracks.service.tracks.TrackSelectionService.validate_initiation",
        return_value=client_track,
    ):
        # When
        lifecycle.initiate(
            user=default_user,
            track=TrackName.ADOPTION,
            eligibility_organization_id=org.id,
        )
        # Then
        assert mock_flush.call_count == 1


@patch("models.tracks.lifecycle.logger")
def test_initiate_flush_error(mock_log, factories, default_user):
    mock_bind = mock.Mock()
    mock_log.bind.return_value = mock_bind
    mock_error = mock.Mock()
    mock_bind.error = mock_error

    org = factories.OrganizationFactory.create()
    client_track = factories.ClientTrackFactory.create(
        organization=org, track=TrackName.ADOPTION
    )

    with mock.patch(
        "tracks.service.tracks.TrackSelectionService.validate_initiation",
        return_value=client_track,
    ), mock.patch(
        "storage.connection.db.session.flush",
        side_effect=TestDBException("DB Flush Error"),
    ):
        with pytest.raises(TestDBException):
            lifecycle.initiate(
                user=default_user,
                track=TrackName.ADOPTION,
                eligibility_organization_id=org.id,
            )
        mock_bind.error.assert_called_once_with(
            "[Member Track] Error while init MemberTrack.",
            exception="DB Flush Error",
            user_id=default_user.id,
            track_id=None,
            track_name=TrackName.ADOPTION,
            org_id=org.id,
            change_reason=None,
            transitioning_to=None,
            anchor_date=datetime.utcnow().date(),
            is_multi_track=False,
        )


def test_initiate_mismatched_org(factories, default_user):

    # Given
    org1 = factories.OrganizationFactory.create()
    org2 = factories.OrganizationFactory.create()

    factories.ClientTrackFactory.create(organization=org1, track=TrackName.ADOPTION)
    factories.ClientTrackFactory.create(organization=org2, track=TrackName.ADOPTION)
    verification = e9y_factories.VerificationFactory.create(
        user_id=default_user.id,
        organization_id=org1.id,
        active_effective_range=True,
    )
    # When
    with mock.patch(
        "eligibility.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ), pytest.raises(MismatchedOrganizationError):
        lifecycle.initiate(
            user=default_user,
            track=TrackName.ADOPTION,
            eligibility_organization_id=org2.id,
        )
        # Then exception should be thrown


@patch("tracks.service.tracks.TrackSelectionService.validate_initiation")
def test_initiate_missing_client_track(
    mock_validate_initiation, factories, default_user
):
    mock_validate_initiation.side_effect = MissingClientTrackError()

    org = factories.OrganizationFactory.create()

    with pytest.raises(MissingClientTrackError):
        # Given
        lifecycle.initiate(
            user=default_user,
            track=TrackName.ADOPTION,
            eligibility_organization_id=org.id,
        )
        # Then exception should be thrown


def test_initiate_transition_inactive_client_track(factories, default_user):
    with pytest.raises(MissingClientTrackError):
        # Given
        org = factories.OrganizationFactory.create()
        factories.ClientTrackFactory.create(organization=org, track=TrackName.PREGNANCY)
        factories.ClientTrackFactory.create(
            organization=org, track=TrackName.PREGNANCYLOSS, active=False
        )
        verification = e9y_factories.VerificationFactory.create(
            user_id=default_user.id, organization_id=org.id, active_effective_range=True
        )
        # When
        with mock.patch(
            "eligibility.EnterpriseVerificationService.get_verification_for_user_and_org",
            return_value=verification,
        ):
            lifecycle.initiate(
                user=default_user,
                track=TrackName.PREGNANCY,
                modified_by="123",
                change_reason=ChangeReason.API_PATCH_HEALTH_PROFILE_UPDATE,
                eligibility_organization_id=org.id,
            )

            # When
            lifecycle.transition(
                source=default_user.current_member_track,
                target=TrackName.PREGNANCYLOSS,
                modified_by="234",
                change_reason=ChangeReason.API_PROGRAM_INITIATE_TRANSITION,
            )
        # Then exception should be thrown


def test_initiate_transition_modified_by_change_reason(factories, default_user):
    org = factories.OrganizationFactory.create()
    client_track_1 = factories.ClientTrackFactory.create(
        organization=org, track=TrackName.PREGNANCY
    )
    factories.ClientTrackFactory.create(organization=org, track=TrackName.PREGNANCYLOSS)

    with mock.patch(
        "tracks.service.tracks.TrackSelectionService.validate_initiation",
        return_value=client_track_1,
    ):
        lifecycle.initiate(
            user=default_user,
            track=TrackName.PREGNANCY,
            modified_by="123",
            change_reason=ChangeReason.API_PATCH_HEALTH_PROFILE_UPDATE,
            eligibility_organization_id=org.id,
        )

        first_track = default_user.current_member_track
        assert first_track.modified_by == "123"
        assert first_track.change_reason == ChangeReason.API_PATCH_HEALTH_PROFILE_UPDATE

        lifecycle.transition(
            source=default_user.current_member_track,
            target=TrackName.PREGNANCYLOSS,
            modified_by="234",
            change_reason=ChangeReason.API_PROGRAM_INITIATE_TRANSITION,
        )

        second_track = default_user.current_member_track
        assert first_track.name != second_track.name
        assert first_track.change_reason == second_track.change_reason


def test_initiate_transition_skip_elig_check_no_verification(factories, default_user):
    org = factories.OrganizationFactory.create()
    factories.ClientTrackFactory.create(organization=org, track=TrackName.PREGNANCY)
    factories.ClientTrackFactory.create(organization=org, track=TrackName.PREGNANCYLOSS)
    verification = e9y_factories.VerificationFactory.create(
        user_id=default_user.id, organization_id=org.id, active_effective_range=True
    )

    with mock.patch(
        "eligibility.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ):
        lifecycle.initiate(
            user=default_user,
            track=TrackName.PREGNANCY,
            modified_by="123",
            change_reason=ChangeReason.API_PATCH_HEALTH_PROFILE_UPDATE,
            eligibility_organization_id=org.id,
        )

        first_track = default_user.current_member_track
        assert first_track.modified_by == "123"
        assert first_track.change_reason == ChangeReason.API_PATCH_HEALTH_PROFILE_UPDATE
        assert first_track.eligibility_member_id == verification.eligibility_member_id
        assert first_track.eligibility_verification_id == verification.verification_id
        assert (
            first_track.eligibility_member_2_id == verification.eligibility_member_2_id
        )

    with mock.patch(
        "eligibility.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=None,
    ):
        lifecycle.transition(
            source=default_user.current_member_track,
            target=TrackName.PREGNANCYLOSS,
            modified_by="234",
            change_reason=ChangeReason.API_PROGRAM_INITIATE_TRANSITION,
        )

        second_track = default_user.current_member_track
        assert first_track.name != second_track.name
        assert first_track.change_reason == second_track.change_reason
        assert second_track.eligibility_member_id == first_track.eligibility_member_id
        assert (
            second_track.eligibility_verification_id
            == first_track.eligibility_verification_id
        )
        assert (
            second_track.eligibility_member_2_id == first_track.eligibility_member_2_id
        )


def test_initiate_transition_require_elig_check_no_verification(
    factories, default_user
):
    org = factories.OrganizationFactory.create()
    factories.ClientTrackFactory.create(organization=org, track=TrackName.PREGNANCY)
    factories.ClientTrackFactory.create(organization=org, track=TrackName.GENERIC)
    verification = e9y_factories.VerificationFactory.create(
        user_id=default_user.id, organization_id=org.id, active_effective_range=True
    )

    with mock.patch(
        "eligibility.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ):
        lifecycle.initiate(
            user=default_user,
            track=TrackName.PREGNANCY,
            modified_by="123",
            change_reason=ChangeReason.API_PATCH_HEALTH_PROFILE_UPDATE,
            eligibility_organization_id=org.id,
        )

        first_track = default_user.current_member_track
        assert first_track.modified_by == "123"
        assert first_track.change_reason == ChangeReason.API_PATCH_HEALTH_PROFILE_UPDATE
        assert first_track.eligibility_member_id == verification.eligibility_member_id
        assert first_track.eligibility_verification_id == verification.verification_id
        assert (
            first_track.eligibility_member_2_id == verification.eligibility_member_2_id
        )

    with mock.patch(
        "eligibility.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=None,
    ), pytest.raises(MissingVerificationError):
        lifecycle.transition(
            source=default_user.current_member_track,
            target=TrackName.GENERIC,
            modified_by="234",
            change_reason=ChangeReason.API_PROGRAM_INITIATE_TRANSITION,
        )


def test_initiate_a_second_track(factories):
    user = factories.EnterpriseUserFactory.create(
        tracks__name=TrackName.TRYING_TO_CONCEIVE,
        enabled_tracks=[TrackName.PARENTING_AND_PEDIATRICS],
    )
    # Given
    org = factories.OrganizationFactory.create()
    client_track = factories.ClientTrackFactory.create(
        organization=org, track=TrackName.PARENTING_AND_PEDIATRICS
    )
    with mock.patch(
        "tracks.service.tracks.TrackSelectionService.validate_initiation",
        return_value=client_track,
    ):
        # When
        lifecycle.initiate(
            user=user,
            track=TrackName.PARENTING_AND_PEDIATRICS,
            eligibility_organization_id=org.id,
        )
        # Then
        assert user.active_tracks[0].name == TrackName.TRYING_TO_CONCEIVE
        assert user.active_tracks[1].name == TrackName.PARENTING_AND_PEDIATRICS


def test_should_bypass_eligibility_true_conditions():
    true_conditions = [
        ("pregnancy", "postpartum"),
        ("pregnancy", "pregnancyloss"),
        ("postpartum", "pregnancyloss"),
        ("partner_pregnant", "partner_newparent"),
        ("partner_pregnant", "pregnancyloss"),
        ("partner_newparent", "pregnancyloss"),
        ("fertility", "pregnancyloss"),
        ("fertility", "trying_to_conceive"),
        ("fertility", "partner_fertility"),
        ("fertility", "adoption"),
        ("fertility", "surrogacy"),
        ("fertility", "egg_freezing"),
        ("trying_to_conceive", "fertility"),
        ("trying_to_conceive", "partner_fertility"),
        ("trying_to_conceive", "adoption"),
        ("trying_to_conceive", "surrogacy"),
        ("trying_to_conceive", "egg_freezing"),
        ("partner_fertility", "fertility"),
        ("partner_fertility", "trying_to_conceive"),
        ("partner_fertility", "adoption"),
        ("partner_fertility", "surrogacy"),
        ("partner_fertility", "egg_freezing"),
        ("adoption", "fertility"),
        ("adoption", "trying_to_conceive"),
        ("adoption", "partner_fertility"),
        ("adoption", "surrogacy"),
        ("adoption", "egg_freezing"),
        ("surrogacy", "fertility"),
        ("surrogacy", "trying_to_conceive"),
        ("surrogacy", "partner_fertility"),
        ("surrogacy", "adoption"),
        ("surrogacy", "egg_freezing"),
        ("egg_freezing", "fertility"),
        ("egg_freezing", "trying_to_conceive"),
        ("egg_freezing", "partner_fertility"),
        ("egg_freezing", "adoption"),
        ("egg_freezing", "surrogacy"),
    ]
    for source, target in true_conditions:
        assert lifecycle._should_bypass_eligibility(source, target)


def test_should_bypass_eligibility_false_conditions():
    false_conditions = [
        ("pregnancy", "fertility"),
        ("trying_to_conceive", "partner_newparent"),
        ("adoption", "pregnancy"),
    ]
    for source, target in false_conditions:
        assert not lifecycle._should_bypass_eligibility(source, target)


def test_renew(default_user, mock_org_with_track, factories):
    # Given
    verification = e9y_factories.VerificationFactory.create(
        user_id=default_user.id,
        organization_id=mock_org_with_track.id,
        active_effective_range=True,
    )
    # When
    with mock.patch(
        "eligibility.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ):
        lifecycle.initiate(
            user=default_user,
            track=TrackName.ADOPTION,
            eligibility_organization_id=mock_org_with_track.id,
        )
    # Then
    current_track = default_user.current_member_track
    with mock.patch(
        "provider_matching.services.care_team_assignment.replace_care_team_members_during_transition"
    ) as assign_method, mock.patch(
        "tracks.repository.MemberTrackRepository.get"
    ) as mock_member_tracks_get:
        mock_member_tracks_get.return_value = current_track
        lifecycle.renew(current_track)
        assert assign_method.not_called(default_user)
        renewed_track = default_user.scheduled_tracks[0]
        assert renewed_track.name == TrackName.ADOPTION
        assert renewed_track.previous_member_track_id == current_track.id
        assert renewed_track.bucket_id == current_track.bucket_id


@patch("models.tracks.lifecycle.logger")
def test_renew_flush_error(mock_log, default_user, mock_org_with_track, factories):
    verification = e9y_factories.VerificationFactory.create(
        user_id=default_user.id,
        organization_id=mock_org_with_track.id,
        active_effective_range=True,
    )
    mock_bind = mock.Mock()
    mock_log.bind.return_value = mock_bind
    mock_error = mock.Mock()
    mock_bind.error = mock_error
    with mock.patch(
        "eligibility.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ):
        lifecycle.initiate(
            user=default_user,
            track=TrackName.ADOPTION,
            eligibility_organization_id=mock_org_with_track.id,
        )
    current_track = default_user.current_member_track
    with mock.patch(
        "tracks.repository.MemberTrackRepository.get"
    ) as mock_member_tracks_get, mock.patch(
        "storage.connection.db.session.flush",
        side_effect=TestDBException("DB Flush Error"),
    ):
        mock_member_tracks_get.return_value = current_track
        with pytest.raises(TestDBException):
            lifecycle.renew(current_track)

        mock_bind.error.assert_called_once_with(
            "Failed to renew track",
            exception="DB Flush Error",
            user_id=default_user.id,
            track_id=current_track.id,
            track_name=current_track.name,
            org_id=current_track.organization.id,
            change_reason=current_track.change_reason,
            transitioning_to=current_track.transitioning_to,
            anchor_date=current_track.anchor_date,
        )


@patch("eligibility.EnterpriseVerificationService.get_verification_for_user_and_org")
def test_initiate_overeligibility(
    patch_get_verification_for_user_and_org,
    default_user,
    factories,
    ff_test_data: TestData,
):
    # Given

    ff_test_data.update(
        ff_test_data.flag(
            "overeligibility-create-tracks",
        ).value_for_all(True),
    )

    org1 = factories.OrganizationFactory.create()
    org2 = factories.OrganizationFactory.create()
    verification1 = e9y_factories.VerificationFactory.create(
        user_id=default_user.id,
        organization_id=org1.id,
        is_active=True,
        active_effective_range=True,
    )
    verification1.effective_range.upper = datetime.utcnow().date() + timedelta(days=365)
    verification2 = e9y_factories.VerificationFactory.create(
        user_id=default_user.id,
        organization_id=org2.id,
        is_active=True,
        active_effective_range=True,
    )
    verification2.effective_range.upper = datetime.utcnow().date() + timedelta(days=365)

    def side_effect(*args, **kwargs):
        if kwargs["organization_id"] == org1.id:
            return verification1
        else:
            return verification2

    patch_get_verification_for_user_and_org.side_effect = side_effect

    client_track1 = factories.ClientTrackFactory.create(
        organization=org1, track=TrackName.PARENTING_AND_PEDIATRICS
    )
    factories.ClientTrackFactory.create(
        organization=org2, track=TrackName.PARENTING_AND_PEDIATRICS
    )
    # When
    lifecycle.initiate(
        user=default_user,
        track=TrackName.PARENTING_AND_PEDIATRICS,
        eligibility_organization_id=org1.id,
    )
    # Then
    assert default_user.active_tracks[0].name == TrackName.PARENTING_AND_PEDIATRICS
    assert default_user.active_tracks[0].client_track_id == client_track1.id


def test_initiate_overeligibility_flag_off(
    default_user,
    factories,
    ff_test_data: TestData,
):
    with pytest.raises(MismatchedOrganizationError):
        # Given

        ff_test_data.update(
            ff_test_data.flag(
                "overeligibility-create-tracks",
            ).value_for_all(False),
        )

        org1 = factories.OrganizationFactory.create()
        org2 = factories.OrganizationFactory.create()

        verification1 = e9y_factories.VerificationFactory.create(
            user_id=default_user.id,
            organization_id=org1.id,
            active_effective_range=True,
        )
        verification2 = e9y_factories.VerificationFactory.create(
            user_id=default_user.id,
            organization_id=org2.id,
            active_effective_range=True,
        )

        def side_effect(*args, **kwargs):
            if kwargs["organization_id"] == org1.id:
                return verification1
            else:
                return verification2

        factories.ClientTrackFactory.create(
            organization=org1, track=TrackName.PARENTING_AND_PEDIATRICS
        )
        client_track_2 = factories.ClientTrackFactory.create(
            organization=org2, track=TrackName.PARENTING_AND_PEDIATRICS
        )
        # When
        with mock.patch(
            "tracks.service.tracks.TrackSelectionService.validate_initiation",
            return_value=client_track_2,
        ), mock.patch(
            "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
            side_effect=side_effect,
        ):
            lifecycle.initiate(
                user=default_user,
                track=TrackName.PARENTING_AND_PEDIATRICS,
                eligibility_organization_id=org1.id,
            )
            # Then MismatchedOrganizationError is thrown


@patch(
    "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
)
def test_transition_bypass_verification(
    patch_get_verification_for_user_and_org, mock_org_with_track, factories
):
    # Given
    target_name = TrackName.PREGNANCYLOSS
    user = factories.EnterpriseUserFactory.create(
        tracks__name=TrackName.FERTILITY, enabled_tracks=[target_name]
    )
    verification = e9y_factories.VerificationFactory.create(
        user_id=user.id,
        organization_id=mock_org_with_track.id,
        active_effective_range=True,
    )
    patch_get_verification_for_user_and_org.return_value = verification
    # When
    lifecycle.transition(user.current_member_track, target_name)

    # When
    shim = lifecycle.transition(user.current_member_track, target_name)
    track = shim.user.current_member_track
    # Then
    assert user.current_member_track == shim
    assert shim.name == track.name == target_name


def test_initiate_requires_eligibility_organization_id(default_user):
    with pytest.raises(lifecycle.MismatchedOrganizationError):
        lifecycle.initiate(user=default_user, track=TrackName.ADOPTION)


def test_initiate_with_validation_eligibility_organization_id(default_user, factories):
    org = factories.OrganizationFactory.create()
    client_track: ClientTrack = factories.ClientTrackFactory.create(
        organization=org, track=TrackName.ADOPTION
    )

    with mock.patch(
        "tracks.service.tracks.TrackSelectionService.validate_initiation",
        return_value=client_track,
    ):
        lifecycle.initiate(
            user=default_user,
            track=TrackName.ADOPTION,
            eligibility_organization_id=org.id,
        )

    assert len(default_user.active_tracks) == 1
    assert default_user.active_tracks[0].organization.id == org.id


def test_initiate_with_validation_eligibility_organization_id_must_match_client_track(
    default_user, factories
):
    org = factories.OrganizationFactory.create()
    different_org = factories.OrganizationFactory.create()
    client_track: ClientTrack = factories.ClientTrackFactory.create(
        organization=org, track=TrackName.ADOPTION
    )

    with pytest.raises(lifecycle.MismatchedOrganizationError):
        with mock.patch(
            "tracks.service.tracks.TrackSelectionService.validate_initiation",
            return_value=client_track,
        ):
            lifecycle.initiate(
                user=default_user,
                track=TrackName.ADOPTION,
                eligibility_organization_id=different_org.id,
            )

    assert len(default_user.active_tracks) == 0


def test_initiate_without_validation_falls_back_to_eligibility_organization_id(
    default_user, factories
):
    org = factories.OrganizationFactory.create()
    client_track: ClientTrack = factories.ClientTrackFactory.create(
        organization=org, track=TrackName.ADOPTION
    )

    with mock.patch(
        "tracks.service.tracks.TrackSelectionService.validate_initiation",
        return_value=client_track,
    ):
        lifecycle.initiate(
            user=default_user,
            track=TrackName.ADOPTION,
            eligibility_organization_id=org.id,
            with_validation=False,
        )

    assert len(default_user.active_tracks) == 1
    assert default_user.active_tracks[0].organization.id == org.id


def test_event_handlers_count_on_initiate(factories, default_user):
    from tracks.lifecycle_events.event_system import EventType, event_manager

    original_handlers = event_manager._handlers.get(EventType.INITIATE.value, []).copy()
    event_manager._handlers[EventType.INITIATE.value] = []

    handler_execution_count = 0

    from tracks.lifecycle_events.event_system import event_handler

    @event_handler(EventType.INITIATE)
    def test_initiate_handler1(track, user):
        nonlocal handler_execution_count
        handler_execution_count += 1

    @event_handler(EventType.INITIATE)
    def test_initiate_handler2(track, user):
        nonlocal handler_execution_count
        handler_execution_count += 1

    assert len(event_manager._handlers.get(EventType.INITIATE.value, [])) == 2

    target_name = TrackName.PREGNANCY
    employee = factories.OrganizationEmployeeFactory.create(email=default_user.email)
    org = employee.organization
    client_track = factories.ClientTrackFactory.create(
        organization=org, track=target_name
    )

    from models.tracks import lifecycle
    from tracks.lifecycle_events.event_system import execute_handler

    with patch(
        "tracks.service.tracks.TrackSelectionService.validate_initiation"
    ) as mock_validate:
        mock_validate.return_value = client_track

        track = lifecycle.initiate(
            user=default_user,
            track=target_name,
            with_validation=True,
            eligibility_organization_id=org.id,
        )

        for handler_name in [
            h.__name__ for h in event_manager._handlers[EventType.INITIATE.value]
        ]:
            execute_handler(
                handler_name, EventType.INITIATE.value, track=track, user=default_user
            )

    assert handler_execution_count == 2

    event_manager._handlers[EventType.INITIATE.value] = original_handlers


def test_event_handlers_fault_isolation_actual_execution(factories, default_user):
    from tracks.lifecycle_events.event_system import EventType, event_manager

    original_handlers = event_manager._handlers.get(
        EventType.TERMINATE.value, []
    ).copy()
    event_manager._handlers[EventType.TERMINATE.value] = []

    handler_results = {
        "handler1_executed": False,
        "handler2_executed": False,
        "handler3_executed": False,
    }

    from tracks.lifecycle_events.event_system import event_handler

    @event_handler(EventType.TERMINATE)
    def failing_handler(track_id, user_id):
        handler_results["handler1_executed"] = True
        raise ValueError("Intentional test error")

    @event_handler(EventType.TERMINATE)
    def successful_handler1(track_id, user_id):
        handler_results["handler2_executed"] = True

    @event_handler(EventType.TERMINATE)
    def successful_handler2(track_id, user_id):
        handler_results["handler3_executed"] = True

    assert len(event_manager._handlers.get(EventType.TERMINATE.value, [])) == 3

    target_name = TrackName.PREGNANCY
    employee = factories.OrganizationEmployeeFactory.create(email=default_user.email)
    org = employee.organization
    factories.ClientTrackFactory.create(organization=org, track=target_name)

    track = factories.MemberTrackFactory.create(user=default_user, name=target_name)

    from tracks.lifecycle_events.event_system import execute_handler

    for handler_name in [
        h.__name__ for h in event_manager._handlers[EventType.TERMINATE.value]
    ]:
        execute_handler(
            handler_name,
            EventType.TERMINATE.value,
            track_id=track.id,
            user_id=default_user.id,
        )

    assert handler_results["handler1_executed"] is True
    assert handler_results["handler2_executed"] is True
    assert handler_results["handler3_executed"] is True

    event_manager._handlers[EventType.TERMINATE.value] = original_handlers
