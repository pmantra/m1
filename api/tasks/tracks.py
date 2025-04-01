import datetime
import os
from itertools import chain

from ldclient import Stage
from maven import feature_flags
from maven.feature_flags import migration_variation
from sqlalchemy import func

import eligibility
from authn.models.user import User
from common import stats
from common.health_profile.health_profile_service_client import (
    HealthProfileServiceClient,
)
from common.health_profile.health_profile_service_models import ClinicalStatus, Modifier
from health.services.hps_export_utils import get_or_create_pregnancy
from health.utils.constants import MIGRATE_PREGNANCY_DATA_FROM_MONO_TO_HPS
from models.tracks import ChangeReason, ClientTrack, MemberTrack, TrackName
from models.tracks.lifecycle import (
    IncompatibleTrackError,
    MismatchedOrganizationError,
    MissingInformationError,
    TrackDateConfigurationError,
    TrackLifecycleError,
    TransitionNotConfiguredError,
    check_track_state,
    terminate,
    transition,
)
from models.tracks.member_track import MemberTrackPhaseReporting
from storage.connection import db
from tasks.queues import job
from tracks import repository
from utils import braze
from utils.ddtrace_filters import ignore_trace
from utils.exceptions import ProgramLifecycleError
from utils.launchdarkly import user_context
from utils.log import logger

log = logger(__name__)

failure_error_types = (
    TrackDateConfigurationError,
    TransitionNotConfiguredError,
    MissingInformationError,
    IncompatibleTrackError,
    MismatchedOrganizationError,
)


def get_tracks_past_scheduled_end_query():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return (
        db.session.query(MemberTrack)
        .join(ClientTrack, ClientTrack.id == MemberTrack.client_track_id)
        .filter(
            MemberTrack.active,
            MemberTrack.user_id != 0,
            MemberTrack.client_track_id != 0,
            func.adddate(MemberTrack.anchor_date, ClientTrack.length_in_days)
            < func.now(),
        )
    )


def get_tracks_past_scheduled_end_count():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return get_tracks_past_scheduled_end_query().count()


@ignore_trace()
@job(team_ns="enrollments", service_ns="tracks")
def auto_transition_or_terminate_member_tracks_coordinator(
    chunk_size: int = 1_000,
) -> None:
    """
    This job coordinates creating `auto_transition_or_terminate_member_tracks` jobs
    which chunk the work load of process all ending tracks
    """
    active_tracks_count = get_tracks_past_scheduled_end_count()
    chunks = int(active_tracks_count / chunk_size) + 1

    log.info(
        "Coordinating creation of auto_transition_or_terminate_member_tracks jobs",
        active_tracks_count=active_tracks_count,
        chunks=chunks,
    )

    for chunk in range(chunks):
        auto_transition_or_terminate_member_tracks.delay(
            chunk=chunk,
            chunk_size=chunk_size,
        )


@ignore_trace()
@job(team_ns="enrollments", service_ns="tracks")
def auto_transition_or_terminate_member_tracks(
    chunk: int = 0, chunk_size: int = 1_000
) -> None:
    """
    This job updates MemberTracks that are past their scheduled end date.

    If the track should auto-transition to another track (e.g. pregnancy -> postpartum),
    do the auto-transition. This terminates the current track and initiates the new track.

    If the track doesn't have an auto-transition configured, just terminate the track.
    """
    log.info(
        "Processing MemberTracks past scheduled end.",
        chunk=chunk,
        chunk_size=chunk_size,
    )

    active_tracks = (
        get_tracks_past_scheduled_end_query()
        .order_by(MemberTrack.id)
        .limit(chunk_size)
        .offset(chunk * chunk_size)
    )

    tracks_past_scheduled_end = (t for t in active_tracks if t.beyond_scheduled_end)

    success = True
    for track in tracks_past_scheduled_end:
        should_update_pregnancy_in_hps = get_should_update_pregnancy_in_hps(track)
        hp_mono_due_date = (
            track.user.health_profile.due_date if track.user.health_profile else None
        )

        if should_update_pregnancy_in_hps:
            log.info(f"update_pregnancy_in_hps job starting for user: {track.user_id}")
            update_pregnancy_in_hps.delay(track.user_id, hp_mono_due_date)

        success &= handle_auto_transition_or_terminate_member_tracks(track=track)

    log.info(
        "Finished processing MemberTracks past scheduled end.",
        chunk=chunk,
        chunk_size=chunk_size,
    )

    # fail the job if there were any issues processing the tracks
    if not success:
        raise Exception("Error encountered handling scheduled track transitions.")


@job("priority", team_ns="mpractice_core", service_ns="health_profile")
def update_pregnancy_in_hps(user_id: int, hp_mono_due_date: datetime.datetime) -> None:
    """
    Update a user's pregnancy status in the Health Profile Service (HPS).

    This function is called during track auto-transition (specifically pregnancy -> postpartum)
    to mark the active pregnancy as RESOLVED in the Health Profile Service.

    Args:
        user_id (int): The user whose pregnancy status needs to be updated
        hp_mono_due_date (datetime): due_date in health_profile table json column

    The function performs the following steps:
    1. Initialize Health Profile Service client with the user
    2. Retrieve the user's active pregnancy from HPS
    3. If there is no estimated date from HPS, due_date from health_profile in mono will be used
    4. Mark the pregnancy as RESOLVED using the System modifier
    5. Send the updated pregnancy data to HPS
    """
    if not user_id:
        log.error("update_pregnancy_in_hps skipping because of no user id")
        return

    user = User.query.get(user_id)
    if not user:
        log.error(
            f"update_pregnancy_in_hps skipping because no user was found for id {user_id}"
        )
        return
    hps_client = HealthProfileServiceClient(user=user)

    pregnancy = get_or_create_pregnancy(hps_client, user)
    if not pregnancy.estimated_date and not hp_mono_due_date:
        log.warn(
            f"update_pregnancy_in_hps skipped during auto transition because of no estimated date for user: {user_id}"
        )
        return

    if pregnancy.estimated_date is None and hp_mono_due_date is not None:
        pregnancy.estimated_date = hp_mono_due_date
    pregnancy.status = ClinicalStatus.RESOLVED
    pregnancy.modifier = Modifier(name="track_auto_transition_cron", role="system")

    hps_client.put_pregnancy(pregnancy)
    log.info("update_pregnancy_in_hps finished")


def get_should_update_pregnancy_in_hps(track: MemberTrack) -> bool:
    (migration_stage, _) = migration_variation(
        flag_key=MIGRATE_PREGNANCY_DATA_FROM_MONO_TO_HPS,
        context=user_context(track.user),
        default=Stage.OFF,
    )

    if migration_stage is None or track is None or track.auto_transition_to is None:
        return False

    return (
        migration_stage != Stage.OFF
        and track.name == TrackName.PREGNANCY.value
        and track.auto_transition_to.value == TrackName.POSTPARTUM.value
    )


def handle_auto_transition_or_terminate_member_tracks(track: MemberTrack) -> bool:
    metric_prefix = "api.tasks.tracks.auto_transition_or_terminate_member_tracks"
    eligibility_service = eligibility.get_verification_service()
    end_track = track.auto_transition_to
    is_end_track_active_in_org = False
    if end_track:
        repo: repository.TracksRepository = repository.TracksRepository()
        active_tracks = repo.get_active_tracks(
            organization_id=track.client_track.organization_id
        )
        is_end_track_active_in_org = any(
            map(
                lambda client_track: client_track.name == end_track,
                active_tracks,
            )
        )

    should_auto_transition = end_track and is_end_track_active_in_org

    action_name = (
        f"auto-transition to {track.auto_transition_to}"
        if should_auto_transition
        else "terminate"
    )

    if not is_end_track_active_in_org:
        log.debug(
            "Member Track transition not supported by the Organization (End Track is not active)",
            member_track_id=track.id,
            user_id=track.user_id,
            track_name=track.name,
            anchor_date=track.anchor_date,
            scheduled_end=track.get_scheduled_end_date(),
            action=action_name,
        )

    log.debug(
        "Handling MemberTrack past scheduled end date.",
        member_track_id=track.id,
        user_id=track.user_id,
        track_name=track.name,
        anchor_date=track.anchor_date,
        scheduled_end=track.get_scheduled_end_date(),
        action=action_name,
    )

    success = False
    try:
        if should_auto_transition:
            new_track = transition(
                track,
                target=end_track,
                as_auto_transition=True,
                prepare_user=True,
                change_reason=ChangeReason.AUTO_JOB_TRANSITION,
            )
            log.info(
                "Auto-transitioned MemberTrack",
                previous_member_track_id=track.id,
                previous_member_track_name=track.name,
                new_member_track_id=new_track.id,
                new_member_track_name=new_track.name,
            )
        else:
            terminate(track, change_reason=ChangeReason.AUTO_JOB_TERMINATE)
            log.info("Terminated MemberTrack.", member_track_id=track.id)

            # check if the user associated with the terminated track has any scheduled tracks
            # and that the scheduled track is associated with the terminated track
            # and has a start date <= today
            log.info(
                "Checking for any tracks to be renewed",
                user_id=track.user_id,
                previous_member_track_id=track.id,
            )
            user: User = track.user
            scheduled_tracks = [
                st
                for st in user.scheduled_tracks
                if st.previous_member_track_id == track.id
                and st.start_date <= datetime.datetime.utcnow().date()
            ]
            if scheduled_tracks:
                scheduled_track: MemberTrack = scheduled_tracks[0]
                log_ = log.bind(
                    user_id=scheduled_track.user_id,
                    renewed_member_track_id=scheduled_track.id,
                    renewed_member_track_name=scheduled_track.name,
                )
                log_.info("Found track to be renewed")

                # verify that the user is still eligible
                log_.info("Verifying the member is still eligible")
                is_known_to_be_eligible = (
                    eligibility_service.is_user_known_to_be_eligible_for_org(
                        user_id=user.id,
                        organization_id=scheduled_track.organization.id,
                        timeout=3,
                    )
                )

                # if eligible, activate the track
                if is_known_to_be_eligible:
                    log_.info("User is eligible. Activating renewed track")
                    scheduled_track.activated_at = datetime.datetime.utcnow()
                    org_id = scheduled_track.client_track.organization_id
                    scheduled_track.sub_population_id = (
                        eligibility_service.get_sub_population_id_for_user_and_org(
                            user_id=user.id, organization_id=org_id
                        )
                    )

                # if ineligible, terminate the scheduled track
                else:
                    log_.info("User is no longer eligible. Terminating renewed track")
                    terminate(
                        scheduled_track,
                        change_reason=ChangeReason.AUTO_JOB_RENEW_TERMINATE,
                    )

        db.session.commit()
        stats.increment(
            metric_name=f"{metric_prefix}.transaction",
            pod_name=stats.PodNames.ENROLLMENTS,
            tags=["status:complete"],
        )
        success = True
    except TrackLifecycleError as e:
        db.session.rollback()
        log.error(e)
        stats.increment(
            metric_name=f"{metric_prefix}.transaction",
            pod_name=stats.PodNames.ENROLLMENTS,
            tags=["status:known_error"],
        )
        if not isinstance(e, failure_error_types):
            success = True
    # TODO: [Track] Phase 3 - drop this.
    except ProgramLifecycleError as e:
        db.session.rollback()
        log.log(e.log_level, e)
        stats.increment(
            metric_name=f"{metric_prefix}.transaction",
            pod_name=stats.PodNames.ENROLLMENTS,
            tags=["status:known_error"],
        )
    except Exception as e:
        db.session.rollback()
        log.exception(
            "Unhandled exception occurred while terminating or auto-transitioning member track.",
            exception=e,
            member_track_id=track.id,
        )
        stats.increment(
            metric_name=f"{metric_prefix}.transaction",
            pod_name=stats.PodNames.ENROLLMENTS,
            tags=["status:unexpected_error"],
        )

    return success


def get_active_track_query():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return db.session.query(MemberTrack).filter(
        MemberTrack.active, MemberTrack.user_id != 0, MemberTrack.client_track_id != 0
    )


def get_active_track_query_count():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return get_active_track_query().count()


@ignore_trace()
@job(team_ns="enrollments", service_ns="tracks")
def ensure_track_state_coordinator(
    chunk_size: int = 1_000,
) -> None:
    """
    This job coordinates creating `ensure_track_state` jobs which chunk the
    work load of process all active tracks
    """
    active_tracks_count = get_active_track_query_count()
    chunks = int(active_tracks_count / chunk_size) + 1

    log.info(
        "Coordinating creation of ensure_track_state jobs",
        active_tracks_count=active_tracks_count,
        chunks=chunks,
    )

    for chunk in range(chunks):
        ensure_track_state.delay(
            chunk=chunk,
            chunk_size=chunk_size,
        )


@ignore_trace()
@job(team_ns="enrollments", service_ns="tracks")
def ensure_track_state(chunk: int = 0, chunk_size: int = 1_000) -> None:
    """
    This job calls check_track_state in Tracks lifecycle to ensure the user is in
    the correct track and has the correct anchor date. It also updates the phase
    of the legacy program.
    """
    log.info(
        "Checking track states of active MemberTracks.",
        chunk=chunk,
        chunk_size=chunk_size,
    )

    active_tracks = (
        get_active_track_query()
        .order_by(MemberTrack.id)
        .limit(chunk_size)
        .offset(chunk * chunk_size)
    )

    success = True
    for member_track in active_tracks:
        success &= handle_ensure_track_state(member_track)

    log.info(
        "Finished checking track states of active MemberTracks.",
        chunk=chunk,
        chunk_size=chunk_size,
    )

    # fail the job if there were any issues
    if not success:
        raise Exception("Error encountered while ensuring track state.")


def handle_ensure_track_state(
    member_track: MemberTrack,
) -> bool:
    metric_prefix = "api.tasks.tracks.ensure_track_state"

    success = False
    try:
        if check_track_state(
            member_track, change_reason=ChangeReason.ENSURE_JOB_CHECK_STATE
        ):
            db.session.commit()
        stats.increment(
            metric_name=f"{metric_prefix}.transaction",
            pod_name=stats.PodNames.ENROLLMENTS,
            tags=["status:complete"],
        )
        success = True
    except TrackLifecycleError as e:
        log.error(e)
        db.session.rollback()
        stats.increment(
            metric_name=f"{metric_prefix}.transaction",
            pod_name=stats.PodNames.ENROLLMENTS,
            tags=["status:known_error"],
        )
        if not isinstance(e, failure_error_types):
            success = True
    except ProgramLifecycleError as e:
        db.session.rollback()
        log.error(e)
        stats.increment(
            metric_name=f"{metric_prefix}.transaction",
            pod_name=stats.PodNames.ENROLLMENTS,
            tags=["status:known_error"],
        )
    except Exception as e:
        db.session.rollback()
        log.exception(
            "Unhandled exception occurred while checking track state",
            member_track_id=member_track.id,
            exception=e,
        )
        stats.increment(
            metric_name=f"{metric_prefix}.transaction",
            pod_name=stats.PodNames.ENROLLMENTS,
            tags=["status:unexpected_error"],
        )

    return success


@ignore_trace()
@job(team_ns="enrollments", service_ns="tracks")
def update_member_track_phase_history_coordinator(
    chunk_size: int = 1_000,
) -> None:
    """
    This job coordinates creating `update_member_track_phase_history` jobs which chunk the
    work load of process all active tracks
    """
    active_tracks_count = get_active_track_query_count()
    chunks = int(active_tracks_count / chunk_size) + 1

    log.info(
        "Coordinating creation of update_member_track_phase_history jobs",
        active_tracks_count=active_tracks_count,
        chunks=chunks,
    )

    for chunk in range(chunks):
        update_member_track_phase_history.delay(
            chunk=chunk,
            chunk_size=chunk_size,
        )


@ignore_trace()
@job(team_ns="enrollments", service_ns="tracks")
def update_member_track_phase_history(chunk: int = 0, chunk_size: int = 1_000) -> None:
    log.info(
        "Updating track phase history of active MemberTracks.",
        chunk=chunk,
        chunk_size=chunk_size,
    )

    active_tracks = (
        get_active_track_query()
        .order_by(MemberTrack.id)
        .limit(chunk_size)
        .offset(chunk * chunk_size)
    )

    success = True
    for member_track in active_tracks:
        success &= handle_update_member_track_phase_history(member_track)

    log.info(
        "Finished updating track phase history of active MemberTracks.",
        chunk=chunk,
        chunk_size=chunk_size,
    )

    # fail the job if there were any issues
    if not success:
        raise Exception("Error encountered while updating member track phase history.")


def handle_update_member_track_phase_history(
    member_track: MemberTrack,
) -> bool:
    metric_prefix = "api.tasks.tracks.update_member_track_phase_history"

    inserts = []
    updates = []

    success = False

    try:
        most_recent_phase = (
            MemberTrackPhaseReporting.query.filter(
                MemberTrackPhaseReporting.member_track_id == member_track.id
            )
            .order_by(MemberTrackPhaseReporting.started_at.desc())
            .first()
        )
        current_phase = member_track.current_phase
        current_phase_reporting = MemberTrackPhaseReporting(
            member_track_id=member_track.id,
            name=current_phase.name,
            started_at=current_phase.started_at,
            ended_at=current_phase.ended_at,
        )
        # If there is an existing phase see what we should update, if anything.
        if most_recent_phase:
            # If it's the same phase, we don't want to create a new one...
            if current_phase.name == most_recent_phase.name:
                # If the reported boundaries have changed, track that
                if (
                    current_phase.started_at != most_recent_phase.started_at
                    or current_phase.ended_at != most_recent_phase.ended_at
                ):
                    most_recent_phase.started_at = current_phase.started_at
                    most_recent_phase.ended_at = current_phase.ended_at
                    updates.append(most_recent_phase)
                # Then/else just move on, don't create a new phase
            else:
                # Otherwise track the end boundary, setting to the start of the current phase.
                most_recent_phase.ended_at = current_phase.started_at
                updates.append(most_recent_phase)
                inserts.append(current_phase_reporting)
        else:
            inserts.append(current_phase_reporting)

        if len(inserts) > 0:
            if not feature_flags.bool_variation(
                flag_key="kill-switch-braze-api-requests",
                default=not bool(os.environ.get("TESTING")),
            ):
                log.debug(
                    "Skipping update_current_track_phase request in when `kill-switch-braze-api-requests` flag is disabled."
                )
            else:
                update_current_track_phase.delay(
                    member_track.id,
                    caller="handle_update_member_track_phase_history",
                )

        log.info(
            "Found MemberTrackPhaseReporting records to process.",
            member_track_id=member_track.id,
            num_inserts=len(inserts),
            num_updates=len(updates),
        )

        db.session.add_all(chain(inserts, updates))
        db.session.commit()

        stats.increment(
            metric_name=f"{metric_prefix}.transaction",
            pod_name=stats.PodNames.ENROLLMENTS,
            tags=["status:complete"],
        )

        success = True
    except Exception as e:
        db.session.rollback()
        log.exception(
            "Unhandled exception occurred while updating member track phase history",
            exception=e,
            member_track_id=member_track.id,
        )
        stats.increment(
            metric_name=f"{metric_prefix}.transaction",
            pod_name=stats.PodNames.ENROLLMENTS,
            tags=["status:unexpected_error"],
        )

    return success


@job(team_ns="enrollments", service_ns="tracks")
def update_current_track_phase(
    track_id: int,
) -> None:
    track = MemberTrack.query.get(track_id)
    if not track:
        log.warning("Track id not found", member_track_id=track_id)
        return

    resp = braze.update_current_track_phase(track=track)

    if not resp or not resp.ok:
        raise Exception("Error encountered while updating current track phase.")
