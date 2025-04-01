from collections import defaultdict

from sqlalchemy import func

from models.tracks.member_track import MemberTrackPhaseReporting
from storage.connection import db


def run(dry_run=True):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    member_track_ids = find_tracks_with_duplicate_static_phases()
    print(f"Found {len(member_track_ids)} member tracks with duplicate static phases.")

    # Keep track of phase ids to delete across all tracks so we can do a single
    # delete query and commit at the end (when not in dry-run mode).
    deletes = []
    for mt_id in member_track_ids:
        deletes_for_track = repair_duplicate_static_phases(mt_id, dry_run=dry_run)
        deletes.extend(deletes_for_track)

    if dry_run:
        print("Dry run, rolling back!")
        db.session.rollback()
        print("Rolled back.")
    else:
        print(f"Deleting {len(deletes)} phases...")
        db.session.query(MemberTrackPhaseReporting).filter(
            MemberTrackPhaseReporting.id.in_(deletes)
        ).delete(synchronize_session="fetch")

        print("Committing changes!")
        db.session.commit()
        print("Committed changes.")
        print("Deleted phases with ids: ", deletes)


def _groupby(iterable, key):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    itertools.groupby requires the iterable to be sorted, because it
    only groups together consecutive elements with the same key.
    """
    groups = defaultdict(list)
    for element in iterable:
        groups[key(element)].append(element)
    return groups


def find_tracks_with_duplicate_static_phases():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    SELECT member_track_id
    FROM `maven-clinic-bi.api_data.ao_member_track_phase`
    WHERE name = "static"
    GROUP BY member_track_id, name, started_at
    HAVING COUNT(*) > 1
    """
    query = (
        db.session.query(MemberTrackPhaseReporting.member_track_id)
        .select_from(MemberTrackPhaseReporting)
        .group_by(
            MemberTrackPhaseReporting.member_track_id, MemberTrackPhaseReporting.name
        )
        .filter(MemberTrackPhaseReporting.name == "static")
        .having(func.count(MemberTrackPhaseReporting.id) > 1)
    )
    results = query.all()
    # convert single-element tuples like [(1, ), (2, )] to [1, 2]
    return [r for r, in results]


def repair_duplicate_static_phases(member_track_id, dry_run=True):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    print(f"Repairing phases for member track {member_track_id}")

    phases = MemberTrackPhaseReporting.query.filter(
        MemberTrackPhaseReporting.member_track_id == member_track_id
    ).all()

    # First, group the phases by the phase name.
    grouped_by_name = _groupby(phases, lambda p: p.name)

    ids_to_delete = []

    for name, phases_for_name in grouped_by_name.items():
        if dry_run:
            print(f"Found {len(phases_for_name)} phases with name {name}")
        if len(phases_for_name) == 1:
            continue

        # Group the phases (with the same name) by their start date.
        grouped_by_start_date = _groupby(phases_for_name, lambda p: p.started_at)

        if dry_run and len(grouped_by_start_date) > 1:
            print(f"Found multiple phases with name {name} and different start dates!")

        min_start_date = min(grouped_by_start_date.keys())
        for start_date, phases_for_start_date in grouped_by_start_date.items():
            if start_date > min_start_date:
                ids_to_delete.extend(p.id for p in phases_for_start_date)
            else:
                min_created_at = min(p.created_at for p in phases_for_start_date)
                min_phase_id = min(p.id for p in phases_for_start_date)

                assert (
                    next(
                        p for p in phases_for_start_date if p.id == min_phase_id
                    ).created_at
                    == min_created_at
                )
                ids_to_delete.extend(
                    p.id for p in phases_for_start_date if p.id != min_phase_id
                )

    if dry_run:
        print(f"Would DELETE {len(ids_to_delete)} phases: ", ids_to_delete)

    return ids_to_delete
