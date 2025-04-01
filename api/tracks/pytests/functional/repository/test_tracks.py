from __future__ import annotations

import datetime
from typing import List
from unittest import mock

import pytest

from models.tracks import ClientTrack, MemberTrack, TrackName
from pytests import factories


class TestTracksRepositoryGetActiveTracks:
    def test_get_active_tracks_correct_org(self, tracks_repository):
        """Test that we only return active tracks for the correct organization"""
        # Given
        expected_org = factories.OrganizationFactory.create()
        another_org = factories.OrganizationFactory.create()
        expected_track = factories.ClientTrackFactory(organization=expected_org)
        factories.ClientTrackFactory(organization=another_org)
        # When
        active_tracks: List[ClientTrack] = tracks_repository.get_active_tracks(
            organization_id=expected_org.id
        )
        # Then
        assert [expected_track] == active_tracks

    def test_get_active_tracks_only_active(self, tracks_repository):
        """Test that we don't return inactive tracks"""
        # Given
        org = factories.OrganizationFactory.create()
        factories.ClientTrackFactory(organization=org, active=False)
        # When
        active_tracks: List[ClientTrack] = tracks_repository.get_active_tracks(
            organization_id=org.id
        )
        # Then
        assert not active_tracks

    def test_get_active_tracks_only_launched(self, tracks_repository):
        """Test that we only return active tracks that are launched"""
        # Given
        org = factories.OrganizationFactory.create()
        launched_track = factories.ClientTrackFactory(
            organization=org,
            active=True,
            launch_date=datetime.date.today() - datetime.timedelta(days=10),
        )
        factories.ClientTrackFactory(
            organization=org,
            active=True,
            launch_date=datetime.date.today() + datetime.timedelta(days=10),
        )

        # When
        active_tracks: List[ClientTrack] = tracks_repository.get_active_tracks(
            organization_id=org.id
        )

        # Then
        assert [launched_track] == active_tracks


class TestTracksRepositoryGetAllEnrolledTracks:
    def test_get_all_enrolled_tracks(self, tracks_repository):
        """Test that by default we only return active tracks"""
        # Given
        org = factories.OrganizationFactory.create()
        client_track_1 = factories.ClientTrackFactory(
            track=TrackName.POSTPARTUM,
            organization=org,
            active=True,
            launch_date=datetime.date.today() - datetime.timedelta(days=10),
        )
        client_track_2 = factories.ClientTrackFactory(
            track=TrackName.GENERAL_WELLNESS,
            organization=org,
            active=True,
            launch_date=datetime.date.today() - datetime.timedelta(days=10),
        )
        member_track = factories.MemberTrackFactory(client_track=client_track_1)
        factories.MemberTrackFactory(
            client_track=client_track_2, user=member_track.user
        )

        # When
        enrolled_tracks: ClientTrack | None = tracks_repository.get_all_enrolled_tracks(
            user_id=member_track.user_id
        )

        # Then
        assert len(enrolled_tracks) == 2

    def test_get_all_enrolled_tracks_exclude_inactive(self, tracks_repository):
        """Test that by default we only return active tracks - exclude inactive tracks"""
        # Given
        org = factories.OrganizationFactory.create()
        client_track_1 = factories.ClientTrackFactory(
            track=TrackName.POSTPARTUM,
            organization=org,
            active=True,
            launch_date=datetime.date.today() - datetime.timedelta(days=10),
        )
        client_track_2 = factories.ClientTrackFactory(
            track=TrackName.GENERAL_WELLNESS,
            organization=org,
            active=False,
            launch_date=datetime.date.today() + datetime.timedelta(days=10),
        )
        member_track = factories.MemberTrackFactory(client_track=client_track_1)
        factories.MemberTrackFactory(
            client_track=client_track_2, user=member_track.user, activated_at=None
        )

        # When
        enrolled_tracks: ClientTrack | None = tracks_repository.get_all_enrolled_tracks(
            user_id=member_track.user_id
        )

        # Then
        assert len(enrolled_tracks) == 1

    def test_get_all_enrolled_tracks_include_inactive(self, tracks_repository):
        """Test that by default we only return active tracks - exclude inactive tracks"""
        # Given
        org = factories.OrganizationFactory.create()
        client_track_1 = factories.ClientTrackFactory(
            track=TrackName.POSTPARTUM,
            organization=org,
            active=True,
            launch_date=datetime.date.today() - datetime.timedelta(days=10),
        )
        client_track_2 = factories.ClientTrackFactory(
            track=TrackName.GENERAL_WELLNESS,
            organization=org,
            active=False,
            launch_date=datetime.date.today() + datetime.timedelta(days=10),
        )
        member_track = factories.MemberTrackFactory(client_track=client_track_1)
        factories.MemberTrackFactory(
            client_track=client_track_2, user=member_track.user
        )

        # When
        enrolled_tracks: ClientTrack | None = tracks_repository.get_all_enrolled_tracks(
            user_id=member_track.user_id, active_only=False
        )

        # Then
        assert len(enrolled_tracks) == 2


class TestTracksRepositoryGetClientTrack:
    def test_get_client_track(self, tracks_repository):
        """Test that we only return active track when the active_only filter is used"""
        # Given
        org = factories.OrganizationFactory.create()
        launched_track_a: ClientTrack = factories.ClientTrackFactory(
            track=TrackName.PREGNANCY,
            organization=org,
            active=True,
            launch_date=datetime.date.today() - datetime.timedelta(days=10),
        )
        factories.ClientTrackFactory(
            track=TrackName.POSTPARTUM,
            organization=org,
            active=True,
            launch_date=datetime.date.today() - datetime.timedelta(days=10),
        )
        factories.ClientTrackFactory(
            track=TrackName.GENERAL_WELLNESS,
            organization=org,
            active=True,
            launch_date=datetime.date.today() + datetime.timedelta(days=10),
        )

        # When
        active_tracks: ClientTrack | None = tracks_repository.get_client_track(
            organization_id=org.id, track=launched_track_a.track
        )

        # Then
        assert launched_track_a == active_tracks

    def test_get_client_track_active_only(self, tracks_repository):
        """Test that we don't return an inactive track when active_only filter is used"""
        # Given
        org = factories.OrganizationFactory.create()
        launched_track_a: ClientTrack = factories.ClientTrackFactory(
            track=TrackName.PREGNANCY,
            organization=org,
            active=False,
            launch_date=datetime.date.today() - datetime.timedelta(days=10),
        )
        factories.ClientTrackFactory(
            track=TrackName.POSTPARTUM,
            organization=org,
            active=False,
            launch_date=datetime.date.today() - datetime.timedelta(days=10),
        )
        factories.ClientTrackFactory(
            track=TrackName.GENERAL_WELLNESS,
            organization=org,
            active=False,
            launch_date=datetime.date.today() + datetime.timedelta(days=10),
        )

        # When
        active_tracks: ClientTrack | None = tracks_repository.get_client_track(
            organization_id=org.id, track=launched_track_a.track, active_only=True
        )

        # Then
        assert active_tracks is None


class TestTracksRepositoryGetEnrolledTracks:
    def test_get_enrolled_tracks(self, tracks_repository):
        """Test that we return the tracks that a user is enrolled in for an organization"""
        # Given
        org = factories.OrganizationFactory.create()
        client_track = factories.ClientTrackFactory(organization=org)
        member_track = factories.MemberTrackFactory(client_track=client_track)
        # When
        enrolled_tracks: List[MemberTrack] = tracks_repository.get_enrolled_tracks(
            user_id=member_track.user.id, organization_id=org.id
        )
        # Then
        assert [member_track] == enrolled_tracks

    def test_get_enrolled_only_active(self, tracks_repository):
        """Test that we don't return enrolled tracks that have already ended"""
        # Given
        uoe = factories.UserOrganizationEmployeeFactory.create()
        org = uoe.organization_employee.organization
        client_track_a = factories.ClientTrackFactory(organization=org)
        client_track_b = factories.ClientTrackFactory(organization=org)
        active_track = factories.MemberTrackFactory(
            user=uoe.user, client_track=client_track_a
        )
        factories.MemberTrackFactory(
            user=uoe.user,
            client_track=client_track_b,
            ended_at=datetime.datetime.today() - datetime.timedelta(days=20),
        )
        # When
        enrolled_tracks: List[MemberTrack] = tracks_repository.get_enrolled_tracks(
            user_id=uoe.user.id, organization_id=org.id
        )
        # Then
        assert [active_track] == enrolled_tracks


class TestTracksRepositoryGetEligibleTracks:
    def test_get_eligible_tracks(self, tracks_repository):
        """Test that we don't fetch the tracks that someone is already enrolled in"""
        # Given
        org = factories.OrganizationFactory.create()
        client_track_enrolled = factories.ClientTrackFactory(
            organization=org, track=TrackName.PREGNANCY
        )
        client_track_expected = factories.ClientTrackFactory(
            organization=org, track=TrackName.PARENTING_AND_PEDIATRICS
        )
        member_track = factories.MemberTrackFactory(client_track=client_track_enrolled)
        # When
        available_tracks: List[ClientTrack] = tracks_repository.get_available_tracks(
            user_id=member_track.user.id, organization_id=org.id
        )
        # Then
        assert [client_track_expected] == available_tracks

    def test_get_eligible_tracks_multi_org(self, tracks_repository):
        """Test that we only get the eligible tracks for the right user/org"""
        # Given
        expected_org = factories.OrganizationFactory.create()
        another_org = factories.OrganizationFactory.create()
        client_track_enrolled = factories.ClientTrackFactory(
            track=TrackName.PREGNANCY,
            organization=expected_org,
        )
        client_track_expected = factories.ClientTrackFactory(
            track=TrackName.PARENTING_AND_PEDIATRICS,
            organization=expected_org,
        )
        factories.ClientTrackFactory(organization=another_org)
        member_track = factories.MemberTrackFactory(client_track=client_track_enrolled)
        # When
        available_tracks: List[ClientTrack] = tracks_repository.get_available_tracks(
            user_id=member_track.user.id, organization_id=expected_org.id
        )
        # Then
        assert [client_track_expected] == available_tracks

    def test_get_all_available_tracks_multi_org(self, tracks_repository):
        """Test that we don't fetch the tracks that someone is already enrolled in"""
        # Given
        org_1 = factories.OrganizationFactory.create()
        client_track_enrolled = factories.ClientTrackFactory(
            organization=org_1, track=TrackName.PREGNANCY
        )
        client_track_expected_1 = factories.ClientTrackFactory(
            organization=org_1, track=TrackName.PARENTING_AND_PEDIATRICS
        )
        org_2 = factories.OrganizationFactory.create()
        client_track_expected_2 = factories.ClientTrackFactory(
            organization=org_2, track=TrackName.PARENTING_AND_PEDIATRICS
        )
        member_track = factories.MemberTrackFactory(client_track=client_track_enrolled)
        with mock.patch(
            "eligibility.service.EnterpriseVerificationService.get_eligible_features_for_user",
            return_value=None,
        ):
            # When
            available_tracks: List[
                ClientTrack
            ] = tracks_repository.get_all_available_tracks(
                user_id=member_track.user.id, organization_ids=[org_1.id, org_2.id]
            )
            # Then
            assert set([client_track_expected_1, client_track_expected_2]) == set(
                available_tracks
            )

    @pytest.mark.skip(reason="Skipping test due to excessive flakiness in CI.")
    def test_get_eligible_tracks_enrolled_and_ended(self, tracks_repository):
        """Test that if someone has already finished a track, they are eligible again for that track"""
        # Given
        uoe = factories.UserOrganizationEmployeeFactory.create()
        org = uoe.organization_employee.organization
        client_track_a = factories.ClientTrackFactory(organization=org)
        client_track_b = factories.ClientTrackFactory(organization=org)
        factories.MemberTrackFactory(
            client_track=client_track_a,
            user=uoe.user,
            ended_at=datetime.datetime.today() - datetime.timedelta(days=2),
        )
        factories.MemberTrackFactory(
            client_track=client_track_b,
            user=uoe.user,
        )
        # When
        available_tracks: List[ClientTrack] = tracks_repository.get_available_tracks(
            user_id=uoe.user.id, organization_id=org.id
        )
        # Then
        assert [client_track_a] == available_tracks

    @pytest.mark.skip(reason="Flaky")
    def test_get_all_available_tracks_enrolled_and_ended(self, tracks_repository):
        """Test that if someone has already finished a track, they are eligible again for that track"""
        # Given
        uoe = factories.UserOrganizationEmployeeFactory.create()
        org_1 = factories.OrganizationFactory.create()
        client_track_a = factories.ClientTrackFactory(
            organization=org_1, track=TrackName.ADOPTION
        )
        client_track_b = factories.ClientTrackFactory(
            organization=org_1, track=TrackName.PREGNANCY
        )
        factories.MemberTrackFactory(
            client_track=client_track_a,
            user=uoe.user,
            ended_at=datetime.datetime.today() - datetime.timedelta(days=2),
        )
        factories.MemberTrackFactory(client_track=client_track_b, user=uoe.user)
        org_2 = factories.OrganizationFactory.create()
        client_track_2 = factories.ClientTrackFactory(
            organization=org_2, track=TrackName.PARENTING_AND_PEDIATRICS
        )
        with mock.patch(
            "eligibility.service.EnterpriseVerificationService.get_eligible_features_for_user",
            return_value=None,
        ):
            # When
            available_tracks: List[
                ClientTrack
            ] = tracks_repository.get_all_available_tracks(
                user_id=uoe.user.id, organization_ids=[org_1.id, org_2.id]
            )
            # Then
            assert set([client_track_a, client_track_2]) == set(available_tracks)

    def test_get_enrolled_tracks_eligible(self, tracks_repository):
        """
        Tests that if the track ID is returned by the e9y utility function, the track will be
        considered eligible.
        """
        # Given
        org = factories.OrganizationFactory.create()
        client_track_enrolled = factories.ClientTrackFactory(
            organization=org, track=TrackName.PREGNANCY
        )
        client_track_expected = factories.ClientTrackFactory(
            organization=org, track=TrackName.POSTPARTUM
        )
        member_track = factories.MemberTrackFactory(client_track=client_track_enrolled)

        # When
        with mock.patch(
            "eligibility.service.EnterpriseVerificationService.get_eligible_features_for_user_and_org"
        ) as mock_get_eligible_features_for_user_and_org:
            mock_get_eligible_features_for_user_and_org.return_value = [
                client_track_expected.id
            ]
            available_tracks: List[
                ClientTrack
            ] = tracks_repository.get_available_tracks(
                user_id=member_track.user.id, organization_id=org.id
            )

        # Then
        assert [client_track_expected] == available_tracks

    def test_get_all_available_tracks_multi_org_with_eligible(self, tracks_repository):
        """Test that we don't fetch the tracks that someone is already enrolled in"""
        # Given
        org_1 = factories.OrganizationFactory.create()
        client_track_enrolled = factories.ClientTrackFactory(
            organization=org_1, track=TrackName.PREGNANCY
        )
        client_track_expected_1 = factories.ClientTrackFactory(
            organization=org_1, track=TrackName.PARENTING_AND_PEDIATRICS
        )
        org_2 = factories.OrganizationFactory.create()
        client_track_expected_2 = factories.ClientTrackFactory(
            organization=org_2, track=TrackName.PARENTING_AND_PEDIATRICS
        )
        member_track = factories.MemberTrackFactory(client_track=client_track_enrolled)
        with mock.patch(
            "eligibility.service.EnterpriseVerificationService.get_eligible_features_for_user",
            return_value=[client_track_expected_1.id, client_track_expected_2.id],
        ):
            # When
            available_tracks: List[
                ClientTrack
            ] = tracks_repository.get_all_available_tracks(
                user_id=member_track.user.id, organization_ids=[org_1.id, org_2.id]
            )
            # Then
            assert set([client_track_expected_1, client_track_expected_2]) == set(
                available_tracks
            )

    def test_get_enrolled_tracks_none_eligible(self, tracks_repository):
        """
        Tests that if no track ID is returned by the e9y utility function, the track will not be
        considered eligible.
        """
        # Given
        org = factories.OrganizationFactory.create()
        client_track_enrolled = factories.ClientTrackFactory(
            organization=org, track=TrackName.PREGNANCY
        )
        # Creating another track that the e9y service will not list as eligible
        factories.ClientTrackFactory(organization=org, track=TrackName.POSTPARTUM)
        member_track = factories.MemberTrackFactory(client_track=client_track_enrolled)

        # When
        with mock.patch(
            "eligibility.service.EnterpriseVerificationService.get_eligible_features_for_user_and_org"
        ) as mock_get_eligible_features_for_user_and_org:
            mock_get_eligible_features_for_user_and_org.return_value = []
            available_tracks: List[
                ClientTrack
            ] = tracks_repository.get_available_tracks(
                user_id=member_track.user.id, organization_id=org.id
            )

        # Then
        assert [] == available_tracks

    def test_get_all_available_tracks_multi_org_without_eligible(
        self, tracks_repository
    ):
        """Test that we don't fetch the tracks that someone is already enrolled in"""
        # Given
        org_1 = factories.OrganizationFactory.create()
        client_track_enrolled = factories.ClientTrackFactory(
            organization=org_1, track=TrackName.PREGNANCY
        )
        factories.ClientTrackFactory(
            organization=org_1, track=TrackName.PARENTING_AND_PEDIATRICS
        )
        org_2 = factories.OrganizationFactory.create()
        factories.ClientTrackFactory(
            organization=org_2, track=TrackName.PARENTING_AND_PEDIATRICS
        )
        member_track = factories.MemberTrackFactory(client_track=client_track_enrolled)
        with mock.patch(
            "eligibility.service.EnterpriseVerificationService.get_eligible_features_for_user",
            return_value=[],
        ):
            # When
            available_tracks: List[
                ClientTrack
            ] = tracks_repository.get_all_available_tracks(
                user_id=member_track.user.id, organization_ids=[org_1.id, org_2.id]
            )
            # Then
            assert [] == available_tracks

    def test_get_enrolled_tracks_no_population(self, tracks_repository):
        """
        Tests that if no population is configured, the track will be considered eligible
        by default.
        """
        # Given
        org = factories.OrganizationFactory.create()
        client_track_enrolled = factories.ClientTrackFactory(
            organization=org, track=TrackName.PREGNANCY
        )
        client_track_expected = factories.ClientTrackFactory(
            organization=org, track=TrackName.POSTPARTUM
        )
        member_track = factories.MemberTrackFactory(client_track=client_track_enrolled)

        # When
        with mock.patch(
            "eligibility.service.EnterpriseVerificationService.get_eligible_features_for_user_and_org"
        ) as mock_get_eligible_features_for_user_and_org:
            mock_get_eligible_features_for_user_and_org.return_value = None
            available_tracks: List[
                ClientTrack
            ] = tracks_repository.get_available_tracks(
                user_id=member_track.user.id, organization_id=org.id
            )

        # Then
        assert [client_track_expected] == available_tracks


class TestTracksRepositoryGetTracksByOrgID:
    def test_get_active_tracks_correct_org(self, tracks_repository):
        """Test we return the user from the target org"""
        # Given
        member_1 = factories.DefaultUserFactory.create(id=111)
        member_2 = factories.DefaultUserFactory.create(id=222)
        member_3 = factories.DefaultUserFactory.create(id=333)
        uoe_1 = factories.UserOrganizationEmployeeFactory.create(user=member_1)
        uoe_2 = factories.UserOrganizationEmployeeFactory.create(user=member_2)
        uoe_3 = factories.UserOrganizationEmployeeFactory.create(user=member_3)
        org_a = factories.OrganizationFactory.create()
        org_b = factories.OrganizationFactory.create()

        client_track_a = factories.ClientTrackFactory(organization=org_a)
        factories.ClientTrackFactory(organization=org_b)
        factories.MemberTrackFactory(user=uoe_1.user, client_track=client_track_a)
        factories.MemberTrackFactory(user=uoe_2.user, client_track=client_track_a)
        factories.MemberTrackFactory(
            client_track=client_track_a,
            user=uoe_3.user,
            ended_at=datetime.datetime.today() - datetime.timedelta(days=2),
        )

        # When
        result = tracks_repository.get_all_users_based_on_org_id(org_id=org_a.id)
        # Then
        assert len(result) == 2
        candidate1 = (111,)
        candidate2 = (222,)
        # if the candidate not in the result, it will throw ValueError
        assert result.index(candidate1) >= 0
        assert result.index(candidate2) >= 0


class TestTrackRepositoryHasWallet:
    def test_has_active_wallet_when_no_ros(self, tracks_repository):
        org = factories.OrganizationFactory.create()
        track = factories.ClientTrackFactory(organization=org)
        assert tracks_repository.has_active_wallet(track) == False

    def test_has_active_wallet_when_active_ros(self, tracks_repository):
        org = factories.OrganizationFactory.create()
        resource = factories.ResourceFactory(id=5)
        factories.ReimbursementOrganizationSettingsFactory.create(
            organization=org,
            benefit_faq_resource_id=resource.id,
            survey_url="fake_url",
        )
        track = factories.ClientTrackFactory(organization=org)
        assert tracks_repository.has_active_wallet(track) == True

    def test_has_active_wallet_when_inactive_ros(self, tracks_repository):
        org = factories.OrganizationFactory.create()
        resource = factories.ResourceFactory(id=5)
        factories.ReimbursementOrganizationSettingsFactory.create(
            organization=org,
            benefit_faq_resource_id=resource.id,
            survey_url="fake_url",
            started_at=datetime.datetime.utcnow() + datetime.timedelta(days=30),
        )
        track = factories.ClientTrackFactory(organization=org)
        assert tracks_repository.has_active_wallet(track) == False
