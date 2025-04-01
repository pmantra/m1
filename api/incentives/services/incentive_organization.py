import csv
import datetime
import io
from collections import defaultdict
from typing import List, Optional

import ddtrace
from sqlalchemy import or_

from appointments.models.appointment import Appointment
from appointments.models.schedule import Schedule
from authn.models.user import User
from incentives.models.incentive import (
    IncentiveAction,
    IncentiveOrganization,
    IncentiveOrganizationCountry,
    IncentiveType,
)
from incentives.models.incentive_fulfillment import (
    IncentiveFulfillment,
    IncentiveStatus,
)
from incentives.repository.incentive import IncentiveRepository
from incentives.repository.incentive_fulfillment import IncentiveFulfillmentRepository
from incentives.repository.incentive_organization import IncentiveOrganizationRepository
from models.enterprise import Organization
from models.profiles import MemberProfile
from models.tracks import MemberTrack
from models.tracks.client_track import ClientTrack
from models.tracks.track import TrackName
from storage.connection import db
from tasks.queues import job
from tracks import service as tracks_svc
from tracks.service import TrackSelectionService
from utils import braze
from utils.log import logger

log = logger(__name__)

INCENTIVES_IMPLEMENTATION_DATE = datetime.datetime(2023, 12, 19, 0, 0, 0)


class InvalidIncentiveOrganizationException(Exception):
    ...


class OrganizationNotEligibleForGiftCardException(
    InvalidIncentiveOrganizationException
):
    message = "This organization is not allowed to receive gift cards."


class OrganizationNotEligibleForWelcomeBoxException(
    InvalidIncentiveOrganizationException
):
    message = "This organization is not allowed to receive welcome boxes."


class IncentiveOrgAlreadyExistsException(InvalidIncentiveOrganizationException):
    message = "This organization already has an active incentive configured for this action and track."


class IncentiveUsedOnIncentiveOrgException(InvalidIncentiveOrganizationException):
    message = "This incentive is in use on the Incentive-Organization page. Please remove it before marking this Incentive as `inactive`"


class InvalidIncentiveIdException(InvalidIncentiveOrganizationException):
    message = "The provided incentive id is invalid"


class UserNotEligibleForIncentiveException(InvalidIncentiveOrganizationException):
    message = "User not eligible for incentive"


class UserAlreadySawIncentiveException(InvalidIncentiveOrganizationException):
    message = "User already saw incentive"


class UserAlreadyFulfilledIncentiveException(InvalidIncentiveOrganizationException):
    message = "User already fulfilled incentive. An incentive_fulfillment row with status EARNED, PROCESSING or FULFILLED"


class InvalidIncentiveFulfillmentException(Exception):
    ...


class IncentiveStatusFulfilledDateIssuedRequiredException(
    InvalidIncentiveFulfillmentException
):
    message = 'Date Issued is required for Incentive Status "FULFILLED"'


class IncentiveStatusSeenEarnedProcessingDateIssuedNotEmptyException(
    InvalidIncentiveFulfillmentException
):
    message = 'Date Issued does not apply for Incentive Status "SEEN", "EARNED", or "PROCESSING"'


class IncentiveStatusFulfilledDateEarnedDateIssuedRequiredException(
    InvalidIncentiveFulfillmentException
):
    message = (
        'Date Earned and Date Issued are required for Incentive Status "FULFILLED"'
    )


class IncentiveStatusEarnedProcessingDateEarnedRequiredException(
    InvalidIncentiveFulfillmentException
):
    message = 'Date Earned is required Incentive Status "EARNED" or "PROCESSING"'


class IncentiveStatusSeenDateEarnedNotEmptyException(
    InvalidIncentiveFulfillmentException
):
    message = 'Date Earned does not apply for Incentive Status "SEEN"'


class IncentiveFulfillmentResourceMsg(str):
    SUCCESSFUL_INCENTIVE_SEEN = "Successfully recorded that member saw incentive"


class IncentiveOrganizationService:
    @ddtrace.tracer.wrap()
    def validate_incentive_exists(self, incentive_id: int) -> None:
        """
        Log error with provided incentive_id and raise an IncentiveException if no incentive exists for provided incentive_id
        """
        incentive = IncentiveRepository().get(id=incentive_id)
        if not incentive:
            raise InvalidIncentiveIdException

    @ddtrace.tracer.wrap()
    def _validate_user_has_incentive(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self, user_id, incentive_id, member_track_id, incentivized_action
    ):
        track_name = (
            db.session.query(MemberTrack.name)
            .filter(MemberTrack.id == member_track_id)
            .first()
        )
        if track_name:
            track_name = track_name[0]  # As db result is a tuple (track_name,)
            incentive = self.get_user_incentive(
                user_id, incentivized_action, track_name
            )
            if incentive and incentive.id == incentive_id:
                return True
        raise UserNotEligibleForIncentiveException

    @ddtrace.tracer.wrap()
    def _validate_incentive_has_not_been_seen(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self, member_track_id, incentivized_action
    ):
        incentive_fulfillment = IncentiveFulfillmentRepository().get_by_params(
            member_track_id=member_track_id, incentivized_action=incentivized_action
        )
        if (
            incentive_fulfillment
            and incentive_fulfillment.status == IncentiveStatus.SEEN
        ):
            raise UserAlreadySawIncentiveException
        if incentive_fulfillment:  # Case when status is EARNED, PROCESSING or FULFILLED
            raise UserAlreadyFulfilledIncentiveException

    @ddtrace.tracer.wrap()
    def post_member_saw_incentive(
        self,
        user_id: int,
        incentive_id: int,
        member_track_id: int,
        incentivized_action: str,
        date_seen: datetime.datetime,
    ) -> None:
        """
        Register in the incentive_fulfillment table that user<user_id> saw incentive<incentive_id> on <date_seen>
        Raise exceptions if creating record is not possible.
        """
        # First lets validate that member is eligibile for the incentive
        self._validate_user_has_incentive(
            user_id, incentive_id, member_track_id, incentivized_action
        )

        # Next lets validate that the incentive has not been seen already
        self._validate_incentive_has_not_been_seen(member_track_id, incentivized_action)

        # Else, lets create incentive fulfillment
        incentive_fulfillment = IncentiveFulfillmentRepository().create(
            incentive_id=incentive_id,
            member_track_id=member_track_id,
            incentivized_action=incentivized_action,
            date_status_changed=date_seen,
            status=IncentiveStatus.SEEN,
        )
        db.session.commit()
        return incentive_fulfillment

    @ddtrace.tracer.wrap()
    def get_user_incentive(self, user_id, incentivized_action, track):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        Get currently active incentive for the member.
        Will search incentive_organization table based on provided
        incentivized_action and track, as well as users organization and country.
        """
        track_svc = tracks_svc.TrackSelectionService()
        user_org_id = track_svc.get_organization_id_for_user(user_id=user_id)
        if not user_org_id:
            log.info(
                "Could not find org id for user_id. Either user doesnt exist or it has no organization",
                user_id=user_id,
            )
            return None

        # Should use ProfileService when it exists
        user_country_code = (
            db.session.query(MemberProfile.country_code)
            .filter_by(user_id=user_id)
            .first()
        )
        user_country_code = (
            user_country_code[0] if user_country_code else None
        )  # Given that db result is a tuple (value,)
        if not user_country_code:
            log.info(
                "User has no country code",
                user_id=user_id,
            )
            return None

        log.info(
            "Getting incentive for user",
            user_id=user_id,
            organization_id=user_org_id,
            country_code=user_country_code,
            track=track,
            incentivized_action=incentivized_action,
        )

        incentive = IncentiveRepository().get_by_params(
            user_id=user_id,
            country_code=user_country_code,
            organization_id=user_org_id,
            incentivized_action=incentivized_action,
            track=track,
        )

        return incentive

    @ddtrace.tracer.wrap()
    def get_incentive_fulfillment(
        self, member_track_id: id, incentivized_action: IncentiveAction  # type: ignore[valid-type] # Function "builtins.id" is not valid as a type
    ) -> IncentiveFulfillment:
        return IncentiveFulfillmentRepository().get_by_params(
            member_track_id=member_track_id, incentivized_action=incentivized_action
        )

    @ddtrace.tracer.wrap()
    def set_incentive_as_earned(
        self,
        incentive_fulfillment: IncentiveFulfillment,
        date_earned: datetime.datetime,
    ) -> None:
        """
        Set an incentive_fulfillment status as earned
        """
        # Check to make sure that this incentive_fulfillment record isn't already EARNED or PROCESSING or FULFILLED,
        # we'd only want to update it if it was SEEN
        if incentive_fulfillment.status != IncentiveStatus.SEEN:
            ## DD log alert: https://app.datadoghq.com/monitors/135861056
            log.warning(
                "Failed trying to set incentive fulfillment as EARNED, its status is not SEEN",
                incentive_fulfillment_id=incentive_fulfillment.id,
                incentive_fulfillment_status=incentive_fulfillment.status,
            )
            return

        # Change incentive_fulfillment status
        IncentiveFulfillmentRepository().set_status(
            incentive_fulfillment=incentive_fulfillment,
            status=IncentiveStatus.EARNED,
            date_status_changed=date_earned,
        )
        db.session.commit()
        log.info(
            "Incentive Fulfillment status changes to EARNED",
            incentive_fulfillment_id=incentive_fulfillment.id,
            dt_earned=date_earned,
        )

    @ddtrace.tracer.wrap()
    def attempt_to_set_intro_appt_incentive_as_earned(
        self, appointment: Appointment
    ) -> None:
        log.info(
            "Attempting to set intro appt incentive as earned",
            appointment_id=appointment.id,
        )

        # Get the user id using the appointment schedule id
        user_id = (
            db.session.query(Schedule.user_id)
            .filter(Schedule.id == appointment.member_schedule_id)
            .first()
        )
        if not user_id:
            ## DD log alert: https://app.datadoghq.com/monitors/136192975
            log.warning(
                "Failed getting user from Appointment",
                appointment_id=appointment.id,
                schedule_id=appointment.member_schedule_id,
            )
            return
        user_id = user_id[0]  # As db result comes in a tuple
        user = db.session.query(User).get(user_id)

        date_incentive_earned = (
            appointment.ended_at if appointment.ended_at else datetime.datetime.utcnow()
        )

        # We can assume that, in the context of a ca intro, the incentive is associated to the member's active track with highest priority
        active_tracks = user.active_tracks
        highest_priority_track = TrackSelectionService().get_highest_priority_track(
            tracks=active_tracks
        )
        highest_priority_track_id = highest_priority_track.id  # type: ignore[union-attr] # Item "None" of "Optional[MemberTrack]" has no attribute "id"

        self.attempt_to_set_incentive_as_earned(
            user_id=user_id,
            member_track_id=highest_priority_track_id,
            incentivized_action=IncentiveAction.CA_INTRO,
            date_incentive_earned=date_incentive_earned,
        )

    @ddtrace.tracer.wrap()
    def _check_for_recent_offboarding_incentive_fulfillment_records(
        self, user_id: int, track_name: str
    ) -> List[IncentiveFulfillment]:
        log.info(
            "Checking for incentive-fulfillment records earned within the last 2 months.",
            user_id=user_id,
            track_name=track_name,
        )
        two_months_ago = datetime.datetime.utcnow() - datetime.timedelta(days=60)
        return (
            db.session.query(IncentiveFulfillment.id)
            .join(MemberTrack)
            .filter(
                MemberTrack.name == track_name,
                MemberTrack.user_id == user_id,
                IncentiveFulfillment.incentivized_action
                == IncentiveAction.OFFBOARDING_ASSESSMENT,
                IncentiveFulfillment.date_earned > two_months_ago,
            )
            .first()
        )

    @ddtrace.tracer.wrap()
    def _get_member_track_id_when_offboarding_assessment_completed(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self, user_id: int, track_name: str
    ):
        """
        Given user_id and track_name, find the MemberTrack that should be associated with the new incentive_fulfillment.

        If a member has more than one track with the same track_name (e.g. member enrolled in a pregnancy track twice),
        we choose the track with the following filters:

        1. Filter out tracks with an end_date before Dec 1, 2023. Some members may have recieved incentives before we created
        incentive_fulfillments, and we did not backfill data for those members. We assume no one should now recieve an incentive for
        offboarding a track ended so long ago.

        2. Filter out tracks with incentive_fulfillment, because that means a track for which an offboarding incentive has already
        been earned (as rows for offboarding incentives at the moment exist in that table only with status EARNED, PROCESSING or FULFILLED).

        3. Pick the earliest created track from what remains. If a member has two pregnancy tracks, and the two don't have an incentive_fulfillment
        row, we will assume that the member is completing the offboarding assessment for the first track.
        """
        incentive_fulfillment_backfill_cutoff = datetime.datetime(2023, 12, 1)
        member_tracks = (
            db.session.query(MemberTrack)
            .filter_by(user_id=user_id, name=track_name)
            # 1. Filter out track with ended_at before Dec 1, 2023
            .filter(
                or_(
                    MemberTrack.ended_at == None,
                    MemberTrack.ended_at > incentive_fulfillment_backfill_cutoff,
                )
            )
            .all()
        )
        if not member_tracks:
            return None

        if len(member_tracks) == 1:
            return member_tracks[0].id
        else:
            tracks_with_no_incentive_fulfillment = []
            # 2. Filter out tracks that have an incentive_fulfillment row for offboarding assessment incentive
            for member_track in member_tracks:
                incentive_fulfillment_for_track = (
                    IncentiveFulfillmentRepository().get_by_params(
                        member_track_id=member_track.id,
                        incentivized_action=IncentiveAction.OFFBOARDING_ASSESSMENT,
                    )
                )
                if not incentive_fulfillment_for_track:
                    tracks_with_no_incentive_fulfillment.append(member_track)
            if not tracks_with_no_incentive_fulfillment:
                ## DD log alert: https://app.datadoghq.com/monitors/136411447
                log.warning(
                    "Failed to find member_track_id, could not find a track that has no incentive_fulfillment row",
                    user_id=user_id,
                    track_name=track_name,
                    member_tracks_ids=[mt.id for mt in member_tracks],
                )
                return

            # 3. Choose oldest track
            oldest_track = (
                (
                    db.session.query(MemberTrack).filter(
                        MemberTrack.user_id == user_id,
                        MemberTrack.name == track_name,
                        MemberTrack.id.in_(
                            [mt.id for mt in tracks_with_no_incentive_fulfillment]
                        ),
                    )
                )
                .order_by(MemberTrack.created_at.asc())
                .first()
            )
            return oldest_track.id

    def on_assessment_completion(
        self, user_id: int, slug: str, date_completed: datetime.datetime
    ) -> None:
        if not self._is_an_offboarding_assessment(slug):
            return

        assessment_track = self._get_assessment_track_name(slug)
        if not assessment_track:
            return

        self.attempt_to_set_offboarding_assessment_incentive_as_earned(
            user_id=user_id,
            track_name=assessment_track,
            date_incentive_earned=date_completed,
        )

    @staticmethod
    def _is_an_offboarding_assessment(slug: str) -> bool:
        # To be replaced by use of assessment_track table in EPEN-3959
        valid_offboarding_assessments_slugs = [
            "postpartum-offboarding",
            "menopause-offboarding",
            "fertility-offboarding",
            "ttc-offboarding",
            "egg-freezing-offboarding",
            "bms-offboarding",
        ]
        return slug in valid_offboarding_assessments_slugs

    @staticmethod
    def _get_assessment_track_name(slug: str) -> Optional[str]:
        # To be replaced by use of assessment_track table in EPEN-3959
        assessment_slugs_to_track_name = {
            "postpartum-offboarding": TrackName.POSTPARTUM.value,
            "menopause-offboarding": TrackName.MENOPAUSE.value,
            "fertility-offboarding": TrackName.FERTILITY.value,
            "ttc-offboarding": TrackName.TRYING_TO_CONCEIVE.value,
            "egg-freezing-offboarding": TrackName.EGG_FREEZING.value,
            "bms-offboarding": TrackName.BREAST_MILK_SHIPPING.value,
        }
        if slug in assessment_slugs_to_track_name:
            return assessment_slugs_to_track_name[slug]
        return None

    @ddtrace.tracer.wrap()
    def attempt_to_set_offboarding_assessment_incentive_as_earned(
        self, user_id: int, track_name: str, date_incentive_earned: datetime.datetime
    ) -> None:
        log.info(
            "Attempting to set offboarding assesment incentive as earned",
            user_id=user_id,
            track_name=track_name,
            date_incentive_earned=str(date_incentive_earned),
        )
        recently_created_fulfillment_record = (
            self._check_for_recent_offboarding_incentive_fulfillment_records(
                user_id=user_id, track_name=track_name
            )
        )
        if recently_created_fulfillment_record:
            log.info(
                "An Offboarding Assessment incentive-fulfillment record has been earned within the last 2 months for this user on this track. We can assume this is a duplicate submission and we will not create another incentive-fulfillment record.",
                user_id=user_id,
                track_name=track_name,
            )
            return
        member_track_id = (
            self._get_member_track_id_when_offboarding_assessment_completed(
                user_id=user_id, track_name=track_name
            )
        )
        if not member_track_id:
            # DD log alert: https://app.datadoghq.com/monitors/136411678
            log.warning(
                "Could not find member track id when setting offboarding assessment incentive to earned",
                user_id=user_id,
                track_name=track_name,
            )
            return

        self.attempt_to_set_incentive_as_earned(
            user_id=user_id,
            member_track_id=member_track_id,
            incentivized_action=IncentiveAction.OFFBOARDING_ASSESSMENT,
            date_incentive_earned=date_incentive_earned,
        )

    @ddtrace.tracer.wrap()
    def attempt_to_set_incentive_as_earned(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self,
        user_id: int,
        member_track_id: int,
        incentivized_action: IncentiveAction,
        date_incentive_earned=datetime.datetime,
    ) -> None:
        log.info(
            "Attempting to set incentive as earned",
            user_id=user_id,
            member_track_id=member_track_id,
            incentivized_action=incentivized_action,
            date_incentive_earned=date_incentive_earned,
        )

        # Retrieve incentive_fulfillment associated to the member's track and incentivized_action
        incentive_fulfillment = (
            IncentiveOrganizationService().get_incentive_fulfillment(
                member_track_id=member_track_id,
                incentivized_action=incentivized_action,
            )
        )

        if incentive_fulfillment:
            # Set incentive as earned (as long as it has not been earned yet). Do nothing else.
            if incentive_fulfillment.status == IncentiveStatus.SEEN:
                IncentiveOrganizationService().set_incentive_as_earned(
                    incentive_fulfillment=incentive_fulfillment,
                    date_earned=date_incentive_earned,
                )
            else:
                log.info(
                    "Not marking as earned. Incentive has already been earned",
                    incentive_fulfillment_id=incentive_fulfillment.id,
                    incentive_fulfillment_status=incentive_fulfillment.status,
                    user_id=user_id,
                    member_track_id=member_track_id,
                    incentivized_action=incentivized_action,
                    date_incentive_earned=date_incentive_earned,
                )
        else:
            """
            If no incentive_fulfillment is found, that means that either:
            a) member was never eligible for one, which is totally fine.
            b) member was eligible for an incentive, but somehow an incentive_fulfillment recording they saw the incentive was not created.
            b.1) in the case of ca_intro, the incentive_fulfillment should have been created, but there are a couple valid cases:
            b.1.a) the member is a transition. these members are not eligible for incentives and should not have incentive-fulfillment records
            b.1.b) the member is not a transition and started their track prior incentives launch date (12/19/2023). these members are eligible for incentives and should be added as EARNED
            b.1.c) the member is not a transition and started their track after incentives launch date. after alerting on these members for a month,
                   these members are either members without country at onboarding or members who dropped out of onboarding without seeing the incentive.
                   both of these should be eligible for incentives, so we will add incentive-fulfillment records as EARNED.
            b.2) in the case of offboarding_assessment, this is expected, as we are currently not creating incentive_fulfillment with status SEEN as discussed in KICK-1576

            To warn about b.1), the fact is its not possible to get a member's incentive at the moment of their onboarding (when they should have had the incentive_fulfilmment with SEEN created).
            A walk around is to check if the member has an incentive today.
            We acknowledge that this could raise a false alarm,
            given that it could be the case that the incentive was deleted or expired between the point the member saw the incentive and they earned it.
            Ultimately, we hope that this check for scenario b.1) is unneccesary and that it can be removed. Will do so in KICK-1588
            """

            member_track_name_and_created_at = (
                db.session.query(MemberTrack.name, MemberTrack.created_at)
                .filter_by(id=member_track_id)
                .first()
            )
            if not member_track_name_and_created_at:
                # DD log alert: https://app.datadoghq.com/monitors/136411795
                log.info("Could not find track name", member_track_id=member_track_id)
                return
            member_track_name = member_track_name_and_created_at[
                0
            ]  # As results comes in a tuple from the db
            member_track_created_at = member_track_name_and_created_at[1]

            user_incentive = IncentiveOrganizationService().get_user_incentive(
                user_id=user_id,
                incentivized_action=incentivized_action,
                track=member_track_name,
            )
            if (
                not user_incentive
            ):  # Case where user was never eligible for the incentive, good to move on
                log.info(
                    "No incentive marked as earned as incentive_fulfillment was not found, which makes sense as user is not eligible for one",
                    member_track_id=member_track_id,
                    incentivized_action=incentivized_action,
                )
                return

            # In the case the user did have an incentive configured
            if incentivized_action == IncentiveAction.CA_INTRO:
                """
                There are a couple valid scenarios here:
                1. The user is a transition from another track. They should not be eligible for an incentive, so it's
                valid that there is no incentive_fulfillment record. We won't alert here.
                2. The user onboarded prior to our implementation of Incentives Admin Config, but is not transitioning.
                These users should be added to the incentive_fulfillment table, and we'll mark them as EARNED without a
                SEEN record.
                3. If a user doesn't fit into one of these scenarios, we assume that they did not have a country during
                onboarding (or another valid reason). We will mark these users as EARNED without a SEEN record, but log
                a warning. TODO: fix enrollments flow so no users are without a country, and stop adding incentive-
                fulfillment records for users in this scenario (alert instead).
                """

                # check to see if user is transitioning tracks
                # they would have an inactive track that ended the same day their active track started
                most_recent_inactive_track = (
                    db.session.query(MemberTrack.ended_at)
                    .filter(MemberTrack.user_id == user_id)
                    .order_by(MemberTrack.ended_at.desc())
                    .first()
                )
                most_recent_inactive_track = most_recent_inactive_track[0]
                if most_recent_inactive_track:
                    if (
                        most_recent_inactive_track.date()
                        == member_track_created_at.date()
                    ):
                        log.info(
                            "Member is transitioning tracks. They do not have an incentive-fulfillment record because they are not eligible for incentives.",
                            user_incentive_id=user_incentive.id,
                            incentivized_action=incentivized_action,
                            member_track_id=member_track_id,
                            track_name=member_track_name,
                            user_id=user_id,
                            inactive_track_end_date=most_recent_inactive_track,
                            current_track_start_date=member_track_created_at,
                        )
                        return

                # we know remaining users are not transitions
                # check to see if user started track prior to implementation date
                if member_track_created_at < INCENTIVES_IMPLEMENTATION_DATE:
                    log.info(
                        "Member has no incentive-fulfillment record, is not a transition, started track prior to implementation date, and is currently eligible for an incentive. Will create EARNED incentive-fulfillment record.",
                        user_incentive_id=user_incentive.id,
                        incentivized_action=incentivized_action,
                        member_track_id=member_track_id,
                        track_name=member_track_name,
                        user_id=user_id,
                    )
                else:
                    log.warning(
                        "Member has no incentive-fulfillment record, is not a transition, started track after implementation, and is currently eligible for an incentive. Will create EARNED incentive-fulfillment record.",
                        user_incentive_id=user_incentive.id,
                        incentivized_action=incentivized_action,
                        member_track_id=member_track_id,
                        track_name=member_track_name,
                        user_id=user_id,
                    )
                incentive_fulfillment = IncentiveFulfillmentRepository().create(
                    incentive_id=user_incentive.id,
                    member_track_id=member_track_id,
                    incentivized_action=incentivized_action,
                    date_status_changed=date_incentive_earned,
                    status=IncentiveStatus.EARNED,
                )
                db.session.commit()
                log.info(
                    "Successfully created incentive_fulfillment for an earned CA intro incentive",
                    incentive_fulfillment_id=incentive_fulfillment.id,
                    member_track_id=member_track_id,
                    incentivized_action=incentivized_action,
                    date_earned=date_incentive_earned,
                )

            elif incentivized_action == IncentiveAction.OFFBOARDING_ASSESSMENT:
                # We need to create the incentive_fulfillment here, and mark it as EARNED straight away
                incentive_fulfillment = IncentiveFulfillmentRepository().create(
                    incentive_id=user_incentive.id,
                    member_track_id=member_track_id,
                    incentivized_action=incentivized_action,
                    date_status_changed=date_incentive_earned,
                    status=IncentiveStatus.EARNED,
                )
                db.session.commit()
                log.info(
                    "Successfully created incentive_fulfillment for an earned offboarding assessment incentive",
                    incentive_fulfillment_id=incentive_fulfillment.id,
                    member_track_id=member_track_id,
                    incentivized_action=incentivized_action,
                    date_earned=date_incentive_earned,
                )

    @ddtrace.tracer.wrap()
    def validate_incentive_not_used_when_deactivating(self, incentive_id, active):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # if we are going from active -> inactive
        if not active:
            incentive_in_use = (
                db.session.query(IncentiveOrganization)
                .filter(
                    IncentiveOrganization.incentive_id == incentive_id,
                    IncentiveOrganization.active == True,
                )
                .first()
            )
            if incentive_in_use:
                exception = IncentiveUsedOnIncentiveOrgException()
                log.info(
                    exception.message,
                    incentive_id=incentive_id,
                )
                raise exception

    @ddtrace.tracer.wrap()
    def check_eligibility(self, organization, incentive):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if incentive.type == IncentiveType.WELCOME_BOX:
            if not organization.welcome_box_allowed:
                exception = OrganizationNotEligibleForWelcomeBoxException()
                log.info(
                    exception.message,
                    organization_id=organization.id,
                    incentive_id=incentive.id,
                    incentive_type=incentive.type,
                    welcome_box_allowed=organization.welcome_box_allowed,
                )
                raise exception
        else:
            if not organization.gift_card_allowed:
                exception = OrganizationNotEligibleForGiftCardException()  # type: ignore[assignment] # Incompatible types in assignment (expression has type "OrganizationNotEligibleForGiftCardException", variable has type "OrganizationNotEligibleForWelcomeBoxException")
                log.info(
                    exception.message,
                    organization_id=organization.id,
                    incentive_id=incentive.id,
                    incentive_type=incentive.type,
                    gift_card_allowed=organization.gift_card_allowed,
                )
                raise exception

    @ddtrace.tracer.wrap()
    def check_for_duplicates(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self, organization, action, track_name, active, incentive_organization_id=None
    ):
        """
        this is used for both edits and creates
        - on create, this incentive_organization record does not yet exist, so there will
        not be an incentive_organization_id
        - on edit, the incentive_organization record exists, so we need to confirm
        that no other active incentive_organization records exist with the same organization,
        incentivized action, and track
        """
        if active:
            existing_incentive_org_query = db.session.query(
                IncentiveOrganization
            ).filter(
                IncentiveOrganization.organization_id == organization.id,
                IncentiveOrganization.action == action,
                IncentiveOrganization.track_name == track_name,
                IncentiveOrganization.active == True,
            )
            if incentive_organization_id:
                existing_incentive_org_query = existing_incentive_org_query.filter(
                    IncentiveOrganization.id != incentive_organization_id,
                )
            existing_incentive_org = existing_incentive_org_query.first()
            if existing_incentive_org:
                exception = IncentiveOrgAlreadyExistsException()
                log.info(
                    exception.message,
                    organization_id=organization.id,
                    incentivized_action=action,
                    track=track_name,
                    incentive_organization_id=incentive_organization_id,
                    existing_incentive_org_id=existing_incentive_org.id,
                )
                raise exception

    def get_incentive_fulfillments(self, ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        log.info(
            "Getting incentive fulfillments by ids",
            incentive_fulfillments_ids=ids,
        )
        return IncentiveFulfillmentRepository().get_all_by_ids(ids)

    def create_incentive_fulfillment_csv(self, incentive_fulfillments):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        log.info(
            "Generating csv for incentive fulfillments",
            incentive_fulfillments_ids=[i.id for i in incentive_fulfillments],
        )
        report = io.StringIO()
        writer = csv.DictWriter(
            report,
            fieldnames=[
                "id",
                "member_id",
                "member_email",
                "member_first_name",
                "member_last_name",
                "member_street_address",
                "member_city",
                "member_zip_code",
                "member_state",
                "member_country",
                "incentive_name",
                "vendor",
                "amount",
                "incentivized_action",
                "track",
                "status",
                "date_earned",
                "date_issued",
            ],
            extrasaction="ignore",
        )
        writer.writeheader()

        for record in incentive_fulfillments:
            member_track = getattr(record, "member_track", {})
            user = getattr(member_track, "user", {})
            user_country = getattr(user, "country", {})
            member_profile = getattr(user, "member_profile", {})
            address = getattr(member_profile, "address", {})
            writer.writerow(
                {
                    "id": record.id,
                    "member_id": getattr(member_track, "user_id", ""),
                    "member_email": getattr(user, "email", ""),
                    "member_first_name": getattr(user, "first_name", ""),
                    "member_last_name": getattr(user, "last_name", ""),
                    "member_street_address": getattr(address, "street_address", ""),
                    "member_city": getattr(address, "city", ""),
                    "member_zip_code": getattr(address, "zip_code", ""),
                    "member_state": getattr(address, "state", ""),
                    "member_country": getattr(user_country, "name", ""),
                    "incentive_name": record.incentive.name,
                    "vendor": record.incentive.vendor,
                    "amount": record.incentive.amount,
                    "incentivized_action": record.incentivized_action.value,
                    "track": getattr(member_track, "name", ""),
                    "status": record.status,
                    "date_earned": record.date_earned,
                    "date_issued": record.date_issued,
                }
            )
        report.seek(0)
        return report

    def get_ca_intro_incentive_organizations_auto_created(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        amazon_25_id = (
            IncentiveRepository().get_incentive_by_name("$25 Amazon Gift Card").id
        )

        # United Arab Emirates, Australia, Canada, Germany, Spain, France, United Kingdom, Italy, Japan, Mexico, Sweden, Singapore, United States
        country_codes = [
            "AE",
            "AU",
            "CA",
            "DE",
            "ES",
            "FR",
            "GB",
            "IT",
            "JP",
            "MX",
            "SE",
            "SG",
            "US",
        ]
        return [
            {
                "incentivized_action": IncentiveAction.CA_INTRO,
                "incentive_id": amazon_25_id,
                "track": TrackName.PREGNANCY,
                "countries": country_codes,
            },
            {
                "incentivized_action": IncentiveAction.CA_INTRO,
                "incentive_id": amazon_25_id,
                "track": TrackName.POSTPARTUM,
                "countries": country_codes,
            },
        ]

    def get_offboarding_assessment_incentive_organizations_auto_created(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        amazon_20_id = (
            IncentiveRepository().get_incentive_by_name("$20 Amazon Gift Card").id
        )

        # United Arab Emirates, Australia, Canada, Germany, Spain, France, United Kingdom, Italy, Japan, Mexico, Sweden, Singapore, United States
        country_codes = [
            "AE",
            "AU",
            "CA",
            "DE",
            "ES",
            "FR",
            "GB",
            "IT",
            "JP",
            "MX",
            "SE",
            "SG",
            "US",
        ]
        return [
            {
                "incentivized_action": IncentiveAction.OFFBOARDING_ASSESSMENT,
                "incentive_id": amazon_20_id,
                "track": TrackName.POSTPARTUM,
                "countries": country_codes,
            },
            {
                "incentivized_action": IncentiveAction.OFFBOARDING_ASSESSMENT,
                "incentive_id": amazon_20_id,
                "track": TrackName.FERTILITY,
                "countries": country_codes,
            },
            {
                "incentivized_action": IncentiveAction.OFFBOARDING_ASSESSMENT,
                "incentive_id": amazon_20_id,
                "track": TrackName.TRYING_TO_CONCEIVE,
                "countries": country_codes,
            },
        ]

    def get_incentive_orgs_auto_created(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return [
            *self.get_ca_intro_incentive_organizations_auto_created(),
            *self.get_offboarding_assessment_incentive_organizations_auto_created(),
        ]

    # Determine if there are existing welcome box incentive organizations that would prevent
    # the user from enabling the gift card incentives
    def get_welcome_box_incentive_orgs_by_organization(self, organization_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # Get the CA intro incentive organization data (which is used to automatically create incentive organizations associated with incentive gift cards)
        # This will indicate what tracks and incentive actions we should query for below
        # Return any welcome box incentives for those tracks and actions
        ca_intro_incentive_org_data = (
            self.get_ca_intro_incentive_organizations_auto_created()
        )
        log.info(
            "Getting welcome box incentive organizations based on auto created incentive orgs",
            organization_id=organization_id,
        )

        incentive_org_data = []
        for row in ca_intro_incentive_org_data:
            incentive_org = IncentiveOrganizationRepository().get_by_params(
                organization_id,
                IncentiveType.WELCOME_BOX,
                row.get("track"),
                row.get("incentivized_action"),
            )
            if incentive_org:
                incentive_org_data.append(incentive_org)

        return incentive_org_data

    def create_incentive_organizations_on_organization_change(self, organization):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        auto_created_incentive_orgs = self.get_incentive_orgs_auto_created()
        log.info(
            "Auto creating incentive org rows when gift card is set to allowed in Organization admin view",
            organization_id=organization.id,
        )

        incentive_orgs_added = []
        incentive_orgs_not_added = []
        for auto_created_incentive_org in auto_created_incentive_orgs:
            try:
                # check for conflicting incentive org rows
                self.check_for_duplicates(
                    organization=organization,
                    action=auto_created_incentive_org.get("incentivized_action"),
                    track_name=auto_created_incentive_org.get("track"),
                    active=True,
                )
            except IncentiveOrgAlreadyExistsException:
                incentive_orgs_not_added.append(auto_created_incentive_org)
                continue

            incentive_org = IncentiveOrganization(
                action=auto_created_incentive_org.get("incentivized_action"),
                incentive_id=auto_created_incentive_org.get("incentive_id"),
                track_name=auto_created_incentive_org.get("track"),
                organization_id=organization.id,
                active=True,
            )
            db.session.add(incentive_org)
            # need to commit so incentive-org exists before creating incentive-org-country
            db.session.commit()

            for country_code in auto_created_incentive_org.get("countries"):
                new_incentive_org_country = IncentiveOrganizationCountry(
                    incentive_organization_id=incentive_org.id,
                    country_code=country_code,
                )
                db.session.add(new_incentive_org_country)
                db.session.commit()

            incentive_orgs_added.append(auto_created_incentive_org)

        return (incentive_orgs_added, incentive_orgs_not_added)

    def inactivate_incentive_orgs_on_incentive_change(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self, organization, incentive_type
    ):
        log.info(
            "Inactivating incentive org rows because incentives were disabled",
            organization_id=organization.id,
            incentive_type=incentive_type,
        )
        inactive_incentive_orgs = IncentiveOrganizationRepository().get_incentive_orgs_by_incentive_type_and_org(
            organization.id, incentive_type
        )
        for incentive_org in inactive_incentive_orgs:
            incentive_org.active = False

        db.session.commit()
        return inactive_incentive_orgs


@job
def report_incentives_for_user(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    user_id: int,
    track: str,
):
    """
    looks up what incentives the user is eligible for on given track
    and sends a user's current incentive_ids to braze
    """
    user_esp_id = db.session.query(User.esp_id).filter_by(id=user_id).first()
    if not user_esp_id:
        log.warn(
            "Invalid user_id. No incentive was sent to Braze.",
            user_id=user_id,
        )
        return
    esp_id = user_esp_id[0]

    # get the incentives the user is eligible for on this track
    ca_intro_incentive = IncentiveOrganizationService().get_user_incentive(
        user_id, IncentiveAction.CA_INTRO.name.lower(), track
    )
    offboarding_incentive = IncentiveOrganizationService().get_user_incentive(
        user_id, IncentiveAction.OFFBOARDING_ASSESSMENT.name.lower(), track
    )

    # send the incentives to braze
    if ca_intro_incentive or offboarding_incentive:
        ca_intro_incentive_id = ca_intro_incentive.id if ca_intro_incentive else None
        offboarding_incentive_id = (
            offboarding_incentive.id if offboarding_incentive else None
        )
        braze.send_incentive(
            external_id=esp_id,
            incentive_id_ca_intro=ca_intro_incentive_id,
            incentive_id_offboarding=offboarding_incentive_id,
        )
        log.info(
            "Sent member's incentive to Braze",
            user_id=user_id,
            esp_id=esp_id,
            track=track,
            incentive_id_ca_intro=ca_intro_incentive_id,
            incentive_id_offboarding=offboarding_incentive_id,
        )
    else:
        log.info(
            "Member not currently eligible for incentives for this track. Not sending incentives to Braze.",
            user_id=user_id,
            track=track,
        )


@job
def update_braze_incentive_offboarding_for_org_users(organization_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    log.info(
        "Starting job to update Braze with incentive_offboarding_id for all users in org",
        organization_id=organization_id,
    )

    offboarding_incentive_orgs = (
        IncentiveOrganizationRepository().get_offboarding_incentive_orgs_for_org(
            organization_id
        )
    )

    if not offboarding_incentive_orgs:
        log.info(
            "No active offboarding assessment incentives found for this org. No updates will be sent to Braze.",
            organization_id=organization_id,
        )
        return

    offboarding_incentive_tracks = {
        incentive_org.track_name for incentive_org in offboarding_incentive_orgs
    }
    log.info(
        "Found active offboarding assessment incentives for this org",
        organization_id=organization_id,
        tracks=offboarding_incentive_tracks,
    )

    # get all active users for this org who are active in a track that offers offboarding assessments
    active_users = IncentiveOrganizationRepository().get_org_users_with_potential_offboarding_incentives(
        organization_id, offboarding_incentive_tracks
    )

    if not active_users:
        log.warn(
            "No active users for this org are on tracks that offer offboarding assessments",
            organization_id=organization_id,
            tracks=offboarding_incentive_tracks,
        )
        return

    braze_incentives = []

    # build a dictionary of all offboarding incentives for the org and look up the incentive
    # a user is eligible for rather than querying the incentives for users one by one
    offboarding_incentive_orgs_dict = defaultdict(lambda: defaultdict(dict))
    for incentive_org in offboarding_incentive_orgs:
        offboarding_incentive_orgs_dict[incentive_org.track_name.lower()][
            incentive_org.country_code
        ] = {
            "incentive_id": incentive_org.incentive_id,
        }

    for user in active_users:
        user_id = user.id
        # get highest priority track
        highest_priority_track = TrackSelectionService().get_highest_priority_track(
            user.active_tracks
        )
        if not highest_priority_track:
            log.warn(
                "User has no active tracks. Not sending incentive to Braze.",
                user_id=user_id,
                organization_id=organization_id,
            )
            continue
        highest_priority_track_name = highest_priority_track.name
        user_country_code = user.country_code
        if not user_country_code:
            log.info(
                "User has no country. Not eligible for incentives.",
                user_id=user_id,
                org_id=organization_id,
                track=highest_priority_track_name,
            )
            continue
        # look for a matching incentive_org record
        incentive_org_match = offboarding_incentive_orgs_dict[
            highest_priority_track_name
        ][user_country_code]
        if not incentive_org_match:
            log.info(
                "No offboarding incentive found for user.",
                user_id=user_id,
                org_id=organization_id,
                track=highest_priority_track_name,
                country=user_country_code,
            )
            continue
        log.info(
            "Found incentive to send to Braze.",
            user_id=user_id,
            org_id=organization_id,
            track=highest_priority_track_name,
            country=user_country_code,
            incentive_id=incentive_org_match["incentive_id"],
        )
        # append to incentive list to send to braze
        braze_incentives.append(
            braze.client.BrazeUserAttributes(
                external_id=user.esp_id,
                attributes={
                    "incentive_id_offboarding": incentive_org_match["incentive_id"],
                },
            )
        )

    if braze_incentives:
        _send_offboarding_incentives_to_braze(braze_incentives, organization_id)
    else:
        log.info(
            "No user incentives found. Not updating Braze",
            organization_id=organization_id,
        )


def _send_offboarding_incentives_to_braze(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    braze_incentives: List[braze.client.BrazeUserAttributes], organization_id: int
):
    log.info(
        "Sending incentives to Braze.",
        num_incentvies={len(braze_incentives)},
    )
    braze_client = braze.client.BrazeClient()
    resp = braze_client.track_users(user_attributes=braze_incentives)
    if resp and resp.ok:
        log.info(
            "Successfully sent updated offboarding incentives to Braze",
            organization_id=organization_id,
        )
    else:
        # https://app.datadoghq.com/monitors/138327080
        log.error(
            "Failed to send updated offboarding incentives to Braze",
            organization_id=organization_id,
        )


@job
def get_and_mark_incentive_as_seen(user_id, track_name, member_track_id, call_from):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    incentivized_action = IncentiveAction.CA_INTRO

    user_incentive = IncentiveOrganizationService().get_user_incentive(
        user_id=user_id, incentivized_action=incentivized_action, track=track_name
    )

    # trigger job to send incentives to braze
    report_incentives_for_user.delay(
        user_id=user_id, track=track_name, service_ns="incentive"
    )

    if not user_incentive:
        log.info(
            "Incentive not found",
            user_id=user_id,
            incentivized_action=incentivized_action,
            track=track_name,
            call_from=call_from,
        )

        return {}

    incentive_id = user_incentive.id

    log.info(
        "Incentive found",
        user_id=user_id,
        incentive_id=incentive_id,
        incentivized_action=incentivized_action,
        track=track_name,
        call_from=call_from,
    )

    try:
        log.info(
            "Starting to mark incentive as SEEN",
            user_id=user_id,
            incentive_id=incentive_id,
            incentivized_action=incentivized_action,
            member_track_id=member_track_id,
            call_from=call_from,
        )

        now = datetime.datetime.utcnow()
        incentive_fulfillment = (
            IncentiveOrganizationService().post_member_saw_incentive(
                user_id=user_id,
                incentive_id=incentive_id,
                member_track_id=member_track_id,
                incentivized_action=incentivized_action,
                date_seen=now,
            )
        )

        log.info(
            IncentiveFulfillmentResourceMsg.SUCCESSFUL_INCENTIVE_SEEN,
            user_id=user_id,
            incentive_id=incentive_id,
            member_track_id=member_track_id,
            incentivized_action=incentivized_action,
            incentive_fulfillment_id=incentive_fulfillment.id,
            call_from=call_from,
        )

        return incentive_fulfillment

    except UserAlreadySawIncentiveException as e:
        log.info(
            e.message,  # Equal to "User already saw incentive"
            user_id=user_id,
            incentive_id=incentive_id,
            member_track_id=member_track_id,
            incentivized_action=IncentiveAction,
            call_from=call_from,
        )

    except (
        UserNotEligibleForIncentiveException,
        UserAlreadyFulfilledIncentiveException,
    ) as e:
        # DD log monitors:
        # https://app.datadoghq.com/monitors/135012911
        # https://app.datadoghq.com/monitors/135012918
        log.warn(e.message, call_from=call_from)


@job
def update_braze_incentive_when_org_changes_in_admin(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    org_id, is_welcome_box_enabled, is_gift_card_enabled
):
    active_users_in_org = (
        db.session.query(User.esp_id)
        .filter(
            User.active == True,
        )
        .join(MemberTrack)
        .join(ClientTrack)
        .join(Organization)
        .filter(Organization.id == org_id)
        .all()
    )

    for user in active_users_in_org:
        braze.send_incentives_allowed(
            external_id=user.esp_id,
            welcome_box_allowed=is_welcome_box_enabled,
            gift_card_allowed=is_gift_card_enabled,
        )
