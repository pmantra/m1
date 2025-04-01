from storage.connection import db
from utils.log import logger

log = logger(__name__)


def backfill_em(force=False):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    # unpredictable results for users with multiple active tracks
    # (very few in prod, but many in qa...)
    result = db.session.execute(
        """
        UPDATE member_care_team
        JOIN member_track ON member_track.user_id = member_care_team.user_id
        SET json = CONCAT('{\"member_track_id\":', member_track.id, '}')
        WHERE member_track.ended_at IS NULL AND member_care_team.type = 'QUIZ';
        """
    )
    log.debug(
        f"""
        Backfilling {result.rowcount} rows in member_care_team with json
        including member_track_id for QUIZ types!!!
        """
    )

    if force == True:
        db.session.commit()
    else:
        log.debug("...But not committing.")
        db.session.rollback()
