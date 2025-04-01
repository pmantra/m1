from models.programs import Module, module_vertical_groups
from models.tracks.vertical_groups import tracks_vertical_groups
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def backfill_tracks_vertical_groups(dry_run=True):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log.info(f"Starting backfill with dry_run={dry_run}")

    if not dry_run:
        db.session.execute(tracks_vertical_groups.delete())

    module_names_and_vertical_group_ids = (
        db.session.query(Module.name, module_vertical_groups.c.vertical_group_id)
        .select_from(Module)
        .join(module_vertical_groups)
        .all()
    )
    log.debug(
        f"Found {len(module_names_and_vertical_group_ids)} rows from module_vertical_groups"
    )

    db.session.execute(
        tracks_vertical_groups.insert().values(module_names_and_vertical_group_ids)
    )

    if not dry_run:
        log.info("Committing changes (dry_run=False)")
        db.session.commit()
    else:
        db.session.rollback()
