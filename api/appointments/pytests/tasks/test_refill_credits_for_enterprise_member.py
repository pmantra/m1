from __future__ import annotations

import datetime
from unittest import mock

import pytest

from appointments.models.payments import Credit
from appointments.tasks.credits import refill_credits_for_enterprise_member
from eligibility.e9y import EligibilityVerification
from eligibility.pytests import factories as e9y_factories
from pytests.factories import ClientTrackFactory, MemberTrackFactory


@mock.patch("appointments.tasks.credits.tracks_svc")
@pytest.mark.usefixtures("frozen_now")
def test_refill_credits_for_enterprise_member_refill_2000(
    tracks_svc, member_with_add_appointment, new_credit, db, datetime_now
):
    """
    Test that the enterprise user who has less than 1000 credits gets 2000 credits
    refill.
    """

    # Given a user with less than 1000 credits
    tracks_svc_instance = mock.Mock()
    tracks_svc.TrackSelectionService.return_value = tracks_svc_instance
    tracks_svc_instance.is_enterprise.return_value = True
    member = member_with_add_appointment
    verification: EligibilityVerification = e9y_factories.VerificationFactory.create()
    verification.user_id = member.id

    new_credit(800, member)
    client_track = ClientTrackFactory.create(length_in_days=100)
    member_track = MemberTrackFactory.create(
        name="pregnancy",
        user=member,
        active=True,
        client_track_id=client_track.id,
        anchor_date=datetime.date.today(),
        eligibility_member_id=verification.eligibility_member_id,
        eligibility_verification_id=verification.verification_id,
    )
    track_scheduled_end = member_track.get_scheduled_end_date()

    # When
    with mock.patch(
        "eligibility.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ):
        refill_credits_for_enterprise_member(member_id=member.id, appointment_id=1)

    # The second available credit we get is the newly added credit.
    available_credits = db.session.query(Credit).filter(Credit.user_id == member.id)
    new_credit = available_credits[1]
    assert new_credit.amount == 2000
    assert new_credit.expires_at == datetime.datetime(
        track_scheduled_end.year,
        track_scheduled_end.month,
        track_scheduled_end.day,
        23,
        59,
        59,
    )
    assert new_credit.activated_at == datetime_now - datetime.timedelta(minutes=1)
    assert new_credit.user_id == member.id
    assert new_credit.eligibility_member_id == verification.eligibility_member_id
    assert new_credit.eligibility_verification_id == verification.verification_id


@mock.patch("appointments.tasks.credits.tracks_svc")
def test_refill_credits_for_enterprise_member_marketplace_user_no_refill(
    tracks_svc, member_with_add_appointment, new_credit, db
):
    """
    Test that the marketplace user won't get credit refill.
    """
    # Given a marketplace member
    tracks_svc_instance = mock.Mock()
    tracks_svc.TrackSelectionService.return_value = tracks_svc_instance
    tracks_svc_instance.is_enterprise.return_value = False
    member = member_with_add_appointment
    new_credit(800, member)
    client_track = ClientTrackFactory.create(length_in_days=100)
    MemberTrackFactory.create(
        name="pregnancy",
        user=member,
        active=True,
        client_track_id=client_track.id,
        anchor_date=datetime.date.today(),
    )

    # When
    with mock.patch(
        "eligibility.EnterpriseVerificationService.get_verification_for_user_and_org"
    ) as mock_get_verification:
        refill_credits_for_enterprise_member(member_id=member.id, appointment_id=1)
        mock_get_verification.assert_not_called()

    # Then
    # Assert there is only 1 credit (the original credit) and there is no new credit refilled
    available_credits = (
        db.session.query(Credit).filter(Credit.user_id == member.id).all()
    )
    assert len(available_credits) == 1
    assert available_credits[0].amount == 800


@mock.patch("appointments.tasks.credits.tracks_svc")
def test_refill_credits_for_enterprise_member_enterprise_user_no_refill(
    tracks_svc, member_with_add_appointment, new_credit, db
):
    """
    Test that the enterprise user who has more than 1000 credits won't get
    credit refill.
    """
    tracks_svc_instance = mock.Mock()
    tracks_svc.TrackSelectionService.return_value = tracks_svc_instance
    tracks_svc_instance.is_enterprise.return_value = True
    member = member_with_add_appointment
    new_credit(1200, member)
    client_track = ClientTrackFactory.create(length_in_days=100)
    MemberTrackFactory.create(
        name="pregnancy",
        user=member,
        active=True,
        client_track_id=client_track.id,
        anchor_date=datetime.date.today(),
    )

    with mock.patch(
        "eligibility.EnterpriseVerificationService.get_verification_for_user_and_org"
    ) as mock_get_verification:
        refill_credits_for_enterprise_member(member_id=member.id, appointment_id=1)
        mock_get_verification.assert_not_called()

    available_credits = (
        db.session.query(Credit).filter(Credit.user_id == member.id).all()
    )
    # Assert there is only 1 credit (the original credit) and there is no new credit refilled
    assert len(available_credits) == 1
    assert available_credits[0].amount == 1200
