"""
This script is intended to fix previous_member_track_id and bucket_id
on MemberTracks, if the values from the backfill were not correct.

See: /Users/peggyli/code/maven/api/utils/migrations/tracks/backfill_member_tracks_and_member_track_phases.py
"""

from datetime import timedelta

from models.tracks import TrackConfig, TrackName
from models.tracks.member_track import MemberTrack
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def fix_tracks_for_user(user_id, dry_run=True):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log.info("Checking tracks for user.", user_id=user_id, dry_run=dry_run)

    member_tracks = (
        db.session.query(
            MemberTrack.id,
            MemberTrack.name,
            MemberTrack.bucket_id,
            MemberTrack.previous_member_track_id,
            MemberTrack.created_at,
            MemberTrack.ended_at,
        )
        .filter(MemberTrack.user_id == user_id)
        .order_by(MemberTrack.created_at)
        .all()
    )

    configured_transitions = _get_configured_transitions()

    update_rows = []
    if len(member_tracks) > 1:
        bucket_id = member_tracks[0].bucket_id
        for i, member_track in enumerate(member_tracks[1:], start=1):
            previous = member_tracks[i - 1]

            # Check that a transition is configured between the previous and 'current' track,
            # and the previous track actually ended when the 'current' track started.
            if (previous.name, member_track.name) in configured_transitions and (
                previous.ended_at
                and member_track.created_at - previous.ended_at < timedelta(minutes=1)
            ):
                if (
                    member_track.previous_member_track_id != previous.id
                    or member_track.bucket_id != previous.bucket_id
                ):
                    update_rows.append(
                        dict(
                            id=member_track.id,
                            previous_member_track_id=previous.id,
                            bucket_id=bucket_id,
                        )
                    )
            else:
                bucket_id = member_track.bucket_id

    log.info("Found rows to update.", num_update=len(update_rows))

    if dry_run:
        log.debug(update_rows)

    if dry_run:
        log.debug("Dry run mode, rolling back...")
        db.session.rollback()
        log.info("Rolled back.")
    else:
        log.debug("Committing changes...")
        db.session.bulk_update_mappings(MemberTrack, update_rows)
        db.session.commit()
        log.info("Committed changes.")


def _get_configured_transitions():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    transitions = set()
    for name in [*TrackName]:
        conf = TrackConfig.from_name(name)
        for transition in conf.transitions:
            transitions.add((conf.name.value, transition.name))
    return transitions
