import datetime
from typing import List
from unittest import mock

import pytest

from eligibility import EnterpriseEligibilitySettings
from eligibility.e9y import EligibilityVerification
from eligibility.pytests import factories as e9y_factories
from models.enterprise import Organization
from models.tracks import ClientTrack, MemberTrack, TrackConfig, TrackName
from pytests import factories
from pytests.factories import OrganizationFactory
from tracks import constants, service
from tracks.service.tracks import OverEligibilityRuleError


class Test_GetEnrollableTracks:
    def test_get_enrollable_tracks_enrolled_in_one_pnp_one_other(self, track_service):
        # Given
        org: Organization = factories.OrganizationFactory.create()
        cts: List[ClientTrack] = [
            factories.ClientTrackFactory.create(
                organization=org, track=TrackName.PREGNANCY
            ),
        ]
        # Enrolled in 1 pnp and 1 non-pnp
        mts: List[MemberTrack] = [
            factories.MemberTrackFactory.create(
                name=TrackName.PARENTING_AND_PEDIATRICS
            ),
            factories.MemberTrackFactory.create(name=TrackName.GENERAL_WELLNESS),
        ]

        # When
        enrollable_tracks: List[ClientTrack] = track_service._get_enrollable_tracks(
            enrolled=mts,
            available=cts,
        )

        # Then
        assert not enrollable_tracks

    def test_get_enrollable_tracks_enrolled_in_one_non_pnp(self, track_service):
        # Given
        org: Organization = factories.OrganizationFactory.create()
        cts: List[ClientTrack] = [
            factories.ClientTrackFactory.create(
                organization=org, track=TrackName.PARENTING_AND_PEDIATRICS
            ),
            factories.ClientTrackFactory.create(
                organization=org, track=TrackName.PREGNANCY
            ),
        ]
        mts: List[MemberTrack] = [
            factories.MemberTrackFactory.create(name=TrackName.GENERAL_WELLNESS),
        ]

        # When
        enrollable_tracks: List[ClientTrack] = track_service._get_enrollable_tracks(
            enrolled=mts,
            available=cts,
        )

        assert (
            len(enrollable_tracks) == 1
            and enrollable_tracks[0].name == TrackName.PARENTING_AND_PEDIATRICS
        )

    def test_get_enrollable_tracks_enrolled_in_pnp(self, track_service):
        # Given
        org: Organization = factories.OrganizationFactory.create()
        cts: List[ClientTrack] = [
            factories.ClientTrackFactory.create(
                organization=org, track=TrackName.GENERAL_WELLNESS
            ),
            factories.ClientTrackFactory.create(
                organization=org, track=TrackName.PREGNANCY
            ),
        ]
        # Enrolled in pnp only
        mts: List[MemberTrack] = [
            factories.MemberTrackFactory.create(
                name=TrackName.PARENTING_AND_PEDIATRICS
            ),
        ]

        # When
        enrollable_tracks: List[ClientTrack] = track_service._get_enrollable_tracks(
            enrolled=mts,
            available=cts,
        )

        assert len(enrollable_tracks) == len(cts)


class TestGetEnrollableTracksForVerification:
    @mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_org_e9y_settings"
    )
    @mock.patch("tracks.repository.MemberTrackRepository.get_active_tracks")
    def test_get_enrollable_tracks_for_verification_calls_get_active_tracks(
        self, mock_get_active_tracks, mock_get_org_e9y_settings, track_service
    ):
        # Given
        v: EligibilityVerification = e9y_factories.VerificationFactory()
        e9y_settings: EnterpriseEligibilitySettings = (
            e9y_factories.EnterpriseEligibilitySettingsFactory()
        )
        mock_get_org_e9y_settings.return_value = e9y_settings

        # When
        track_service.get_enrollable_tracks_for_verification(verification=v)

        # Then
        mock_get_active_tracks.assert_called_once_with(
            user_id=v.user_id,
        )

    @mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_org_e9y_settings"
    )
    @mock.patch("tracks.repository.TracksRepository.get_available_tracks")
    def test_get_enrollable_tracks_for_verification_calls_get_available_tracks(
        self, mock_get_available_tracks, mock_get_org_e9y_settings, track_service
    ):
        # Given
        v: EligibilityVerification = e9y_factories.VerificationFactory()
        e9y_settings: EnterpriseEligibilitySettings = (
            e9y_factories.EnterpriseEligibilitySettingsFactory()
        )
        mock_get_org_e9y_settings.return_value = e9y_settings

        # When
        track_service.get_enrollable_tracks_for_verification(verification=v)

        # Then
        mock_get_available_tracks.assert_called_once_with(
            user_id=v.user_id, organization_id=v.organization_id
        )

    @mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_org_e9y_settings"
    )
    @mock.patch("tracks.service.TrackSelectionService._get_enrollable_tracks")
    def test_get_enrollable_tracks_for_verification_calls_get_enrollable_tracks(
        self, mock_get_enrollable_tracks, mock_get_org_e9y_settings, track_service
    ):
        # Given
        v: EligibilityVerification = e9y_factories.VerificationFactory()
        e9y_settings: EnterpriseEligibilitySettings = (
            e9y_factories.EnterpriseEligibilitySettingsFactory()
        )
        mock_get_org_e9y_settings.return_value = e9y_settings

        # When
        track_service.get_enrollable_tracks_for_verification(verification=v)

        # Then
        mock_get_enrollable_tracks.assert_called()

    def test_get_enrollable_tracks_for_verification_raises_exception_when_missing_verification(
        self, track_service
    ):
        # Given
        verification = None

        # When Then
        with pytest.raises(ValueError):
            track_service.get_enrollable_tracks_for_verification(
                verification=verification
            )


class TestGetEnrollableTracksForOrg:
    @mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
    )
    def test_get_enrollable_tracks_for_org_no_verifications(
        self, mock_get_verification_for_user_and_org, track_service
    ):
        # Given
        mock_get_verification_for_user_and_org.return_value = None

        # When
        tracks: List[ClientTrack] = track_service.get_enrollable_tracks_for_org(
            user_id=1, organization_id=10
        )

        # Then
        assert not tracks

    @mock.patch(
        "tracks.service.TrackSelectionService.get_enrollable_tracks_for_verification"
    )
    @mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
    )
    def test_get_enrollable_tracks_for_org_calls_get_enrollable_tracks_for_verification(
        self,
        mock_get_verification_for_user_and_org,
        mock_get_enrollable_tracks_for_verification,
        mock_valid_verification,
        track_service,
    ):
        # Given
        verification: EligibilityVerification = mock_valid_verification
        mock_get_verification_for_user_and_org.return_value = mock_valid_verification

        # When
        track_service.get_enrollable_tracks_for_org(
            user_id=1, organization_id=verification.organization_id
        )

        # Then
        mock_get_enrollable_tracks_for_verification.assert_called_once_with(
            verification=verification
        )

    @mock.patch(
        "tracks.service.TrackSelectionService.get_enrollable_tracks_for_verification"
    )
    @mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
    )
    def test_get_enrollable_tracks_for_user_calls_get_enrollable_tracks_for_verification(
        self,
        mock_get_verification_for_user_and_org,
        mock_get_enrollable_tracks_for_verification,
        mock_valid_verification,
        track_service,
    ):
        # Given
        verification: EligibilityVerification = mock_valid_verification
        mock_get_verification_for_user_and_org.return_value = verification

        # When
        track_service.get_enrollable_tracks_for_org(
            user_id=1, organization_id=verification.organization_id
        )

        # Then
        mock_get_enrollable_tracks_for_verification.assert_called_once_with(
            verification=verification
        )


class TestGetOrderedRecommendedTracks:
    def test_get_ordered_recommended_tracks_returns_expected_order(
        self, all_client_tracks
    ):
        ordered_tracks = service.TrackSelectionService._get_ordered_recommended_tracks(
            previous_track=TrackName.ADOPTION, enrollable_tracks=all_client_tracks
        )

        expected_order = constants.ORDERED_TRACK_RECOMMENDATIONS[TrackName.ADOPTION]

        for i, expected_track in enumerate(expected_order):
            assert ordered_tracks[i].name == expected_track

    def test_get_ordered_recommended_tracks_for_all_tracks(self, all_client_tracks):
        for track in TrackName:
            assert (
                service.TrackSelectionService._get_ordered_recommended_tracks(
                    previous_track=track, enrollable_tracks=all_client_tracks
                )
                is not None
            )

    def test_get_ordered_recommended_tracks_for_track_without_ordering(
        self, all_client_tracks
    ):
        ordered_tracks = service.TrackSelectionService._get_ordered_recommended_tracks(
            previous_track=TrackName.SPONSORED, enrollable_tracks=all_client_tracks
        )

        expected = [TrackConfig.from_name(t.name) for t in all_client_tracks]

        assert ordered_tracks == expected

    @pytest.mark.parametrize(
        "track_name,tracks_to_omit",
        [
            (TrackName.POSTPARTUM, [TrackName.POSTPARTUM]),
            (TrackName.PARTNER_NEWPARENT, [TrackName.POSTPARTUM]),
        ],
    )
    def test_get_ordered_recommended_tracks_omits_tracks(
        self, all_client_tracks, track_name, tracks_to_omit
    ):
        ordered_tracks = service.TrackSelectionService._get_ordered_recommended_tracks(
            previous_track=track_name, enrollable_tracks=all_client_tracks
        )

        omitted_tracks = [t for t in ordered_tracks if t.name in ordered_tracks]

        assert len(omitted_tracks) == 0


class TestGetUpdatedTrackDescription:
    @pytest.mark.parametrize(
        "track_name,track_length,expect_default_description",
        [
            (TrackName.POSTPARTUM, 90, False),
            (TrackName.POSTPARTUM, 168, False),
            (TrackName.POSTPARTUM, 348, True),
            (TrackName.PARTNER_NEWPARENT, 90, False),
            (TrackName.PARTNER_NEWPARENT, 168, False),
            (TrackName.PARTNER_NEWPARENT, 348, True),
            (TrackName.GENERAL_WELLNESS, 90, True),
            (TrackName.GENERAL_WELLNESS, 168, True),
            (TrackName.GENERAL_WELLNESS, 348, True),
        ],
    )
    @mock.patch("tracks.service.TrackSelectionService._get_track_length")
    def test_get_updated_track_description_updates_track_description(
        self,
        mock_get_track_length,
        track_service,
        track_name,
        track_length,
        expect_default_description,
    ):
        mock_get_track_length.return_value = track_length
        v: EligibilityVerification = e9y_factories.VerificationFactory()
        track_description = TrackConfig.from_name(track_name).description
        updated_description = track_service.get_updated_track_description(
            user_id=v.user_id,
            organization_id=v.organization_id,
            track_description=track_description,
            track_name=track_name,
        )

        if expect_default_description:
            assert updated_description == track_description
        else:
            assert updated_description != track_description

    @pytest.mark.parametrize(
        "track_name,should_call",
        [
            (TrackName.POSTPARTUM, True),
            (TrackName.PARTNER_NEWPARENT, True),
            (TrackName.ADOPTION, False),
        ],
    )
    @mock.patch("tracks.repository.TracksRepository.get_client_track")
    def test_get_updated_track_description_calls_get_client_track(
        self, mock_get_client_track, track_service, track_name, should_call
    ):
        v: EligibilityVerification = e9y_factories.VerificationFactory()
        track_service.get_updated_track_description(
            user_id=v.user_id,
            organization_id=v.organization_id,
            track_description="mocked_track_description",
            track_name=track_name,
        )

        if should_call:
            mock_get_client_track.assert_called_once_with(
                organization_id=v.organization_id, track=track_name
            )
        else:
            mock_get_client_track.assert_not_called()


class TestIsEnterprise:
    @pytest.mark.parametrize(
        argnames="tracks,expected_is_enterprise",
        argvalues=[
            (["track1", "track2"], True),
            ([], False),
        ],
        ids=["tracks", "no_tracks"],
    )
    @mock.patch("tracks.repository.MemberTrackRepository.get_active_tracks")
    def test_is_enterprise(
        self,
        mock_get_active_tracks,
        track_service,
        tracks,
        expected_is_enterprise,
    ):
        # Given
        mock_get_active_tracks.return_value = tracks

        # When
        is_enterprise: bool = track_service.is_enterprise(user_id=1)

        # Then
        assert is_enterprise is expected_is_enterprise


class TestGetOrganizationForUser:
    def test_get_organization_single_active_track(self, track_service):
        # Given
        org: Organization = factories.OrganizationFactory.create()
        client_track = factories.ClientTrackFactory.create(
            organization=org, track=TrackName.PREGNANCY
        )
        member_track = factories.MemberTrackFactory.create(
            name=TrackName.PARENTING_AND_PEDIATRICS, client_track=client_track
        )

        # When
        organization_id = track_service.get_organization_id_for_user(
            user_id=member_track.user_id
        )
        organization = track_service.get_organization_for_user(
            user_id=member_track.user_id
        )
        org_id_via_active = (
            track_service.get_organization_id_for_user_via_active_tracks(
                user_id=member_track.user_id
            )
        )
        # Then
        assert organization_id == org.id
        assert organization == org
        assert org_id_via_active == org.id

    def test_get_organization_multiple_orgs(self, track_service):
        # Given
        org: Organization = factories.OrganizationFactory.create()
        org_2: Organization = factories.OrganizationFactory.create()
        client_track_org_1 = factories.ClientTrackFactory.create(
            organization=org, track=TrackName.PREGNANCY
        )
        client_track_org_2 = factories.ClientTrackFactory.create(
            organization=org_2, track=TrackName.PARENTING_AND_PEDIATRICS
        )
        member_track = factories.MemberTrackFactory.create(
            name=TrackName.PREGNANCY, client_track=client_track_org_1
        )
        factories.MemberTrackFactory.create(
            name=TrackName.PARENTING_AND_PEDIATRICS,
            client_track=client_track_org_2,
            user=member_track.user,
        )

        # When
        organization_id = track_service.get_organization_id_for_user(
            user_id=member_track.user_id
        )
        organization = track_service.get_organization_for_user(
            user_id=member_track.user_id
        )
        org_id_via_active = (
            track_service.get_organization_id_for_user_via_active_tracks(
                user_id=member_track.user_id
            )
        )
        # Then
        assert organization_id in [org.id, org_2.id]
        assert organization in [org, org_2]
        assert org_id_via_active in [org.id, org_2.id]

    def test_get_organization_single_inactive_track(self, track_service):
        # Given
        org: Organization = factories.OrganizationFactory.create()
        client_track = factories.ClientTrackFactory.create(
            organization=org,
            track=TrackName.PREGNANCY,
            active=False,
            launch_date=datetime.date.today() + datetime.timedelta(days=10),
        )
        member_track = factories.MemberTrackFactory.create(
            name=TrackName.PARENTING_AND_PEDIATRICS,
            client_track=client_track,
            activated_at=None,
        )

        # When
        organization_id = track_service.get_organization_id_for_user(
            user_id=member_track.user_id
        )
        organization = track_service.get_organization_for_user(
            user_id=member_track.user_id
        )
        org_id_via_active = (
            track_service.get_organization_id_for_user_via_active_tracks(
                user_id=member_track.user_id
            )
        )

        # Then
        assert organization_id == org.id
        assert organization == org
        assert org_id_via_active is None

    def test_get_organization_multiple_orgs_inactive(self, track_service):
        # Given
        org: Organization = factories.OrganizationFactory.create()
        org_2: Organization = factories.OrganizationFactory.create()
        client_track_org_1 = factories.ClientTrackFactory.create(
            organization=org,
            track=TrackName.PREGNANCY,
            active=False,
            launch_date=datetime.date.today() + datetime.timedelta(days=10),
        )
        client_track_org_2 = factories.ClientTrackFactory.create(
            organization=org_2,
            track=TrackName.PARENTING_AND_PEDIATRICS,
            active=False,
            launch_date=datetime.date.today() + datetime.timedelta(days=10),
        )
        member_track = factories.MemberTrackFactory.create(
            name=TrackName.PREGNANCY, client_track=client_track_org_1, activated_at=None
        )
        factories.MemberTrackFactory.create(
            name=TrackName.PARENTING_AND_PEDIATRICS,
            client_track=client_track_org_2,
            user=member_track.user,
            activated_at=None,
        )

        # When
        organization_id = track_service.get_organization_id_for_user(
            user_id=member_track.user_id
        )
        org_id_via_active = (
            track_service.get_organization_id_for_user_via_active_tracks(
                user_id=member_track.user_id
            )
        )

        # Then
        assert organization_id in [org.id, org_2.id]
        assert org_id_via_active is None

    def test_get_organization_no_tracks(self, track_service):
        # Given
        user = factories.DefaultUserFactory.create()

        # When
        organization_id = track_service.get_organization_id_for_user(user_id=user.id)
        org_id_via_active = (
            track_service.get_organization_id_for_user_via_active_tracks(
                user_id=user.id
            )
        )

        # Then
        assert organization_id is None
        assert org_id_via_active is None


class TestIsEligibleForIntroAppointment:
    @pytest.mark.parametrize(
        argnames="track_name,track_eligible",
        argvalues=[
            ("pregnancy", True),
            ("menopause", True),
            ("postpartum", True),
            ("adoption", True),
            ("egg_freezing", True),
            ("fertility", True),
            ("surrogacy", True),
            ("trying_to_conceive", True),
            ("pregnancyloss", True),
            ("general_wellness", False),
            ("generic", False),
            ("parenting_and_pediatrics", False),
            ("pregnancy_options", False),
            ("sponsored", False),
            ("breast_milk_shipping", False),
            ("partner_fertility", False),
            ("partner_newparent", False),
            ("partner_pregnant", False),
        ],
    )
    def test__is_eligible_for_intro_appointment(
        self, track_name, track_eligible, track_service, mock_intro_appointment_flag
    ):
        # When
        mock_intro_appointment_flag(
            "pregnancy, menopause, postpartum, fertility, pregnancyloss, trying_to_conceive, egg_freezing, adoption, surrogacy"
        )
        is_eligible = track_service._is_eligible_for_intro_appointment(
            track_name=track_name
        )

        # Then
        assert is_eligible == track_eligible


class TestAnyEligibleForIntroAppointment:
    @pytest.mark.parametrize(
        argnames="track_names, checking_one_track_is_enough, track_eligible",
        argvalues=[
            (["pregnancy", "menopause"], True, True),
            (["pregnancy", "general_wellness"], True, True),
            (["general_wellness", "pregnancy"], False, True),
            (["general_wellness", "generic"], False, False),
        ],
    )
    @mock.patch(
        "tracks.service.tracks.TrackSelectionService._is_eligible_for_intro_appointment"
    )
    def test_any_eligible_for_intro_appointment(
        self,
        mock_is_eligible_for_intro_appointment,
        track_names,
        checking_one_track_is_enough,
        track_eligible,
        track_service,
        mock_intro_appointment_flag,
    ):
        # Given
        mock_intro_appointment_flag(
            "pregnancy, menopause, postpartum, fertility, pregnancyloss, trying_to_conceive, egg_freezing, adoption, surrogacy"
        )
        if checking_one_track_is_enough:
            mock_is_eligible_for_intro_appointment.return_value = track_eligible
        else:
            mock_is_eligible_for_intro_appointment.side_effect = [False, track_eligible]

        # When
        is_eligible = track_service.any_eligible_for_intro_appointment(
            track_names=track_names
        )

        # Then
        assert is_eligible == track_eligible
        if checking_one_track_is_enough:
            mock_is_eligible_for_intro_appointment.assert_called_once_with(
                track_name=track_names[0]
            )
        else:
            mock_is_eligible_for_intro_appointment.assert_has_calls(
                [
                    mock.call(track_name=track_names[0]),
                    mock.call(track_name=track_names[1]),
                ]
            )


class TestGetHighestPriorityTrack:
    def test_get_highest_priority_track__no_tracks(self, track_service):
        assert not track_service.get_highest_priority_track([])

    def test_get_highest_priority_track__one_track(self, track_service):
        # Given one track
        member = factories.EnterpriseUserFactory.create(
            tracks__name=TrackName.PREGNANCY,
            enabled_tracks=[TrackName.PREGNANCY],
        )

        track = factories.MemberTrackFactory.create(
            user=member,
            name=TrackName.PREGNANCY,
        )
        # When
        highest_priority_track = track_service.get_highest_priority_track([track])
        # Then
        assert highest_priority_track == track

    def test_get_highest_priority_track__three_tracks(self, track_service):
        # Given 3 tracks
        member = factories.EnterpriseUserFactory.create(
            tracks__name=TrackName.PREGNANCY,
            enabled_tracks=[TrackName.PREGNANCY],
        )
        track1 = factories.MemberTrackFactory.create(
            user=member,
            name=TrackName.PARENTING_AND_PEDIATRICS,
        )
        track2 = factories.MemberTrackFactory.create(
            user=member,
            name=TrackName.GENERAL_WELLNESS,
        )
        track3 = factories.MemberTrackFactory.create(
            user=member,
            name=TrackName.PREGNANCY,
        )
        # When
        highest_priority_track = track_service.get_highest_priority_track(
            [track1, track2, track3]
        )
        # Then
        assert highest_priority_track == track3


class TestGetUsersByOrg:
    def test_get_active_users_by_org_id(self, track_service):
        # Given
        member_1 = factories.DefaultUserFactory.create(id=111)
        member_2 = factories.DefaultUserFactory.create(id=222)
        member_3 = factories.DefaultUserFactory.create(id=333)
        uoe_1 = factories.UserOrganizationEmployeeFactory.create(user=member_1)
        uoe_2 = factories.UserOrganizationEmployeeFactory.create(user=member_2)
        uoe_3 = factories.UserOrganizationEmployeeFactory.create(user=member_3)
        org_a = factories.OrganizationFactory.create()

        client_track_a = factories.ClientTrackFactory(organization=org_a)
        factories.MemberTrackFactory(user=uoe_1.user, client_track=client_track_a)
        factories.MemberTrackFactory(user=uoe_2.user, client_track=client_track_a)
        factories.MemberTrackFactory(
            client_track=client_track_a,
            user=uoe_3.user,
            ended_at=datetime.datetime.today() - datetime.timedelta(days=2),
        )
        # When
        result = track_service.get_users_by_org_id(org_id=org_a.id)
        # Then
        assert len(result) == 2
        candidate1 = (111,)
        candidate2 = (222,)
        # if the candidate not in the result, it will throw ValueError
        assert result.index(candidate1) >= 0
        assert result.index(candidate2) >= 0

    def test_get_deactivate_users_by_org_id(self, track_service):
        # Given
        member_1 = factories.DefaultUserFactory.create(id=1111)
        uoe_1 = factories.UserOrganizationEmployeeFactory.create(user=member_1)
        org_a = factories.OrganizationFactory.create()

        client_track_a = factories.ClientTrackFactory(organization=org_a)

        factories.MemberTrackFactory(
            client_track=client_track_a,
            user=uoe_1.user,
            ended_at=datetime.datetime.today() - datetime.timedelta(days=2),
        )
        # When
        result = track_service.get_users_by_org_id(org_id=org_a.id)
        # Then
        assert len(result) == 0

    def test_get_no_users_by_org_id(self, track_service):
        # Given
        org_a = factories.OrganizationFactory.create()
        factories.ClientTrackFactory(organization=org_a)
        # When
        result = track_service.get_users_by_org_id(org_id=org_a.id)
        # Then
        assert len(result) == 0


def test_available_tracks_when_pnp_not_enabled(factories, track_service):
    user = factories.DefaultUserFactory.create()
    client_track = factories.ClientTrackFactory(track=TrackName.PREGNANCY)
    mts: List[MemberTrack] = [
        factories.MemberTrackFactory.create(user=user, client_track=client_track),
    ]
    cts: List[ClientTrack] = [client_track]

    assert (
        len(
            track_service._get_enrollable_tracks(
                enrolled=mts,
                available=cts,
            )
        )
        == 0
    )


@pytest.mark.parametrize(
    argnames="active_track_names,expected_available_tracks",
    argvalues=[
        (
            [
                TrackName.PARENTING_AND_PEDIATRICS,
                TrackName.PREGNANCY,
                TrackName.POSTPARTUM,
                TrackName.FERTILITY,
            ],
            [],
        ),
        ([TrackName.PREGNANCY], [TrackName.PARENTING_AND_PEDIATRICS]),
        (
            [TrackName.PARENTING_AND_PEDIATRICS],
            [TrackName.PREGNANCY, TrackName.POSTPARTUM, TrackName.FERTILITY],
        ),
        ([TrackName.PREGNANCY, TrackName.PARENTING_AND_PEDIATRICS], []),
    ],
    ids=[
        "With no active tracks, all allowed tracks are available",
        "With a non-P&P track, P&P is available",
        "With a P&P track, all non-P&P tracks available",
        "With multitrack, no tracks available",
    ],
)
def test_available_tracks_when_pnp_enabled(
    active_track_names, expected_available_tracks, factories, track_service
):
    user = factories.DefaultUserFactory.create()
    allowed_tracks = [
        TrackName.PARENTING_AND_PEDIATRICS,
        TrackName.PREGNANCY,
        TrackName.POSTPARTUM,
        TrackName.FERTILITY,
    ]
    org = OrganizationFactory.create(allowed_tracks=allowed_tracks)
    emp = factories.OrganizationEmployeeFactory.create(organization=org)
    client_tracks = {}
    for track_name in allowed_tracks:
        track = factories.ClientTrackFactory.create(organization=org, track=track_name)
        client_tracks[track_name] = track

    for track_name in active_track_names:
        factories.MemberTrackFactory.create(
            user=user,
            name=track_name,
            client_track=client_tracks[track_name],
        )
    verification = e9y_factories.build_verification_from_oe(
        user_id=user.id, employee=emp
    )
    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ), mock.patch(
        "eligibility.service.EnterpriseVerificationService.is_verification_active",
        return_value=True,
    ):
        available_tracks = track_service.get_enrollable_tracks_for_org(
            user_id=user.id, organization_id=emp.organization.id
        )
        available_names = [t.name for t in available_tracks]
        assert set(available_names) == set(expected_available_tracks)


class TestOverEligibilityRule:
    @staticmethod
    def test_filter_by_wallet_when_empty():
        res = service.tracks.OverEligibilityRule.filter_by_wallet([])
        assert res == []

    @staticmethod
    def test_filter_by_wallet_when_only_1_track():
        track = factories.ClientTrackFactory.create()
        res = service.tracks.OverEligibilityRule.filter_by_wallet([track])
        assert res == [track]

    @staticmethod
    def test_filter_by_wallet_when_1_has_wallet():
        track_a = factories.ClientTrackFactory.create()
        track_b = factories.ClientTrackFactory.create()
        track_c = factories.ClientTrackFactory.create()

        def mock_has_wallet(track: ClientTrack):
            return track_b == track

        with mock.patch(
            "tracks.service.tracks.OverEligibilityRule.has_active_wallet",
        ) as mock_call:
            mock_call.side_effect = mock_has_wallet
            res = service.tracks.OverEligibilityRule.filter_by_wallet(
                [track_a, track_b, track_c]
            )
        assert res == [track_b]

    @staticmethod
    def test_filter_by_wallet_when_1plus_has_wallet():
        track_a = factories.ClientTrackFactory.create()
        track_b = factories.ClientTrackFactory.create()
        track_c = factories.ClientTrackFactory.create()
        track_d = factories.ClientTrackFactory.create()

        def mock_has_wallet(track: ClientTrack):
            return track_b == track or track_d == track

        with mock.patch(
            "tracks.service.tracks.OverEligibilityRule.has_active_wallet",
        ) as mock_call:
            mock_call.side_effect = mock_has_wallet
            res = service.tracks.OverEligibilityRule.filter_by_wallet(
                [track_a, track_b, track_c, track_d]
            )
        assert set(res) == set([track_b, track_d])

    @staticmethod
    def test_filter_by_wallet_when_none_has_wallet():
        track_a = factories.ClientTrackFactory.create()
        track_b = factories.ClientTrackFactory.create()
        track_c = factories.ClientTrackFactory.create()

        with mock.patch(
            "tracks.service.tracks.OverEligibilityRule.has_active_wallet",
            return_value=False,
        ):
            res = service.tracks.OverEligibilityRule.filter_by_wallet(
                [track_a, track_b, track_c]
            )
        assert set(res) == set([track_a, track_b, track_c])

    @staticmethod
    def test_filter_by_wallet_when_all_has_wallet():
        track_a = factories.ClientTrackFactory.create()
        track_b = factories.ClientTrackFactory.create()
        track_c = factories.ClientTrackFactory.create()

        with mock.patch(
            "tracks.service.tracks.OverEligibilityRule.has_active_wallet",
            return_value=True,
        ):
            res = service.tracks.OverEligibilityRule.filter_by_wallet(
                [track_a, track_b, track_c]
            )
        assert set(res) == set([track_a, track_b, track_c])

    @staticmethod
    def test_filter_by_track_length_when_empty():
        res = service.tracks.OverEligibilityRule.filter_by_track_length([])
        assert res == []

    @staticmethod
    def test_filter_by_track_length_when_only_1_track():
        track = factories.ClientTrackFactory.create()
        res = service.tracks.OverEligibilityRule.filter_by_track_length([track])
        assert res == [track]

    @staticmethod
    def test_filter_by_track_length_when_1_max_length_track():
        track_a = factories.ClientTrackFactory.create(
            length_in_days=100,
        )
        track_b = factories.ClientTrackFactory.create(
            length_in_days=100,
        )
        track_c = factories.ClientTrackFactory.create(
            length_in_days=101,
        )
        res = service.tracks.OverEligibilityRule.filter_by_track_length(
            [track_a, track_b, track_c]
        )
        assert res == [track_c]

    @staticmethod
    def test_filter_by_track_length_when_1plus_max_length_tracks():
        track_a = factories.ClientTrackFactory.create(
            length_in_days=100,
        )
        track_b = factories.ClientTrackFactory.create(
            length_in_days=101,
        )
        track_c = factories.ClientTrackFactory.create(
            length_in_days=100,
        )
        track_d = factories.ClientTrackFactory.create(
            length_in_days=101,
        )
        res = service.tracks.OverEligibilityRule.filter_by_track_length(
            [track_a, track_b, track_c, track_d]
        )
        assert set(res) == set([track_b, track_d])

    ###

    @staticmethod
    def test_filter_by_number_of_active_tracks_when_empty():
        res = service.tracks.OverEligibilityRule.filter_by_number_of_active_tracks([])
        assert res == []

    @staticmethod
    def test_filter_by_number_of_active_tracks_when_only_1_track():
        track = factories.ClientTrackFactory.create()
        res = service.tracks.OverEligibilityRule.filter_by_number_of_active_tracks(
            [track]
        )
        assert res == [track]

    @staticmethod
    def test_filter_by_number_of_active_tracks_when_1_max_track():
        track_a = factories.ClientTrackFactory.create()
        track_b = factories.ClientTrackFactory.create()
        track_c = factories.ClientTrackFactory.create()

        def mock_number_of_active_tracks(track: ClientTrack):
            if track == track_b:
                return 2
            else:
                return 1

        with mock.patch(
            "tracks.service.tracks.OverEligibilityRule.get_number_of_active_tracks"
        ) as mock_call:
            mock_call.side_effect = mock_number_of_active_tracks

            res = service.tracks.OverEligibilityRule.filter_by_number_of_active_tracks(
                [track_a, track_b, track_c]
            )
            assert res == [track_b]

    @staticmethod
    def test_filter_by_number_of_active_tracks_when_1plus_max_tracks():
        track_a = factories.ClientTrackFactory.create()
        track_b = factories.ClientTrackFactory.create()
        track_c = factories.ClientTrackFactory.create()

        def mock_number_of_active_tracks(track: ClientTrack):
            if track == track_a or track == track_c:
                return 2
            else:
                return 1

        with mock.patch(
            "tracks.service.tracks.OverEligibilityRule.get_number_of_active_tracks"
        ) as mock_call:
            mock_call.side_effect = mock_number_of_active_tracks

            res = service.tracks.OverEligibilityRule.filter_by_number_of_active_tracks(
                [track_a, track_b, track_c]
            )
        assert set(res) == set([track_c, track_a])

    @staticmethod
    def test_filter_by_organization_id_when_empty():
        res = service.tracks.OverEligibilityRule.filter_by_organization_id([])
        assert res == []

    @staticmethod
    def test_filter_by_organization_id_when_only_1_track():
        track = factories.ClientTrackFactory.create()
        res = service.tracks.OverEligibilityRule.filter_by_organization_id([track])
        assert res == [track]

    @staticmethod
    def test_filter_by_organization_id_when_1_max_created_at():
        org_a = factories.OrganizationFactory.create()
        track_a = factories.ClientTrackFactory.create(
            organization=org_a,
        )
        org_b = factories.OrganizationFactory.create(id=org_a.id + 1)
        track_b = factories.ClientTrackFactory.create(
            organization=org_b,
        )
        org_c = factories.OrganizationFactory.create(id=org_b.id + 1)
        track_c = factories.ClientTrackFactory.create(
            organization=org_c,
        )
        res = service.tracks.OverEligibilityRule.filter_by_organization_id(
            [track_a, track_b, track_c]
        )
        assert res == [track_c]

    @staticmethod
    @pytest.mark.parametrize("repo_val", [True, False])
    def test_has_wallet_call_repo(repo_val):
        track = factories.ClientTrackFactory.create()
        with mock.patch(
            "tracks.repository.TracksRepository.has_active_wallet",
            return_value=repo_val,
        ):
            res = service.tracks.OverEligibilityRule.has_active_wallet(track)
            assert res == repo_val

    @staticmethod
    def test_get_number_of_active_tracks():
        track_a = factories.ClientTrackFactory.create()
        track_b = factories.ClientTrackFactory.create(organization=track_a.organization)
        with mock.patch(
            "tracks.repository.TracksRepository.get_active_tracks",
            return_value=[track_a, track_b],
        ):
            res = service.tracks.OverEligibilityRule.get_number_of_active_tracks(
                track_a
            )
        assert res == 2


class TestApplyOverEligibilityRules:
    @staticmethod
    def test_apply_over_eligibility_rules_when_1_track(track_service):
        track = factories.ClientTrackFactory.create()
        res = track_service._apply_over_eligibility_rules([track])
        assert res == [track]

    @staticmethod
    def test_apply_over_eligibility_rules_when_1v1_track(track_service):
        org_1 = factories.OrganizationFactory.create()
        org_2 = factories.OrganizationFactory.create()
        track_a = factories.ClientTrackFactory.create(
            track=TrackName.ADOPTION,
            organization=org_1,
        )
        track_b = factories.ClientTrackFactory.create(
            track=TrackName.BREAST_MILK_SHIPPING,
            organization=org_2,
        )

        res = track_service._apply_over_eligibility_rules([track_a, track_b])
        assert set(res) == set([track_a, track_b])

    @staticmethod
    def test_apply_over_eligibility_rules_when_1vx_track(track_service):
        org_1 = factories.OrganizationFactory.create()
        org_2 = factories.OrganizationFactory.create()
        org_3 = factories.OrganizationFactory.create()
        org_4 = factories.OrganizationFactory.create()
        org_5 = factories.OrganizationFactory.create()
        track_a = factories.ClientTrackFactory.create(
            track=TrackName.ADOPTION,
            organization=org_1,
        )
        track_b = factories.ClientTrackFactory.create(
            track=TrackName.ADOPTION,
            organization=org_2,
        )
        track_c = factories.ClientTrackFactory.create(
            track=TrackName.ADOPTION,
            organization=org_3,
        )
        track_d = factories.ClientTrackFactory.create(
            track=TrackName.ADOPTION,
            organization=org_4,
        )
        track_e = factories.ClientTrackFactory.create(
            track=TrackName.ADOPTION,
            organization=org_5,
        )
        tracks_a_e = [track_a, track_b, track_c, track_d, track_e]
        tracks_b_e = [track_b, track_c, track_d, track_e]
        tracks_c_e = [track_c, track_d, track_e]
        tracks_d_e = [track_d, track_e]
        with mock.patch(
            "tracks.service.tracks.OverEligibilityRule.filter_by_wallet",
            return_value=tracks_b_e,
        ) as mock_filter_by_wallet, mock.patch(
            "tracks.service.tracks.OverEligibilityRule.filter_by_track_length",
            return_value=tracks_c_e,
        ) as mock_filter_by_track_length, mock.patch(
            "tracks.service.tracks.OverEligibilityRule.filter_by_number_of_active_tracks",
            return_value=tracks_d_e,
        ) as mock_filter_by_number_of_active_tracks, mock.patch(
            "tracks.service.tracks.OverEligibilityRule.filter_by_organization_id",
            return_value=[track_e],
        ) as mock_filter_by_organization_id:
            res = track_service._apply_over_eligibility_rules(tracks_a_e)
            assert res == [track_e]
            mock_filter_by_wallet.assert_called_once()
            assert set(mock_filter_by_wallet.call_args[0][0]) == set(tracks_a_e)
            mock_filter_by_track_length.assert_called_once_with(tracks_b_e)
            mock_filter_by_number_of_active_tracks.assert_called_once_with(tracks_c_e)
            mock_filter_by_organization_id.assert_called_once_with(tracks_d_e)

    @staticmethod
    def test_apply_over_eligibility_rules_when_exception(track_service):
        org_1 = factories.OrganizationFactory.create()
        org_2 = factories.OrganizationFactory.create()
        track_a = factories.ClientTrackFactory.create(
            track=TrackName.ADOPTION,
            organization=org_1,
        )
        track_b = factories.ClientTrackFactory.create(
            track=TrackName.ADOPTION,
            organization=org_2,
        )
        tracks = [track_a, track_b]
        with mock.patch(
            "tracks.service.tracks.OverEligibilityRule.filter_by_wallet",
            return_value=tracks,
        ), mock.patch(
            "tracks.service.tracks.OverEligibilityRule.filter_by_track_length",
            return_value=tracks,
        ), mock.patch(
            "tracks.service.tracks.OverEligibilityRule.filter_by_number_of_active_tracks",
            return_value=tracks,
        ), mock.patch(
            "tracks.service.tracks.OverEligibilityRule.filter_by_organization_id",
            return_value=tracks,
        ), pytest.raises(
            OverEligibilityRuleError, match=r"^0 or multiple tracks after rules"
        ):
            track_service._apply_over_eligibility_rules(tracks)


class TestGetEnrollableTracksForUserAndOrgs:
    @staticmethod
    def test_empty_input(track_service):
        with pytest.raises(
            ValueError,
            match="At least 1 organization id is needed for track enrollment",
        ):
            track_service.get_enrollable_tracks_for_user_and_orgs(
                user_id=1, organization_ids=[]
            )

    @staticmethod
    def test_happy_path(track_service):
        org_1 = factories.OrganizationFactory.create()
        org_2 = factories.OrganizationFactory.create()
        org_3 = factories.OrganizationFactory.create()
        org_4 = factories.OrganizationFactory.create()
        org_5 = factories.OrganizationFactory.create()
        track_a = factories.ClientTrackFactory.create(
            track=TrackName.ADOPTION,
            organization=org_1,
        )
        track_b = factories.ClientTrackFactory.create(
            track=TrackName.ADOPTION,
            organization=org_2,
        )
        track_c = factories.ClientTrackFactory.create(
            track=TrackName.ADOPTION,
            organization=org_3,
        )
        track_d = factories.ClientTrackFactory.create(
            track=TrackName.ADOPTION,
            organization=org_4,
        )
        track_e = factories.ClientTrackFactory.create(
            track=TrackName.ADOPTION,
            organization=org_5,
        )
        enrolled = [track_a]
        all_available = [track_b, track_c, track_d, track_e]
        available = [track_c, track_d, track_e]
        output = [track_d, track_e]
        user_id = 1
        organization_ids = [100, 101]
        with mock.patch(
            "tracks.repository.MemberTrackRepository.get_active_tracks",
            return_value=enrolled,
        ) as mock_get_active_tracks, mock.patch(
            "tracks.repository.TracksRepository.get_all_available_tracks",
            return_value=all_available,
        ) as mock_get_all_available_tracks, mock.patch(
            "tracks.service.TrackSelectionService._apply_over_eligibility_rules",
            return_value=available,
        ) as mock_apply_over_eligibility_rules, mock.patch(
            "tracks.service.TrackSelectionService._get_enrollable_tracks",
            return_value=output,
        ) as mock_get_enrollable_tracks:
            res = track_service.get_enrollable_tracks_for_user_and_orgs(
                user_id=user_id, organization_ids=organization_ids
            )
            assert set(res) == set(output)
            mock_get_active_tracks.assert_called_once_with(user_id=user_id)
            mock_get_all_available_tracks.assert_called_once_with(
                user_id=user_id, organization_ids=organization_ids
            )
            mock_apply_over_eligibility_rules.assert_called_once_with(all_available)
            mock_get_enrollable_tracks.assert_called_once_with(
                enrolled=enrolled, available=available
            )
