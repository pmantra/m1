# https://mavenclinic.atlassian.net/browse/BEX-4230
import click

from app import create_app
from storage.connection import db
from utils.log import logger

log = logger(__name__)


@click.option(
    "--dry-run",
    "-D",
    is_flag=True,
    help="Run the script but do not save the result in the database.",
)
def backfill(dry_run: bool = True):
    with create_app().app_context():
        update_query = "UPDATE bill SET status='REFUNDED' where id in (15584, 15607) and payor_type='CLINIC'"
        count_query = "SELECT ROW_COUNT() AS affected_rows"
        try:
            db.session.execute(update_query)
            affected_rows = db.session.execute(count_query).scalar()
            if affected_rows != 2:
                raise Exception(f"{affected_rows=} is not 2")
            if dry_run:
                log.info(
                    "Dry run requested. Rolling back changes.", count=affected_rows
                )
                db.session.rollback()
            else:
                log.info("Committing changes...", count=affected_rows)
                db.session.commit()
                log.info("Finished.")
        except Exception as ex:
            log.error("Error", ex=ex)
            db.session.rollback()


if __name__ == "__main__":
    backfill()
