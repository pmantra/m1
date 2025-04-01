import uuid
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Optional

import ddtrace
from maven import feature_flags
from sqlalchemy import func

from appointments.models.payments import Credit
from authn.util.constants import (
    COMPANY_MFA_SYNC_LAUNCH_DARKLY_CONTEXT_NAME,
    COMPANY_MFA_SYNC_LAUNCH_DARKLY_KEY,
)
from common import stats
from models.tracks.client_track import ClientTrack
from models.tracks.member_track import (
    ChangeReason,
    MemberTrack,
    MemberTrackPhaseReporting,
    PregnancyMemberTrack,
    TrackChangeReason,
)
from models.tracks.track import RequiredInformation, TrackConfig, TrackName
from storage.connection import db
from utils import log
from utils.exceptions import log_exception_message
from utils.transactional import only_on_successful_commit

if TYPE_CHECKING:
    from authn.models.user import User
    from health.models.health_profile import HealthProfile

__all__ = (
    "initiate",
    "renew",
    "terminate",
    "transition",
    "on_health_profile_update",
    "initiate_transition",
    "cancel_transition",
    "finish_transition",
    "check_track_state",
    "TrackLifecycleError",
    "IncompatibleTrackError",
    "MissingInformationError",
    "MissingEmployeeError",
    "MissingClientTrackError",
    "InvalidEmployeeError",
    "InvalidOrganizationError",
    "TrackConfigurationError",
    "TrackDateConfigurationError",
    "TransitionNotConfiguredError",
    "IneligibleRenewalError",
    "InactiveTrackError",
    "TrackAlreadyRenewedError",
    "MissingVerificationError",
    "InactiveVerificationError",
    "EligibleForWrongOrgError",
    "MismatchedOrganizationError",
)

logger = log.logger(__name__)
span = ddtrace.tracer.wrap()


class TrackLifecycleError(ValueError):
    """The root Exception for Tracks Lifecycle.

    To catch all exceptions related to Tracks lifecycle, just use this one.
    """


class IncompatibleTrackError(TrackLifecycleError):
    """An error indicating the User has reached their limit in active tracks."""


class MissingInformationError(TrackLifecycleError):
    """A generic error indicating we're missing information about the user we need."""


class MissingEmployeeError(MissingInformationError):
    """An error indicating we can't locate an employee for the provided user."""


class TrackConfigurationError(TrackLifecycleError):
    """A generic error indicating the track configuration does not allow the operation."""


class TrackDateConfigurationError(TrackConfigurationError):
    """An error indicating the due_date or birthday is invalid for the track."""


class MissingClientTrackError(TrackConfigurationError):
    """An error indicating the user's organization hasn't paid for the target track."""


class InvalidEmployeeError(TrackConfigurationError):
    """An error indicating the employee provided cannot be associate to the user."""


class InvalidOrganizationError(TrackConfigurationError):
    """An error indicating the employee provided is associated to an invalid org."""


class TransitionNotConfiguredError(TrackConfigurationError):
    """An error indicating the user can't transition to the target track."""


class IneligibleRenewalError(TrackConfigurationError):
    """An error indicating the track is not configured to be renewed."""


class InactiveTrackError(TrackLifecycleError):
    """An error indicating the track to be renewed is inactive."""


class TrackAlreadyRenewedError(TrackLifecycleError):
    """An error indicating the track has already been renewed"""


class MismatchedOrganizationError(TrackLifecycleError):
    """An error indicating that track is already associated with another organization."""


class MissingVerificationError(TrackLifecycleError):
    """An error indicating that the user has never verified eligibility at any org."""


class InactiveVerificationError(TrackLifecycleError):
    """An error indicating that the user has previously verified eligibility but it is no longer active."""


class EligibleForWrongOrgError(TrackLifecycleError):
    """An error indicating that the user has active eligibility but not for the org we are trying to initialize a track wtih."""


def check_required_information(target: MemberTrack) -> None:
    """Validate the required information on a MemberTrack.

    Notes:
        This is only activated during an auto-transition,
        since the required information is gathered pre-emptively during a manual one.
    """
    for attr in target.required_information:
        handler = _REQUIRED_INFORMATION_HANDLERS[attr]  # type: ignore[index] # Invalid index type "str" for "Dict[RequiredInformation, Callable[[MemberTrack], Any]]"; expected type "RequiredInformation"
        handler(target)


def _check_due_date(track: MemberTrack) -> None:  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    due_date: date = track.user.health_profile.due_date
    if not due_date:
        raise MissingInformationError(
            f"{track.user} is missing a due-date, "
            f"which is required for Track {track.name}."
        )
    today = date.today()
    if due_date <= today:
        raise TrackDateConfigurationError(
            f"The reported due-date must be in the future: {due_date.isoformat()!r}"
        )
    if due_date - today > track.length():
        raise TrackDateConfigurationError(
            f"The reported due-date is too far in the future: {due_date.isoformat()!r}"
        )


def _check_child_birth(track: MemberTrack) -> None:
    health_profile: "HealthProfile" = track.user.health_profile
    birthday = health_profile.last_child_birthday
    today = date.today()
    # If we don't have a birthday, we can't move on.
    if not birthday:
        raise MissingInformationError(
            f"{track.user} is missing a child birthday, "
            f"which is required for Track {track.name}."
        )
    # If the birthday is too far in the past, or too far in the future, we can't move on
    if birthday < today - track.length() or birthday > today:
        raise TrackDateConfigurationError(
            "The reported birthday must be between "
            f"{today - track.length()} and {today}."
        )


_REQUIRED_INFORMATION_HANDLERS = {
    RequiredInformation.DUE_DATE: _check_due_date,
    RequiredInformation.CHILD_BIRTH: _check_child_birth,
}


def _is_valid_child_birthday_for_auto_transition(birthday: date) -> bool:
    """
    Used to determine if we can use an existing child birth day as the anchor date
    for a new track during an autotransition.

    For example, if we're auto-transitioning a user who has a child birth date, say, 11
    months ago, we probably don't want to use that as the anchor date for a new track.

    Returns true if birthday is in last 2 months, false otherwise.
    """
    # TODO: this logic is arbitrary, and it always has been. We need to clear up what
    #  exactly an autotransition means, and exactly where in the postpartum track we
    #  want to drop users based on their information.
    two_months_ago = date.today() - timedelta(days=60)
    return birthday is not None and two_months_ago < birthday <= date.today()


def prepare_user_for_auto_transition(track: "MemberTrack") -> None:
    """
    Prepares a user state for an auto-transition. Right now this just adds a child
    if child_birth_date is going to be required but there's only a due_date.

    TODO: If we have auto-transitions between different types of tracks, will this ever
     need to validate/fill in information other than a child birth date?
    """
    log = logger.bind(user_id=track.user.id, track_id=track.id)
    if not track.auto_transition_to:
        raise TrackLifecycleError(
            "Trying to prepare a user for a non-existent auto-transition."
        )
    required_info = TrackConfig.from_name(track.auto_transition_to).required_information
    if RequiredInformation.CHILD_BIRTH not in required_info:
        # Child birthdate not required for auto-transition, we're good to return
        return

    if _is_valid_child_birthday_for_auto_transition(
        track.user.health_profile.last_child_birthday
    ):
        # We have a valid child birth date, we don't have to do anything
        return

    if not track.user.health_profile.due_date:
        if track.anchor_date:
            # If there is an anchor_date, that means there must have previously been a due_date
            # and the anchor_date is calculated as (due_date - PregnancyMemberTrack.PREGNANCY_DURATION)
            due_date_from_anchor_date = (
                track.anchor_date + PregnancyMemberTrack.PREGNANCY_DURATION
            )
            track.user.health_profile.due_date = due_date_from_anchor_date

            log.warn(
                "Trying to prepare user for auto-transition but there is no due date on their health profile. Calculated from anchor date.",
                due_date_from_anchor_date=due_date_from_anchor_date,
            )
        else:
            # There should be no scenario where there is no due_date or anchor_date because a due_date is required
            # to initiate the pregnancy/partner pregnancy tracks
            log.error(
                "Trying to prepare user for auto-transition but there is no due date on their health profile and no anchor date."
            )

    due_date = track.user.health_profile.due_date

    if not due_date or not _is_valid_child_birthday_for_auto_transition(due_date):
        # Due date is not a valid child birth date. We're going to have an error during
        # tracks.initiate
        log_exception_message(
            "Auto-transition problem: due date not a valid child birthday"
        )
        log.warn(
            "Trying to prepare user for auto-transition but their due date is not a valid child birthday",
            due_date=due_date,
        )
        return
    hp: HealthProfile = track.user.health_profile
    hp.add_child_using_due_date()
    db.session.add(track.user.health_profile)


def expire_track_relationships(user: "User") -> None:
    db.session.expire(
        user,
        [
            "current_member_track",
            "active_tracks",
            "inactive_tracks",
            "scheduled_tracks",
        ],
    )


@span
def initiate(
    user: "User",
    track: TrackName,
    *,
    is_employee: bool = None,  # type: ignore[assignment] # Incompatible default for argument "is_employee" (default has type "None", argument has type "bool")
    as_auto_transition: bool = False,
    with_validation: bool = True,
    previous_member_track_id: int = None,  # type: ignore[assignment] # Incompatible default for argument "previous_member_track_id" (default has type "None", argument has type "int")
    previous_member_track_org_id: int = None,  # type: ignore[assignment] # Incompatible default for argument "previous_member_track_org_id" (default has type "None", argument has type "int")
    bucket_id: str = None,  # type: ignore[assignment] # Incompatible default for argument "bucket_id" (default has type "None", argument has type "str")
    flush: bool = True,
    start_date: date = None,  # type: ignore[assignment] # Incompatible default for argument "start_date" (default has type "None", argument has type "date")
    activate: bool = True,
    modified_by: str = None,  # type: ignore[assignment] # Incompatible default for argument "modified_by" (default has type "None", argument has type "str")
    change_reason: ChangeReason = None,  # type: ignore[assignment] # Incompatible default for argument "change_reason" (default has type "None", argument has type "ChangeReason")
    is_transition: bool = False,
    should_bypass_eligibility: bool = False,
    is_renew: bool = False,
    eligibility_organization_id: int = None,  # type: ignore[assignment] # Incompatible default for argument "eligibility_organization_id" (default has type "None", argument has type "int")
) -> MemberTrack:
    """Initiate a new MemberTrack given the supplied context."""
    # Skip validation - used mainly for transitioning, where we can assume this is all OK.

    if eligibility_organization_id is None:
        raise MismatchedOrganizationError("Eligibility organization ID is required")
    organization_id = eligibility_organization_id

    track = TrackName(track)
    log = logger.bind(
        user_id=user.id,
        is_employee=is_employee,
        target_track=track,
        as_auto_transition=as_auto_transition,
        with_validation=with_validation,
        previous_member_track_id=previous_member_track_id,
        bucket_id=bucket_id,
        flush=flush,
        start_date=start_date,
        activate=activate,
        modified_by=modified_by,
        change_reason=change_reason,
        is_transition=is_transition,
        should_bypass_eligibility=should_bypass_eligibility,
        is_renew=is_renew,
        eligibility_organization_id=eligibility_organization_id,
        organization_id=organization_id,
    )
    log.info("Initiating new MemberTrack for User.")

    # TODO: Avoid circular dependency until we can migrate everything in this file to tracks/
    from tracks import service as track_service

    track_svc: track_service.TrackSelectionService = (
        track_service.TrackSelectionService()
    )
    import eligibility
    from eligibility import e9y

    verification_svc: eligibility.EnterpriseVerificationService = (
        eligibility.get_verification_service()
    )
    # Prevent any automatic flushing
    #   to ensure we only write data once everything is validated.
    with db.session.no_autoflush:
        verification: Optional[e9y.EligibilityVerification] = None
        if with_validation:
            client_track: ClientTrack = track_svc.validate_initiation(
                track=track,
                user_id=user.id,
                organization_id=organization_id,
                should_bypass_eligibility=is_transition and should_bypass_eligibility,
            )

            if client_track.organization_id != organization_id:
                raise MismatchedOrganizationError(
                    f"Mismatch between current org for client track: {client_track.organization_id} and input org: {organization_id} for user_id: {user.id}"
                )
        # If no validation, just get the required information
        else:
            org_id: Optional[int] = None
            if previous_member_track_org_id is not None:
                org_id = previous_member_track_org_id
            elif previous_member_track_id is not None:
                previous_member_track = MemberTrack.query.get(previous_member_track_id)
                if previous_member_track and previous_member_track.organization:
                    org_id = previous_member_track.organization.id
            else:
                # prefer to use organization_id from the provided OrganizationEmployee object, or else fall back to e9y
                stats.increment(
                    metric_name="track.initiate.organization.id.fallback.e9y",
                    pod_name=stats.PodNames.ELIGIBILITY,
                )

                if organization_id is not None:
                    org_id = organization_id
                else:
                    org_ids = verification_svc.get_eligible_organization_ids_for_user(
                        user_id=user.id
                    )
                    org_id = org_ids[0] if len(org_ids) == 1 else None
                    if not org_id:
                        log.error(
                            "Failed to get organization id from fallback e9y verifications",
                            org_ids=org_ids,
                        )

            if is_transition and should_bypass_eligibility:
                log.info(
                    "Bypassing eligibility check during transition - initiate",
                    track=track,
                    user_id=user.id,
                )
            else:
                if not org_id:
                    # TODO: https://mavenclinic.atlassian.net/browse/ELIG-2354 cleanup code or handle organization_id missing case
                    stats.increment(
                        metric_name="track.initiate.organization.id.fallback.e9y.2",
                        pod_name=stats.PodNames.ELIGIBILITY,
                    )
                    log.info(
                        "fallback verification called",
                        user_id=user.id,
                    )
                    verification = verification_svc.get_verification_for_user(
                        user_id=user.id
                    )
                    if verification:
                        org_id = verification.organization_id
                    else:
                        raise MissingEmployeeError(
                            f"No enterprise verification found for user_id: {user.id}"
                        )

                if org_id != organization_id:
                    raise MismatchedOrganizationError(
                        f"Mismatch between current org for client track: {org_id} and input org: {organization_id} for user_id: {user.id}"
                    )

            client_track = (
                db.session.query(ClientTrack)
                .filter_by(track=track, organization_id=org_id)
                .first()
            )
            if not client_track:
                raise MissingClientTrackError(
                    f"Error renewing for user {user.id}: Organization {org_id} "
                    f"is not configured for Track {track}."
                )
        log.info(
            "Got user and ClientTrack.",
            user_id=user.id,
            client_track=client_track.id,
        )
        eligibility_member_2_id: Optional[int] = None
        eligibility_member_2_version: Optional[int] = None
        eligibility_member_id: Optional[int] = None
        eligibility_verification_id: Optional[int] = None
        eligibility_verification_2_id: Optional[int] = None

        # get eligibility_member_id here, it is used for both member_track and credit
        if not verification:
            verification = verification_svc.get_verification_for_user_and_org(
                user_id=user.id, organization_id=client_track.organization_id
            )
            if verification:
                log.info(
                    "Got verification for user and org",
                    user_id=user.id,
                    organization_id=client_track.organization_id,
                    verification_id=verification.verification_id,
                    eligibility_member_id=verification.eligibility_member_id,
                    eligibility_member_2_id=verification.eligibility_member_2_id,
                    eligibility_member_2_version=verification.eligibility_member_2_version,
                )

        if not verification:
            # for track transition that can skip eligibility check, if no existing verification found
            # fall back to use the e9y_member_id & e9y_verification_id from previous track
            if (
                is_transition
                and should_bypass_eligibility
                and previous_member_track_id is not None
            ):
                previous_member_track = MemberTrack.query.get(previous_member_track_id)
                if previous_member_track:
                    log.info(
                        "Use previous track to write e9y_ids: failed to get verification for user and org",
                        user_id=user.id,
                        organization_id=client_track.organization_id,
                    )
                    eligibility_member_id = previous_member_track.eligibility_member_id
                    eligibility_verification_id = (
                        previous_member_track.eligibility_verification_id
                    )
                    eligibility_member_2_id = (
                        previous_member_track.eligibility_member_2_id
                    )
                    eligibility_member_2_version = (
                        previous_member_track.eligibility_member_2_version
                    )
                    eligibility_verification_2_id = (
                        previous_member_track.eligibility_verification_2_id
                    )
            else:
                log.warning(
                    "Cannot write e9y_ids to member_track: failed to get verification for user and org",
                    user_id=user.id,
                    organization_id=client_track.organization_id,
                )
        else:
            if (
                not should_bypass_eligibility
                and not verification_svc.is_verification_active(
                    verification=verification
                )
            ):
                raise InvalidEmployeeError(
                    f"This verification is no longer valid for user_id: {user.id}"
                )

            eligibility_member_id = verification.eligibility_member_id
            eligibility_verification_id = verification.verification_id
            eligibility_verification_2_id = verification.verification_2_id
            eligibility_member_2_id = verification.eligibility_member_2_id
            eligibility_member_2_version = verification.eligibility_member_2_version

        sub_population_id: Optional[
            int
        ] = verification_svc.get_sub_population_id_for_user_and_org(
            user_id=user.id, organization_id=client_track.organization_id
        )

        # Create the MemberTrack for this user.
        mt = MemberTrack(
            name=track,
            client_track=client_track,
            client_track_id=client_track.id,
            user=user,
            user_id=user.id,
            eligibility_member_id=eligibility_member_id,
            eligibility_verification_id=eligibility_verification_id,
            eligibility_member_2_id=eligibility_member_2_id,
            eligibility_member_2_version=eligibility_member_2_version,
            eligibility_verification_2_id=eligibility_verification_2_id,
            sub_population_id=sub_population_id,
            is_employee=is_employee,
            auto_transitioned=as_auto_transition,
            previous_member_track_id=previous_member_track_id,
            bucket_id=bucket_id or str(uuid.uuid4()),
            start_date=start_date or datetime.utcnow().date(),
            activated_at=func.now() if activate else None,
            modified_by=modified_by,
            change_reason=change_reason,
        )
        # Make sure the user is in the right state.
        log.debug(
            "Ensuring User has the required information for Track.",
            required_information=mt.required_information,
        )
        check_required_information(mt)
        # Set the pointer for weekly calculations.
        mt.set_anchor_date()
        log.debug("Determined anchor-date for MemberTrack.", anchor_date=mt.anchor_date)
        try:
            db.session.add(mt)
            log.debug("Creating initial for phase reporting.")
            phase = mt.initial_phase
            mtpr = MemberTrackPhaseReporting(
                member_track=mt, name=phase.name, started_at=phase.started_at
            )
            db.session.add(mtpr)

            # Grant credits to the user so they can book appointments immediately.
            # TODO: This is a legacy concept that should be reviewed...
            #   Any user an an active track should be able to book appointments regardless
            #   of a "credit amount".
            credit = Credit(
                user_id=user.id,
                eligibility_member_id=eligibility_member_id,
                eligibility_member_2_id=eligibility_member_2_id,
                eligibility_member_2_version=eligibility_member_2_version,
                eligibility_verification_id=eligibility_verification_id,
                eligibility_verification_2_id=eligibility_verification_2_id,
                amount=2000,
                activated_at=datetime.utcnow(),
            )
            db.session.add(credit)

            expire_track_relationships(user)

            if flush:
                db.session.flush()
                force_ca_replacement = (
                    track not in {TrackName.PARENTING_AND_PEDIATRICS, TrackName.GENERIC}
                    and len(mt.user.member_tracks) > 1
                    and not is_transition
                    and not is_renew
                )
                if force_ca_replacement:
                    log.info(
                        "Enforcing CA reassign when creating a second track other than P&P and generic.",
                        user_id=mt.user.id,
                        track=track,
                    )
                on_user_member_track_change(mt.user, force_ca_replacement)

            after_activate(user_id=user.id)

            from tracks.lifecycle_events.event_system import dispatch_initiate_event

            # Dispatch event after successful commit
            dispatch_initiate_event(track=mt, user=user)

            company_mfa_lts_enabled = feature_flags.bool_variation(
                COMPANY_MFA_SYNC_LAUNCH_DARKLY_KEY,
                feature_flags.Context.create(
                    COMPANY_MFA_SYNC_LAUNCH_DARKLY_CONTEXT_NAME
                ),
                default=False,
            )
            if company_mfa_lts_enabled:
                log.info("Initiating the company mfa sync job")
                from tasks.enterprise import update_single_user_company_mfa

                update_single_user_company_mfa.delay(
                    user_id=user.id, org_id=client_track.organization_id
                )

            log.info("Done initiating new MemberTrack.", track_id=mt.id)
            return mt
        except Exception as e:
            log.error(
                "[Member Track] Error while init MemberTrack.",
                exception=str(e),
                user_id=user.id,
                track_id=mt.id,
                track_name=track,
                org_id=organization_id,
                change_reason=mt.change_reason,
                transitioning_to=mt.transitioning_to,
                anchor_date=mt.anchor_date,
                is_multi_track=len(user.active_tracks) > 1,
            )
            raise e


@span
def terminate(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    track: MemberTrack,
    *,
    expire_credits: bool = True,
    flush: bool = True,
    modified_by: str = None,  # type: ignore[assignment] # Incompatible default for argument "modified_by" (default has type "None", argument has type "str")
    change_reason: ChangeReason = None,  # type: ignore[assignment] # Incompatible default for argument "change_reason" (default has type "None", argument has type "ChangeReason")
):
    """Mark the given track as completed."""
    log = logger.bind(
        user_id=track.user.id,
        track_id=track.id,
        current_track=track.name,
        current_phase=track.current_phase.name,
    )
    log.info("Terminating Track for User.")

    if track.ended_at:
        log.debug(
            "Track has already ended.", track_id=track.id, ended_at=track.ended_at
        )
        expire_track_relationships(track.user)
        return

    db.session.add(track)
    # Prevent any automatic flushing
    #   to ensure we only write data once everything is validated.
    with db.session.no_autoflush:
        # Set the end-date (this is the "termination")
        track.ended_at = datetime.utcnow()
        track.modified_by = modified_by
        track.change_reason = change_reason
        # Expire any active credits for the user if no tracks remain.
        # If the user is transitioning to a new Track, expire_credits will be False.
        remaining_tracks = [t for t in track.user.active_tracks if t.id != track.id]
        renewals = [
            t
            for t in track.user.scheduled_tracks
            if t.name == track.name and t.previous_member_track_id == track.id
        ]
        neither_transition_nor_renewal = not remaining_tracks and not renewals
        if expire_credits and neither_transition_nor_renewal:
            Credit.expire_all_enterprise_credits_for_user(
                user_id=track.user_id,
                expires_at=track.ended_at,
            )
        # Expire the calculated phases if they're cached.
        track.expire_phases()
        expire_track_relationships(track.user)
        final_phase = track.final_phase
        mtpr = (
            db.session.query(MemberTrackPhaseReporting)
            .filter_by(member_track_id=track.id, name=final_phase.name)  # type: ignore[union-attr] # Item "None" of "Optional[MemberTrackPhase]" has no attribute "name"
            .order_by(MemberTrackPhaseReporting.created_at.desc())
            .first()
        ) or MemberTrackPhaseReporting(
            member_track_id=track.id,
            name=final_phase.name,  # type: ignore[union-attr] # Item "None" of "Optional[MemberTrackPhase]" has no attribute "name"
            started_at=final_phase.started_at,  # type: ignore[union-attr] # Item "None" of "Optional[MemberTrackPhase]" has no attribute "started_at"
        )
        mtpr.ended_at = track.ended_at.date()
        db.session.add(mtpr)

    if flush:
        db.session.flush()

    after_terminate(user_id=track.user.id)

    from tracks.lifecycle_events.event_system import dispatch_terminate_event

    # Dispatch event after successful commit
    dispatch_terminate_event(track=track, user=track.user)

    company_mfa_lts_enabled = feature_flags.bool_variation(
        COMPANY_MFA_SYNC_LAUNCH_DARKLY_KEY,
        feature_flags.Context.create(COMPANY_MFA_SYNC_LAUNCH_DARKLY_CONTEXT_NAME),
        default=False,
    )
    if company_mfa_lts_enabled:
        log.info("Initiating the company mfa sync job")
        # To change the company mfa to false
        from tasks.enterprise import update_single_user_company_mfa

        update_single_user_company_mfa.delay(user_id=track.user_id, is_terminate=True)

    log.info("Done terminating track.")


@span
def transition(
    source: MemberTrack,
    target: TrackName,
    *,
    as_auto_transition: bool = False,
    prepare_user: bool = False,
    with_validation: bool = True,
    modified_by: str = None,  # type: ignore[assignment] # Incompatible default for argument "modified_by" (default has type "None", argument has type "str")
    change_reason: ChangeReason = None,  # type: ignore[assignment] # Incompatible default for argument "change_reason" (default has type "None", argument has type "ChangeReason")
) -> MemberTrack:
    """Move a user from their current MemberTrack to a new one."""
    # No-op if the source is the same as the target.

    target = TrackName(target)
    log = logger.bind(
        user_id=source.user.id,
        source_track_id=source.id,
        source_track=source.name,
        source_phase=source.current_phase.name,
        target_track=target,
        as_auto_transition=as_auto_transition,
    )
    log.info("Transitioning User to new MemberTrack.")
    if source.name == target:
        log.debug("User is already in the targeted MemberTrack.")
        return source

    # EPEN-3330
    should_bypass_eligibility = _should_bypass_eligibility(source.name, target)

    with db.session.no_autoflush:
        # If we're calling this from `finish_transition`,
        # we can assume we've already done this in `initiate_transition`
        if with_validation:
            log.debug("Validating transition target.")
            _validate_transition_target(source, target)

        if prepare_user:
            prepare_user_for_auto_transition(source)

        # Un-set due_date if it WAS required but isn't anymore.
        # Prevent pregnancy users from having a due_date if they, say, transition to
        # pregnancyloss.
        source_required_info = source.required_information
        target_required_info = TrackConfig.from_name(target).required_information
        due_date_was_needed = RequiredInformation.DUE_DATE in source_required_info
        due_date_will_be_needed = RequiredInformation.DUE_DATE in target_required_info
        if due_date_was_needed and not due_date_will_be_needed:
            log.debug("Clearing due_date that is not needed for target track.")
            source.user.health_profile.due_date = None

        terminate(
            source,
            expire_credits=False,
            flush=False,
            modified_by=modified_by,
            change_reason=change_reason,
        )
        track = initiate(
            source.user,
            target,
            with_validation=False,
            is_employee=source.is_employee,
            as_auto_transition=as_auto_transition,
            previous_member_track_id=source.id,
            previous_member_track_org_id=source.organization.id,
            bucket_id=source.bucket_id,
            flush=True,
            modified_by=modified_by,
            change_reason=change_reason,
            is_transition=True,
            should_bypass_eligibility=should_bypass_eligibility,
            eligibility_organization_id=source.organization.id,
        )

    expire_track_relationships(source.user)

    from braze.client.utils import rq_delay_with_feature_flag
    from braze.events import send_track_transition_event  # Avoid circular import

    rq_delay_with_feature_flag(
        func=send_track_transition_event,
        user_esp_id=source.user.esp_id,
        source=source.name,
        target=target,
        as_auto_transition=as_auto_transition,
    )

    # if track is transitioning from trying_to_conceive or fertility to pregnancy, enforce to reassign CA
    if (
        source.name in {TrackName.TRYING_TO_CONCEIVE, TrackName.FERTILITY}
        and target == TrackName.PREGNANCY
    ):
        from provider_matching.services.care_team_assignment import ensure_care_advocate

        ensure_care_advocate(source.user, force_ca_replacement=True)
        log.info(
            "Enforcing CA reassign when transitioning user.",
            user_id=source.user.id,
            original_track=source.name,
            target_track=target,
        )

    # if member is transitioning to a track that has modifiers, determine whether they have booked appointments with providers that are not supported by that track and alert
    from appointments.services.common import (
        cancel_invalid_appointment_post_track_transition,
    )

    cancel_invalid_appointment_post_track_transition(
        user_id=source.user.id,
        member_track_modifiers=track.track_modifiers,
        client_track_ids=[track.client_track_id],
    )

    log.info(
        "Done transitioning User.",
        user_id=source.user.id,
        original_track=source.name,
        target_track=target,
    )

    from tracks.lifecycle_events.event_system import dispatch_transition_event

    # Dispatch event after successful commit
    dispatch_transition_event(source_track=source, target_track=track, user=source.user)

    return track


@span
def initiate_transition(
    track: MemberTrack,
    target: TrackName,
    modified_by: str = None,  # type: ignore[assignment] # Incompatible default for argument "modified_by" (default has type "None", argument has type "str")
    change_reason: ChangeReason = None,  # type: ignore[assignment] # Incompatible default for argument "change_reason" (default has type "None", argument has type "ChangeReason")
) -> MemberTrack:
    target = TrackName(target)
    log = logger.bind(
        user_id=track.user.id,
        source_track_id=track.id,
        source_track=track.name,
        source_phase=track.current_phase.name,
        target_track=target,
    )
    log.info("Initiating multi-stage transition for User.")
    if track.name == target:
        log.debug("User is already in the targeted MemberTrack.")
        return track
    _validate_transition_target(track, target)
    given = track
    # We already started this transition, no-op.
    if track.transitioning_to == target:
        log.debug("User is already transitioning to the targeted MemberTrack.")
        return track
    # Begin the transition.
    track.transitioning_to = target
    track.modified_by = modified_by
    track.change_reason = change_reason
    log.info("Done initiating transition.")
    return given


@span
def cancel_transition(
    track: MemberTrack, modified_by: str = None, change_reason: ChangeReason = None  # type: ignore[assignment] # Incompatible default for argument "modified_by" (default has type "None", argument has type "str") #type: ignore[assignment] # Incompatible default for argument "change_reason" (default has type "None", argument has type "ChangeReason")
) -> MemberTrack:
    log = logger.bind(
        user_id=track.user.id,
        source_track_id=track.id,
        source_track=track.name,
        source_phase=track.current_phase.name,
        target_track=track.transitioning_to,
    )
    log.info("Canceling multi-stage transition for User.")
    given = track
    # No transition in progress, no-op.
    if track.transitioning_to is None:
        log.debug("User isn't currently transitioning to any Track.")
        return track
    track.transitioning_to = None
    track.modified_by = modified_by
    track.change_reason = change_reason
    log.info("Done cancelling transition for user.")
    return given


@span
def finish_transition(
    track: MemberTrack, modified_by: str = None, change_reason: ChangeReason = None  # type: ignore[assignment] # Incompatible default for argument "modified_by" (default has type "None", argument has type "str") #type: ignore[assignment] # Incompatible default for argument "change_reason" (default has type "None", argument has type "ChangeReason")
) -> MemberTrack:
    log = logger.bind(
        user_id=track.user.id,
        source_track_id=track.id,
        source_track=track.name,
        source_phase=track.current_phase.name,
        target_track=track.transitioning_to,
    )
    log.info("Finalizing multi-stage transition for User.")
    if not track.transitioning_to:
        log.debug("User isn't currently transitioning to any Track.")
        return track

    return transition(
        track,
        track.transitioning_to,
        with_validation=False,
        modified_by=modified_by,
        change_reason=change_reason,
    )


def _validate_renewal(track: MemberTrack) -> bool:
    """
    Don't allow a renewal if:
      - the track does not allow renewals
      - the track is no longer active
      - a renewal is already scheduled for this track
    """
    if not track.can_be_renewed:
        raise IneligibleRenewalError()

    if not track.active:
        raise InactiveTrackError()

    if any(t.name == track.name for t in track.user.scheduled_tracks):
        raise TrackAlreadyRenewedError()

    return True


@span
def renew(
    track: MemberTrack,
    is_auto_renewal: bool = False,
    modified_by: str = None,  # type: ignore[assignment] # Incompatible default for argument "modified_by" (default has type "None", argument has type "str")
    change_reason: ChangeReason = None,  # type: ignore[assignment] # Incompatible default for argument "change_reason" (default has type "None", argument has type "ChangeReason")
) -> MemberTrack:
    log = logger.bind(
        user_id=track.user.id,
        source_track_id=track.id,
        source_track=track.name,
    )
    log.info("Scheduling a track renewal")

    _validate_renewal(track)

    current_track_scheduled_end_date = track.get_scheduled_end_date()
    old_track = track
    try:
        with db.session.no_autoflush:
            track = initiate(
                track.user,
                track.name,
                with_validation=False,
                is_employee=track.is_employee,
                previous_member_track_id=track.id,
                bucket_id=track.bucket_id,
                flush=False,
                start_date=current_track_scheduled_end_date,
                activate=False,
                modified_by=modified_by,
                change_reason=change_reason,
                is_renew=True,
                eligibility_organization_id=track.organization.id,
            )
            db.session.flush()
    except Exception as e:
        log.error(
            "Failed to renew track",
            exception=str(e),
            user_id=old_track.user.id,
            track_id=old_track.id,
            track_name=track.name,
            org_id=track.organization.id,
            change_reason=old_track.change_reason,
            transitioning_to=old_track.transitioning_to,
            anchor_date=old_track.anchor_date,
        )
        raise e

    from utils import braze_events  # Avoid circular import

    if is_auto_renewal:
        braze_events.track_auto_renewal(
            track.user,
            track.name,  # type: ignore[arg-type] # Argument 2 to "track_auto_renewal" has incompatible type "str"; expected "TrackName"
            current_track_scheduled_end_date,
        )
    else:
        braze_events.track_renewal(
            track.user,
            track.name,  # type: ignore[arg-type] # Argument 2 to "track_renewal" has incompatible type "str"; expected "TrackName"
            current_track_scheduled_end_date,
        )

    log.info("Done scheduling track renewal")
    return track


@span
def add_track_closure_reason(member_track, closure_reason_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if TrackChangeReason.query.get(closure_reason_id):
        member_track.closure_reason_id = closure_reason_id
        db.session.add(member_track)
        db.session.commit()

        log = logger.bind(
            user_id=member_track.user.id,
            track_id=member_track.id,
            current_track=member_track.name,
            current_phase=member_track.current_phase.name,
        )
        log.info(
            "Added closure reason to member_track",
            member_track_id=member_track.id,
            closure_reason_id=closure_reason_id,
        )
    else:
        raise TrackLifecycleError(
            f"Attempted to set track closure reason for track id {member_track.id} "
            f"to unknown close reason id {closure_reason_id}"
        )


@span
def on_health_profile_update(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    user: "User", modified_by: str = None, change_reason: ChangeReason = None  # type: ignore[assignment] # Incompatible default for argument "modified_by" (default has type "None", argument has type "str") #type: ignore[assignment] # Incompatible default for argument "change_reason" (default has type "None", argument has type "ChangeReason")
):
    """Update MemberTrack state on changes to a User's HealthProfile."""
    # TODO: [multitrack] Do this in a loop over all of user.active_tracks
    track = user.current_member_track
    if not track:
        return
    log = logger.bind(
        user_id=user.id,
        track_id=track.id,
        current_track=track.name,
        current_phase=track.current_phase.name,
    )
    log.info("User health-profile update-hook called.")
    check_track_state(track, modified_by, change_reason)


@span
def check_track_state(
    track: MemberTrack, modified_by: str = None, change_reason: ChangeReason = None  # type: ignore[assignment] # Incompatible default for argument "modified_by" (default has type "None", argument has type "str") #type: ignore[assignment] # Incompatible default for argument "change_reason" (default has type "None", argument has type "ChangeReason")
) -> bool:
    """Ensure a user is within the correct track and pinned to the correct anchor date."""
    log = logger.bind(
        user_id=track.user.id,
        current_track_id=track.id,
        current_track=track.name,
        current_phase=track.current_phase.name,
    )
    log.info("Checking MemberTrack state with against User information.")
    changed = False
    with db.session.begin_nested():
        log.debug("Resetting anchor-date.", current_anchor_date=track.anchor_date)
        if track.set_anchor_date():
            changed = True
        log.debug("Reset anchor-date.", new_anchor_date=track.anchor_date)
        # If we're beyond the scheduled end of this track and this track has an
        # auto-transition, do the thing.
        if track.beyond_scheduled_end and track.auto_transition_to:
            log.debug("Auto-Transitioning User.", target=track.auto_transition_to)
            transition(
                track,
                track.auto_transition_to,
                as_auto_transition=True,
                prepare_user=True,
                modified_by=modified_by,
                change_reason=change_reason,
            )
            changed = True
        log.info("Done checking MemberTrack state.")
        return changed


def _should_bypass_eligibility(source, target) -> bool:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    allowed_transitions = {
        ("pregnancy", "postpartum"),
        ("pregnancy", "pregnancyloss"),
        ("postpartum", "pregnancyloss"),
        ("partner_pregnant", "partner_newparent"),
        ("partner_pregnant", "pregnancyloss"),
        ("partner_newparent", "pregnancyloss"),
        ("fertility", "pregnancyloss"),
    }

    family_building_set = {
        "fertility",
        "trying_to_conceive",
        "partner_fertility",
        "adoption",
        "surrogacy",
        "egg_freezing",
    }

    return (source, target) in allowed_transitions or (
        source != target
        and source in family_building_set
        and target in family_building_set
    )


def _validate_transition_target(source: MemberTrack, target: TrackName):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    # Only transition to pre-configured tracks.
    valid_transitions = {t.name for t in source.transitions} | {TrackName.GENERIC.value}
    if target not in valid_transitions:
        raise TransitionNotConfiguredError(
            f"Transitions from Track '{source.name}' to '{target}' are not allowed. "
            "Users in this track may transition to one of: "
            f"{(*(t for t in valid_transitions),)}"
        )
    if target == TrackName.GENERIC:
        logger.debug(
            "Got a user transitioning to Generic.",
            source_track_id=source.id,
            user_id=source.user_id,
        )

    verification_error_message = (
        TrackConfig.from_name(target).track_unavailable_for_transition_message or ""
    )

    # TODO: Avoid circular dependency until we can migrate everything in this file to tracks/
    from tracks import repository

    tracks_repo: repository.TracksRepository = repository.TracksRepository()
    client_track: ClientTrack | None = tracks_repo.get_client_track(  # type: ignore[syntax] # X | Y syntax for unions requires Python 3.10
        organization_id=source.organization.id, track=target, active_only=True
    )
    if client_track is None:
        raise MissingClientTrackError(
            f"Organization {source.organization.id} "
            f"is not configured for Track {target.value!r}.",
            verification_error_message,
        )

    # EPEN-3330
    should_bypass_eligibility = _should_bypass_eligibility(source.name, target)
    if should_bypass_eligibility:
        logger.info(
            "Always allow transitions",
            source=source.name,
            target=target,
            source_track_id=source.id,
            user_id=source.user_id,
        )
        return

    _validate_eligibility_for_transition(source, verification_error_message)


def _validate_eligibility_for_transition(source: MemberTrack, verification_error_message: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    import eligibility
    from eligibility import e9y

    verification_svc: eligibility.EnterpriseVerificationService = (
        eligibility.get_verification_service()
    )
    verification: Optional[
        e9y.EligibilityVerification
    ] = verification_svc.get_verification_for_user_and_org(
        user_id=source.user.id, organization_id=source.client_track.organization_id
    )

    if not verification:
        cancel_transition(source)
        raise MissingVerificationError(
            f"[Transition cancelled] No verification for user_id={source.user.id}",
            verification_error_message,
        )
    if not verification_svc.is_verification_active(verification=verification):
        cancel_transition(source)
        raise InactiveVerificationError(
            f"[Transition cancelled] Verification not active for user_id={source.user.id}",
            verification_error_message,
        )
    if verification.organization_id != source.client_track.organization_id:
        cancel_transition(source)
        raise EligibleForWrongOrgError(
            f"[Transition cancelled] Verification for user_id={source.user.id} expected org {source.client_track.organization_id} got {verification.organization_id}",
            verification_error_message,
        )


def on_user_member_track_change(user, force_ca_replacement):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    from provider_matching.services.care_team_assignment import (
        ensure_care_advocate,
        replace_care_team_members_during_transition,
    )

    logger.info(
        "Got a user track modification event.",
        user=user.id,
        active_tracks=[t.name for t in user.active_tracks],
        inactive_tracks=[[t.name for t in user.inactive_tracks]],
    )
    replaced = ensure_care_advocate(user, force_ca_replacement=force_ca_replacement)
    if not replaced:
        logger.debug(
            "Didn't replace existing care coordinators for user.", user_id=user.id
        )
    replace_care_team_members_during_transition(user)


@only_on_successful_commit
def after_activate(user_id: int) -> None:
    from braze.attributes import activate_track

    activate_track.delay(user_id, caller="initiate")
    logger.info(
        "Dispatched member track activation braze event after commit",
        user_id=user_id,
    )


@only_on_successful_commit
def after_terminate(user_id: int) -> None:
    from braze.attributes import terminate_track

    terminate_track.delay(user_id, caller="terminate")
    logger.info(
        "Dispatched member track termination braze event after commit",
        user_id=user_id,
    )
