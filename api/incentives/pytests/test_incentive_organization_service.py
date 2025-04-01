import csv
import datetime
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import func

from authn.models.user import User
from incentives.models.incentive import (
    IncentiveAction,
    IncentiveOrganization,
    IncentiveType,
)
from incentives.models.incentive_fulfillment import IncentiveStatus
from incentives.services.incentive_organization import (
    IncentiveFulfillmentResourceMsg,
    IncentiveOrgAlreadyExistsException,
    IncentiveOrganizationService,
    IncentiveUsedOnIncentiveOrgException,
    InvalidIncentiveIdException,
    OrganizationNotEligibleForGiftCardException,
    OrganizationNotEligibleForWelcomeBoxException,
    UserAlreadyFulfilledIncentiveException,
    UserAlreadySawIncentiveException,
    UserNotEligibleForIncentiveException,
    get_and_mark_incentive_as_seen,
    report_incentives_for_user,
    update_braze_incentive_offboarding_for_org_users,
)
from models.tracks.track import TrackName
from storage.connection import db
from utils import braze


class TestGetUserIncentive:
    @patch("incentives.services.incentive_organization.log.info")
    def test_get_user_incentive__user_doesnt_exist(self, mock_log_info):
        # Given a user id that doesnt exist
        max_user_id = db.session.query(func.max(User.id)).first()[0]
        fake_user_id = (max_user_id or 0) + 1
        incentive_action = IncentiveAction.CA_INTRO

        # When retrieving the incentive
        retrieved_incentive = IncentiveOrganizationService().get_user_incentive(
            user_id=fake_user_id,
            incentivized_action=incentive_action,
            track="pregnancy",
        )

        # Then we get no incentive
        assert (
            mock_log_info.call_args[0][0]
            == "Could not find org id for user_id. Either user doesnt exist or it has no organization"
        )
        assert not retrieved_incentive

    @patch("incentives.services.incentive_organization.log.info")
    def test_get_user_incentive__user_has_no_country_code(
        self, mock_log_info, incentive_user
    ):
        # Given a user with no country code
        incentive_user.member_profile.country_code = None
        incentivized_action = IncentiveAction.CA_INTRO

        # When retrieving the incentive
        retrieved_incentive = IncentiveOrganizationService().get_user_incentive(
            user_id=incentive_user.id,
            incentivized_action=incentivized_action,
            track="pregnancy",
        )

        # Then we get no incentive
        assert mock_log_info.call_args[0][0] == "User has no country code"
        assert not retrieved_incentive

    @patch("incentives.repository.incentive.IncentiveRepository.get_by_params")
    def test_get_user_incentive__incentive_does_not_exist(
        self, get_by_params_mock, incentive_user
    ):
        # Given a user with all params to get an incentive
        user_id = incentive_user.id
        incentivized_action = IncentiveAction.CA_INTRO
        get_by_params_mock.return_value = None

        # When retrieving the incentive for the user
        retrieved_incentive = IncentiveOrganizationService().get_user_incentive(
            user_id=user_id, incentivized_action=incentivized_action, track="pregnancy"
        )

        # Then, repository was called and we do not get the incentive
        get_by_params_mock.assert_called_once()
        assert not retrieved_incentive

    @patch("incentives.repository.incentive.IncentiveRepository.get_by_params")
    def test_get_user_incentive__incentive_exists(
        self, get_by_params_mock, user_and_incentive
    ):
        # Given a user and an incentive configured for them
        user, incentive = user_and_incentive

        # When retrieving the incentive for the user
        user_id = user.id
        incentivized_action = incentive.incentive_organizations[0].action
        track = incentive.incentive_organizations[0].track_name

        get_by_params_mock.return_value = incentive

        retrieved_incentive = IncentiveOrganizationService().get_user_incentive(
            user_id=user_id, incentivized_action=incentivized_action, track=track
        )

        # Then, we repository was called and we get the incentive
        get_by_params_mock.assert_called_once()
        assert incentive == retrieved_incentive


class TestGetIncentiveFulfillment:
    @patch(
        "incentives.repository.incentive_fulfillment.IncentiveFulfillmentRepository.get_by_params"
    )
    def test_get_incentive_fulfillment(self, mock_get_by_params):
        # Given
        member_track_id = 1
        incentivized_action = "best_action"

        # When calling get_incentive_fulfillment
        IncentiveOrganizationService().get_incentive_fulfillment(
            member_track_id=member_track_id, incentivized_action=incentivized_action
        )

        # Then, repo is called
        mock_get_by_params.assert_called_once_with(
            member_track_id=member_track_id, incentivized_action=incentivized_action
        )


class TestSetIncentiveAsEarned:
    @patch(
        "incentives.repository.incentive_fulfillment.IncentiveFulfillmentRepository.set_status"
    )
    def test_set_incentive_as_earned__successful(
        self, mock_set_status, incentive_fulfillment
    ):
        # Given an incentive_fulfillment that exits and whose status is seen
        incentive_fulfillment.status = IncentiveStatus.SEEN
        now = datetime.datetime.utcnow()

        # When calling set incentive as earned
        IncentiveOrganizationService().set_incentive_as_earned(
            incentive_fulfillment=incentive_fulfillment, date_earned=now
        )

        # Then the repository was called to update its status
        mock_set_status.assert_called_once_with(
            incentive_fulfillment=incentive_fulfillment,
            status=IncentiveStatus.EARNED,
            date_status_changed=now,
        )

    @patch("incentives.services.incentive_organization.log.warning")
    @patch(
        "incentives.repository.incentive_fulfillment.IncentiveFulfillmentRepository.set_status"
    )
    def test_set_incentive_as_earned____incentive_fulfillment_status_not_seen(
        self, mock_set_status, mock_log_warning, incentive_fulfillment
    ):
        # Given an incentive_fulfillment that exits and whose status is not SEEN
        incentive_fulfillment.status = IncentiveStatus.EARNED
        now = datetime.datetime.utcnow()

        # When calling set incentive as earned
        IncentiveOrganizationService().set_incentive_as_earned(
            incentive_fulfillment=incentive_fulfillment, date_earned=now
        )

        # Then the log warning is called and the repository is not called to set new status
        mock_log_warning.assert_called_once_with(
            "Failed trying to set incentive fulfillment as EARNED, its status is not SEEN",
            incentive_fulfillment_id=incentive_fulfillment.id,
            incentive_fulfillment_status=incentive_fulfillment.status,
        )
        assert not mock_set_status.called


class TestAttemptToSetIntroApptIncentiveAsEarned:
    @patch(
        "incentives.services.incentive_organization.IncentiveOrganizationService.attempt_to_set_incentive_as_earned"
    )
    @patch(
        "incentives.services.incentive_organization.TrackSelectionService.get_highest_priority_track"
    )
    def test_attempt_to_set_intro_appt_incentive_as_earned(
        self,
        mock_get_highest_priority_track,
        mock_attempt_to_set_incentive_as_earned,
        incentive_fulfillment,
        factories,
    ):
        # Given an appointment and a track for the member
        appointment = factories.AppointmentFactory()
        member_track = factories.MemberTrackFactory(user=appointment.member)
        now = datetime.datetime.now()
        appointment.member_started_at = (
            appointment.practitioner_started_at
        ) = appointment.member_ended_at = appointment.practitioner_ended_at = now

        mock_get_highest_priority_track.return_value = member_track

        # When calling attempt to set incentive as earner
        IncentiveOrganizationService().attempt_to_set_intro_appt_incentive_as_earned(
            appointment
        )

        # Then, we call the appropriate internal functions
        mock_get_highest_priority_track.assert_called_once_with(
            tracks=[member_track],
        )
        mock_attempt_to_set_incentive_as_earned.assert_called_once_with(
            user_id=appointment.member.id,
            member_track_id=member_track.id,
            incentivized_action=IncentiveAction.CA_INTRO,
            date_incentive_earned=now,
        )


class TestAttemptToSetOffboardingAssessmentIncentiveAsEarned:
    @patch(
        "incentives.services.incentive_organization.IncentiveOrganizationService.attempt_to_set_incentive_as_earned"
    )
    def test_attempt_to_set_offboarding_assessment_incentive_as_earned(
        self,
        mock_attempt_to_set_incentive_as_earned,
        incentive_fulfillment,
        factories,
    ):
        # Given a member with track
        user = factories.MemberFactory()
        user_id = user.id
        member_track = factories.MemberTrackFactory(user=user)
        now = datetime.datetime.now()

        # When calling attempt to set offboarding incentive as earned
        IncentiveOrganizationService().attempt_to_set_offboarding_assessment_incentive_as_earned(
            user_id=user_id, track_name=member_track.name, date_incentive_earned=now
        )

        # Then, we call the appropriate internal function
        mock_attempt_to_set_incentive_as_earned.assert_called_once_with(
            user_id=user_id,
            member_track_id=member_track.id,
            incentivized_action=IncentiveAction.OFFBOARDING_ASSESSMENT,
            date_incentive_earned=now,
        )

    @patch(
        "incentives.services.incentive_organization.IncentiveOrganizationService.attempt_to_set_incentive_as_earned"
    )
    @patch("incentives.services.incentive_organization.log.info")
    def test_attempt_to_set_offboarding_assessment_incentive_as_earned__recently_created_fulfillment_record(
        self,
        mock_log_info,
        mock_attempt_to_set_incentive_as_earned,
        incentive_fulfillment,
        factories,
    ):
        # Given a member with track and an incentive-fulfillment record recently created
        user = factories.MemberFactory()
        user_id = user.id
        member_track = factories.MemberTrackFactory(user=user)
        now = datetime.datetime.now()
        incentive = factories.IncentiveFactory()
        factories.IncentiveFulfillmentFactory.create(
            member_track=member_track,
            incentivized_action=IncentiveAction.OFFBOARDING_ASSESSMENT,
            incentive=incentive,
            status=IncentiveStatus.EARNED,
            date_earned=now,
        )

        # When calling attempt to set offboarding incentive as earned
        IncentiveOrganizationService().attempt_to_set_offboarding_assessment_incentive_as_earned(
            user_id=user_id, track_name=member_track.name, date_incentive_earned=now
        )

        # Then, we do not call the internal function to set incentive as earned
        mock_attempt_to_set_incentive_as_earned.assert_not_called()

        # And we log that the incentive-fulfillment record was recently created
        mock_log_info.assert_called_with(
            "An Offboarding Assessment incentive-fulfillment record has been earned within the last 2 months for this user on this track. We can assume this is a duplicate submission and we will not create another incentive-fulfillment record.",
            user_id=user.id,
            track_name=member_track.name,
        )


class TestCheckForRecentOffboardingIncentiveFulfillmentRecords:
    def test_check_for_recent_offboarding_incentive_fulfillment_records__valid_record(
        self, factories
    ):
        # Given an incentive-fulfillment record for the user on the given track
        user = factories.MemberFactory()
        user_id = user.id
        member_track = factories.MemberTrackFactory(user=user)
        now = datetime.datetime.utcnow()
        incentive = factories.IncentiveFactory()
        incentive_fulfillment = factories.IncentiveFulfillmentFactory.create(
            member_track=member_track,
            incentivized_action=IncentiveAction.OFFBOARDING_ASSESSMENT,
            incentive=incentive,
            status=IncentiveStatus.EARNED,
            date_earned=now,
        )

        # When we call _check_for_recent_offboarding_incentive_fulfillment_records
        recent_records = IncentiveOrganizationService()._check_for_recent_offboarding_incentive_fulfillment_records(
            user_id=user_id, track_name=member_track.name
        )

        # Then we return the incentive-fulfillment record we expect
        assert recent_records[0] == incentive_fulfillment.id

    def test_check_for_recent_offboarding_incentive_fulfillment_records__excludes_expected_records(
        self, factories
    ):
        # Given incentive-fulfillment records that do not fit the criteria for _check_for_recent_offboarding_incentive_fulfillment_records
        user = factories.MemberFactory()
        user_id = user.id
        member_track = factories.MemberTrackFactory(user=user)
        now = datetime.datetime.utcnow()
        incentive = factories.IncentiveFactory()
        # record too old
        factories.IncentiveFulfillmentFactory.create(
            member_track=member_track,
            incentivized_action=IncentiveAction.OFFBOARDING_ASSESSMENT,
            incentive=incentive,
            status=IncentiveStatus.EARNED,
            date_earned=now - datetime.timedelta(days=90),
        )
        # record has wrong incentivized_action
        factories.IncentiveFulfillmentFactory.create(
            member_track=member_track,
            incentivized_action=IncentiveAction.CA_INTRO,
            incentive=incentive,
            status=IncentiveStatus.EARNED,
            date_earned=now - datetime.timedelta(days=10),
        )

        # When we call _check_for_recent_offboarding_incentive_fulfillment_records
        recent_records = IncentiveOrganizationService()._check_for_recent_offboarding_incentive_fulfillment_records(
            user_id=user_id, track_name=member_track.name
        )

        # Then we return no incentive-fulfillment records to be found
        assert not recent_records


class TestGetMemberTrackIdWhenOffboardingAssessmentCompleted:
    def test_get_member_track_id_when_offboarding_assessment_completed__no_member_track(
        self,
    ):
        # Given no member_track exists
        user_id = 1
        track_name = "pregnancy"

        # When
        member_track_id = IncentiveOrganizationService()._get_member_track_id_when_offboarding_assessment_completed(
            user_id=user_id, track_name=track_name
        )

        # Then
        assert not member_track_id

    def test_get_member_track_id_when_offboarding_assessment_completed__one_member_track(
        self, factories
    ):
        # Given one member track exists
        member_track = factories.MemberTrackFactory()
        user_id = member_track.user.id
        track_name = member_track.name

        # When
        member_track_id = IncentiveOrganizationService()._get_member_track_id_when_offboarding_assessment_completed(
            user_id=user_id, track_name=track_name
        )

        # Then
        assert member_track_id == member_track.id

    @patch("incentives.services.incentive_organization.log.warning")
    def test_get_member_track_id_when_offboarding_assessment_completed__all_tracks_have_incentive_fulfillments(
        self, mock_log_warning, user_and_incentive, factories
    ):
        # Given two tracks and both with incentive fulfillment rows
        user, incentive = user_and_incentive
        member_track_1 = user.current_member_track
        track_name = member_track_1.name
        member_track_2 = factories.MemberTrackFactory(name=track_name, user=user)

        factories.IncentiveFulfillmentFactory.create(
            member_track=member_track_1,
            incentive=incentive,
            incentivized_action=IncentiveAction.OFFBOARDING_ASSESSMENT,
        )
        factories.IncentiveFulfillmentFactory.create(
            member_track=member_track_2,
            incentive=incentive,
            incentivized_action=IncentiveAction.OFFBOARDING_ASSESSMENT,
        )

        # When
        member_track_id = IncentiveOrganizationService()._get_member_track_id_when_offboarding_assessment_completed(
            user_id=user.id, track_name=track_name
        )

        # Then
        mock_log_warning.assert_called_once_with(
            "Failed to find member_track_id, could not find a track that has no incentive_fulfillment row",
            user_id=user.id,
            track_name=track_name,
            member_tracks_ids=[mt.id for mt in [member_track_1, member_track_2]],
        )
        assert not member_track_id

    def test_get_member_track_id_when_offboarding_assessment_completed__some_tracks_with_old_ended_at__oldest_created_at_track_returned(
        self, factories
    ):
        # Given a member with three tracks, none have incentive fulfillment, one ended_at before Dec 1 2023, the others after and have diff created_at
        user = factories.DefaultUserFactory()
        track_name = "pregnancy"
        jan_1st_2022 = datetime.datetime(2022, 1, 1)
        jan_1st_2023 = datetime.datetime(2023, 1, 1)
        dec_2nd_2023 = datetime.datetime(2023, 12, 2)

        # Member track with too old ended_at
        factories.MemberTrackFactory(
            user=user, name=track_name, created_at=jan_1st_2022, ended_at=jan_1st_2023
        )

        member_track_with_acceptable_ended_at_and_oldest_created_at = (
            factories.MemberTrackFactory(
                user=user,
                name=track_name,
                created_at=jan_1st_2022,
                ended_at=dec_2nd_2023,
            )
        )

        # Member track with acceptable ended at but not oldest created_at
        factories.MemberTrackFactory(
            user=user, name=track_name, created_at=jan_1st_2023, ended_at=dec_2nd_2023
        )

        # When
        member_track_id = IncentiveOrganizationService()._get_member_track_id_when_offboarding_assessment_completed(
            user_id=user.id, track_name=track_name
        )

        # Then we get the track with acceptable ended_at and oldest created_at
        assert (
            member_track_id
            is member_track_with_acceptable_ended_at_and_oldest_created_at.id
        )

    @patch("incentives.services.incentive_organization.log.warning")
    def test_get_member_track_id_when_offboarding_assessment_completed__all_tracks_with_old_ended_at__no_track_returned(
        self, mock_log_warning, factories
    ):
        # Given a member with three tracks, none have incentive fulfillment, all ended_at before Dec 1 2023
        user = factories.DefaultUserFactory()
        track_name = "pregnancy"
        jan_1st_2022 = datetime.datetime(2022, 1, 1)
        jan_1st_2023 = datetime.datetime(2023, 1, 1)

        # Three member tracks with too old created at
        factories.MemberTrackFactory(
            user=user,
            name=track_name,
            created_at=jan_1st_2022,
            ended_at=jan_1st_2023,
        )

        factories.MemberTrackFactory(
            user=user,
            name=track_name,
            created_at=jan_1st_2022 + datetime.timedelta(days=1),
            ended_at=jan_1st_2023,
        )

        factories.MemberTrackFactory(
            user=user,
            name=track_name,
            created_at=jan_1st_2022 + datetime.timedelta(days=2),
            ended_at=jan_1st_2023,
        )

        # When
        member_track_id = IncentiveOrganizationService()._get_member_track_id_when_offboarding_assessment_completed(
            user_id=user.id, track_name=track_name
        )

        # Then, no tracks pass the ended_at filter, so none returned
        assert not member_track_id


class TestAttemptToSetIncentiveAsEarned:
    @pytest.mark.parametrize(
        argnames="incentivized_action",
        argvalues=[IncentiveAction.CA_INTRO, IncentiveAction.OFFBOARDING_ASSESSMENT],
    )
    @patch(
        "incentives.services.incentive_organization.IncentiveOrganizationService.get_incentive_fulfillment"
    )
    @patch(
        "incentives.services.incentive_organization.IncentiveOrganizationService.set_incentive_as_earned"
    )
    def test_attempt_to_set_incentive_as_earned__incentive_fulfillment_exists_and_status_seen(
        self,
        mock_set_incentive_as_earned,
        mock_get_incentive_fulfillment,
        incentivized_action,
        incentive_fulfillment,
    ):
        # Given an incentive fulfillment exists and its status is seen
        incentive_fulfillment.status = IncentiveStatus.SEEN
        mock_get_incentive_fulfillment.return_value = incentive_fulfillment

        # When calling attempt to set incentive as EARNED
        user_id = 1  # Can be fake, wont be used
        member_track_id = 1  # Can be fake, wont be used
        date_incentive_earned = datetime.datetime.now()
        IncentiveOrganizationService().attempt_to_set_incentive_as_earned(
            user_id=user_id,
            member_track_id=member_track_id,
            incentivized_action=incentivized_action,
            date_incentive_earned=date_incentive_earned,
        )

        # Then, we call the appropriate internal functions
        mock_get_incentive_fulfillment.assert_called_once_with(
            member_track_id=member_track_id,
            incentivized_action=incentivized_action,
        )
        mock_set_incentive_as_earned.assert_called_once_with(
            incentive_fulfillment=incentive_fulfillment,
            date_earned=date_incentive_earned,
        )

    @pytest.mark.parametrize(
        argnames="incentivized_action",
        argvalues=[IncentiveAction.CA_INTRO, IncentiveAction.OFFBOARDING_ASSESSMENT],
    )
    @patch("incentives.services.incentive_organization.log.info")
    @patch(
        "incentives.services.incentive_organization.IncentiveOrganizationService.get_incentive_fulfillment"
    )
    @patch(
        "incentives.services.incentive_organization.IncentiveOrganizationService.set_incentive_as_earned"
    )
    def test_attempt_to_set_incentive_as_earned__incentive_fulfillment_exists_and_status_not_seen(
        self,
        mock_set_incentive_as_earned,
        mock_get_incentive_fulfillment,
        mock_log_info,
        incentivized_action,
        incentive_fulfillment,
    ):
        # Given an incentive fulfillment exists and its status is not seen
        incentive_fulfillment.status = IncentiveStatus.EARNED
        mock_get_incentive_fulfillment.return_value = incentive_fulfillment

        # When calling attempt to set incentive as EARNED
        user_id = 1  # Can be fake, wont be used
        member_track_id = 1  # Can be fake, wont be used
        date_incentive_earned = datetime.datetime.now()
        IncentiveOrganizationService().attempt_to_set_incentive_as_earned(
            user_id=user_id,
            member_track_id=member_track_id,
            incentivized_action=incentivized_action,
            date_incentive_earned=date_incentive_earned,
        )

        # Then, we call the appropriate internal functions
        mock_get_incentive_fulfillment.assert_called_once_with(
            member_track_id=member_track_id,
            incentivized_action=incentivized_action,
        )
        assert not mock_set_incentive_as_earned.called
        mock_log_info.assert_called_with(
            "Not marking as earned. Incentive has already been earned",
            incentive_fulfillment_id=incentive_fulfillment.id,
            incentive_fulfillment_status=incentive_fulfillment.status,
            user_id=user_id,
            member_track_id=member_track_id,
            incentivized_action=incentivized_action,
            date_incentive_earned=date_incentive_earned,
        )

    @pytest.mark.parametrize(
        argnames="incentivized_action",
        argvalues=[IncentiveAction.CA_INTRO, IncentiveAction.OFFBOARDING_ASSESSMENT],
    )
    @patch("incentives.services.incentive_organization.log.info")
    @patch(
        "incentives.services.incentive_organization.IncentiveOrganizationService.get_user_incentive"
    )
    @patch(
        "incentives.services.incentive_organization.IncentiveOrganizationService.get_incentive_fulfillment"
    )
    @patch(
        "incentives.services.incentive_organization.IncentiveOrganizationService.set_incentive_as_earned"
    )
    def test_attempt_to_set_incentive_as_earned__incentive_fulfillment_doesnt_exist_and_no_incentive_configured(
        self,
        mock_set_incentive_as_earned,
        mock_get_incentive_fulfillment,
        mock_get_user_incentive,
        mock_log_info,
        incentivized_action,
        user_and_incentive,
        factories,
    ):
        # Given no incentive fulfillment exists and no incentive configured
        user = factories.MemberFactory()
        user_id = user.id
        member_track = factories.MemberTrackFactory(user=user)
        member_track_id = member_track.id

        mock_get_incentive_fulfillment.return_value = None
        mock_get_user_incentive.return_value = None

        # When calling attempt to set incentive as earned
        date_incentive_earned = datetime.datetime.now()
        IncentiveOrganizationService().attempt_to_set_incentive_as_earned(
            user_id=user_id,
            member_track_id=member_track_id,
            incentivized_action=incentivized_action,
            date_incentive_earned=date_incentive_earned,
        )

        # Then, we call the appropriate internal functions
        mock_get_incentive_fulfillment.assert_called_once_with(
            member_track_id=member_track_id,
            incentivized_action=incentivized_action,
        )
        assert not mock_set_incentive_as_earned.called
        mock_get_user_incentive.assert_called_once_with(
            user_id=user_id,
            incentivized_action=incentivized_action,
            track=member_track.name,
        )
        mock_log_info.assert_called_with(
            "No incentive marked as earned as incentive_fulfillment was not found, which makes sense as user is not eligible for one",
            member_track_id=member_track.id,
            incentivized_action=incentivized_action,
        )

    @patch("incentives.services.incentive_organization.log.info")
    @patch(
        "incentives.services.incentive_organization.IncentiveOrganizationService.get_user_incentive"
    )
    @patch(
        "incentives.services.incentive_organization.IncentiveOrganizationService.get_incentive_fulfillment"
    )
    @patch(
        "incentives.services.incentive_organization.IncentiveOrganizationService.set_incentive_as_earned"
    )
    def test_attempt_to_set_incentive_as_earned__incentive_fulfillment_doesnt_exist_but_incentive_is_configured__ca_intro__transition(
        self,
        mock_set_incentive_as_earned,
        mock_get_incentive_fulfillment,
        mock_get_user_incentive,
        mock_log_info,
        user_and_incentive,
        incentive_fulfillment,
        factories,
    ):
        # Given no incentive fulfillment exists, but an incentive does exist for the user, in the context of a ca intro
        incentivized_action = IncentiveAction.CA_INTRO
        user, incentive = user_and_incentive
        mock_get_incentive_fulfillment.return_value = None
        mock_get_user_incentive.return_value = incentive
        # and the user is a transition
        member_track_end_date = datetime.datetime.now()
        # round microseconds
        temp_date_time = member_track_end_date + datetime.timedelta(seconds=0.5)
        member_track_end_date = temp_date_time.replace(microsecond=0)
        factories.MemberTrackFactory(
            user=user,
            ended_at=member_track_end_date,
        )
        # When calling attempt to set incentive as earned
        user_id = user.id
        member_track = user.current_member_track
        member_track_id = member_track.id
        date_incentive_earned = datetime.datetime.now()

        IncentiveOrganizationService().attempt_to_set_incentive_as_earned(
            user_id=user_id,
            member_track_id=member_track_id,
            incentivized_action=incentivized_action,
            date_incentive_earned=date_incentive_earned,
        )

        # Then, we call the appropriate internal functions
        mock_get_incentive_fulfillment.assert_called_once_with(
            member_track_id=member_track_id,
            incentivized_action=incentivized_action,
        )
        assert not mock_set_incentive_as_earned.called
        mock_get_user_incentive.assert_called_once_with(
            user_id=user_id,
            incentivized_action=IncentiveAction.CA_INTRO,
            track=member_track.name,
        )
        mock_log_info.assert_called_with(
            "Member is transitioning tracks. They do not have an incentive-fulfillment record because they are not eligible for incentives.",
            user_incentive_id=incentive.id,
            incentivized_action=IncentiveAction.CA_INTRO,
            member_track_id=member_track.id,
            track_name=member_track.name,
            user_id=user_id,
            inactive_track_end_date=member_track_end_date,
            current_track_start_date=member_track.created_at,
        )

    @patch(
        "incentives.services.incentive_organization.IncentiveOrganizationService.get_user_incentive"
    )
    @patch(
        "incentives.services.incentive_organization.IncentiveOrganizationService.get_incentive_fulfillment"
    )
    @patch(
        "incentives.repository.incentive_fulfillment.IncentiveFulfillmentRepository.create"
    )
    def test_attempt_to_set_incentive_as_earned__incentive_fulfillment_doesnt_exist_but_incentive_is_configured__ca_intro__onboarded_before_implementation(
        self,
        mock_create_incentive_fulfillment,
        mock_get_incentive_fulfillment,
        mock_get_user_incentive,
        user_and_incentive,
        incentive_fulfillment,
        factories,
    ):
        # Given no incentive fulfillment exists, but an incentive does exist for the user, in the context of a ca intro
        # but the user onboarded before incentives implementation so is eligible for an incentive
        incentivized_action = IncentiveAction.CA_INTRO
        user, incentive = user_and_incentive
        mock_get_incentive_fulfillment.return_value = None
        mock_get_user_incentive.return_value = incentive

        # When calling attempt to set incentive as earned
        user_id = user.id
        # need new member track to avoid duplicate entry
        member_track = factories.MemberTrackFactory(
            user=user,
            name=TrackName.EGG_FREEZING,
        )
        member_track_id = member_track.id
        member_track.created_at = datetime.datetime(2023, 12, 18, 0, 0, 0)
        date_incentive_earned = datetime.datetime.now()

        IncentiveOrganizationService().attempt_to_set_incentive_as_earned(
            user_id=user_id,
            member_track_id=member_track_id,
            incentivized_action=incentivized_action,
            date_incentive_earned=date_incentive_earned,
        )

        # Then, we call the appropriate internal functions and mark the incentive as earned
        mock_get_incentive_fulfillment.assert_called_once_with(
            member_track_id=member_track_id,
            incentivized_action=incentivized_action,
        )
        mock_get_user_incentive.assert_called_once_with(
            user_id=user_id,
            incentivized_action=IncentiveAction.CA_INTRO,
            track=member_track.name,
        )
        mock_create_incentive_fulfillment.assert_called_once_with(
            incentive_id=incentive.id,
            member_track_id=member_track_id,
            incentivized_action=incentivized_action,
            date_status_changed=date_incentive_earned,
            status=IncentiveStatus.EARNED,
        )

    @patch(
        "incentives.repository.incentive_fulfillment.IncentiveFulfillmentRepository.create"
    )
    @patch("incentives.services.incentive_organization.log.warning")
    @patch(
        "incentives.services.incentive_organization.IncentiveOrganizationService.get_user_incentive"
    )
    @patch(
        "incentives.services.incentive_organization.IncentiveOrganizationService.get_incentive_fulfillment"
    )
    @patch(
        "incentives.services.incentive_organization.IncentiveOrganizationService.set_incentive_as_earned"
    )
    def test_attempt_to_set_incentive_as_earned__incentive_fulfillment_doesnt_exist_but_incentive_is_configured__ca_intro__all_other_scenarios(
        self,
        mock_set_incentive_as_earned,
        mock_get_incentive_fulfillment,
        mock_get_user_incentive,
        mock_log_warning,
        mock_create_incentive_fulfillment,
        user_and_incentive,
        incentive_fulfillment,
        factories,
    ):
        # Given no incentive fulfillment exists, but an incentive does exist for the user, in the context of a ca intro
        incentivized_action = IncentiveAction.CA_INTRO
        user, incentive = user_and_incentive
        mock_get_incentive_fulfillment.return_value = None
        mock_get_user_incentive.return_value = incentive

        # When calling attempt to set incentive as earned
        user_id = user.id
        # need new member track to avoid duplicate entry
        member_track = factories.MemberTrackFactory(
            user=user,
            name=TrackName.ADOPTION,
        )
        member_track.created_at = datetime.datetime(2023, 12, 20, 0, 0, 0)
        date_incentive_earned = datetime.datetime.now()

        IncentiveOrganizationService().attempt_to_set_incentive_as_earned(
            user_id=user_id,
            member_track_id=member_track.id,
            incentivized_action=incentivized_action,
            date_incentive_earned=date_incentive_earned,
        )

        # Then, we call the appropriate internal functions
        mock_get_incentive_fulfillment.assert_called_once_with(
            member_track_id=member_track.id,
            incentivized_action=incentivized_action,
        )
        assert not mock_set_incentive_as_earned.called
        mock_get_user_incentive.assert_called_once_with(
            user_id=user_id,
            incentivized_action=IncentiveAction.CA_INTRO,
            track=member_track.name,
        )
        mock_log_warning.assert_called_once_with(
            "Member has no incentive-fulfillment record, is not a transition, started track after implementation, and is currently eligible for an incentive. Will create EARNED incentive-fulfillment record.",
            user_incentive_id=incentive.id,
            incentivized_action=IncentiveAction.CA_INTRO,
            member_track_id=member_track.id,
            track_name=member_track.name,
            user_id=user_id,
        )
        mock_create_incentive_fulfillment.assert_called_once_with(
            incentive_id=incentive.id,
            member_track_id=member_track.id,
            incentivized_action=incentivized_action,
            date_status_changed=date_incentive_earned,
            status=IncentiveStatus.EARNED,
        )

    @patch("incentives.services.incentive_organization.log.info")
    @patch(
        "incentives.repository.incentive_fulfillment.IncentiveFulfillmentRepository.create"
    )
    @patch(
        "incentives.services.incentive_organization.IncentiveOrganizationService.get_user_incentive"
    )
    @patch(
        "incentives.services.incentive_organization.IncentiveOrganizationService.get_incentive_fulfillment"
    )
    @patch(
        "incentives.services.incentive_organization.IncentiveOrganizationService.set_incentive_as_earned"
    )
    def test_attempt_to_set_incentive_as_earned__incentive_fulfillment_doesnt_exist_but_incentive_is_configured__offboarding_assessment(
        self,
        mock_set_incentive_as_earned,
        mock_get_incentive_fulfillment,
        mock_get_user_incentive,
        mock_create,
        mock_log_info,
        user_and_incentive,
        incentive_fulfillment,
    ):
        # Given no incentive fulfillment exists, but an incentive does exist for the user, in the context of an offboaridng assessment
        incentivized_action = IncentiveAction.OFFBOARDING_ASSESSMENT
        user, incentive = user_and_incentive
        mock_get_incentive_fulfillment.return_value = None
        mock_get_user_incentive.return_value = incentive
        mock_create.return_value = incentive_fulfillment

        # When calling attempt to set incentive as earned
        user_id = user.id
        member_track = user.current_member_track
        member_track_id = member_track.id
        date_incentive_earned = datetime.datetime.now()

        IncentiveOrganizationService().attempt_to_set_incentive_as_earned(
            user_id=user_id,
            member_track_id=member_track_id,
            incentivized_action=incentivized_action,
            date_incentive_earned=date_incentive_earned,
        )

        # Then, we call the appropriate internal functions
        mock_get_incentive_fulfillment.assert_called_once_with(
            member_track_id=member_track_id,
            incentivized_action=incentivized_action,
        )
        assert not mock_set_incentive_as_earned.called
        mock_get_user_incentive.assert_called_once_with(
            user_id=user_id,
            incentivized_action=incentivized_action,
            track=member_track.name,
        )
        mock_create.assert_called_once_with(
            incentive_id=incentive.id,
            member_track_id=member_track_id,
            incentivized_action=incentivized_action,
            date_status_changed=date_incentive_earned,
            status=IncentiveStatus.EARNED,
        )

        mock_log_info.assert_called_with(
            "Successfully created incentive_fulfillment for an earned offboarding assessment incentive",
            incentive_fulfillment_id=incentive_fulfillment.id,
            member_track_id=member_track_id,
            incentivized_action=incentivized_action,
            date_earned=date_incentive_earned,
        )


class TestValidateIncentiveExists:
    @patch("incentives.repository.incentive.IncentiveRepository.get_by_params")
    def test_validate_incentive_exists__incentive_exists(self, mock_get, factories):
        # Given an incentive will be returned by the incentive repository
        incentive = factories.IncentiveFactory()
        mock_get.return_value = incentive

        # When
        IncentiveOrganizationService().validate_incentive_exists(
            incentive_id=incentive.id
        )

        # No exception is raised

    @patch("incentives.repository.incentive.IncentiveRepository.get")
    def test_validate_incentive_exists__incentive_does_not_exist(self, mock_get):
        # Given an incentive will not be returned by the incentive repository
        mock_get.return_value = None

        # Then
        with pytest.raises(InvalidIncentiveIdException):
            # When
            IncentiveOrganizationService().validate_incentive_exists(incentive_id=1)


class TestValidateUserHasIncentive:
    @patch(
        "incentives.services.incentive_organization.IncentiveOrganizationService.get_user_incentive"
    )
    def test_validate_user_has_incentive__user_has_incentive(
        self, mock_get_user_incentive, user_and_incentive
    ):
        # Given a user that has an incentive
        user, incentive = user_and_incentive
        member_track_id = user.current_member_track.id
        incentivized_action = incentive.incentive_organizations[0].action

        mock_get_user_incentive.return_value = incentive

        # When validating user has it
        IncentiveOrganizationService()._validate_user_has_incentive(
            user_id=user.id,
            incentive_id=incentive.id,
            member_track_id=member_track_id,
            incentivized_action=incentivized_action,
        )

        # No exceptions raised

    @patch(
        "incentives.services.incentive_organization.IncentiveOrganizationService.get_user_incentive"
    )
    def test_validate_user_has_incentive__user_does_not_have_incentive(
        self, mock_get_user_incentive, user_and_incentive
    ):
        # Given a user that does not have an incentive
        user, incentive = user_and_incentive
        member_track_id = user.current_member_track.id
        incentivized_action = incentive.incentive_organizations[0].action

        # Mock return to be None
        mock_get_user_incentive.return_value = None

        # Then
        with pytest.raises(UserNotEligibleForIncentiveException):
            # When validating user has the incentive
            IncentiveOrganizationService()._validate_user_has_incentive(
                user_id=user.id,
                incentive_id=incentive.id,
                member_track_id=member_track_id,
                incentivized_action=incentivized_action,
            )


class TestValidateIncentiveHasNotBeenSeen:
    @patch(
        "incentives.repository.incentive_fulfillment.IncentiveFulfillmentRepository.get_by_params"
    )
    def test_validate_incentive_has_not_been_seen__incentive_not_seen(
        self, mock_get_by_params, user_and_incentive
    ):
        # Given a user that has an incentive which has not been seen
        user, incentive = user_and_incentive
        member_track_id = user.current_member_track.id
        incentivized_action = incentive.incentive_organizations[0].action

        mock_get_by_params.return_value = None

        # When validating if user has seen the incentive
        IncentiveOrganizationService()._validate_incentive_has_not_been_seen(
            member_track_id=member_track_id,
            incentivized_action=incentivized_action,
        )

        # No exceptions raised

    @patch(
        "incentives.repository.incentive_fulfillment.IncentiveFulfillmentRepository.get_by_params"
    )
    def test_validate_incentive_has_not_been_seen__incentive_seen(
        self, mock_get_by_params, user_and_incentive, factories
    ):
        # Given a user that has an incentive which has been seen
        user, incentive = user_and_incentive
        member_track_id = user.current_member_track.id
        incentivized_action = incentive.incentive_organizations[0].action

        incentive_fulfillment = factories.IncentiveFulfillmentFactory.create(
            member_track=user.current_member_track,
            incentive=incentive,
            incentivized_action=incentivized_action,
            status=IncentiveStatus.SEEN,
        )
        mock_get_by_params.return_value = incentive_fulfillment

        # Then exception is raised
        with pytest.raises(UserAlreadySawIncentiveException):
            # When validating if user has seen the incentive
            IncentiveOrganizationService()._validate_incentive_has_not_been_seen(
                member_track_id=member_track_id,
                incentivized_action=incentivized_action,
            )

    @patch(
        "incentives.repository.incentive_fulfillment.IncentiveFulfillmentRepository.get_by_params"
    )
    def test_validate_incentive_has_not_been_seen__incentive_fulfilled(
        self, mock_get_by_params, user_and_incentive, factories
    ):
        # Given a user that has an incentive which has been fulfilled
        user, incentive = user_and_incentive
        member_track_id = user.current_member_track.id
        incentivized_action = incentive.incentive_organizations[0].action

        incentive_fulfillment = factories.IncentiveFulfillmentFactory.create(
            member_track=user.current_member_track,
            incentive=incentive,
            incentivized_action=incentivized_action,
            status=IncentiveStatus.EARNED,
        )
        mock_get_by_params.return_value = incentive_fulfillment

        # Then exception is raised
        with pytest.raises(UserAlreadyFulfilledIncentiveException):
            # When validating if user has seen the incentive
            IncentiveOrganizationService()._validate_incentive_has_not_been_seen(
                member_track_id=member_track_id,
                incentivized_action=incentivized_action,
            )


class TestPostMemberSawIncentive:
    @patch(
        "incentives.repository.incentive_fulfillment.IncentiveFulfillmentRepository.create"
    )
    @patch(
        "incentives.services.incentive_organization.IncentiveOrganizationService._validate_incentive_has_not_been_seen"
    )
    @patch(
        "incentives.services.incentive_organization.IncentiveOrganizationService._validate_user_has_incentive"
    )
    def test_post_member_saw_incentive__no_exceptions_raised(
        self,
        mock_validate_user_has_incentive,
        mock_validate_incentive_has_not_been_seen,
        mock_create,
        user_and_incentive,
        factories,
    ):
        # Given no exceptions raised during validations, and we mock a succesful fulfillment creation
        mock_validate_user_has_incentive.return_value = True
        mock_validate_incentive_has_not_been_seen.return_value = True
        user, incentive = user_and_incentive
        member_track_id = user.current_member_track.id
        incentivized_action = incentive.incentive_organizations[0].action
        incentive_fulfillment = factories.IncentiveFulfillmentFactory.create(
            member_track=user.current_member_track,
            incentive=incentive,
            incentivized_action=incentivized_action,
        )
        mock_create.return_value = incentive_fulfillment

        # When we call post incentive fulfillment
        date_seen = datetime.datetime.utcnow()
        retrieved_incentive_fulfillment = (
            IncentiveOrganizationService().post_member_saw_incentive(
                user_id=user.id,
                incentive_id=incentive.id,
                member_track_id=member_track_id,
                incentivized_action=incentivized_action,
                date_seen=date_seen,
            )
        )

        # Then
        assert retrieved_incentive_fulfillment == incentive_fulfillment

    @patch(
        "incentives.services.incentive_organization.IncentiveOrganizationService._validate_user_has_incentive"
    )
    def test_post_member_saw_incentive__validate_user_has_incentive_exception_raised(
        self, mock_validate_user_has_incentive, user_and_incentive
    ):
        # Given a user does not have incentive and hence validation fails
        mock_validate_user_has_incentive.side_effect = Mock(
            side_effect=UserNotEligibleForIncentiveException("Test")
        )
        user, incentive = user_and_incentive
        member_track_id = user.current_member_track.id
        incentivized_action = incentive.incentive_organizations[0].action

        # Then exception is raised
        with pytest.raises(UserNotEligibleForIncentiveException):
            # When we call  post incentive fulfillment
            date_seen = datetime.datetime.utcnow()
            IncentiveOrganizationService().post_member_saw_incentive(
                user_id=user.id,
                incentive_id=incentive.id,
                member_track_id=member_track_id,
                incentivized_action=incentivized_action,
                date_seen=date_seen,
            )

    @patch(
        "incentives.services.incentive_organization.IncentiveOrganizationService._validate_incentive_has_not_been_seen"
    )
    @patch(
        "incentives.services.incentive_organization.IncentiveOrganizationService._validate_user_has_incentive"
    )
    def test_post_member_saw_incentive___validate_incentive_has_not_been_seen_exception_raised(
        self,
        mock_validate_user_has_incentive,
        mock_validate_incentive_has_not_been_seen,
        user_and_incentive,
    ):
        # Given a user has already seen incentive and hence validation fails
        mock_validate_user_has_incentive.return_value = True
        mock_validate_incentive_has_not_been_seen.side_effect = Mock(
            side_effect=UserAlreadyFulfilledIncentiveException("Test")
        )

        user, incentive = user_and_incentive
        member_track_id = user.current_member_track.id
        incentivized_action = incentive.incentive_organizations[0].action

        # Then exception is raised
        with pytest.raises(UserAlreadyFulfilledIncentiveException):
            # When we call  post incentive fulfillment
            date_seen = datetime.datetime.utcnow()
            IncentiveOrganizationService().post_member_saw_incentive(
                user_id=user.id,
                incentive_id=incentive.id,
                member_track_id=member_track_id,
                incentivized_action=incentivized_action,
                date_seen=date_seen,
            )


class TestValidateIncentiveNotUsedWhenDeactivating:
    def test_validate_incentive_not_used_when_deactivating__incentive_in_use(
        self, factories
    ):
        # given an active incentive being used in an incentive-org
        incentive = factories.IncentiveFactory.create()
        incentive.active = False
        factories.IncentiveOrganizationFactory.create(incentive=incentive)
        # when we call the validation check
        # assert the exception is raised
        with pytest.raises(IncentiveUsedOnIncentiveOrgException):
            IncentiveOrganizationService().validate_incentive_not_used_when_deactivating(
                incentive.id, incentive.active
            )

    def test_validate_incentive_not_used_when_deactivating__incentive_not_in_use(
        self, factories
    ):
        # given an inactive incentive that is not used on incentive-organization
        incentive = factories.IncentiveFactory.create()
        incentive.active = False
        # when we call the validation check
        # then there is no exception raised
        assert (
            IncentiveOrganizationService().validate_incentive_not_used_when_deactivating(
                incentive.id, incentive.active
            )
            is None
        )

    def test_validate_incentive_not_used_when_deactivating__active(self, factories):
        # given an active incentive
        incentive = factories.IncentiveFactory.create()
        # when we call the validation check
        # then there is no exception raised
        assert (
            IncentiveOrganizationService().validate_incentive_not_used_when_deactivating(
                incentive.id, incentive.active
            )
            is None
        )


class TestIncentiveEligibility:
    def test_check_eligibility__welcome_box__eligible(self, factories):
        # given a welcome box incentive and an org eligible for welcome boxes
        incentive = factories.IncentiveFactory.create()
        incentive.type = IncentiveType.WELCOME_BOX
        organization = factories.OrganizationFactory.create()
        organization.welcome_box_allowed = True
        # when we call the validation check
        # then there is no exception raised
        assert (
            IncentiveOrganizationService().check_eligibility(organization, incentive)
            is None
        )

    def test_check_eligibility__welcome_box__not_eligible(self, factories):
        # given a welcome box incentive and an org ineligible for welcome boxes
        incentive = factories.IncentiveFactory.create()
        incentive.type = IncentiveType.WELCOME_BOX
        organization = factories.OrganizationFactory.create()
        organization.welcome_box_allowed = False
        # when we call the validation check
        # then the exception is raised
        with pytest.raises(OrganizationNotEligibleForWelcomeBoxException):
            IncentiveOrganizationService().check_eligibility(organization, incentive)

    def test_check_eligibility__gift_card__eligible(self, factories):
        # given a gift card incentive and an org eligible for gift cards
        incentive = factories.IncentiveFactory.create()
        incentive.type = IncentiveType.GIFT_CARD
        organization = factories.OrganizationFactory.create()
        organization.gift_card_allowed = True
        # when we call the validation check
        # then there is no exception raised
        assert (
            IncentiveOrganizationService().check_eligibility(organization, incentive)
            is None
        )

    def test_check_eligibility__gift_card__not_eligible(self, factories):
        # given a gift card incentive and an org ineligible for gift cards
        incentive = factories.IncentiveFactory.create()
        incentive.type = IncentiveType.GIFT_CARD
        organization = factories.OrganizationFactory.create()
        organization.gift_card_allowed = False
        # when we call the validation check
        # then the exception is raised
        with pytest.raises(OrganizationNotEligibleForGiftCardException):
            IncentiveOrganizationService().check_eligibility(organization, incentive)


class TestCheckIncentiveDuplicates:
    def test_check_duplicates_edit__not_active(self, factories):
        # given an incentive org that is inactive
        incentive_org = factories.IncentiveOrganizationFactory.create()
        incentive_org.active = False
        # when we call the validation check
        # then the validation passes
        assert (
            IncentiveOrganizationService().check_for_duplicates(
                incentive_org.organization,
                incentive_org.action,
                incentive_org.track_name,
                incentive_org.active,
                incentive_org.id,
            )
            is None
        )

    def test_check_duplicates_edit__existing_org_equals_incentive_org(self, factories):
        # given an active incentive-org and no other incentive-orgs
        incentive_org = factories.IncentiveOrganizationFactory.create()
        # when we check for duplicates with the same values as our incentive-org
        # the only result is the incentive-org we are editing
        # then the validation passes
        assert (
            IncentiveOrganizationService().check_for_duplicates(
                incentive_org.organization,
                incentive_org.action,
                incentive_org.track_name,
                incentive_org.active,
                incentive_org.id,
            )
            is None
        )

    def test_check_duplicates_edit__existing_org_different_incentive_org(
        self, factories
    ):
        # given an active incentive-org and no other incentive-orgs
        incentive_org = factories.IncentiveOrganizationFactory.create()
        factories.IncentiveOrganizationFactory.create(
            organization=incentive_org.organization,
            action=incentive_org.action,
            track_name=incentive_org.track_name,
            active=True,
        )
        # when we check for duplicates with the same values as our incentive-org
        # the result is a different incentive-org than we are editing
        # then the exception is raised
        with pytest.raises(IncentiveOrgAlreadyExistsException):
            IncentiveOrganizationService().check_for_duplicates(
                incentive_org.organization,
                incentive_org.action,
                incentive_org.track_name,
                incentive_org.active,
                incentive_org.id,
            )

    def test_check_duplicates_create__not_active(self, factories):
        # given an incentive org that is inactive
        incentive_org = factories.IncentiveOrganizationFactory.create()
        incentive_org.active = False
        # when we call the validation check
        # then the validation passes
        assert (
            IncentiveOrganizationService().check_for_duplicates(
                incentive_org.organization,
                incentive_org.action,
                incentive_org.track_name,
                incentive_org.active,
            )
            is None
        )

    def test_check_duplicates_create__not_existing_org(self, factories):
        # given an active incentive-org and no other incentive-orgs
        incentive_org = factories.IncentiveOrganizationFactory.create()
        # set active = False to make sure we don't return our newly created incentive-org
        incentive_org.active = False
        # when we check for duplicates with the same values as our incentive-org
        # there are no incentive-orgs returned
        # then the validation passes
        assert (
            IncentiveOrganizationService().check_for_duplicates(
                incentive_org.organization,
                incentive_org.action,
                incentive_org.track_name,
                True,
            )
            is None
        )

    def test_check_duplicates_create__existing_org(self, factories):
        # given an active incentive-org and another incentive-org with the same info
        incentive_org = factories.IncentiveOrganizationFactory.create()
        factories.IncentiveOrganizationFactory.create(
            organization=incentive_org.organization,
            action=incentive_org.action,
            track_name=incentive_org.track_name,
            active=True,
        )
        # when we check for duplicates with the same values as our incentive-org
        # then the validation passes
        with pytest.raises(IncentiveOrgAlreadyExistsException):
            assert (
                IncentiveOrganizationService().check_for_duplicates(
                    incentive_org.organization,
                    incentive_org.action,
                    incentive_org.track_name,
                    incentive_org.active,
                )
                is None
            )


class TestGetIncentiveFulfillments:
    def test_get_incentive_fulfillments__one_fulfillment(
        self, user_and_incentive, factories
    ):
        # Given a user with an incentive
        user, incentive = user_and_incentive
        incentivized_action = incentive.incentive_organizations[0].action

        incentive_fulfillment = factories.IncentiveFulfillmentFactory.create(
            member_track=user.current_member_track,
            incentive=incentive,
            incentivized_action=incentivized_action,
        )

        with patch(
            "incentives.repository.incentive_fulfillment.IncentiveFulfillmentRepository.get_all_by_ids"
        ) as mock_request:
            IncentiveOrganizationService().get_incentive_fulfillments(
                [incentive_fulfillment.id]
            )

            mock_request.assert_called_once_with([incentive_fulfillment.id])


class TestCreateIncentiveFulfillmentCsv:
    def test_create_incentive_fulfillment_csv(self, user_and_incentive, factories):
        # Output incentive fulfillment data into csv
        user, incentive = user_and_incentive
        incentivized_action = incentive.incentive_organizations[0].action

        incentive_fulfillment = factories.IncentiveFulfillmentFactory.create(
            member_track=user.current_member_track,
            incentive=incentive,
            incentivized_action=incentivized_action,
            date_earned=datetime.datetime.utcnow(),
            date_issued=datetime.datetime.utcnow() - datetime.timedelta(weeks=2),
        )

        records = IncentiveOrganizationService().get_incentive_fulfillments(
            [incentive_fulfillment.id]
        )

        report = IncentiveOrganizationService().create_incentive_fulfillment_csv(
            records
        )

        # Confirm CSV has correct rows and data
        list_report = list(csv.DictReader(report))

        assert len(list_report) == 1
        csv_row_1 = list_report[0]

        assert csv_row_1["id"] == str(incentive_fulfillment.id)
        assert csv_row_1["member_id"] == str(incentive_fulfillment.member_track.user_id)
        assert (
            csv_row_1["member_email"] == incentive_fulfillment.member_track.user.email
        )
        assert (
            csv_row_1["member_first_name"]
            == incentive_fulfillment.member_track.user.first_name
        )
        assert (
            csv_row_1["member_last_name"]
            == incentive_fulfillment.member_track.user.last_name
        )
        address = incentive_fulfillment.member_track.user.member_profile.address
        assert csv_row_1["member_street_address"] == address.street_address
        assert csv_row_1["member_city"] == address.city
        assert csv_row_1["member_zip_code"] == address.zip_code
        assert csv_row_1["member_state"] == address.state
        assert (
            csv_row_1["member_country"]
            == incentive_fulfillment.member_track.user.country.name
        )
        assert csv_row_1["incentive_name"] == incentive_fulfillment.incentive.name
        assert csv_row_1["vendor"] == incentive_fulfillment.incentive.vendor
        assert csv_row_1["amount"] == str(incentive_fulfillment.incentive.amount)
        assert (
            csv_row_1["incentivized_action"]
            == incentive_fulfillment.incentivized_action.value
        )
        assert csv_row_1["track"] == incentive_fulfillment.member_track.name
        assert csv_row_1["status"] == incentive_fulfillment.status
        assert csv_row_1["date_earned"] == incentive_fulfillment.date_earned.strftime(
            "%Y-%m-%d %H:%M:%S.%f"
        )
        assert csv_row_1["date_issued"] == incentive_fulfillment.date_issued.strftime(
            "%Y-%m-%d %H:%M:%S.%f"
        )


class TestReportIncentivesForUser:
    def test_report_incentives_for_user__has_offboarding_no_ca_intro(
        self, user_and_offboarding_incentive
    ):
        # given a member with an offboarding incentive
        incentive_user, incentive = user_and_offboarding_incentive
        with patch("utils.braze.send_incentive") as mock_request:
            # when we send an incentive
            report_incentives_for_user(
                user_id=incentive_user.id,
                track="pregnancy",
            )
            # the braze call is made with only offboarding
            mock_request.assert_called_once_with(
                external_id=incentive_user.esp_id,
                incentive_id_ca_intro=None,
                incentive_id_offboarding=incentive.id,
            )

    def test_report_incentives_for_user__has_ca_intro_no_offboarding(
        self, user_and_ca_intro_incentive
    ):
        # given a member with a ca intro incentive
        incentive_user, incentive = user_and_ca_intro_incentive
        with patch("utils.braze.send_incentive") as mock_request:
            # when we send an incentive
            report_incentives_for_user(
                user_id=incentive_user.id,
                track="pregnancy",
            )
            # then braze call is made with only ca intro populated
            mock_request.assert_called_once_with(
                external_id=incentive_user.esp_id,
                incentive_id_ca_intro=incentive.id,
                incentive_id_offboarding=None,
            )

    def test_report_incentives_for_user__has_ca_intro_and_offboarding(
        self, user_and_ca_intro_incentive_and_offboarding_incentive
    ):
        # given a member with a ca intro incentive and offboarding assessment incentive
        (
            incentive_user,
            ca_intro_incentive,
            offboarding_incentive,
        ) = user_and_ca_intro_incentive_and_offboarding_incentive

        with patch("utils.braze.send_incentive") as mock_request:
            # when we send an incentive
            report_incentives_for_user(
                user_id=incentive_user.id,
                track="pregnancy",
            )
            # then braze call is made with both incentives populated
            mock_request.assert_called_once_with(
                external_id=incentive_user.esp_id,
                incentive_id_ca_intro=ca_intro_incentive.id,
                incentive_id_offboarding=offboarding_incentive.id,
            )

    def test_report_incentives_for_user__no_incentives(self, factories):
        # given a member with no incentives
        user = factories.EnterpriseUserFactory()
        factories.MemberProfileFactory.create(user=user, country_code="AR")
        with patch("incentives.services.incentive_organization.log.info") as mock_info:
            # when we send an incentive
            report_incentives_for_user(
                user_id=user.id,
                track="pregnancy",
            )
            # then we log that no incentives were sent
            mock_info.assert_called_with(
                "Member not currently eligible for incentives for this track. Not sending incentives to Braze.",
                user_id=user.id,
                track="pregnancy",
            )

    def test_report_incentives_for_user__invalid_user_id(self, invalid_user_id):
        # given a member with an invalid user_id
        with patch("incentives.services.incentive_organization.log.warn") as mock_warn:
            # when we send an incentive with an invalid member_id
            report_incentives_for_user(
                user_id=invalid_user_id,
                track="pregnancy",
            )
            # then we log a warning
            mock_warn.assert_called_once_with(
                "Invalid user_id. No incentive was sent to Braze.",
                user_id=invalid_user_id,
            )


class TestAutoCreateIncentivesAdminViews:
    def test_get_welcome_box_incentive_orgs_by_organization(
        self,
        incentive_user,
        amazon_incentives,
        create_incentive_org,
    ):
        ca_intro_incentive_org_data = (
            IncentiveOrganizationService().get_ca_intro_incentive_organizations_auto_created()
        )

        incentive_orgs = IncentiveOrganizationService().get_welcome_box_incentive_orgs_by_organization(
            incentive_user.current_member_track.client_track.organization.id
        )
        assert len(incentive_orgs) == 0

        # create incentive orgs that conflict with incentive gift card rows
        create_incentive_org(
            incentive_action=IncentiveAction.CA_INTRO,
            track=ca_intro_incentive_org_data[0].get("track"),
        )
        incentive_orgs = IncentiveOrganizationService().get_welcome_box_incentive_orgs_by_organization(
            incentive_user.current_member_track.client_track.organization.id
        )
        assert len(incentive_orgs) == 1

        create_incentive_org(
            incentive_action=IncentiveAction.CA_INTRO,
            track=ca_intro_incentive_org_data[1].get("track"),
        )
        incentive_orgs = IncentiveOrganizationService().get_welcome_box_incentive_orgs_by_organization(
            incentive_user.current_member_track.client_track.organization.id
        )

        assert len(incentive_orgs) == 2

        # create another incentive org that does not satisfy welcome box query
        create_incentive_org(
            incentive_action=IncentiveAction.CA_INTRO, track=TrackName.GENERIC
        )
        incentive_orgs = IncentiveOrganizationService().get_welcome_box_incentive_orgs_by_organization(
            incentive_user.current_member_track.client_track.organization.id
        )
        assert len(incentive_orgs) == 2

    def test_create_incentive_organizations_on_organization_change_no_conflicts(
        self,
        incentive_user,
        amazon_incentives,
        default_organization,
    ):
        IncentiveOrganizationService().create_incentive_organizations_on_organization_change(
            default_organization
        )

        auto_created_incentive_orgs = (
            IncentiveOrganizationService().get_incentive_orgs_auto_created()
        )
        incentive_orgs = db.session.query(IncentiveOrganization).all()
        assert len(auto_created_incentive_orgs) == len(incentive_orgs)

    def test_create_incentive_organizations_on_organization_change_with_conflicts(
        self, incentive_user, amazon_incentives, create_incentive_org
    ):
        # create a row that would've been auto created
        create_incentive_org(
            incentive_type=IncentiveType.GIFT_CARD,
            incentive_action=IncentiveAction.CA_INTRO,
            track=TrackName.PREGNANCY,
        )

        IncentiveOrganizationService().create_incentive_organizations_on_organization_change(
            incentive_user.current_member_track.client_track.organization
        )
        auto_created_incentive_orgs = (
            IncentiveOrganizationService().get_incentive_orgs_auto_created()
        )
        incentive_orgs = db.session.query(IncentiveOrganization).all()
        # should be the same length, despite an existing row already existing
        assert len(auto_created_incentive_orgs) == len(incentive_orgs)


class TestInactivateIncentiveOrgsOnIncentiveChange:
    @pytest.mark.parametrize(
        argnames="incentive_type,num_disabled",
        argvalues=[
            (IncentiveType.GIFT_CARD, 2),
            (IncentiveType.WELCOME_BOX, 1),
            ("ALL", 3),
        ],
    )
    def test_inactivate_incentive_orgs_on_incentive_change(
        self, incentive_type, num_disabled, factories, create_incentive_org
    ):
        # given an org and 3 incentive-orgs
        org = factories.OrganizationFactory()
        org.welcome_box_allowed = True
        org.gift_card_allowed = True
        create_incentive_org(
            organization=org,
            incentive_type=IncentiveType.GIFT_CARD,
            incentive_action=IncentiveAction.CA_INTRO,
            track=TrackName.PREGNANCY,
        )
        create_incentive_org(
            organization=org,
            incentive_type=IncentiveType.GIFT_CARD,
            incentive_action=IncentiveAction.OFFBOARDING_ASSESSMENT,
            track=TrackName.EGG_FREEZING,
        )
        create_incentive_org(
            organization=org,
            incentive_type=IncentiveType.WELCOME_BOX,
            incentive_action=IncentiveAction.CA_INTRO,
            track=TrackName.POSTPARTUM,
        )

        # when we call inactivate_incentive_orgs_on_incentive_change
        incentive_orgs_disabled = IncentiveOrganizationService().inactivate_incentive_orgs_on_incentive_change(
            organization=org, incentive_type=incentive_type
        )
        # then we have the expected number of results
        assert len(incentive_orgs_disabled) == num_disabled
        # and each incentive_org is inactive
        for incentive_org in incentive_orgs_disabled:
            assert not incentive_org.active


class TestUpdateBrazeIncentiveOffboardingForOrgUsers:
    @patch("braze.client.BrazeClient.track_users")
    def test_update_braze_incentive_offboarding_for_org_users(
        self, mock_braze_track_users, incentive_user, create_incentive_org, factories
    ):
        # given users with incentives live on an org
        user_1 = incentive_user
        org = factories.OrganizationFactory()
        factories.MemberTrackFactory.create(
            user=user_1,
            client_track=factories.ClientTrackFactory(organization=org),
            name=TrackName.PREGNANCY,
        )
        # and incentive-org rows
        incentive_org_1 = create_incentive_org(
            organization=org,
            incentive_type=IncentiveType.GIFT_CARD,
            incentive_action=IncentiveAction.OFFBOARDING_ASSESSMENT,
            track=TrackName.PREGNANCY,
        )
        create_incentive_org(
            organization=org,
            incentive_type=IncentiveType.GIFT_CARD,
            incentive_action=IncentiveAction.OFFBOARDING_ASSESSMENT,
            track=TrackName.POSTPARTUM,
        )

        expected_attributes = [
            braze.client.BrazeUserAttributes(
                external_id=user_1.esp_id,
                attributes={
                    "incentive_id_offboarding": incentive_org_1.incentive_id,
                },
            ),
        ]

        # when we call update_braze_incentive_offboarding_for_org_users
        update_braze_incentive_offboarding_for_org_users(org.id)
        # then braze.track_user is called
        mock_braze_track_users.assert_called_once_with(
            user_attributes=expected_attributes
        )


class TestGetAndMarkIncentiveAsSeen:
    @patch("incentives.services.incentive_organization.log.info")
    def test_get_and_mark_incentive_as_seen__no_incentive(
        self, mock_log_info, factories
    ):
        user = factories.DefaultUserFactory.create()
        factories.MemberProfileFactory.create(
            user_id=user.id,
        )
        track = factories.MemberTrackFactory.create(user=user, name=TrackName.PREGNANCY)

        get_and_mark_incentive_as_seen(user.id, track.name, track.id, call_from="test")
        assert mock_log_info.call_args[0][0] == "Incentive not found"

    @patch("incentives.services.incentive_organization.log.info")
    def test_get_and_mark_incentive_as_seen__has_incentive(
        self, mock_log_info, factories, create_incentive_org
    ):
        user = factories.DefaultUserFactory.create()
        org = factories.OrganizationFactory(name="I love goats")
        factories.MemberProfileFactory.create(user_id=user.id, country_code="US")

        track = factories.MemberTrackFactory.create(
            user=user,
            name=TrackName.PREGNANCY,
            client_track=factories.ClientTrackFactory(organization=org),
        )

        create_incentive_org(
            incentive_action=IncentiveAction.CA_INTRO,
            track=TrackName.PREGNANCY,
            organization=org,
        )

        incentive_fulfillment = get_and_mark_incentive_as_seen(
            user.id, track.name, track.id, call_from="test"
        )

        assert (
            mock_log_info.call_args[0][0]
            == IncentiveFulfillmentResourceMsg.SUCCESSFUL_INCENTIVE_SEEN
        )
        assert incentive_fulfillment.status == IncentiveStatus.SEEN
