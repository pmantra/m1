from storage.connection import db
from utils.log import logger
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
)

log = logger(__name__)


def backfill_required_tracks(dry_run=True):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    settings = ReimbursementOrganizationSettings.query.all()
    for s in settings:
        if s.required_module_id:
            s.required_track = s.required_module.name

            if dry_run:
                log.debug(
                    "Setting required_track from required_module name.",
                    required_module_id=s.required_module_id,
                    required_track=s.required_module.name,
                )

    if dry_run:
        log.info("Dry-run mode, rolling back changes.")
        db.session.rollback()
    else:
        log.info("Committing changes.")
        db.session.commit()
