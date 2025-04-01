from models.marketing import (
    Resource,
    ResourceConnectedContentTrackPhase,
    ResourceTrackPhase,
    resource_connected_content_phases,
    resource_phases,
)
from models.programs import Module, Phase
from models.tracks.phase import convert_legacy_phase_name
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def run_backfills(dry_run=True):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    backfill_resource_track_phases(dry_run)
    backfill_resource_connected_content_track_phases(dry_run)


def backfill_resource_track_phases(dry_run=True):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log.info("Starting backfill of resource_track_phases from resource_phases")

    # these are the values from the "old" table that we want to backfill into the "new" table.
    # gets tuples of (resource id, module name, phase name)
    resource_ids_with_track_phase_names = (
        db.session.query(Resource.id, Module.name, Phase.name)
        .select_from(Resource)
        .join(resource_phases, Resource.id == resource_phases.c.resource_id)
        .join(Phase, resource_phases.c.phase_id == Phase.id)
        .join(Module, Phase.module_id == Module.id)
        .all()
    )
    log.debug(
        f"Found {len(resource_ids_with_track_phase_names)} values in the original table"
    )

    # these are the existing values in the "new" table that we don't need to backfill again.
    # gets existing records in new table as (resource_id, track_name, phase_name) tuples
    existing_values_in_new_table = db.session.query(ResourceTrackPhase).all()
    log.debug(
        f"Found {len(existing_values_in_new_table)} values already in the new table"
    )

    values_to_insert = []
    for (resource_id, module_name, phase_name) in resource_ids_with_track_phase_names:
        if (resource_id, module_name, phase_name) in existing_values_in_new_table:
            continue

        values_to_insert.append(
            {
                "resource_id": resource_id,
                "track_name": module_name,
                "phase_name": convert_legacy_phase_name(phase_name, module_name),
            }
        )

    log.info(f"Found {len(values_to_insert)} values to insert")

    if dry_run:
        log.info("Running in dry run mode, not committing changes.")
    elif values_to_insert:
        log.info("Committing changes")
        db.session.bulk_insert_mappings(ResourceTrackPhase, values_to_insert)

        db.session.commit()

    log.info("Done backfilling resource_track_phases")


def backfill_resource_connected_content_track_phases(dry_run=True):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log.info(
        "Starting backfill of resource_connected_content_track_phases from resource_connected_content_phases"
    )

    # these are the values from the "old" table that we want to backfill into the "new" table.
    # gets tuples of (resource id, module name, phase name)
    values_to_insert = (
        db.session.query(Resource.id, Module.name, Phase.name)
        .select_from(Resource)
        .join(
            resource_connected_content_phases,
            Resource.id == resource_connected_content_phases.c.resource_id,
        )
        .join(Phase, resource_connected_content_phases.c.phase_id == Phase.id)
        .join(Module, Phase.module_id == Module.id)
        .all()
    )
    log.debug(f"Found {len(values_to_insert)} values to insert")

    if dry_run:
        log.info("Running in dry run mode, not committing changes.")
    elif values_to_insert:
        db.session.execute("TRUNCATE TABLE resource_connected_content_track_phases")
        log.info("Committing changes.")
        insert_mappings = [
            {"resource_id": id, "track_name": track_name, "phase_name": phase_name}
            for (id, track_name, phase_name) in values_to_insert
        ]
        db.session.bulk_insert_mappings(
            ResourceConnectedContentTrackPhase, insert_mappings
        )

        db.session.commit()

    log.info("Done backfilling resource_connected_content_track_phases")
