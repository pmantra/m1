"""
This script is intended to delete MemberTrackPhaseReporting rows for
"end" phases in Pregnancy and Partner-Pregnant tracks that were
erroneously created starting on 12/17/2020.
"""

from models.tracks.member_track import MemberTrack, MemberTrackPhaseReporting
from storage.connection import db


def delete_end_phases(dry_run=True):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    phases_to_delete = (
        db.session.query(MemberTrackPhaseReporting)
        .join(MemberTrack)
        .filter(
            MemberTrack.name.in_(("pregnancy", "partner_pregnant")),
            MemberTrackPhaseReporting.name == "end",
        )
        .all()
    )

    for d in phases_to_delete:
        db.session.delete(d)

    print(f"Found {len(phases_to_delete)} phases to delete.")

    if dry_run:
        print("Dry run, rolling back changes...")
        db.session.rollback()
        print("Rolled back.")
    else:
        print("Committing changes...")
        db.session.commit()
        print("Committed changes.")
