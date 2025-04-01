from storage.connection import db
from utils.log import logger

log = logger(__name__)


def deactivate_ttc_and_partner_fertility(dry_run=True):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    ttc_result = db.session.execute(
        """
        UPDATE client_track
        SET active = 0
        WHERE track = 'trying_to_conceive' AND active = 1
        """
    )
    partner_fertility_result = db.session.execute(
        """
        UPDATE client_track
        SET active = 0
        WHERE track = 'partner_fertility' AND active = 1
        """
    )

    if dry_run:
        log.info(
            "Dry run of deactivating TTC and Partner Fertility client tracks",
            active_ttc_tracks=ttc_result.rowcount,
            active_partner_fertility_tracks=partner_fertility_result.rowcount,
        )
        db.session.rollback()
    else:
        log.info(
            "Deactivating TTC and Partner Fertility client tracks",
            active_ttc_tracks=ttc_result.rowcount,
            active_partner_fertility_tracks=partner_fertility_result.rowcount,
        )
        db.session.commit()
