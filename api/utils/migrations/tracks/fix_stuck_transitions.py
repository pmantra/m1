"""
This script cancels tracks that are mid-transition if the associated user
is not eligible at the org of the target track
"""

import eligibility
from models import tracks
from models.tracks.member_track import ChangeReason, MemberTrack
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def fix_stuck_transitions(dry_run=True):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log.info(f"Dry run: {dry_run}")
    tracks_in_transition = (
        db.session.query(MemberTrack)
        .filter(MemberTrack.transitioning_to.isnot(None), MemberTrack.active == True)
        .all()
    )

    verification_svc: eligibility.EnterpriseVerificationService = (
        eligibility.get_verification_service()
    )

    log.info(f"Found {len(tracks_in_transition)} tracks in transition")
    cancelled = 0

    for track in tracks_in_transition:

        verification = verification_svc.get_verification_for_user_and_org(
            user_id=track.user.id, organization_id=track.client_track.organization_id
        )

        if not verification:
            if dry_run is False:
                cancel_transition(track)
            cancelled += 1
            log.info("No verification for user", user_id=track.user.id)

        elif not verification_svc.is_verification_active(verification=verification):
            if dry_run is False:
                cancel_transition(track)
            cancelled += 1
            log.info("Verification not active for user", user_id=track.user.id)

        elif verification.organization_id != track.client_track.organization_id:
            if dry_run is False:
                cancel_transition(track)
            cancelled += 1
            log.info(
                "Verification for user is for incorrect org",
                user_id=track.user.id,
                expected_org_id=track.client_track.organization_id,
                got_org_id=verification.organization_id,
            )

    log.info(f"Cancelled {cancelled} tracks")

    if dry_run:
        log.info("Dry run, rolling back changes...")
        db.session.rollback()
        log.info("Rolled back.")
    else:
        log.info("Committing changes...")
        db.session.commit()
        log.info("Committed changes.")


def cancel_transition(track):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    tracks.cancel_transition(
        track=track.user.current_member_track,
        change_reason=ChangeReason.MANUAL_UPDATE,
    )
