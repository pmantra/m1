"""
This script is intended to fix a specific issue affecting phase history reporting
for Pregnancy and Partner-Pregnant tracks between 12/17 - 12/22, 2020 (inclusive).
"""

from datetime import date, datetime, timedelta

from sqlalchemy import and_

from models.tracks.member_track import MemberTrack, MemberTrackPhaseReporting
from storage.connection import db

JOB_BUFFER = timedelta(minutes=10)

# The bug started in the cronjob at ran at 06:00 UTC on 12/17. See api/crontab.
BUG_STARTED_ON_DATE = date(2020, 12, 17)
BUG_STARTED_ON_TIME = datetime(2020, 12, 17, 6, 0, 0)

# The bug still was present during the 12/22 run, but fixed by the 12/23 run.
BUG_FIXED_AFTER_DATE = date(2020, 12, 22)
BUG_FIXED_AFTER_TIME = datetime(2020, 12, 22, 6, 0, 0) + JOB_BUFFER


"""
For each affected track:
1. Delete rows written during these dates.
2. Fix the ended_at time of the last phase to track.ended_at
"""


def run(dry_run=True):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    track_ids = find_tracks()
    print(f"Found {len(track_ids)} MemberTracks to fix.")

    errors = []
    for track_id in track_ids:
        try:
            fix_track(track_id, dry_run)

            if dry_run:
                print("Dry run, rolling back changes...")
                db.session.rollback()
                print("Rolled back.")
            else:
                print("Committing changes...")
                db.session.commit()
                print("Committed changes.")
        except:  # noqa  B001  TODO:  Do not use bare `except:`, it also catches unexpected events like memory errors, interrupts, system exit, and so on.  Prefer `except Exception:`.  If you're sure what you're doing, be explicit and write `except BaseException:`.
            print("Dry run, rolling back changes...")
            db.session.rollback()
            print("Rolled back.")

            errors.append(track_id)

    print(f"Error occurred for {len(errors)} out of {len(track_ids)} tracks.")
    print(errors)


def find_tracks():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    # TODO: there might be a few tracks that ended closer to 12/22,
    # so a correct new phase row was written on or after 12/17,
    # but incorrect data got written on the subsequent days.
    # It might be better to just address those individually...

    results = (
        db.session.query(MemberTrack.id)
        # all pregnancy (including partner) tracks that were already ended
        .filter(
            MemberTrack.name.in_(("pregnancy", "partner_pregnant")),
            MemberTrack.ended_at <= BUG_STARTED_ON_TIME,
        ).all()
    )
    tracks = [r.id for r in results]
    return tracks


def fix_track(member_track_id, dry_run=True):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    print(f"\n********** STARTING for MemberTrack {member_track_id} **********")

    # Step 1
    # Delete any phase history rows writen between 12/17-12/22 (inclusive).
    # These rows were created due to a bug and can just be deleted.
    # They are not in the BQ ao table because they were created using
    # bulk_insert_mappings, which doesn't trigger the export hook.
    deletes = MemberTrackPhaseReporting.query.filter(
        MemberTrackPhaseReporting.member_track_id == member_track_id,
        and_(
            MemberTrackPhaseReporting.created_at >= BUG_STARTED_ON_TIME,
            MemberTrackPhaseReporting.created_at <= BUG_FIXED_AFTER_TIME,
        ),
    ).all()

    if dry_run:
        print(
            f"Would DELETE these member_track_phase_rows for MemberTrack {member_track_id}"
            + "\nThese rows have most likely NOT been exported to BigQuery."
        )
        for d in deletes:
            print(_format_member_track_phase_reporting(d))

    for d in deletes:
        db.session.delete(d)

    # Step 2
    # Fix the ended_at date of the last phase before 12/17, which should match.
    # Find the latest (correct) phase whose ended_at is probably between 12/17-12/22
    # and reset the ended_at value back to the track end date.
    most_recent_phase = (
        MemberTrackPhaseReporting.query.filter(
            MemberTrackPhaseReporting.member_track_id == member_track_id
        )
        .filter(MemberTrackPhaseReporting.created_at < BUG_STARTED_ON_TIME)
        .order_by(MemberTrackPhaseReporting.started_at.desc())
        .first()
    )

    track_ended_at = MemberTrack.query.get(member_track_id).ended_at
    most_recent_phase.ended_at = track_ended_at

    if dry_run:
        print(
            f"Would UPDATE phase {most_recent_phase.id} {most_recent_phase.name} "
            + f"and set ended_at to: {track_ended_at}"
        )
        print(
            "Current state of this phase: "
            + _format_member_track_phase_reporting(most_recent_phase)
        )


def _format_member_track_phase_reporting(p):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return (
        f"ID: {p.id}, Member Track: {p.member_track_id}, Name: {p.name}, "
        + f"Started: {p.started_at}, Ended: {p.ended_at}, Created: {p.created_at}, Modified: {p.modified_at}"
    )
