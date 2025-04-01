import datetime

import ddtrace
from sqlalchemy import func

import eligibility
from activity import service
from common import stats
from eligibility import EnterpriseVerificationService
from models.tracks import (
    ChangeReason,
    ClientTrack,
    MemberTrack,
    TrackLifecycleError,
    get_renewable_tracks,
    renew,
)
from storage.connection import db
from tasks.queues import job
from utils.log import logger

log = logger(__name__)

METRIC_NAME = "api.tasks.tracks.find_tracks_qualified_for_opt_out_renewals"


@job(team_ns="enrollments", service_ns="tracks")
def find_tracks_qualified_for_opt_out_renewals():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    This job will set the `MemberTrack.qualified_for_optout` field when the appropriate conditions are met.

    Conditions:
      - Track is ending in exactly 30 days
      - Track is renewable
      - User is known to be eligible
      - User has logged in in the prior month
    """
    log.info("Finding tracks that are qualified for opt-out renewals.")

    renewable_tracks = [str(track) for track in get_renewable_tracks()]

    tracks = (
        db.session.query(MemberTrack)
        .join(ClientTrack, ClientTrack.id == MemberTrack.client_track_id)
        .filter(
            MemberTrack.active,
            MemberTrack.name.in_(renewable_tracks),
            func.adddate(MemberTrack.anchor_date, ClientTrack.length_in_days)
            <= func.adddate(func.now(), 30),
        )
    )

    tracks_ending_in_30_days = (
        t
        for t in tracks
        if t.get_scheduled_end_date()
        == datetime.datetime.utcnow().date() + datetime.timedelta(days=30)
        and t.is_eligible_for_renewal()
    )

    verification_service = eligibility.get_verification_service()

    today = datetime.datetime.utcnow().date()
    last_month = today - datetime.timedelta(days=30)

    for track in tracks_ending_in_30_days:
        process_track_for_opt_out_renewals(
            track=track,
            last_month=last_month,
            verification_service=verification_service,
        )


@ddtrace.tracer.wrap()
def process_track_for_opt_out_renewals(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    track: MemberTrack,
    last_month: datetime.date,
    verification_service: EnterpriseVerificationService,
):
    user = track.user

    log_ = log.bind(user_id=user.id, track_id=track.id)

    log_.info("Checking if user is known to be eligible")
    user_is_known_to_be_eligible = (
        verification_service.is_user_known_to_be_eligible_for_org(
            user_id=user.id,
            organization_id=track.organization.id,
            timeout=3,
        )
    )

    if not user_is_known_to_be_eligible:
        log_.info(
            "User is not known to be eligible and is not qualified for opt-out renewals",
        )
        stats.increment(
            metric_name=METRIC_NAME,
            pod_name=stats.PodNames.ENROLLMENTS,
            tags=["result:not_eligible"],
        )
        track.qualified_for_optout = False

    else:
        log_.info("User is eligible and qualified for opt-out renewals")

        user_activity_service = service.get_user_activity_service()
        last_login_date = user_activity_service.get_last_login_date(user_id=user.id)

        if not last_login_date or last_login_date < last_month:
            log_.info(
                "User does not meet the activity threshold to qualify for opt-out renewals"
            )
            stats.increment(
                metric_name=METRIC_NAME,
                pod_name=stats.PodNames.ENROLLMENTS,
                tags=["result:not_active"],
            )
            track.qualified_for_optout = False
        else:
            try:
                renew(
                    track=track,
                    is_auto_renewal=True,
                    change_reason=ChangeReason.OPT_OUT_JOB_RENEW,
                )
                track.qualified_for_optout = True

                stats.increment(
                    metric_name=METRIC_NAME,
                    pod_name=stats.PodNames.ENROLLMENTS,
                    tags=["result:scheduled_renewal"],
                )
            except TrackLifecycleError as e:
                db.session.rollback()
                log_.error(e)
                stats.increment(
                    metric_name=METRIC_NAME,
                    pod_name=stats.PodNames.ENROLLMENTS,
                    tags=["result:scheduled_renewal_error"],
                )
                track.qualified_for_optout = False

    db.session.add(track)
    db.session.commit()
