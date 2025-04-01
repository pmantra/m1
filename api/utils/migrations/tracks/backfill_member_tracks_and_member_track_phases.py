# TODO: [Tracks] Remove after tracks refactor is over
import itertools
from collections import defaultdict
from datetime import date, timedelta
from typing import Dict

from sqlalchemy import func, tuple_
from sqlalchemy.orm import aliased

from models.enterprise import OrganizationEmployee, OrganizationModuleExtension
from models.programs import CareProgram, CareProgramPhase, Module, Phase
from models.tracks import TrackConfig, TrackName
from models.tracks.client_track import (  # type: ignore[attr-defined] # Module "models.tracks.client_track" has no attribute "TrackExtension"
    ClientTrack,
    TrackExtension,
)
from models.tracks.member_track import (
    MemberTrack,
    MemberTrackPhaseReporting,
    PregnancyMemberTrack,
)
from models.tracks.phase import convert_legacy_phase_name
from storage.connection import db
from utils.log import logger

from events_join_data.export_event_join_tables import (  # type: ignore[attr-defined] # Module "events_join_data.export_event_join_tables" has no attribute "export_member_track_phases" # isort: skip
    export_member_track_phases as export_member_track_phases_to_bq,
)
from events_join_data.export_event_join_tables import (  # type: ignore[attr-defined] # Module "events_join_data.export_event_join_tables" has no attribute "export_member_tracks" # isort: skip
    export_member_tracks as export_member_tracks_to_bq,
)

log = logger(__name__)
BOGUS_DATE = "3000-01-01 00:00:00"
ProgramHistoryT = Dict[int, Dict[str, str]]


def backfill_and_export_all(dry_run=True):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    backfill_member_tracks(dry_run)
    backfill_previous_and_bucket_member_track_ids(dry_run)
    backfill_member_track_phases(dry_run)
    export_tracks_to_bigquery()


def backfill_member_tracks(dry_run=True):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log_ = log.bind(dry_run=dry_run)
    log_.info("Starting member track backfill.")
    log_.info("Fetching care program splits.")
    splits = _care_program_splits()
    log_.info("Finished fetching care program splits.")
    # First, create any missing client tracks.
    log_.info("Locating missing client tracks.")
    client_track_inserts = []
    seen_client_tracks = set()
    legacy_program_history: ProgramHistoryT = defaultdict(dict)
    for split in splits:
        legacy_program_history[split.legacy_program_id][
            split.name
        ] = split.latest_phase_name
        client_track_key = (split.name, split.organization_id)
        if split.client_track_id or client_track_key in seen_client_tracks:
            continue
        seen_client_tracks.add(client_track_key)
        client_track_inserts.append(
            {
                "track": split.name,
                "organization_id": split.organization_id,
                "active": False,
            }
        )
    # If this isn't a dry run, actually commit the changes.
    inactive_client_tracks_by_key = {}
    log_.info("Found missing client tracks", number=len(client_track_inserts))
    if client_track_inserts and not dry_run:
        log_.info("Creating missing client tracks.")
        db.session.bulk_insert_mappings(ClientTrack, client_track_inserts)
        # Get a mapping of (track, organization_id) -> id
        inactive_client_tracks_by_key = {
            (ct.track, ct.organization_id): ct.id
            for ct in (
                db.session.query(
                    ClientTrack.id, ClientTrack.track, ClientTrack.organization_id
                )
                .filter(
                    tuple_(ClientTrack.track, ClientTrack.organization_id).in_(
                        seen_client_tracks
                    )
                )
                .all()
            )
        }
        log_.info(
            "Created client tracks and fetched ids.",
            number=len(inactive_client_tracks_by_key),
        )
    # Now, create/update the member tracks
    member_track_updates = []
    member_track_inserts = []
    log_.info("Sorting member tracks for inserts/updates.")
    for split in splits:
        member_track_mapping = split._asdict()
        member_track_mapping.update(
            anchor_date=_get_anchor_date(
                split=split, legacy_program_history=legacy_program_history
            )
        )
        client_track_key = (split.name, split.organization_id)
        if (
            not split.client_track_id
            and client_track_key in inactive_client_tracks_by_key
        ):
            member_track_mapping["client_track_id"] = inactive_client_tracks_by_key[
                client_track_key
            ]

        if split.id:  # Update
            member_track_updates.append(member_track_mapping)
        else:  # Create
            member_track_inserts.append(member_track_mapping)

    log_.info(
        "Fetched all member tracks to update and create.",
        num_update=len(member_track_updates),
        num_create=len(member_track_inserts),
    )
    if not dry_run:
        log_.info("Committing changes.")
        db.session.bulk_update_mappings(MemberTrack, member_track_updates)
        db.session.bulk_insert_mappings(MemberTrack, member_track_inserts)
        db.session.commit()
    else:
        db.session.rollback()


def backfill_previous_and_bucket_member_track_ids(dry_run=True):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log_ = log.bind(dry_run=dry_run)
    log_.info("Starting previous_member_track_id backfill.")

    member_tracks_query = (
        db.session.query(
            MemberTrack.user_id, MemberTrack.id, MemberTrack.name, MemberTrack.bucket_id
        )
        .order_by(MemberTrack.user_id, MemberTrack.anchor_date)
        .all()
    )

    # Group all of a user’s member tracks together by the user id, with member tracks
    # ordered by created_at.
    grouped = {
        user_id: list(member_tracks)
        for user_id, member_tracks in itertools.groupby(
            member_tracks_query, lambda t: t.user_id
        )
    }

    configured_transitions = _get_configured_transitions()

    update_rows = []
    for (
        user_id,  # noqa  B007  TODO:  Loop control variable 'user_id' not used within the loop body. If this is intended, start the name with an underscore.
        member_tracks,
    ) in grouped.items():
        if len(member_tracks) > 1:
            bucket_id = member_tracks[0].bucket_id
            for i, member_track in enumerate(member_tracks[1:], start=1):
                previous = member_tracks[i - 1]
                if (previous.name, member_track.name) in configured_transitions:
                    update_rows.append(
                        dict(
                            id=member_track.id,
                            previous_member_track_id=previous.id,
                            bucket_id=bucket_id,
                        )
                    )
                else:
                    bucket_id = member_track.bucket_id

    log_.info("Fetched all member tracks to update.", num_update=len(update_rows))

    if not dry_run:
        log_.info("Committing changes.")
        db.session.bulk_update_mappings(MemberTrack, update_rows)
        db.session.commit()


def _get_configured_transitions():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    transitions = set()
    for name in [*TrackName]:
        conf = TrackConfig.from_name(name)
        for transition in conf.transitions:
            transitions.add((conf.name.value, transition.name))
    return transitions


def _get_anchor_date(split, legacy_program_history: ProgramHistoryT) -> date:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    _PREG_LENGTH = int(PregnancyMemberTrack.PREGNANCY_DURATION / timedelta(weeks=1))

    phase = split.entry_phase_name
    started = split.created_at.date()
    # If we don't have a weekly track, just return the start date.
    if not phase.startswith("week"):
        return started
    # If we have a weekly track, we can figure out the "anchor date" retroactively
    # by extracting the week number from the phase
    # and subtracting that delta value from the "started" date.
    week = int(phase.rsplit("-", 1)[-1])
    # Legacy postpartum phases continue their counter from pregnancy
    # So we need to reset it.
    if split.name in {TrackName.POSTPARTUM, TrackName.PARTNER_NEWPARENT}:
        history = legacy_program_history[split.legacy_program_id]
        preg_length = _PREG_LENGTH
        # If this user transitioned from pregnancy,
        # get the actual length of the pregnancy track.
        # Handles late births and early births.
        pregnancy = (
            TrackName.PREGNANCY
            if split.name == TrackName.POSTPARTUM
            else TrackName.PARTNER_PREGNANT
        )
        if pregnancy in history:
            final_phase = history[pregnancy]
            preg_counter = final_phase.rsplit("-", 1)[-1]
            preg_length = int(preg_counter) if preg_counter.isdigit() else _PREG_LENGTH
        week -= preg_length
        # Can happen for an early birth.
        if week < 1:
            week = 1
    # Phases start at 1 but delta starts at 0!
    weeks = timedelta(weeks=week - 1)
    return started - weeks


def backfill_member_track_phases(dry_run=True):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log_ = log.bind(dry_run=dry_run)
    log_.info("Starting member track phase backfill.")

    log_.info("Fetching member track ids.")
    member_track_ids = {
        f"{x.legacy_program_id}{x.track_name}": x.id for x in _get_member_track_ids()
    }

    log_.info("Fetching care program phases.")
    old_phases = _care_program_phases()
    log_.info("Finished fetching care program phases.")

    member_track_phase_updates = []
    member_track_phase_inserts = []

    for phase in old_phases:
        member_track_phase_values = phase._asdict()
        member_track_phase_values["name"] = convert_legacy_phase_name(
            phase.phase_name, phase.module_name
        )
        member_track_phase_values["member_track_id"] = member_track_ids[
            f"{phase.program_id}{phase.module_name}"
        ]

        if phase.id:  # Update
            member_track_phase_updates.append(member_track_phase_values)
        else:  # Create
            member_track_phase_inserts.append(member_track_phase_values)

    log_.info(
        "Fetched all member track phases to update and create.",
        num_update=len(member_track_phase_updates),
        num_create=len(member_track_phase_inserts),
    )
    if not dry_run:
        log_.info("Committing changes.")
        db.session.bulk_update_mappings(
            MemberTrackPhaseReporting, member_track_phase_updates
        )
        db.session.bulk_insert_mappings(
            MemberTrackPhaseReporting, member_track_phase_inserts
        )
        db.session.commit()


def export_tracks_to_bigquery():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    log.info("Exporting member tracks to BigQuery.")
    export_member_tracks_to_bq.delay()

    log.info("Exporting member track phases to BigQuery.")
    export_member_track_phases_to_bq.delay()


def _get_member_track_ids():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return (
        db.session.query(
            MemberTrack.legacy_program_id,
            MemberTrack.name.label("track_name"),
            MemberTrack.id,
        )
        .select_from(MemberTrack)
        .all()
    )


def _care_program_splits_query():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    # We can only reliably query for an aggregated value and the group-by columns.
    # MySQL won't complain if you throw others into the mix,
    # but it'll just pick the first value it comes by with ordering.
    # Get the date of the initial care program phases for each module in a care program.
    initial_cpp_date = (
        db.session.query(
            CareProgramPhase.program_id,
            Phase.module_id,
            func.min(CareProgramPhase.started_at).label("module_started_at"),
        )
        .join(Phase, Phase.id == CareProgramPhase.phase_id)
        .group_by(CareProgramPhase.program_id, Phase.module_id)
        .order_by(CareProgramPhase.program_id, Phase.module_id)
        .subquery(name="initial_cpp_date")
    )
    # Using the module/program/module_started_at as inner join keys,
    # get the data we need for our split
    initial_cpp = (
        db.session.query(
            CareProgramPhase.id,
            CareProgramPhase.program_id,
            CareProgramPhase.started_at,
            Phase.module_id,
            Phase.name,
        )
        .join(Phase, Phase.id == CareProgramPhase.phase_id)
        .join(
            initial_cpp_date,
            tuple_(
                initial_cpp_date.c.program_id,
                initial_cpp_date.c.module_id,
                initial_cpp_date.c.module_started_at,
            )
            == tuple_(
                CareProgramPhase.program_id,
                Phase.module_id,
                CareProgramPhase.started_at,
            ),
        )
        .subquery(name="initial_cpp")
    )
    # Get the date of the last care program phase for each module in a care program
    # Coalesce NULL to a future date so they're not ignored (handles an active cpp)
    latest_cpp_date = (
        db.session.query(
            CareProgramPhase.program_id,
            Phase.module_id,
            func.max(func.coalesce(CareProgramPhase.ended_at, BOGUS_DATE)).label(
                "module_ended_at"
            ),
        )
        .join(Phase, Phase.id == CareProgramPhase.phase_id)
        .group_by(CareProgramPhase.program_id, Phase.module_id)
        .order_by(CareProgramPhase.program_id, Phase.module_id)
        .subquery(name="latest_cpp_date")
    )
    # Using the module/program/module_ended_at as inner join keys,
    # get the data we need for our split
    latest_cpp = (
        db.session.query(
            CareProgramPhase.id,
            CareProgramPhase.program_id,
            CareProgramPhase.ended_at,  # We can use the raw value here, not the coalesced
            Phase.module_id,
            Phase.name,
        )
        .join(Phase, Phase.id == CareProgramPhase.phase_id)
        .join(
            latest_cpp_date,
            tuple_(
                latest_cpp_date.c.program_id,
                latest_cpp_date.c.module_id,
                latest_cpp_date.c.module_ended_at,
            )
            == tuple_(
                CareProgramPhase.program_id,
                Phase.module_id,
                # Coalesce on the join to match the date query
                func.coalesce(CareProgramPhase.ended_at, BOGUS_DATE),
            ),
        )
        .subquery(name="latest_cpp")
    )
    # Finally, get whether this module was auto-transitioned.
    auto_cpp = (
        db.session.query(
            CareProgramPhase.program_id,
            Phase.module_id,
            func.max(CareProgramPhase.as_auto_transition).label("auto_transitioned"),
        )
        .join(Phase, Phase.id == CareProgramPhase.phase_id)
        .group_by(CareProgramPhase.program_id, Phase.module_id)
        .order_by(CareProgramPhase.program_id, Phase.module_id)
        .subquery(name="auto_cpp")
    )
    # Join in and select all the data!
    TargetModule = aliased(Module, name="target_module")

    query = (
        db.session.query(
            MemberTrack.id.label("id"),
            CareProgram.id.label("legacy_program_id"),
            CareProgram.user_id,
            CareProgram.organization_employee_id,
            OrganizationEmployee.organization_id,
            CareProgram.is_employee,
            TargetModule.name.label("transitioning_to"),
            Module.name.label("name"),
            Module.id.label("legacy_module_id"),
            ClientTrack.id.label("client_track_id"),
            auto_cpp.c.auto_transitioned,
            initial_cpp.c.started_at.label("created_at"),
            initial_cpp.c.name.label("entry_phase_name"),
            latest_cpp.c.ended_at,
            latest_cpp.c.name.label("latest_phase_name"),
            TrackExtension.id.label("track_extension_id"),
        )
        .select_from(CareProgram)
        .join(CareProgramPhase, CareProgramPhase.program_id == CareProgram.id)
        .join(Phase, CareProgramPhase.phase_id == Phase.id)
        .join(
            OrganizationEmployee,
            CareProgram.organization_employee_id == OrganizationEmployee.id,
        )
        .join(Module, Module.id == Phase.module_id)
        .join(
            initial_cpp,
            tuple_(CareProgram.id, Module.id)
            == tuple_(initial_cpp.c.program_id, initial_cpp.c.module_id),
        )
        .join(
            latest_cpp,
            tuple_(CareProgram.id, Module.id)
            == tuple_(latest_cpp.c.program_id, latest_cpp.c.module_id),
        )
        .join(
            auto_cpp,
            tuple_(CareProgram.id, Module.id)
            == tuple_(auto_cpp.c.program_id, auto_cpp.c.module_id),
        )
        .outerjoin(TargetModule, CareProgram.target_module_id == TargetModule.id)
        .outerjoin(
            ClientTrack,
            tuple_(Module.name, OrganizationEmployee.organization_id)
            == tuple_(ClientTrack.track, ClientTrack.organization_id),
        )
        .outerjoin(
            MemberTrack,
            tuple_(Module.id, CareProgram.id, CareProgram.user_id)
            == tuple_(
                MemberTrack.legacy_module_id,
                MemberTrack.legacy_program_id,
                MemberTrack.user_id,
            ),
        )
        .outerjoin(
            OrganizationModuleExtension,
            OrganizationModuleExtension.id
            == CareProgram.organization_module_extension_id,
        )
        .outerjoin(
            TrackExtension,
            tuple_(
                OrganizationModuleExtension.extension_days,
                func.lower(OrganizationModuleExtension.extension_logic),
            )
            == tuple_(TrackExtension.extension_days, TrackExtension.extension_logic),
        )
        .group_by(CareProgram.id, Module.id)
        .order_by(CareProgram.id, Module.id)
    )
    return query


def _care_program_splits():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    query = _care_program_splits_query()
    return query.all()


def _care_program_phases_query():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    query = (
        db.session.query(
            MemberTrackPhaseReporting.id,
            Phase.name.label("phase_name"),
            Module.name.label("module_name"),
            CareProgramPhase.started_at,
            CareProgramPhase.ended_at,
            CareProgramPhase.id.label("legacy_program_phase_id"),
            CareProgramPhase.program_id,
        )
        .select_from(CareProgramPhase)
        .join(Phase, Phase.id == CareProgramPhase.phase_id)
        .join(Module, Module.id == Phase.module_id)
        .outerjoin(
            MemberTrackPhaseReporting,
            MemberTrackPhaseReporting.legacy_program_phase_id == CareProgramPhase.id,
        )
        .order_by(CareProgramPhase.started_at)
    )
    return query


def _care_program_phases():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    query = _care_program_phases_query()
    return query.all()
